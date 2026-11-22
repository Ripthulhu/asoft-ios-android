#!/usr/bin/env python3
"""Separate read-only audit of a completed, still-unbooted ios26-partition.

Default: verify inputs and print a plan, without writes, processes, or network.
--execute uses the preparation session's exact frozen native helper supervisor.
The preparation session, its four runner sources and its disk stay unchanged.
"""
import argparse
import ast
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


SOURCES = ("cold_boot_dt.py", "cold_boot_ios26.py", "prepare_ios26_stages.py", "prepare_ios26.py")
AUDIT_SOURCES = ("audit_ios26_partition.py", "audit_ios26_partition_guest.py")
REVIEWED_SCRIPTS = {
    "setup/scripts/ios26/root26-prefs.py": "85ee109d54f99fa1f589d5f8c7e1bedbf55ab9eaaa7c10fdddffef39fee0f086",
    "setup/scripts/ios26/root26-trim.py": "5c4ae4758eb7708dbd4a4a5d413c574b724cddc4302210e3e20b15fc0e40e88b",
    "setup/scripts/ios26/mk-root26g.sh": "e756308f9d03513016925bd9aa919640518d0ac19b050df8b2853a014b391166",
    "setup/steps/ios26/tweaks.sh": "38fac994621a0a945d0db5fede0d086c092e63ee4719a9f72e25df1b04ad05fb",
}
NO_BOOT = {"boot_complete": False, "gpu_path_complete": False, "app_gate_changed": False}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(path, exists=True):
    path = Path(path).absolute()
    if path != path.resolve(strict=exists) or any(c in str(path) for c in ",\r\n\x00"):
        raise ValueError("path must be canonical, without symlinks or QEMU separators")
    return path


def source_bytes(path):
    path = canonical(path)
    if not stat.S_ISREG(path.lstat().st_mode) or path.stat().st_size > 2 << 20:
        raise ValueError("missing or oversized authored source")
    return path.read_bytes()


def frozen_runner(directory, expected):
    directory = canonical(directory)
    if set(expected) != set(SOURCES):
        raise ValueError("preparation did not bind exactly the four frozen sources")
    bodies = {name: source_bytes(directory / name) for name in SOURCES}
    if {name: sha(data) for name, data in bodies.items()} != expected:
        raise ValueError("frozen runner source differs from preparation session")
    # Compile the exact bytes already hashed, with no pycache or stale imports.
    modules, previous = {}, {}
    try:
        for name in SOURCES:
            module_name = name[:-3]
            previous[module_name] = sys.modules.get(module_name)
            module = types.ModuleType(module_name)
            module.__file__ = str(directory / name)
            sys.modules[module_name] = module
            exec(compile(bodies[name], module.__file__, "exec"), module.__dict__)
            modules[name] = module
    finally:
        for name, old in previous.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old
    return modules["prepare_ios26.py"]


def guest_module(body, path):
    module = types.ModuleType("partition_audit_guest_verified")
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def checkpoint_boundary(prep, work, session):
    """Check record identities; only the audited disk needs an asset rehash."""
    completed, records, previous, partition = [], {}, None, None
    checkpoint_dir = canonical(work / "checkpoints")
    expected = list(prep.stages.STAGES[:prep.stages.STAGES.index("ios26-partition") + 1])
    if set(p.name for p in checkpoint_dir.iterdir()) != {stage + ".json" for stage in expected}:
        raise ValueError("audit requires the completed partition boundary, before any later setup stage")
    for stage in expected:
        path = canonical(checkpoint_dir / (stage + ".json"))
        data = source_bytes(path)
        record = json.loads(data)
        if (record.get("schema") != 1 or record.get("stage") != stage or record.get("status") != "STAGE_COMPLETE" or
                record.get("session_sha256") != prep.digest(session) or record.get("previous_sha256") != previous or
                not isinstance(record.get("artifacts"), dict)):
            raise ValueError("invalid preparation checkpoint chain")
        records[str(path)] = sha(data)
        previous = sha(data)
        completed.append(stage)
        if stage == "ios26-partition":
            partition = record
    if set(partition["artifacts"]) != {"root26g.qcow2"}:
        raise ValueError("unexpected partition output inventory")
    disk_record = partition["artifacts"]["root26g.qcow2"]
    disk = prep.contained(work, disk_record["path"])
    return disk, disk_record, records


