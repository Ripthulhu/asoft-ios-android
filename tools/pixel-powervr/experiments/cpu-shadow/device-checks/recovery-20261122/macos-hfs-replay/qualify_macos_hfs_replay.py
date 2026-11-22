#!/usr/bin/env python3
"""Exercise Apple's durable HFS+ journal replay on a newly generated image."""

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import struct
import subprocess
import sys
import tempfile

IMAGE_BYTES = 96 * 1024 * 1024
VOLUME_HEADER_OFFSET = 1024
UNMOUNTED = 0x100
JOURNALED = 0x2000
INCONSISTENT = 0x800
FINDER_INFO = "com.apple.FinderInfo"
BEFORE = b"BAD!asft" + bytes(24)
AFTER = b"GOODasft" + bytes(24)
SENTINEL = b"asoft disposable journal replay fixture\n"
JOURNAL_HEADER_SIZE = 48
DISK = re.compile(r"/dev/disk[0-9]+")


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, timeout=60).stdout


@contextmanager
def attach(image, readonly=False):
    require(image.resolve() == image and image.is_file(), "expected local fixture file")
    args = [
        "/usr/bin/hdiutil", "attach", "-nomount", "-noautofsck",
        "-imagekey", "diskimage-class=CRawDiskImage", "-plist",
    ]
    if readonly:
        args.append("-readonly")
    data = plistlib.loads(run(*args, str(image)))
    entities = data["system-entities"]
    whole_disks = [
        entry["dev-entry"] for entry in entities
        if DISK.fullmatch(entry.get("dev-entry", ""))
    ]
    require(len(whole_disks) == 1, "unexpected disk image attachment")
    disk = whole_disks[0]
    try:
        require(len(entities) == 1 and not entities[0].get("mount-point"),
                "expected a single unmounted whole disk")
        yield disk, disk.replace("/dev/disk", "/dev/rdisk", 1)
    finally:
        run("/usr/bin/hdiutil", "detach", disk)


@contextmanager
def mount(disk, path):
    require(not os.path.ismount(path) and not any(path.iterdir()),
            "expected an unused fixture mountpoint")
    run("/usr/bin/sudo", "-n", "/sbin/mount_hfs", "-o", "nobrowse,nosuid,nodev",
        disk, str(path))
    try:
        require(os.path.ismount(path), "the fixture did not mount")
        yield
    finally:
        run("/usr/bin/sudo", "-n", "/sbin/umount", str(path))
        require(not os.path.ismount(path), "the fixture is still mounted")


def read_at(src, offset, size):
    require(0 <= offset <= IMAGE_BYTES - size, "read outside the fixture")
    src.seek(offset)
    data = src.read(size)
    require(len(data) == size, "short fixture read")
    return data


def write_at(src, offset, data):
    require(0 <= offset <= IMAGE_BYTES - len(data), "write outside the fixture")
    src.seek(offset)
    require(src.write(data) == len(data), "short fixture write")


def checksum(data):
    result = 0
    for value in data:
        result = ((result << 8) ^ (result + value)) & 0xFFFFFFFF
    return result ^ 0xFFFFFFFF


@dataclass(frozen=True)
class Layout:
    attributes: int
    allocation_bytes: int
    journal_offset: int
    journal_bytes: int
    catalog_offset: int
    catalog_bytes: int


