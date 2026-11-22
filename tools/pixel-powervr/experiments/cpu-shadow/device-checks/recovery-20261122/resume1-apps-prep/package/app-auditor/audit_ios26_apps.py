#!/usr/bin/env python3
"""Separate read-only apps-copy audit at exactly the completed ios26-apps boundary.

Default is preflight only. Earlier guard/inspection evidence stays bound to its
original prefix; no frozen runner, checkpoint or disk is modified.
"""
import argparse
import contextlib
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import signal
import stat
import struct
import sys
import tarfile
import time
import types


STAGE = "ios26-apps"
SOURCES = ("audit_ios26_apps.py", "audit_ios26_apps_guest.py")
APPROVED = {
    "inspect_ios26_firstboot.py": "2b127ecda390b199287358cdad7e6e7774f5b787148aea524e7b0247a2640cf3",
    "inspect_ios26_firstboot_guest.py": "ada26de8ababb11bb4af20e558708545eb64fd516481359fd5d0ccf6a7cbae2b",
    "guard_ios26_firstboot.py": "ea40638312d6ac41607806ecb03c148fbd0677df6ab01480e13fd40536869674",
    "audit_ios26_partition_guest.py": "6874b9b6b68c7fb50c3f9cf05c1b6a86a53f8fed75863c00a6ad9254b1640593",
}
SCRIPT_SHA256 = {
    "phone/jobs/ios26-apps.sh": "d19d1935d5996b63c5e8ec5916e44c31f3f1b97248a5b3db2022cd0ba6654e18",
    "steps/ios26/apps-get.sh": "52a7280d6bc0c0c29cacf7af87ce484c1ef162782634ea0d6e53dd52553eccc7",
    "steps/ios26/apps-put.sh": "61781e7459fb3ebe2e2f5b1a126e6039d0c2a15495cab08d49c9c09a114c265a",
    "scripts/ios26/apply-apps.sh": "e3c1a995ddbf80a712749d842d9718bdf400012797c68646ee5dc78fd0ccd1a5",
    "scripts/ios26/m2-peek.sh": "71682ff656a361cc942cf6d8c879a5578f69a821549d122584a076574a887837",
    "scripts/ios26/apply-staged.sh": "f921666a408cc57533c80ea96a72f88599484d2c986d5350dbec8eb53d2de92e",
    "scripts/ios26/root26-staged.py": "57bf2f60cf192b9331791562da30a563818b2d5a683c38dc6e118285c42b4886",
    "scripts/ios26/root26-nowatchdog.py": "50aced32d6722a0411be6f4269a3a53a0be228300184e1485573a717148ae8c6",
    "scripts/ios26/root26-aod.py": "d94ece29d7a936bb68d59a2bc4d5b8b248a4b2feec7fc9549bc72e258b270f54",
}
INITRD_SHA256 = "7dff81e88f5e6261ae206c6c481f53748374d76ebd433be7b263f34c571a4a24"
OS_LOGICAL = "os/094-97246-090.dmg"
DISK_BYTES = 51_541_704_704
OUTPUTS = {"apps-audit/result.json", "apps-audit/fsck-activation.txt", "apps-audit/fsck-apps.txt", "apps-audit/apfs-mount.txt"}
NO_BOOT = {"boot_complete": False, "gpu_path_complete": False, "applications_launched": False, "app_gate_changed": False}


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


def approved_module(path):
    path = canonical(path)
    body = read(path)
    if sha(body) != APPROVED[path.name]:
        raise ValueError("unreviewed prerequisite source: " + path.name)
    return module_from(body, path), body


