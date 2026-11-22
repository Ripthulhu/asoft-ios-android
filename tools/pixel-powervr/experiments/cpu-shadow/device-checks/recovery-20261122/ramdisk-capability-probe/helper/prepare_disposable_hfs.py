#!/usr/bin/env python3
"""Embed the authored helper into a fresh HFS ramdisk copy with the pinned Linux VM."""

import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import types

BASE = Path("/data/local/tmp")
PREVIOUS_SOURCE = BASE / "asoft-rd-source-04/probe_ios26_ramdisk.py"
PREVIOUS_SOURCE_SHA = "891dce3d722c091b4c56e9a2bcba61be22b91d91acd6f8a805d956960bc46b63"
PREVIOUS_RESULT = BASE / "asoft-rd-probe-04/run/result.json"
PREVIOUS_RESULT_SHA = "07a7ec7e0c38aafef571fac2125ff4f60a3b3e88510e8a5384e9a2b7137f54ea"
SIGNED = BASE / "asoft-rd-probe-04/guest-unmount.signed"
SIGNED_SHA = "00e39e335386e61ee4c208d186a910b9daad40531b3d81d6feb5a2827f859b55"
CACHE = BASE / "asoft-rd-probe-04/ramdisk.tc"
CACHE_SHA = "c3aeacc6132a14afe6318f15041cc9eb15d461073953b0dd5b03c19f4f2954fd"
FIRST_EMBED_RESULT = BASE / "asoft-rd-embed-01/result.json"
FIRST_EMBED_SHA = "8c9d735830dcd0af07c46df922af165ba85c0ae1899468cc04630f5f1bf9fcec"
FIFTH_RESULT = BASE / "asoft-rd-probe-05/run/result.json"
FIFTH_SHA = "493254a47740cfc0fd54cbf5fff18e0d7f17b6a2fbd9d7c54b0ccf7f0e421af6"
WORK = BASE / "asoft-rd-fixture-01"
FIXTURE_BYTES = 96 << 20
OPTIONS = types.SimpleNamespace(helper_seconds=180, max_log_mib=64, min_free_mib=1536, min_available_mib=512)


def source_digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def load_probe():
    state = PREVIOUS_SOURCE.read_bytes()
    if hashlib.sha256(state).hexdigest() != PREVIOUS_SOURCE_SHA:
        raise ValueError("prior probe source mismatch")
    probe = types.ModuleType("pinned_ramdisk_probe")
    probe.__file__ = str(PREVIOUS_SOURCE)
    exec(compile(state, str(PREVIOUS_SOURCE), "exec"), vars(probe))
    return probe


def grace_reap(original, receipt, seconds=5):
    """Wait briefly for this dedicated owner's children to exit without signals."""
    deadline = time.monotonic() + 3
    natural = []
    receipt["natural_grace_reaped"] = natural
    while time.monotonic() < deadline:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return {"echild": True, "forced_descendants": []}
        if pid:
            natural.append(pid)
        else:
            time.sleep(0.025)
    return original(seconds)


SCRIPT = """#!/bin/bash
set -euo pipefail
root=/mnt/asoft-embed
mkdir -m 700 "$root"
mount -t hfsplus -o rw ramdisk.hfs "$root"
trap 'umount "$root"' EXIT
mountpoint -q "$root"
python3 - <<'COPY'
from pathlib import Path
import hashlib, os
root = Path('/mnt/asoft-embed')
if (root / 'bin').resolve(strict=True) != root / 'bin':
    raise ValueError('ramdisk bin directory is not a real directory')
body = Path('asoft-unmount').read_bytes()
if hashlib.sha256(body).hexdigest() != 'SIGNED_HELPER_SHA':
    raise ValueError('helper input hash mismatch')
target = root / 'bin/asoft-unmount'
with target.open('xb') as stream:
    stream.write(body)
    os.fchmod(stream.fileno(), 0o755)
    stream.flush()
    os.fsync(stream.fileno())
if target.read_bytes() != body:
    raise ValueError('copied helper mismatch')
mount_directory = root / 'mnt'
if not mount_directory.exists():
    mount_directory.mkdir(mode=0o755)
if mount_directory.resolve(strict=True) != mount_directory:
    raise ValueError('ramdisk mount directory is not a real directory')
(mount_directory / 'asoft-recovery').mkdir(mode=0o700)
COPY
sync
umount "$root"
trap - EXIT
if mountpoint -q "$root"; then
    exit 1
fi
fsck.hfsplus -f -n ramdisk.hfs
test -b disposable.hfs
mkfs.hfsplus -J -v ASOFTDisposable disposable.hfs
fsck.hfsplus -f -n disposable.hfs
printf '%s\\n' '{"schema":1,"copied":true,"unmounted":true,"readonly_fsck":true,"disposable_formatted":true,"sha256":"SIGNED_HELPER_SHA"}' > patch-result.json
""".replace("SIGNED_HELPER_SHA", SIGNED_SHA)