def layout(src):
    require(os.fstat(src.fileno()).st_size == IMAGE_BYTES, "fixture size differs")
    header = read_at(src, VOLUME_HEADER_OFFSET, 512)
    require(header[:4] == b"H+\x00\x04", "expected a plain HFS+ fixture")
    attributes, version, jib_block = struct.unpack_from(">I4sI", header, 4)
    require(attributes & JOURNALED and not attributes & INCONSISTENT,
            "expected a journaled and consistent fixture")
    require(version == b"HFSJ", "fixture was not last mounted by journaled HFS+")
    allocation, blocks = struct.unpack_from(">II", header, 40)
    require(512 <= allocation <= 65536 and not allocation & (allocation - 1) and
            allocation * blocks == IMAGE_BYTES, "unexpected allocation geometry")
    jib_offset = jib_block * allocation
    jib = read_at(src, jib_offset, 52)
    flags, = struct.unpack_from(">I", jib)
    journal_offset, journal_bytes = struct.unpack_from(">QQ", jib, 36)
    require(flags & 7 == 1 and journal_offset > 0 and
            journal_bytes > 0 and journal_offset + journal_bytes <= IMAGE_BYTES and
            not (journal_offset < jib_offset + allocation and
                 jib_offset < journal_offset + journal_bytes),
            "expected an initialized internal journal")
    catalog_offset, catalog_blocks = struct.unpack_from(">II", header, 288)
    catalog_offset *= allocation
    catalog_bytes = catalog_blocks * allocation
    require(catalog_offset > 0 and catalog_bytes > 0 and
            catalog_offset + catalog_bytes <= IMAGE_BYTES and
            not (catalog_offset < journal_offset + journal_bytes and
                 journal_offset < catalog_offset + catalog_bytes),
            "expected a catalog extent outside the journal")
    return Layout(attributes, allocation, journal_offset, journal_bytes,
                  catalog_offset, catalog_bytes)


@dataclass(frozen=True)
class Journal:
    endian: str
    header: bytes
    start: int
    end: int
    list_bytes: int
    sector: int
    sequence: int


def journal(src, volume):
    raw = read_at(src, volume.journal_offset, JOURNAL_HEADER_SIZE)
    endian = "<" if raw[:4] == b"xLNJ" else ">"
    fields = struct.unpack(endian + "IIQQQIIII", raw)
    magic, order, start, end, size, list_bytes, saved_checksum, sector, sequence = fields
    require(magic == 0x4A4E4C78 and order == 0x12345678 and size == volume.journal_bytes,
            "unexpected journal format")
    require(sector in (512, 4096) and sector <= list_bytes <= size // 2 and
            list_bytes % sector == 0 and sector <= start <= size and
            sector <= end <= size and start % sector == 0 and end % sector == 0,
            "unexpected journal geometry")
    header = read_at(src, volume.journal_offset, sector)
    require(header[:36] + bytes(4) + header[40:44] == raw[:36] + bytes(4) + raw[40:44] and
            checksum(raw[:36] + bytes(4) + raw[40:44]) == saved_checksum,
            "journal header checksum failed")
    return Journal(endian, header, start, end, list_bytes, sector, sequence)