def policy_from_tools(tooling):
    for relative, expected in REVIEWED_SCRIPTS.items():
        if sha(source_bytes(tooling / relative)) != expected:
            raise ValueError("authored disk/tweak script differs from reviewed audit policy")
    syntax = ast.parse(source_bytes(tooling / "setup/scripts/ios26/root26-trim.py"))
    assignments = [n for n in syntax.body if isinstance(n, ast.Assign) and
                   any(isinstance(t, ast.Name) and t.id == "LABELS" for t in n.targets)]
    if len(assignments) != 1:
        raise ValueError("trim label literal is ambiguous")
    labels = ast.literal_eval(assignments[0].value)
    if (type(labels) is not list or not labels or len(labels) != len(set(labels)) or
            not all(type(s) is str and re.fullmatch(r"[A-Za-z0-9_.-]+", s) for s in labels)):
        raise ValueError("invalid authored trim labels")
    return {"schema": 1, "trim_labels": labels, "reviewed_sources": REVIEWED_SCRIPTS}


def readonly_disk(prep, path, record, work, disk_bytes):
    actual = prep.file_record(path, work)
    if actual != record or actual.get("backing_chain") != [actual["path"]]:
        raise ValueError("partition disk identity changed or has an unexpected backing file")
    with path.open("rb") as stream:
        header = stream.read(104)
    if len(header) < 104 or struct.unpack_from(">Q", header, 24)[0] != disk_bytes:
        raise ValueError("partition qcow2 virtual size differs from exact geometry")
    return prep.cold.readonly_identity(path)


def preflight(args):
    for name in ("prep_work", "runner_dir", "work"):
        if not getattr(args, name):
            raise ValueError("required argument --" + name.replace("_", "-"))
    prep_work, runner_dir = canonical(args.prep_work), canonical(args.runner_dir)
    work = canonical(args.work, False)
    if len(str(work)) > 55 or not work.parent.is_dir() or work.exists():
        raise ValueError("audit needs a fresh short work path (at most 55 characters) with an existing parent")
    stored = canonical(prep_work / "session.json")
    session_bytes = source_bytes(stored)
    session = json.loads(session_bytes)
    if (session.get("schema") != 1 or session.get("kind") != "standalone_ios26_preparation" or
            session.get("native_required") is not True or session.get("tcg_retry") is not False or
            session.get("timebase_hz") != 38_400_000):
        raise ValueError("unsupported preparation session/native execution contract")
    prep = frozen_runner(runner_dir, session["runner_sources"])
    plan = {"session": session, "work": str(prep_work)}
    prep.recheck(plan)
    if prep.same_runtime(Path(session["package"])) != session["runtime"]:
        raise ValueError("qualification fixture and QEMU runtime provenance changed")
    tooling = canonical(session["tooling"])
    for root in (prep_work, runner_dir, tooling, canonical(session["package"]), canonical(session["qualification_file"]).parent):
        if work.is_relative_to(root) or root.is_relative_to(work):
            raise ValueError("audit output must be outside preparation, source, tooling and qualification trees")
    manifest_path = tooling / prep.TOOL_ENTRIES["setup_manifest"]
    if prep.cold.sha(manifest_path) != session["setup_manifest_sha256"]:
        raise ValueError("setup manifest differs from preparation session")
    plan["manifest"] = json.loads(manifest_path.read_text())
    source_dir = canonical(Path(__file__).parent)
    bodies = {name: source_bytes(source_dir / name) for name in AUDIT_SOURCES}
    guest = guest_module(bodies[AUDIT_SOURCES[1]], source_dir / AUDIT_SOURCES[1])
    disk, record, checkpoints = checkpoint_boundary(prep, prep_work, session)
    identity = readonly_disk(prep, disk, record, prep_work, guest.DISK_BYTES)
    policy = policy_from_tools(tooling)
    audit_session = {"schema": 1, "kind": "standalone_ios26_partition_audit", "prep_work": str(prep_work),
        "runner_dir": str(runner_dir), "prep_session_sha256": sha(session_bytes), "checkpoints": checkpoints,
        "frozen_runner_sources": session["runner_sources"], "auditor_sources": {n: sha(b) for n, b in bodies.items()},
        "qualification_sha256": session["qualification"]["qualification_sha256"], "runtime": session["runtime"],
        "tooling_manifest_sha256": session["tooling_manifest_sha256"], "disk": record, "disk_identity": identity,
        "policy_sha256": prep.digest(policy), "readonly": True, "native_required": True, "tcg_retry": False}
    public = {"schema": 1, "status": "PREFLIGHT_READY", "work": str(work), "session": audit_session,
              "execution_verified": False, **NO_BOOT,
              "notes": ["No process or file is created without --execute.",
                        "Only the partition output is rehashed; predecessor identities are bound by the checkpoint chain.",
                        "Both unmounted HFS+ volumes must pass forced read-only fsck before separate read-only mounts.",
                        "All unchanged files are checksummed; only exact validated authored changes are allowed.",
                        "Unexplained HFS internal entries fail closed for separate review.",
                        "This audit does not complete iOS boot, native GPU or application qualification."]}
    return {"public": public, "prep": prep, "guest": guest, "plan": plan, "policy": policy,
            "disk": disk, "bodies": bodies, "prep_work": prep_work, "work": work, "source_dir": source_dir}


