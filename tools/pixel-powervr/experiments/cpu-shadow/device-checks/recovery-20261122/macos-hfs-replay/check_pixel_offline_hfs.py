#!/usr/bin/env python3
"""Run the pinned native Linux read-only HFS checker on a detached raw volume."""

import fcntl
import json
import os
from pathlib import Path
import re
import sys
import types


def main():
    if len(sys.argv) != 5 or sys.argv[1] != "--execute" or not sys.flags.isolated:
        raise ValueError("usage: Python -I -B SCRIPT --execute RAW SHA256 NEW-WORK")
    image = Path(sys.argv[2])
    digest = sys.argv[3]
    work = Path(sys.argv[4])
    source = Path("/data/local/tmp/asoft-pixel-replay-input-01/probe_pixel_replay.py")
    if os.geteuid() != 0 or not sys.dont_write_bytecode:
        raise ValueError("root and Python -B are required")
    if (not re.fullmatch(r"[0-9a-f]{64}", digest) or
            work.parent != Path("/data/local/tmp") or work != work.resolve() or
            not re.fullmatch(r"asoft-offline-hfs-check-[a-z0-9]+", work.name)):
        raise ValueError("expected a pinned raw image and a fresh test work path")

    import hashlib
    body = source.read_bytes()
    if hashlib.sha256(body).hexdigest() != "1644dc916290a025d51a2f6515f03db62fa2a9efc5452ec5449af4ffb12d390c":
        raise ValueError("unexpected helper source")
    loader = types.ModuleType("pinned_replay_loader")
    loader.__file__ = str(source)
    exec(compile(body, str(source), "exec"), vars(loader))
    probe = loader.load_bound(loader.OLD_PROBE, loader.BASELINE_PINS[loader.OLD_PROBE],
                              "pinned_rd_probe_restored")
    lock = os.open(probe.PREP / "owner.lock", os.O_RDONLY | os.O_NOFOLLOW)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        probe.check_inputs()
        prep, _ = probe.preparation()
        session = json.loads(probe.file_pin(probe.SESSION, probe.PINS[probe.SESSION], body=True))
        probe.file_pin(image, digest)
        if image.stat().st_size not in (96 << 20, 16 << 30):
            raise ValueError("expected a detached fixture or Data-sized raw volume")
        prep.require_memory(session["helper_ram_mib"])
        result = {"status": "INCOMPLETE", "started_utc": prep.cold.utc()}
        work.mkdir(mode=0o700)
        try:
            manifest = Path(session["tooling"]) / prep.TOOL_ENTRIES["setup_manifest"]
            plan = {"session": session, "manifest": json.loads(manifest.read_bytes()),
                    "work": str(work), "artifacts": {}}
            recipe = {"files": [], "out": ["fsck.txt", "fsck-status.txt"], "scratch": []}
            raw = {"path": image, "format": "raw", "readonly": True,
                   "serial": "d0", "at": "detached-volume.hfs"}
            recipe_text = """#!/bin/bash
set -euo pipefail
test -b detached-volume.hfs
test "$(blockdev --getro detached-volume.hfs)" = 1
status=0
fsck.hfsplus -f -n detached-volume.hfs > fsck.txt 2>&1 || status=$?
printf '%s\\n' "$status" > fsck-status.txt
"""
            archive = prep.input_tar(plan, recipe, work, [raw], authored_script=recipe_text)
            returned = work / "out.raw"
            with returned.open("xb") as stream:
                stream.truncate(8 << 20)
            disks = [{"path": archive, "format": "raw", "readonly": True, "serial": "in"},
                     {"path": returned, "format": "raw", "readonly": False, "serial": "out"}, raw]
            argv, env = prep.helper_command(plan, work, disks)
            options = types.SimpleNamespace(helper_seconds=240, max_log_mib=64,
                                            min_free_mib=1536, min_available_mib=512)
            prep.cold.subreaper()
            original_reap = prep.cold.reap_owned
            prep.cold.reap_owned = lambda seconds=5: loader.clean_reap(original_reap, seconds)
            try:
                vm = prep.supervise_vm(plan, "offline-hfs-readonly-fsck", work, argv, env, options)
            finally:
                prep.cold.reap_owned = original_reap
            if not vm["witnesses"]["native_svc_final"] or len(vm["out_sizes"]) != 1:
                raise ValueError("missing native checker completion")
            files = work / "files"
            files.mkdir(mode=0o700)
            prep.safe_return_tar(returned, vm["out_sizes"][0], files, recipe["out"])
            code = int((files / "fsck-status.txt").read_text())
            text = (files / "fsck.txt").read_bytes()
            result["checker_exit_code"] = code
            result["checker_reported_ok"] = b"appears to be OK" in text
            result["native_checker_completed"] = True
            result["checker_log_sha256"] = hashlib.sha256(text).hexdigest()
            if code or not result["checker_reported_ok"]:
                raise ValueError("read-only HFS check was not accepted")
        except BaseException as error:
            result["error"] = f"{type(error).__name__}: {error}"
        finally:
            try:
                probe.file_pin(image, digest)
                result["input_sha256_reverified"] = digest
                probe.check_inputs()
            except Exception as error:
                result["preservation_error"] = f"{type(error).__name__}: {error}"
            if not {"error", "preservation_error"} & result.keys():
                result["status"] = "READ_ONLY_HFS_CHECK_PASSED"
            result["finished_utc"] = prep.cold.utc()
            prep.atomic_json(work / "verification.json", result)
        print(json.dumps(result, sort_keys=True), flush=True)
        return 0 if result["status"] == "READ_ONLY_HFS_CHECK_PASSED" else 2
    finally:
        os.close(lock)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"status": "REFUSED", "error": f"{type(error).__name__}: {error}"}), flush=True)
        raise SystemExit(2)
