#!/usr/bin/env python3
"""Run an isolated native Pixel replay-only test on the synthetic HFSX volume."""

import argparse
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import struct
import sys
import time
import types

BASE = Path("/data/local/tmp")
INPUT = BASE / "asoft-pixel-replay-input-01"
STAGE = BASE / "asoft-rd-replay-stage-01"
WORK = BASE / "asoft-rd-probe-replay1"
OLD_PROBE = BASE / "asoft-rd-source-06/probe_ios26_ramdisk.py"
OLD_RUN = BASE / "asoft-rd-probe-06"
OLD_FIXTURE = BASE / "asoft-rd-fixture-01"
BASELINE_PINS = {
    OLD_PROBE: "35151a69c21bef98e9fe99a6f32de7b76b715d106680d14954062b68f73569ae",
    OLD_RUN / "cache-result.json": "afc7d7076d1d072d6e6d00cf355c591fd470596a1246dabb5f22979a6909a607",
    OLD_RUN / "ramdisk.tc": "c3aeacc6132a14afe6318f15041cc9eb15d461073953b0dd5b03c19f4f2954fd",
    OLD_RUN / "run/result.json": "61a48cb59e15ae7068f4dd3a78583f2189b1818af84b6bd234aed3c1a65ea475",
    OLD_FIXTURE / "rd-shell-with-helper.hfs": "5ed8b90314d95ebb3554e763edf5c8d3c9e75faa6c2b909d7784463c02665226",
}
PROBE_STATUS = "DISPOSABLE_REPLAY_GUEST_OBSERVED"
REPLAY_MARKER = "HFS_REPLAY_JOURNAL returned success"
CANDIDATE = "/bin/asoft-replay-fixture"
IMAGE_BYTES = 96 << 20


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_bound(path, sha, name, transform=lambda body: body):
    require(path == path.resolve(strict=True) and path.is_file(), "unexpected bound source")
    body = path.read_bytes()
    require(len(body) <= 128 << 10 and hashlib.sha256(body).hexdigest() == sha,
            "bound source hash differs")
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(transform(body), str(path), "exec"), module.__dict__)
    return module


def replay_status_only(body):
    previous = b"DISPOSABLE_HFS_UNMOUNT_OBSERVED"
    require(body.count(previous) == 1, "unexpected status in prior probe")
    return body.replace(previous, PROBE_STATUS.encode())


def expand_fixture(probe, metadata, expected_archive, path):
    packed = INPUT / "synthetic-hfsx.raw.gz"
    probe.file_pin(packed, expected_archive)
    require(packed.stat().st_size <= 1 << 20, "synthetic input archive too large")
    with gzip.open(packed, "rb") as source, path.open("xb") as target:
        remaining = IMAGE_BYTES
        while remaining:
            chunk = source.read(min(remaining, 1 << 20))
            require(chunk, "synthetic HFSX image truncated")
            target.write(chunk)
            remaining -= len(chunk)
        require(not source.read(1), "synthetic HFSX image expanded past its bound")
        target.flush()
        os.fsync(target.fileno())
    probe.file_pin(path, metadata["sha256"])


def read_fixture(inspector, image, metadata):
    finder_offset = metadata["finder_info_offset"]
    expected = bytes.fromhex(metadata["finder_info_after_hex"])
    require(len(expected) == 32 and expected[:8] == b"GOODasft", "wrong FinderInfo witness")
    with image.open("rb") as source:
        info = inspector.layout(source)
        journal = inspector.journal(source, info)
        require(info.catalog_offset <= finder_offset <=
                info.catalog_offset + info.catalog_bytes - len(expected),
                "FinderInfo witness outside fixture catalog")
        witness = inspector.read_at(source, finder_offset, len(expected))
    return (journal.start, journal.end), witness, info.attributes, expected


def clean_reap(original, seconds=5):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return {"echild": True, "forced_descendants": []}
        if pid == 0:
            time.sleep(0.025)
    return original(seconds)


