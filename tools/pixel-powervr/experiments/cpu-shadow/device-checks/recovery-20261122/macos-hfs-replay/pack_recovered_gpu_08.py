#!/usr/bin/env python3
"""Complete locale and the standalone pack after a passed saved GPU disk inspection."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import sys
import types

BASE = Path("/data/local/tmp")
CONTROL = BASE / "asoft-recovered-control-01"
AUDIT = BASE / "asoft-recovered-gpu-audit-08"
BOOT = BASE / "asoft-recovered-gpu-boot-08"
INSTALL = BASE / "asoft-continue-05"
WORK = BASE / "asoft-recovered-pack-08"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_bytes())


def main():
    require(sys.argv[1:] == ["--execute"] and sys.flags.isolated and sys.dont_write_bytecode and os.geteuid() == 0,
            "requires root Python -I -B and explicit --execute")
    source = CONTROL / "inspect_recovered_gpu_boot_08.py"
    adapter = types.ModuleType("gpu_saved_disk_adapter")
    adapter.__file__ = str(source)
    source_body = source.read_bytes()
    require(source.resolve(strict=True) == source and hashlib.sha256(source_body).hexdigest() == "f86a876d400d1cce87bc0f7ecaf45782991fbc48d991932f8fb5fa77b91c8e19",
            "GPU inspection source differs")
    exec(compile(source_body, str(source), "exec"), vars(adapter))
    adapter.wait_for(5009)
    observation = read(AUDIT / "result.json")
    inspected = read(AUDIT / "inspection-session.json")
    boot = read(BOOT / "result.json")
    built = read(INSTALL / "result.json")
    guest = observation["guest_result"]
    require(observation["status"] == "SAVED_FIRSTBOOT_INSPECTION_PASSED" and
            observation["full_backing_chain_unchanged"] and observation["preparation_and_guard_unchanged"] and
            observation["natural_exit"] and observation["cleanup"]["echild"] and
            not observation["cleanup"]["forced_qemu"] and not observation["cleanup"]["forced_descendants"] and
            not observation["cleanup"]["errors"] and observation["cleanup"]["exit_code"] == 0 and
            all(observation["native_witnesses"].get(n) is True
                for n in ("native_initialization", "native_execution", "native_svc_final")) and
            not observation["native_witnesses"]["fatal_markers"] and guest["readonly_attachments"] and
            guest["raw_metadata_unchanged"] and guest["gpt"] == guest["baseline_gpt"] and
            all(guest["fsck"][n]["status"] == guest["journals"][n]["status"] == "PASSED"
                for n in ("Data", "iOSRoot")), "saved GPU disk inspection didn't pass")
    require(boot["status"] == "GUARDED_NATIVE_GPU_BOOT_OBSERVED" and boot["preservation_verified"] and
            adapter.sha((BOOT / "result.json").read_bytes()) == inspected["boot_result_sha256"] and
            boot["target_sha256"] == inspected["physical_boot_sha256"] and
            adapter.sha((INSTALL / "result.json").read_bytes()) == boot["preparation_sha256"],
            "GPU disk proof isn't bound to the accepted preparation")
    driver = adapter.load(CONTROL / "continue_recovered_chain_grace.py",
                          "6de8efcdcf93d6b9de4a357f696d0ad3ad6ca81a435e19f0b563650c41a7029b")
    _, receipt, recovery_proof = driver.wait_inspection(27579)
    session_body = (driver.PREP / "session.json").read_bytes()
    require(adapter.sha(session_body) == receipt["prep_session_sha256"] and
            built["whole_image_inspection_sha256"] == recovery_proof, "preparation inputs differ")
    session = json.loads(session_body)
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
        prep.refuse_live_children(INSTALL)
        prep.refuse_live_children(BOOT)
        prep.recheck({"session": session})
        driver.WORK = WORK
        plan, paths = driver.setup(prep, session, receipt,
                                  {"path": str(driver.RECOVERED), "sha256": driver.RECOVERED_SHA})
        primary = built["stages"]["ios26-gpu"]
        disk, trust = (BOOT / "files" / name for name in ("root.qcow2", "root.tc"))
        for path, digest in (
            (disk, boot["target_sha256"]), (trust, primary["root26-gpu.tc"]["sha256"]),
            (driver.RECOVERED, driver.RECOVERED_SHA),
        ):
            require(path.resolve(strict=True) == path and prep.cold.sha(path) == digest,
                    "saved input changed: " + path.name)
        chain = prep.cold.qcow_chain(disk)
        require([r["path"] for r in chain[5:]] == primary["root26-gpu.qcow2"]["backing_chain"] and
                str(driver.RECOVERED) in [r["path"] for r in chain], "saved disk ancestry differs")
        paths.update({"root.qcow2": disk, "root.tc": trust})
        for logical, path, digest in (("root.qcow2", disk, boot["target_sha256"]),
                                      ("root.tc", trust, primary["root26-gpu.tc"]["sha256"])):
            plan["artifacts"][logical] = {"path": str(path), "sha256": digest}
        plan["completed"].extend([*driver.STAGES, "ios26-gpu", "ios26-wallpaper"])
        preserved_paths = {disk, trust, *(Path(i["path"]) for i in chain)}
        original = {p: prep.cold.readonly_identity(p) for p in preserved_paths}
        WORK.mkdir(mode=0o700)
        (WORK / "attempts").mkdir(mode=0o700)
        bounds = types.SimpleNamespace(helper_seconds=3600, max_log_mib=64,
                                       min_free_mib=1536, min_available_mib=512)
        result = {"status": "INCOMPLETE", "apk_allowed": False,
                  "physical_gpu_disk_sha256": boot["target_sha256"],
                  "saved_gpu_disk_inspection_sha256": prep.cold.sha(AUDIT / "result.json")}
        try:
            result["locale"] = driver.run_stage(prep, plan, paths, "ios26-locale", bounds)
            require(shutil.disk_usage(WORK).free >= int((prep.stages.SPACE_GB["ios26-pack"] + 1.5) * 1e9),
                    "insufficient pack storage")
            for logical in {"root.qcow2", *prep.stages.PACK_FILES}:
                require(prep.cold.sha(paths[logical]) == plan["artifacts"][logical]["sha256"],
                        "pack input changed: " + logical)
            attempt = prep.next_attempt(plan, "ios26-pack")
            print(json.dumps({"stage": "ios26-pack", "attempt": str(attempt)}), flush=True)
            prep.pack_stage(plan, attempt, bounds)
            assets = attempt / "files/ios26"
            packed_disk = assets / "root26s-aod.qcow2"
            expected = {"root26s-aod.qcow2", "install.json", *prep.stages.PACK_FILES.values()}
            require({p.name for p in assets.iterdir()} == expected, "pack inventory differs")
            for logical, name in prep.stages.PACK_FILES.items():
                require(prep.cold.sha(assets / name) == plan["artifacts"][logical]["sha256"],
                        "pack copy changed: " + name)
            prep.image_tool(plan, ["compare", "-f", "qcow2", "-F", "qcow2",
                                   str(paths["root.qcow2"]), str(packed_disk)],
                            attempt, "compare-packed", bounds, 3600)
            require(all(prep.cold.readonly_identity(p) == i for p, i in original.items()) and
                    prep.cold.sha(disk) == boot["target_sha256"], "GPU boot input changed")
            result.update(status="VERIFIED_NATIVE_IOS26_PACK", assets=str(assets),
                          packed_disk_matches_locale=True,
                          files={f.name: {"bytes": f.stat().st_size, "sha256": prep.cold.sha(f)}
                                 for f in sorted(assets.iterdir())})
        except BaseException as error:
            result["error"] = type(error).__name__ + ": " + str(error)
        finally:
            prep.atomic_json(WORK / "result.json", result)
            print(json.dumps({"status": result["status"], "error": result.get("error")}), flush=True)
        return 0 if result["status"] == "VERIFIED_NATIVE_IOS26_PACK" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, InterruptedError) as error:
        print(json.dumps({"status": "REFUSED", "error": str(error)}), flush=True)
        raise SystemExit(2)
