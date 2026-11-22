#!/usr/bin/env python3
"""Continue native preparation on the inspected recovery chain."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import sys
import time
import types

BASE = Path("/data/local/tmp")
PREP = BASE / "pixel-prep-e9cc754"
RUNNER = BASE / "pixel-prep-runner-f4d64db"
AUDIT = BASE / "asoft-recovered-audit-01"
RECOVERED = BASE / "asoft-data-copy-recovery-01/recovered.qcow2"
RECOVERED_SHA = "edd1213461f0cf5b83b8e4e3e1c6b299ec56b20746f68c4b394c93bcbbac8735"
GUARD = BASE / "pixel-boot-checks-counter1/firstboot/guard_ios26_firstboot.py"
APP_SOURCE = BASE / "pixel-app-checks-0126693"
INSPECTOR = BASE / "pixel-saved-checks-resume5/inspect_ios26_firstboot_guest.py"
STAGES = ("ios26-persona", "ios26-activation", "ios26-apps")
WORK = BASE / "asoft-continue-02"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def load(path, digest):
    body = path.read_bytes()
    require(path.resolve(strict=True) == path and sha(body) == digest, "changed source " + str(path))
    module = types.ModuleType("bound_" + path.stem)
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def wait_inspection(pid):
    deadline = time.monotonic() + 600
    while True:
        try:
            state = Path("/proc", str(pid), "stat").read_text().rsplit(")", 1)[1].split()[0]
        except FileNotFoundError:
            break
        if state == "Z":
            break
        require(time.monotonic() < deadline, "inspection owner deadline")
        time.sleep(1)
    src = AUDIT / "result.json"
    require(src.is_file(), "inspection did not produce a receipt")
    body = src.read_bytes()
    result = json.loads(body)
    receipt = json.loads((AUDIT / "inspection-session.json").read_bytes())
    guest = result.get("guest_result", {})
    native, cleanup = result.get("native_witnesses", {}), result.get("cleanup", {})
    require(result["status"] == "SAVED_FIRSTBOOT_INSPECTION_PASSED" and
            result["full_backing_chain_unchanged"] and result["preparation_and_guard_unchanged"] and
            result["natural_exit"] and cleanup["echild"] and cleanup["exit_code"] == 0 and
            not cleanup["forced_descendants"] and not cleanup["forced_qemu"] and not cleanup["errors"] and
            all(native.get(k) is True for k in ("native_initialization", "native_execution", "native_svc_final")) and
            not native["fatal_markers"] and guest["readonly_attachments"] and guest["raw_metadata_unchanged"] and
            guest["gpt"] == guest["baseline_gpt"] and
            all(guest["fsck"][n]["status"] == guest["journals"][n]["status"] == "PASSED"
                for n in ("Data", "iOSRoot")) and
            receipt["recovered_descendant"]["sha256"] == RECOVERED_SHA,
            "no accepted whole-image inspection on the recovered descendant")
    return result, receipt, sha(body)


def setup(prep, session, receipt, recovered):
    completed = prep.stages.STAGES[:8]
    checkpoints = [PREP / "checkpoints" / (name + ".json") for name in completed]
    require(set(receipt["checkpoints"]) == set(map(str, checkpoints)), "inspection checkpoint prefix differs")
    artifacts = {}
    for checkpoint in checkpoints:
        body = checkpoint.read_bytes()
        require(sha(body) == receipt["checkpoints"][str(checkpoint)], "prepared checkpoint changed")
        artifacts.update(json.loads(body)["artifacts"])
    paths = {n: prep.contained(PREP, row["path"]) for n, row in artifacts.items()}
    artifacts = dict(artifacts)
    paths["root26g.qcow2"] = RECOVERED
    artifacts["root26g.qcow2"] = recovered
    manifest = Path(session["tooling"]) / prep.TOOL_ENTRIES["setup_manifest"]
    require(prep.cold.sha(manifest) == session["setup_manifest_sha256"], "setup manifest changed")
    plan = {"work": str(WORK), "session": session, "manifest": json.loads(manifest.read_bytes()),
            "artifacts": artifacts, "completed": list(completed)}
    prep.source_path = lambda _plan, logical: paths[logical]
    return plan, paths


def artifact(prep, path, predecessor=None):
    before = prep.cold.readonly_identity(path)
    row = {"path": str(path), "bytes": before["bytes"], "sha256": prep.cold.sha(path)}
    require(path.is_relative_to(WORK) and path.resolve(strict=True) == path and
            row["bytes"] > 0 and prep.cold.readonly_identity(path) == before, "output changed or escaped")
    if path.suffix == ".qcow2":
        chain = prep.cold.qcow_chain(path)
        require(chain[1:] == prep.cold.qcow_chain(predecessor), "output has wrong backing")
        row["backing_chain"] = [item["path"] for item in chain]
    return row


def run_stage(prep, plan, paths, name, bounds):
    require(shutil.disk_usage(WORK).free >= int((prep.stages.SPACE_GB[name] + 1.5) * 1e9),
            "insufficient stage storage")
    recipe = prep.stages.job(name, plan["manifest"])
    inputs = {row["source"] for row in recipe["disks"]}
    inputs.update(n for n in paths if any(n == f or n.startswith(f + "/") for f in recipe["files"]))
    for n in inputs:
        require(prep.cold.sha(paths[n]) == plan["artifacts"][n]["sha256"], "stage input bytes changed: " + n)
    started = {n: prep.cold.readonly_identity(paths[n]) for n in sorted(inputs)}
    attempt = prep.next_attempt(plan, name)
    prep.atomic_json(attempt / "stage-inputs.json", {"stage": name, "inputs": started})
    print(json.dumps({"stage": name, "attempt": str(attempt)}), flush=True)
    names = prep.helper_stage(plan, name, attempt, bounds)
    observed = json.loads((attempt / "vm-result.json").read_bytes())
    require(prep.vm_success(observed, True) and observed["witnesses"]["native_svc_final"],
            "missing accepted native stage")
    for n, previous in started.items():
        require(prep.cold.readonly_identity(paths[n]) == previous, "stage changed predecessor " + n)
    outputs = {}
    for logical in names:
        row = next((v for v in recipe["disks"] if v["logical"] == logical), None)
        previous = paths[row["source"]] if row else None
        path = attempt / "files" / logical
        outputs[logical] = artifact(prep, path, previous)
    prep.atomic_json(attempt / "stage-result.json", {"stage": name, "status": "STAGE_COMPLETE", "outputs": outputs})
    for logical, record in outputs.items():
        paths[logical] = Path(record["path"])
    plan["artifacts"].update(outputs)
    plan["completed"].append(name)
    return outputs


def app_audit(prep, plan, paths, predecessor, receipt, bounds):
    source = APP_SOURCE / "audit_ios26_apps.py"
    app = load(source, "948478f244ea96c40df5693f66bef7c28d4da59dee0db7cc56badac1377232e6")
    guest_path = APP_SOURCE / "audit_ios26_apps_guest.py"
    guest = load(guest_path, "aee8d203cc10fdc2a75d93bed9293d66588190e103cddb50720924c46a43c8c5")
    dependency = Path(receipt["partition_guest_source"])
    auditor = load(dependency, receipt["partition_guest_sha256"])
    firstboot_body = INSPECTOR.read_bytes()
    require(sha(firstboot_body) == receipt["inspector_sources"][INSPECTOR.name], "inspection guest source changed")
    os_image = paths[app.OS_LOGICAL]
    sources = [paths["root26-apps.qcow2"], paths["root26-activation.qcow2"], os_image]
    identities = [prep.cold.readonly_identity(p) for p in sources]
    state = {"prep": prep, "bodies": {guest_path.name: guest_path.read_bytes()}, "guest": guest,
             "partition_body": dependency.read_bytes(), "firstboot_body": firstboot_body, "auditor": auditor}
    attempt = WORK / "apps-audit"
    attempt.mkdir(mode=0o700)
    (attempt / "files").mkdir(mode=0o700)
    policy = {"schema": 1, "audit_nonce": os.urandom(16).hex(),
              "partition_guest_sha256": sha(state["partition_body"]), "firstboot_guest_sha256": sha(state["firstboot_body"]),
              "os_bytes": os_image.stat().st_size, "approved_system_journal": predecessor["journals"]["iOSRoot"]}
    prep.atomic_json(attempt / "expected-policy.json", policy)
    tar = app.input_tar(state, attempt, policy)
    raw = attempt / "out.raw"
    with raw.open("xb") as stream:
        stream.truncate(32 << 20)
    disks = [{"path": tar, "format": "raw", "readonly": True, "serial": "in"},
             {"path": raw, "format": "raw", "readonly": False, "serial": "out"}]
    disks.extend({"path": p, "format": fmt, "readonly": True, "serial": f"d{i}"}
                 for i, (p, fmt) in enumerate(zip(sources, ("qcow2", "qcow2", "raw"))))
    argv, env = prep.helper_command(plan, attempt, disks)
    observed = prep.supervise_vm(plan, "apps-copy-audit", attempt, argv, env, bounds)
    require(prep.vm_success(observed, True) and observed["witnesses"]["native_svc_final"] and
            len(observed["out_sizes"]) == 1, "app audit native completion incomplete")
    regular = prep.safe_return_tar(raw, observed["out_sizes"][0], attempt / "files", ["apps-audit"])
    require(regular <= app.OUTPUTS and "apps-audit/result.json" in regular, "app audit inventory differs")
    result_path = attempt / "files/apps-audit/result.json"
    result = json.loads(result_path.read_bytes())
    print(json.dumps({"stage": "apps-copy-audit", "guest_status": result["status"],
                      "errors": result["errors"]}), flush=True)
    app.guest_pass(state, result_path.parent, policy)
    require([prep.cold.readonly_identity(p) for p in sources] == identities, "read-only audit input changed")
    return sha(result_path.read_bytes())


def allow_natural_reap(cold):
    original = cold.reap_owned

    def reap(seconds=5):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            try:
                pid, _ = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                return {"echild": True, "forced_descendants": []}
            if not pid:
                time.sleep(0.025)
        return original(seconds)

    cold.reap_owned = reap


def interrupt(number, _frame):
    raise InterruptedError("stage owner interrupted: " + str(number))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--after-inspection-pid", type=int, required=True)
    args = parser.parse_args()
    require(sys.flags.isolated and sys.dont_write_bytecode and os.geteuid() == 0, "requires root Python -I -B")
    inspection, receipt, digest = wait_inspection(args.after_inspection_pid)
    guard = load(GUARD, "ea40638312d6ac41607806ecb03c148fbd0677df6ab01480e13fd40536869674")
    session_body = (PREP / "session.json").read_bytes()
    require(sha(session_body) == receipt["prep_session_sha256"], "preparation session changed")
    session = json.loads(session_body)
    prep = guard.load_frozen(RUNNER, session["runner_sources"])
    prep.cold.require_phone(session)
    prep.cold.subreaper()
    allow_natural_reap(prep.cold)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, interrupt)
    with (PREP / "owner.lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        prep.refuse_live_children(PREP)
        prep.recheck({"session": session})
        require(prep.cold.sha(RECOVERED) == RECOVERED_SHA and
                prep.cold.readonly_identity(RECOVERED) == receipt["recovered_descendant"]["identity"],
                "accepted recovery image changed")
        WORK.mkdir(mode=0o700)
        (WORK / "attempts").mkdir(mode=0o700)
        plan, paths = setup(prep, session, receipt, {"path": str(RECOVERED), "sha256": RECOVERED_SHA})
        bounds = types.SimpleNamespace(helper_seconds=3600, max_log_mib=64,
                                       min_free_mib=1536, min_available_mib=512)
        result = {"status": "INCOMPLETE", "whole_image_inspection_sha256": digest, "stages": {}}
        try:
            for name in STAGES:
                result["stages"][name] = run_stage(prep, plan, paths, name, bounds)
            result["apps_audit_sha256"] = app_audit(prep, plan, paths, inspection["guest_result"], receipt, bounds)
            result["stages"]["ios26-gpu"] = run_stage(prep, plan, paths, "ios26-gpu", bounds)
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
