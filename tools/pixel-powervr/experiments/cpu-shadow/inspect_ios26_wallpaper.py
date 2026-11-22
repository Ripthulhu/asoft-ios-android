#!/usr/bin/env python3
"""Separate read-only saved-wallpaper journal/fsck gate before locale.

Default is preflight. Only a fresh owned audit directory receives writes.
The successful wallpaper guard and every earlier proof retain their own scope.
"""
import argparse
import contextlib
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import stat
import sys
import tarfile
import time
import types


SOURCES = ("inspect_ios26_wallpaper.py", "inspect_ios26_wallpaper_guest.py")
RAW_SHA256 = "ada26de8ababb11bb4af20e558708545eb64fd516481359fd5d0ccf6a7cbae2b"
PARTITION_SHA256 = "6874b9b6b68c7fb50c3f9cf05c1b6a86a53f8fed75863c00a6ad9254b1640593"
# Wallpaper execution guard from commit 079a9da, independently reviewed.
GUARD_SHA256 = "a92e26604ec76d2280528ad396a961a8cda901e29177f87887d5b7ce8b495c44"
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
        raise ValueError("nonregular or oversized source/metadata file")
    return path.read_bytes()


def module_from(body, path):
    module = types.ModuleType("bound_" + Path(path).stem)
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def preflight(args):
    if not args.guard_work or not args.work:
        raise ValueError("required --guard-work and --work")
    if not 1 <= args.helper_seconds <= 14400 or not 8 <= args.max_log_mib <= 64 or args.min_free_mib < 1536 or args.min_available_mib < 512:
        raise ValueError("inspection bounds cannot be weakened or disabled")
    guard_work, work = canonical(args.guard_work), canonical(args.work, False)
    if work.exists() or not work.parent.is_dir() or len(str(work)) > 55:
        raise ValueError("fresh inspection directory requires an existing parent and at most 55 characters")
    guarded = json.loads(read(guard_work / "guard-session.json"))
    guarded_result = json.loads(read(guard_work / "result.json"))
    recorded = json.loads(read(guard_work / "guard-observations.json"))
    guard_source = canonical(guarded["guard_source"])
    guard_body = read(guard_source)
    if sha(guard_body) != GUARD_SHA256 or guarded.get("guard_source_sha256") != GUARD_SHA256:
        raise ValueError("wallpaper guard source is not the approved immutable revision")
    guard = module_from(guard_body, guard_source)
    context = guard.context(guarded["apps_audit"]["work"], guard.STAGE)
    bound = guard.guard_acceptance(context, guard_work, guarded, guarded_result, recorded)
    prep, plan, session = context["prep"], context["plan"], context["plan"]["session"]
    guard_state = {"prep": prep, "receipt": guarded, "prep_work": context["prep_work"], "plan": plan}
    guard.unchanged_inputs(guard_state, allow_wallpaper=True, full=True)
    source_dir = canonical(Path(__file__).parent)
    bodies = {name: read(source_dir / name) for name in SOURCES}
    raw_body, partition_body = context["raw_body"], context["partition_body"]
    if sha(raw_body) != RAW_SHA256 or sha(partition_body) != PARTITION_SHA256:
        raise ValueError("saved-wallpaper raw inspection dependencies changed")
    roots = guard.output_roots(context) | {guard_work, guard_source.parent, source_dir}
    if any(work.is_relative_to(root) or root.is_relative_to(work) for root in roots):
        raise ValueError("inspection output must be outside every input/source/evidence tree")
    dependencies = {str(context["raw_source"]): RAW_SHA256, str(context["partition_source"]): PARTITION_SHA256,
                    str(guard_source): GUARD_SHA256}
    receipt = {"schema": 1, "kind": "ios26_saved_wallpaper_inspection", "prep_work": str(context["prep_work"]),
        "runner_dir": str(context["runner"]), "prep_session_sha256": sha(read(context["prep_work"] / "session.json")),
        "frozen_sources": session["runner_sources"], "guard_work": str(guard_work),
        "guard_source": str(guard_source), "guard_source_sha256": GUARD_SHA256,
        "wallpaper_guard_files": bound, "guard_checkpoint": guarded_result["checkpoint"],
        "apps_audit": context["apps_audit"], "checkpoints": context["inventory"]["hashes"],
        "disk_chain": context["disk_chain"], "baseline": context["disk_chain"][1],
        "source_directory": str(source_dir), "inspector_sources": {name: sha(body) for name, body in bodies.items()},
        "dependency_files": dependencies, "runtime": session["runtime"],
        "qualification_sha256": session["qualification"]["qualification_sha256"],
        "tooling_manifest_sha256": session["tooling_manifest_sha256"],
        "readonly": True, "mounts_allowed": False, "replay_allowed": False, "repair_allowed": False,
        "native_required": True, "tcg_retry": False,
        "helper_ram_mib": session["helper_ram_mib"], "helper_vcpus": session["helper_vcpus"],
        "bounds": {"helper_seconds": args.helper_seconds, "max_log_mib": args.max_log_mib,
                   "min_free_mib": args.min_free_mib, "min_available_mib": args.min_available_mib}, **NO_BOOT}
    return {"prep": prep, "guard": guard, "guard_state": guard_state, "app": context["app"], "plan": plan,
        "inventory": context["inventory"], "work": work, "prep_work": context["prep_work"],
        "disk": canonical(context["disk_chain"][0]["identity"]["path"]),
        "baseline": canonical(context["disk_chain"][1]["identity"]["path"]),
        "bodies": bodies, "raw_body": raw_body, "partition_body": partition_body,
        "auditor": context["auditor"], "receipt": receipt}


