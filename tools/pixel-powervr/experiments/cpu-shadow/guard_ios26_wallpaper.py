#!/usr/bin/env python3
"""Run only the frozen wallpaper stage under explicit additional evidence guards.

Default preflight writes nothing. The original runner still creates its own
checkpoint, owns QEMU and closes its frame descriptor. This separate source
adds only receipt/input checks and the disclosed QMP/supervision hooks.
"""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import struct
import sys
import time
import types


STAGE = "ios26-wallpaper"
PREDECESSOR = "ios26-gpu"
DISK_BYTES = 51_541_704_704
DISKS = (("ios26-partition", "root26g.qcow2"), ("ios26-firstboot", "root26g.qcow2"),
         ("ios26-persona", "root26g.qcow2"), ("ios26-activation", "root26-activation.qcow2"),
         ("ios26-apps", "root26-apps.qcow2"), (PREDECESSOR, "root26-gpu.qcow2"), (STAGE, "root.qcow2"))
NO_BOOT = {"boot_complete": False, "gpu_path_complete": False, "app_gate_changed": False}
# Independently reviewed app-copy auditor, commit fe0a649ab7b5135f8b9b6729802c3418e336e347.
APP_AUDITOR_SOURCES = {
    "audit_ios26_apps.py": "948478f244ea96c40df5693f66bef7c28d4da59dee0db7cc56badac1377232e6",
    "audit_ios26_apps_guest.py": "aee8d203cc10fdc2a75d93bed9293d66588190e103cddb50720924c46a43c8c5",
}


def sha(body):
    return hashlib.sha256(body).hexdigest()


def canonical(value, exists=True):
    path = Path(value).absolute()
    if path != path.resolve(strict=exists) or any(c in str(path) for c in ",\r\n\x00"):
        raise ValueError("noncanonical or unsupported path")
    return path


def read(path, limit=4 << 20):
    path = canonical(path)
    if not stat.S_ISREG(path.lstat().st_mode) or path.stat().st_size > limit:
        raise ValueError("nonregular or oversized source/metadata file")
    return path.read_bytes()


def module_from(body, path):
    module = types.ModuleType("bound_" + Path(path).stem)
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def prefix(inventory, through):
    names = inventory["completed"][:inventory["completed"].index(through) + 1]
    artifacts, prior = {}, {}
    for name in names:
        artifacts.update(inventory["rows"][name]["artifacts"])
        if name != through:
            prior.update(inventory["rows"][name]["artifacts"])
    return {"completed": names, "rows": {n: inventory["rows"][n] for n in names},
            "hashes": {p: value for p, value in inventory["hashes"].items() if Path(p).stem in names},
            "artifacts": artifacts, "prior": prior}


def checkpoint_inventory(prep, work, session, through):
    if through not in (PREDECESSOR, STAGE):
        raise ValueError("wallpaper guards accept only GPU or wallpaper boundaries")
    expected = list(prep.stages.STAGES[:prep.stages.STAGES.index(through) + 1])
    if {p.name for p in (work / "checkpoints").iterdir()} != {name + ".json" for name in expected}:
        raise ValueError("current checkpoint boundary is not the exact requested wallpaper boundary")
    rows, hashes, previous = {}, {}, None
    for name in expected:
        path = work / "checkpoints" / (name + ".json")
        body = read(path)
        row = json.loads(body)
        if (row.get("schema") != 1 or row.get("status") != "STAGE_COMPLETE" or row.get("stage") != name or
                row.get("session_sha256") != prep.digest(session) or row.get("previous_sha256") != previous or
                type(row.get("artifacts")) is not dict):
            raise ValueError("invalid current checkpoint chain")
        for logical, record in row["artifacts"].items():
            prep.stages.relative(logical)
            prep.stages.relative(record["path"])
        rows[name], hashes[str(path)] = row, sha(body)
        previous = hashes[str(path)]
    return prefix({"completed": expected, "rows": rows, "hashes": hashes}, through)


def full_disks(prep, work, inventory):
    sequence = DISKS[:6 if inventory["completed"][-1] == PREDECESSOR else 7]
    records = [inventory["rows"][stage]["artifacts"][name] for stage, name in sequence]
    paths = [record["path"] for record in reversed(records)]
    if len(paths) != len(set(paths)):
        raise ValueError("each immutable disk generation must have a distinct owned path")
    result = []
    for index, record in enumerate(reversed(records)):
        path = canonical(prep.contained(work, record["path"]))
        chain = [canonical(item["path"]).relative_to(work).as_posix() for item in prep.cold.qcow_chain(path)]
        if chain != paths[index:] or record.get("backing_chain") != chain:
            raise ValueError("actual backing chain differs from exact checkpoint ancestry")
        before = prep.cold.readonly_identity(path)
        with path.open("rb") as stream:
            header = stream.read(32)
        if len(header) != 32 or struct.unpack_from(">Q", header, 24)[0] != DISK_BYTES:
            raise ValueError("backing-chain virtual geometry changed")
        actual = prep.file_record(path, work)
        if actual != record or prep.cold.readonly_identity(path) != before:
            raise ValueError("full disk/backing hash or identity changed")
        result.append({"identity": before, "record": actual})
    return result


