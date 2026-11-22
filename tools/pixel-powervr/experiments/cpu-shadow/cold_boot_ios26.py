#!/usr/bin/env python3
"""Preflight, then optionally observe a bounded native-EL0 iOS26 cold boot.

No arguments, missing inputs, and ordinary invocation never start a process or
write files. --boot is explicit. Guest inputs are never downloaded or modified;
only a new directory, copied device tree, and new qcow2 overlay are writable.
An observed native/GPU workload is not a complete product or UI qualification.
"""
import argparse
import ctypes
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import mmap
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import socket
import struct
import subprocess
import sys
import time
import zlib


DT_TOOL_SHA256 = "6931310e1318a6397ee2d7eead966bd0fcdeaae9c10038ca2f2aa01de1a45f7e"
TIMEBASE_HZ = 38_400_000  # Measured Pixel evidence: experiments/counter-frequency.
TREE = "dtree-root26v-smp4-19m2"
CPU = "max,pauth-impdef=on,x-el0-pac-off=on,sve=off,sme=off,x-host-counter=on,x-keep-kernel-tlb=off"
CASES = {"probe", "alias", "fragmented", "chunk-boundary", "fixed", "rebind", "heap",
         "arguments", "dynamic-rebind", "lifetime", "tile", "efi", "efi-fragmented",
         "native", "native-swap"}
FATAL = ("required initialization failed", "no stub factory", "staying on TCG",
         "failed on the GPU", "CPU-shadow counters unavailable", "panic(cpu", "panic(")


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".new")
    with temporary.open("w") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def readonly_identity(path):
    """Cheap disk-change witness; deliberately not a full 26GB disk hash."""
    path = Path(path).resolve(strict=True)
    s = path.stat()
    with path.open("rb") as stream:
        header = stream.read(65536)
    return {"path": str(path), "device": s.st_dev, "inode": s.st_ino,
            "bytes": s.st_size, "mtime_ns": s.st_mtime_ns, "ctime_ns": s.st_ctime_ns,
            "first_64k_sha256": hashlib.sha256(header).hexdigest()}


def qcow_chain(path):
    """Inspect local qcow2 headers without running qemu-img or opening for write."""
    chain, seen = [], set()
    while path is not None:
        path = Path(path).resolve(strict=True)
        if path in seen or len(chain) >= 32:
            raise ValueError("cyclic or excessive qcow2 backing chain")
        seen.add(path)
        with path.open("rb") as stream:
            header = stream.read(104)
            if len(header) < 72 or header[:4] != b"QFI\xfb":
                raise ValueError("expected local qcow2 backing file: " + str(path))
            version, offset, length = struct.unpack_from(">IQI", header, 4)
            if version not in (2, 3) or length > 4096 or bool(offset) != bool(length):
                raise ValueError("unsupported qcow2 header: " + str(path))
            backing = None
            if length:
                if offset + length > path.stat().st_size:
                    raise ValueError("truncated qcow2 backing path")
                stream.seek(offset)
                name = stream.read(length).decode("utf-8")
                if not name or "\0" in name or ":" in name:
                    raise ValueError("nonlocal qcow2 backing path")
                backing = (path.parent / name).resolve(strict=True)
        chain.append(readonly_identity(path))
        path = backing
    return chain


def tree_properties(data):
    """Read the ADT layout independently of the existing copy-patching tool."""
    properties = {}

    def walk(offset, parent, depth=0):
        if depth > 64 or offset + 8 > len(data):
            raise ValueError("invalid ADT node")
        count, children = struct.unpack_from("<II", data, offset)
        offset += 8
        if count > 10000 or children > 10000:
            raise ValueError("excessive ADT node")
        values, name = {}, None
        for _ in range(count):
            if offset + 36 > len(data):
                raise ValueError("truncated ADT property")
            key = data[offset:offset + 32].split(b"\0")[0].decode("ascii")
            size = struct.unpack_from("<I", data, offset + 32)[0] & 0x7fffffff
            value = offset + 36
            end = value + ((size + 3) & ~3)
            if end > len(data) or key in values:
                raise ValueError("truncated or duplicate ADT property")
            values[key] = (value, size)
            if key == "name":
                name = data[value:value + size].split(b"\0")[0].decode("ascii")
            offset = end
        if not name or "/" in name:
            raise ValueError("missing or invalid ADT node name")
        here = parent + "/" + name if parent else name
        if here in properties:
            raise ValueError("duplicate ADT node")
        properties[here] = values
        for _ in range(children):
            offset = walk(offset, here, depth + 1)
        return offset

    if walk(0, "") != len(data):
        raise ValueError("ADT trailing bytes")
    return properties