def unchanged_inputs(state, full=True):
    prep, guard, receipt = state["prep"], state["guard"], state["receipt"]
    guard.unchanged_inputs(state["guard_state"], allow_wallpaper=True, full=full)
    inventory = guard.checkpoint_inventory(prep, state["prep_work"], state["plan"]["session"], guard.STAGE)
    if inventory["hashes"] != receipt["checkpoints"]:
        raise ValueError("wallpaper checkpoint boundary changed")
    for path, expected in receipt["wallpaper_guard_files"].items():
        if sha(read(path)) != expected:
            raise ValueError("successful wallpaper guard/attempt evidence changed")
    if {name: sha(read(Path(receipt["source_directory"]) / name)) for name in SOURCES} != receipt["inspector_sources"]:
        raise ValueError("saved-wallpaper inspection source changed")
    for path, expected in receipt["dependency_files"].items():
        if sha(read(path)) != expected:
            raise ValueError("reviewed raw inspection dependency changed")
    if full:
        if guard.full_disks(prep, state["prep_work"], inventory) != receipt["disk_chain"]:
            raise ValueError("full saved-wallpaper/backing identity changed")
    elif any(prep.cold.readonly_identity(row["identity"]["path"]) != row["identity"] for row in receipt["disk_chain"]):
        raise ValueError("saved-wallpaper/backing identity changed")