def require_boundary(prep, plan):
    expected = list(prep.stages.STAGES[:prep.stages.STAGES.index(STAGE)])
    if (plan["completed"] != expected or plan["remaining"] != [STAGE] or plan["through"] != STAGE or
            plan["network_stages"] or plan["guest_boot_stages"] != [STAGE] or plan["helper_smoke"]):
        raise ValueError("guard requires exactly GPU completed and wallpaper as its only new stage")
    if (prep.stages.boot_inputs(STAGE) != {"source": "root26-gpu.qcow2", "output": "root.qcow2",
            "kernel": "fw/bootkc", "tree": "dtree-phone-aod", "trustcache": "root26-gpu.tc",
            "settle_seconds": 360, "deadline_seconds": 18000}):
        raise ValueError("wallpaper boot/settling contract changed")


def app_audit_acceptance(app, state, audit_work, receipt, result, prior, inputs, bodies):
    """Revalidate the passed app audit at its original, shorter prefix."""
    prep, plan, session = state["prep"], state["plan"], state["plan"]["session"]
    work, inventory = state["prep_work"], prefix(state["inventory"], app.STAGE)
    scripts = {str(canonical(session["tooling"]) / "setup" / name): value for name, value in app.SCRIPT_SHA256.items()}
    dependencies = {"partition_guest_sha256": app.APPROVED["audit_ios26_partition_guest.py"],
                    "firstboot_guest_sha256": app.APPROVED["inspect_ios26_firstboot_guest.py"]}
    if (receipt.get("schema") != 1 or receipt.get("kind") != "ios26_apps_copy_audit" or
            receipt.get("prep_work") != str(work) or receipt.get("runner_dir") != str(state["runner"]) or
            receipt.get("prep_session_sha256") != sha(read(work / "session.json")) or
            receipt.get("frozen_sources") != session["runner_sources"] or receipt.get("through") != app.STAGE or
            receipt.get("checkpoints") != inventory["hashes"] or receipt.get("input_chains") != inputs or
            receipt.get("prior_evidence") != prior or receipt.get("auditor_sources") != APP_AUDITOR_SOURCES or
            receipt.get("dependency_sources") != dependencies or receipt.get("script_files") != scripts or
            receipt.get("runtime") != session["runtime"] or
            receipt.get("qualification_sha256") != session["qualification"]["qualification_sha256"] or
            receipt.get("tooling_manifest_sha256") != session["tooling_manifest_sha256"] or
            receipt.get("helper_initrd_sha256") != app.INITRD_SHA256 or
            receipt.get("helper_ram_mib") != session["helper_ram_mib"] or receipt.get("helper_vcpus") != session["helper_vcpus"] or
            receipt.get("readonly_inputs") is not True or receipt.get("replay_allowed") is not False or
            receipt.get("repair_allowed") is not False or receipt.get("native_required") is not True or
            receipt.get("tcg_retry") is not False):
        raise ValueError("app audit does not bind the exact original apps prefix and approved source")
    bounds = receipt.get("bounds", {})
    if (type(bounds.get("helper_seconds")) is not int or not 60 <= bounds["helper_seconds"] <= 14400 or
            type(bounds.get("max_log_mib")) is not int or not 8 <= bounds["max_log_mib"] <= 64 or
            type(bounds.get("min_free_mib")) is not int or bounds["min_free_mib"] < 1536 or
            type(bounds.get("min_available_mib")) is not int or bounds["min_available_mib"] < 512):
        raise ValueError("app audit execution bounds differ from the approved contract")
    if any(sha(read(path)) != expected for path, expected in scripts.items()) or prep.cold.sha(canonical(session["tooling"]) / "helper/initrd.gz") != app.INITRD_SHA256:
        raise ValueError("reviewed app-copy scripts or helper utility image changed")
    if (result.get("schema") != 1 or result.get("status") != "APP_COPY_AUDIT_PASSED" or
            result.get("apps_audit_session_sha256") != prep.digest(receipt) or
            result.get("full_input_chains_unchanged") is not True or
            result.get("preparation_and_prior_evidence_unchanged") is not True):
        raise ValueError("completed unchanged app-copy audit is mandatory")
    app.require_native(result)
    attempt = canonical(result.get("attempt", ""))
    if attempt != audit_work / "a1" or json.loads(read(attempt / "apps-audit-result.json")) != result:
        raise ValueError("app audit result copies or owned attempt disagree")
    policy = json.loads(read(attempt / "expected-policy.json"))
    if (policy.get("schema") != 1 or not re.fullmatch(r"[0-9a-f]{32}", policy.get("audit_nonce", "")) or
            policy.get("apps_audit_session_sha256") != prep.digest(receipt) or
            any(policy.get(name) != value for name, value in dependencies.items()) or
            policy.get("os_bytes") != inventory["artifacts"][app.OS_LOGICAL]["bytes"] or
            policy.get("approved_system_journal") != prior["approved_system_journal"]):
        raise ValueError("app audit policy does not belong to its approved predecessor/session")
    launch_path = attempt / "launch.json"
    if result.get("launch") != {"path": str(launch_path), "sha256": sha(read(launch_path))}:
        raise ValueError("app audit actual launch identity changed")
    vm = json.loads(read(attempt / "vm-result.json"))
    if (vm.get("stage") != "apps-copy-audit" or not prep.vm_success(vm, True) or
            vm.get("status") != "VM_OBSERVATION_COMPLETE" or vm.get("natural_exit") is not True or
            vm.get("witnesses") != result["native_witnesses"] or vm.get("cleanup") != result["cleanup"] or
            len(vm.get("out_sizes", [])) != 1):
        raise ValueError("app audit actual native completion/cleanup differs from its receipt")
    if set(result.get("outputs", {})) != app.OUTPUTS:
        raise ValueError("app audit complete raw metadata inventory required")
    files = {**prior["files"], **scripts}
    for name, record in result["outputs"].items():
        path = prep.verify_artifact(record, audit_work)
        if path != attempt / "files" / name:
            raise ValueError("app audit output is not in its owned collection directory")
        files[str(path)] = sha(read(path))
    if app.guest_pass({"prep": prep, "auditor": state["auditor"], "guest": state["app_guest"]},
                      attempt / "files/apps-audit", policy) != result.get("guest_result"):
        raise ValueError("app audit raw comparison result differs from its receipt")
    for path in (audit_work / "apps-audit-session.json", audit_work / "result.json",
                 attempt / "apps-audit-result.json", attempt / "expected-policy.json", launch_path, attempt / "vm-result.json"):
        files[str(path)] = sha(read(path))
    for name, body in bodies.items():
        path = canonical(Path(receipt["source_directory"]) / name)
        if sha(read(path)) != sha(body) or sha(body) != APP_AUDITOR_SOURCES[name]:
            raise ValueError("committed app auditor source changed during verification")
        files[str(path)] = sha(body)
    return {"work": str(audit_work), "source_directory": receipt["source_directory"],
            "source_hashes": APP_AUDITOR_SOURCES.copy(),
            "apps_audit_session_sha256": sha(read(audit_work / "apps-audit-session.json")),
            "apps_audit_result_sha256": sha(read(audit_work / "result.json")),
            "checkpoints": inventory["hashes"], "files": files}