def checkpoint_inventory(prep, work, session):
    expected = list(prep.stages.STAGES[:prep.stages.STAGES.index(STAGE) + 1])
    if {p.name for p in (work / "checkpoints").iterdir()} != {name + ".json" for name in expected}:
        raise ValueError("apps audit requires exactly the completed apps boundary")
    rows, hashes, previous = {}, {}, None
    for stage in expected:
        path = work / "checkpoints" / (stage + ".json")
        body = read(path)
        row = json.loads(body)
        if (row.get("schema") != 1 or row.get("status") != "STAGE_COMPLETE" or row.get("stage") != stage or
                row.get("session_sha256") != prep.digest(session) or row.get("previous_sha256") != previous or
                type(row.get("artifacts")) is not dict):
            raise ValueError("invalid current checkpoint chain")
        for name, record in row["artifacts"].items():
            prep.stages.relative(name)
            prep.stages.relative(record["path"])
        rows[stage] = row
        hashes[str(path)] = previous = sha(body)
    return prefix_inventory({"completed": expected, "rows": rows, "hashes": hashes}, STAGE)


def prefix_inventory(inventory, through):
    names = inventory["completed"][:inventory["completed"].index(through) + 1]
    artifacts, prior = {}, {}
    for stage in names:
        artifacts.update(inventory["rows"][stage]["artifacts"])
        if stage != through:
            prior.update(inventory["rows"][stage]["artifacts"])
    return {"completed": names, "rows": {s: inventory["rows"][s] for s in names},
            "hashes": {p: value for p, value in inventory["hashes"].items() if Path(p).stem in names},
            "artifacts": artifacts, "prior": prior}


def require_native(result):
    cleanup, native = result.get("cleanup", {}), result.get("native_witnesses", {})
    if (result.get("natural_exit") is not True or cleanup.get("exit_code") != 0 or cleanup.get("echild") is not True or
            cleanup.get("errors") != [] or cleanup.get("forced_qemu") is not False or
            cleanup.get("forced_descendants") != [] or native.get("native_initialization") is not True or
            native.get("native_execution") is not True or native.get("fatal_markers") != []):
        raise ValueError("native natural completion and clean owned reaping are mandatory")


def full_inputs(prep, work, inventory):
    """Bind the actual five-member chain, not just recorded backing names."""
    sequence = (("ios26-partition", "root26g.qcow2"), ("ios26-firstboot", "root26g.qcow2"),
                ("ios26-persona", "root26g.qcow2"), ("ios26-activation", "root26-activation.qcow2"),
                (STAGE, "root26-apps.qcow2"))
    records = [inventory["rows"][stage]["artifacts"][name] for stage, name in sequence]
    expected = [record["path"] for record in reversed(records)]
    if len(set(expected)) != len(expected):
        raise ValueError("successive immutable disks must have distinct owned paths")
    for index, record in enumerate(reversed(records)):
        path = prep.contained(work, record["path"])
        actual = [canonical(item["path"]).relative_to(work).as_posix() for item in prep.cold.qcow_chain(path)]
        if actual != expected[index:] or record.get("backing_chain") != actual:
            raise ValueError("actual apps/predecessor backing chain differs from exact checkpoint ancestry")
    source = inventory["rows"]["ios26-decrypt"]["artifacts"][OS_LOGICAL]
    if source != inventory["artifacts"][OS_LOGICAL] or source["path"] in expected:
        raise ValueError("original decoded OS identity was replaced")
    result = []
    for record in records + [source]:
        path = canonical(prep.contained(work, record["path"]))
        identity = prep.cold.readonly_identity(path)
        if path.suffix == ".qcow2":
            with path.open("rb") as stream:
                head = stream.read(32)
            if len(head) != 32 or struct.unpack_from(">Q", head, 24)[0] != DISK_BYTES:
                raise ValueError("partitioned backing member geometry changed")
        actual = prep.file_record(path, work)
        if actual != record or prep.cold.readonly_identity(path) != identity:
            raise ValueError("full input/backing member hash or identity changed")
        result.append({"identity": identity, "record": actual})
    return result