def make_pending_transaction(image):
    with image.open("r+b") as src:
        volume = layout(src)
        active = journal(src, volume)
        require(volume.attributes & UNMOUNTED and active.start == active.end,
                "fixture must be clean before injection")
        require(volume.allocation_bytes % active.sector == 0 and
                volume.catalog_offset % active.sector == 0,
                "catalog bytes are misaligned")
        catalog = read_at(src, volume.catalog_offset, volume.catalog_bytes)
        marker = catalog.find(AFTER)
        require(marker >= 0 and catalog.find(AFTER, marker + 1) == -1 and BEFORE not in catalog,
                "expected exactly one FinderInfo witness in the catalog extent")
        node_bytes, = struct.unpack_from(">H", catalog, 32)
        require(active.sector <= node_bytes <= 32768 and node_bytes % active.sector == 0,
                "unexpected catalog node size")
        target = volume.catalog_offset + marker // node_bytes * node_bytes
        marker_offset = marker % node_bytes
        require(marker >= node_bytes and marker_offset + len(AFTER) <= node_bytes and
                target + node_bytes <= volume.catalog_offset + volume.catalog_bytes,
                "witness lies outside a complete catalog data node")

        block = read_at(src, target, node_bytes)
        dirty_block = block[:marker_offset] + BEFORE + block[marker_offset + len(AFTER):]
        start = active.sector
        end = start + active.list_bytes + len(block)
        require(end + active.list_bytes <= volume.journal_bytes,
                "fixture transaction must fit without wrapping")
        sequence = (active.sequence + 1) & 0xFFFFFFFF or 1
        block_list = bytearray(active.list_bytes)
        max_blocks = min((active.list_bytes - 16) // 16, volume.journal_bytes // active.sector)
        struct.pack_into(active.endian + "HHIIIQII", block_list, 0,
                         max_blocks, 2, active.list_bytes + len(block), 0, 3, 0, 0, sequence)
        list_checksum = checksum(block_list[:32])
        struct.pack_into(active.endian + "I", block_list, 8, list_checksum)
        struct.pack_into(active.endian + "QII", block_list, 32,
                         target // active.sector, len(block), checksum(block))

        header = bytearray(active.header)
        struct.pack_into(active.endian + "QQ", header, 8, start, end)
        struct.pack_into(active.endian + "III", header, 36, 0, active.sector, sequence)
        struct.pack_into(active.endian + "I", header, 36, checksum(header[:44]))

        # This is a synthetic fixture, with an empty block at the recorded end.
        write_at(src, volume.journal_offset + start, block_list + block + bytes(active.list_bytes))
        write_at(src, volume.journal_offset, header)
        write_at(src, target, dirty_block)
        write_at(src, VOLUME_HEADER_OFFSET + 4, struct.pack(">I", volume.attributes & ~UNMOUNTED))
        src.flush()
        os.fsync(src.fileno())
        require(read_at(src, target + marker_offset, len(BEFORE)) == BEFORE,
                "pre-mount FinderInfo witness differs")
        pending = journal(src, volume)
        require((pending.start, pending.end) == (start, end), "fixture journal did not persist")
    return start, end, target + marker_offset


def sha256(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def main():
    require(sys.platform == "darwin", "this probe requires native macOS")
    require(len(sys.argv) == 1, "this probe creates its own fixture and accepts no paths")
    with tempfile.TemporaryDirectory(prefix="asoft-hfs-replay-") as temp:
        root = Path(temp).resolve()
        image = root / "disposable.raw"
        mountpoint = root / "mount"
        mountpoint.mkdir()
        sentinel = root / "seed.txt"
        sentinel.write_bytes(SENTINEL)
        probe = mountpoint / "xattr-probe.txt"
        with image.open("xb") as output:
            output.truncate(IMAGE_BYTES)

        print("Creating stock journaled HFS+ fixture", flush=True)
        with attach(image) as (disk, raw):
            run("/usr/bin/sudo", "-n", "/sbin/newfs_hfs", "-J", "-v", "ASoftReplay", raw)
            with mount(disk, mountpoint):
                run("/usr/bin/sudo", "-n", "/bin/cp", str(sentinel), str(probe))
                run("/usr/bin/sudo", "-n", "/usr/bin/xattr", "-wx", FINDER_INFO,
                    AFTER.hex(), str(probe))

        start, end, marker_offset = make_pending_transaction(image)
        print(f"Pending on-disk journal {start}..{end}. Mounting disposable volume.", flush=True)
        with attach(image) as (disk, _):
            with mount(disk, mountpoint):
                actual = bytes.fromhex(run("/usr/bin/xattr", "-px", FINDER_INFO, str(probe)).decode())
                require(actual == AFTER, "native mount did not replay FinderInfo")
                require(probe.read_bytes() == SENTINEL, "sentinel contents differ")

        with image.open("rb") as src:
            volume = layout(src)
            committed = journal(src, volume)
            require(committed.start == committed.end, "journal is still pending after unmount")
            require(volume.attributes & UNMOUNTED, "volume is still marked mounted")
            require(read_at(src, marker_offset, len(AFTER)) == AFTER, "replayed bytes did not persist")

        before_fsck = sha256(image)
        with attach(image, readonly=True) as (_, raw):
            check = run("/usr/bin/sudo", "-n", "/sbin/fsck_hfs", "-fn", raw)
        require(sha256(image) == before_fsck, "read-only fsck changed the image")
        print(check.decode(errors="replace"), end="")
        print(json.dumps({
            "durable_replay": True,
            "native_mount_finder_info_verified": True,
            "pending_before": [start, end],
            "journal_after_unmount": [committed.start, committed.end],
            "read_only_fsck_passed": True,
            "replayed_bytes_persisted": True,
        }, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        sys.exit(f"{error}\n{error.stdout.decode(errors='replace')}\n"
                 f"{error.stderr.decode(errors='replace')}")
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        sys.exit(str(error))
