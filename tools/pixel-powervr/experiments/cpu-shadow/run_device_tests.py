#!/usr/bin/env python3
"""Run the authored GPU/native qualification package in bounded child processes.

This performs no app build or installation and reads no Apple guest image. Each
case receives a fresh shader cache and an explicit environment. The complete
package must have been reconstructed by install_device_update.py first.
"""
import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import time


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".new")
    with temporary.open("w") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def close_children():
    """Reap/stop only this dedicated runner's own adopted children."""
    children = Path(f"/proc/self/task/{os.getpid()}/children")
    deadline = time.monotonic() + 3
    forced = set()
    while time.monotonic() < deadline:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return True, sorted(forced)
        if pid:
            continue
        try:
            child_ids = [int(value) for value in children.read_text().split()]
        except FileNotFoundError:
            # Some kernels omit CONFIG_CHECKPOINT_RESTORE's children file.
            # This process is single threaded and does not reap asynchronously:
            # a direct child's PID remains owned until our next waitpid.
            child_ids = []
            for directory in Path("/proc").iterdir():
                if not directory.name.isdigit():
                    continue
                try:
                    status = (directory / "status").read_text()
                except (FileNotFoundError, ProcessLookupError, PermissionError):
                    continue
                if re.search(r"^PPid:\s*" + str(os.getpid()) + r"\s*$", status, re.M):
                    child_ids.append(int(directory.name))
        for child in child_ids:
            try:
                os.kill(child, signal.SIGKILL)
                forced.add(child)
            except ProcessLookupError:
                pass
        time.sleep(0.02)
    return False, sorted(forced)