def context(apps_audit_work, through):
    """Read-only validation usable at GPU or wallpaper, preserving older scopes."""
    if set(APP_AUDITOR_SOURCES) != {"audit_ios26_apps.py", "audit_ios26_apps_guest.py"}:
        raise ValueError("committed app-copy auditor source approval is not installed")
    audit_work = canonical(apps_audit_work)
    receipt = json.loads(read(audit_work / "apps-audit-session.json"))
    result = json.loads(read(audit_work / "result.json"))
    directory = canonical(receipt["source_directory"])
    bodies = {name: read(directory / name) for name in APP_AUDITOR_SOURCES}
    if receipt.get("auditor_sources") != APP_AUDITOR_SOURCES or {n: sha(b) for n, b in bodies.items()} != APP_AUDITOR_SOURCES:
        raise ValueError("app-copy audit sources are not the approved committed pair")
    app = module_from(bodies["audit_ios26_apps.py"], directory / "audit_ios26_apps.py")
    app_guest = module_from(bodies["audit_ios26_apps_guest.py"], directory / "audit_ios26_apps_guest.py")
    inspection_work = canonical(receipt["prior_evidence"]["inspection_work"])
    inspected = json.loads(read(inspection_work / "inspection-session.json"))
    inspection_result = json.loads(read(inspection_work / "result.json"))
    old_directory = canonical(inspected["source_directory"])
    expected_inspector = {name: app.APPROVED[name] for name in ("inspect_ios26_firstboot.py", "inspect_ios26_firstboot_guest.py")}
    if inspected.get("inspector_sources") != expected_inspector:
        raise ValueError("earlier saved-firstboot inspection source pair changed")
    inspector, _ = app.approved_module(old_directory / "inspect_ios26_firstboot.py")
    _, raw_body = app.approved_module(old_directory / "inspect_ios26_firstboot_guest.py")
    firstguard, _ = app.approved_module(inspected["guard_source"])
    if inspected.get("guard_source_sha256") != app.APPROVED["guard_ios26_firstboot.py"]:
        raise ValueError("earlier execution guard source changed")
    auditor, partition_body = app.approved_module(inspected["partition_guest_source"])
    work, runner = canonical(inspected["prep_work"]), canonical(inspected["runner_dir"])
    session_body = read(work / "session.json")
    session = json.loads(session_body)
    if (session.get("kind") != "standalone_ios26_preparation" or session.get("native_required") is not True or
            session.get("tcg_retry") is not False or session.get("guest_ram_gib") != 3 or session.get("timebase_hz") != 38_400_000):
        raise ValueError("unsupported preparation/native/memory contract")
    prep = firstguard.load_frozen(runner, session["runner_sources"])
    parsed, argv = firstguard.runner_arguments(prep, session, work, runner)
    parsed.through, parsed.execute = STAGE, False
    argv[argv.index("--through") + 1] = STAGE
    plan = prep.preflight(parsed)
    inventory = checkpoint_inventory(prep, work, session, through)
    if (plan["session"] != session or plan["completed"] != inventory["completed"] or
            plan["artifacts"] != inventory["artifacts"] or
            plan["remaining"] != ([STAGE] if through == PREDECESSOR else []) or
            plan["manifest"]["os"]["ios26"]["vars"]["OS"] != Path(app.OS_LOGICAL).name):
        raise ValueError("exact current wallpaper boundary was not reproduced")
    earlier = prefix(inventory, app.STAGE)
    prior = app.saved_inspection(inspector, firstguard, prep, inspection_work, inspected,
                                 inspection_result, earlier, plan, session)
    inputs = app.full_inputs(prep, work, earlier)
    state = {"prep": prep, "firstguard": firstguard, "app": app, "app_guest": app_guest,
        "auditor": auditor, "plan": plan, "inventory": inventory, "prep_work": work, "runner": runner,
        "runner_args": parsed, "equivalent_argv": argv, "app_receipt": receipt,
        "raw_body": raw_body, "partition_body": partition_body,
        "raw_source": old_directory / "inspect_ios26_firstboot_guest.py",
        "partition_source": canonical(inspected["partition_guest_source"])}
    state["apps_audit"] = app_audit_acceptance(app, state, audit_work, receipt, result, prior, inputs, bodies)
    state["disk_chain"] = full_disks(prep, work, inventory)
    return state