def expected_tree(data, ram_gib, scale):
    result = bytearray(data)
    nodes = tree_properties(data)
    found, frequencies = {}, 0
    for path, properties in nodes.items():
        leaf = path.rsplit("/", 1)[-1]
        if "/cpus/" in path and "timebase-frequency" in properties:
            offset, size = properties["timebase-frequency"]
            if size != 8:
                raise ValueError("ADT timebase-frequency is not a u64")
            struct.pack_into("<Q", result, offset, TIMEBASE_HZ)
            frequencies += 1
        if leaf in ("chosen", "memory") or path.endswith("/product/util"):
            found["util" if path.endswith("/product/util") else leaf] = properties
    if frequencies != 4:
        raise ValueError("this harness expects the four-CPU iOS26 tree")
    for node, key, size in (("chosen", "dram-size", 8), ("chosen", "display-scale", 4),
                            ("memory", "reg", 16), ("util", "reg", 16)):
        if node not in found or key not in found[node] or found[node][key][1] != size:
            raise ValueError("missing or incompatible ADT " + node + "/" + key)
    if struct.unpack_from("<I", data, found["chosen"]["display-scale"][0])[0] != scale:
        raise ValueError("tree display scale differs; use a matching prepared disk/tree")
    size = ram_gib << 30
    offset = found["memory"]["reg"][0]
    base = struct.unpack_from("<Q", data, offset)[0]
    struct.pack_into("<Q", result, found["chosen"]["dram-size"][0], size)
    struct.pack_into("<Q", result, offset + 8, size)
    struct.pack_into("<Q", result, found["util"]["reg"][0], base + size)
    return bytes(result)


def qualified_package(package, qualification):
    checksums = {}
    for line in (package / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        path = package / name
        if (not re.fullmatch(r"[0-9a-f]{64}", digest) or name in checksums or
                Path(name).is_absolute() or ".." in Path(name).parts or
                not path.resolve().is_relative_to(package) or sha(path) != digest):
            raise ValueError("package checksum mismatch: " + name)
        checksums[name] = digest
    if "qemu-system-aarch64" not in checksums or not any(n.startswith("lib/") for n in checksums):
        raise ValueError("qualification package lacks QEMU or dependencies")
    actual = {p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()}
    if actual != set(checksums) | {"SHA256SUMS"}:
        raise ValueError("package has unchecked or missing files")
    if any(p.is_symlink() for p in package.rglob("*")):
        raise ValueError("qualification package must not contain symlinks")
    if any(p.name.startswith("libvulkan") for p in (package / "lib").iterdir()):
        raise ValueError("system Vulkan route must not contain a bundled Vulkan loader/driver")
    report = json.loads(qualification.read_text())
    if not isinstance(report, dict):
        raise ValueError("qualification must be a JSON object")
    cases = report.get("cases", [])
    if not isinstance(cases, list) or not all(isinstance(case, dict) for case in cases):
        raise ValueError("qualification cases must be objects")
    names = [case.get("case") for case in cases]
    if (report.get("all_cases_passed") is not True or report.get("package_rechecked") is not True or
            report.get("package_sha256") != checksums or len(set(names)) != len(names) or
            not CASES.issubset(names) or not all(case.get("passed") is True for case in cases)):
        raise ValueError("need matching completed physical qualification including native-swap")
    for case in cases:
        name = case["case"]
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9-]+", name):
            raise ValueError("invalid qualification case name")
        if sha(qualification.parent / name / "output.log") != case.get("log_sha256"):
            raise ValueError("qualification log mismatch: " + name)
    probe = next(case for case in cases if case["case"] == "probe").get("probe", {})
    if (not isinstance(probe, dict) or probe.get("checks_passed") != 127 or
            probe.get("backend") != "system_cpu_shadow"):
        raise ValueError("qualification lacks all seven system GPU probe checks")
    device = report.get("device")
    if (not isinstance(device, dict) or not isinstance(device.get("ro.build.fingerprint"), str) or
            not device["ro.build.fingerprint"]):
        raise ValueError("qualification lacks a device build fingerprint")
    return {"qemu_sha256": checksums["qemu-system-aarch64"],
            "qualification_sha256": sha(qualification), "device": device,
            "probe": probe, "checksums": checksums}


