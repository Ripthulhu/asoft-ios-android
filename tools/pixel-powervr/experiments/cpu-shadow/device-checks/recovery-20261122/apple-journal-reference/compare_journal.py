#!/usr/bin/env python3
"""Compare Apple's fsck_hfs callback stream with the pinned Resume5 diagnostic."""

import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import sys

SECTOR_BYTES = 512
JOURNAL_BYTES = 8 * 1024 * 1024
JOURNAL_SHA = "0b33a53eac6f0b19b5f74a0b8e7f6109f5877a4778ce0827f37e92197d7a73db"
DIAGNOSTIC_SHA = "6d1829c3a1a4982e4cdcf11a6854fb862f93a12d5025a783331d4a578de28efc"
JOURNAL_HEADER = struct.Struct("<IIQQQIIII")
BLOCK_LIST = struct.Struct("<HHIII")
BLOCK_INFO = struct.Struct("<QII")
DEAD_BLOCK = (1 << 64) - 1


def checksum(data):
    state = 0
    for value in data:
        state = ((state << 8) ^ (state + value)) & 0xFFFFFFFF
    return state ^ 0xFFFFFFFF


def read_pinned(path, expected_size, expected_sha):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size != expected_size:
            raise ValueError(f"{path.name} is not the expected regular extract")
        data = source.read(expected_size + 1)
    if hashlib.sha256(data).hexdigest() != expected_sha:
        raise ValueError(f"{path.name} does not match its retained SHA-256")
    return data


def create_snapshot():
    # Termux may expose memfd_create through bionic only.
    if hasattr(os, "memfd_create"):
        return os.memfd_create("hfs-journal-extract", os.MFD_ALLOW_SEALING)
    memfd_create = ctypes.CDLL(None, use_errno=True).memfd_create
    memfd_create.argtypes = (ctypes.c_char_p, ctypes.c_uint)
    memfd_create.restype = ctypes.c_int
    mfd_cloexec = 0x0001
    mfd_allow_sealing = 0x0002
    fd = memfd_create(b"hfs-journal-extract", mfd_cloexec | mfd_allow_sealing)
    if fd == -1:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    return fd


def observe(binary, journal):
    """Pass a read-only, sealed copy of the bounded extract to the child."""
    if len(journal) != JOURNAL_BYTES:
        raise ValueError("unexpected extract length")
    snapshot = create_snapshot()
    with os.fdopen(snapshot, "wb") as sealed:
        sealed.write(journal)
        sealed.flush()
        seals = (
            fcntl.F_SEAL_SEAL | fcntl.F_SEAL_SHRINK |
            fcntl.F_SEAL_GROW | fcntl.F_SEAL_WRITE
        )
        fcntl.fcntl(sealed, fcntl.F_ADD_SEALS, seals)
        fd = os.open(f"/proc/self/fd/{snapshot}", os.O_RDONLY)
        try:
            identity = {}
            if os.geteuid() == 0:
                identity = {"user": 2000, "group": 2000, "extra_groups": ()}
            result = subprocess.run(
                [str(binary), str(fd)], pass_fds=(fd,), capture_output=True,
                check=False, text=True, timeout=15, **identity
            )
        finally:
            os.close(fd)
    if result.returncode != 0 or result.stderr:
        raise ValueError(f"Apple reader child status {result.returncode}")
    rows = []
    for line in result.stdout.splitlines():
        target, size, payload_checksum = line.split()
        rows.append((int(target), int(size), int(payload_checksum, 16)))
    return rows