def output_roots(state):
    session, receipt = state["plan"]["session"], state["app_receipt"]
    return {state["prep_work"], state["runner"], canonical(session["tooling"]), canonical(session["package"]),
            canonical(session["qualification_file"]).parent, canonical(state["apps_audit"]["work"]),
            canonical(receipt["source_directory"]), canonical(receipt["prior_evidence"]["inspection_work"]),
            canonical(receipt["prior_evidence"]["guard_work"]),
            canonical(receipt["prior_evidence"]["partition_audit"]["work"]),
            canonical(receipt["prior_evidence"]["partition_audit"]["source_directory"]),
            *{Path(path).parent for path in state["apps_audit"]["files"]}}


def preflight(args):
    if not args.apps_audit_work or not args.work:
        raise ValueError("required --apps-audit-work and --work")
    work = canonical(args.work, False)
    if work.exists() or not work.parent.is_dir():
        raise ValueError("guard evidence directory must be fresh with an existing parent")
    state = context(args.apps_audit_work, PREDECESSOR)
    prep, plan, session = state["prep"], state["plan"], state["plan"]["session"]
    require_boundary(prep, plan)
    source = canonical(__file__)
    if any(work.is_relative_to(root) or root.is_relative_to(work) for root in output_roots(state) | {source.parent}):
        raise ValueError("guard output must be outside all input/source/evidence roots")
    identities = {name: prep.cold.readonly_identity(prep.source_path(plan, name)) for name in plan["artifacts"]}
    receipt = {"schema": 1, "kind": "ios26_wallpaper_execution_guard", "guard_source": str(source),
        "guard_source_sha256": sha(read(source)), "prep_work": str(state["prep_work"]), "runner_dir": str(state["runner"]),
        "prep_session_sha256": sha(read(state["prep_work"] / "session.json")), "frozen_sources": session["runner_sources"],
        "apps_audit": state["apps_audit"], "bound_files": state["apps_audit"]["files"],
        "checkpoints": state["inventory"]["hashes"], "input_identities": identities,
        "input_disk_chain": state["disk_chain"], "prior_input_chains": state["app_receipt"]["input_chains"],
        "equivalent_frozen_runner_argv": state["equivalent_argv"],
        "execution_method": "in-process frozen prepare.execute with two explicit wallpaper guard hooks",
        "hooks": ["Qmp.call(stop): original stop then strict post-stop blockstats",
                  "supervise_vm(ios26-wallpaper): delegate then require shell sync and original native/GPU/frame/settling witnesses"],
        "counter_scope": "recorded failed guest writes/flushes; stop-internal flush return is not observed",
        "mandatory_next_gate": "separate saved-wallpaper raw journal and forced read-only fsck before locale",
        **NO_BOOT}
    state.update(work=work, receipt=receipt, events=[], supervision=[])
    state["runner_args"].execute = True
    return state


