#!/usr/bin/env python3
"""Carry the pinned iOSRoot alternate-header proof into the app-copy audit."""
import argparse
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
PREVIOUS = BASE / "asoft-continue-02"
WORK = BASE / "asoft-continue-03"
SOURCE_PIN = "6de8efcdcf93d6b9de4a357f696d0ad3ad6ca81a435e19f0b563650c41a7029b"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def load_driver():
    path = CONTROL / "continue_recovered_chain_grace.py"
    body = path.read_bytes()
    require(hashlib.sha256(body).hexdigest() == SOURCE_PIN, "stage owner source changed")
    driver = types.ModuleType("accepted_preparation_driver")
    driver.__file__ = str(path)
    exec(compile(body, str(path), "exec"), driver.__dict__)
    return driver


def wait_owner(pid):
    deadline = time.monotonic() + 7200
    while time.monotonic() < deadline:
        try:
            status = Path("/proc", str(pid), "stat").read_text().rsplit(")", 1)[1].split()[0]
        except FileNotFoundError:
            return
        if status == "Z":
            return
        time.sleep(2)
    raise TimeoutError("previous preparation owner deadline")


def bind_known_alternate(driver, receipt, approval):
    old = driver.INSPECTOR
    source = old.read_bytes()
    require(driver.sha(source) == receipt["inspector_sources"][old.name] and
            approval["header_classification"]["state"] == "ROOT_AUTHORED_NEEDINIT_TO_INITIALIZED_EMPTY",
            "unexpected source or prior iOSRoot classification")
    alternate = approval["volume"]["alternate_sha256"]
    require(len(alternate) == 64 and all(c in "0123456789abcdef" for c in alternate),
            "invalid alternate header SHA-256")
    adapter = '''
# Authorized iOSRoot-only compatibility for the unchanged authored alternate.
_checked_volume_headers = volume_headers


def volume_headers(stream, base, size, root_alternate=False):
    if (base, size) != (ROOT_BASE, ROOT_BYTES):
        return _checked_volume_headers(stream, base, size, root_alternate)
    info, headers = _checked_volume_headers(stream, base, size, True)
    if info["attributes"][1] & (1 << 11):
        require(info["alternate_sha256"] == ALTERNATE_PIN,
                "root_alternate_differs_from_accepted_inspection")
        require(info["attributes"][0] & (1 << 8), "root_primary_not_clean")
    return info, headers
'''.replace("ALTERNATE_PIN", repr(alternate)).encode("ascii")
    dependency = WORK / "bound-sources" / old.name
    dependency.parent.mkdir(mode=0o700)
    with dependency.open("xb") as stream:
        stream.write(source + b"\n" + adapter)
    corrected = dict(receipt)
    corrected["inspector_sources"] = dict(receipt["inspector_sources"])
    corrected["inspector_sources"][old.name] = driver.sha(dependency.read_bytes())
    driver.INSPECTOR = dependency
    return corrected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--after-preparation-pid", required=True, type=int)
    args = parser.parse_args()
    require(sys.flags.isolated and sys.dont_write_bytecode and os.geteuid() == 0, "requires root Python -I -B")
    wait_owner(args.after_preparation_pid)
    old = json.loads((PREVIOUS / "result.json").read_bytes())
    if old["status"] == "NATIVE_GPU_BOOT_INPUTS_PREPARED":
        print("The original audit passed and its queued GPU boot owns the continuation.", flush=True)
        return 0
    driver = load_driver()
    require(old["status"] == "INCOMPLETE" and set(old["stages"]) == set(driver.STAGES),
            "persona, activation, and apps preparation must have been accepted")
    failure_path = PREVIOUS / "apps-audit/files/apps-audit/result.json"
    failure = json.loads(failure_path.read_bytes())
    require(failure["status"] == "INCOMPLETE" and
            failure["errors"] == [{"code": "volume_not_journaled_or_inconsistent"}] and
            failure["readonly_inputs"] and not failure["cleanup_errors"], "unexpected preceding app audit result")
    inspection, receipt, digest = driver.wait_inspection(27579)
    require(old["whole_image_inspection_sha256"] == digest, "source inspection receipt changed")
    approved = inspection["guest_result"]["journals"]["iOSRoot"]
    session_data = (driver.PREP / "session.json").read_bytes()
    require(driver.sha(session_data) == receipt["prep_session_sha256"], "preparation session changed")
    session = json.loads(session_data)
    guard = driver.load(driver.GUARD, "ea40638312d6ac41607806ecb03c148fbd0677df6ab01480e13fd40536869674")
    prep = guard.load_frozen(driver.RUNNER, session["runner_sources"])
    prep.cold.require_phone(session)
    prep.cold.subreaper()
    driver.allow_natural_reap(prep.cold)
    for s in (signal.SIGINT, signal.SIGTERM):
        signal.signal(s, driver.interrupt)
    with (driver.PREP / "owner.lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        prep.refuse_live_children(driver.PREP)
        prep.refuse_live_children(PREVIOUS)
        prep.recheck({"session": session})
        require(prep.cold.sha(driver.RECOVERED) == driver.RECOVERED_SHA, "verified recovery changed")
        WORK.mkdir(mode=0o700)
        (WORK / "attempts").mkdir(mode=0o700)
        driver.WORK = WORK
        plan, paths = driver.setup(prep, session, receipt,
                                  {"path": str(driver.RECOVERED), "sha256": driver.RECOVERED_SHA})
        for stage in driver.STAGES:
            for name, record in old["stages"][stage].items():
                path = Path(record["path"])
                require(path.resolve(strict=True) == path and path.is_relative_to(PREVIOUS) and
                        prep.cold.sha(path) == record["sha256"], "unowned or changed stage output")
                if name.endswith(".qcow2"):
                    require([r["path"] for r in prep.cold.qcow_chain(path)] == record["backing_chain"],
                            "stage backing ancestry changed")
                paths[name] = path
                plan["artifacts"][name] = record
        typed = bind_known_alternate(driver, receipt, approved)
        bounds = types.SimpleNamespace(helper_seconds=3600, max_log_mib=64,
                                       min_free_mib=1536, min_available_mib=512)
        result = {"status": "INCOMPLETE", "whole_image_inspection_sha256": digest,
                  "stages": dict(old["stages"]), "failed_audit_sha256": driver.sha(failure_path.read_bytes()),
                  "bound_alternate_sha256": approved["volume"]["alternate_sha256"]}
        try:
            result["apps_audit_sha256"] = driver.app_audit(prep, plan, paths, inspection["guest_result"], typed, bounds)
            result["stages"]["ios26-gpu"] = driver.run_stage(prep, plan, paths, "ios26-gpu", bounds)
            result["status"] = "NATIVE_GPU_BOOT_INPUTS_PREPARED"
        except BaseException as error:
            result["error"] = type(error).__name__ + ": " + str(error)
        finally:
            prep.atomic_json(WORK / "result.json", result)
            print(json.dumps({"status": result["status"], "completed": list(result["stages"]),
                              "error": result.get("error")}), flush=True)
        return 0 if result["status"] == "NATIVE_GPU_BOOT_INPUTS_PREPARED" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, InterruptedError) as error:
        print(json.dumps({"status": "REFUSED", "error": str(error)}), flush=True)
        raise SystemExit(2)
