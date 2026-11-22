#!/usr/bin/env python3
"""Observe a diskless Darwin ramdisk with the qualified native Pixel runtime."""

import argparse
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import struct
import subprocess
import sys
import tarfile
import tempfile
import time
import types

BASE = Path("/data/local/tmp")
TRANSFER = BASE / "pixel-gpu-transfer-sxtv33sh"
PREP = BASE / "pixel-prep-e9cc754"
RUNNER = BASE / "pixel-prep-runner-f4d64db"
TOOLS = BASE / "pixel-tools-1528a782/setup/scripts/ios26"
QUALIFICATION = TRANSFER / "qualification-e9cc754/qualification.json"
PACKAGE = TRANSFER / "pixel-cpu-shadow-ksceynt6/cpu-shadow-qualification"
GUARD = BASE / "pixel-boot-checks-counter1/firstboot/guard_ios26_firstboot.py"
ADAPTER = TRANSFER / "run-ios26-firstboot-memfd-adapter-resume1.py"
SESSION = PREP / "session.json"
PINS = {
    GUARD: "ea40638312d6ac41607806ecb03c148fbd0677df6ab01480e13fd40536869674",
    ADAPTER: "ede70023bc1e05b08730b48fab1016c3e665c0e83469509e5b8b74c6f2364ec7",
    SESSION: "406cfe4a378840d8fc4d8d2e02043bb5655322d4e7fbb415400ad3a6090b50c8",
    TOOLS / "adhoc_sign.py": "e9440ffda8eb91369b29c3a4cf14da2ec1257db7a00c167ebaabb4e3870b2898",
    TOOLS / "mktc.py": "ff75ae203184eb6a302b22ab227a4049d2e9a6dfa68daf2d6d5e0f5cb4272b2b",
    QUALIFICATION: "8844f6c851af1ebd2624e41e1c58de09dcd4eb08d3c91441f478fe898a9aa78d",
    BASE / "pixel-firstboot-guard-e9cc754-resume1/result.json":
        "8d2731493b0ccdad2056677e56774f11718d9d01fb35e895023963d98847f8e3",
    BASE / "pixel-saved-audit-e9cc754-resume5/result.json":
        "08ab06ea5b0e1d46a168935df1dbaabeda0daa7ab569b1e001f61e17d7cfc828",
    TRANSFER / "ios26-data-journal-diagnostic-resume5/result.json":
        "6d1829c3a1a4982e4cdcf11a6854fb862f93a12d5025a783331d4a578de28efc",
    BASE / "asoft-rd-probe-01/run/result.json":
        "fff33fa9cf74d2c72963fcf3cf26112d1513030177707605c9ceac6696f60613",
    BASE / "asoft-rd-probe-02/run/result.json":
        "3935bcf3a3e7b2f746b9aa1c35f7e4b0059cc0d64ce9f1878f147c2e57b57afb",
    BASE / "asoft-rd-probe-03/run/result.json":
        "8b9a619c792bdc2a3b9f87606d8f65188ffb84915858c81ce58ecb8bf96cd7f0",
}
INPUTS = {
    "bootkc": ("attempts/01-0001/files/cloud/kernelcache.research.vphone600.decompressed",
               "86895a2eebeb7fcfb68bcd60f2d7e685687faea07ee31166fb58c872b38e0d92"),
    "sptm": ("attempts/01-0001/files/fw/sptm", "437a4427ffba5da5a34668b0b6cbfd672e6db16f01c1600e278c10360156b21e"),
    "txm": ("attempts/01-0001/files/fw/txm", "819861b6b534b6dc53287b010e822b9d93633d07a29b6e5b968c076929ebfbc1"),
    "dtree": ("attempts/02-0001/files/dtree-phone", "ac3e7b91732a319f271c5da0ccbc8d2f8cd14619a2ec93580c0630203b84577c"),
    "ramdisk": ("attempts/02-0001/files/rd-shell.hfs", "3dfeeb907b5057d7ce622b2dd1b24408b519e5f7da6c361ab06de7da838feac4"),
    "apple_cache": ("attempts/02-0001/files/cloud/rd.trustcache.im4p",
                    "142c48b96c42f801c203a7ac43231c56a6912260fe5058f369a3e23ef4148afa"),
    "sysroot": ("attempts/00-0001/files/downloads/ios_sysroot.tar.gz",
                "ee27653106055a6046428465d1cf68f5dfdc1be5e9b6ffdf402bdd0b6034a8dc"),
}
RAM_MIB = 3072
RUNTIME_AVAILABLE_MIB = 512
DEADLINE_SECONDS = 360
BOUNDS = types.SimpleNamespace(max_log_mib=64, min_free_mib=1536)
UNMOUNT_PATHS = ("/sbin/umount", "/bin/umount", "/usr/sbin/umount", "/usr/bin/umount")
HFS_MOUNT_PATHS = ("/sbin/mount_hfs", "/System/Library/Filesystems/hfs.fs/Contents/Resources/mount_hfs")
UTILITIES = ("/sbin/mount", *HFS_MOUNT_PATHS, *UNMOUNT_PATHS, "/bin/stat", "/bin/sync")
RECORD_TAG = "ASOFT-RD2"
ROOT_SOURCE = r"(?:/dev/)?[A-Za-z0-9_][A-Za-z0-9_.-]{0,47}"
HELPER_UNSIGNED_SHA = "e077546177739191e2cdd0b3f40cf6f2997980120bc7f55d8ab269a48926a4e3"
HELPER_NAME = "guest-unmount.signed"
GUEST_HELPER_DIR = "/asoft-rd-probe-helper"