def guard_acceptance(state, guard_work, receipt, result, recorded):
    """Accept only the exact successful guard and current wallpaper checkpoint."""
    prep, work, inventory = state["prep"], state["prep_work"], state["inventory"]
    session, predecessor = state["plan"]["session"], prefix(inventory, PREDECESSOR)
    if inventory["completed"][-1] != STAGE:
        raise ValueError("wallpaper receipt acceptance requires exactly its completed boundary")
    checkpoint_path, checkpoint = work / "checkpoints" / (STAGE + ".json"), inventory["rows"][STAGE]
    identities = {name: prep.cold.readonly_identity(prep.contained(work, row["path"]))
                  for name, row in predecessor["artifacts"].items()}
    source = canonical(__file__)
    if (receipt.get("schema") != 1 or receipt.get("kind") != "ios26_wallpaper_execution_guard" or
            receipt.get("guard_source") != str(source) or receipt.get("guard_source_sha256") != sha(read(source)) or
            receipt.get("prep_work") != str(work) or receipt.get("runner_dir") != str(state["runner"]) or
            receipt.get("prep_session_sha256") != sha(read(work / "session.json")) or
            receipt.get("frozen_sources") != session["runner_sources"] or receipt.get("apps_audit") != state["apps_audit"] or
            receipt.get("bound_files") != state["apps_audit"]["files"] or receipt.get("checkpoints") != predecessor["hashes"] or
            receipt.get("input_identities") != identities or receipt.get("input_disk_chain") != state["disk_chain"][1:] or
            receipt.get("prior_input_chains") != state["app_receipt"]["input_chains"] or
            receipt.get("equivalent_frozen_runner_argv") != state["equivalent_argv"] or
            result.get("schema") != 1 or result.get("status") != "GUARDED_WALLPAPER_COMPLETE" or
            result.get("guard_session_sha256") != prep.digest(receipt) or
            result.get("checkpoint_accepted_by_guard") is not True or
            result.get("original_wallpaper_checkpoint_present") is not True or result.get("bound_inputs_unchanged") is not True or
            result.get("checkpoint") != {"path": str(checkpoint_path), "sha256": inventory["hashes"][str(checkpoint_path)]} or
            result.get("output_disk_chain") != state["disk_chain"]):
        raise ValueError("exact successful wallpaper guard, original inputs and current checkpoint required")
    output_tc, original_tc = checkpoint["artifacts"].get("root.tc", {}), predecessor["artifacts"]["root26-gpu.tc"]
    if (set(checkpoint["artifacts"]) != {"root.qcow2", "root.tc"} or
            (output_tc.get("bytes"), output_tc.get("sha256")) != (original_tc["bytes"], original_tc["sha256"])):
        raise ValueError("wallpaper disk/trustcache output contract changed")
    prep.verify_artifact(output_tc, work)
    events, supervision = result.get("post_stop_blockstats"), result.get("supervision")
    if (type(events) is not list or len(events) != 1 or type(supervision) is not list or len(supervision) != 1 or
            recorded != {"schema": 1, "post_stop_blockstats": events, "supervision": supervision}):
        raise ValueError("wallpaper guard observations missing or inconsistent")
    event, observed = events[0], supervision[0]
    counters = state["firstguard"].failed_io_counters(event.get("post_stop_blockstats"))
    if (event.get("status") != "COUNTERS_CHECKED" or event.get("stop_acknowledged") is not True or
            event.get("failed_io_counters_zero") is not True or event.get("counter_check") != counters or
            event.get("stop_internal_flush_return_observed") is not False or
            observed.get("stage") != STAGE or observed.get("status") != "GUARDED_SUPERVISION_PASSED" or
            observed.get("original_supervision_status") != "VM_OBSERVATION_COMPLETE" or observed.get("guest_sync_answered") is not True):
        raise ValueError("wallpaper failed-I/O counter/shell-sync witnesses are incomplete")
    actual = result.get("actual_attempt", {})
    attempt = canonical(actual.get("attempt", ""))
    if (attempt.parent != work / "attempts" or not re.fullmatch(r"12-\d{4}", attempt.name) or
            str(attempt) != checkpoint.get("attempt") or str(attempt) != observed.get("attempt")):
        raise ValueError("guard attempt is not the checkpoint's wallpaper attempt")
    expected = {"stage-inputs.json", "launch.json", "vm-result.json", "stage-result.json"}
    if set(actual.get("files", {})) != expected:
        raise ValueError("wallpaper guard attempt metadata inventory incomplete")
    files, decoded = {}, {}
    for name in sorted(expected):
        body = read(attempt / name)
        if actual["files"][name] != {"sha256": sha(body), "bytes": len(body)}:
            raise ValueError("wallpaper guard attempt metadata changed")
        files[str(attempt / name)] = sha(body)
        decoded[name] = json.loads(body)
    launch, vm = decoded["launch.json"], decoded["vm-result.json"]
    if (launch != actual.get("launch.json") or vm != actual.get("vm-result.json") or
            decoded["stage-result.json"] != checkpoint or
            decoded["stage-inputs.json"] != {"stage": STAGE, "session_sha256": prep.digest(session), "inputs": identities} or
            vm.get("stage") != STAGE or vm.get("status") != "VM_OBSERVATION_COMPLETE" or
            vm.get("guest_sync_answered") is not True or not prep.vm_success(vm, False)):
        raise ValueError("wallpaper launch/native/cleanup metadata differs from its original guarded attempt")
    trace = [row for row in vm.get("qmp", []) if row.get("request", {}).get("execute") in ("stop", "query-blockstats", "quit")]
    if ([row.get("request", {}).get("execute") for row in trace] != ["stop", "query-blockstats", "quit"] or
            any("error" in row.get("response", {}) or "return" not in row.get("response", {}) for row in trace) or
            trace[1]["response"]["return"] != event["post_stop_blockstats"]):
        raise ValueError("actual wallpaper QMP trace lacks the ordered guarded counter check")
    devices = [launch["command"][i + 1] for i, arg in enumerate(launch.get("command", [])[:-1]) if arg == "-device"]
    if [d for d in devices if "drive=root" in d] != ["virtio-blk-pci,drive=root"]:
        raise ValueError("unreviewed wallpaper block-sector configuration")
    files.update({str(guard_work / name): sha(read(guard_work / name))
                  for name in ("guard-session.json", "result.json", "guard-observations.json")})
    files[str(source)] = sha(read(source))
    return files


