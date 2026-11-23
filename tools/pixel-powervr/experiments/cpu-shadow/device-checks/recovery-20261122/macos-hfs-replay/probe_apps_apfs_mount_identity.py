#!/usr/bin/env python3
"""Record the read-only APFS-FUSE mount identity on the pinned Pixel helper."""
import fcntl
import json
import os
from pathlib import Path
import sys
import types

BASE = Path("/data/local/tmp")
CONTROL = BASE / "asoft-recovered-control-01"
WORK = BASE / "asoft-apfs-identity-01"


def main():
    if sys.argv[1:] != ["--execute"] or not sys.flags.isolated or not sys.dont_write_bytecode or os.geteuid():
        raise ValueError("requires root Python -I -B and explicit --execute")
    src = CONTROL / "continue_apps_with_root_proof.py"
    mod = types.ModuleType("bound_app_audit_continuation")
    mod.__file__ = str(src)
    body = src.read_bytes()
    import hashlib
    if hashlib.sha256(body).hexdigest() != "0d5ed9798d8713a329bdb1cb215feb1fb91449dea6be0b43ffb0d45b7373a77f":
        raise ValueError("source changed")
    exec(compile(body, str(src), "exec"), vars(mod))
    driver = mod.load_driver()
    _, receipt, _ = driver.wait_inspection(27579)
    session_body = (driver.PREP / "session.json").read_bytes()
    driver.require(driver.sha(session_body) == receipt["prep_session_sha256"], "session changed")
    session = json.loads(session_body)
    guard = driver.load(driver.GUARD, "ea40638312d6ac41607806ecb03c148fbd0677df6ab01480e13fd40536869674")
    prep = guard.load_frozen(driver.RUNNER, session["runner_sources"])
    prep.cold.require_phone(session)
    prep.cold.subreaper()
    driver.allow_natural_reap(prep.cold)
    with (driver.PREP / "owner.lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        prep.refuse_live_children(driver.PREP)
        plan, paths = driver.setup(prep, session, receipt,
                                   {"path": str(driver.RECOVERED), "sha256": driver.RECOVERED_SHA})
        logical = "os/094-97246-090.dmg"
        original = paths[logical]
        identity = prep.cold.readonly_identity(original)
        driver.require(prep.cold.sha(original) == plan["artifacts"][logical]["sha256"], "APFS input changed")
        WORK.mkdir(mode=0o700)
        source = {"path": original, "format": "raw", "readonly": True, "serial": "d0", "at": "original.dmg"}
        script = """#!/bin/bash
set -euo pipefail
image=$(realpath original.dmg)
test -b "$image"
test "$(blockdev --getro "$image")" = 1
tmp=$(mktemp -d /tmp/asoft-apfs-name.XXXXXX)
trap 'if mountpoint -q "$tmp/os"; then fusermount -u "$tmp/os"; fi' EXIT
ln -s "$image" "$tmp/source.dmg"
mkdir "$tmp/os"
apfs-fuse -o ro,nosuid,nodev,noexec,allow_other "$tmp/source.dmg" "$tmp/os"
python3 - "$tmp" "$image" <<'PY'
import json,sys
from pathlib import Path
root, image=sys.argv[1:]
target=root+'/os'
matches=[]
for line in Path('/proc/self/mountinfo').read_text().splitlines():
 fields=line.split()
 if fields[4]==target:
  pivot=fields.index('-')
  source=fields[pivot+2]
  matches.append({'root':fields[3],'options':fields[5].split(','),'type':fields[pivot+1],
                  'source':source,'source_is_image_alias':source==root+'/source.dmg',
                  'source_is_attached_block':source==image})
assert len(matches)==1
assert {'ro','nosuid','nodev','noexec'} <= set(matches[0]['options'])
Path('mount-identity.json').write_text(json.dumps(matches[0],sort_keys=True)+'\\n')
PY
fusermount -u "$tmp/os"
if mountpoint -q "$tmp/os"; then exit 1; fi
trap - EXIT
"""
        recipe = {"files": [], "out": ["mount-identity.json"], "scratch": []}
        archive = prep.input_tar(plan, recipe, WORK, [source], authored_script=script)
        raw = WORK / "out.raw"
        with raw.open("xb") as stream:
            stream.truncate(8 << 20)
        argv, env = prep.helper_command(plan, WORK, [
            {"path": archive, "format": "raw", "readonly": True, "serial": "in"},
            {"path": raw, "format": "raw", "readonly": False, "serial": "out"}, source])
        bound = types.SimpleNamespace(helper_seconds=300, max_log_mib=64, min_free_mib=1536, min_available_mib=512)
        observed = prep.supervise_vm(plan, "apfs-mount-identity", WORK, argv, env, bound)
        driver.require(prep.vm_success(observed, True) and observed["witnesses"]["native_svc_final"] and
                       len(observed["out_sizes"]) == 1 and prep.cold.readonly_identity(original) == identity,
                       "APFS identification helper was not accepted")
        files = WORK / "files"
        files.mkdir(mode=0o700)
        prep.safe_return_tar(raw, observed["out_sizes"][0], files, recipe["out"])
        print((files / "mount-identity.json").read_text(), end="", flush=True)


if __name__ == "__main__":
    main()
