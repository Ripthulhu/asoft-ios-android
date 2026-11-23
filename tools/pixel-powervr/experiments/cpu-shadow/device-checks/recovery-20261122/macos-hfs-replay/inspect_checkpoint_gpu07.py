#!/usr/bin/env python3
"""Inspect the recovered Data and whole image after the second GPU boot."""
import hashlib
import json
import os
from pathlib import Path
import sys
import types

BASE = Path("/data/local/tmp")
C = BASE / "asoft-recovered-control-01"
STATE = BASE / "asoft-data-copy-recovery-gpu06"
INSPECT = BASE / "asoft-gpu-resume-input-audit-07"
INTERRUPTED = BASE / "asoft-recovered-gpu-boot-06/files/root.qcow2"
OLDER = (BASE / "asoft-data-copy-recovery-gpu05/recovered.qcow2",
         BASE / "asoft-recovered-gpu-boot-05/files/root.qcow2")
RECOVERED = STATE / "recovered.qcow2"
INSTALL = BASE / "asoft-continue-05"


def need(ok, message):
    if not ok:
        raise ValueError(message)


def load(path, pin):
    data = path.read_bytes()
    need(path.resolve(strict=True) == path and hashlib.sha256(data).hexdigest() == pin,
         "changed source " + str(path))
    return data


def module(path, code, **extra):
    out = types.ModuleType("resume_" + path.stem)
    out.__file__ = str(path)
    vars(out).update(extra)
    exec(compile(code, str(path), "exec"), vars(out))
    return out


def read(path):
    return json.loads(path.read_bytes())


def inspect_input(adapter):
    adapter.wait_for(25471)
    manifest = read(STATE / "manifest.json")
    proof = read(STATE / "stop-proof.json")
    need(manifest["status"] == "RECOVERED_DATA_COPY_VERIFIED" and
         manifest["source_sha256"] == "344e7fb9b1e2dc140d3bcbb7e481de99a0211fe3830b794bccfc6c9d26e3b44d" and
         manifest["read_only_data_fsck_passed"] and manifest["outside_data_allocations"] == 0 and
         manifest["direct_data_readback_bytes"] == 16 << 30 and proof["qmp"]["failed_io_counters_zero"] and
         proof["source_sha256"] == manifest["source_sha256"] and
         adapter.sha((STATE / "manifest.json").read_bytes()) == proof["manifest_sha256"],
         "interrupted Data recovery did not pass")
    driver_path = C / "continue_recovered_chain_grace.py"
    driver = module(driver_path, load(driver_path,
                    "6de8efcdcf93d6b9de4a357f696d0ad3ad6ca81a435e19f0b563650c41a7029b"))
    _, receipt, prefix = driver.wait_inspection(27579)
    session_body = (driver.PREP / "session.json").read_bytes()
    need(adapter.sha(session_body) == receipt["prep_session_sha256"], "preparation session changed")
    session = json.loads(session_body)
    guard = driver.load(driver.GUARD, "ea40638312d6ac41607806ecb03c148fbd0677df6ab01480e13fd40536869674")
    prep = guard.load_frozen(driver.RUNNER, session["runner_sources"])
    prep.cold.require_phone(session)
    driver.allow_natural_reap(prep.cold)
    plan, _ = driver.setup(prep, session, receipt,
                            {"path": str(driver.RECOVERED), "sha256": driver.RECOVERED_SHA})
    built = read(INSTALL / "result.json")
    need(built["status"] == "NATIVE_GPU_BOOT_INPUTS_PREPARED" and
         built["whole_image_inspection_sha256"] == prefix, "GPU preparation differs")
    accepted = built["stages"]["ios26-gpu"]["root26-gpu.qcow2"]
    gpu = Path(accepted["path"])
    chain = prep.cold.qcow_chain(RECOVERED)
    need([r["path"] for r in chain] == [str(RECOVERED), str(INTERRUPTED), *map(str, OLDER), *accepted["backing_chain"]],
         "resume layer has the wrong backing chain")
    pins = [(RECOVERED, manifest["new_overlay_sha256"]), (INTERRUPTED, manifest["source_sha256"]),
            (gpu, accepted["sha256"]), (driver.RECOVERED, driver.RECOVERED_SHA),
            (OLDER[0], "d587766a186e6d1315718750b550f5136751df49a585e803eabdf957eafa9f02"),
            (OLDER[1], "163c2124429aee5e0ea74175158772d67f69a7a0c2d17cb579cb078c0028b7cc")]

    def unchanged(_state, full=True):
        need(prep.cold.qcow_chain(RECOVERED) == chain and
             all(prep.cold.sha(path) == digest for path, digest in pins), "resume disk changed")
        prep.recheck(plan)

    source_dir = driver.INSPECTOR.parent
    host = source_dir / "inspect_ios26_firstboot.py"
    inspector = module(host, load(host, receipt["inspector_sources"][host.name]))
    bodies = {n: load(source_dir / n, receipt["inspector_sources"][n]) for n in inspector.SOURCES}
    partition = Path(receipt["partition_guest_source"])
    part = load(partition, receipt["partition_guest_sha256"])
    inspector.unchanged_inputs = unchanged
    state = {"prep": prep, "prep_work": driver.PREP, "plan": plan, "work": INSPECT,
             "disk": RECOVERED, "baseline": gpu, "bodies": bodies, "dependency_body": part,
             "guest": module(driver.INSPECTOR, bodies[driver.INSPECTOR.name]),
             "auditor": module(partition, part), "receipt": {
                 "schema": 1, "kind": "interrupted_native_gpu_resume_input",
                 "partition_guest_sha256": receipt["partition_guest_sha256"],
                 "inspector_sources": receipt["inspector_sources"], "readonly": True,
                 "portable_recovery_manifest_sha256": proof["manifest_sha256"],
                 "recovered_wallpaper_sha256": manifest["new_overlay_sha256"]}}
    args = inspector.parser().parse_args(["--work", str(INSPECT), "--inspection-seconds", "1200", "--execute"])
    result = inspector.execute(state, args)
    guest = result.get("guest_result", {})
    print(json.dumps({"status": result["status"], "error": result.get("error"),
                      "guest_errors": guest.get("errors")}), flush=True)
    need(result["status"] == "SAVED_FIRSTBOOT_INSPECTION_PASSED" and
         result["full_backing_chain_unchanged"] and guest["raw_metadata_unchanged"] and
         all(guest["fsck"][n]["status"] == guest["journals"][n]["status"] == "PASSED"
             for n in ("iOSRoot", "Data")), "recovered wallpaper image didn't pass")
    return manifest["new_overlay_sha256"]


def main():
    need(sys.argv[1:] == ["--execute"] and
         sys.flags.isolated and sys.dont_write_bytecode and os.geteuid() == 0, "unexpected invocation")
    check_path = C / "inspect_recovered_gpu_boot_05.py"
    adapter = module(check_path, load(check_path,
                     "63bf97d0e939b081308940352ce76e7ecc3be2602600d4e74e6089048fb2cf81"))
    inspect_input(adapter)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"status": "REFUSED", "error": type(error).__name__ + ": " + str(error)}), flush=True)
        raise SystemExit(2)
