#!/usr/bin/env python3
"""Explicit firstboot guard around the hash-bound frozen preparation runner.

Default: read-only preflight. --execute delegates only ios26-firstboot, adding
post-stop failed guest-I/O counter checks and a mandatory shell-sync witness.
No frozen file/session is edited and only the frozen owner writes checkpoints.
Zero counters do not expose QMP stop's internal bdrv_flush_all return value.
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
import sys
import time
import types


FROZEN = ("cold_boot_dt.py", "cold_boot_ios26.py", "prepare_ios26_stages.py", "prepare_ios26.py")
AUDITOR = ("audit_ios26_partition.py", "audit_ios26_partition_guest.py")
STAGE = "ios26-firstboot"
NO_BOOT = {"boot_complete": False, "gpu_path_complete": False, "app_gate_changed": False}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(path, exists=True):
    path = Path(path).absolute()
    if path != path.resolve(strict=exists) or any(c in str(path) for c in ",\r\n\x00"):
        raise ValueError("noncanonical or unsupported path")
    return path


def read(path, limit=4 << 20):
    path = canonical(path)
    if not stat.S_ISREG(path.lstat().st_mode) or path.stat().st_size > limit:
        raise ValueError("nonregular or oversized metadata/source file")
    return path.read_bytes()


def load_frozen(directory, expected):
    if set(expected) != set(FROZEN):
        raise ValueError("session must bind exactly the four frozen sources")
    bodies = {name: read(directory / name) for name in FROZEN}
    if {name: sha(body) for name, body in bodies.items()} != expected:
        raise ValueError("frozen source hash mismatch")
    previous, modules = {}, {}
    try:
        for name in FROZEN:
            module_name = name[:-3]
            previous[module_name] = sys.modules.get(module_name)
            module = types.ModuleType(module_name)
            module.__file__ = str(directory / name)
            sys.modules[module_name] = module
            exec(compile(bodies[name], module.__file__, "exec"), module.__dict__)
            modules[name] = module
    finally:
        for name, value in previous.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value
    return modules["prepare_ios26.py"]


def require_boundary(prep, plan):
    prefix = list(prep.stages.STAGES[:prep.stages.STAGES.index(STAGE)])
    if plan["completed"] != prefix or plan["remaining"] != [STAGE] or plan["through"] != STAGE:
        raise ValueError("guard requires exactly the partition boundary and one new firstboot")
    if plan["network_stages"] or plan["guest_boot_stages"] != [STAGE] or plan["helper_smoke"]:
        raise ValueError("guard cannot execute helpers, network work, or other boots")


def failed_io_counters(stats):
    """Strict BlockStats shape, including every parent/backing entry returned."""
    if type(stats) is not list or len(stats) != 1 or type(stats[0]) is not dict or stats[0].get("device") != "root":
        raise ValueError("post-stop stats must identify exactly the root backend")
    nodes, seen = [], set()

    def walk(row, location, depth=0):
        if type(row) is not dict or depth > 32 or len(nodes) >= 128 or id(row) in seen:
            raise ValueError("malformed or excessive block-statistics graph")
        seen.add(id(row))
        counters = row.get("stats")
        if type(counters) is not dict:
            raise ValueError("block statistics are missing the stats object")
        selected = {}
        for name in ("failed_wr_operations", "failed_flush_operations"):
            value = counters.get(name)
            if type(value) is not int or value < 0:
                raise ValueError("missing or malformed failed-I/O counter: " + name)
            if value != 0:
                raise ValueError("recorded failed guest I/O: " + name)
            selected[name] = value
        nodes.append({"location": location, "device": row.get("device"), "node_name": row.get("node-name"), **selected})
        for name in ("parent", "backing"):
            if name in row:
                walk(row[name], location + "." + name, depth + 1)
    walk(stats[0], "root")
    return {"failed_io_counters_zero": True, "nodes_checked": len(nodes), "nodes": nodes,
            "stop_internal_flush_return_observed": False}


def runner_arguments(prep, session, work, runner):
    argv = ["--package", session["package"], "--qualification", session["qualification_file"],
            "--tooling", session["tooling"], "--tooling-sha256", session["tooling_manifest_sha256"],
            "--work", str(work), "--timezone", session["locale"]["timezone"],
            "--region", session["locale"]["region"], "--clock", str(session["locale"]["clock"]),
            "--helper-ram-mib", str(session["helper_ram_mib"]), "--helper-vcpus", str(session["helper_vcpus"]),
            "--through", STAGE, "--execute", "--allow-guest-boots"]
    return prep.parser().parse_args(argv), [sys.executable, "-B", str(runner / "prepare_ios26.py"), *argv]


def audit_identity(prep, audit_work, auditor_dir, session, plan, prep_work, runner_dir):
    session_path, result_path = audit_work / "audit-session.json", audit_work / "result.json"
    audit_bytes, result_bytes = read(session_path), read(result_path)
    audited, result = json.loads(audit_bytes), json.loads(result_bytes)
    if (audited.get("schema") != 1 or audited.get("kind") != "standalone_ios26_partition_audit" or
            audited.get("readonly") is not True or audited.get("native_required") is not True or audited.get("tcg_retry") is not False or
            audited.get("prep_work") != str(prep_work) or audited.get("runner_dir") != str(runner_dir) or
            audited.get("prep_session_sha256") != sha(read(prep_work / "session.json")) or
            audited.get("frozen_runner_sources") != session["runner_sources"] or
            audited.get("runtime") != session["runtime"] or
            audited.get("qualification_sha256") != session["qualification"]["qualification_sha256"] or
            audited.get("tooling_manifest_sha256") != session["tooling_manifest_sha256"]):
        raise ValueError("partition audit does not bind this exact preparation session")
    actual_sources = {name: sha(read(auditor_dir / name)) for name in AUDITOR}
    if audited.get("auditor_sources") != actual_sources:
        raise ValueError("actual auditor source hashes do not match the passed audit")
    if (result.get("schema") != 1 or result.get("status") != "PARTITION_AUDIT_PASSED" or
            result.get("session_sha256") != prep.digest(audited) or result.get("disk_unchanged") is not True or
            result.get("preparation_records_unchanged") is not True or result.get("natural_exit") is not True):
        raise ValueError("a completed unchanged-disk partition audit is mandatory")
    cleanup, native = result.get("cleanup", {}), result.get("native_witnesses", {})
    if (cleanup.get("exit_code") != 0 or cleanup.get("echild") is not True or cleanup.get("errors") != [] or
            cleanup.get("forced_qemu") or cleanup.get("forced_descendants") or
            native.get("native_initialization") is not True or native.get("native_execution") is not True or native.get("fatal_markers") != []):
        raise ValueError("partition audit lacks clean native execution/reaping")
    artifacts = result.get("outputs", {})
    names = {"audit/result.json", "audit/fsck-system.txt", "audit/fsck-data.txt"}
    if set(artifacts) != names:
        raise ValueError("partition audit output inventory is incomplete")
    files = {str(session_path): sha(audit_bytes), str(result_path): sha(result_bytes)}
    paths = {}
    for name, record in artifacts.items():
        path = prep.verify_artifact(record, audit_work)
        paths[name] = path
        files[str(path)] = record["sha256"]
    guest = json.loads(read(paths["audit/result.json"]))
    if (guest != result.get("guest_result") or guest.get("status") != "PARTITION_AUDIT_PASSED" or
            guest.get("readonly_attachment") is not True or guest.get("errors") != [] or guest.get("cleanup_errors") != [] or
            guest.get("data_copy", {}).get("status") != "PASSED" or guest["data_copy"].get("errors") != [] or
            set(guest.get("fsck", {})) != {"iOSRoot", "Data"} or
            any(row.get("status") != "PASSED" or row.get("exit_code") != 0 for row in guest["fsck"].values())):
        raise ValueError("partition audit raw result does not match its successful receipt")
    for volume, name in (("iOSRoot", "audit/fsck-system.txt"), ("Data", "audit/fsck-data.txt")):
        # Match the auditor's strict UTF-8 text hash, including full diagnostics.
        text = paths[name].read_text(encoding="utf-8", errors="strict")
        if sha(text.encode()) != guest["fsck"][volume].get("diagnostic_sha256"):
            raise ValueError("partition filesystem log hash mismatch")
    checkpoints = {str(prep_work / "checkpoints" / (s + ".json")):
                   sha(read(prep_work / "checkpoints" / (s + ".json"))) for s in plan["completed"]}
    if audited.get("checkpoints") != checkpoints or audited.get("disk") != plan["artifacts"].get("root26g.qcow2"):
        raise ValueError("partition audit checkpoint/disk identity differs from current boundary")
    disk = prep.source_path(plan, "root26g.qcow2")
    if prep.cold.readonly_identity(disk) != audited.get("disk_identity"):
        raise ValueError("partition disk changed after its audit")
    return {"work": str(audit_work), "source_directory": str(auditor_dir), "source_hashes": actual_sources,
            "files": files, "checkpoints": checkpoints, "disk": audited["disk"],
            "audit_session_sha256": sha(audit_bytes), "audit_result_sha256": sha(result_bytes)}


def preflight(args):
    for name in ("audit_work", "auditor_dir", "runner_dir", "work"):
        if not getattr(args, name):
            raise ValueError("required --" + name.replace("_", "-"))
    audit_work, auditor_dir, runner_dir = (canonical(getattr(args, n)) for n in ("audit_work", "auditor_dir", "runner_dir"))
    work = canonical(args.work, False)
    if work.exists() or not work.parent.is_dir():
        raise ValueError("guard evidence directory must be fresh with an existing parent")
    audited = json.loads(read(audit_work / "audit-session.json"))
    prep_work = canonical(audited["prep_work"])
    session_bytes = read(prep_work / "session.json")
    session = json.loads(session_bytes)
    if (session.get("kind") != "standalone_ios26_preparation" or session.get("native_required") is not True or
            session.get("tcg_retry") is not False or session.get("guest_ram_gib") != 3 or session.get("timebase_hz") != 38_400_000):
        raise ValueError("unsupported preparation/native/memory contract")
    prep = load_frozen(runner_dir, session["runner_sources"])
    parsed, equivalent_argv = runner_arguments(prep, session, prep_work, runner_dir)
    plan = prep.preflight(parsed)  # Exact package, every checkpoint/artifact and existing session configuration.
    require_boundary(prep, plan)
    if plan["session"] != session:
        raise ValueError("frozen session configuration was not reproduced exactly")
    audit = audit_identity(prep, audit_work, auditor_dir, session, plan, prep_work, runner_dir)
    source = canonical(__file__)
    for root in (prep_work, audit_work, auditor_dir, runner_dir, source.parent,
                 canonical(session["package"]), canonical(session["tooling"]), canonical(session["qualification_file"]).parent):
        if work.is_relative_to(root) or root.is_relative_to(work):
            raise ValueError("guard output must be outside immutable inputs and preparation/evidence roots")
    identities = {name: prep.cold.readonly_identity(prep.source_path(plan, name)) for name in plan["artifacts"]}
    receipt = {"schema": 1, "kind": "ios26_firstboot_execution_guard", "guard_source": str(source),
        "guard_source_sha256": sha(read(source)), "prep_work": str(prep_work), "runner_dir": str(runner_dir),
        "prep_session_sha256": sha(session_bytes), "frozen_sources": session["runner_sources"],
        "frozen_input_identities": identities, "partition_audit": audit, "equivalent_frozen_runner_argv": equivalent_argv,
        "execution_method": "in-process frozen prepare.execute with two explicit guard hooks",
        "hooks": ["Qmp.call(stop): original stop then strict post-stop blockstats",
                  "supervise_vm(ios26-firstboot): delegate then require shell sync and unchanged bound inputs"],
        "counter_scope": "recorded failed guest writes/flushes; stop-internal flush return is not observed",
        "mandatory_next_gate": "separate saved-filesystem/journal check before any Linux disk mutation",
        **NO_BOOT}
    return {"prep": prep, "plan": plan, "runner_args": parsed, "work": work, "receipt": receipt,
            "events": [], "supervision": [], "prep_work": prep_work, "source": source,
            "status": "PREFLIGHT_READY"}


def unchanged_inputs(state, allow_firstboot=False):
    prep, receipt = state["prep"], state["receipt"]
    if sha(read(state["source"])) != receipt["guard_source_sha256"]:
        raise ValueError("guard source changed")
    if sha(read(state["prep_work"] / "session.json")) != receipt["prep_session_sha256"]:
        raise ValueError("preparation session changed")
    runner = Path(receipt["runner_dir"])
    if {name: sha(read(runner / name)) for name in FROZEN} != receipt["frozen_sources"]:
        raise ValueError("frozen runner source changed")
    audit = receipt["partition_audit"]
    if {name: sha(read(Path(audit["source_directory"]) / name)) for name in AUDITOR} != audit["source_hashes"]:
        raise ValueError("auditor source changed")
    for path, expected in {**audit["files"], **audit["checkpoints"]}.items():
        if sha(read(path)) != expected:
            raise ValueError("bound audit/preparation record changed")
    names = {p.name for p in (state["prep_work"] / "checkpoints").iterdir()}
    expected = {Path(p).name for p in audit["checkpoints"]}
    if names != expected and not (allow_firstboot and names == expected | {STAGE + ".json"}):
        raise ValueError("preparation boundary changed unexpectedly")
    for original in receipt["frozen_input_identities"].values():
        if prep.cold.readonly_identity(original["path"]) != original:
            raise ValueError("frozen preparation input changed")
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
            result = original_call(qmp, name, seconds)
            event["stop_acknowledged"] = True
            unchanged_inputs(state)
            stats = original_call(qmp, "query-blockstats", 5)
            event["post_stop_blockstats"] = stats
            event["counter_check"] = failed_io_counters(stats)
            unchanged_inputs(state)
            event.update(status="COUNTERS_CHECKED", failed_io_counters_zero=True)
            return result
        except BaseException as error:
            event["error"] = type(error).__name__ + ": " + str(error)
            raise
        finally:
            event["finished_utc"] = prep.cold.utc()
            # A receipt-write failure also raises into original stop cleanup.
            observations(state)

    def guarded_supervise(plan, stage, attempt, argv, env, args, frame=None):
        if stage != STAGE or frame is None:
            raise ValueError("firstboot guard cannot supervise another stage")
        event = {"stage": stage, "attempt": str(attempt), "status": "INCOMPLETE", "started_utc": prep.cold.utc()}
        state["supervision"].append(event)
        try:
            unchanged_inputs(state)
            result = original_supervise(plan, stage, attempt, argv, env, args, frame)
            event["original_supervision_status"] = result.get("status")
            event["guest_sync_answered"] = result.get("guest_sync_answered") is True
            if result.get("guest_sync_answered") is not True:
                raise ValueError("firstboot did not return the mandatory shell __SYNCED__ witness")
            if len(state["events"]) != 1 or state["events"][0].get("failed_io_counters_zero") is not True:
                raise ValueError("firstboot lacks its unique verified post-stop counter check")
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


def owned_attempt(state):
    prefix = f"{state['prep'].stages.STAGES.index(STAGE):02d}-"
    return {p.name for p in (state["prep_work"] / "attempts").iterdir() if re.fullmatch(prefix + r"\d{4}", p.name)}


def collect_attempt(state, before):
    new = owned_attempt(state) - before
    if len(new) != 1:
        raise ValueError("guard must identify exactly one new firstboot attempt")
    attempt = state["prep_work"] / "attempts" / new.pop()
    output = {"attempt": str(attempt), "files": {}}
    for name in ("stage-inputs.json", "launch.json", "vm-result.json", "stage-result.json"):
        path = attempt / name
        if path.exists():
            body = read(path)
            output["files"][name] = {"sha256": sha(body), "bytes": len(body)}
            if name in ("launch.json", "vm-result.json"):
                output[name] = json.loads(body)
    return output


def execute(state):
    prep, work = state["prep"], state["work"]
    unchanged_inputs(state)
    work.mkdir(mode=0o700)
    lock = os.open(work / "owner.lock", os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        prep.atomic_json(work / "guard-session.json", state["receipt"])
        result = {"schema": 1, "status": "INCOMPLETE", "started_utc": prep.cold.utc(),
                  "guard_session_sha256": prep.digest(state["receipt"]), **NO_BOOT}
        started, before = time.monotonic(), owned_attempt(state)
        try:
            with installed_hooks(state):
                returned = prep.execute(state["plan"], state["runner_args"])
            if len(state["supervision"]) != 1 or state["supervision"][0].get("status") != "GUARDED_SUPERVISION_PASSED":
                raise ValueError("frozen execution did not perform one guarded firstboot")
            unchanged_inputs(state, True)
            checkpoint_path = state["prep_work"] / "checkpoints" / (STAGE + ".json")
            checkpoint = json.loads(read(checkpoint_path))
            expected_completed = list(prep.stages.STAGES[:prep.stages.STAGES.index(STAGE) + 1])
            if (returned.get("status") != "PREPARATION_CHECKPOINT" or returned.get("completed") != expected_completed or
                    checkpoint.get("status") != "STAGE_COMPLETE" or checkpoint.get("stage") != STAGE or
                    checkpoint.get("session_sha256") != prep.digest(state["plan"]["session"])):
                raise ValueError("frozen firstboot checkpoint did not complete")
            result["status"] = "GUARDED_FIRSTBOOT_COMPLETE"
            result["checkpoint"] = {"path": str(checkpoint_path), "sha256": sha(read(checkpoint_path))}
        except BaseException as error:
            result["error"] = type(error).__name__ + ": " + str(error)
        finally:
            with prep.cleanup_signals():
                try:
                    unchanged_inputs(state, True)
                    result["bound_inputs_unchanged"] = True
                except Exception as error:
                    result["status"] = "INCOMPLETE"
                    result["identity_error"] = type(error).__name__ + ": " + str(error)
                try:
                    result["actual_attempt"] = collect_attempt(state, before)
                    if result["status"] == "GUARDED_FIRSTBOOT_COMPLETE":
                        checkpoint = json.loads(read(result["checkpoint"]["path"]))
                        if checkpoint.get("attempt") != result["actual_attempt"]["attempt"] or "launch.json" not in result["actual_attempt"]:
                            raise ValueError("guard checkpoint does not belong to its actual launched attempt")
                except Exception as error:
                    result["status"] = "INCOMPLETE"
                    result["attempt_error"] = type(error).__name__ + ": " + str(error)
                checkpoint_exists = (state["prep_work"] / "checkpoints" / (STAGE + ".json")).exists()
                result["original_firstboot_checkpoint_present"] = checkpoint_exists
                result["checkpoint_accepted_by_guard"] = result["status"] == "GUARDED_FIRSTBOOT_COMPLETE"
                result["post_stop_blockstats"] = state["events"]
                result["supervision"] = state["supervision"]
                result["finished_utc"] = prep.cold.utc()
                result["elapsed_seconds"] = time.monotonic() - started
                prep.atomic_json(work / "result.json", result)
        return result
    finally:
        os.close(lock)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("audit-work", "auditor-dir", "runner-dir", "work"):
        p.add_argument("--" + name)
    p.add_argument("--execute", action="store_true", help="run the audited firstboot under both additional guards")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    old_handlers = {}
    try:
        state = preflight(args)
        result = {"schema": 1, "status": "PREFLIGHT_READY", "guard_session": state["receipt"], **NO_BOOT}
        if args.execute:
            def interrupted(number, _):
                raise InterruptedError("signal " + str(number))
            old_handlers = {s: signal.signal(s, interrupted) for s in (signal.SIGINT, signal.SIGTERM)}
            result = execute(state)
    except (Exception, KeyboardInterrupt) as error:
        result = {"schema": 1, "status": "INCOMPLETE", "error": type(error).__name__ + ": " + str(error), **NO_BOOT}
    finally:
        for number, handler in old_handlers.items():
            signal.signal(number, handler)
    print(json.dumps(result, indent=2))
    return 2 if result["status"] == "INCOMPLETE" else 0


if __name__ == "__main__":
    raise SystemExit(main())