def embed_helper(probe, prep, signed, expected):
    source = OLD_FIXTURE / "rd-shell-with-helper.hfs"
    image = STAGE / "rd-shell-with-helper.hfs"
    with source.open("rb") as stream, image.open("xb") as copy:
        shutil.copyfileobj(stream, copy, 1 << 20)
        copy.flush()
        os.fsync(copy.fileno())
    probe.file_pin(image, BASELINE_PINS[source])

    session = json.loads(probe.file_pin(probe.SESSION, probe.PINS[probe.SESSION], body=True))
    prep.require_memory(session["helper_ram_mib"])
    manifest = Path(session["tooling"]) / prep.TOOL_ENTRIES["setup_manifest"]
    plan = {"session": session, "manifest": json.loads(manifest.read_bytes()), "work": str(STAGE),
            "artifacts": {signed.name: {"path": signed.name}}}
    file_list = {"files": [signed.name], "out": ["patch-result.json"], "scratch": []}
    guest_script = """#!/bin/bash
set -euo pipefail
root=/mnt/asoft-embed-replay
mkdir -m 700 "$root"
mount -t hfsplus -o rw ramdisk.hfs "$root"
trap 'umount "$root"' EXIT
mountpoint -q "$root"
test ! -L "$root/bin"
test ! -e "$root/bin/asoft-replay-fixture"
sha256sum -c <<'HASH'
DIGEST  asoft-replay-fixture
HASH
install -m 755 asoft-replay-fixture "$root/bin/asoft-replay-fixture"
cmp asoft-replay-fixture "$root/bin/asoft-replay-fixture"
sync
umount "$root"
trap - EXIT
if mountpoint -q "$root"; then exit 1; fi
fsck.hfsplus -f -n ramdisk.hfs
printf '%s\\n' '{"schema":1,"helper_sha256":"DIGEST","unmounted":true,"readonly_fsck":true}' > patch-result.json
""".replace("DIGEST", expected)
    target = {"path": image, "format": "raw", "readonly": False, "serial": "d0", "at": "ramdisk.hfs"}
    archive = prep.input_tar(plan, file_list, STAGE, [target], authored_script=guest_script)
    returned = STAGE / "out.raw"
    with returned.open("xb") as stream:
        stream.truncate(8 << 20)
    disks = [{"path": archive, "format": "raw", "readonly": True, "serial": "in"},
             {"path": returned, "format": "raw", "readonly": False, "serial": "out"}, target]
    argv, env = prep.helper_command(plan, STAGE, disks)
    options = types.SimpleNamespace(helper_seconds=180, max_log_mib=64, min_free_mib=1536,
                                    min_available_mib=512)
    prep.cold.subreaper()
    original_reap = prep.cold.reap_owned
    prep.cold.reap_owned = lambda seconds=5: clean_reap(original_reap, seconds)
    try:
        vm = prep.supervise_vm(plan, "replay-helper-embed", STAGE, argv, env, options)
    finally:
        prep.cold.reap_owned = original_reap
    require(vm["witnesses"]["native_svc_final"] and len(vm["out_sizes"]) == 1,
            "embedding VM did not publish the native completion witness")
    files = STAGE / "files"
    files.mkdir(mode=0o700)
    prep.safe_return_tar(returned, vm["out_sizes"][0], files, file_list["out"])
    guest = json.loads((files / "patch-result.json").read_bytes())
    require(guest == {"schema": 1, "helper_sha256": expected, "unmounted": True,
                      "readonly_fsck": True}, "ramdisk embedding receipt mismatch")
    require(image.stat().st_size == source.stat().st_size and sha256(image) != BASELINE_PINS[source],
            "embedded replay ramdisk has unexpected identity")
    return image


