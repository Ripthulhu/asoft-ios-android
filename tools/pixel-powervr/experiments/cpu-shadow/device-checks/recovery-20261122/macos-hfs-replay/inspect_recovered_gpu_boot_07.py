#!/usr/bin/env python3
"""Inspect the saved GPU boot child with the pinned read-only disk checker."""
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
WORK = BASE / "asoft-recovered-gpu-audit-07"
BOOT = BASE / "asoft-recovered-gpu-boot-07"
INSTALL = BASE / "asoft-continue-05"
EXPECTED_TARGET = BOOT / "files/root.qcow2"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def load(path, digest):
    source = path.read_bytes()
    require(path.resolve(strict=True) == path and sha(source) == digest, "source changed " + str(path))
    mod = types.ModuleType("bound_" + path.stem)
    mod.__file__ = str(path)
    exec(compile(source, str(path), "exec"), mod.__dict__)
    return mod


def wait_for(pid):
    until = time.monotonic() + 36000
    while time.monotonic() < until:
        try:
            status = Path("/proc", str(pid), "stat").read_text().rsplit(")", 1)[1].split()[0]
        except FileNotFoundError:
            return
        if status == "Z":
            return
        time.sleep(3)
    raise TimeoutError("GPU boot owner deadline")


def read(path):
    return json.loads(path.read_bytes())


def main():
    require(sys.argv[1:] == ["--execute"] and sys.flags.isolated and sys.dont_write_bytecode and os.geteuid() == 0,
            "requires root Python -I -B and explicit --execute")
    wait_for(30548)
    boot = read(BOOT / "result.json")
    prepared = read(INSTALL / "result.json")
    require(boot["status"] == "GUARDED_NATIVE_GPU_BOOT_OBSERVED" and boot["preservation_verified"] and
            boot["guest_sync_answered"] and boot["qmp_io_proof"]["failed_io_counters_zero"] and
            boot["target"] == str(EXPECTED_TARGET) and
            boot["preparation_sha256"] == sha((INSTALL / "result.json").read_bytes()),
            "GPU boot must be independently accepted before inspection")
    native = boot["witnesses"]
    require(all(native.get(n) is True for n in ("native_initialization", "native_execution",
                "native_svc_final", "gpu_execution", "frame_captured")) and not native["fatal_markers"],
            "GPU or native evidence incomplete")
    driver = load(CONTROL / "continue_recovered_chain_grace.py",
                   "6de8efcdcf93d6b9de4a357f696d0ad3ad6ca81a435e19f0b563650c41a7029b")
    _, receipt, inspection_hash = driver.wait_inspection(27579)
    require(inspection_hash == prepared["whole_image_inspection_sha256"], "original inspection changed")
    session_raw = (driver.PREP / "session.json").read_bytes()
    require(sha(session_raw) == receipt["prep_session_sha256"], "session differs")
    session = json.loads(session_raw)
    guard = driver.load(driver.GUARD, "ea40638312d6ac41607806ecb03c148fbd0677df6ab01480e13fd40536869674")
    prep = guard.load_frozen(driver.RUNNER, session["runner_sources"])
    prep.cold.require_phone(session)
    driver.allow_natural_reap(prep.cold)
    plan, _ = driver.setup(prep, session, receipt,
                            {"path": str(driver.RECOVERED), "sha256": driver.RECOVERED_SHA})
    baseline = prepared["stages"]["ios26-gpu"]["root26-gpu.qcow2"]
    prior = Path(baseline["path"])
    require(prior.resolve(strict=True) == prior and prior.is_relative_to(INSTALL), "GPU parent escaped")
    chain = prep.cold.qcow_chain(EXPECTED_TARGET)
    require(chain[5:] == prep.cold.qcow_chain(prior) and
            [r["path"] for r in chain[1:5]] == [str(BASE / p) for p in (
                "asoft-data-copy-recovery-gpu06/recovered.qcow2",
                "asoft-recovered-gpu-boot-06/files/root.qcow2",
                "asoft-data-copy-recovery-gpu05/recovered.qcow2",
                "asoft-recovered-gpu-boot-05/files/root.qcow2")] and
            str(driver.RECOVERED) in [x["path"] for x in chain], "boot chain differs")
    pinned = [(EXPECTED_TARGET, boot["target_sha256"]), (prior, baseline["sha256"]),
              (driver.RECOVERED, driver.RECOVERED_SHA)]
    source_dir = driver.INSPECTOR.parent
    host = source_dir / "inspect_ios26_firstboot.py"
    inspector = load(host, receipt["inspector_sources"][host.name])
    bodies = {n: (source_dir / n).read_bytes() for n in inspector.SOURCES}
    require({n: sha(s) for n, s in bodies.items()} == receipt["inspector_sources"],
            "checker source set changed")
    auditor_path = Path(receipt["partition_guest_source"])
    auditor = load(auditor_path, receipt["partition_guest_sha256"])

    def unchanged(_state, full=True):
        require(prep.cold.qcow_chain(EXPECTED_TARGET) == chain, "inspection disk identity changed")
        require(all(prep.cold.sha(path) == pin for path, pin in pinned), "inspection disk hash changed")
        prep.recheck(plan)

    inspector.unchanged_inputs = unchanged
    state = {
        "prep": prep, "prep_work": driver.PREP, "plan": plan, "work": WORK,
        "disk": EXPECTED_TARGET, "baseline": prior, "bodies": bodies,
        "dependency_body": auditor_path.read_bytes(),
        "guest": load(driver.INSPECTOR, receipt["inspector_sources"][driver.INSPECTOR.name]),
        "auditor": auditor, "receipt": {"schema": 1, "kind": "recovered_gpu_boot_disk_inspection",
             "boot_result_sha256": sha((BOOT / "result.json").read_bytes()),
             "physical_boot_sha256": boot["target_sha256"],
             "partition_guest_sha256": receipt["partition_guest_sha256"],
             "inspector_sources": receipt["inspector_sources"], "readonly": True},
    }
    for s in (signal.SIGINT, signal.SIGTERM):
        signal.signal(s, driver.interrupt)
    args = inspector.parser().parse_args(["--work", str(WORK), "--inspection-seconds", "1200", "--execute"])
    result = inspector.execute(state, args)
    guest = result.get("guest_result", {})
    print(json.dumps({"status": result["status"], "error": result.get("error"),
                      "identity_error": result.get("identity_error"), "guest_errors": guest.get("errors"),
                      "journal_status": {k: j["status"] for k, j in guest.get("journals", {}).items()}}), flush=True)
    return 0 if result["status"] == "SAVED_FIRSTBOOT_INSPECTION_PASSED" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, InterruptedError) as error:
        print(json.dumps({"status": "REFUSED", "error": str(error)}), flush=True)
        raise SystemExit(2)
