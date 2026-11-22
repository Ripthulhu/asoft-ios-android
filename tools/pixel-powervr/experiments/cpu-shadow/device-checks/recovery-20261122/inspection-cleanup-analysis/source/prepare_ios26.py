#!/usr/bin/env python3
"""Standalone, explicitly executed iOS26 preparation. Default: read-only plan.

The app is neither installed nor impersonated. Existing pinned helper bodies
and input decoders are used through a verified tooling bundle. Every guest disk
write goes to a fresh, owned stage disk/overlay; no successful predecessor is
reused for write. The two real iOS setup boots are explicit stage boundaries.
"""
import argparse
import contextlib
import ctypes
import fcntl
import hashlib
import io
import json
import mmap
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import stat
import struct
import subprocess
import sys
import tarfile
import time

import cold_boot_ios26 as cold
import prepare_ios26_stages as stages


SCHEMA = 1
TOOL_ENTRIES = {"qemu_img": "tools/qemu-img", "java_dex": "java/classes.dex",
                "native_unpack": "lib/libunpack.so", "helper_kernel": "helper/Image16k.gz",
                "helper_initrd": "helper/initrd.gz", "setup_manifest": "setup/asoft-setup.json"}
STANDALONE_SOURCE = ("prepare_ios26.py", "prepare_ios26_stages.py", "cold_boot_ios26.py", "cold_boot_dt.py")
BOOT_COMPLETE = {"boot_complete": False, "gpu_path_complete": False, "app_gate_changed": False}
ANDROID_RUNTIME_ENV = ("ANDROID_ROOT", "ANDROID_DATA", "ANDROID_ART_ROOT", "ANDROID_I18N_ROOT",
                       "ANDROID_RUNTIME_ROOT", "ANDROID_TZDATA_ROOT", "BOOTCLASSPATH",
                       "DEX2OATBOOTCLASSPATH", "SYSTEMSERVERCLASSPATH", "EXTERNAL_STORAGE", "ASEC_MOUNTPOINT")