def recheck_package(plan):
    current = qualified_package(Path(plan["package"]), Path(plan["qualification_file"]))
    if current != plan["qualification"]:
        raise ValueError("runtime or physical qualification changed after preflight")


def read_log(path, limit):
    if not path.exists():
        return ""
    with path.open("rb") as stream:
        return stream.read(limit).decode(errors="replace")


def storage_report(run, args):
    sizes = {p.name: p.stat().st_size for pattern in ("*.txt", "*.log") for p in run.glob(pattern)}
    total, free, limit = sum(sizes.values()), shutil.disk_usage(run).free, args.max_log_mib << 20
    truncated = [name for name in ("qemu-stderr.txt", "serial.txt") if sizes.get(name, 0) > limit]
    return {"log_sizes": sizes, "log_bytes": total, "free_bytes": free,
            "max_log_bytes": limit, "min_free_bytes": args.min_free_mib << 20,
            "evidence_truncated": truncated,
            "within_bounds": total <= limit and free >= args.min_free_mib << 20}


def command(plan, frame_fd):
    run, assets = Path(plan["run_dir"]), Path(plan["assets"])
    width, height = plan["frame_size"]
    argv = [str(Path(plan["package"]) / "qemu-system-aarch64"), "-name", "Pixel iOS26 cold boot",
            "-M", f"vresearch,fb={width}x{height},unauth-root=on,pvg=reims,aks-stub=on,amfi-lc-off=on,aks-crypt=on,acm-stub=on,hfs-dp-stub=on"]
    for flag, path in (("bootkc", assets / "bootkc"), ("sptm", assets / "sptm"),
                       ("txm", assets / "txm"), ("dtree", run / "device-tree"),
                       ("tc", Path(plan["trustcache"])), ("ramdisk", assets / "rd-shell.hfs")):
        argv += ["-" + flag, str(path)]
    argv += ["-args", "serial=3 -v debug=0x14e cpus=4 rd=disk0s1 wdt=-1 keepsyms=1 -noprogress "
             "launchd_unsecure_cache=1 launchd_disable_all_timeouts=1 aks-endpoint=0 cpu_boot_timeout_secs=30",
             "-cpu", CPU, "-smp", "4", "-accel", "tcg,thread=multi,tb-size=768",
             "-display", "none", "-monitor", "none", "-parallel", "none",
             "-chardev", f"socket,id=con,path={run}/console.sock,server=on,wait=off,logfile={run}/serial.txt",
             "-serial", "chardev:con", "-d", "guest_errors,unimp", "-D", str(run / "qemu.log"),
             "-drive", f"file={run}/coldboot-overlay.qcow2,if=none,id=root,cache=none,discard=unmap,format=qcow2",
             "-object", "iothread,id=disk", "-device", "virtio-blk-pci,drive=root",
             "-qmp", f"unix:{run}/qmp.sock,server,nowait",
             "-device", "qemu-xhci,id=xhci,conditional-intr-mapping=on,nonremovable=2",
             "-device", "usb-touchscreen,bus=xhci.0,port=2,id=utouch",
             "-device", "usb-consumer,bus=xhci.0,port=3,id=ucons", "-no-reboot"]
    env = {"PATH": "/system/bin", "LD_LIBRARY_PATH": str(Path(plan["package"]) / "lib"),
           "TMPDIR": str(run), "XDG_CACHE_HOME": str(run / "cache"),
           "REIMS_VGPU_CPU_SHADOW": "1", "REIMS_VGPU_DEFERRED_VIEWS": "1",
           "REIMS_VGPU_LOG": "info", "RUST_BACKTRACE": "1", "ASOFT_PAGE_BITS": "14",
           "ASOFT_NATIVE_EL0": "1", "ASOFT_NATIVE_EL0_REQUIRED": "1",
           "ASOFT_NATIVE_EL0_TPIDRRO": "1", "ASOFT_NATIVE_EL0_STUBS": "24",
           "ASOFT_NATIVE_EL0_DELAY_MS": "20000", "ASOFT_NATIVE_EL0_PAC": "off",
           "ASOFT_NATIVE_EL0_STATS": "1", "ASOFT_EL_SAMPLER": "30",
           "ASOFT_FRAME_FD": str(frame_fd)}
    return argv, env