def saved_inspection(inspector, guard, prep, inspection_work, receipt, result, inventory, plan, session):
    """Validate preserved earlier proofs against their own exact prefixes."""
    work = canonical(receipt["prep_work"])
    firstboot = prefix_inventory(inventory, "ios26-firstboot")
    partition = prefix_inventory(inventory, "ios26-partition")
    guard_work = canonical(receipt["guard_work"])
    guard_receipt = json.loads(read(guard_work / "guard-session.json"))
    guard_result = json.loads(read(guard_work / "result.json"))
    observations = json.loads(read(guard_work / "guard-observations.json"))
    guard_files = inspector.guard_acceptance(guard, prep, guard_work, guard_receipt, guard_result,
                                            observations, firstboot, work, session)
    audit = receipt["partition_audit"]
    prior_plan = dict(plan, completed=partition["completed"], artifacts=partition["artifacts"])
    original_audit = guard.audit_identity(prep, canonical(audit["work"]), canonical(audit["source_directory"]),
                                          session, prior_plan, work, canonical(receipt["runner_dir"]))
    if original_audit != audit or guard_receipt.get("partition_audit") != audit:
        raise ValueError("partition audit is not the guard's original predecessor")
    if (receipt.get("schema") != 1 or receipt.get("kind") != "ios26_saved_firstboot_inspection" or
            receipt.get("prep_session_sha256") != sha(read(work / "session.json")) or
            receipt.get("frozen_sources") != session["runner_sources"] or receipt.get("guard_files") != guard_files or
            receipt.get("guard_checkpoint") != guard_result["checkpoint"] or receipt.get("checkpoints") != firstboot["hashes"] or
            receipt.get("runtime") != session["runtime"] or receipt.get("tooling_manifest_sha256") != session["tooling_manifest_sha256"] or
            receipt.get("qualification_sha256") != session["qualification"]["qualification_sha256"] or
            receipt.get("readonly") is not True or receipt.get("mounts_allowed") is not False or
            receipt.get("replay_allowed") is not False or receipt.get("repair_allowed") is not False or
            receipt.get("native_required") is not True or receipt.get("tcg_retry") is not False):
        raise ValueError("saved inspection does not bind the exact earlier firstboot prefix")
    chain = inspector.full_chain(prep, work, firstboot["artifacts"]["root26g.qcow2"], firstboot)
    if chain != receipt.get("backing_chain"):
        raise ValueError("inspected firstboot backing chain changed")
    if (result.get("schema") != 1 or result.get("status") != "SAVED_FIRSTBOOT_INSPECTION_PASSED" or
            result.get("inspection_session_sha256") != prep.digest(receipt) or
            result.get("full_backing_chain_unchanged") is not True or result.get("preparation_and_guard_unchanged") is not True):
        raise ValueError("successful unchanged saved inspection is mandatory")
    require_native(result)
    attempt = canonical(result.get("attempt", ""))
    if attempt != inspection_work / "a1":
        raise ValueError("inspection attempt is outside its owned evidence directory")
    if json.loads(read(attempt / "inspection-result.json")) != result:
        raise ValueError("inspection result copies disagree")
    policy = json.loads(read(attempt / "expected-policy.json"))
    if policy.get("inspection_session_sha256") != prep.digest(receipt):
        raise ValueError("inspection policy belongs to another session")
    launch_path = attempt / "launch.json"
    if result.get("launch") != {"path": str(launch_path), "sha256": sha(read(launch_path))}:
        raise ValueError("inspection launch identity changed")
    vm = json.loads(read(attempt / "vm-result.json"))
    if (not prep.vm_success(vm, True) or vm.get("witnesses") != result["native_witnesses"] or
            vm.get("cleanup") != result["cleanup"] or vm.get("natural_exit") is not True or
            len(vm.get("out_sizes", [])) != 1):
        raise ValueError("inspection native supervision no longer matches receipt")
    auditor_path = canonical(receipt["partition_guest_source"])
    if auditor_path != canonical(Path(audit["source_directory"]) / "audit_ios26_partition_guest.py"):
        raise ValueError("inspection partition dependency path differs from the passed audit")
    auditor, auditor_body = approved_module(auditor_path)
    if (receipt.get("partition_guest_sha256") != sha(auditor_body) or
            audit["source_hashes"].get(auditor_path.name) != sha(auditor_body) or
            policy.get("partition_guest_sha256") != sha(auditor_body)):
        raise ValueError("inspection's passed partition dependency differs")
    names = {"inspection/result.json", "inspection/fsck-system.txt", "inspection/fsck-data.txt"}
    if set(result.get("outputs", {})) != names:
        raise ValueError("saved inspection output inventory incomplete")
    files = {**guard_files, **audit["files"], **audit["checkpoints"]}
    for name, expected in audit["source_hashes"].items():
        path = canonical(Path(audit["source_directory"]) / name)
        if sha(read(path)) != expected:
            raise ValueError("partition auditor source changed")
        files[str(path)] = expected
    for name, record in result["outputs"].items():
        path = prep.verify_artifact(record, inspection_work)
        if path != attempt / "files" / name:
            raise ValueError("inspection output path differs from owned layout")
        files[str(path)] = sha(read(path))
    inspected = inspector.guest_pass({"prep": prep, "auditor": auditor}, attempt / "files/inspection", policy)
    if inspected != result.get("guest_result"):
        raise ValueError("saved inspection raw result differs")
    for path in (inspection_work / "inspection-session.json", inspection_work / "result.json",
                 attempt / "inspection-result.json", attempt / "expected-policy.json", launch_path, attempt / "vm-result.json",
                 auditor_path, canonical(receipt["guard_source"])):
        files[str(path)] = sha(read(path))
    for name, expected in receipt["inspector_sources"].items():
        path = canonical(Path(receipt["source_directory"]) / name)
        if sha(read(path)) != expected or APPROVED.get(name) != expected:
            raise ValueError("inspection source identity changed")
        files[str(path)] = expected
    for original in guard_receipt["frozen_input_identities"].values():
        if prep.cold.readonly_identity(original["path"]) != original:
            raise ValueError("original guarded input identity changed")
    return {"files": files, "inspection_session_sha256": sha(read(inspection_work / "inspection-session.json")),
            "inspection_result_sha256": sha(read(inspection_work / "result.json")),
            "inspection_work": str(inspection_work), "guard_work": str(guard_work),
            "firstboot_checkpoints": firstboot["hashes"], "partition_audit": audit,
            "approved_system_journal": inspected["journals"]["iOSRoot"],
            "frozen_input_identities": guard_receipt["frozen_input_identities"]}