# The existing console brackets this fixed Bash command with a fresh nonce.
# Emit a single record so asynchronous kernel output can be kept out of it.
# Only the root row's short source token and filesystem type leave the shell.
GUEST_COMMAND = " ".join((
    "u=; n=0; s=-; f=-;",
    "for p in " + " ".join(UTILITIES) + "; do",
    r"""if [[ -f $p && -x $p ]]; then u+=1; else u+=0; fi; done;""",
    r"""if m=$(/sbin/mount 2>/dev/null) && (( ${#m} <= 4096 )); then""",
    r"""while IFS= read -r l; do if [[ $l =~ ^([^[:space:]]+)\ on\ /\ \(([a-zA-Z0-9_]{1,16})[,\)] ]]; then""",
    r"""((n+=1)); s=${BASH_REMATCH[1]}; f=${BASH_REMATCH[2]}; fi; done <<< "$m"; fi;""",
    r"""[[ $s =~ ^(/dev/)?[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,47}$ ]] || s=-;""",
    rf"""printf '{RECORD_TAG} %s %s %s %s %s %s\n' "$UID" "$EUID" "$n" "$s" "$f" "$u" """.rstrip(),
))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def file_pin(path, digest, *, body=False):
    require(path == path.resolve(strict=True), f"noncanonical input: {path}")
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, f"not an ordinary input: {path}")
        if body:
            require(before.st_size <= 4 << 20, f"oversized source: {path}")
            data = stream.read((4 << 20) + 1)
            actual = hashlib.sha256(data).hexdigest()
        else:
            data = None
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        after = os.fstat(stream.fileno())

    def identity(value):
        return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns

    require(actual == digest and identity(before) == identity(after) == identity(path.stat()),
            f"input hash or identity changed: {path}")
    return data


def load_source(path):
    module = types.ModuleType(path.stem)
    module.__file__ = str(path)
    exec(compile(file_pin(path, PINS[path], body=True), str(path), "exec"), vars(module))
    return module


def check_inputs():
    for path, digest in PINS.items():
        file_pin(path, digest)
    assets = {key: PREP / relative for key, (relative, _) in INPUTS.items()}
    for key, path in assets.items():
        file_pin(path, INPUTS[key][1])
    return assets