def unchanged_inputs(state, allow_wallpaper=False, full=False):
    prep, receipt, work = state["prep"], state["receipt"], state["prep_work"]
    if sha(read(receipt["guard_source"])) != receipt["guard_source_sha256"]:
        raise ValueError("wallpaper guard source changed")
    if sha(read(work / "session.json")) != receipt["prep_session_sha256"]:
        raise ValueError("preparation session changed")
    if {name: sha(read(Path(receipt["runner_dir"]) / name)) for name in receipt["frozen_sources"]} != receipt["frozen_sources"]:
        raise ValueError("frozen runner sources changed")
    for path, expected in receipt["bound_files"].items():
        if sha(read(path)) != expected:
            raise ValueError("bound app/prior evidence or dependency source changed")
    current = STAGE if allow_wallpaper and (work / "checkpoints" / (STAGE + ".json")).exists() else PREDECESSOR
    inventory = checkpoint_inventory(prep, work, state["plan"]["session"], current)
    predecessor = prefix(inventory, PREDECESSOR)
    if predecessor["hashes"] != receipt["checkpoints"]:
        raise ValueError("original GPU checkpoint prefix changed")
    for original in receipt["input_identities"].values():
        if prep.cold.readonly_identity(original["path"]) != original:
            raise ValueError("immutable wallpaper input changed")
    if full:
        checked = full_disks(prep, work, predecessor)
        if checked != receipt["input_disk_chain"]:
            raise ValueError("full original GPU/backing identity changed")
        known = {row["identity"]["path"]: row for row in checked}
        for original in receipt["prior_input_chains"]:
            path = original["identity"]["path"]
            if path in known:
                if original != known[path]:
                    raise ValueError("app audit predecessor identity changed")
            elif (prep.cold.readonly_identity(path) != original["identity"] or
                  prep.file_record(Path(path), work) != original["record"] or
                  prep.cold.readonly_identity(path) != original["identity"]):
                raise ValueError("full original app-audit input changed")
    elif any(prep.cold.readonly_identity(row["identity"]["path"]) != row["identity"] for row in receipt["prior_input_chains"]):
        raise ValueError("original app-audit input identity changed")
    prep.recheck(state["plan"])