def expected_active(journal, analysis):
    """Use the independently verified early diagnostic's active list bounds."""
    rows = []
    scope = analysis["scope"]
    for record in analysis["records"]:
        start = record["journal_offset"]
        entry = start + BLOCK_LIST.size + BLOCK_INFO.size
        cursor = start + scope["block_list_bytes"]
        end = start + record["bytes_used"]
        for _ in range(record["num_blocks"] - 1):
            target, size, recorded_checksum = BLOCK_INFO.unpack_from(journal, entry)
            if target != DEAD_BLOCK:
                computed = checksum(journal[cursor:cursor + size])
                if computed != recorded_checksum:
                    raise ValueError("active payload no longer matches its checksum")
                rows.append((target * SECTOR_BYTES, size, computed))
            entry += BLOCK_INFO.size
            cursor += size
        if cursor != end:
            raise ValueError("active list differs from the existing diagnostic")
    if len(rows) != analysis["counts"]["live_entries"]:
        raise ValueError("active callback count differs from the existing diagnostic")
    return rows


def synthetic_fixture(next_sequence):
    """Build one active list, with an optional list after the advertised end."""
    start = SECTOR_BYTES
    payload_size = SECTOR_BYTES
    list_bytes = SECTOR_BYTES + payload_size
    active_end = start + list_bytes
    image = bytearray(JOURNAL_BYTES)

    def put_block_list(at, target, sequence, fill):
        payload = bytes([fill]) * payload_size
        BLOCK_LIST.pack_into(image, at, 31, 2, list_bytes, 0, 3)
        BLOCK_INFO.pack_into(image, at + BLOCK_LIST.size, 0, 0, sequence)
        struct.pack_into("<I", image, at + 8, checksum(image[at:at + 32]))
        payload_checksum = checksum(payload)
        BLOCK_INFO.pack_into(
            image, at + BLOCK_LIST.size + BLOCK_INFO.size,
            target, payload_size, payload_checksum
        )
        image[at + SECTOR_BYTES:at + list_bytes] = payload
        return target * SECTOR_BYTES, payload_size, payload_checksum

    JOURNAL_HEADER.pack_into(
        image, 0, 0x4A4E4C78, 0x12345678, start, active_end, JOURNAL_BYTES,
        SECTOR_BYTES, 0, SECTOR_BYTES, 10
    )
    struct.pack_into("<I", image, 36, checksum(image[:44]))
    expected = [put_block_list(start, 100, 10, 0x12)]
    if next_sequence is not None:
        next_row = put_block_list(active_end, 101, next_sequence, 0xE7)
        if next_sequence == 11:
            expected.append(next_row)
    return image, expected


def main():
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: {Path(sys.argv[0]).name} BINARY DIAGNOSTIC_DIRECTORY")
    binary = Path(sys.argv[1]).resolve(strict=True)
    source = Path(sys.argv[2])

    checks = {}
    for label, next_sequence in (
        ("empty_at_end", None),
        ("consecutive_list_after_end", 11),
        ("stale_list_after_end", 8),
    ):
        fixture, expected = synthetic_fixture(next_sequence)
        if observe(binary, fixture) != expected:
            raise ValueError(f"synthetic fixture failed: {label}")
        checks[label] = True

    journal = read_pinned(source / "journal.bin", JOURNAL_BYTES, JOURNAL_SHA)
    diagnostic = read_pinned(source / "result.json", 13026, DIAGNOSTIC_SHA)
    analysis = json.loads(diagnostic)["analysis"]
    active = expected_active(journal, analysis)
    callbacks = observe(binary, journal)
    if callbacks[:len(active)] != active:
        raise ValueError("Apple callback stream differs within the active interval")
    read_pinned(source / "journal.bin", JOURNAL_BYTES, JOURNAL_SHA)
    read_pinned(source / "result.json", 13026, DIAGNOSTIC_SHA)
    print(json.dumps({
        "schema": 1,
        "apple_hfs_commit": "d1bac2f062e6e9c0dfcce302d9aacb10173d0eea",
        "journal_sha256": JOURNAL_SHA,
        "synthetic_checks_passed": checks,
        "active_lists_matched": len(analysis["records"]),
        "active_callbacks_matched_in_order": len(active),
        "active_payload_bytes_matched": sum(size for _, size, _ in active),
        "additional_callbacks_after_active_interval": len(callbacks) - len(active),
        "retained_extracts_match_after": True,
        "volume_attached": False,
        "filesystem_replayed": False,
    }, sort_keys=True, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error)) from None