def preparation():
    session = json.loads(file_pin(SESSION, PINS[SESSION], body=True))
    prep = load_source(GUARD).load_frozen(RUNNER, session["runner_sources"])
    cold = prep.cold
    qualified = cold.qualified_package(PACKAGE, QUALIFICATION)
    require(qualified == session["qualification"] and prep.same_runtime(PACKAGE) == session["runtime"],
            "native runtime differs from the original qualification")
    require(session["native_required"] is True and session["tcg_retry"] is False
            and session["guest_ram_gib"] == 3 and session["timebase_hz"] == 38_400_000,
            "unexpected native preparation contract")
    cold.require_phone({"qualification": qualified})
    prep.refuse_live_children(PREP)
    return prep, qualified


def parse_guest(answer):
    require(len(answer) <= 4096, "guest observation exceeds bound")
    records = [line for line in answer.replace("\r", "").splitlines() if line.startswith(RECORD_TAG)]
    require(len(records) == 1, "expected exactly one structured guest record")
    record = re.fullmatch(rf"{RECORD_TAG} ([0-9]{{1,10}}) ([0-9]{{1,10}}) ([0-9]{{1,4}}) "
                          rf"({ROOT_SOURCE}|-) ([A-Za-z0-9_]{{1,16}}|-) ([01]{{{len(UTILITIES)}}})", records[0])
    require(record is not None, "invalid structured guest record")
    uid, euid, rows, source, filesystem, bits = record.groups()
    count = int(rows)
    require(count != 0 or source == filesystem == "-", "unexpected mount data with zero root rows")
    return {"uid": int(uid), "euid": int(euid),
            "root_mount": {"rows": count, "source": None if source == "-" else source,
                           "target": "/" if count == 1 else None, "filesystem": None if filesystem == "-" else filesystem},
            "utility_is_executable_file": {name: bit == "1" for name, bit in zip(UTILITIES, bits, strict=True)}}


def require_capabilities(guest, *, using_helper=False):
    require(guest["uid"] == guest["euid"] == 0, "guest shell did not observe root UID and EUID")
    root = guest["root_mount"]
    require(root["rows"] == 1 and root["filesystem"] == "hfs" and root["source"] is not None,
            "guest did not observe exactly one identifiable HFS root mount")
    tools = guest["utility_is_executable_file"]
    require(tools["/sbin/mount"] and any(tools[name] for name in HFS_MOUNT_PATHS),
            "guest did not observe executable mount and HFS mount utilities")
    if not using_helper:
        require(any(tools[name] for name in UNMOUNT_PATHS), "no checked unmount utility was executable")


def prepare_helper(source, work):
    require(source.is_absolute(), "guest helper source requires an absolute path")
    unsigned = file_pin(source, HELPER_UNSIGNED_SHA, body=True)
    signed = work / HELPER_NAME
    with signed.open("xb") as stream:
        stream.write(unsigned)
    signer = load_source(TOOLS / "adhoc_sign.py")
    cdhash = signer.sign(signed, "com.asoft.asoft-unmount")
    require(re.fullmatch(r"[0-9a-f]{40}", cdhash), "invalid guest helper CDHash")
    body = signed.read_bytes()
    require(len(body) <= 64 << 10, "signed guest helper exceeds the transfer bound")
    return {"unsigned_sha256": HELPER_UNSIGNED_SHA, "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(), "cdhash": cdhash}


def build_cache(assets, output, helper=None):
    signer = load_source(TOOLS / "adhoc_sign.py")
    mktc = load_source(TOOLS / "mktc.py")
    original = mktc.read_tc(assets["apple_cache"].read_bytes())
    entries = dict(original)
    signed = 0
    with tempfile.TemporaryDirectory(prefix="sign-", dir=output.parent) as stage:
        binary = Path(stage) / "binary"
        with tarfile.open(assets["sysroot"], "r:gz") as archive:
            for member in archive:
                if not member.isfile():
                    continue
                require(member.name.startswith("ios_sysroot/") and 0 <= member.size <= 16 << 20,
                        "unexpected sysroot archive entry")
                with archive.extractfile(member) as stream:
                    magic = stream.read(4)
                    if magic != b"\xcf\xfa\xed\xfe":
                        continue
                    binary.write_bytes(magic + stream.read())
                cdhash = bytes.fromhex(signer.sign(binary, "com.asoft." + Path(member.name).name))
                entries.setdefault(cdhash, (2, 0, 0))
                signed += 1
    require(signed > 0 and len(entries) > len(original), "sysroot produced no added trust entries")
    if helper is not None:
        cdhash = bytes.fromhex(helper["cdhash"])
        require(cdhash not in entries, "helper CDHash already exists in the original cache")
        entries[cdhash] = (2, 0, 0)
    raw = struct.pack("<I16sI", 1, b"A" * 16, len(entries))
    raw += b"".join(cdhash + bytes(entries[cdhash][:2]) for cdhash in sorted(entries))
    require(mktc.read_tc(raw) == {key: (*fields[:2], 0) for key, fields in entries.items()},
            "combined cache did not round trip")
    with output.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "apple_entries": len(original), "signed_files": signed, "entries": len(entries)}