def observations(state):
    state["prep"].atomic_json(state["work"] / "guard-observations.json",
        {"schema": 1, "post_stop_blockstats": state["events"], "supervision": state["supervision"]})


@contextlib.contextmanager
def installed_hooks(state):
    prep = state["prep"]
    original_call, original_supervise = prep.cold.Qmp.call, prep.supervise_vm

    def guarded_call(qmp, name, seconds):
        if name != "stop":
            return original_call(qmp, name, seconds)
        event = {"started_utc": prep.cold.utc(), "status": "INCOMPLETE", "failed_io_counters_zero": False,
                 "stop_internal_flush_return_observed": False}
        state["events"].append(event)
        try:
            returned = original_call(qmp, name, seconds)
            event["stop_acknowledged"] = True
            unchanged_inputs(state)
            stats = original_call(qmp, "query-blockstats", 5)
            event["post_stop_blockstats"] = stats
            event["counter_check"] = state["firstguard"].failed_io_counters(stats)
            unchanged_inputs(state)
            event.update(status="COUNTERS_CHECKED", failed_io_counters_zero=True)
            return returned
        except BaseException as error:
            event["error"] = type(error).__name__ + ": " + str(error)
            raise
        finally:
            event["finished_utc"] = prep.cold.utc()
            observations(state)

    def guarded_supervise(plan, stage, attempt, argv, env, args, frame=None):
        if stage != STAGE or frame is None:
            raise ValueError("wallpaper guard cannot supervise another stage or a helper")
        event = {"stage": stage, "attempt": str(attempt), "status": "INCOMPLETE", "started_utc": prep.cold.utc()}
        state["supervision"].append(event)
        try:
            unchanged_inputs(state)
            result = original_supervise(plan, stage, attempt, argv, env, args, frame)
            event["original_supervision_status"] = result.get("status")
            event["guest_sync_answered"] = result.get("guest_sync_answered") is True
            if result.get("guest_sync_answered") is not True:
                raise ValueError("wallpaper did not return the mandatory shell __SYNCED__ witness")
            if not prep.vm_success(result, False) or result.get("status") != "VM_OBSERVATION_COMPLETE":
                raise ValueError("original wallpaper native/GPU/frame/milestone/settling requirements failed")
            if len(state["events"]) != 1 or state["events"][0].get("failed_io_counters_zero") is not True:
                raise ValueError("wallpaper lacks its unique verified post-stop failed-I/O check")
            unchanged_inputs(state)
            event["status"] = "GUARDED_SUPERVISION_PASSED"
            return result
        except BaseException as error:
            event["error"] = type(error).__name__ + ": " + str(error)
            raise
        finally:
            event["finished_utc"] = prep.cold.utc()
            observations(state)
    prep.cold.Qmp.call, prep.supervise_vm = guarded_call, guarded_supervise
    try:
        yield
    finally:
        prep.cold.Qmp.call, prep.supervise_vm = original_call, original_supervise


def owned_attempts(state):
    prefix_name = f"{state['prep'].stages.STAGES.index(STAGE):02d}-"
    return {p.name for p in (state["prep_work"] / "attempts").iterdir() if re.fullmatch(prefix_name + r"\d{4}", p.name)}


def collect_attempt(state, before):
    new = owned_attempts(state) - before
    if len(new) != 1:
        raise ValueError("guard must identify exactly one new wallpaper attempt")
    attempt = state["prep_work"] / "attempts" / new.pop()
    result = {"attempt": str(attempt), "files": {}}
    for name in ("stage-inputs.json", "launch.json", "vm-result.json", "stage-result.json"):
        path = attempt / name
        if path.exists():
            body = read(path)
            result["files"][name] = {"sha256": sha(body), "bytes": len(body)}
            if name in ("launch.json", "vm-result.json"):
                result[name] = json.loads(body)
    return result


