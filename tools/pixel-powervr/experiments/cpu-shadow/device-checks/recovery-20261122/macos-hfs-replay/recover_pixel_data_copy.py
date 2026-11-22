#!/usr/bin/env python3
"""Recover Resume5 Data on a new qcow2 descendant and verify the partition boundary."""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile

BASE = Path("/data/local/tmp")
PREP = BASE / "pixel-prep-e9cc754"
SOURCE = PREP / "attempts/07-0004/files/root26g.qcow2"
PARENT = PREP / "attempts/06-0001/files/root26g.qcow2"
QEMU = BASE / "pixel-tools-1528a782/tools/qemu-img"
EXTRACTS = BASE / "pixel-gpu-transfer-sxtv33sh/ios26-data-journal-diagnostic-resume5"
DATA_START = 34360786944
DATA_SIZE = 16 << 30
CHUNK = 1 << 20
PINS = {
    QEMU: "1bd2fd6b968c492d0263436c260af2a8c2ee807cf4afd4fd2abb3300446e2440",
    SOURCE: "36a910108a8e1d462ffaf96e4f76dd8dceda439d5c24330695ed085538651250",
    PARENT: "49a453b3a3c6b6b2a204a80e10381480972d5484789595756dea2118d7004f99",
    EXTRACTS / "result.json":
        "6d1829c3a1a4982e4cdcf11a6854fb862f93a12d5025a783331d4a578de28efc",
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha256(path):
    require(path.resolve(strict=True) == path, "unexpected symlink in recovery input")
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
                "expected one ordinary recovery input")
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
        after = os.fstat(stream.fileno())
        require((before.st_ino, before.st_size, before.st_mtime_ns) ==
                (after.st_ino, after.st_size, after.st_mtime_ns),
                "recovery input changed while hashing")
        return digest


def check_originals():
    for path, digest in PINS.items():
        require(sha256(path) == digest, f"preservation hash differs for {path.name}")


def run(*arguments, timeout=600):
    result = subprocess.run([str(QEMU), *map(str, arguments)], check=True,
                            capture_output=True, text=True, timeout=timeout)
    return result.stdout


def options(path, offset, size):
    return (f"driver=raw,offset={offset},size={size},file.driver=qcow2,"
            f"file.file.driver=file,file.file.filename={path}")


def identity(path):
    info = json.loads(run("info", "--output=json", path))
    require(info.get("format") == "qcow2" and
            info.get("full-backing-filename") == str(SOURCE) and
            info.get("virtual-size", 0) >= DATA_START + DATA_SIZE,
            "unexpected new overlay backing file or size")
    return info


def write_receipt(path, data):
    with path.open("x", encoding="utf8") as stream:
        json.dump(data, stream, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps(data, sort_keys=True), flush=True)


def prepare(work):
    require(shutil.disk_usage(BASE).free >= 54 << 30,
            "insufficient phone storage for three detached working copies")
    check_originals()
    work.mkdir(mode=0o700)
    overlay = work / "recovered.qcow2"
    run("create", "-f", "qcow2", "-F", "qcow2", "-b", SOURCE, overlay)
    identity(overlay)
    before = work / "pending-data.raw"
    run("convert", "--image-opts", "-O", "raw", options(overlay, DATA_START, DATA_SIZE), before)
    require(before.stat().st_size == DATA_SIZE, "Data export size differs")
    reference = json.loads((EXTRACTS / "result.json").read_bytes())
    with before.open("rb") as source:
        for item in reference["retained_reads"]:
            source.seek(item["virtual_offset"] - DATA_START)
            data = source.read(item["bytes"])
            require(len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"],
                    f"snapshot differs from the retained {item['label']} extract")
    check_originals()
    write_receipt(work / "prepared.json", {
        "status": "DATA_COPY_PREPARED", "source_sha256": PINS[SOURCE],
        "pending_data_sha256": sha256(before), "new_overlay_sha256": sha256(overlay),
    })