def command(cold, assets, cache, run, frame_fd):
    plan = {"run_dir": str(run), "assets": str(run), "package": str(PACKAGE),
            "trustcache": str(cache), "frame_size": [1179, 2556]}
    argv, env = cold.command(plan, frame_fd)
    argv[2] = "Pixel iOS26 diskless ramdisk probe"
    for option, asset in (("-bootkc", "bootkc"), ("-sptm", "sptm"), ("-txm", "txm"), ("-ramdisk", "ramdisk")):
        argv[argv.index(option) + 1] = str(assets[asset])
    args_index = argv.index("-args") + 1
    require(argv[args_index].split().count("rd=disk0s1") == 1, "unexpected frozen boot arguments")
    argv[args_index] = argv[args_index].replace("rd=disk0s1", "rd=md0")
    backend = argv.index("-drive")
    require(argv[backend + 2:backend + 6] == ["-object", "iothread,id=disk", "-device", "virtio-blk-pci,drive=root"],
            "unexpected frozen disk arguments")
    del argv[backend:backend + 6]
    argv += ["-S", "-nodefaults", "-nic", "none"]
    require(env.get("ASOFT_NATIVE_EL0") == env.get("ASOFT_NATIVE_EL0_REQUIRED") == "1",
            "frozen launch does not require native EL0")
    require(not {"-drive", "-blockdev", "-hda", "-hdb", "-sd", "-mtdblock"} & set(argv),
            "disk arguments survived diskless launch construction")
    return argv, env


def check_diskless(qmp):
    require(qmp.call("query-block", 5) == [] and qmp.call("query-named-block-nodes", 5) == [],
            "QMP observed a block device or named block node")


def guest_step(prep, child, console, run, deadline, script, name):
    command = rf"""( {script} ); printf 'ASOFT_HELPER_EXIT %s\n' "$?" """
    require(len(command.encode()) + 80 < 1024, "guest helper command exceeds the console bound")
    require(console.send(command), f"console closed before helper {name}")
    step_end = min(deadline, time.monotonic() + 15)
    while child.poll() is None and time.monotonic() < step_end:
        prep.process_bounds(run, BOUNDS)
        require(prep.mem_available_mib() >= RUNTIME_AVAILABLE_MIB, "VM low-memory stop bound")
        answer = console.poll()
        if answer is not None:
            require(len(answer) <= 4096, f"helper {name} observation exceeds bound")
            lines = answer.replace("\r", "").splitlines()
            markers = [line for line in lines if line.startswith("ASOFT_HELPER_EXIT ")]
            require(markers == ["ASOFT_HELPER_EXIT 0"], f"guest helper {name} did not complete successfully")
            return lines
        time.sleep(0.05)
    raise TimeoutError(f"guest helper {name} deadline")


def helper_chunks(binary):
    for offset in range(0, len(binary), 384):
        chunk = binary[offset:offset + 384]
        if any(chunk):
            yield offset, base64.b64encode(chunk).decode("ascii")