def execute(state):
    prep, work = state["prep"], state["work"]
    unchanged_inputs(state, full=True)
    work.mkdir(mode=0o700)
    lock = os.open(work / "owner.lock", os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        prep.atomic_json(work / "guard-session.json", state["receipt"])
        result = {"schema": 1, "status": "INCOMPLETE", "started_utc": prep.cold.utc(),
                  "guard_session_sha256": prep.digest(state["receipt"]), **NO_BOOT}
        started, before = time.monotonic(), owned_attempts(state)
        try:
            with installed_hooks(state):
                returned = prep.execute(state["plan"], state["runner_args"])
            if len(state["supervision"]) != 1 or state["supervision"][0].get("status") != "GUARDED_SUPERVISION_PASSED":
                raise ValueError("frozen execution did not perform one guarded wallpaper boot")
            unchanged_inputs(state, allow_wallpaper=True, full=True)
            inventory = checkpoint_inventory(prep, state["prep_work"], state["plan"]["session"], STAGE)
            checkpoint_path = state["prep_work"] / "checkpoints" / (STAGE + ".json")
            checkpoint = inventory["rows"][STAGE]
            if returned.get("status") != "PREPARATION_CHECKPOINT" or returned.get("completed") != inventory["completed"]:
                raise ValueError("frozen wallpaper checkpoint did not complete")
            result["output_disk_chain"] = full_disks(prep, state["prep_work"], inventory)
            expected_tc = inventory["prior"]["root26-gpu.tc"]
            output_tc = checkpoint["artifacts"].get("root.tc", {})
            if (set(checkpoint["artifacts"]) != {"root.qcow2", "root.tc"} or
                    (output_tc.get("bytes"), output_tc.get("sha256")) != (expected_tc["bytes"], expected_tc["sha256"])):
                raise ValueError("wallpaper output/trustcache identity differs from the frozen recipe")
            prep.verify_artifact(output_tc, state["prep_work"])
            result["status"] = "GUARDED_WALLPAPER_COMPLETE"
            result["checkpoint"] = {"path": str(checkpoint_path), "sha256": sha(read(checkpoint_path))}
        except BaseException as error:
            result["error"] = type(error).__name__ + ": " + str(error)
        finally:
            with prep.cleanup_signals():
                try:
                    unchanged_inputs(state, allow_wallpaper=True, full=True)
                    result["bound_inputs_unchanged"] = True
                except Exception as error:
                    result["status"] = "INCOMPLETE"
                    result["identity_error"] = type(error).__name__ + ": " + str(error)
                try:
                    result["actual_attempt"] = collect_attempt(state, before)
                    if result["status"] == "GUARDED_WALLPAPER_COMPLETE":
                        checkpoint = json.loads(read(result["checkpoint"]["path"]))
                        if checkpoint.get("attempt") != result["actual_attempt"]["attempt"] or "launch.json" not in result["actual_attempt"]:
                            raise ValueError("wallpaper checkpoint does not belong to its launched attempt")
                except Exception as error:
                    result["status"] = "INCOMPLETE"
                    result["attempt_error"] = type(error).__name__ + ": " + str(error)
                result["original_wallpaper_checkpoint_present"] = (state["prep_work"] / "checkpoints" / (STAGE + ".json")).exists()
                result["checkpoint_accepted_by_guard"] = result["status"] == "GUARDED_WALLPAPER_COMPLETE"
                result["post_stop_blockstats"], result["supervision"] = state["events"], state["supervision"]
                result["finished_utc"], result["elapsed_seconds"] = prep.cold.utc(), time.monotonic() - started
                prep.atomic_json(work / "result.json", result)
        return result
    finally:
        os.close(lock)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apps-audit-work")
    p.add_argument("--work")
    p.add_argument("--execute", action="store_true")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    previous = {}
    try:
        state = preflight(args)
        result = {"schema": 1, "status": "PREFLIGHT_READY", "guard_session": state["receipt"], **NO_BOOT}
        if args.execute:
            def interrupted(number, _):
                raise InterruptedError("signal " + str(number))
            previous = {s: signal.signal(s, interrupted) for s in (signal.SIGINT, signal.SIGTERM)}
            result = execute(state)
    except (Exception, KeyboardInterrupt) as error:
        result = {"schema": 1, "status": "INCOMPLETE", "error": type(error).__name__ + ": " + str(error), **NO_BOOT}
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] in ("PREFLIGHT_READY", "GUARDED_WALLPAPER_COMPLETE") else 2


if __name__ == "__main__":
    raise SystemExit(main())