def unchanged_inputs(state, full_disk=True):
    prep, public = state["prep"], state["public"]["session"]
    if prep.cold.sha(state["prep_work"] / "session.json") != public["prep_session_sha256"]:
        raise ValueError("preparation session changed during audit")
    disk, record, checkpoints = checkpoint_boundary(prep, state["prep_work"], state["plan"]["session"])
    if checkpoints != public["checkpoints"] or disk != state["disk"] or record != public["disk"]:
        raise ValueError("preparation checkpoint changed during audit")
    if full_disk:
        identity = readonly_disk(prep, disk, record, state["prep_work"], state["guest"].DISK_BYTES)
    else:
        identity = prep.cold.readonly_identity(disk)
    if identity != public["disk_identity"]:
        raise ValueError("partition disk changed during audit")
    prep.recheck(state["plan"])
    if {n: sha(source_bytes(state["source_dir"] / n)) for n in AUDIT_SOURCES} != public["auditor_sources"]:
        raise ValueError("auditor source changed during audit")


@contextlib.contextmanager
def own_audit(state):
    # The only original-session operation is a nonwriting lock acquisition.
    prep_lock = os.open(state["prep_work"] / "owner.lock", os.O_RDONLY | os.O_NOFOLLOW)
    audit_lock = None
    try:
        if not stat.S_ISREG(os.fstat(prep_lock).st_mode):
            raise ValueError("preparation owner lock is not a regular file")
        try:
            fcntl.flock(prep_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("preparation is still owned by another running process") from None
        state["prep"].refuse_live_children(state["prep_work"])
        unchanged_inputs(state, False)
        state["work"].mkdir(mode=0o700)
        audit_lock = os.open(state["work"] / "owner.lock", os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        fcntl.flock(audit_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state["prep"].atomic_json(state["work"] / "audit-session.json", state["public"]["session"])
        yield
    finally:
        if audit_lock is not None:
            os.close(audit_lock)
        os.close(prep_lock)


def input_tar(state, attempt, policy):
    files = {".job/run": b"run.sh\n", ".job/disks": b"d0 audit-disk.qcow2\n", ".job/out": b"audit\n",
             ".job/scratch": b"", "audit_guest.py": state["bodies"][AUDIT_SOURCES[1]],
             "audit-policy.json": json.dumps(policy, sort_keys=True).encode(),
             "run.sh": b"#!/bin/bash\nset -euo pipefail\npython3 -I audit_guest.py /work/audit-disk.qcow2 /work/audit-policy.json /work/audit\n"}
    target = attempt / "in.tar"
    with target.open("xb") as output, tarfile.open(fileobj=output, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name, data in sorted(files.items()):
            entry = tarfile.TarInfo(name)
            entry.mode, entry.size = (0o755 if name.endswith(".sh") else 0o644), len(data)
            archive.addfile(entry, io.BytesIO(data))
    return target


def guest_pass(guest, directory, policy):
    result = json.loads((directory / "result.json").read_text())
    if (result.get("schema") != 1 or result.get("kind") != "ios26_readonly_partition_audit" or
            result.get("status") != "PARTITION_AUDIT_PASSED" or result.get("readonly_attachment") is not True or
            result.get("audit_nonce") != policy["audit_nonce"] or
            result.get("policy_sha256") != guest.digest(guest.json_bytes(policy)) or
            result.get("errors") != [] or result.get("cleanup_errors") != [] or
            result.get("gpt", {}).get("status") != "PASSED" or result["gpt"].get("disk_bytes") != guest.DISK_BYTES or
            result.get("system", {}).get("status") != "PASSED" or
            (result["system"].get("build"), result["system"].get("version")) != ("23G90", "26.6.2") or
            result.get("data_copy", {}).get("status") != "PASSED" or result["data_copy"].get("errors") != [] or
            result["data_copy"].get("checked_unchanged_files", 0) <= 0):
        raise ValueError("guest audit is incomplete; retained result contains metadata findings")
    if set(result.get("fsck", {})) != {"iOSRoot", "Data"}:
        raise ValueError("missing filesystem-check verdict")
    journal = result["data_copy"].get("journal_metadata", {})
    if (not isinstance(journal, dict) or journal.get("status") != "PASSED" or
            journal.get("state") != "authored_uninitialized_need_init" or journal.get("jib_flags") != 5 or
            journal.get("initialized_journals_allowed") is not False or
            set(journal.get("files", {})) != {".journal", ".journal_info_block"}):
        raise ValueError("missing exact pre-firstboot journal classification")
    catalog = journal.get("catalog", {})
    if (not isinstance(catalog, dict) or catalog.get("status") != "PASSED" or
            catalog.get("node_bytes") != 8192 or catalog.get("extent_overflow_allowed") is not False or
            set(catalog.get("records", {})) != {".journal", ".journal_info_block"}):
        raise ValueError("missing exact journal catalog-fork classification")
    for name, filename in (("iOSRoot", "fsck-system.txt"), ("Data", "fsck-data.txt")):
        raw = (directory / filename).read_text(encoding="utf-8", errors="strict")
        verdict = guest.fsck_verdict(result["fsck"][name].get("exit_code"), raw)
        if verdict["status"] != "PASSED" or verdict != result["fsck"][name]:
            raise ValueError("unfiltered filesystem log does not match a full clean check")
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
                  "session_sha256": prep.digest(state["public"]["session"]), **NO_BOOT}
        started = time.monotonic()
        try:
            policy = dict(state["policy"], audit_nonce=os.urandom(16).hex(), audit_session_sha256=result["session_sha256"])
            prep.atomic_json(attempt / "expected-policy.json", policy)
            tar = input_tar(state, attempt, policy)
            raw = attempt / "out.raw"
            with raw.open("xb") as stream:
                stream.truncate(16 << 20)
            disks = [{"path": tar, "format": "raw", "readonly": True, "serial": "in"},
                     {"path": raw, "format": "raw", "readonly": False, "serial": "out"},
                     {"path": state["disk"], "format": "qcow2", "readonly": True, "serial": "d0"}]
            argv, env = prep.helper_command(state["plan"], attempt, disks)
            observed = prep.supervise_vm(state["plan"], "partition-audit", attempt, argv, env, args)
            if not prep.vm_success(observed, True) or len(observed.get("out_sizes", [])) != 1:
                raise ValueError("audit helper lacks unique output or natural native completion")
            regular = prep.safe_return_tar(raw, observed["out_sizes"][0], attempt / "files", ["audit"])
            expected = {"audit/result.json", "audit/fsck-system.txt", "audit/fsck-data.txt"}
            if not regular <= expected or "audit/result.json" not in regular:
                raise ValueError("unexpected audit output files")
            result["guest_result"] = guest_pass(state["guest"], attempt / "files/audit", policy)
            if regular != expected:
                raise ValueError("audit output is missing a complete filesystem log")
            result["outputs"] = {n: prep.file_record(attempt / "files" / n, work) for n in sorted(regular)}
            result["native_witnesses"] = observed["witnesses"]
            result["cleanup"] = observed["cleanup"]
            result["natural_exit"] = observed["natural_exit"]
            result["status"] = "PARTITION_AUDIT_PASSED"
        except BaseException as error:
            result["error"] = type(error).__name__ + ": " + str(error)
        finally:
            with prep.cleanup_signals():
                try:
                    unchanged_inputs(state, True)
                    result["disk_unchanged"] = True
                    result["preparation_records_unchanged"] = True
                except Exception as error:
                    result["status"] = "INCOMPLETE"
                    result["identity_error"] = type(error).__name__ + ": " + str(error)
                result["finished_utc"] = cold.utc()
                result["elapsed_seconds"] = time.monotonic() - started
                prep.atomic_json(attempt / "audit-result.json", result)
                prep.atomic_json(work / "result.json", result)
        return result


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("prep-work", "runner-dir", "work"):
        p.add_argument("--" + name)
    p.add_argument("--execute", action="store_true")
    p.add_argument("--audit-seconds", dest="helper_seconds", type=int, default=7200)
    p.add_argument("--max-log-mib", type=int, default=64)
    p.add_argument("--min-free-mib", type=int, default=1536)
    p.add_argument("--min-available-mib", type=int, default=512)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    old_handlers = {}
    try:
        if not 60 <= args.helper_seconds <= 14400 or not 8 <= args.max_log_mib <= 128 or args.min_free_mib < 512 or args.min_available_mib < 256:
            raise ValueError("invalid bounded audit resource limits")
        state = preflight(args)
        result = state["public"]
        if args.execute:
            def interrupted(number, _):
                raise InterruptedError("signal " + str(number))
            old_handlers = {s: signal.signal(s, interrupted) for s in (signal.SIGINT, signal.SIGTERM)}
            result = execute(state, args)
    except (Exception, KeyboardInterrupt) as error:
        result = {"schema": 1, "status": "INCOMPLETE", "error": type(error).__name__ + ": " + str(error), **NO_BOOT}
    finally:
        for number, previous in old_handlers.items():
            signal.signal(number, previous)
    print(json.dumps(result, indent=2))
    return 2 if result["status"] == "INCOMPLETE" else 0


if __name__ == "__main__":
    raise SystemExit(main())
