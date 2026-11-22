#!/usr/bin/env python3
"""Separate read-only saved-firstboot inspection; default is preflight only.

This does not resume or alter preparation. An exact successful firstboot guard
receipt and its still-current checkpoint are mandatory. Only the fresh owned
inspection directory receives writes; the original owner lock is nonwriting.
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


STAGE = "ios26-firstboot"
SOURCES = ("inspect_ios26_firstboot.py", "inspect_ios26_firstboot_guest.py")
GUARD_SHA256 = "ea40638312d6ac41607806ecb03c148fbd0677df6ab01480e13fd40536869674"
DISK_BYTES = 51_541_704_704
NO_BOOT = {"boot_complete": False, "gpu_path_complete": False, "app_gate_changed": False}


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
        raise ValueError("nonregular or oversized metadata/source file")
    return path.read_bytes()


def module_from(body, path):
    module = types.ModuleType("bound_" + Path(path).stem)
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def checkpoint_inventory(prep, work, session):
    expected = list(prep.stages.STAGES[:prep.stages.STAGES.index(STAGE) + 1])
    if {p.name for p in (work / "checkpoints").iterdir()} != {name + ".json" for name in expected}:
        raise ValueError("inspection requires exactly the completed firstboot boundary")
    hashes, rows, artifacts, prior, previous = {}, {}, {}, {}, None
    for stage in expected:
        path = work / "checkpoints" / (stage + ".json")
        body = read(path)
        row = json.loads(body)
        if (row.get("schema") != 1 or row.get("status") != "STAGE_COMPLETE" or row.get("stage") != stage or
                row.get("session_sha256") != prep.digest(session) or row.get("previous_sha256") != previous or
                type(row.get("artifacts")) is not dict):
            raise ValueError("invalid current checkpoint chain")
        hashes[str(path)] = previous = sha(body)
        rows[stage] = row
        for name, record in row["artifacts"].items():
            prep.stages.relative(name)
            prep.stages.relative(record["path"])
            artifacts[name] = record
        if stage != STAGE:
            prior.update(row["artifacts"])
    return {"completed": expected, "hashes": hashes, "rows": rows, "artifacts": artifacts, "prior": prior}


def guard_acceptance(guard, prep, guard_work, receipt, result, observations, inventory, work, session):
    """Do not adopt an original checkpoint whose guard failed after writing it."""
    checkpoint_path = work / "checkpoints" / (STAGE + ".json")
    checkpoint = inventory["rows"][STAGE]
    if (receipt.get("schema") != 1 or receipt.get("kind") != "ios26_firstboot_execution_guard" or
            receipt.get("guard_source_sha256") != GUARD_SHA256 or receipt.get("prep_work") != str(work) or
            receipt.get("prep_session_sha256") != sha(read(work / "session.json")) or
            receipt.get("frozen_sources") != session["runner_sources"] or
            result.get("schema") != 1 or result.get("status") != "GUARDED_FIRSTBOOT_COMPLETE" or
            result.get("guard_session_sha256") != prep.digest(receipt) or
            result.get("checkpoint_accepted_by_guard") is not True or
            result.get("original_firstboot_checkpoint_present") is not True or
            result.get("bound_inputs_unchanged") is not True or
            result.get("checkpoint") != {"path": str(checkpoint_path), "sha256": inventory["hashes"][str(checkpoint_path)]}):
        raise ValueError("exact successful guard receipt/current checkpoint required")
    events, supervision = result.get("post_stop_blockstats"), result.get("supervision")
    if (type(events) is not list or len(events) != 1 or type(supervision) is not list or len(supervision) != 1 or
            observations != {"schema": 1, "post_stop_blockstats": events, "supervision": supervision}):
        raise ValueError("guard observations missing or inconsistent")
    event, observed = events[0], supervision[0]
    counters = guard.failed_io_counters(event.get("post_stop_blockstats"), event.get("post_stop_blocks"))
    if (event.get("status") != "COUNTERS_CHECKED" or event.get("stop_acknowledged") is not True or
            event.get("failed_io_counters_zero") is not True or event.get("counter_check") != counters or
            event.get("stop_internal_flush_return_observed") is not False or
            observed.get("stage") != STAGE or observed.get("status") != "GUARDED_SUPERVISION_PASSED" or
            observed.get("original_supervision_status") != "VM_OBSERVATION_COMPLETE" or
            observed.get("guest_sync_answered") is not True):
        raise ValueError("guard counter/shell-sync witness incomplete")
    actual = result.get("actual_attempt", {})
    attempt = canonical(actual.get("attempt", ""))
    if (attempt.parent != work / "attempts" or not re.fullmatch(r"07-\d{4}", attempt.name) or
            str(attempt) != checkpoint.get("attempt") or str(attempt) != observed.get("attempt")):
        raise ValueError("guard attempt is not the checkpoint's firstboot attempt")
    expected = {"stage-inputs.json", "launch.json", "vm-result.json", "stage-result.json"}
    if set(actual.get("files", {})) != expected:
        raise ValueError("guard attempt metadata inventory incomplete")
    files, decoded = {}, {}
    for name in sorted(expected):
        body = read(attempt / name)
        if actual["files"][name] != {"sha256": sha(body), "bytes": len(body)}:
            raise ValueError("guard attempt metadata changed")
        files[str(attempt / name)] = sha(body)
        decoded[name] = json.loads(body)
    launch, vm = decoded["launch.json"], decoded["vm-result.json"]
    if (launch != actual.get("launch.json") or vm != actual.get("vm-result.json") or
            decoded["stage-result.json"] != checkpoint or
            decoded["stage-inputs.json"] != {"stage": STAGE, "session_sha256": prep.digest(session),
                                             "inputs": receipt.get("frozen_input_identities")} or
            vm.get("stage") != STAGE or vm.get("status") != "VM_OBSERVATION_COMPLETE" or
            vm.get("guest_sync_answered") is not True or not prep.vm_success(vm, False)):
        raise ValueError("guard launch/native/cleanup metadata does not match its original attempt")
    trace = [row for row in vm.get("qmp", []) if row.get("request", {}).get("execute") in ("stop", "query-blockstats", "query-block", "quit")]
    if ([row.get("request", {}).get("execute") for row in trace] != ["stop", "query-blockstats", "query-block", "quit"] or
            any("error" in row.get("response", {}) or "return" not in row.get("response", {}) for row in trace) or
            trace[1]["response"]["return"] != event["post_stop_blockstats"] or
            trace[2]["response"]["return"] != event["post_stop_blocks"]):
        raise ValueError("actual QMP trace lacks the exact ordered guarded counter check")
    devices = [launch["command"][i + 1] for i, arg in enumerate(launch.get("command", [])[:-1]) if arg == "-device"]
    if [d for d in devices if "drive=root" in d] != ["virtio-blk-pci,drive=root"]:
        raise ValueError("unreviewed guest block-sector configuration")
    files.update({str(guard_work / name): sha(read(guard_work / name))
                  for name in ("guard-session.json", "result.json", "guard-observations.json")})
    return files


def full_chain(prep, work, record, inventory):
    """Hash every member against the original full artifact records."""
    known = {}
    for checkpoint in inventory["rows"].values():
        for item in checkpoint["artifacts"].values():
            if item["path"] in known and known[item["path"]] != item:
                raise ValueError("conflicting artifact identity for a disk path")
            known[item["path"]] = item
    path = prep.contained(work, record["path"])
    chain = prep.cold.qcow_chain(path)
    relative = [Path(item["path"]).relative_to(work).as_posix() for item in chain]
    partition = inventory["prior"]["root26g.qcow2"]
    if relative != record.get("backing_chain") or relative != [record["path"], partition["path"]]:
        raise ValueError("firstboot disk must have exactly its audited partition predecessor")
    identities = []
    for item in chain:
        actual = canonical(item["path"])
        name = actual.relative_to(work).as_posix()
        if name not in known:
            raise ValueError("unrecorded backing-chain member")
        before = prep.cold.readonly_identity(actual)
        pinned = prep.file_record(actual, work)
        with actual.open("rb") as stream:
            head = stream.read(32)
        if len(head) != 32 or struct.unpack_from(">Q", head, 24)[0] != DISK_BYTES:
            raise ValueError("backing-chain virtual geometry differs from the audited disk")
        if pinned != known[name] or prep.cold.readonly_identity(actual) != before:
            raise ValueError("full backing-chain hash/identity mismatch")
        identities.append({"identity": before, "record": pinned})
    return identities


def preflight(args):
    if not args.guard_work or not args.work:
        raise ValueError("required --guard-work and --work")
    if not 1 <= args.helper_seconds <= 14400 or not 8 <= args.max_log_mib <= 64 or args.min_free_mib < 1536 or args.min_available_mib < 512:
        raise ValueError("inspection bounds cannot be disabled or weakened")
    guard_work, work = canonical(args.guard_work), canonical(args.work, False)
    if work.exists() or not work.parent.is_dir() or len(str(work)) > 55:
        raise ValueError("fresh inspection path must be at most 55 characters with an existing parent")
    receipt = json.loads(read(guard_work / "guard-session.json"))
    result = json.loads(read(guard_work / "result.json"))
    observations = json.loads(read(guard_work / "guard-observations.json"))
    guard_source = canonical(receipt["guard_source"])
    guard_body = read(guard_source)
    if sha(guard_body) != GUARD_SHA256 or receipt.get("guard_source_sha256") != GUARD_SHA256:
        raise ValueError("guard source is not the approved immutable revision")
    guard = module_from(guard_body, guard_source)
    prep_work, runner = canonical(receipt["prep_work"]), canonical(receipt["runner_dir"])
    session_body = read(prep_work / "session.json")
    session = json.loads(session_body)
    if (session.get("kind") != "standalone_ios26_preparation" or session.get("native_required") is not True or
            session.get("tcg_retry") is not False or session.get("guest_ram_gib") != 3 or session.get("timebase_hz") != 38_400_000):
        raise ValueError("unsupported preparation/native contract")
    prep = guard.load_frozen(runner, session["runner_sources"])
    parsed, _ = guard.runner_arguments(prep, session, prep_work, runner)
    plan = prep.preflight(parsed)  # Full original artifact/package/tooling verification; no execution.
    inventory = checkpoint_inventory(prep, prep_work, session)
    if plan["session"] != session or plan["completed"] != inventory["completed"] or plan["remaining"] or plan["artifacts"] != inventory["artifacts"]:
        raise ValueError("current complete firstboot boundary was not reproduced exactly")
    bound = guard_acceptance(guard, prep, guard_work, receipt, result, observations, inventory, prep_work, session)
    previous_plan = dict(plan, completed=inventory["completed"][:-1], artifacts=inventory["prior"])
    audit = receipt["partition_audit"]
    # Revalidate exactly the earlier prefix; the audit never acquires credit
    # for firstboot's output merely because its receipt remains on disk.
    audited = guard.audit_identity(prep, canonical(audit["work"]), canonical(audit["source_directory"]),
                                   session, previous_plan, prep_work, runner)
    if audited != audit:
        raise ValueError("partition audit identity changed from the successful guard")
    guard_state = {"prep": prep, "receipt": receipt, "source": guard_source, "prep_work": prep_work, "plan": plan}
    guard.unchanged_inputs(guard_state, True)
    source_dir = canonical(Path(__file__).parent)
    bodies = {name: read(source_dir / name) for name in SOURCES}
    dependency = canonical(Path(audit["source_directory"]) / "audit_ios26_partition_guest.py")
    dependency_body = read(dependency)
    if sha(dependency_body) != audit["source_hashes"][dependency.name]:
        raise ValueError("passed partition guest dependency changed")
    guest = module_from(bodies[SOURCES[1]], source_dir / SOURCES[1])
    auditor = module_from(dependency_body, dependency)
    disk = prep.contained(prep_work, plan["artifacts"]["root26g.qcow2"]["path"])
    baseline = prep.contained(prep_work, inventory["prior"]["root26g.qcow2"]["path"])
    chain = full_chain(prep, prep_work, plan["artifacts"]["root26g.qcow2"], inventory)
    roots = (prep_work, guard_work, runner, guard_source.parent, source_dir, canonical(audit["work"]),
             canonical(audit["source_directory"]), canonical(session["tooling"]), canonical(session["package"]),
             canonical(session["qualification_file"]).parent)
    if any(work.is_relative_to(root) or root.is_relative_to(work) for root in roots):
        raise ValueError("inspection directory must be outside every input/evidence/source tree")
    inspection = {"schema": 1, "kind": "ios26_saved_firstboot_inspection", "prep_work": str(prep_work),
        "runner_dir": str(runner), "prep_session_sha256": sha(session_body), "frozen_sources": session["runner_sources"],
        "guard_work": str(guard_work), "guard_source": str(guard_source), "guard_source_sha256": GUARD_SHA256,
        "guard_files": bound, "guard_checkpoint": result["checkpoint"], "partition_audit": audit,
        "checkpoints": inventory["hashes"], "backing_chain": chain,
        "source_directory": str(source_dir), "inspector_sources": {name: sha(body) for name, body in bodies.items()},
        "partition_guest_source": str(dependency), "partition_guest_sha256": sha(dependency_body),
        "runtime": session["runtime"], "qualification_sha256": session["qualification"]["qualification_sha256"],
        "tooling_manifest_sha256": session["tooling_manifest_sha256"],
        "readonly": True, "mounts_allowed": False, "replay_allowed": False, "repair_allowed": False,
        "native_required": True, "tcg_retry": False,
        "helper_ram_mib": session["helper_ram_mib"], "helper_vcpus": session["helper_vcpus"],
        "bounds": {"helper_seconds": args.helper_seconds, "max_log_mib": args.max_log_mib,
                   "min_free_mib": args.min_free_mib, "min_available_mib": args.min_available_mib}, **NO_BOOT}
    return {"prep": prep, "guard": guard, "guard_state": guard_state, "plan": plan, "inventory": inventory,
            "work": work, "prep_work": prep_work, "disk": disk, "baseline": baseline, "bodies": bodies,
            "dependency_body": dependency_body, "guest": guest, "auditor": auditor, "receipt": inspection}


def unchanged_inputs(state, full=True):
    prep, receipt = state["prep"], state["receipt"]
    state["guard"].unchanged_inputs(state["guard_state"], True)
    inventory = checkpoint_inventory(prep, state["prep_work"], state["plan"]["session"])
    if inventory["hashes"] != receipt["checkpoints"]:
        raise ValueError("current preparation boundary changed")
    for path, expected in receipt["guard_files"].items():
        if sha(read(path)) != expected:
            raise ValueError("successful guard/attempt evidence changed")
    if {name: sha(read(Path(receipt["source_directory"]) / name)) for name in SOURCES} != receipt["inspector_sources"]:
        raise ValueError("inspector source changed")
    if sha(read(receipt["partition_guest_source"])) != receipt["partition_guest_sha256"]:
        raise ValueError("partition guest dependency changed")
    if full:
        actual = full_chain(prep, state["prep_work"], inventory["artifacts"]["root26g.qcow2"], inventory)
        if actual != receipt["backing_chain"]:
            raise ValueError("full saved/backing disk identity changed")
    elif any(prep.cold.readonly_identity(item["identity"]["path"]) != item["identity"] for item in receipt["backing_chain"]):
        raise ValueError("saved/backing disk identity changed")


@contextlib.contextmanager
def own_inspection(state):
    original = os.open(state["prep_work"] / "owner.lock", os.O_RDONLY | os.O_NOFOLLOW)
    owned = None
    try:
        if not stat.S_ISREG(os.fstat(original).st_mode):
            raise ValueError("original preparation lock is not regular")
        try:
            fcntl.flock(original, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("preparation is still owned by a running process") from None
        state["prep"].refuse_live_children(state["prep_work"])
        unchanged_inputs(state, True)
        state["work"].mkdir(mode=0o700)
        owned = os.open(state["work"] / "owner.lock", os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        fcntl.flock(owned, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state["prep"].atomic_json(state["work"] / "inspection-session.json", state["receipt"])
        yield
    finally:
        if owned is not None:
            os.close(owned)
        os.close(original)


def input_tar(state, attempt, policy):
    files = {".job/run": b"run.sh\n", ".job/disks": b"d0 saved.qcow2\nd1 predecessor.qcow2\n",
             ".job/out": b"inspection\n", ".job/scratch": b"",
             "inspection_guest.py": state["bodies"][SOURCES[1]],
             "partition_guest.py": state["dependency_body"], "policy.json": state["guest"].json_bytes(policy),
             "run.sh": b"#!/bin/bash\nset -euo pipefail\npython3 -I inspection_guest.py /work/saved.qcow2 /work/predecessor.qcow2 /work/policy.json /work/partition_guest.py /work/inspection\n"}
    target = attempt / "in.tar"
    with target.open("xb") as stream, tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name, body in sorted(files.items()):
            entry = tarfile.TarInfo(name)
            entry.mode, entry.size = (0o755 if name.endswith(".sh") else 0o644), len(body)
            archive.addfile(entry, io.BytesIO(body))
    return target


def guest_pass(state, directory, policy):
    result = json.loads(read(directory / "result.json"))
    if (result.get("schema") != 1 or result.get("kind") != "ios26_saved_firstboot_inspection" or
            result.get("status") != "SAVED_FIRSTBOOT_INSPECTION_PASSED" or result.get("errors") != [] or
            result.get("cleanup_errors") != [] or result.get("readonly_attachments") is not True or
            result.get("raw_metadata_unchanged") is not True or result.get("mounted") is not False or
            result.get("replayed") is not False or result.get("repaired") is not False or
            result.get("inspection_nonce") != policy["inspection_nonce"] or
            result.get("policy_sha256") != state["prep"].digest(policy) or
            result.get("gpt", {}).get("status") != "PASSED" or result["gpt"].get("disk_bytes") != DISK_BYTES or
            result.get("baseline_gpt") != result["gpt"] or set(result.get("journals", {})) != {"iOSRoot", "Data"} or
            set(result.get("fsck", {})) != {"iOSRoot", "Data"}):
        raise ValueError("guest inspection incomplete; retained metadata classifies the boundary")
    for name, filename in (("iOSRoot", "fsck-system.txt"), ("Data", "fsck-data.txt")):
        row = result["journals"][name]
        if row.get("status") != "PASSED" or row.get("journal", {}).get("status") != "PASSED" or row["journal"].get("state") not in (
                "INITIALIZED_EMPTY", "UNTOUCHED_AUTHORED_NEEDINIT"):
            raise ValueError("raw journal classification incomplete")
        raw = read(directory / filename).decode("utf-8", "strict")
        verdict = state["auditor"].fsck_verdict(result["fsck"][name].get("exit_code"), raw)
        if verdict["status"] != "PASSED" or verdict != result["fsck"][name]:
            raise ValueError("filesystem log is not a matching complete forced read-only clean check")
    return result


def execute(state, args):
    prep, cold, work = state["prep"], state["prep"].cold, state["work"]
    cold.require_phone(state["plan"]["session"])
    cold.subreaper()
    with own_inspection(state):
        attempt = work / "a1"
        attempt.mkdir(mode=0o700)
        (attempt / "files").mkdir(mode=0o700)
        result = {"schema": 1, "status": "INCOMPLETE", "attempt": str(attempt), "started_utc": cold.utc(),
                  "inspection_session_sha256": prep.digest(state["receipt"]), **NO_BOOT}
        started = time.monotonic()
        try:
            policy = {"schema": 1, "inspection_nonce": os.urandom(16).hex(),
                      "inspection_session_sha256": result["inspection_session_sha256"],
                      "partition_guest_sha256": state["receipt"]["partition_guest_sha256"]}
            prep.atomic_json(attempt / "expected-policy.json", policy)
            tar = input_tar(state, attempt, policy)
            raw = attempt / "out.raw"
            with raw.open("xb") as stream:
                stream.truncate(16 << 20)
            disks = [{"path": tar, "format": "raw", "readonly": True, "serial": "in"},
                     {"path": raw, "format": "raw", "readonly": False, "serial": "out"},
                     {"path": state["disk"], "format": "qcow2", "readonly": True, "serial": "d0"},
                     {"path": state["baseline"], "format": "qcow2", "readonly": True, "serial": "d1"}]
            argv, env = prep.helper_command(state["plan"], attempt, disks)
            observed = prep.supervise_vm(state["plan"], "saved-firstboot-inspection", attempt, argv, env, args)
            result.update(native_witnesses=observed.get("witnesses"), cleanup=observed.get("cleanup"),
                          natural_exit=observed.get("natural_exit"))
            if not prep.vm_success(observed, True) or len(observed.get("out_sizes", [])) != 1:
                raise ValueError("inspection helper lacks unique output or natural native completion")
            regular = prep.safe_return_tar(raw, observed["out_sizes"][0], attempt / "files", ["inspection"])
            allowed = {"inspection/result.json", "inspection/fsck-system.txt", "inspection/fsck-data.txt"}
            if not regular <= allowed or "inspection/result.json" not in regular:
                raise ValueError("unexpected inspection output inventory")
            result["outputs"] = {n: prep.file_record(attempt / "files" / n, work) for n in sorted(regular)}
            result["guest_result"] = json.loads(read(attempt / "files/inspection/result.json"))
            guest_pass(state, attempt / "files/inspection", policy)
            if regular != allowed:
                raise ValueError("missing complete filesystem diagnostics")
            result["status"] = "SAVED_FIRSTBOOT_INSPECTION_PASSED"
        except BaseException as error:
            result["error"] = type(error).__name__ + ": " + str(error)
        finally:
            with prep.cleanup_signals():
                try:
                    unchanged_inputs(state, True)
                    result["full_backing_chain_unchanged"] = True
                    result["preparation_and_guard_unchanged"] = True
                except Exception as error:
                    result["status"] = "INCOMPLETE"
                    result["identity_error"] = type(error).__name__ + ": " + str(error)
                if (attempt / "launch.json").exists():
                    result["launch"] = {"path": str(attempt / "launch.json"), "sha256": sha(read(attempt / "launch.json"))}
                result["finished_utc"] = cold.utc()
                result["elapsed_seconds"] = time.monotonic() - started
                prep.atomic_json(attempt / "inspection-result.json", result)
                prep.atomic_json(work / "result.json", result)
        return result


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--guard-work")
    p.add_argument("--work")
    p.add_argument("--execute", action="store_true")
    p.add_argument("--inspection-seconds", dest="helper_seconds", type=int, default=7200)
    p.add_argument("--max-log-mib", type=int, default=64)
    p.add_argument("--min-free-mib", type=int, default=1536)
    p.add_argument("--min-available-mib", type=int, default=512)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    previous = {}
    try:
        state = preflight(args)
        result = {"schema": 1, "status": "PREFLIGHT_READY", "inspection_session": state["receipt"], **NO_BOOT}
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
    return 0 if result["status"] in ("PREFLIGHT_READY", "SAVED_FIRSTBOOT_INSPECTION_PASSED") else 2


if __name__ == "__main__":
    raise SystemExit(main())