def inspect_helper(prep, child, console, qmp, run, result, deadline, helper):
    pin, binary = helper
    target = GUEST_HELPER_DIR + "/asoft-unmount"
    stage = {"sha256": pin["sha256"], "cdhash": pin["cdhash"], "chunks": 0,
             "volatile_root_remounted": False, "inspect_root_executed": False, "unmount_exercised": False}
    result["guest_helper"] = stage
    check_diskless(qmp)
    root = result["guest"]["root_mount"]
    require(root == {"rows": 1, "source": "root_device", "target": "/", "filesystem": "hfs"},
            "refuse remount of a different root")
    serial = prep.cold.read_log(run / "serial.txt", BOUNDS.max_log_mib << 20)
    require(re.search(r"\bBSD root:\s*md0(?:,|\s|$)", serial), "refuse remount without the md0 witness")
    guest_step(prep, child, console, run, deadline, "/sbin/mount -uw /", "volatile root remount")
    stage["volatile_root_remounted"] = True
    guest_step(prep, child, console, run, deadline,
               f"/bin/mkdir -m 700 {GUEST_HELPER_DIR} && /bin/dd if=/dev/zero of={target} "
               f"bs=1 count=1 seek={len(binary) - 1} 2>/dev/null", "allocation")
    for offset, encoded in helper_chunks(binary):
        guest_step(prep, child, console, run, deadline,
                   f"set -o pipefail; printf '%s' '{encoded}' | /bin/base64 -d | /bin/dd "
                   f"of={target} bs=1 seek={offset} conv=notrunc 2>/dev/null", "transfer")
        stage["chunks"] += 1
    digest = pin["sha256"]
    lines = guest_step(prep, child, console, run, deadline,
                       f"""a=$(/bin/sha256sum {target}) && [[ "${{a%% *}}" == '{digest}' ]] && """
                       f"/bin/chmod 700 {target} && {target} --inspect-root", "hash check and inspection")
    records = [line for line in lines if line.startswith("ASOFT_ROOT_MOUNT ")]
    require(records == [f'ASOFT_ROOT_MOUNT {root["source"]} {root["filesystem"]}'],
            "statfs helper and mount table do not agree on the root mount")
    stage["inspect_root_executed"] = True
    check_diskless(qmp)
    stage["qmp_diskless_after_inspection"] = True


def observe(prep, child, console, qmp, run, result, started, helper):
    require(qmp.call("query-status", 5)["running"] is False, "QEMU was not stopped for block verification")
    check_diskless(qmp)
    result["qmp_diskless_before_continue"] = True
    qmp.call("cont", 5)
    next_query = time.monotonic() + 20
    while child.poll() is None and time.monotonic() - started < DEADLINE_SECONDS:
        prep.process_bounds(run, BOUNDS)
        require(prep.mem_available_mib() >= RUNTIME_AVAILABLE_MIB, "VM low-memory stop bound")
        answer = console.poll()
        if answer is not None and re.search(rf"(?m)^{RECORD_TAG}\b", answer.replace("\r", "")):
            check_diskless(qmp)
            result["qmp_diskless_after_observation"] = True
            result["guest"] = parse_guest(answer)
            require_capabilities(result["guest"], using_helper=helper is not None)
            if helper is not None:
                inspect_helper(prep, child, console, qmp, run, result, started + DEADLINE_SECONDS, helper)
            return
        if time.monotonic() >= next_query and console.send(GUEST_COMMAND):
            next_query = time.monotonic() + 20
        time.sleep(0.25)
    raise RuntimeError("no complete guest observation before the VM deadline or exit")