def preflight(args):
    result = {"schema": 1, "status": "INCOMPLETE", "stage": "preflight", "created_utc": utc(),
              "guest_started": False, "boot_complete": False, "gpu_path_complete": False,
              "blockers": []}
    for name in ("assets", "package", "qualification", "qemu_img", "run_dir"):
        if getattr(args, name) is None:
            result["blockers"].append("missing --" + name.replace("_", "-"))
    if result["blockers"]:
        return result
    try:
        paths = {name: getattr(args, name).resolve() for name in
                 ("assets", "package", "qualification", "qemu_img", "run_dir", "dt_tool")}
        for name, path in paths.items():
            if any(c in str(path) for c in (",", "\n", "\r", "\0")):
                raise ValueError("unsupported path delimiter: " + name)
        assets, run = paths["assets"], paths["run_dir"]
        if not assets.is_dir():
            raise ValueError("guest assets directory is absent: " + str(assets))
        if run.exists() or not run.parent.is_dir():
            raise ValueError("run directory must be new and its parent must exist")
        if run.is_relative_to(assets) or run.is_relative_to(paths["package"]):
            raise ValueError("run directory must be outside read-only assets and package")
        if len(str(run / "console.sock").encode()) >= 108:
            raise ValueError("run directory is too long for Unix sockets")
        variant = args.variant
        if variant is None:
            present = [v for v, n in (("manual", "root26r.qcow2"), ("aod", "root26s-aod.qcow2"))
                       if (assets / n).is_file()]
            if len(present) != 1:
                raise ValueError("need exactly one installed base or explicit --variant")
            variant = present[0]
        default_disk = assets / ("root26s-aod.qcow2" if variant == "aod" else "root26r.qcow2")
        disk = (args.disk or default_disk).resolve()
        dtree = (args.dtree or assets / (TREE + ("-aod" if variant == "aod" else ""))).resolve()
        tc = (args.trustcache or assets / ("root26s-aod.tc" if variant == "aod" else "root26m.tc")).resolve()
        inputs = [assets / n for n in ("bootkc", "sptm", "txm", "rd-shell.hfs")]
        inputs += [dtree, tc, paths["qemu_img"], paths["dt_tool"]]
        for path in inputs:
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError("missing or empty input: " + str(path))
        if sha(paths["dt_tool"]) != DT_TOOL_SHA256:
            raise ValueError("device-tree helper differs from the pinned existing tool")
        if dtree.stat().st_size > 16 << 20:
            raise ValueError("device tree exceeds the 16 MiB input bound")
        expected_tree(dtree.read_bytes(), args.ram_gib, args.scale)
        chain = qcow_chain(disk)
        if not any(Path(item["path"]) == default_disk for item in chain):
            raise ValueError("selected disk chain does not contain its declared variant base")
        for item in chain:
            if run.is_relative_to(Path(item["path"]).parent):
                raise ValueError("run directory must be outside all backing-disk directories")
        image_lib = (args.qemu_img_lib or paths["package"] / "lib").resolve()
        if not image_lib.is_dir():
            raise ValueError("qemu-img dependency directory is absent")
        qualified = qualified_package(paths["package"], paths["qualification"])
        for path in (paths["qemu_img"], paths["package"] / "qemu-system-aarch64"):
            if not os.access(path, os.X_OK):
                raise ValueError("input is not executable: " + str(path))
        free = shutil.disk_usage(run.parent).free
        if free < args.min_free_mib << 20:
            raise ValueError("insufficient free space for writable overlay and logs")
        plan = {k: str(v) for k, v in paths.items()}
        plan.update(variant=variant, source_disk=str(disk), dtree=str(dtree), trustcache=str(tc),
                    qemu_img_lib=str(image_lib), disk_chain=chain, ram_gib=args.ram_gib,
                    scale=args.scale, frame_size=[1179, 2556] if args.scale == 3 else [786, 1704],
                    timeout_seconds=args.seconds, timebase_hz=TIMEBASE_HZ, expect_serial=args.expect_serial,
                    qualification_file=str(paths["qualification"]), qualification=qualified, free_bytes=free,
                    input_identities=[readonly_identity(p) for p in inputs],
                    tool_sha256={"qemu_img": sha(paths["qemu_img"]), "dt_tool": DT_TOOL_SHA256})
        argv, env = command(plan, "INHERITED_MEMFD")
        result.update(status="PREFLIGHT_READY", plan=plan, command=argv, environment=env)
    except (OSError, ValueError, KeyError, TypeError, struct.error) as error:
        result["blockers"].append(str(error))
    return result


