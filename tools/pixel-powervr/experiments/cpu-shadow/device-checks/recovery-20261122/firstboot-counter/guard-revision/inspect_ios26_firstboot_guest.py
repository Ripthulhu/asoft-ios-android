#!/usr/bin/env python3
"""Inspect saved firstboot journals and filesystems without mounts or replay.

The passed partition auditor supplies its byte-identical GPT/fsck/loop helpers.
Journal discovery itself is raw volume-header -> JIB -> journal-header reading.
Only metadata, digests, verdicts and full fsck diagnostics leave this guest.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import subprocess
import sys
import time
import types


BLOCK = 4096
SECTOR = 512
JOURNAL_BYTES = 8 << 20
MAGIC = 0x4A4E4C78
ENDIAN_MAGIC = 0x12345678
CHECKSUM_BYTES = 44  # Pinned SVerify1.c: offsetof(journal_header, sequence_num).


def sha(body):
    return hashlib.sha256(body).hexdigest()


def json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


class InspectionError(Exception):
    def __init__(self, code, metadata=None):
        self.code, self.metadata = code, metadata
        super().__init__(code)


def require(condition, code, metadata=None):
    if not condition:
        raise InspectionError(code, metadata)


def read_at(stream, offset, size):
    require(type(offset) is int and offset >= 0 and type(size) is int and 0 < size <= 1 << 20,
            "raw_read_bounds")
    stream.seek(offset)
    body = stream.read(size)
    require(len(body) == size, "short_raw_read")
    return body


def checksum(body):
    """TN1150 byte algorithm, with explicit uint32 overflow at every step."""
    require(len(body) >= CHECKSUM_BYTES, "short_journal_header")
    data = bytearray(body[:CHECKSUM_BYTES])
    data[36:40] = bytes(4)
    value = 0
    for byte in data:
        value = ((value << 8) ^ (value + byte)) & 0xFFFFFFFF
    return (~value) & 0xFFFFFFFF


def volume_headers(stream, base, size):
    """Both real headers must agree on the journal's discovery geometry."""
    headers = [read_at(stream, base + offset, SECTOR) for offset in (1024, size - 1024)]
    geometries = []
    for body in headers:
        signature, version, attributes, _, jib = struct.unpack_from(">HHIII", body)
        block, blocks = struct.unpack_from(">II", body, 40)
        require((signature, version, block, blocks) == (0x4858, 5, BLOCK, size // BLOCK),
                "unsupported_volume_geometry")
        require(attributes & (1 << 13) and not attributes & (1 << 11),
                "volume_not_journaled_or_inconsistent")
        require(0 < jib < blocks - 1, "jib_block_out_of_volume")
        geometries.append({"block_bytes": block, "blocks": blocks, "jib_block": jib,
                           "volume_id_sha256": sha(body[104:112])})
    require(geometries[0] == geometries[1], "volume_headers_disagree")
    return {"geometry": geometries[0], "primary_sha256": sha(headers[0]),
            "alternate_sha256": sha(headers[1]),
            "attributes": [struct.unpack_from(">I", b, 4)[0] for b in headers]}, headers


def no_metadata_overlap(headers, jib_offset, journal_offset, journal_size, volume_size):
    """Reject discovery pointers into inline allocation/metadata extents."""
    reserved = ((0, BLOCK), (volume_size - BLOCK, volume_size),
                (jib_offset, jib_offset + BLOCK))
    left, right = journal_offset, journal_offset + journal_size
    require(all(right <= a or left >= b for a, b in reserved), "journal_reserved_overlap")
    for header in headers:
        for fork in (112, 192, 272, 352, 432):
            logical, _, allocated = struct.unpack_from(">QII", header, fork)
            require(logical <= allocated * BLOCK and allocated < volume_size // BLOCK,
                    "metadata_fork_size")
            total = 0
            ended = False
            for index in range(8):
                start, count = struct.unpack_from(">II", header, fork + 16 + index * 8)
                if count == 0:
                    require(start == 0, "metadata_empty_extent")
                    ended = True
                    continue
                require(not ended and 0 < start < start + count <= volume_size // BLOCK - 1,
                        "metadata_extent_bounds")
                a, b = start * BLOCK, (start + count) * BLOCK
                require((b <= left or a >= right) and (b <= jib_offset or a >= jib_offset + BLOCK),
                        "metadata_journal_overlap")
                total += count
            require(total <= allocated, "metadata_extent_count")


def journal_info(stream, base, size, volume):
    offset = volume["geometry"]["jib_block"] * BLOCK
    body = read_at(stream, base + offset, BLOCK)
    flags = struct.unpack_from(">I", body)[0]
    journal_offset, journal_size = struct.unpack_from(">QQ", body, 36)
    require(flags in (1, 5), "unsupported_jib_flags")
    # This preparation uses the original in-volume, allocation-aligned journal.
    # Relocated/resized journals are left for separate classification.
    require(journal_size == JOURNAL_BYTES and journal_offset % BLOCK == 0 and
            BLOCK <= journal_offset < journal_offset + journal_size <= size - BLOCK,
            "unsupported_journal_range")
    return {"flags": flags, "jib_offset": offset, "offset": journal_offset,
            "bytes": journal_size, "jib_sha256": sha(body)}, body


def initialized_header(body, info):
    """Validate an empty initialized header before asking fsck any question."""
    require(len(body) == SECTOR, "journal_header_sector_size")
    if body[4:8] == b"\x12\x34\x56\x78":
        endian = ">"
    elif body[4:8] == b"\x78\x56\x34\x12":
        endian = "<"
    else:
        raise InspectionError("journal_endian_magic")
    magic, marker, start, end, size, block_header, stored, header = struct.unpack_from(endian + "IIQQQIII", body)
    metadata = {"endian": "big" if endian == ">" else "little", "magic": magic, "endian_marker": marker,
                "start": start, "end": end, "bytes": size, "block_header_bytes": block_header,
                "header_bytes": header, "checksum": stored, "computed_checksum": checksum(body),
                "checksum_bytes": CHECKSUM_BYTES, "header_sha256": sha(body)}
    require(magic == MAGIC and marker == ENDIAN_MAGIC, "journal_magic_or_mixed_endian", metadata)
    require(size == info["bytes"], "journal_header_size_mismatch", metadata)
    # The frozen QEMU virtio-blk-pci qcow2 backend exposes 512-byte sectors.
    require(header == SECTOR, "unsupported_journal_header_sector", metadata)
    # A block-list header has 16-byte header/entries, with a UInt16 count.
    # Sector alignment and representability are required; no 'typical' 4-16K
    # assumption is used. Unknown configurations are refused, never replayed.
    require(header <= block_header <= 0xFFFF * 16 and block_header % header == 0 and
            block_header <= size - header, "unsupported_journal_block_header", metadata)
    require(stored == metadata["computed_checksum"], "journal_header_checksum", metadata)
    # This deliberately supports only normalized circular-buffer positions.
    # A cursor at size is INCOMPLETE, not silently normalized to jhdr_size.
    require(header <= start < size and header <= end < size and
            start % header == 0 and end % header == 0, "unsupported_journal_cursor", metadata)
    require(start == end, "nonempty_journal", metadata)
    return {"status": "PASSED", "state": "INITIALIZED_EMPTY", "endian": "big" if endian == ">" else "little",
            "start": start, "end": end, "bytes": size, "block_header_bytes": block_header,
            "header_bytes": header, "checksum": stored, "checksum_bytes": CHECKSUM_BYTES,
            "header_sha256": sha(body), "inactive_payload_examined": False}


def authored_jib(volume_size):
    """Pinned newfs_hfs 540.1: bitmap, JIB, then the default 8MiB journal."""
    bitmap = (volume_size // BLOCK + 7) // 8
    require(bitmap % BLOCK == 0, "unsupported_formatter_bitmap")
    jib = 1 + bitmap // BLOCK
    body = bytearray(BLOCK)
    body[180:SECTOR] = b"\xdb" * (SECTOR - 180)
    struct.pack_into(">I", body, 0, 5)
    struct.pack_into(">QQ", body, 36, (jib + 1) * BLOCK, JOURNAL_BYTES)
    return jib, bytes(body)


def zero_region(stream, offset, size):
    digest = hashlib.sha256()
    for position in range(0, size, 1 << 20):
        body = read_at(stream, offset + position, min(1 << 20, size - position))
        require(not any(body), "needinit_journal_not_zero")
        digest.update(body)
    return digest.hexdigest()


def inspect_volume(current, baseline, base, size):
    volume, headers = volume_headers(current, base, size)
    previous, previous_headers = volume_headers(baseline, base, size)
    require(volume["geometry"] == previous["geometry"], "baseline_volume_geometry_changed")
    info, jib = journal_info(current, base, size, volume)
    original, original_jib = journal_info(baseline, base, size, previous)
    require({k: info[k] for k in ("jib_offset", "offset", "bytes")} ==
            {k: original[k] for k in ("jib_offset", "offset", "bytes")}, "baseline_journal_location_changed")
    no_metadata_overlap(headers, info["jib_offset"], info["offset"], info["bytes"], size)
    no_metadata_overlap(previous_headers, original["jib_offset"], original["offset"], original["bytes"], size)
    if info["flags"] == 1:
        verdict = initialized_header(read_at(current, base + info["offset"], SECTOR), info)
    else:
        block, expected = authored_jib(size)
        require(original["flags"] == 5 and volume["geometry"]["jib_block"] == block and
                jib == original_jib == expected, "needinit_not_exact_authored_jib")
        require(headers == previous_headers, "needinit_volume_headers_changed")
        current_zero = zero_region(current, base + info["offset"], info["bytes"])
        previous_zero = zero_region(baseline, base + original["offset"], original["bytes"])
        require(current_zero == previous_zero, "needinit_baseline_journal_changed")
        verdict = {"status": "PASSED", "state": "UNTOUCHED_AUTHORED_NEEDINIT",
                   "flags": 5, "journal_sha256": current_zero, "journal_bytes": info["bytes"],
                   "baseline_journal_sha256": previous_zero, "baseline_headers_identical": True,
                   "baseline_jib_identical": True, "journal_all_zero": True}
    return {"status": "PASSED", "volume": volume, "baseline_volume": previous,
            "journal_info": info, "journal": verdict}


def load_auditor(path, expected):
    body = Path(path).read_bytes()
    require(sha(body) == expected, "auditor_dependency_hash")
    module = types.ModuleType("bound_partition_auditor")
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def inspect_disks(auditor, device, predecessor, policy, out):
    result = {"schema": 1, "kind": "ios26_saved_firstboot_inspection", "status": "INCOMPLETE",
              "inspection_nonce": policy.get("inspection_nonce"), "policy_sha256": sha(json_bytes(policy)),
              "errors": [], "cleanup_errors": [], "fsck": {}, "journals": {},
              "readonly_attachments": False, "mounted": False, "replayed": False, "repaired": False,
              "boot_complete": False, "gpu_path_complete": False}
    started, loops = time.monotonic(), []
    try:
        require(policy.get("schema") == 1 and isinstance(policy.get("inspection_nonce"), str) and
                re.fullmatch(r"[0-9a-f]{32}", policy["inspection_nonce"]) is not None, "inspection_policy")
        paths = [str(Path(p).resolve(strict=True)) for p in (device, predecessor)]
        require(paths[0] != paths[1], "duplicate_attachment")
        for path in paths:
            require(re.fullmatch(r"/dev/vd[a-z]+", path) is not None and stat.S_ISBLK(os.stat(path).st_mode),
                    "unexpected_disk_device")
            require(auditor.command(["blockdev", "--getro", path]) == "1" and
                    int(auditor.command(["blockdev", "--getsize64", path])) == auditor.DISK_BYTES,
                    "attachment_not_readonly_exact")
            auditor.ensure_unmounted(path)
        result["readonly_attachments"] = True
        with open(paths[0], "rb", buffering=0) as current, open(paths[1], "rb", buffering=0) as baseline:
            result["gpt"] = auditor.verify_gpt(current, auditor.DISK_BYTES)
            result["baseline_gpt"] = auditor.verify_gpt(baseline, auditor.DISK_BYTES)
            require(result["gpt"] == result["baseline_gpt"], "baseline_gpt_changed")
            for start, sectors, name in auditor.PARTITIONS:
                try:
                    result["journals"][name] = inspect_volume(current, baseline, start * SECTOR, sectors * SECTOR)
                except InspectionError as error:
                    result["journals"][name] = {"status": "INCOMPLETE", "code": error.code,
                                              **({"metadata": error.metadata} if error.metadata else {})}
                    raise
            # Both raw journal gates run before either fsck; no permissive fsck
            # routine is allowed to decide whether journal replay is necessary.
            for index, (start, sectors, name) in enumerate(auditor.PARTITIONS):
                loop = auditor.command(auditor.loop_command(paths[0], start, sectors))
                require(re.fullmatch(r"/dev/loop[0-9]+", loop) is not None, "unexpected_loop_device")
                loops.append(loop)
                require(auditor.command(["blockdev", "--getro", loop]) == "1" and
                        int(auditor.command(["blockdev", "--getsize64", loop])) == sectors * SECTOR,
                        "loop_not_readonly_exact")
                auditor.ensure_unmounted(loop)
                log = out / ("fsck-system.txt" if index == 0 else "fsck-data.txt")
                try:
                    with log.open("xb") as stream:
                        checked = subprocess.run(["fsck.hfsplus", "-f", "-n", loop], stdin=subprocess.DEVNULL,
                            stdout=stream, stderr=subprocess.STDOUT, timeout=1200, check=False,
                            preexec_fn=auditor.fsck_output_bound)
                    require(log.stat().st_size <= 4 << 20, "fsck_log_limit")
                    result["fsck"][name] = auditor.fsck_verdict(checked.returncode, log.read_text(encoding="utf-8", errors="strict"))
                except subprocess.TimeoutExpired:
                    result["fsck"][name] = {"status": "INCOMPLETE", "reasons": ["timeout"]}
                auditor.ensure_unmounted(loop)
            require(set(result["fsck"]) == {"iOSRoot", "Data"} and
                    all(row["status"] == "PASSED" for row in result["fsck"].values()), "fsck_not_clean")
            require(auditor.verify_gpt(current, auditor.DISK_BYTES) == result["gpt"] and
                    auditor.verify_gpt(baseline, auditor.DISK_BYTES) == result["baseline_gpt"], "gpt_changed_during_check")
            for start, sectors, name in auditor.PARTITIONS:
                require(inspect_volume(current, baseline, start * SECTOR, sectors * SECTOR) == result["journals"][name],
                        "raw_journal_changed_during_check")
        result["raw_metadata_unchanged"] = True
        result["status"] = "SAVED_FIRSTBOOT_INSPECTION_PASSED"
    except (InspectionError, auditor.AuditError) as error:
        result["errors"].append({"code": error.code})
    except Exception as error:
        result["errors"].append({"code": "unexpected_exception", "type": type(error).__name__})
    finally:
        for loop in reversed(loops):
            try:
                auditor.ensure_unmounted(loop)
                auditor.command(["losetup", "--detach", loop])
            except Exception:
                result["cleanup_errors"].append("detach_loop")
        if result["cleanup_errors"]:
            result["status"] = "INCOMPLETE"
        result["elapsed_seconds"] = time.monotonic() - started
    return result


def main():
    device, predecessor, policy_path, auditor_path, output = sys.argv[1:]
    out = Path(output)
    out.mkdir(mode=0o700)
    try:
        policy = json.loads(Path(policy_path).read_text())
        auditor = load_auditor(auditor_path, policy["partition_guest_sha256"])
        result = inspect_disks(auditor, device, predecessor, policy, out)
    except Exception as error:
        result = {"schema": 1, "status": "INCOMPLETE", "errors": [{"code": "inspection_setup_failed", "type": type(error).__name__}]}
    (out / "result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    # Export classified failures through the helper's success-only tar channel;
    # the host independently requires the inspection pass and complete logs.
    print("SAVED_FIRSTBOOT_INSPECTION_RESULT " + result["status"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