def preflight(args):
    if not args.inspection_work or not args.work:
        raise ValueError("required --inspection-work and --work")
    if not 60 <= args.helper_seconds <= 14400 or not 8 <= args.max_log_mib <= 64 or args.min_free_mib < 1536 or args.min_available_mib < 512:
        raise ValueError("apps audit bounds cannot be weakened or disabled")
    inspection_work, work = canonical(args.inspection_work), canonical(args.work, False)
    if work.exists() or not work.parent.is_dir() or len(str(work)) > 55:
        raise ValueError("fresh audit path must have an existing parent and at most 55 characters")
    inspected = json.loads(read(inspection_work / "inspection-session.json"))
    previous_result = json.loads(read(inspection_work / "result.json"))
    directory = canonical(inspected["source_directory"])
    if inspected.get("inspector_sources") != {n: APPROVED[n] for n in ("inspect_ios26_firstboot.py", "inspect_ios26_firstboot_guest.py")}:
        raise ValueError("saved inspection did not use the approved inspector pair")
    inspector, _ = approved_module(directory / "inspect_ios26_firstboot.py")
    _, firstboot_body = approved_module(directory / "inspect_ios26_firstboot_guest.py")
    guard, _ = approved_module(inspected["guard_source"])
    if inspected.get("guard_source_sha256") != APPROVED["guard_ios26_firstboot.py"]:
        raise ValueError("saved inspection guard source differs")
    prep_work, runner = canonical(inspected["prep_work"]), canonical(inspected["runner_dir"])
    session_body = read(prep_work / "session.json")
    session = json.loads(session_body)
    if (session.get("kind") != "standalone_ios26_preparation" or session.get("native_required") is not True or
            session.get("tcg_retry") is not False or session.get("guest_ram_gib") != 3 or session.get("timebase_hz") != 38_400_000):
        raise ValueError("unsupported preparation/native contract")
    prep = guard.load_frozen(runner, session["runner_sources"])
    parsed, _ = guard.runner_arguments(prep, session, prep_work, runner)
    parsed.through, parsed.execute = STAGE, False
    plan = prep.preflight(parsed)
    inventory = checkpoint_inventory(prep, prep_work, session)
    if (plan["session"] != session or plan["completed"] != inventory["completed"] or plan["remaining"] or
            plan["artifacts"] != inventory["artifacts"] or plan["manifest"]["os"]["ios26"]["vars"]["OS"] != Path(OS_LOGICAL).name):
        raise ValueError("exact current apps boundary was not reproduced")
    tooling = canonical(session["tooling"])
    script_files = {str(tooling / "setup" / name): expected for name, expected in SCRIPT_SHA256.items()}
    if any(sha(read(path)) != expected for path, expected in script_files.items()):
        raise ValueError("apps copy scripts differ from the reviewed authored semantics")
    if prep.cold.sha(tooling / "helper/initrd.gz") != INITRD_SHA256:
        raise ValueError("apps audit requires the reviewed helper utility image")
    prior = saved_inspection(inspector, guard, prep, inspection_work, inspected, previous_result, inventory, plan, session)
    inputs = full_inputs(prep, prep_work, inventory)
    source_dir = canonical(Path(__file__).parent)
    bodies = {name: read(source_dir / name) for name in SOURCES}
    partition_body = read(inspected["partition_guest_source"])
    roots = (prep_work, inspection_work, directory, runner, source_dir, canonical(inspected["guard_source"]).parent,
             canonical(prior["guard_work"]), canonical(prior["partition_audit"]["work"]),
             canonical(prior["partition_audit"]["source_directory"]), tooling, canonical(session["package"]),
             canonical(session["qualification_file"]).parent)
    if any(work.is_relative_to(root) or root.is_relative_to(work) for root in roots):
        raise ValueError("audit output must be outside every preparation/input/source/evidence tree")
    receipt = {"schema": 1, "kind": "ios26_apps_copy_audit", "prep_work": str(prep_work), "runner_dir": str(runner),
        "prep_session_sha256": sha(session_body), "frozen_sources": session["runner_sources"],
        "through": STAGE, "checkpoints": inventory["hashes"], "input_chains": inputs, "prior_evidence": prior,
        "source_directory": str(source_dir), "auditor_sources": {n: sha(b) for n, b in bodies.items()},
        "dependency_sources": {"partition_guest_sha256": sha(partition_body), "firstboot_guest_sha256": sha(firstboot_body)},
        "script_files": script_files, "runtime": session["runtime"],
        "qualification_sha256": session["qualification"]["qualification_sha256"],
        "tooling_manifest_sha256": session["tooling_manifest_sha256"], "helper_initrd_sha256": INITRD_SHA256,
        "readonly_inputs": True, "replay_allowed": False, "repair_allowed": False, "native_required": True, "tcg_retry": False,
        "helper_ram_mib": session["helper_ram_mib"], "helper_vcpus": session["helper_vcpus"],
        "bounds": {"helper_seconds": args.helper_seconds, "max_log_mib": args.max_log_mib,
                   "min_free_mib": args.min_free_mib, "min_available_mib": args.min_available_mib}, **NO_BOOT}
    guest = module_from(bodies[SOURCES[1]], source_dir / SOURCES[1])
    auditor, _ = approved_module(inspected["partition_guest_source"])
    return {"prep": prep, "plan": plan, "inventory": inventory, "prep_work": prep_work, "work": work,
            "receipt": receipt, "bodies": bodies, "partition_body": partition_body, "firstboot_body": firstboot_body,
            "guest": guest, "auditor": auditor,
            "apps": prep.source_path(plan, "root26-apps.qcow2"),
            "activation": prep.source_path(plan, "root26-activation.qcow2"), "os": prep.source_path(plan, OS_LOGICAL)}