def run_tool(argv, env, timeout=30):
    child = subprocess.Popen(argv, env=env, stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        output, _ = child.communicate(timeout=timeout)
    except BaseException:
        if child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        child.wait(timeout=5)
        raise
    if child.returncode:
        raise RuntimeError("tool failed: " + str(argv[0]) + ": " + output.decode(errors="replace")[-4096:])
    return output.decode()


def prepare_run(plan):
    run = Path(plan["run_dir"])
    (run / "cache").mkdir(mode=0o700)
    _, env = command(plan, "NOT_STARTED")
    image_env = {"PATH": "/system/bin", "LD_LIBRARY_PATH": plan["qemu_img_lib"], "TMPDIR": str(run)}
    info = run_tool([plan["qemu_img"], "info", "--output=json", "--backing-chain", plan["source_disk"]], image_env)
    save(run / "backing-chain.json", json.loads(info))
    overlay = run / "coldboot-overlay.qcow2"
    run_tool([plan["qemu_img"], "create", "-f", "qcow2", "-F", "qcow2",
              "-b", plan["source_disk"], str(overlay)], image_env)
    if [p["path"] for p in qcow_chain(overlay)][1:] != [p["path"] for p in plan["disk_chain"]]:
        raise ValueError("new overlay backing chain differs")
    source = Path(plan["dtree"])
    shutil.copyfile(source, run / "input-device-tree")
    output = run_tool([sys.executable, "-I", "-B", plan["dt_tool"], str(run / "input-device-tree"),
                       str(run / "device-tree"), "--timebase", str(TIMEBASE_HZ),
                       "--ram-gib", str(plan["ram_gib"])], {"PATH": "/system/bin"}, 10)
    (run / "device-tree-patch.txt").write_text(output)
    if (run / "device-tree").read_bytes() != expected_tree(source.read_bytes(), plan["ram_gib"], plan["scale"]):
        raise ValueError("patched tree differs beyond the expected timebase/RAM fields")
    return env


class Qmp:
    def __init__(self, path, transcript):
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.settimeout(3)
        self.buffer, self.sequence, self.transcript = b"", 0, transcript
        try:
            self.socket.connect(str(path))
            greeting = self.read(time.monotonic() + 3)
            if "QMP" not in greeting:
                raise ValueError("missing QMP greeting")
            self.call("qmp_capabilities", 3)
        except BaseException:
            self.close()
            raise

    def read(self, deadline):
        while b"\n" not in self.buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("QMP response deadline")
            self.socket.settimeout(remaining)
            data = self.socket.recv(65536)
            if not data:
                raise EOFError("QMP closed")
            self.buffer += data
            if len(self.buffer) > 1 << 20:
                raise ValueError("excessive QMP response")
        line, self.buffer = self.buffer.split(b"\n", 1)
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError("QMP message is not an object")
        return value

    def call(self, name, seconds):
        self.sequence += 1
        request = {"execute": name, "id": self.sequence}
        self.transcript.append({"at_utc": utc(), "request": request})
        self.socket.settimeout(seconds)
        self.socket.sendall(json.dumps(request).encode() + b"\n")
        deadline = time.monotonic() + seconds
        while True:
            reply = self.read(deadline)
            if reply.get("id") == self.sequence:
                self.transcript[-1]["response"] = reply
                if "error" in reply or "return" not in reply:
                    raise ValueError("QMP command failed: " + name)
                return reply["return"]

    def close(self):
        self.socket.close()


def subreaper():
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0):  # PR_SET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), "cannot own descendants")


def reap_owned(seconds=5):
    """The dedicated single-threaded owner reaps/kills only its direct children."""
    forced = set()
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return {"echild": True, "forced_descendants": sorted(forced)}
        if pid:
            continue
        for directory in Path("/proc").iterdir():
            if not directory.name.isdigit():
                continue
            try:
                status = (directory / "status").read_text()
                if re.search(r"^PPid:\s*" + str(os.getpid()) + r"\s*$", status, re.M):
                    child = int(directory.name)
                    os.kill(child, signal.SIGKILL)
                    forced.add(child)
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                pass
        time.sleep(0.02)
    return {"echild": False, "forced_descendants": sorted(forced)}