def run_case(name, arguments, environment, out, expected, seconds):
    folder = out / name
    folder.mkdir(mode=0o700)
    cache = folder / "cache"
    cache.mkdir(mode=0o700)
    env = {**environment, "XDG_CACHE_HOME": str(cache)}
    started = time.monotonic()
    record = {"case": name, "started_utc": utc(), "command": arguments,
              "timeout_seconds": seconds, "environment": env,
              "cache_started_empty": True, "timed_out": False}
    log = folder / "output.log"
    with log.open("xb") as stream:
        child = subprocess.Popen(arguments, stdin=subprocess.DEVNULL, stdout=stream,
                                 stderr=subprocess.STDOUT, env=env,
                                 start_new_session=True)
        try:
            record["exit_code"] = child.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            record["timed_out"] = True
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                record["exit_code"] = child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                record["exit_code"] = None
        stream.flush()
        os.fsync(stream.fileno())
    record["all_children_reaped"], record["forced_descendant_cleanup"] = close_children()
    output = log.read_text(errors="replace")
    record.update(log_sha256=sha(log), elapsed_seconds=time.monotonic() - started,
                  expected_markers=expected,
                  observed_markers=[text for text in expected if text in output])
    record["passed"] = (record["exit_code"] == 0 and not record["timed_out"] and
                        record["all_children_reaped"] and not record["forced_descendant_cleanup"] and
                        record["observed_markers"] == expected)
    save(folder / "result.json", record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    package, out = args.package.resolve(), args.out.resolve()
    installed = json.loads((package.parent / "installation.json").read_text())
    if (installed["status"] != "GPU_TEST_PACKAGE_VERIFIED_NOT_EXECUTED" or
            installed["package"] != str(package)):
        parser.error("package is not a verified diagnostic installation")
    checksums = {}
    for line in (package / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        path = package / name
        if (not re.fullmatch(r"[0-9a-f]{64}", digest) or name in checksums or
                not path.resolve().is_relative_to(package) or sha(path) != digest):
            parser.error("package checksum failed: " + name)
        checksums[name] = digest
    if sha(package / "qemu-system-aarch64") != installed["qemu_sha256"]:
        parser.error("QEMU differs from the verified installation")
    required = {"cpu_shadow_qualification", "cpu-shadow-alias.air", "cpu-shadow-fixed.air",
                "cpu-shadow-tile-vertex.air", "cpu-shadow-tile-fragment.air",
                "efi-memfd-integration", "native-efi-owner", "native-efi-guest.elf"}
    if not required.issubset(checksums):
        parser.error("package lacks qualification payloads: " + str(sorted(required - checksums.keys())))
    # A dedicated, single-threaded process owns every child created below.
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0):  # PR_SET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), "cannot own diagnostic descendants")
    out.mkdir(parents=True, mode=0o700, exist_ok=False)
    properties = {}
    for prop in ("ro.product.model", "ro.product.device", "ro.build.fingerprint",
                 "ro.build.version.release", "ro.build.version.sdk", "ro.hardware"):
        properties[prop] = subprocess.check_output(["/system/bin/getprop", prop],
                                                  text=True, timeout=5).strip()
    environment = {"PATH": "/system/bin", "LD_LIBRARY_PATH": str(package / "lib"),
                   "REIMS_VGPU_CPU_SHADOW": "1", "REIMS_VGPU_LOG": "info"}
    qualification = str(package / "cpu_shadow_qualification")
    kernel, render, vertex, fragment = (str(package / name) for name in (
        "cpu-shadow-alias.air", "cpu-shadow-fixed.air",
        "cpu-shadow-tile-vertex.air", "cpu-shadow-tile-fragment.air"))
    nonce = secrets.token_hex(32)
    cases = [
        ("probe", [str(package / "qemu-system-aarch64"), "--asoft-gpu-probe", nonce],
         ["ASOFT_GPU_PROBE "], 45),
        ("alias", [qualification, "alias", kernel], ["RESULT=REIMS_CPU_SHADOW_ALIAS_PASS fragmented=false"], 35),
        ("fragmented", [qualification, "fragmented", kernel], ["RESULT=REIMS_CPU_SHADOW_ALIAS_PASS fragmented=true"], 35),
        ("chunk-boundary", [qualification, "chunk-boundary", kernel], ["chunk_boundary=true", "RESULT=REIMS_CPU_SHADOW_ALIAS_PASS"], 35),
        ("fixed", [qualification, "fixed", render], ["CPU_SHADOW_FIXED_COMPLETE"], 45),
        ("rebind", [qualification, "rebind"], ["CPU_SHADOW_REBIND_COMPLETE"], 45),
        ("heap", [qualification, "heap"], ["CPU_SHADOW_HEAP_COMPLETE addresses=stable"], 45),
        ("lifetime", [qualification, "lifetime"], ["RESULT=CPU_SHADOW_LIFETIME_PASS"], 45),
        ("tile", [qualification, "tile", vertex, fragment], ["RESULT=REIMS_CPU_SHADOW_TILE_PASS"], 45),
        ("efi", [str(package / "efi-memfd-integration")], ["\"status\":\"EFI_CPU_SHADOW_PASS\"", "\"frames_checked\":3", "\"fragmented\":false"], 40),
        ("efi-fragmented", [str(package / "efi-memfd-integration"), "--fragmented"], ["\"status\":\"EFI_CPU_SHADOW_PASS\"", "\"frames_checked\":3", "\"fragmented\":true"], 40),
        ("native", [str(package / "native-efi-owner"), str(package), str(out / "native-guest")],
         ["NATIVE_EFI_INTEGRATION_PASS", "frames=2", "ECHILD=1"], 55),
    ]
    result = {"started_utc": utc(), "device": properties, "package": str(package),
              "installed_manifest_sha256": installed["update_manifest_sha256"],
              "package_sha256": checksums, "cases": [], "android_apk": False,
              "gpu_path_complete": False, "apple_guest_tested": False,
              "scope": "authored GPU and native-EL0 qualification; product boot is separate"}
    for name, command, expected, seconds in cases:
        record = run_case(name, command, environment, out, expected, seconds)
        if name == "probe" and record["passed"]:
            lines = (out / name / "output.log").read_text().splitlines()
            reports = [line.removeprefix("ASOFT_GPU_PROBE ") for line in lines
                       if line.startswith("ASOFT_GPU_PROBE ")]
            try:
                data = json.loads(reports[0]) if len(reports) == 1 else {}
                if not isinstance(data, dict):
                    data = {}
            except ValueError:
                data = {}
            record["probe"] = data
            record["passed"] = (data.get("nonce") == nonce and data.get("schema") == 1 and
                                data.get("backend") == "system_cpu_shadow" and
                                data.get("status") == "pass" and
                                isinstance(data.get("checks_passed"), int) and
                                data["checks_passed"] & 0x7f == 0x7f)
            save(out / name / "result.json", record)
        print(json.dumps({"case": name, "passed": record["passed"],
                          "exit_code": record["exit_code"],
                          "log": str(out / name / "output.log")}), flush=True)
        result["cases"].append(record)
        result["all_cases_passed"] = len(result["cases"]) == len(cases) and all(
            case["passed"] for case in result["cases"])
        save(out / "qualification.json", result)
        if not record["passed"]:
            print("GPU_QUALIFICATION_STOPPED case=" + name, flush=True)
            return 1
    for name, digest in checksums.items():
        if sha(package / name) != digest:
            result["all_cases_passed"] = False
            result["package_changed"] = name
            save(out / "qualification.json", result)
            return 1
    result["finished_utc"] = utc()
    result["package_rechecked"] = True
    save(out / "qualification.json", result)
    print("GPU_QUALIFICATION_PASSED cases=" + str(len(cases)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
