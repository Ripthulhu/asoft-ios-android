#!/usr/bin/env python3
"""Observe the installed native GPU path on a disposable boot child."""
import argparse
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time
import types

BASE = Path("/data/local/tmp")
CONTROL = BASE / "asoft-recovered-control-01"
INSTALL = BASE / "asoft-continue-05"
APP_PREP = BASE / "asoft-continue-02"
BOOT = BASE / "asoft-recovered-gpu-boot-05"
DRIVER_PIN = "6de8efcdcf93d6b9de4a357f696d0ad3ad6ca81a435e19f0b563650c41a7029b"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def load_driver():
    path = CONTROL / "continue_recovered_chain_grace.py"
    body = path.read_bytes()
    require(hashlib.sha256(body).hexdigest() == DRIVER_PIN, "preparation driver changed")
    module = types.ModuleType("bound_preparation_driver")
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def wait_owner(pid):
    deadline = time.monotonic() + 14400
    while time.monotonic() < deadline:
        try:
            stat = Path("/proc", str(pid), "stat").read_text()
        except FileNotFoundError:
            return
        if stat.rsplit(")", 1)[1].split()[0] == "Z":
            return
        time.sleep(2)
    raise TimeoutError("native preparation owner deadline")


def ensure_memfd():
    if hasattr(os, "memfd_create"):
        return
    creator = ctypes.CDLL(None, use_errno=True).memfd_create
    creator.argtypes = (ctypes.c_char_p, ctypes.c_uint)
    creator.restype = ctypes.c_int

    def memfd_create(name, flags):
        fd = creator(os.fsencode(name), flags)
        if fd < 0:
            errno = ctypes.get_errno()
            raise OSError(errno, os.strerror(errno))
        return fd

    os.memfd_create = memfd_create
    os.MFD_CLOEXEC = 1
    os.MFD_ALLOW_SEALING = 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", required=True)
    parser.add_argument("--after-preparation-pid", type=int, required=True)
    args = parser.parse_args()
    require(sys.flags.isolated and sys.dont_write_bytecode and os.geteuid() == 0,
            "requires root Python -I -B")
    driver = load_driver()
    wait_owner(args.after_preparation_pid)
    built_path = INSTALL / "result.json"
    built_body = built_path.read_bytes()
    built = json.loads(built_body)
    require(built["status"] == "NATIVE_GPU_BOOT_INPUTS_PREPARED" and
            set(built["stages"]) == {*driver.STAGES, "ios26-gpu"}, "GPU preparation was not accepted")
    _, receipt, digest = driver.wait_inspection(27579)
    require(built["whole_image_inspection_sha256"] == digest, "whole-image proof changed")
    app_audit = INSTALL / "apps-audit/files/apps-audit/result.json"
    require(driver.sha(app_audit.read_bytes()) == built["apps_audit_sha256"], "apps audit changed")
    session_file = driver.PREP / "session.json"
    session_body = session_file.read_bytes()
    require(driver.sha(session_body) == receipt["prep_session_sha256"], "preparation session changed")
    session = json.loads(session_body)
    guard = driver.load(driver.GUARD, "ea40638312d6ac41607806ecb03c148fbd0677df6ab01480e13fd40536869674")
    prep = guard.load_frozen(driver.RUNNER, session["runner_sources"])
    prep.cold.require_phone(session)
    prep.cold.subreaper()
    driver.allow_natural_reap(prep.cold)
    ensure_memfd()
    for s in (signal.SIGINT, signal.SIGTERM):
        signal.signal(s, driver.interrupt)

    with (driver.PREP / "owner.lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        prep.refuse_live_children(driver.PREP)
        prep.refuse_live_children(INSTALL)
        prep.recheck({"session": session})
        require(prep.cold.sha(driver.RECOVERED) == driver.RECOVERED_SHA, "verified recovery changed")
        plan, paths = driver.setup(prep, session, receipt,
                                  {"path": str(driver.RECOVERED), "sha256": driver.RECOVERED_SHA})
        for stage in [*driver.STAGES, "ios26-gpu"]:
            for name, record in built["stages"][stage].items():
                path = Path(record["path"])
                require(path.resolve(strict=True) == path and
                        any(path.is_relative_to(root) for root in (INSTALL, APP_PREP)),
                        "accepted stage output is not owned")
                paths[name] = path
                plan["artifacts"][name] = record
        cfg = prep.stages.boot_inputs("ios26-wallpaper")
        used = {cfg[k] for k in ("source", "kernel", "tree", "trustcache")} | {"fw/sptm", "fw/txm", "rd-shell.hfs"}
        for name in used:
            require(prep.cold.sha(paths[name]) == plan["artifacts"][name]["sha256"], "boot input changed: " + name)
        ancestry = prep.cold.qcow_chain(paths[cfg["source"]])
        require([item["path"] for item in ancestry] == plan["artifacts"][cfg["source"]]["backing_chain"] and
                str(driver.RECOVERED) in [item["path"] for item in ancestry], "boot ancestry differs")
        preserved = {p: prep.cold.readonly_identity(p) for p in [paths[n] for n in used] +
                     [Path(item["path"]) for item in ancestry]}
        prep.require_memory(3072)
        BOOT.mkdir(mode=0o700)
        (BOOT / "files").mkdir(mode=0o700)
        target = BOOT / "files" / cfg["output"]
        io_proofs = []
        original_call = prep.cold.Qmp.call

        def call(qmp, name, seconds):
            ret = original_call(qmp, name, seconds)
            if name == "stop":
                stats = original_call(qmp, "query-blockstats", 5)
                blocks = original_call(qmp, "query-block", 5)
                active = next(row for row in blocks if row.get("device") == "root")
                require(active["inserted"]["file"] == str(target), "QMP root is not the disposable child")
                io_proofs.append(guard.failed_io_counters(stats, blocks))
            return ret

        prep.cold.Qmp.call = call
        bounds = types.SimpleNamespace(max_log_mib=64, min_free_mib=1536, min_available_mib=512)
        result = {"status": "INCOMPLETE", "preparation_sha256": driver.sha(built_body),
                  "wallpaper_filesystem_inspection_passed": False, "apk_allowed": False}
        try:
            print("Launching the guarded native GPU boot on a fresh child", flush=True)
            prep.guest_stage(plan, "ios26-wallpaper", BOOT, bounds)
            vm = json.loads((BOOT / "vm-result.json").read_bytes())
            require(prep.vm_success(vm, False) and vm.get("guest_sync_answered") is True and
                    vm["witnesses"]["native_svc_final"] and len(io_proofs) == 1,
                    "GPU boot lacked a complete native, frame, sync, or I/O witness")
            require(prep.cold.qcow_chain(target)[1:] == ancestry, "boot child backing changed")
            result.update(status="GUARDED_NATIVE_GPU_BOOT_OBSERVED", target=str(target),
                          target_sha256=prep.cold.sha(target), witnesses=vm["witnesses"],
                          frames=vm["frames"], guest_sync_answered=True,
                          qmp_io_proof=io_proofs[0], cleanup=vm["cleanup"])
        except BaseException as error:
            result["error"] = type(error).__name__ + ": " + str(error)
        finally:
            prep.cold.Qmp.call = original_call
            try:
                require(all(prep.cold.readonly_identity(path) == old for path, old in preserved.items()),
                        "a preserved boot input changed")
                require(prep.cold.sha(driver.RECOVERED) == driver.RECOVERED_SHA, "recovered base changed")
                result["preservation_verified"] = True
            except (OSError, ValueError) as error:
                result["status"] = "INCOMPLETE"
                result["preservation_error"] = str(error)
            prep.atomic_json(BOOT / "result.json", result)
            print(json.dumps({"status": result["status"], "error": result.get("error"),
                              "preservation_error": result.get("preservation_error")}), flush=True)
        return 0 if result["status"] == "GUARDED_NATIVE_GPU_BOOT_OBSERVED" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, InterruptedError) as error:
        print(json.dumps({"status": "REFUSED", "error": str(error)}), flush=True)
        raise SystemExit(2)