def run_probe(prep, qualified, assets, work, cache, cache_hash, source_hash, helper):
    cold = prep.cold
    prep.require_memory(RAM_MIB)
    prep.process_bounds(work, BOUNDS)
    run = work / "run"
    run.mkdir(mode=0o700)
    result = {"schema": 1, "status": "INCOMPLETE", "started_utc": cold.utc(),
              "owner": prep.process_identity(os.getpid()), "source_sha256": source_hash,
              "trust_cache_sha256": cache_hash,
              "qmp": [], "boot_complete": False, "gpu_path_complete": False, "apk_allowed": False}
    fd = child = qmp = console = None
    try:
        cold.subreaper()
        tree_tool = RUNNER / "cold_boot_dt.py"
        argv = [sys.executable, "-I", "-B", str(tree_tool), str(assets["dtree"]), str(run / "device-tree"),
                "--timebase", "38400000", "--ram-gib", "3"]
        prep.run_process(argv, {"PATH": "/system/bin"}, run, "device-tree", 10, BOUNDS)
        require((run / "device-tree").read_bytes() == cold.expected_tree(assets["dtree"].read_bytes(), 3, 3),
                "generated device tree does not match the expected 38.4 MHz / 3 GiB tree")
        (run / "cache").mkdir()
        adapter = load_source(ADAPTER)
        adapter.accepted_smoke()
        fd = adapter.libc_adapter()("pixel-ios26-ramdisk-probe", 3)
        os.ftruncate(fd, 1179 * 2556 * 4)
        fcntl.fcntl(fd, fcntl.F_ADD_SEALS, fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL)
        argv, env = command(cold, assets, cache, run, fd)
        prep.atomic_json(run / "launch.json", {"argv": argv, "environment": env, "deadline_seconds": DEADLINE_SECONDS})
        prep.require_memory(RAM_MIB)
        started = time.monotonic()
        with (run / "qemu-stderr.txt").open("xb") as log:
            child = subprocess.Popen(argv, env=env, cwd=run, stdin=subprocess.DEVNULL, stdout=log,
                                     stderr=subprocess.STDOUT, pass_fds=(fd,), start_new_session=True,
                                     preexec_fn=prep.pdeathsig(os.getpid()))
        result["child"] = prep.process_identity(child.pid)
        require(result["child"] is not None, "QEMU exited before publishing its process identity")
        prep.atomic_json(run / "vm.child.json", result["child"])
        qmp_path = run / "qmp.sock"
        while not qmp_path.exists() and child.poll() is None and time.monotonic() - started < 20:
            time.sleep(0.05)
        if qmp_path.exists():
            qmp = cold.Qmp(qmp_path, result["qmp"])
        require(qmp is not None, "QMP socket did not become available")
        console = prep.GuestConsole(run / "console.sock")
        observe(prep, child, console, qmp, run, result, started, helper)
    except BaseException as error:
        result["error"] = f"{type(error).__name__}: {error}"
    finally:
        with prep.cleanup_signals():
            try:
                if console is not None:
                    console.close()
            finally:
                try:
                    result["cleanup"] = cold.shutdown(child, qmp) if child is not None else cold.reap_owned()
                finally:
                    if fd is not None:
                        os.close(fd)
            try:
                prep.process_bounds(run, BOUNDS)
                stderr = cold.read_log(run / "qemu-stderr.txt", BOUNDS.max_log_mib << 20)
                serial = cold.read_log(run / "serial.txt", BOUNDS.max_log_mib << 20)
                witness = cold.evidence(stderr, serial, [], [])
                result["kernel_md0_root_marker"] = bool(re.search(r"\bBSD root:\s*md0(?:,|\s|$)", serial))
                result["native_witnesses"] = {key: witness[key] for key in
                                              ("native_initialization", "native_execution", "native_svc_final", "fatal_markers")}
                cleanup = result["cleanup"]
                require(cleanup.get("stop_flushed") and cleanup.get("quit_acknowledged")
                        and cleanup.get("exit_code") == 0 and cleanup.get("echild")
                        and not (cleanup.get("errors") or cleanup.get("forced_qemu") or cleanup.get("forced_descendants")),
                        "QEMU teardown did not pass the clean ownership checks")
                require(all(witness[key] for key in ("native_initialization", "native_execution", "native_svc_final"))
                        and not witness["fatal_markers"], "required native witnesses are incomplete")
                require(result["kernel_md0_root_marker"], "missing Darwin md0 root-device witness")
            except Exception as error:
                result["final_check_error"] = f"{type(error).__name__}: {error}"
            try:
                cold.recheck_package({"package": str(PACKAGE), "qualification_file": str(QUALIFICATION),
                                      "qualification": qualified})
                check_inputs()
                file_pin(cache, cache_hash)
                if helper is not None:
                    file_pin(work / HELPER_NAME, helper[0]["sha256"])
                file_pin(Path(__file__).resolve(), source_hash)
                result["bound_inputs_reverified"] = True
            except Exception as error:
                result["preservation_error"] = f"{type(error).__name__}: {error}"
            if not {"error", "final_check_error", "preservation_error"} & result.keys():
                result["status"] = "RAMDISK_HELPER_INSPECTED" if helper else "RAMDISK_CAPABILITIES_OBSERVED"
            result["finished_utc"] = cold.utc()
            prep.atomic_json(run / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--guest-helper", type=Path, help="pinned unsigned helper to sign during --prepare-cache")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--prepare-cache", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    require(args.guest_helper is None or args.prepare_cache, "--guest-helper is only for --prepare-cache")
    work = args.work
    require(os.geteuid() == 0 and sys.flags.isolated and sys.dont_write_bytecode,
            "run as root using Python -I -B on the qualified phone")
    require(work.parent == BASE and re.fullmatch(r"asoft-rd-probe-[a-z0-9]{1,12}", work.name)
            and work == work.resolve(), "select a canonical task-owned work path")
    source = Path(__file__).resolve()
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    lock = os.open(PREP / "owner.lock", os.O_RDONLY | os.O_NOFOLLOW)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assets = check_inputs()
        prep, qualified = preparation()
        resources = {"mem_available_mib": prep.mem_available_mib(), "mem_required_mib": RAM_MIB + 768,
                     "free_bytes": shutil.disk_usage(BASE).free}
        result = {"status": "PREFLIGHT_OBSERVED", "resources": resources, "source_sha256": source_hash}
        if args.prepare_cache:
            require(resources["free_bytes"] >= BOUNDS.min_free_mib << 20, "free storage below floor")
            work.mkdir(mode=0o700)
            if args.guest_helper is not None:
                result["helper"] = prepare_helper(args.guest_helper, work)
            result["cache"] = build_cache(assets, work / "ramdisk.tc", result.get("helper"))
            result["status"] = "RAMDISK_TRUST_CACHE_PREPARED"
            prep.atomic_json(work / "cache-result.json", result)
        elif args.execute:
            require(work.is_dir() and not (work / "run").exists(), "prepared work and a fresh run are required")
            receipt_path = work / "cache-result.json"
            require(receipt_path.is_file() and not receipt_path.is_symlink() and receipt_path.stat().st_size <= 4096,
                    "prepared trust cache receipt is invalid")
            receipt = json.loads(receipt_path.read_bytes())
            require(receipt["status"] == "RAMDISK_TRUST_CACHE_PREPARED" and receipt["source_sha256"] == source_hash,
                    "trust cache receipt does not bind this source")
            cache = work / "ramdisk.tc"
            cache_hash = receipt["cache"]["sha256"]
            file_pin(cache, cache_hash)
            helper = None
            if "helper" in receipt:
                pin = receipt["helper"]
                binary = file_pin(work / HELPER_NAME, pin["sha256"], body=True)
                require(0 < len(binary) == pin["bytes"] <= 64 << 10 and pin["unsigned_sha256"] == HELPER_UNSIGNED_SHA,
                        "guest helper does not match the prepared binary")
                entries = load_source(TOOLS / "mktc.py").read_tc(cache.read_bytes())
                require(entries.get(bytes.fromhex(pin["cdhash"])) == (2, 0, 0),
                        "guest helper is missing from the prepared cache")
                helper = pin, binary
            result = run_probe(prep, qualified, assets, work, cache, cache_hash, source_hash, helper)
            result = {key: value for key, value in result.items() if key != "qmp"}
        print(json.dumps(result, sort_keys=True), flush=True)
        return 0 if result["status"] != "INCOMPLETE" else 2
    finally:
        os.close(lock)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(2))
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"status": "REFUSED", "error": f"{type(error).__name__}: {error}"}), flush=True)
        raise SystemExit(2)