RESUMABLE_DOWNLOADS = {"shared-fetch", "ios26-fetch"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def atomic_json(path, value):
    cold.save(path, value)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def contained(root, name):
    stages.relative(name)
    root = Path(root).absolute()
    if root.is_symlink() or root != root.resolve(strict=True):
        raise ValueError("symlink in owned root: " + str(root))
    path = root / name
    for parent in [path, *path.parents]:
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError("symlink in owned path: " + str(parent))
    if not path.resolve().is_relative_to(root):
        raise ValueError("path escapes owned root")
    return path


def validate_attempt_tree(attempt):
    """Decoder sidecars must be owned ordinary files too, not linked targets."""
    for path in (attempt, *attempt.rglob("*")):
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            raise ValueError("symlink or special file in resumable attempt: " + str(path))
        if stat.S_ISREG(mode) and path.stat().st_nlink != 1:
            raise ValueError("hard-linked file in resumable attempt: " + str(path))


def file_record(path, root):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size <= 0:
        raise ValueError("missing, empty, or symlink artifact: " + str(path))
    before = cold.readonly_identity(path)
    row = {"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": cold.sha(path)}
    if before != cold.readonly_identity(path):
        raise ValueError("artifact changed while hashing")
    if path.suffix == ".qcow2":
        chain = cold.qcow_chain(path)
        if any(not Path(item["path"]).is_relative_to(root) for item in chain):
            raise ValueError("backing disk escapes this preparation session")
        row["backing_chain"] = [Path(item["path"]).relative_to(root).as_posix() for item in chain]
    return row


def verify_artifact(record, root):
    path = contained(root, record["path"])
    if file_record(path, root) != record:
        raise ValueError("completed artifact changed: " + record["path"])
    return path


def verify_tools(root, expected):
    manifest_path = root / "tooling-manifest.json"
    if not re.fullmatch(r"[0-9a-f]{64}", expected or "") or cold.sha(manifest_path) != expected:
        raise ValueError("tooling manifest SHA256 must match its reviewed staging receipt")
    manifest = json.loads(manifest_path.read_text())
    if (manifest.get("schema") != 1 or manifest.get("kind") != "standalone_ios26_preparation_tools" or
            manifest.get("requires_qualified_qemu") is not True or manifest.get("entrypoints") != TOOL_ENTRIES):
        raise ValueError("unsupported tooling manifest or entrypoints")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("tooling manifest has no inventory")
    for name, record in files.items():
        path = contained(root, name)
        if (not path.is_file() or path.stat().st_size != record["bytes"] or
                stat.S_IMODE(path.stat().st_mode) != record["mode"] or cold.sha(path) != record["sha256"]):
            raise ValueError("tooling file mismatch: " + name)
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if actual != set(files) | {"tooling-manifest.json"} or any(p.is_symlink() for p in root.rglob("*")):
        raise ValueError("tooling has unchecked files or symlinks")
    if any(n.startswith("lib/libvulkan") or "qemu-system" in n for n in files):
        raise ValueError("tooling must not supply another QEMU or Vulkan loader")
    for name in TOOL_ENTRIES.values():
        if name not in files:
            raise ValueError("missing tooling entrypoint: " + name)
    return manifest


def same_runtime(package):
    core = json.loads((package / "core-fixture-build.json").read_text())
    qemu = json.loads((package / "qemu-build.json").read_text())
    result = {"archive_sha256": core["library"]["sha256"], "header_sha256": core["header"]["sha256"]}
    if (result["archive_sha256"] != qemu["runtime_archive_sha256"] or
            result["header_sha256"] != qemu["runtime_header_sha256"]):
        raise ValueError("core fixture and QEMU use different runtime archive/header")
    return result


def locale_config(args):
    if (not re.fullmatch(r"[A-Za-z0-9_+/-]+", args.timezone) or ".." in args.timezone or
            args.timezone.startswith("/") or not re.fullmatch(r"[A-Z]{2}|", args.region)):
        raise ValueError("invalid explicit timezone or region")
    return {"timezone": args.timezone, "region": args.region, "clock": args.clock}


def load_checkpoints(work, session):
    artifacts, completed, previous = {}, [], None
    if not work.exists():
        return artifacts, completed
    stored = work / "session.json"
    if not stored.exists():
        names = set(p.name for p in work.iterdir())
        if names and names != {"owner.lock"}:
            raise ValueError("work directory is not an empty or owned preparation session")
        return artifacts, completed
    if json.loads(stored.read_text()) != session:
        raise ValueError("session inputs/configuration changed; use a new work directory")
    if session["kind"] == "standalone_ios26_helper_smoke":
        if (work / "checkpoints").exists():
            raise ValueError("helper smoke must not contain setup checkpoints")
        return {}, []
    missing_seen = False
    for stage in stages.STAGES:
        path = work / "checkpoints" / (stage + ".json")
        if not path.exists():
            missing_seen = True
            continue
        if missing_seen or path.is_symlink():
            raise ValueError("checkpoint sequence is incomplete or symlinked")
        record = json.loads(path.read_text())
        if (record.get("schema") != SCHEMA or record.get("stage") != stage or
                record.get("session_sha256") != digest(session) or record.get("previous_sha256") != previous or
                record.get("status") != "STAGE_COMPLETE" or not isinstance(record.get("artifacts"), dict)):
            raise ValueError("invalid checkpoint: " + stage)
        for name, item in record["artifacts"].items():
            stages.relative(name)
            verify_artifact(item, work)
            artifacts[name] = item
        completed.append(stage)
        previous = cold.sha(path)
    return artifacts, completed


def preflight(args):
    for name in ("package", "qualification", "tooling", "tooling_sha256", "work"):
        if not getattr(args, name):
            raise ValueError("required argument --" + name.replace("_", "-"))
    package, tooling = Path(args.package).resolve(strict=True), Path(args.tooling).resolve(strict=True)
    qualification = Path(args.qualification).resolve(strict=True)
    work = Path(args.work).absolute()
    if work.is_symlink() or work != work.resolve() or any(c in str(work) for c in ",\r\n\x00"):
        raise ValueError("work must be a canonical path without symlinks or QEMU separators")
    if len(str(work)) > 55:
        raise ValueError("use a short work path (at most 55 characters) for QMP/console sockets")
    if not work.parent.is_dir() or any(work.is_relative_to(p) or p.is_relative_to(work) for p in (package, tooling, qualification.parent)):
        raise ValueError("work parent must exist, outside runtime/tooling/evidence trees")
    proof = cold.qualified_package(package, qualification)
    tools = verify_tools(tooling, args.tooling_sha256)
    manifest = json.loads((tooling / TOOL_ENTRIES["setup_manifest"]).read_text())
    if manifest.get("format") != 1 or manifest["os"]["ios26"]["build"] != "23G90":
        raise ValueError("this port requires the reviewed iOS26 23G90 setup manifest")
    for group in ("steps/ios26", "scripts/ios26"):
        if not any(n.startswith("setup/" + group + "/") for n in tools["files"]):
            raise ValueError("tooling lacks original " + group)
    for name in ("setup/phone/prelude.sh", "setup/phone/locale.py"):
        if name not in tools["files"]:
            raise ValueError("tooling lacks " + name)
    for stage in stages.STAGES:
        if stage not in stages.NETWORK | stages.GUEST_BOOTS | {"ios26-pack"}:
            if "setup/phone/jobs/" + stage + ".sh" not in tools["files"]:
                raise ValueError("tooling lacks helper job " + stage)
    source = Path(__file__).resolve().parent
    session = {"schema": SCHEMA, "kind": "standalone_ios26_helper_smoke" if args.helper_smoke else "standalone_ios26_preparation",
               "package": str(package), "qualification_file": str(qualification),
               "qualification": proof, "runtime": same_runtime(package), "tooling": str(tooling),
               "tooling_manifest_sha256": args.tooling_sha256,
               "setup_manifest_sha256": cold.sha(tooling / TOOL_ENTRIES["setup_manifest"]),
               "runner_sources": {n: cold.sha(source / n) for n in STANDALONE_SOURCE},
               "locale": locale_config(args), "helper_ram_mib": args.helper_ram_mib,
               "helper_vcpus": args.helper_vcpus, "timebase_hz": cold.TIMEBASE_HZ,
               "guest_ram_gib": 3, "native_required": True, "tcg_retry": False}
    artifacts, completed = load_checkpoints(work, session)
    remaining = [] if args.helper_smoke else [s for s in stages.STAGES[:stages.STAGES.index(args.through) + 1] if s not in completed]
    return {"schema": SCHEMA, "status": "PREFLIGHT_READY", **BOOT_COMPLETE, "work": str(work),
            "session": session, "manifest": manifest, "artifacts": artifacts, "completed": completed,
            "remaining": remaining, "through": None if args.helper_smoke else args.through, "helper_smoke": args.helper_smoke,
            "network_stages": [s for s in remaining if s in stages.NETWORK],
            "guest_boot_stages": [s for s in remaining if s in stages.GUEST_BOOTS],
            "additional_space_gb": {s: stages.SPACE_GB[s] + 1.5 for s in remaining},
            "execution_verified": False,
            "notes": ["Default planning starts nothing and writes nothing.",
                      "AEA key lookup may use the network during unpack/decrypt.",
                      "Every failed VM attempt remains separate; predecessors are preserved.",
                      "Helper RAM requires fresh MemAvailable >= RAM + 768 MiB.",
                      "Packed asset creation is not final cold-boot/UI qualification."]}


def recheck(plan):
    session = plan["session"]
    cold.recheck_package(session)
    verify_tools(Path(session["tooling"]), session["tooling_manifest_sha256"])
    source = Path(__file__).resolve().parent
    if {n: cold.sha(source / n) for n in STANDALONE_SOURCE} != session["runner_sources"]:
        raise ValueError("runner source changed during preparation")


@contextlib.contextmanager
def exclusive_session(plan):
    work = Path(plan["work"])
    work.mkdir(mode=0o700, exist_ok=True)
    lock = os.open(work / "owner.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("another preparation owner holds this work directory") from None
        stored = work / "session.json"
        if stored.exists():
            if json.loads(stored.read_text()) != plan["session"]:
                raise ValueError("session changed while acquiring exclusive ownership")
        else:
            if set(p.name for p in work.iterdir()) != {"owner.lock"}:
                raise ValueError("work directory gained unowned files before initialization")
            atomic_json(stored, plan["session"])
        folders = ("attempts",) if plan["session"]["kind"] == "standalone_ios26_helper_smoke" else ("checkpoints", "attempts")
        for name in folders:
            path = contained(work, name)
            path.mkdir(exist_ok=True)
        refuse_live_children(work)
        yield
    finally:
        os.close(lock)


def mem_available_mib():
    values = dict(re.findall(r"^(\w+):\s+(\d+) kB$", Path("/proc/meminfo").read_text(), re.M))
    return int(values["MemAvailable"]) // 1024


def require_memory(ram_mib):
    available = mem_available_mib()
    if available < ram_mib + 768:
        raise ValueError(f"not enough MemAvailable: {available} MiB; {ram_mib + 768} MiB required")
    return available


def pdeathsig(owner):
    def configure():
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(1, signal.SIGKILL, 0, 0, 0) or os.getppid() != owner:
            os._exit(120)
    return configure


def process_identity(pid):
    try:
        text = Path(f"/proc/{pid}/stat").read_text()
        # comm can contain spaces and parentheses; starttime is field 22.
        fields = text[text.rfind(")") + 2:].split()
        return {"pid": pid, "start_ticks": int(fields[19])}
    except FileNotFoundError:
        return None


def refuse_live_children(work):
    for path in (work / "attempts").glob("*/*.child.json"):
        recorded = json.loads(path.read_text())
        if process_identity(recorded["pid"]) == recorded:
            raise ValueError("previous attempt child is still alive; preserve it for owned cleanup: " + str(path))
    # A previous owner could die between spawn and its child-record fsync. Do
    # not race a still-live orphan that names this exact private attempt tree.
    marker = (str(work) + "/attempts/").encode()
    for process in Path("/proc").iterdir():
        if not process.name.isdigit():
            continue
        try:
            command = (process / "cmdline").read_bytes()
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if marker in command and (b"qemu-system-aarch64" in command or b"com.asoft.ios.PrepareInputs" in command):
            raise ValueError("live previous attempt process requires owned cleanup: PID " + process.name)


@contextlib.contextmanager
def cleanup_signals():
    previous = {s: signal.signal(s, signal.SIG_IGN) for s in (signal.SIGINT, signal.SIGTERM)}
    try:
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


def operation_name(directory, name):
    """Preserve every log/request when an interrupted input attempt resumes."""
    if not any(directory.glob(name + ".*")):
        return name
    index = 2
    while any(directory.glob(f"{name}-{index}.*")):
        index += 1
    return f"{name}-{index}"


def process_bounds(directory, args):
    logs = [p for p in directory.rglob("*") if p.is_file() and p.suffix in (".txt", ".log")]
    total = sum(p.stat().st_size for p in logs)
    free = shutil.disk_usage(directory).free
    if total > args.max_log_mib << 20 or free < args.min_free_mib << 20:
        raise RuntimeError("process log or free-space bound reached")
    return {"log_bytes": total, "free_bytes": free}


def finish_process(child):
    """Every wait/signal failure still reaches descendant reaping and reporting."""
    result = {"errors": [], "forced_process": False}
    try:
        if child is not None and child.poll() is None:
            try:
                child.terminate()
            except ProcessLookupError:
                pass
            except OSError as error:
                result["errors"].append("terminate: " + str(error))
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                result["forced_process"] = True
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except OSError as error:
                    result["errors"].append("owned group kill: " + str(error))
                finally:
                    try:
                        child.wait(timeout=5)
                    except subprocess.SubprocessError as error:
                        result["errors"].append("final wait: " + str(error))
            except subprocess.SubprocessError as error:
                result["errors"].append("wait: " + str(error))
    finally:
        result["exit_code"] = None if child is None else child.returncode
        try:
            result.update(cold.reap_owned())
        except Exception as error:
            result["echild"] = False
            result["errors"].append("reap: " + str(error))
    return result


def run_process(argv, env, directory, name, seconds, args):
    """Bounded non-VM tool; preserve logs and reap every owned process."""
    output = directory / (name + ".log")
    record = {"command": argv, "timeout_seconds": seconds, "started_utc": cold.utc()}
    child = None
    try:
        with output.open("xb") as stream:
            child = subprocess.Popen(argv, env=env, cwd=directory, stdin=subprocess.DEVNULL,
                                     stdout=stream, stderr=subprocess.STDOUT, start_new_session=True,
                                     preexec_fn=pdeathsig(os.getpid()))
        identity = process_identity(child.pid)
        if identity is not None:
            atomic_json(directory / (name + ".child.json"), identity)
        deadline, update = time.monotonic() + seconds, 0
        while child.poll() is None:
            now = time.monotonic()
            process_bounds(directory, args)
            if now >= deadline:
                raise TimeoutError(name + " deadline")
            if now >= update:
                print(json.dumps({"operation": name, "status": "RUNNING", "log_bytes": output.stat().st_size}), flush=True)
                update = now + 30
            time.sleep(0.2)
        if child.returncode:
            raise RuntimeError(name + " exited " + str(child.returncode))
    finally:
        try:
            with cleanup_signals():
                record["cleanup"] = finish_process(child)
        finally:
            record["finished_utc"] = cold.utc()
            atomic_json(directory / (name + ".process.json"), record)
    process_bounds(directory, args)
    cleanup = record["cleanup"]
    if (not cleanup["echild"] or cleanup.get("forced_descendants") or cleanup.get("forced_process") or cleanup["errors"]):
        raise RuntimeError(name + " did not complete clean owned cleanup")
    return cold.read_log(output, 4 << 20)


def image_tool(plan, argv, attempt, name, args, seconds=60):
    tooling = Path(plan["session"]["tooling"])
    env = {"PATH": "/system/bin", "LD_LIBRARY_PATH": str(tooling / "lib"), "TMPDIR": str(attempt)}
    return run_process([str(tooling / TOOL_ENTRIES["qemu_img"]), *argv], env, attempt, name, seconds, args)


def java_input(plan, request, attempt, name, args):
    tooling = Path(plan["session"]["tooling"])
    validate_attempt_tree(attempt)
    name = operation_name(attempt, name)
    result_file = attempt / "files" / "adapter-results" / (name + ".json")
    request = dict(request, schema=1, output_root=str(attempt / "files"), result_file=str(result_file))
    path = attempt / (name + ".request.json")
    atomic_json(path, request)
    env = {name: os.environ[name] for name in ANDROID_RUNTIME_ENV if name in os.environ}
    if not env.get("BOOTCLASSPATH"):
        raise ValueError("app_process requires this phone's BOOTCLASSPATH runtime environment")
    env.update(PATH="/system/bin", CLASSPATH=str(tooling / TOOL_ENTRIES["java_dex"]),
               LD_LIBRARY_PATH=str(tooling / "lib"), TMPDIR=str(attempt))
    argv = ["/system/bin/app_process", "-Xmx768m", "-Djava.library.path=" + str(tooling / "lib"),
            "/system/bin", "com.asoft.ios.PrepareInputs", str(path)]
    run_process(argv, env, attempt, name, args.input_seconds, args)
    # app_process may redirect its standard streams through RuntimeInit.
    # Completion is an owned fresh JSON file, never inferred from exit 0.
    if (not result_file.is_file() or result_file.is_symlink() or result_file.stat().st_size > (1 << 20) or
            json.loads(result_file.read_text()).get("status") != "COMPLETE"):
        raise ValueError("input adapter returned no complete result")


def source_path(plan, logical):
    if logical not in plan["artifacts"]:
        raise ValueError("missing predecessor artifact: " + logical)
    return contained(Path(plan["work"]), plan["artifacts"][logical]["path"])


def output_path(attempt, logical):
    path = contained(attempt / "files", logical)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def output_records(attempt, work, names):
    result = {}
    for name in names:
        path = contained(attempt / "files", name)
        if path.is_dir():
            children = sorted(path.rglob("*"))
            files = [p for p in children if p.is_file()]
            if not files or any(p.is_symlink() for p in children):
                raise ValueError("empty or symlink output tree: " + name)
            for item in files:
                logical = item.relative_to(attempt / "files").as_posix()
                result[logical] = file_record(item, work)
        else:
            result[name] = file_record(path, work)
    return result


def fetch_stage(plan, stage, attempt, args):
    config = stages.downloads(plan["manifest"], stage == "shared-fetch")
    names = []
    for index, (entry, logical) in enumerate(config["urls"]):
        target = output_path(attempt, logical)
        java_input(plan, {"op": "url", "source": entry["url"], "sha256": entry["sha256"], "output": str(target)},
                   attempt, "url-" + str(index), args)
        names.append(logical)
    members = []
    for entry, logical in config["members"]:
        row = {key: entry[key] for key in ("name", "bytes", "method", "zipBytes", "crc32") if key in entry}
        row["output"] = str(output_path(attempt, logical))
        members.append(row)
        names.append(logical)
    request = {"op": "members", "source": config["source"]["url"], "members": members}
    if "bytes" in config["source"]:
        request["source_bytes"] = config["source"]["bytes"]
    java_input(plan, request, attempt, "members", args)
    return names


def unpack_stage(plan, stage, attempt, args):
    names = []
    for index, (op, source, logical) in enumerate(stages.unpack_operations(plan["manifest"], stage == "shared-unpack")):
        path = source_path(plan, source)
        target = output_path(attempt, logical)
        if target.exists() or Path(str(target) + ".progress").exists():
            raise ValueError("unpack/decrypt outputs must be fresh; preserve the failed attempt")
        request = {"op": op, "input": str(path), "input_sha256": plan["artifacts"][source]["sha256"], "output": str(target)}
        if op == "aea":
            request.update(keys=plan["manifest"]["shared"]["files"]["fcsKeys"],
                           key_cache=str(attempt / "files" / "key-cache"))
        java_input(plan, request, attempt, "unpack-" + str(index), args)
        names.append(logical)
    if stage == "shared-unpack":
        kernel = attempt / "files/cloud/kernelcache.research.vphone600.decompressed"
        with kernel.open("rb") as stream:
            if stream.read(4) != b"\xcf\xfa\xed\xfe":
                raise ValueError("unpacked research kernel is not the expected Mach-O")
        shutil.copyfile(attempt / "files/cloud/vphone600ap.adt", output_path(attempt, "fw/dtree.orig"))
        names.append("fw/dtree.orig")
    return names


def create_disk(plan, attempt, logical, args, source=None, size=None, name="disk"):
    target = output_path(attempt, logical)
    if target.exists():
        raise ValueError("refusing to overwrite an attempt disk")
    argv = ["create", "-q", "-f", "qcow2"]
    if source:
        chain = cold.qcow_chain(source)
        argv += ["-F", "qcow2", "-b", str(source), str(target)]
    else:
        if not isinstance(size, int) or not 0 < size <= 128 << 30:
            raise ValueError("invalid new disk size")
        argv += [str(target), str(size)]
    image_tool(plan, argv, attempt, "create-" + name, args)
    if source and [r["path"] for r in cold.qcow_chain(target)][1:] != [r["path"] for r in chain]:
        raise ValueError("new overlay has a different backing chain")
    return target


def validate_tar_headers(stream, size):
    """Preflight headers before tarfile can allocate a GNU/PAX extension body."""
    position, count = 0, 0
    while position + 1024 <= size:
        stream.seek(position)
        header = stream.read(512)
        if header == b"\0" * 512:
            left = size - position - 512
            while left:
                block = stream.read(min(left, 1 << 20))
                if not block or any(block):
                    raise ValueError("nonzero or truncated returned tar trailer")
                left -= len(block)
            return
        count += 1
        if count > 16384 or len(header) != 512:
            raise ValueError("excessive or truncated returned tar headers")
        try:
            length = int(header[124:136].rstrip(b"\0 ").lstrip(b" ") or b"0", 8)
            checksum = int(header[148:156].rstrip(b"\0 ").lstrip(b" ") or b"0", 8)
        except ValueError:
            raise ValueError("unsupported returned tar numeric encoding") from None
        if checksum != sum(header[:148]) + 8 * 32 + sum(header[156:]):
            raise ValueError("returned tar header checksum mismatch")
        kind = header[156:157]
        if kind not in (b"0", b"\0", b"5", b"L"):
            raise ValueError("unsupported returned tar link/sparse/extended header")
        if length < 0 or (kind == b"5" and length) or (kind == b"L" and not 1 <= length <= 4096):
            raise ValueError("invalid returned tar member/longname size")
        position += 512 + ((length + 511) // 512) * 512
        if position > size - 1024:
            raise ValueError("returned tar member exceeds reported output length")
    raise ValueError("returned tar lacks complete terminal records")


class BoundedReader:
    def __init__(self, stream, size):
        self.stream, self.size = stream, size

    def read(self, count=-1):
        remaining = self.size - self.stream.tell()
        return self.stream.read(remaining if count < 0 else min(count, remaining))

    def tell(self):
        return self.stream.tell()

    def seek(self, offset, whence=0):
        absolute = offset if whence == 0 else self.tell() + offset if whence == 1 else self.size + offset
        if not 0 <= absolute <= self.size:
            raise ValueError("returned tar read escapes reported length")
        return self.stream.seek(absolute)


def safe_return_tar(raw, size, destination, expected):
    """Extract only complete regular-file results; never trust helper paths/links."""
    if size < 1024 or size > raw.stat().st_size or size % 512:
        raise ValueError("invalid helper output length")
    with raw.open("rb") as stream:
        validate_tar_headers(stream, size)
    names, regular = set(), set()
    with raw.open("rb") as stream, tarfile.open(fileobj=BoundedReader(stream, size), mode="r:") as archive:
        for member in archive:
            name = member.name.rstrip("/")
            stages.relative(name)
            if name in names or not any(name == p or name.startswith(p + "/") for p in expected):
                raise ValueError("unexpected or repeated helper output: " + name)
            names.add(name)
            if member.offset_data + member.size > size - 1024 or not (member.isfile() or member.isdir()):
                raise ValueError("truncated, linked, or special helper output")
            path = contained(destination, name)
            if member.isdir():
                path.mkdir(parents=True, exist_ok=True)
                continue
            if member.size <= 0:
                raise ValueError("empty helper output: " + name)
            path.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source, path.open("xb") as out:
                shutil.copyfileobj(source, out, 1 << 20)
                out.flush()
                os.fsync(out.fileno())
            if path.stat().st_size != member.size:
                raise ValueError("short helper output")
            regular.add(name)
    if not all(any(n == p or n.startswith(p + "/") for n in regular) for p in expected):
        raise ValueError("helper result is missing an expected nonempty output")
    return regular


def input_tar(plan, recipe, attempt, disk_rows, authored_script=None):
    tooling = Path(plan["session"]["tooling"])
    values = stages.variables(plan["manifest"], plan["session"]["locale"])
    text = {".job/run": "run.sh\n", ".job/disks": "".join(f"d{i} {r['at']}\n" for i, r in enumerate(disk_rows)),
            ".job/out": "".join(n + "\n" for n in recipe["out"]),
            ".job/scratch": "".join(n + "\n" for n in recipe["scratch"])}
    text["run.sh"] = (authored_script if authored_script is not None else
                      "export ASOFT_S=scripts\n" + (tooling / "setup/phone/prelude.sh").read_text() + "\n" +
                      stages.fill((tooling / ("setup/phone/jobs/" + recipe["name"] + ".sh")).read_text(), values))
    files = {}
    for group, target in (() if authored_script is not None else (("steps", "steps"), ("scripts", "scripts"))):
        for path in sorted((tooling / "setup" / group / "ios26").iterdir()):
            if not path.is_file():
                raise ValueError("unexpected nested imported script directory")
            name = target + "/" + path.name
            if group == "steps":
                text[name] = stages.fill(path.read_text(), values)
            else:
                files[name] = path
    if authored_script is None:
        files["phone/locale.py"] = tooling / "setup/phone/locale.py"
    for logical in recipe["files"]:
        selected = {n: r for n, r in plan["artifacts"].items() if n == logical or n.startswith(logical + "/")}
        if not selected:
            raise ValueError("missing helper input: " + logical)
        for name in selected:
            if name in files or name in text:
                raise ValueError("helper input shadows a script")
            files[name] = source_path(plan, name)
    path = attempt / "in.tar"
    with tarfile.open(path, "w", format=tarfile.USTAR_FORMAT) as archive:
        for name in sorted(text):
            data = text[name].encode()
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), 0o755 if name.endswith(".sh") else 0o644
            archive.addfile(info, io.BytesIO(data))
        for name, source in sorted(files.items()):
            info = tarfile.TarInfo(name)
            info.size, info.mode = source.stat().st_size, 0o755 if name.endswith(".sh") else 0o644
            with source.open("rb") as stream:
                archive.addfile(info, stream)
    return path


def helper_command(plan, attempt, disks):
    session = plan["session"]
    ram, cpus = session["helper_ram_mib"], session["helper_vcpus"]
    tooling, package = Path(session["tooling"]), Path(session["package"])
    argv = [str(package / "qemu-system-aarch64"), "-name", "iOS26 preparation helper",
            "-M", "virt,gic-version=3,memory-backend=m0", "-object", f"memory-backend-memfd,id=m0,size={ram}M,share=on",
            "-cpu", "cortex-a76,x-host-counter=on,cntfrq=38400000", "-smp", str(cpus), "-m", str(ram) + "M",
            "-accel", "tcg,thread=multi,tb-size=256", "-kernel", str(tooling / TOOL_ENTRIES["helper_kernel"]),
            "-initrd", str(tooling / TOOL_ENTRIES["helper_initrd"]), "-append", "console=ttyAMA0 loglevel=4 asoft.job=run",
            "-display", "none", "-monitor", "none", "-parallel", "none", "-no-reboot", "-nic", "none",
            "-serial", "file:" + str(attempt / "serial.txt"), "-qmp", "unix:" + str(attempt / "qmp.sock") + ",server,nowait"]
    for disk in disks:
        path = str(disk["path"])
        if any(c in path for c in ",\n\r\x00"):
            raise ValueError("disk path contains QEMU separators")
        argv += ["-drive", f"file={path},format={disk['format']},if=none,id={disk['serial']},cache=writeback" +
                 (",readonly=on" if disk["readonly"] else ""),
                 "-device", f"virtio-blk-device,drive={disk['serial']},serial={disk['serial']}"]
    env = {"PATH": "/system/bin", "LD_LIBRARY_PATH": str(package / "lib"), "TMPDIR": str(attempt),
           "ASOFT_PAGE_BITS": "14", "ASOFT_NATIVE_EL0": "1", "ASOFT_NATIVE_EL0_REQUIRED": "1",
           # Linux uses its ordinary writable TPIDR_EL0 TLS. The iOS CPU-hint
           # TPIDRRO swap must remain absent from this native helper contract.
           "ASOFT_NATIVE_EL0_STUBS": "8", "ASOFT_NATIVE_EL0_DELAY_MS": "0",
           "ASOFT_NATIVE_EL0_PAC": "off", "ASOFT_NATIVE_EL0_STATS": "1", "ASOFT_EL_SAMPLER": "30"}
    return argv, env


def vm_success(result, helper):
    cleanup, witness = result.get("cleanup", {}), result.get("witnesses", {})
    clean = (cleanup.get("exit_code") == 0 and cleanup.get("echild") and not cleanup.get("forced_qemu") and
             not cleanup.get("forced_descendants") and not cleanup.get("errors") and not result.get("error"))
    native = witness.get("native_initialization") and witness.get("native_execution") and not witness.get("fatal_markers")
    if helper:
        return bool(clean and native and result.get("natural_exit") and result.get("done_codes") == [0])
    return bool(clean and native and cleanup.get("stop_flushed") and result.get("milestone") and result.get("settled") and
                (result["stage"] == "ios26-firstboot" or witness.get("gpu_execution") and witness.get("frame_captured")))


class GuestConsole:
    """Nonblocking console draining; command echo cannot satisfy split markers."""
    def __init__(self, path):
        self.path, self.socket, self.buffer, self.pending = path, None, b"", None

    def poll(self):
        if self.socket is None and self.path.exists():
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.socket.settimeout(1)
            try:
                self.socket.connect(str(self.path))
                self.socket.setblocking(False)
            except BaseException:
                self.close()
                raise
        if self.socket is None:
            return None
        # Return regularly to the owner even under a continuously busy serial
        # stream, so deadline/storage/memory checks cannot be starved.
        for _ in range(4):
            try:
                data = self.socket.recv(65536)
            except BlockingIOError:
                break
            if not data:
                self.close()
                return None
            self.buffer = (self.buffer + data)[-(4 << 20):]
        if self.pending:
            start, end = self.pending
            begin, finish = self.buffer.find(start), self.buffer.find(end)
            if begin >= 0 and finish > begin:
                answer = self.buffer[begin + len(start):finish].decode(errors="replace")
                self.buffer, self.pending = self.buffer[finish + len(end):], None
                return answer
        return None

    def send(self, command):
        if self.socket is None:
            return False
        tag = "P" + os.urandom(8).hex()
        start, end = ("@@" + tag + "S@@").encode(), ("@@" + tag + "E@@").encode()
        wire = ('\x03\x15\recho @@' + tag + '"S"@@; ' + command + '; echo @@' + tag + '"E"@@\r').encode()
        self.socket.settimeout(1)
        try:
            self.socket.sendall(wire)
        finally:
            self.socket.setblocking(False)
        self.pending = (start, end)
        return True

    def close(self):
        if self.socket is not None:
            self.socket.close()
        self.socket, self.pending = None, None


def supervise_vm(plan, stage, attempt, argv, env, args, frame=None):
    helper = frame is None
    result = {"schema": SCHEMA, "stage": stage, "started_utc": cold.utc(), "qmp": [], "frames": [],
              "status": "INCOMPLETE", "natural_exit": False, **BOOT_COMPLETE}
    child = qmp = console = None
    max_seconds = (args.smoke_seconds if stage == "helper-smoke" else args.helper_seconds) if helper else stages.boot_inputs(stage)["deadline_seconds"]
    done_at = milestone_at = None
    next_capture = next_poll = next_report = 0
    settled = False
    try:
        require_memory(plan["session"]["helper_ram_mib"] if helper else 3072)
        recheck(plan)
        atomic_json(attempt / "launch.json", {"command": argv, "environment": env, "deadline_seconds": max_seconds})
        with (attempt / "qemu-stderr.txt").open("xb") as stream:
            child = subprocess.Popen(argv, env=env, cwd=attempt, stdin=subprocess.DEVNULL, stdout=stream,
                                     stderr=subprocess.STDOUT, pass_fds=(() if helper else (frame[0],)),
                                     start_new_session=True, preexec_fn=pdeathsig(os.getpid()))
        identity = process_identity(child.pid)
        if identity is not None:
            atomic_json(attempt / "vm.child.json", identity)
        started = time.monotonic()
        console = None if helper else GuestConsole(attempt / "console.sock")
        while child.poll() is None:
            now = time.monotonic()
            if now - started > max_seconds:
                raise TimeoutError("VM stage deadline")
            if qmp is None and (attempt / "qmp.sock").exists():
                qmp = cold.Qmp(attempt / "qmp.sock", result["qmp"])
            if console:
                answer = console.poll()
                if answer is not None:
                    result["last_console_answer"] = answer[-4096:]
                    ready = any(line.strip() == "__READY__" for line in answer.splitlines()) if stage == "ios26-firstboot" else "LastSystemVersion" in answer
                    if ready and milestone_at is None:
                        milestone_at = now
                        result["milestone"] = True
                        result["milestone_elapsed_seconds"] = now - started
                    if settled and "__SYNCED__" in answer:
                        result["guest_sync_answered"] = True
                        break
                if milestone_at is not None and now - milestone_at >= stages.boot_inputs(stage)["settle_seconds"]:
                    settled = result["settled"] = True
                if now >= next_poll:
                    command = ("sync; echo __SYNCED__" if settled else
                               "test -e /private/var/keybags/persona.kb && test -e /private/var/keybags/usersession.kb && echo __READY__ || echo __WAIT__"
                               if stage == "ios26-firstboot" else "cat /var/mobile/Library/Preferences/com.apple.migration.plist")
                    if console.send(command):
                        next_poll = now + 90
                if settled and now - milestone_at >= stages.boot_inputs(stage)["settle_seconds"] + 180:
                    result["guest_sync_answered"] = False
                    break  # QMP stop/flush remains mandatory in final cleanup.
            if frame and now >= next_capture:
                name = "frame-latest.png"
                result["frames"] = [cold.frame_capture(frame[1], 1179, 2556, attempt / name)]
                next_capture = now + 60
            if now >= next_report:
                result["storage"] = process_bounds(attempt, args)
                if mem_available_mib() < args.min_available_mib:
                    raise RuntimeError("VM low-memory stop bound")
                stderr = cold.read_log(attempt / "qemu-stderr.txt", args.max_log_mib << 20)
                serial = cold.read_log(attempt / "serial.txt", args.max_log_mib << 20)
                result["witnesses"] = cold.evidence(stderr, serial, result["frames"], [])
                if result["witnesses"]["fatal_markers"]:
                    raise RuntimeError("native/guest fatal marker")
                codes = [int(n) for n in re.findall(r"^ASOFT: done (-?\d+)\s*$", serial, re.M)]
                if helper and codes:
                    if codes != [0]:
                        raise RuntimeError("helper reported failure or repeated completion")
                    done_at = done_at or now
                    if now - done_at > 15:
                        raise RuntimeError("helper did not power off after completion")
                result["elapsed_seconds"] = now - started
                atomic_json(attempt / "vm-result.json", result)
                print(json.dumps({"stage": stage, "elapsed_seconds": round(now - started), "witnesses": result["witnesses"]}), flush=True)
                next_report = now + 10
            time.sleep(0.1)
        result["natural_exit"] = child.poll() is not None
    except BaseException as error:
        result["error"] = type(error).__name__ + ": " + str(error)
    finally:
        with cleanup_signals():
            try:
                if console:
                    console.close()
            finally:
                if child is not None:
                    result["cleanup"] = cold.shutdown(child, qmp)
                else:
                    result["cleanup"] = cold.reap_owned()
        stderr = cold.read_log(attempt / "qemu-stderr.txt", args.max_log_mib << 20)
        serial = cold.read_log(attempt / "serial.txt", args.max_log_mib << 20)
        if frame:
            try:
                result["frames"].append(cold.frame_capture(frame[1], 1179, 2556, attempt / "frame-final.png"))
            except Exception as error:
                result["error"] = "final frame: " + str(error)
        result["witnesses"] = cold.evidence(stderr, serial, result["frames"], [])
        result["done_codes"] = [int(n) for n in re.findall(r"^ASOFT: done (-?\d+)\s*$", serial, re.M)]
        result["out_sizes"] = [int(n) for n in re.findall(r"^ASOFT: out (\d+)\s*$", serial, re.M)]
        try:
            process_bounds(attempt, args)
            recheck(plan)
        except Exception as error:
            result["error"] = "final input/bound check: " + str(error)
        result["finished_utc"] = cold.utc()
        result["status"] = "VM_OBSERVATION_COMPLETE" if vm_success(result, helper) else "INCOMPLETE"
        atomic_json(attempt / "vm-result.json", result)
    if result["status"] != "VM_OBSERVATION_COMPLETE":
        raise RuntimeError("VM stage incomplete; see " + str(attempt / "vm-result.json"))
    return result


def helper_stage(plan, stage, attempt, args):
    recipe = stages.job(stage, plan["manifest"])
    disk_rows, outputs = [], []
    for index, row in enumerate(recipe["disks"]):
        source = None if row["mode"] == "new" and row["size"] != "partition" else source_path(plan, row["source"])
        if row["mode"] == "ro":
            path = source
        else:
            size = row["size"]
            if size == "partition":
                with source.open("rb") as stream:
                    header = stream.read(32)
                size = struct.unpack_from(">Q", header, 24)[0] + (16 << 30) + (2 << 20)
            path = create_disk(plan, attempt, row["logical"], args,
                               source if row["mode"] == "overlay" else None, size, str(index))
            outputs.append(row["logical"])
        fmt = "qcow2" if path.suffix == ".qcow2" else "raw"
        if fmt == "raw" and path.stat().st_size % 512:
            raise ValueError("raw helper input is not sector aligned")
        disk_rows.append(dict(row, path=path, format=fmt, readonly=row["mode"] == "ro", serial="d" + str(index)))
    tar = input_tar(plan, recipe, attempt, disk_rows)
    raw = attempt / "out.raw"
    with raw.open("xb") as stream:
        stream.truncate(2 << 30)
    disks = [{"path": tar, "format": "raw", "readonly": True, "serial": "in"},
             {"path": raw, "format": "raw", "readonly": False, "serial": "out"}]
    if recipe["scratch"]:
        scratch = create_disk(plan, attempt, "scratch.qcow2", args, size=recipe["scratch_bytes"], name="scratch")
        disks.append({"path": scratch, "format": "qcow2", "readonly": False, "serial": "scratch"})
    argv, env = helper_command(plan, attempt, disks + disk_rows)
    result = supervise_vm(plan, stage, attempt, argv, env, args)
    if recipe["out"]:
        if len(result["out_sizes"]) != 1:
            raise ValueError("helper output length missing or repeated")
        safe_return_tar(raw, result["out_sizes"][0], attempt / "files", recipe["out"])
    outputs += recipe["out"]
    if stage == "shared-build":
        bundle = attempt / "files/install/work/gpu" / plan["manifest"]["shared"]["vars"]["BUNDLE"]
        for name in ("AppleParavirtGPUMetalIOGPUFamily", plan["manifest"]["shared"]["vars"]["PLUGIN"]):
            if not (bundle / name).is_file():
                raise ValueError("helper did not return a complete GPU bundle")
    for index, row in enumerate(disk_rows):
        if row["mode"] != "ro":
            image_tool(plan, ["check", "--output=json", str(row["path"])], attempt, "check-" + str(index), args, 300)
    return outputs


def guest_stage(plan, stage, attempt, args):
    config = stages.boot_inputs(stage)
    source = source_path(plan, config["source"])
    target = create_disk(plan, attempt, config["output"], args, source=source, name="guest")
    assets = attempt / "boot-inputs"
    assets.mkdir()
    for logical, name in ((config["kernel"], "bootkc"), ("fw/sptm", "sptm"), ("fw/txm", "txm"), ("rd-shell.hfs", "rd-shell.hfs")):
        shutil.copyfile(source_path(plan, logical), assets / name)
    dt = source_path(plan, config["tree"])
    dttool = Path(__file__).with_name("cold_boot_dt.py")
    run_process([sys.executable, "-I", "-B", str(dttool), str(dt), str(attempt / "device-tree"),
                 "--timebase", "38400000", "--ram-gib", "3"], {"PATH": "/system/bin"}, attempt, "device-tree", 10, args)
    if (attempt / "device-tree").read_bytes() != cold.expected_tree(dt.read_bytes(), 3, 3):
        raise ValueError("setup tree copy has unexpected changes")
    (attempt / "cache").mkdir()
    launch_plan = {"run_dir": str(attempt), "assets": str(assets), "package": plan["session"]["package"],
                   "trustcache": str(source_path(plan, config["trustcache"])), "frame_size": [1179, 2556]}
    fd = os.memfd_create("pixel-ios26-preparation-frame", os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
    mapping = None
    try:
        os.ftruncate(fd, 1179 * 2556 * 4)
        fcntl.fcntl(fd, fcntl.F_ADD_SEALS, fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL)
        mapping = mmap.mmap(fd, 1179 * 2556 * 4)
        argv, env = cold.command(launch_plan, fd)
        # The cold harness names its own overlay; this owner supplies its fresh
        # stage overlay, without altering any other qualified launch settings.
        argv = [arg.replace(str(attempt / "coldboot-overlay.qcow2"), str(target)) for arg in argv]
        supervise_vm(plan, stage, attempt, argv, env, args, (fd, mapping))
    finally:
        if mapping is not None:
            mapping.close()
        os.close(fd)
    image_tool(plan, ["check", "--output=json", str(target)], attempt, "check-guest", args, 300)
    outputs = [config["output"]]
    if stage == "ios26-wallpaper":
        shutil.copyfile(source_path(plan, "root26-gpu.tc"), output_path(attempt, "root.tc"))
        outputs.append("root.tc")
    return outputs


def pack_stage(plan, attempt, args):
    source = source_path(plan, "root.qcow2")
    disk = output_path(attempt, "ios26/root26s-aod.qcow2")
    image_tool(plan, ["convert", "-O", "qcow2", "-c", "-o", "compression_type=zstd", str(source), str(disk)],
               attempt, "pack-disk", args, args.helper_seconds)
    if len(cold.qcow_chain(disk)) != 1:
        raise ValueError("packed disk still has a backing file")
    image_tool(plan, ["check", "--output=json", str(disk)], attempt, "check-packed", args, 300)
    for logical, name in stages.PACK_FILES.items():
        shutil.copyfile(source_path(plan, logical), output_path(attempt, "ios26/" + name))
    info = {"format": 1, "what": "ios26", "prepared_by": "standalone native-required stages",
            "build": "23G90", "session_sha256": digest(plan["session"]), "created_utc": cold.utc(), **BOOT_COMPLETE}
    atomic_json(attempt / "files/ios26/install.json", info)
    return ["ios26"]


def next_attempt(plan, stage):
    work = Path(plan["work"])
    root = contained(work, "attempts")
    prefix = "sm-" if stage == "helper-smoke" else f"{stages.STAGES.index(stage):02d}-"
    used = [int(p.name[len(prefix):]) for p in root.iterdir() if re.fullmatch(prefix + r"\d{4}", p.name)]
    if used and stage in RESUMABLE_DOWNLOADS:
        relative = "attempts/" + prefix + f"{max(used):04d}"
        candidate = contained(work, relative)
        validate_attempt_tree(candidate)
        if not contained(work, relative + "/files").is_dir():
            raise ValueError("resumable attempt has no owned files directory")
        saved = contained(work, relative + "/stage-inputs.json")
        if saved.is_file():
            record = json.loads(saved.read_text())
            current = {n: cold.readonly_identity(source_path(plan, n)) for n in plan["artifacts"]}
            if (record.get("stage") == stage and record.get("session_sha256") == digest(plan["session"]) and
                    record.get("inputs") == current):
                # Only incomplete downloads resume; Java verifies pinned entry
                # metadata plus the complete CRC/hash after reuse. AEA cannot
                # authenticate an old plaintext prefix from a progress marker,
                # so decrypt stages and all VM disks always get fresh attempts.
                return candidate
    path = root / (prefix + f"{max(used, default=0) + 1:04d}")
    path.mkdir(mode=0o700)
    (path / "files").mkdir(mode=0o700)
    return path


def helper_smoke(plan, args):
    with exclusive_session(plan):
        attempt = next_attempt(plan, "helper-smoke")
        nonce = os.urandom(16).hex()
        payload = ("standalone-native-helper:" + nonce + "\n").encode() * 4096
        expected = {"schema": 1, "nonce": nonce, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(),
                    "page_size": 16384, "machine": "aarch64"}
        script = ("#!/bin/bash\nset -euo pipefail\npython3 - <<'PY'\n"
                  "import hashlib,json,os,platform\n"
                  f"nonce = {nonce!r}\n"
                  "data = ('standalone-native-helper:' + nonce + '\\n').encode() * 4096\n"
                  "result = {'schema':1,'nonce':nonce,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),"
                  "'page_size':os.sysconf('SC_PAGE_SIZE'),'machine':platform.machine()}\n"
                  "with open('smoke-result.json','w') as f:\n"
                  "    json.dump(result,f,sort_keys=True); f.flush(); os.fsync(f.fileno())\n"
                  "print('Authored helper result written')\nPY\n")
        recipe = {"name": "helper-smoke", "files": [], "out": ["smoke-result.json"], "scratch": []}
        tar = input_tar(plan, recipe, attempt, [], authored_script=script)
        raw = attempt / "out.raw"
        with raw.open("xb") as stream:
            stream.truncate(8 << 20)
        atomic_json(attempt / "expected.json", expected)
        disks = [{"path": tar, "format": "raw", "readonly": True, "serial": "in"},
                 {"path": raw, "format": "raw", "readonly": False, "serial": "out"}]
        argv, env = helper_command(plan, attempt, disks)
        result = {"schema": SCHEMA, "status": "INCOMPLETE", "attempt": str(attempt), "started_utc": cold.utc(), **BOOT_COMPLETE}
        try:
            observed = supervise_vm(plan, "helper-smoke", attempt, argv, env, args)
            if len(observed["out_sizes"]) != 1:
                raise ValueError("smoke helper output length missing or repeated")
            safe_return_tar(raw, observed["out_sizes"][0], attempt / "files", recipe["out"])
            received = json.loads((attempt / "files/smoke-result.json").read_text())
            if received != expected:
                raise ValueError("authored helper result differs from nonce/hash/page-size contract")
            recheck(plan)
            result.update(status="HELPER_SMOKE_PASSED", result=received,
                          output=file_record(attempt / "files/smoke-result.json", Path(plan["work"])),
                          qualification_sha256=plan["session"]["qualification"]["qualification_sha256"],
                          tooling_manifest_sha256=plan["session"]["tooling_manifest_sha256"])
        except BaseException as error:
            result["error"] = type(error).__name__ + ": " + str(error)
            raise
        finally:
            result["finished_utc"] = cold.utc()
            atomic_json(attempt / "smoke-result.json", result)
            atomic_json(Path(plan["work"]) / "result.json", result)
        return result


def execute(plan, args):
    if plan["network_stages"] and not args.allow_network:
        raise ValueError("selected stages need explicit --allow-network (including AEA key lookup)")
    if plan["guest_boot_stages"] and not args.allow_guest_boots:
        raise ValueError("selected stages include actual iOS setup boots; --allow-guest-boots is required")
    cold.require_phone(plan["session"])
    cold.subreaper()
    recheck(plan)
    if plan["helper_smoke"]:
        return helper_smoke(plan, args)
    result = {"schema": SCHEMA, "status": "INCOMPLETE", "started_utc": cold.utc(), **BOOT_COMPLETE}
    with exclusive_session(plan):
        artifacts, completed = load_checkpoints(Path(plan["work"]), plan["session"])
        plan["artifacts"], plan["completed"] = artifacts, completed
        plan["remaining"] = [s for s in plan["remaining"] if s not in completed]
        for stage in plan["remaining"]:
            needed = int((stages.SPACE_GB[stage] + 1.5) * 1e9)
            if shutil.disk_usage(plan["work"]).free < needed:
                raise ValueError(f"{stage} requires {needed} additional free bytes with preserved predecessors")
            attempt = next_attempt(plan, stage)
            result.update(stage=stage, attempt=str(attempt))
            before = {n: cold.readonly_identity(source_path(plan, n)) for n in plan["artifacts"]}
            inputs = attempt / "stage-inputs.json"
            if not inputs.exists():
                atomic_json(inputs, {"stage": stage, "session_sha256": digest(plan["session"]), "inputs": before})
            try:
                if stage.endswith("-fetch"):
                    names = fetch_stage(plan, stage, attempt, args)
                elif stage in ("shared-unpack", "ios26-decrypt"):
                    names = unpack_stage(plan, stage, attempt, args)
                elif stage in stages.GUEST_BOOTS:
                    names = guest_stage(plan, stage, attempt, args)
                elif stage == "ios26-pack":
                    names = pack_stage(plan, attempt, args)
                else:
                    names = helper_stage(plan, stage, attempt, args)
                for name, identity in before.items():
                    if cold.readonly_identity(source_path(plan, name)) != identity:
                        raise ValueError("predecessor changed during stage: " + name)
                recheck(plan)
                records = output_records(attempt, Path(plan["work"]), names)
                previous = None if not plan["completed"] else cold.sha(Path(plan["work"]) / "checkpoints" / (plan["completed"][-1] + ".json"))
                checkpoint = {"schema": SCHEMA, "status": "STAGE_COMPLETE", "stage": stage,
                              "session_sha256": digest(plan["session"]), "previous_sha256": previous,
                              "artifacts": records, "attempt": str(attempt), "finished_utc": cold.utc(), **BOOT_COMPLETE}
                atomic_json(Path(plan["work"]) / "checkpoints" / (stage + ".json"), checkpoint)
                plan["artifacts"].update(records)
                plan["completed"].append(stage)
                atomic_json(attempt / "stage-result.json", checkpoint)
            except BaseException as error:
                result["error"] = type(error).__name__ + ": " + str(error)
                atomic_json(attempt / (operation_name(attempt, "failed-result") + ".json"), result)
                atomic_json(Path(plan["work"]) / "result.json", result)
                raise
        result.update(status="PREPARED_ASSETS" if "ios26-pack" in plan["completed"] else "PREPARATION_CHECKPOINT",
                      completed=plan["completed"], finished_utc=cold.utc())
        if "ios26-pack" in plan["completed"]:
            result["assets"] = str(source_path(plan, "ios26/install.json").parent)
        atomic_json(Path(plan["work"]) / "result.json", result)
    return result


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("package", "qualification", "tooling", "tooling-sha256", "work"):
        p.add_argument("--" + name)
    p.add_argument("--through", choices=stages.STAGES, default="ios26-partition")
    p.add_argument("--execute", action="store_true")
    p.add_argument("--helper-smoke", action="store_true", help="authored native Linux helper only; no Apple inputs or setup checkpoints")
    p.add_argument("--allow-network", action="store_true")
    p.add_argument("--allow-guest-boots", action="store_true")
    p.add_argument("--timezone", default="Etc/UTC")
    p.add_argument("--region", default="")
    p.add_argument("--clock", type=int, choices=(12, 24), default=24)
    p.add_argument("--helper-ram-mib", type=int, choices=(2048, 3072, 4096), default=2048)
    p.add_argument("--helper-vcpus", type=int, choices=(2, 4), default=4)
    p.add_argument("--input-seconds", type=int, default=7200)
    p.add_argument("--helper-seconds", type=int, default=7200)
    p.add_argument("--smoke-seconds", type=int, default=180)
    p.add_argument("--max-log-mib", type=int, default=64)
    p.add_argument("--min-free-mib", type=int, default=1536)
    p.add_argument("--min-available-mib", type=int, default=512)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    result = {"schema": SCHEMA, "status": "INCOMPLETE", **BOOT_COMPLETE}
    old_handlers = {}
    try:
        if not 30 <= args.input_seconds <= 43200 or not 30 <= args.helper_seconds <= 21600 or not 30 <= args.smoke_seconds <= 600:
            raise ValueError("input/helper deadlines outside supported bounds")
        if not 1 <= args.max_log_mib <= 256 or args.min_free_mib < 512 or args.min_available_mib < 256:
            raise ValueError("invalid storage/memory bounds")
        result = preflight(args)
        if args.execute:
            def interrupted(number, _):
                raise InterruptedError("signal " + str(number))
            old_handlers = {s: signal.signal(s, interrupted) for s in (signal.SIGINT, signal.SIGTERM)}
            result = execute(result, args)
    except (Exception, KeyboardInterrupt) as error:
        result = {"schema": SCHEMA, "status": "INCOMPLETE", "error": type(error).__name__ + ": " + str(error), **BOOT_COMPLETE}
    finally:
        for number, handler in old_handlers.items():
            signal.signal(number, handler)
    print(json.dumps(result, indent=2))
    return 2 if result["status"] == "INCOMPLETE" else 0


if __name__ == "__main__":
    raise SystemExit(main())