def verify_data_bytes(work, overlay, recovered):
    blocks_per_read = 256
    with tempfile.TemporaryDirectory(dir=work, prefix="direct-data-read-") as scratch:
        chunk_path = Path(scratch) / "data.raw"
        with recovered.open("rb") as expected:
            for block in range(0, DATA_SIZE // CHUNK, blocks_per_read):
                blocks = min(blocks_per_read, DATA_SIZE // CHUNK - block)
                first = DATA_START // CHUNK + block
                run("dd", "-f", "qcow2", "-O", "raw", f"bs={CHUNK}",
                    f"skip={first}", f"count={first + blocks}",
                    f"if={overlay}", f"of={chunk_path}")
                require(chunk_path.stat().st_size == blocks * CHUNK, "short overlay readback")
                with chunk_path.open("rb") as observed:
                    for index in range(blocks):
                        reference = expected.read(CHUNK)
                        require(len(reference) == CHUNK and observed.read(CHUNK) == reference,
                                f"overlay Data differs at offset {(block + index) * CHUNK}")
                chunk_path.unlink()


def publish(work, check_path, verify_existing):
    check_originals()
    before = work / "pending-data.raw"
    after = work / "recovered-data.raw"
    overlay = work / "recovered.qcow2"
    require(not (work / "manifest.json").exists(), "recovery already published")
    identity(overlay)
    first = json.loads((work / "prepared.json").read_bytes())
    check = json.loads(check_path.read_bytes())
    before_sha, after_sha = sha256(before), sha256(after)
    require(first["status"] == "DATA_COPY_PREPARED" and first["source_sha256"] == PINS[SOURCE] and
            before_sha == first["pending_data_sha256"] and before_sha != after_sha,
            "unexpected recovery input identity")
    overlay_sha = sha256(overlay)
    require((overlay_sha != first["new_overlay_sha256"]) == verify_existing,
            "unexpected overlay modification state")
    require(check["status"] == "READ_ONLY_HFS_CHECK_PASSED" and check["input_sha256_reverified"] == after_sha,
            "recovered Data hasn't passed the independent pinned checker")
    require(before.stat().st_size == after.stat().st_size == DATA_SIZE, "invalid Data volume size")
    patches = []
    with before.open("rb") as old, after.open("rb") as new:
        for offset in range(0, DATA_SIZE, CHUNK):
            a, b = old.read(CHUNK), new.read(CHUNK)
            require(len(a) == len(b) == CHUNK, "short read while evaluating Data changes")
            if a != b:
                patches.append(offset)
                require(len(patches) <= 128, "too many changed recovery regions")
    require(patches, "recovery made no changes")
    with after.open("rb") as volume:
        for offset in patches:
            volume.seek(offset)
            data = volume.read(CHUNK)
            segment = work / f"patch-{offset:010x}.raw"
            if verify_existing:
                require(segment.read_bytes() == data, "existing patch differs from recovered Data")
            else:
                with segment.open("xb") as output:
                    output.write(data)
                run("convert", "-n", "-f", "raw", "--target-image-opts",
                    segment, options(overlay, DATA_START + offset, CHUNK))
    verify_data_bytes(work, overlay, after)
    identity(overlay)
    extents = json.loads(run("map", "--output=json", overlay))
    new_extents = [e for e in extents if e["depth"] == 0 and e.get("present", False)]
    require(new_extents and all(DATA_START <= e["start"] and
                e["start"] + e["length"] <= DATA_START + DATA_SIZE for e in new_extents),
            "new overlay allocated sectors outside Data")
    check_originals()
    require(sha256(after) == after_sha and sha256(before) == before_sha,
            "detached Data artifact changed during injection")
    write_receipt(work / "manifest.json", {
        "status": "RECOVERED_DATA_COPY_VERIFIED", "source_sha256": PINS[SOURCE],
        "recovered_data_sha256": after_sha, "new_overlay_sha256": sha256(overlay),
        "read_only_data_fsck_passed": True, "applied_1mib_regions": len(patches),
        "outside_data_allocations": 0, "direct_data_readback_bytes": DATA_SIZE,
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "publish", "verify"))
    parser.add_argument("work", type=Path)
    parser.add_argument("--check-receipt", type=Path)
    args = parser.parse_args()
    require(sys.flags.isolated and sys.dont_write_bytecode and os.geteuid() == 0,
            "run root Python -I -B")
    work = args.work
    require(work.parent == BASE and work == work.resolve() and
            re.fullmatch(r"asoft-data-copy-recovery-[a-z0-9]+", work.name),
            "select a fresh, canonical recovery work path")
    lock = os.open(PREP / "owner.lock", os.O_RDONLY | os.O_NOFOLLOW)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.mode == "prepare":
            require(args.check_receipt is None, "checker receipt belongs to publication")
            prepare(work)
        else:
            require(args.check_receipt is not None, "the independent checker receipt is required")
            publish(work, args.check_receipt, args.mode == "verify")
    finally:
        os.close(lock)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            print(error.stderr.strip(), file=sys.stderr)
        sys.exit(str(error))