@contextlib.contextmanager
def own_inspection(state):
    original = os.open(state["prep_work"] / "owner.lock", os.O_RDONLY | os.O_NOFOLLOW)
    owned = None
    try:
        if not stat.S_ISREG(os.fstat(original).st_mode):
            raise ValueError("original preparation owner lock is not regular")
        try:
            fcntl.flock(original, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("preparation still has another owner") from None
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
    files = {".job/run": b"run.sh\n", ".job/disks": b"d0 wallpaper.qcow2\nd1 gpu.qcow2\n",
             ".job/out": b"inspection\n", ".job/scratch": b"",
             "wallpaper_guest.py": state["bodies"][SOURCES[1]],
             "raw_guest.py": state["raw_body"], "partition_guest.py": state["partition_body"],
             "policy.json": json.dumps(policy, sort_keys=True).encode(),
             "run.sh": b"#!/bin/bash\nset -euo pipefail\npython3 -I wallpaper_guest.py /work/wallpaper.qcow2 /work/gpu.qcow2 /work/policy.json /work/raw_guest.py /work/partition_guest.py /work/inspection\n"}
    target = attempt / "in.tar"
    with target.open("xb") as stream, tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name, body in sorted(files.items()):
            entry = tarfile.TarInfo(name)
            entry.mode, entry.size = (0o755 if name.endswith(".sh") else 0o644), len(body)
            archive.addfile(entry, io.BytesIO(body))
    return target


def guest_pass(state, directory, policy):
    result = json.loads(read(directory / "result.json"))
    if (result.get("schema") != 1 or result.get("kind") != "ios26_saved_wallpaper_inspection" or
            result.get("status") != "SAVED_WALLPAPER_INSPECTION_PASSED" or result.get("errors") != [] or
            result.get("cleanup_errors") != [] or result.get("readonly_attachments") is not True or
            result.get("raw_metadata_unchanged") is not True or result.get("mounted") is not False or
            result.get("replayed") is not False or result.get("repaired") is not False or
            result.get("inspection_nonce") != policy["inspection_nonce"] or
            result.get("policy_sha256") != state["prep"].digest(policy) or
            result.get("gpt", {}).get("status") != "PASSED" or result["gpt"].get("disk_bytes") != DISK_BYTES or
            result.get("baseline_gpt") != result["gpt"] or set(result.get("journals", {})) != {"iOSRoot", "Data"} or
            set(result.get("fsck", {})) != {"iOSRoot", "Data"} or
            result.get("raw_implementation") != {"guest_sha256": RAW_SHA256, "partition_guest_sha256": PARTITION_SHA256,
                "returned_kind": "ios26_saved_firstboot_inspection", "returned_status": "SAVED_FIRSTBOOT_INSPECTION_PASSED"}):
        raise ValueError("saved-wallpaper raw inspection is incomplete or belongs to another attempt")
    for name, filename in (("iOSRoot", "fsck-system.txt"), ("Data", "fsck-data.txt")):
        row = result["journals"][name]
        if row.get("status") != "PASSED" or row.get("journal", {}).get("status") != "PASSED" or row["journal"].get("state") not in (
                "INITIALIZED_EMPTY", "UNTOUCHED_AUTHORED_NEEDINIT"):
            raise ValueError("saved-wallpaper raw journal gate incomplete")
        output = read(directory / filename).decode("utf-8", "strict")
        verdict = state["auditor"].fsck_verdict(result["fsck"][name].get("exit_code"), output)
        if verdict["status"] != "PASSED" or verdict != result["fsck"][name]:
            raise ValueError("saved-wallpaper filesystem diagnostics do not prove a complete clean read-only check")
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
            policy = {"schema": 1, "kind": "ios26_saved_wallpaper_inspection", "inspection_nonce": os.urandom(16).hex(),
                "inspection_session_sha256": result["inspection_session_sha256"], "raw_guest_sha256": RAW_SHA256,
                "partition_guest_sha256": PARTITION_SHA256}
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
            observed = prep.supervise_vm(state["plan"], "saved-wallpaper-inspection", attempt, argv, env, args)
            result.update(native_witnesses=observed.get("witnesses"), cleanup=observed.get("cleanup"),
                          natural_exit=observed.get("natural_exit"))
            state["app"].require_native(result)
            if not prep.vm_success(observed, True) or len(observed.get("out_sizes", [])) != 1:
                raise ValueError("saved-wallpaper helper lacks unique output or natural native completion")
            regular = prep.safe_return_tar(raw, observed["out_sizes"][0], attempt / "files", ["inspection"])
            allowed = {"inspection/result.json", "inspection/fsck-system.txt", "inspection/fsck-data.txt"}
            if not regular <= allowed or "inspection/result.json" not in regular:
                raise ValueError("unexpected saved-wallpaper inspection output")
            result["outputs"] = {name: prep.file_record(attempt / "files" / name, work) for name in sorted(regular)}
            result["guest_result"] = json.loads(read(attempt / "files/inspection/result.json"))
            guest_pass(state, attempt / "files/inspection", policy)
            if regular != allowed:
                raise ValueError("missing complete saved-wallpaper filesystem diagnostics")
            result["status"] = "SAVED_WALLPAPER_INSPECTION_PASSED"
        except BaseException as error:
            result["error"] = type(error).__name__ + ": " + str(error)
        finally:
            with prep.cleanup_signals():
                try:
                    unchanged_inputs(state, True)
                    result["full_disk_chain_unchanged"] = True
                    result["preparation_and_prior_evidence_unchanged"] = True
                except Exception as error:
                    result["status"] = "INCOMPLETE"
                    result["identity_error"] = type(error).__name__ + ": " + str(error)
                if (attempt / "launch.json").exists():
                    result["launch"] = {"path": str(attempt / "launch.json"), "sha256": sha(read(attempt / "launch.json"))}
                result["finished_utc"], result["elapsed_seconds"] = cold.utc(), time.monotonic() - started
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
    return 0 if result["status"] in ("PREFLIGHT_READY", "SAVED_WALLPAPER_INSPECTION_PASSED") else 2


if __name__ == "__main__":
    raise SystemExit(main())