def do_replay(probe, helper_sha, prep, child, console, qmp, run, result, deadline, fixture):
    probe.check_fixture_attachment(qmp, fixture)
    select = (
        "d=; for p in /dev/rdisk{0,1,2,3}; do "
        'if [[ -c $p ]]; then [[ -z $d ]] || exit 65; d=$p; fi; done; [[ -n $d ]] || exit 66; '
    )
    script = (select + f'a=$(/bin/sha256sum {CANDIDATE}) && '
              f'[[ "${{a%% *}}" == \'{helper_sha}\' ]] && {CANDIDATE} "$d"')
    lines = probe.guest_step(prep, child, console, run, deadline, script, "disposable replay only")
    require(lines.count(REPLAY_MARKER) == 1, "missing unique replay-only success")
    probe.check_fixture_attachment(qmp, fixture)
    result["guest_helper"]["replay_only_exercised"] = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", required=True)
    for flag in ("metadata", "archive", "helper", "inspector"):
        parser.add_argument(f"--{flag}-sha256", required=True)
    args = parser.parse_args()
    require(os.geteuid() == 0 and sys.flags.isolated and sys.dont_write_bytecode,
            "run as root with Python -I -B")
    require(all(re.fullmatch(r"[0-9a-f]{64}", digest) for name, digest in vars(args).items()
                if name.endswith("_sha256")), "supply the four pinned input hashes")

    probe = load_bound(OLD_PROBE, BASELINE_PINS[OLD_PROBE], "pinned_rd_probe", replay_status_only)
    inspector = load_bound(INPUT / "qualify_macos_hfs_replay.py", args.inspector_sha256, "hfsx_fixture_layout")
    lock = os.open(probe.PREP / "owner.lock", os.O_RDONLY | os.O_NOFOLLOW)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for path, digest in BASELINE_PINS.items():
            probe.file_pin(path, digest)
        assets = probe.check_inputs()
        prep, qualified = probe.preparation()
        prep.require_memory(probe.RAM_MIB)
        require(shutil.disk_usage(BASE).free >= 4_500_000_000, "insufficient free scratch storage")
        metadata = json.loads(probe.file_pin(INPUT / "fixture.json", args.metadata_sha256, body=True))
        require(metadata["bytes"] == IMAGE_BYTES and re.fullmatch(r"[0-9a-f]{64}", metadata["sha256"]),
                "invalid synthetic fixture metadata")
        binary = probe.file_pin(INPUT / "replay-fixture-ios", args.helper_sha256, body=True)
        require(0 < len(binary) <= 64 << 10 and binary[:4] == b"\xcf\xfa\xed\xfe",
                "unexpected unsigned Mach-O")
        require(not WORK.exists() and not WORK.is_symlink(), "boot work directory already used")
        STAGE.mkdir(mode=0o700)
        fixture = STAGE / "synthetic-disposable.hfs"
        expand_fixture(probe, metadata, args.archive_sha256, fixture)
        before, witness, attributes, expected = read_fixture(inspector, fixture, metadata)
        require(list(before) == metadata["pending_before"] and before[0] < before[1] and
                witness == b"BAD!asft" + expected[8:] and not attributes & inspector.UNMOUNTED,
                "synthetic input does not contain the expected pending update")

        WORK.mkdir(mode=0o700)
        old = json.loads((OLD_RUN / "cache-result.json").read_bytes())["helper"]
        old_signed = probe.file_pin(OLD_RUN / probe.HELPER_NAME, old["sha256"], body=True)
        with (WORK / probe.HELPER_NAME).open("xb") as stream:
            stream.write(old_signed)
        signed = STAGE / "asoft-replay-fixture"
        with signed.open("xb") as stream:
            stream.write(binary)
        signer = probe.load_source(probe.TOOLS / "adhoc_sign.py")
        cdhash = bytes.fromhex(signer.sign(signed, "com.asoft.replay-fixture"))
        helper_sha = sha256(signed)
        require(signed.stat().st_size <= 64 << 10, "signed helper too large")
        entries = probe.load_source(probe.TOOLS / "mktc.py")
        old_cache = (OLD_RUN / "ramdisk.tc").read_bytes()
        items = entries.read_tc(old_cache)
        require(len(cdhash) == 20 and cdhash not in items and
                items[bytes.fromhex(old["cdhash"])] == (2, 0, 0), "unexpected trust cache binding")
        items[cdhash] = (2, 0, 0)
        new_cache = struct.pack("<I16sI", 1, b"R" * 16, len(items))
        new_cache += b"".join(key + bytes(items[key][:2]) for key in sorted(items))
        require(entries.read_tc(new_cache) == items, "replay cache round-trip failed")
        cache = WORK / "ramdisk.tc"
        with cache.open("xb") as stream:
            stream.write(new_cache)
        image = embed_helper(probe, prep, signed, helper_sha)
        image_sha = sha256(image)
        receipt = {
            "image": {"path": str(image), "sha256": image_sha, "bytes": image.stat().st_size},
            "fixture": {"path": str(fixture), "sha256": metadata["sha256"], "bytes": IMAGE_BYTES},
            "guest": {"sha256": old["sha256"]},
        }
        prep.atomic_json(STAGE / "prepared.json", receipt)
        prepared_sha = sha256(STAGE / "prepared.json")

        def fixture_inputs(expected_sha):
            probe.file_pin(STAGE / "prepared.json", expected_sha)
            probe.file_pin(image, image_sha)
            probe.file_pin(fixture, metadata["sha256"])
            return receipt, {"image": image, "fixture": fixture}

        probe.fixture_inputs = fixture_inputs
        probe.exercise_unmount = lambda *values: do_replay(probe, helper_sha, *values)
        result = probe.run_probe(prep, qualified, assets, WORK, cache, sha256(cache),
                                 BASELINE_PINS[OLD_PROBE], old, prepared_sha)

        copy = WORK / "run/disposable.hfs"
        after, updated, after_attributes, _ = read_fixture(inspector, copy, metadata)
        for path, digest in BASELINE_PINS.items():
            probe.file_pin(path, digest)
        probe.file_pin(fixture, metadata["sha256"])
        good = (result["status"] == PROBE_STATUS and
                result["guest_helper"].get("replay_only_exercised") is True and
                after == (before[1], before[1]) and updated == expected)
        report = {
            "status": "PIXEL_DISPOSABLE_REPLAY_PASSED" if good else "INCOMPLETE",
            "guest_status": result["status"],
            "guest_error": result.get("error"),
            "native_witnesses": result.get("native_witnesses"),
            "journal_before": list(before), "journal_after": list(after),
            "finder_info_persisted": updated == expected,
            "unmounted_bit_after": bool(after_attributes & inspector.UNMOUNTED),
            "fixture_source_hash_verified": True,
            "saved_data_attached": False,
        }
        prep.atomic_json(WORK / "verification.json", report)
        print(json.dumps(report, sort_keys=True), flush=True)
        return 0 if good else 2
    finally:
        os.close(lock)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(2))
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"status": "REFUSED", "error": f"{type(error).__name__}: {error}"}), flush=True)
        raise SystemExit(2)