def shutdown(child, qmp, capture=None, stop_seconds=15, quit_seconds=3, exit_seconds=5):
    record = {"stop_flushed": False, "quit_acknowledged": False, "forced_qemu": False, "errors": []}
    try:
        if child.poll() is None and qmp is not None:
            try:
                qmp.call("stop", stop_seconds)
                record["stop_flushed"] = True
            except Exception as error:
                record["errors"].append("stop: " + str(error))
            try:
                if capture is not None:
                    try:
                        capture()
                    except Exception as error:
                        record["errors"].append("frame capture: " + str(error))
            finally:
                try:
                    qmp.call("quit", quit_seconds)
                    record["quit_acknowledged"] = True
                except Exception as error:
                    record["errors"].append("quit: " + str(error))
    finally:
        try:
            try:
                child.wait(timeout=exit_seconds)
            except subprocess.TimeoutExpired:
                # The leader is still our unreaped child: its process group is owned.
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except OSError as error:
                    record["errors"].append("owned QEMU kill: " + str(error))
                record["forced_qemu"] = True
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    record["errors"].append("QEMU remains unreaped after SIGKILL")
        finally:
            try:
                if qmp is not None:
                    try:
                        qmp.close()
                    except Exception as error:
                        record["errors"].append("QMP close: " + str(error))
            finally:
                record["exit_code"] = child.returncode
                record.update(reap_owned())
    return record


def evidence(stderr, serial, frames, expected):
    active = any(int(ms) > 0 and int(entries) > 0 for ms, entries in
                 re.findall(r"el-sample[^\n]*\| native (\d+) ms[^\n]*? enters (\d+)", stderr))
    final = any(int(enters) > 0 and int(svc) > 0 for enters, svc in
                re.findall(r"native-el0: enters (\d+) svc (\d+)", stderr))
    counts = [list(map(int, values)) for values in re.findall(
        r"cpu-shadow chunks=(\d+) views=(\d+) prepared=(\d+) finished=(\d+) uploaded=(\d+) scattered=(\d+)", stderr)]
    gpu = "vresearch-pvg-reims: frame " in stderr and " shown " in stderr and any(
        all(value > 0 for value in row[:5]) for row in counts)
    errors = [token for token in FATAL if token in stderr or token in serial]
    return {"native_initialization": "required initialization ready mode=stubs;" in stderr,
            "native_execution": active or final, "native_sampler": active, "native_svc_final": final,
            "gpu_execution": gpu, "cpu_shadow_counts": counts[-8:],
            "frame_captured": any(f.get("nonuniform") and f.get("stable") for f in frames),
            "serial_bytes": len(serial.encode()), "expected_serial": expected,
            "serial_markers_found": [marker for marker in expected if marker in serial],
            "fatal_markers": errors}


def frame_capture(mapping, width, height, path):
    first = mapping[:]
    second = mapping[:]
    # The fourth byte is ignored by the x8r8g8b8 display and by our RGB PNG.
    stable = all(first[channel::4] == second[channel::4] for channel in range(3))
    digest = hashlib.sha256(second).hexdigest()
    rgb = bytearray(width * height * 3)
    rgb[0::3], rgb[1::3], rgb[2::3] = second[2::4], second[1::4], second[0::4]
    nonuniform = rgb != rgb[:3] * (width * height)
    record = {"at_utc": utc(), "sha256_bgra": digest, "stable": stable, "nonuniform": nonuniform}
    if stable and nonuniform:
        # B,G,R,A in the shared little-endian x8r8g8b8 frame; no Pillow needed.
        scan = b"".join(b"\0" + rgb[y * width * 3:(y + 1) * width * 3] for y in range(height))
        def chunk(kind, data):
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        path.write_bytes(png + chunk(b"IDAT", zlib.compress(scan, 3)) + chunk(b"IEND", b""))
        record.update(path=str(path), png_sha256=sha(path))
    return record


def require_phone(plan):
    if platform.machine().lower() not in ("aarch64", "arm64") or not Path("/system/bin/getprop").is_file():
        raise ValueError("boot execution requires the qualified Android ARM64 phone")
    fingerprint = run_tool(["/system/bin/getprop", "ro.build.fingerprint"], {"PATH": "/system/bin"}, 5).strip()
    if fingerprint != plan["qualification"]["device"].get("ro.build.fingerprint"):
        raise ValueError("phone build differs from its physical qualification")