def main():
    if sys.argv[1:] != ["--execute"] or os.geteuid() != 0 or not sys.flags.isolated or not sys.dont_write_bytecode:
        raise ValueError("use root Python -I -B with the explicit --execute flag")
    probe = load_probe()
    lock = os.open(probe.PREP / "owner.lock", os.O_RDONLY | os.O_NOFOLLOW)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assets = probe.check_inputs()
        probe.file_pin(PREVIOUS_RESULT, PREVIOUS_RESULT_SHA)
        probe.file_pin(FIRST_EMBED_RESULT, FIRST_EMBED_SHA)
        probe.file_pin(FIFTH_RESULT, FIFTH_SHA)
        probe.file_pin(SIGNED, SIGNED_SHA)
        probe.file_pin(CACHE, CACHE_SHA)
        prep, _ = probe.preparation()
        session = json.loads(probe.file_pin(probe.SESSION, probe.PINS[probe.SESSION], body=True))
        prep.require_memory(session["helper_ram_mib"])
        probe.require(shutil.disk_usage(BASE).free >= 4_500_000_000, "insufficient fresh work storage")
        WORK.mkdir(mode=0o700)
        image = WORK / "rd-shell-with-helper.hfs"
        fixture = WORK / "disposable.hfs"
        receipt = {"schema": 1, "status": "INCOMPLETE", "started_utc": prep.cold.utc()}
        try:
            host_source = Path(__file__).resolve()
            receipt["source_sha256"] = source_digest(host_source)
            with assets["ramdisk"].open("rb") as original, image.open("xb") as copy:
                shutil.copyfileobj(original, copy, 1 << 20)
                copy.flush()
                os.fsync(copy.fileno())
            probe.file_pin(image, probe.INPUTS["ramdisk"][1])
            shutil.copyfile(SIGNED, WORK / "asoft-unmount")
            probe.file_pin(WORK / "asoft-unmount", SIGNED_SHA)
            manifest = Path(session["tooling"]) / prep.TOOL_ENTRIES["setup_manifest"]
            plan = {"session": session, "manifest": json.loads(manifest.read_bytes()), "work": str(WORK),
                    "artifacts": {"asoft-unmount": {"path": "asoft-unmount"}}}
            recipe = {"files": ["asoft-unmount"], "out": ["patch-result.json"], "scratch": []}
            target = {"path": image, "format": "raw", "readonly": False, "serial": "d0", "at": "ramdisk.hfs"}
            with fixture.open("xb") as stream:
                stream.truncate(FIXTURE_BYTES)
            disposable = {"path": fixture, "format": "raw", "readonly": False, "serial": "d1", "at": "disposable.hfs"}
            tar = prep.input_tar(plan, recipe, WORK, [target, disposable], authored_script=SCRIPT)
            returned = WORK / "out.raw"
            with returned.open("xb") as stream:
                stream.truncate(8 << 20)
            disks = [{"path": tar, "format": "raw", "readonly": True, "serial": "in"},
                     {"path": returned, "format": "raw", "readonly": False, "serial": "out"}, target, disposable]
            argv, env = prep.helper_command(plan, WORK, disks)
            prep.cold.subreaper()
            original_reap = prep.cold.reap_owned
            prep.cold.reap_owned = lambda seconds=5: grace_reap(original_reap, receipt, seconds)
            try:
                vm = prep.supervise_vm(plan, "ramdisk-helper-embed", WORK, argv, env, OPTIONS)
            finally:
                prep.cold.reap_owned = original_reap
            probe.require(vm["witnesses"]["native_svc_final"] and len(vm["out_sizes"]) == 1, "missing helper witnesses")
            files = WORK / "files"
            files.mkdir(mode=0o700)
            prep.safe_return_tar(returned, vm["out_sizes"][0], files, recipe["out"])
            guest = json.loads((files / "patch-result.json").read_bytes())
            probe.require(guest == {"schema": 1, "copied": True, "unmounted": True,
                                    "readonly_fsck": True, "disposable_formatted": True,
                                    "sha256": SIGNED_SHA}, "guest receipt mismatch")
            image_sha = source_digest(image)
            probe.require(image.stat().st_size == assets["ramdisk"].stat().st_size
                          and image_sha != probe.INPUTS["ramdisk"][1], "unexpected candidate image identity")
            receipt["image"] = {"path": str(image), "sha256": image_sha, "bytes": image.stat().st_size}
            with fixture.open("rb") as stream:
                stream.seek(1024)
                header = stream.read(512)
            probe.require(fixture.stat().st_size == FIXTURE_BYTES and header[:2] == b"H+"
                          and int.from_bytes(header[4:8], "big") & 0x2000,
                          "disposable volume is not journaled HFS+")
            receipt["fixture"] = {"path": str(fixture), "sha256": source_digest(fixture), "bytes": FIXTURE_BYTES}
            receipt["guest"] = guest
        except BaseException as error:
            receipt["error"] = f"{type(error).__name__}: {error}"
        finally:
            try:
                probe.check_inputs()
                probe.file_pin(PREVIOUS_RESULT, PREVIOUS_RESULT_SHA)
                probe.file_pin(FIRST_EMBED_RESULT, FIRST_EMBED_SHA)
                probe.file_pin(FIFTH_RESULT, FIFTH_SHA)
                probe.file_pin(SIGNED, SIGNED_SHA)
                probe.file_pin(CACHE, CACHE_SHA)
                probe.file_pin(host_source, receipt["source_sha256"])
                receipt["preservation_verified"] = True
            except Exception as error:
                receipt["preservation_error"] = f"{type(error).__name__}: {error}"
            if "error" not in receipt and "preservation_error" not in receipt:
                receipt["status"] = "DISPOSABLE_HFS_FIXTURE_PREPARED"
            receipt["finished_utc"] = prep.cold.utc()
            prep.atomic_json(WORK / "result.json", receipt)
        print(json.dumps(receipt, sort_keys=True), flush=True)
        return 0 if receipt["status"] == "DISPOSABLE_HFS_FIXTURE_PREPARED" else 2
    finally:
        os.close(lock)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"status": "REFUSED", "error": f"{type(error).__name__}: {error}"}), flush=True)
        raise SystemExit(2)