def unchanged_inputs(state, full=True):
    prep, receipt = state["prep"], state["receipt"]
    if sha(read(state["prep_work"] / "session.json")) != receipt["prep_session_sha256"]:
        raise ValueError("preparation session changed")
    if {n: sha(read(Path(receipt["runner_dir"]) / n)) for n in receipt["frozen_sources"]} != receipt["frozen_sources"]:
        raise ValueError("frozen runner source changed")
    inventory = checkpoint_inventory(prep, state["prep_work"], state["plan"]["session"])
    if inventory["hashes"] != receipt["checkpoints"]:
        raise ValueError("current apps checkpoint boundary changed")
    for path, expected in {**receipt["prior_evidence"]["files"], **receipt["script_files"]}.items():
        if sha(read(path)) != expected:
            raise ValueError("bound prerequisite evidence/source changed")
    if {n: sha(read(Path(receipt["source_directory"]) / n)) for n in SOURCES} != receipt["auditor_sources"]:
        raise ValueError("apps auditor source changed")
    for original in receipt["prior_evidence"]["frozen_input_identities"].values():
        if prep.cold.readonly_identity(original["path"]) != original:
            raise ValueError("guarded original input changed")
    if full:
        if full_inputs(prep, state["prep_work"], inventory) != receipt["input_chains"]:
            raise ValueError("full input/backing identity changed")
        prep.recheck(state["plan"])
    elif any(prep.cold.readonly_identity(row["identity"]["path"]) != row["identity"] for row in receipt["input_chains"]):
        raise ValueError("input/backing identity changed")