def witness_status(result, expected):
    w, c, storage = result["witnesses"], result.get("cleanup", {}), result.get("final_storage", {})
    observed = (result.get("stop_reason") == "requested_witnesses_observed" and expected and
                not result.get("changed_originals") and result.get("package_rechecked_after_run") and
                not result.get("owner_cleanup_errors") and storage.get("within_bounds") and
                not storage.get("evidence_truncated") and w["serial_markers_found"] == expected and
                not w["fatal_markers"] and w["native_initialization"] and w["native_execution"] and
                w["gpu_execution"] and w["frame_captured"] and c.get("stop_flushed") and
                c.get("echild") and c.get("exit_code") == 0 and not c.get("forced_qemu") and
                not c.get("forced_descendants") and not c.get("errors"))
    return "WITNESSES_OBSERVED" if observed else "INCOMPLETE"


def boot(preflight_result, args):
    plan = preflight_result["plan"]
    run = Path(plan["run_dir"])
    result = {"schema": 1, "status": "INCOMPLETE", "stage": "boot", "started_utc": utc(),
              "guest_started": False, "boot_complete": False, "gpu_path_complete": False,
              "package_rechecked_after_run": False,
              "scope": "bounded cold native/GPU observation; captured UI needs human review",
              "preflight": preflight_result, "frames": [], "qmp": []}
    child = qmp = mapping = None
    created_run = False
    frame_fd = None
    interrupted = []
    old_handlers = {s: signal.signal(s, lambda signum, _: interrupted.append(signum))
                    for s in (signal.SIGINT, signal.SIGTERM)}
    try:
        require_phone(plan)
        subreaper()
        for original in plan["disk_chain"] + plan["input_identities"]:
            if readonly_identity(original["path"]) != original:
                raise ValueError("input changed after preflight: " + original["path"])
        run.mkdir(mode=0o700, exist_ok=False)
        created_run = True
        prepare_run(plan)
        recheck_package(plan)
        save(run / "result.json", result)
        if interrupted:
            raise InterruptedError("interrupted before launch")
        width, height = plan["frame_size"]
        frame_fd = os.memfd_create("pixel-ios26-frame", os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
        os.ftruncate(frame_fd, width * height * 4)
        fcntl.fcntl(frame_fd, fcntl.F_ADD_SEALS, fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL)
        mapping = mmap.mmap(frame_fd, width * height * 4)
        argv, env = command(plan, frame_fd)
        save(run / "launch.json", {"command": argv, "environment": env})
        started = time.monotonic()
        owner_pid = os.getpid()
        def owned_child():
            libc = ctypes.CDLL(None, use_errno=True)
            if libc.prctl(1, signal.SIGKILL, 0, 0, 0) or os.getppid() != owner_pid:
                os._exit(120)  # PR_SET_PDEATHSIG; normal shutdown still flushes first.
        with (run / "qemu-stderr.txt").open("xb") as log:
            child = subprocess.Popen(argv, env=env, stdin=subprocess.DEVNULL, stdout=log,
                                     stderr=subprocess.STDOUT, pass_fds=(frame_fd,), start_new_session=True,
                                     preexec_fn=owned_child)
        result.update(guest_started=True, qemu_pid=child.pid)
        next_capture, next_report, frame_number = started + 10, started, 0
        while child.poll() is None and not interrupted and time.monotonic() - started < args.seconds:
            now = time.monotonic()
            if qmp is None and (run / "qmp.sock").exists():
                qmp = Qmp(run / "qmp.sock", result["qmp"])
            if now >= next_capture:
                frame_number += 1
                # Bounded retained snapshots: first eight at one-minute intervals, then latest.
                name = f"frame-{frame_number:02}.png" if frame_number <= 8 else "frame-latest.png"
                if name == "frame-latest.png":
                    result["frames"] = [f for f in result["frames"] if f.get("path") != str(run / name)]
                result["frames"].append(frame_capture(mapping, width, height, run / name))
                next_capture = now + 60
            if now >= next_report:
                result["storage"] = storage_report(run, args)
                if not result["storage"]["within_bounds"]:
                    result["stop_reason"] = "storage_bound"
                    break
                stderr = read_log(run / "qemu-stderr.txt", args.max_log_mib << 20)
                serial = read_log(run / "serial.txt", args.max_log_mib << 20)
                result["witnesses"] = evidence(stderr, serial, result["frames"], args.expect_serial)
                result["elapsed_seconds"] = now - started
                if result["witnesses"]["fatal_markers"]:
                    result["stop_reason"] = "fatal_marker"
                    break
                if qmp is not None:
                    result["last_qmp_status"] = qmp.call("query-status", 3)
                save(run / "result.json", result)
                print(json.dumps({"elapsed_seconds": round(now - started), "witnesses": result["witnesses"]}), flush=True)
                next_report = now + 10
                w = result["witnesses"]
                if (args.expect_serial and w["serial_markers_found"] == args.expect_serial and
                        w["native_execution"] and w["gpu_execution"] and w["frame_captured"]):
                    result["stop_reason"] = "requested_witnesses_observed"
                    break
            time.sleep(0.2)
        result.setdefault("stop_reason", "interrupted" if interrupted else "process_exited" if child.poll() is not None else "deadline")
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError, EOFError) as error:
        result["error"] = str(error)
        result["stop_reason"] = "harness_error"
    finally:
        result["owner_cleanup_errors"] = []
        try:
            if child is not None:
                def final_frame():
                    if mapping is not None:
                        result["frames"].append(frame_capture(mapping, *plan["frame_size"], run / "frame-final.png"))
                result["cleanup"] = shutdown(child, qmp, final_frame)
            else:
                result["cleanup"] = reap_owned()
        except Exception as error:
            result["owner_cleanup_errors"].append("process cleanup: " + str(error))
        finally:
            try:
                if mapping is not None:
                    mapping.close()
            except Exception as error:
                result["owner_cleanup_errors"].append("frame mapping: " + str(error))
            finally:
                try:
                    if frame_fd is not None:
                        os.close(frame_fd)
                except Exception as error:
                    result["owner_cleanup_errors"].append("frame descriptor: " + str(error))
                finally:
                    for number, handler in old_handlers.items():
                        signal.signal(number, handler)
        result["finished_utc"] = utc()
        result["signals"] = interrupted
        originals = plan["disk_chain"] + plan["input_identities"]
        changed = []
        for original in originals:
            try:
                if readonly_identity(original["path"]) != original:
                    changed.append(original["path"])
            except OSError:
                changed.append(original["path"])
        result["changed_originals"] = changed
        if created_run:
            try:
                recheck_package(plan)
                result["package_rechecked_after_run"] = True
            except (OSError, ValueError, KeyError, TypeError) as error:
                result["package_recheck_error"] = str(error)
            stderr = read_log(run / "qemu-stderr.txt", args.max_log_mib << 20)
            serial = read_log(run / "serial.txt", args.max_log_mib << 20)
            result["witnesses"] = evidence(stderr, serial, result["frames"], args.expect_serial)
            result["final_storage"] = storage_report(run, args)
            result["status"] = witness_status(result, args.expect_serial)
            try:
                save(run / "result.json", result)
            except OSError as error:
                result["status"] = "INCOMPLETE"
                result["result_write_error"] = str(error)
    return result


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("assets", "package", "qualification", "qemu-img", "qemu-img-lib", "run-dir",
                 "disk", "dtree", "trustcache"):
        p.add_argument("--" + name, type=Path)
    p.add_argument("--dt-tool", type=Path, default=Path(__file__).with_name("cold_boot_dt.py"))
    p.add_argument("--variant", choices=("manual", "aod"))
    p.add_argument("--ram-gib", type=int, choices=(3, 4), default=3)
    p.add_argument("--scale", type=int, choices=(2, 3), default=3)
    p.add_argument("--seconds", type=int, default=900)
    p.add_argument("--min-free-mib", type=int, default=1024)
    p.add_argument("--max-log-mib", type=int, default=64)
    p.add_argument("--expect-serial", action="append", default=[], help="literal expected guest marker; does not prove UI completion")
    p.add_argument("--boot", action="store_true", help="explicitly execute after successful preflight")
    return p


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    if not 30 <= args.seconds <= 1800 or args.min_free_mib < 1 or args.max_log_mib < 1:
        p.error("seconds must be 30..1800; storage bounds must be positive")
    if any(not marker or "\n" in marker for marker in args.expect_serial):
        p.error("serial markers must be nonempty single-line literals")
    result = preflight(args)
    if args.boot and result["status"] == "PREFLIGHT_READY":
        result = boot(result, args)
    print(json.dumps(result, indent=2), flush=True)
    return 0 if result["status"] in ("PREFLIGHT_READY", "WITNESSES_OBSERVED") else 2


if __name__ == "__main__":
    raise SystemExit(main())