@contextlib.contextmanager
def own_audit(state):
    original = os.open(state["prep_work"] / "owner.lock", os.O_RDONLY | os.O_NOFOLLOW)
    owned = None
    try:
        if not stat.S_ISREG(os.fstat(original).st_mode):
            raise ValueError("original owner lock is not regular")
        try:
            fcntl.flock(original, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("preparation is still owned by a running process") from None
        state["prep"].refuse_live_children(state["prep_work"])
        unchanged_inputs(state, True)
        state["work"].mkdir(mode=0o700)
        owned = os.open(state["work"] / "owner.lock", os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        fcntl.flock(owned, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state["prep"].atomic_json(state["work"] / "apps-audit-session.json", state["receipt"])
        yield
    finally:
        if owned is not None:
            os.close(owned)
        os.close(original)


def input_tar(state, attempt, policy):
    files = {".job/run": b"run.sh\n", ".job/disks": b"d0 apps.qcow2\nd1 activation.qcow2\nd2 original.dmg\n",
             ".job/out": b"apps-audit\n", ".job/scratch": b"",
             "apps_guest.py": state["bodies"][SOURCES[1]], "partition_guest.py": state["partition_body"],
             "firstboot_guest.py": state["firstboot_body"], "policy.json": state["guest"].json_bytes(policy),
             "run.sh": b"#!/bin/bash\nset -euo pipefail\npython3 -I apps_guest.py /work/apps.qcow2 /work/activation.qcow2 /work/original.dmg /work/policy.json /work/partition_guest.py /work/firstboot_guest.py /work/apps-audit\n"}
    target = attempt / "in.tar"
    with target.open("xb") as stream, tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name, body in sorted(files.items()):
            entry = tarfile.TarInfo(name)
            entry.mode, entry.size = (0o755 if name.endswith(".sh") else 0o644), len(body)
            archive.addfile(entry, io.BytesIO(body))
    return target


def guest_pass(state, directory, policy):
    result = json.loads(read(directory / "result.json"))
    if (result.get("schema") != 1 or result.get("kind") != "ios26_apps_copy_audit" or
            result.get("status") != "APP_COPY_AUDIT_PASSED" or result.get("errors") != [] or result.get("cleanup_errors") != [] or
            result.get("readonly_inputs") is not True or result.get("raw_metadata_unchanged") is not True or
            result.get("replayed") is not False or result.get("repaired") is not False or
            result.get("audit_nonce") != policy["audit_nonce"] or result.get("policy_sha256") != state["prep"].digest(policy) or
            set(result.get("readonly_mounts", {})) != {"os", "activation", "apps"} or
            set(result.get("systems", {})) != {"os", "activation", "apps"} or
            set(result.get("gpt", {})) != {"activation", "apps"} or
            result["gpt"]["activation"] != result["gpt"]["apps"] or
            result["gpt"]["apps"].get("status") != "PASSED" or result["gpt"]["apps"].get("disk_bytes") != DISK_BYTES):
        raise ValueError("apps guest audit is incomplete or belongs to another attempt")
    comparison = result.get("comparison", {})
    if (comparison.get("status") != "PASSED" or comparison.get("errors") != [] or
            comparison.get("source_bundles", 0) <= 0 or comparison.get("checked_files", 0) <= 0 or
            comparison.get("unexplained_entries_allowed") is not False or comparison.get("global_nlink_compared") is not False or
            not re.fullmatch(r"[0-9a-f]{64}", comparison.get("comparison_sha256", ""))):
        raise ValueError("full application copy comparison is missing")
    systems = list(result["systems"].values())
    if any(row.get("status") != "PASSED" or (row.get("build"), row.get("version")) != ("23G90", "26.6.2") for row in systems) or len({(r.get("path"), r.get("bytes"), r.get("sha256")) for r in systems}) != 1:
        raise ValueError("original OS version plist identity was not preserved")
    if any(not re.fullmatch(r"[0-9a-f]{64}", r.get("sha256", "")) or r.get("bytes", 0) <= 0 for r in systems):
        raise ValueError("original OS version plist digest is missing")
    for name, row in result["readonly_mounts"].items():
        if (row.get("root") != "/" or not {"ro", "nosuid", "nodev", "noexec"} <= set(row.get("options", [])) or
                (name != "os" and row.get("type") != "hfsplus") or
                (name == "os" and (row.get("type") not in ("fuse", "fuse.apfs-fuse") or row.get("source") != "apfs-fuse"))):
            raise ValueError("read-only mount witness missing")
    if set(result.get("fsck", {})) != {"activation", "apps"} or set(result.get("journals", {})) != {"activation", "apps"}:
        raise ValueError("missing raw journal/filesystem gates")
    for name in ("activation", "apps"):
        journal = result["journals"][name]
        if journal.get("status") != "PASSED" or journal.get("journal", {}).get("status") != "PASSED" or journal["journal"].get("state") not in (
                "INITIALIZED_EMPTY", "AUTHORED_UNINITIALIZED_JOURNAL_PRESERVED"):
            raise ValueError("raw system journal classification incomplete")
        approved = policy["approved_system_journal"]
        if (journal.get("journal_info") != approved["journal_info"] or
                journal.get("volume", {}).get("geometry") != approved["volume"]["geometry"] or
                (journal["journal"]["state"] == "INITIALIZED_EMPTY" and journal["journal"] != approved["journal"]) or
                (journal["journal"]["state"] == "AUTHORED_UNINITIALIZED_JOURNAL_PRESERVED" and
                 (approved["journal"].get("state") != "UNTOUCHED_AUTHORED_NEEDINIT" or
                  journal["journal"].get("journal_sha256") != approved["journal"].get("journal_sha256")))):
            raise ValueError("journal witness differs from the saved-inspection predecessor")
        text = read(directory / ("fsck-" + name + ".txt")).decode("utf-8", "strict")
        verdict = state["auditor"].fsck_verdict(result["fsck"][name].get("exit_code"), text)
        if verdict["status"] != "PASSED" or verdict != result["fsck"][name]:
            raise ValueError("unfiltered filesystem log differs from clean forced read-only check")
    if not read(directory / "apfs-mount.txt").startswith(state["guest"].APFS_LOG_HEADER):
        raise ValueError("APFS diagnostic record is missing")
    return result


def execute(state, args):
    prep, cold, work = state["prep"], state["prep"].cold, state["work"]
    cold.require_phone(state["plan"]["session"])
    cold.subreaper()
    with own_audit(state):
        attempt = work / "a1"
        attempt.mkdir(mode=0o700)
        (attempt / "files").mkdir(mode=0o700)
        result = {"schema": 1, "status": "INCOMPLETE", "attempt": str(attempt), "started_utc": cold.utc(),
                  "apps_audit_session_sha256": prep.digest(state["receipt"]), **NO_BOOT}
        started = time.monotonic()
        try:
            policy = {"schema": 1, "audit_nonce": os.urandom(16).hex(),
                      "apps_audit_session_sha256": result["apps_audit_session_sha256"],
                      **state["receipt"]["dependency_sources"],
                      "os_bytes": state["inventory"]["artifacts"][OS_LOGICAL]["bytes"],
                      "approved_system_journal": state["receipt"]["prior_evidence"]["approved_system_journal"]}
            prep.atomic_json(attempt / "expected-policy.json", policy)
            tar = input_tar(state, attempt, policy)
            raw = attempt / "out.raw"
            with raw.open("xb") as stream:
                stream.truncate(32 << 20)
            disks = [{"path": tar, "format": "raw", "readonly": True, "serial": "in"},
                     {"path": raw, "format": "raw", "readonly": False, "serial": "out"},
                     {"path": state["apps"], "format": "qcow2", "readonly": True, "serial": "d0"},
                     {"path": state["activation"], "format": "qcow2", "readonly": True, "serial": "d1"},
                     {"path": state["os"], "format": "raw", "readonly": True, "serial": "d2"}]
            argv, env = prep.helper_command(state["plan"], attempt, disks)
            observed = prep.supervise_vm(state["plan"], "apps-copy-audit", attempt, argv, env, args)
            result.update(native_witnesses=observed.get("witnesses"), cleanup=observed.get("cleanup"),
                          natural_exit=observed.get("natural_exit"))
            require_native(result)
            if not prep.vm_success(observed, True) or len(observed.get("out_sizes", [])) != 1:
                raise ValueError("apps helper lacks unique output or natural native completion")
            regular = prep.safe_return_tar(raw, observed["out_sizes"][0], attempt / "files", ["apps-audit"])
            if not regular <= OUTPUTS or "apps-audit/result.json" not in regular:
                raise ValueError("unexpected apps-audit output inventory")
            result["outputs"] = {name: prep.file_record(attempt / "files" / name, work) for name in sorted(regular)}
            result["guest_result"] = json.loads(read(attempt / "files/apps-audit/result.json"))
            guest_pass(state, attempt / "files/apps-audit", policy)
            if regular != OUTPUTS:
                raise ValueError("missing complete filesystem/APFS diagnostics")
            result["status"] = "APP_COPY_AUDIT_PASSED"
        except BaseException as error:
            result["error"] = type(error).__name__ + ": " + str(error)
        finally:
            with prep.cleanup_signals():
                try:
                    unchanged_inputs(state, True)
                    result["full_input_chains_unchanged"] = True
                    result["preparation_and_prior_evidence_unchanged"] = True
                except Exception as error:
                    result["status"] = "INCOMPLETE"
                    result["identity_error"] = type(error).__name__ + ": " + str(error)
                if (attempt / "launch.json").exists():
                    result["launch"] = {"path": str(attempt / "launch.json"), "sha256": sha(read(attempt / "launch.json"))}
                result["finished_utc"], result["elapsed_seconds"] = cold.utc(), time.monotonic() - started
                prep.atomic_json(attempt / "apps-audit-result.json", result)
                prep.atomic_json(work / "result.json", result)
        return result


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inspection-work")
    p.add_argument("--work")
    p.add_argument("--execute", action="store_true")
    p.add_argument("--audit-seconds", dest="helper_seconds", type=int, default=7200)
    p.add_argument("--max-log-mib", type=int, default=64)
    p.add_argument("--min-free-mib", type=int, default=1536)
    p.add_argument("--min-available-mib", type=int, default=512)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    previous = {}
    try:
        state = preflight(args)
        result = {"schema": 1, "status": "PREFLIGHT_READY", "apps_audit_session": state["receipt"], **NO_BOOT}
        if args.execute:
            def interrupted(number, _):
                raise InterruptedError("signal " + str(number))
            previous = {s: signal.signal(s, interrupted) for s in (signal.SIGINT, signal.SIGTERM)}
            result = execute(state, args)
    except (Exception, KeyboardInterrupt) as error:
        result = {"schema": 1, "status": "INCOMPLETE", "error": type(error).__name__ + ": " + str(error), **NO_BOOT}
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] in ("PREFLIGHT_READY", "APP_COPY_AUDIT_PASSED") else 2


if __name__ == "__main__":
    raise SystemExit(main())
