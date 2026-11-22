"""Offline refusals and owned-helper collection; no phone, mount, GPU or image."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import plistlib
import shutil
import stat
import struct
import sys
import tarfile
import tempfile
import types
import unittest
from unittest import mock
import uuid
import zlib

import audit_ios26_partition as host
import audit_ios26_partition_guest as guest
import prepare_ios26 as prep


CLEAN = """** /dev/loop0 (NO WRITE)
** Checking Journaled HFS Plus volume.
** Checking extents overflow file.
** Checking catalog file.
** Checking Catalog hierarchy.
** Checking volume bitmap.
** Checking volume information.
** The volume Data appears to be OK.
"""


class SparseDisk:
    """Only a few GPT sectors, never a 48 GiB allocation."""
    def __init__(self, mutate_entries=None):
        self.position = 0
        total = guest.DISK_BYTES // 512
        entries = bytearray(128 * 128)
        for i, (start, count, name) in enumerate(guest.PARTITIONS):
            struct.pack_into("<16s16sQQQ72s", entries, i * 128, guest.HFS_TYPE,
                             uuid.UUID(int=i + 2).bytes_le, start, start + count - 1, 0,
                             name.encode("utf-16le").ljust(72, b"\0"))
        if mutate_entries:
            mutate_entries(entries)
        mbr = bytearray(512)
        mbr[450] = 0xEE
        struct.pack_into("<II", mbr, 454, 1, total - 1)
        mbr[510:] = b"\x55\xaa"
        self.blocks = {0: bytes(mbr), 1024: bytes(entries), (total - 33) * 512: bytes(entries)}
        for here, other, array in ((1, total - 1, 2), (total - 1, 1, total - 33)):
            header = bytearray(512)
            struct.pack_into("<8sIIIIQQQQ16sQIII", header, 0, b"EFI PART", 0x10000, 92, 0, 0,
                             here, other, 34, total - 34, uuid.UUID(int=1).bytes_le,
                             array, 128, 128, zlib.crc32(entries) & 0xFFFFFFFF)
            struct.pack_into("<I", header, 16, zlib.crc32(header[:92]) & 0xFFFFFFFF)
            self.blocks[here * 512] = bytes(header)

    def seek(self, position):
        self.position = position

    def read(self, size):
        data = self.blocks[self.position]
        assert len(data) == size
        return data


class GptAndFsck(unittest.TestCase):
    def test_both_independent_gpt_copies(self):
        self.assertEqual(guest.verify_gpt(SparseDisk(), guest.DISK_BYTES)["status"], "PASSED")
        for where in (512, guest.DISK_BYTES - 512):
            with self.subTest(where=where):
                disk = SparseDisk()
                header = bytearray(disk.blocks[where])
                header[16] ^= 1
                disk.blocks[where] = bytes(header)
                with self.assertRaisesRegex(guest.AuditError, "gpt_header_crc"):
                    guest.verify_gpt(disk, guest.DISK_BYTES)

    def test_geometry_is_checked_even_with_valid_crcs(self):
        def wrong_offset(entries):
            struct.pack_into("<Q", entries, 32, 4096)
        with self.assertRaisesRegex(guest.AuditError, "gpt_partition_geometry"):
            guest.verify_gpt(SparseDisk(wrong_offset), guest.DISK_BYTES)
        with self.assertRaisesRegex(guest.AuditError, "disk_size"):
            guest.verify_gpt(SparseDisk(), guest.DISK_BYTES + 512)

    def test_backup_entries_crc_and_extra_partition(self):
        disk = SparseDisk()
        where = guest.DISK_BYTES - 33 * 512
        entries = bytearray(disk.blocks[where])
        entries[-1] ^= 1
        disk.blocks[where] = bytes(entries)
        with self.assertRaisesRegex(guest.AuditError, "gpt_entries_crc"):
            guest.verify_gpt(disk, guest.DISK_BYTES)
        with self.assertRaisesRegex(guest.AuditError, "gpt_extra_or_duplicate_partition"):
            guest.verify_gpt(SparseDisk(lambda b: b.__setitem__(256, 1)), guest.DISK_BYTES)

    def test_clean_requires_real_full_check_and_unfiltered_footer(self):
        self.assertEqual(guest.fsck_verdict(0, CLEAN)["status"], "PASSED")
        for rc, output in ((1, CLEAN), (0, "The volume Data appears to be OK.\n"),
                           (0, CLEAN.replace("** Checking catalog file.\n", "")),
                           (0, CLEAN + "Volume is journaled. No checking performed.\n"),
                           (0, CLEAN + "FILE SYSTEM WAS MODIFIED\n"),
                           (0, CLEAN + "Journal need to be replayed but volume is read-only\n"),
                           (0, "Non-empty journal:  start = 2048, end = 4096\n" + CLEAN),
                           (0, "Only read 512 bytes from journal (expected 1024)\n" + CLEAN),
                           (0, CLEAN + "The volume could not be verified completely.\n"),
                           (0, CLEAN + "Repairing volume.\n")):
            with self.subTest(rc=rc, suffix=output[-70:]):
                self.assertEqual(guest.fsck_verdict(rc, output)["status"], "INCOMPLETE")

    def test_loop_and_mount_never_request_writes_or_force(self):
        loop = guest.loop_command("/dev/vdc", 2048, 67_108_864)
        self.assertIn("--read-only", loop)
        self.assertEqual(loop[loop.index("--offset") + 1], "1048576")
        self.assertEqual(loop[loop.index("--sizelimit") + 1], "34359738368")
        mount = guest.mount_command("/dev/loop0", Path("/tmp/audit-root"))
        self.assertEqual(mount[mount.index("-o") + 1], "ro,nosuid,nodev,noexec")
        self.assertNotIn("force", ",".join(mount))


class AuthoredJournalVolume:
    """Independent literal formatter layout; reads never allocate a 16 GiB image."""
    def __init__(self):
        self.position = 0
        header = bytearray(512)
        struct.pack_into(">HHIII", header, 0, 0x4858, 5, 0x80002100, 0x482b4c78, 129)
        struct.pack_into(">II", header, 40, 4096, 4194304)
        struct.pack_into(">QIIII", header, 112, 524288, 524288, 128, 1, 128)
        for fork, start in ((192, 2178), (272, 2306), (352, 2434)):
            struct.pack_into(">QIIII", header, fork, 524288, 524288, 128, start, 128)
        self.headers = [header, bytearray(header)]
        self.info = bytearray(4096)
        self.info[0:4] = b"\x00\x00\x00\x05"
        self.info[36:44] = (532480).to_bytes(8, "big")
        self.info[44:52] = (8388608).to_bytes(8, "big")
        self.info[180:512] = b"\xdb" * 332
        self.catalog_header = bytearray(8192)
        struct.pack_into(">IIbBHH", self.catalog_header, 0, 0, 0, 1, 0, 3, 0)
        struct.pack_into(">HIIIIHHII", self.catalog_header, 14, 1, 1, 3, 1, 1, 8192, 516, 64, 62)
        self.catalog_header[14 + 37] = 0xBC
        self.catalog_header[248] = 0xC0
        for index, value in enumerate((14, 120, 248, 8184)):
            struct.pack_into(">H", self.catalog_header, 8192 - (index + 1) * 2, value)
        self.catalog_bodies = {}
        for name, cnid, size, start, count in ((".journal", 16, 8388608, 130, 2048),
                                              (".journal_info_block", 17, 4096, 129, 1)):
            body = bytearray(248)
            struct.pack_into(">HHI", body, 0, 2, 2, 0)
            struct.pack_into(">I", body, 8, cnid)
            struct.pack_into(">HI", body, 42, 0o100000, 1)
            struct.pack_into(">IIH", body, 48, 0x6A726E6C, 0x6866732B, 0x5000)
            struct.pack_into(">QIIII", body, 88, size, 0, count, start, count)
            self.catalog_bodies[name] = body
        self.leaf_override = None
        self.extra = []

    def leaf(self):
        if self.leaf_override is not None:
            return self.leaf_override
        rows = []
        for name, body in self.catalog_bodies.items():
            encoded = name.encode("utf-16be")
            rows.append(struct.pack(">HIH", 6 + len(encoded), 2, len(name)) + encoded + body)
        rows.append(struct.pack(">HIHH", 6, 16, 0, 4))
        result = bytearray(8192)
        struct.pack_into(">IIbBHH", result, 0, 0, 0, -1, 1, len(rows), 0)
        position = 14
        for index, row in enumerate(rows):
            struct.pack_into(">H", result, 8192 - (index + 1) * 2, position)
            result[position:position + len(row)] = row
            position += len(row)
        struct.pack_into(">H", result, 8192 - (len(rows) + 1) * 2, position)
        return result

    def seek(self, position):
        self.position = position

    def read(self, size):
        start = self.position
        self.position += size
        result = bytearray(size)
        for offset, data in [(1024, self.headers[0]), (17179869184 - 1024, self.headers[1]),
                             (528384, self.info), (2306 * 4096, self.catalog_header),
                             (2306 * 4096 + 8192, self.leaf()), *self.extra]:
            left, right = max(start, offset), min(start + size, offset + len(data))
            if left < right:
                result[left - start:right - start] = data[left - offset:right - offset]
        return bytes(result)


class JournalFile(io.BytesIO):
    def __init__(self, body, number):
        super().__init__(body)
        self.number = number

    def fileno(self):
        return self.number


class JournalFiles:
    def __init__(self, info):
        self.bodies = {".journal": bytes(8388608), ".journal_info_block": bytes(info)}

    def open(self, name):
        return JournalFile(self.bodies[name], 16 if name == ".journal" else 17)


class JournalClassification(unittest.TestCase):
    def setUp(self):
        self.volume = AuthoredJournalVolume()
        self.files = JournalFiles(self.volume.info)
        self.source = {}
        self.entries = {name: {"type": stat.S_IFREG, "uid": 0, "gid": 0, "mode": 0, "links": 1,
                               "ino": ino, "bytes": size, "blocks": size // 512}
                        for name, ino, size in ((".journal", 16, 8388608), (".journal_info_block", 17, 4096))}
        self.unit = 4096
        self.map_changes = {}

    def ioctl(self, fd, request, body):
        if request == 2:
            self.assertEqual(body, bytes(4))
            return struct.pack("=i", self.unit)
        self.assertEqual(request, 1)
        logical = struct.unpack("=i", body)[0]
        offset, size = (532480, 8388608) if fd == 16 else (528384, 4096)
        physical = offset // self.unit + logical if logical < size // self.unit else 0
        return struct.pack("=i", self.map_changes.get((fd, logical), physical))

    def check(self):
        with mock.patch.object(guest.fcntl, "ioctl", side_effect=self.ioctl):
            return guest.classify_data_journal(self.volume, self.files, self.source, self.entries)

    def assert_bad(self, code):
        with self.assertRaisesRegex(guest.AuditError, "^" + code + "$"):
            self.check()

    def test_exact_need_init_records_have_independent_raw_mounted_proof(self):
        result = self.check()
        self.assertEqual(result["status"], "PASSED")
        self.assertEqual(result["state"], "authored_uninitialized_need_init")
        self.assertEqual(result["jib_flags"], 5)
        self.assertEqual(result["files"][".journal"]["sha256"], hashlib.sha256(bytes(8388608)).hexdigest())
        self.assertEqual(result["files"][".journal_info_block"]["sha256"], hashlib.sha256(self.volume.info).hexdigest())
        self.assertEqual(result["files"][".journal"]["mapping"]["byte_offset"], 532480)
        self.assertFalse(result["initialized_journals_allowed"])

    def test_initialized_or_other_flag_combinations_are_not_a_name_exception(self):
        for flags in (0, 1, 2, 4, 7, 0x80000005):
            with self.subTest(flags=flags):
                struct.pack_into(">I", self.volume.info, 0, flags)
                self.assert_bad("initialized_journal_outside_pre_firstboot_scope" if flags == 1 else "journal_info_flags")

    def test_jib_reserved_bytes_and_both_padding_regions_are_exact(self):
        for where in (4, 35, 52, 179, 180, 511, 512, 4095):
            with self.subTest(where=where):
                self.volume.info[where] ^= 1
                self.assert_bad("journal_info_authored_bytes")
                self.volume.info[where] ^= 1

    def test_journal_pointer_bounds_overlap_and_alignment(self):
        for offset, size in ((0, 8388608), (528384, 8388608), (532481, 8388608), (532480, 0),
                             (532480, 8388609), (17179865088, 8388608), (0xfffffffffffff000, 4096)):
            with self.subTest(offset=offset, size=size):
                struct.pack_into(">QQ", self.volume.info, 36, offset, size)
                self.assert_bad("journal_info_bounds_or_overlap")

    def test_in_bounds_relocated_or_short_journal_is_not_authored(self):
        for offset, size in ((536576, 8388608), (532480, 8384512)):
            struct.pack_into(">QQ", self.volume.info, 36, offset, size)
            self.assert_bad("journal_info_linkage")

    def test_both_volume_headers_and_bitmap_linkage(self):
        for index, where, value, code in ((0, 0, b"H+", "journal_volume_geometry"),
                (1, 12, struct.pack(">I", 130), "journal_volume_geometry"),
                (0, 40, struct.pack(">I", 16384), "journal_volume_geometry"),
                (1, 128, struct.pack(">I", 2), "journal_bitmap_layout")):
            with self.subTest(index=index, where=where):
                old = bytes(self.volume.headers[index][where:where + len(value)])
                self.volume.headers[index][where:where + len(value)] = value
                self.assert_bad(code)
                self.volume.headers[index][where:where + len(value)] = old

    def test_unclean_locked_or_not_journaled_volume_refuses(self):
        for flags, code in ((0x80002000, "journal_volume_not_clean_unmounted"),
                (0x80002900, "journal_volume_not_clean_unmounted"),
                (0x8000a100, "journal_volume_not_clean_unmounted"),
                (0x80000100, "journal_volume_not_journaled")):
            struct.pack_into(">I", self.volume.headers[0], 4, flags)
            self.assert_bad(code)

    def test_metadata_extent_cannot_overlap_journal_or_escape_volume(self):
        for start, count, code in ((129, 1, "journal_metadata_overlap"),
                (130, 1, "journal_metadata_overlap"), (4194303, 2, "journal_metadata_extent_bounds")):
            struct.pack_into(">II", self.volume.headers[0], 192 + 16, start, count)
            self.assert_bad(code)

    def test_wrong_identity_type_owner_mode_links_allocation_or_size(self):
        for name in self.entries:
            for field, value in (("ino", 42), ("type", stat.S_IFLNK), ("uid", 501), ("gid", 501),
                                 ("mode", 0o600), ("links", 2), ("bytes", 8192), ("blocks", 0)):
                with self.subTest(name=name, field=field):
                    old = self.entries[name][field]
                    self.entries[name][field] = value
                    self.assert_bad("journal_entry_identity")
                    self.entries[name][field] = old

    def test_source_collision_and_missing_destination_refuse(self):
        for name in self.entries:
            self.source[name] = {"type": stat.S_IFREG}
            self.assert_bad("journal_source_name_collision")
            self.source.clear()
        row = self.entries.pop(".journal_info_block")
        self.assert_bad("journal_entry_missing")
        self.entries[".journal_info_block"] = row

    def test_raw_journal_first_middle_and_last_bytes_must_be_zero(self):
        for where in (532480, 532480 + 4194304, 532480 + 8388608 - 1):
            self.volume.extra = [(where, b"x")]
            self.assert_bad("journal_uninitialized_nonzero")

    def test_mounted_bytes_cannot_disagree_with_valid_raw_metadata(self):
        self.files.bodies[".journal_info_block"] = bytes(4096)
        self.assert_bad("journal_raw_mounted_mismatch")
        self.files.bodies[".journal_info_block"] = bytes(self.volume.info)
        self.files.bodies[".journal"] = bytes(8388607) + b"x"
        self.assert_bad("journal_uninitialized_nonzero")
        self.files.bodies[".journal"] = bytes(8388607)
        self.assert_bad("journal_short_read")

    def test_equal_zero_bytes_do_not_allow_wrong_raw_extent_mapping(self):
        for key, value in (((16, 0), 131), ((16, 1024), 0), ((17, 0), 130), ((16, 2048), 2178)):
            self.map_changes = {key: value}
            self.assert_bad("journal_mapping_mismatch")

    def test_raw_catalog_rejects_extra_allocated_blocks_even_with_same_logical_file(self):
        body = self.volume.catalog_bodies[".journal"]
        struct.pack_into(">I", body, 100, 2049)
        struct.pack_into(">II", body, 112, 3000, 1)
        self.assert_bad("journal_catalog_forks")

    def test_raw_catalog_rejects_nonempty_resource_fork(self):
        body = self.volume.catalog_bodies[".journal_info_block"]
        struct.pack_into(">QIIII", body, 168, 32, 0, 1, 3000, 1)
        self.assert_bad("journal_catalog_forks")

    def test_raw_catalog_identity_and_single_extent_are_independent_of_stat(self):
        body = self.volume.catalog_bodies[".journal"]
        for where, value, code in ((8, struct.pack(">I", 42), "journal_catalog_identity"),
                (32, struct.pack(">I", 501), "journal_catalog_identity"),
                (42, struct.pack(">H", 0o100600), "journal_catalog_identity"),
                (44, struct.pack(">I", 2), "journal_catalog_identity"),
                (104, struct.pack(">I", 131), "journal_catalog_forks")):
            old = bytes(body[where:where + len(value)])
            body[where:where + len(value)] = value
            self.assert_bad(code)
            body[where:where + len(value)] = old

    def test_catalog_extent_overflow_and_unsupported_node_size_refuse(self):
        struct.pack_into(">I", self.volume.headers[0], 272 + 12, 129)
        self.assert_bad("journal_catalog_overflow_unsupported")
        struct.pack_into(">I", self.volume.headers[0], 272 + 12, 128)
        struct.pack_into(">H", self.volume.catalog_header, 14 + 18, 4096)
        self.assert_bad("journal_catalog_header_geometry")

    def test_catalog_leaf_and_record_bounds_are_checked(self):
        struct.pack_into(">I", self.volume.catalog_header, 14 + 10, 64)
        self.assert_bad("journal_catalog_header_geometry")
        struct.pack_into(">I", self.volume.catalog_header, 14 + 10, 1)
        leaf = self.volume.leaf()
        struct.pack_into(">H", leaf, 8190, 8191)
        self.volume.leaf_override = leaf
        self.assert_bad("journal_catalog_record_offsets")

    def test_catalog_cycle_and_nonbinary_key_order_refuse(self):
        leaf = self.volume.leaf()
        struct.pack_into(">I", leaf, 0, 1)
        struct.pack_into(">H", leaf, 10, 2)  # Only the two root entries; no later-parent stop.
        self.volume.leaf_override = leaf
        self.assert_bad("journal_catalog_leaf_chain")
        self.volume.leaf_override = None
        self.volume.catalog_header[14 + 37] = 0xCF
        self.assert_bad("journal_catalog_header_geometry")

    def test_catalog_missing_and_duplicate_names_are_not_accepted(self):
        body = self.volume.catalog_bodies.pop(".journal_info_block")
        self.assert_bad("journal_catalog_records_missing")
        self.volume.catalog_bodies[".journal_info_block"] = body
        leaf = self.volume.leaf()
        second = struct.unpack_from(">H", leaf, 8188)[0]
        # Corrupt the second key to repeat the first, preserving record offsets.
        leaf[second + 8:second + 8 + 16] = ".journal".encode("utf-16be")
        struct.pack_into(">H", leaf, second, 22)
        struct.pack_into(">H", leaf, second + 6, 8)
        self.volume.leaf_override = leaf
        self.assert_bad("journal_catalog_key_order")

    def test_mapping_units_are_not_the_guest_page_size_and_no_fallback(self):
        self.unit = 1024
        self.assertEqual(self.check()["status"], "PASSED")
        self.unit = 16384
        self.assert_bad("journal_mapping_block_size")
        with mock.patch.object(guest.fcntl, "ioctl", side_effect=OSError("unsupported")):
            with self.assertRaisesRegex(guest.AuditError, "journal_mapping_unavailable"):
                guest.classify_data_journal(self.volume, self.files, self.source, self.entries)


class VirtualOwners(guest.Tree):
    """Non-root host fixture: filesystem metadata except explicit UID/GID maps."""
    def __init__(self, root, owners=None):
        super().__init__(root)
        self.owners = owners or {}

    def inventory(self):
        result = super().inventory()
        for path, (uid, gid) in self.owners.items():
            if path in result:
                result[path].update(uid=uid, gid=gid)
        return result


class DataCopy(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.src, self.dst = self.root / "source", self.root / "data"
        self.src.mkdir()
        (self.src / "ordinary.bin").write_bytes(b"PRIVATE_FILE_BYTES_MUST_NOT_BE_REPORTED" * 10)
        (self.src / "same-content.bin").write_bytes((self.src / "ordinary.bin").read_bytes())
        os.link(self.src / "ordinary.bin", self.src / "linked.bin")
        (self.src / "absolute-link").symlink_to("/never/follow/guest/absolute/path")
        (self.src / "relative-link").symlink_to("ordinary.bin")
        self.pref = "mobile/Library/Preferences/com.apple.springboard.plist"
        self.write_plist(self.src / self.pref, {"PrivateUnrelatedValue": "DO_NOT_REPORT_THIS_VALUE", "ExistingBool": True})
        self.effective = "mobile/Library/UserConfigurationProfiles/EffectiveUserSettings.plist"
        self.write_plist(self.src / self.effective, {"restrictedValue": {"maxInactivity": {"value": 30, "extra": True}}, "untouched": 17})
        self.activation = "containers/Data/System/TEST-CONTAINER"
        self.write_plist(self.src / self.activation / ".com.apple.mobile_container_manager.metadata.plist",
                         {"MCMMetadataIdentifier": "com.apple.mobileactivationd", "Unchanged": b"opaque"})
        shutil.copytree(self.src, self.dst, symlinks=True)
        (self.dst / "linked.bin").unlink()
        os.link(self.dst / "ordinary.bin", self.dst / "linked.bin")
        self.source = VirtualOwners(self.src)
        changes, dirs, _ = guest.expected_changes(self.source, self.source.inventory(), ["authored.service"], "23G90", "26.6.2")
        self.owners = {}
        for path, spec in changes.items():
            self.write_plist(self.dst / path, spec["value"])
            os.chmod(self.dst / path, spec["owner_mode"][2])
            self.owners[path] = spec["owner_mode"][:2]
        for path, metadata in sorted(dirs.items(), key=lambda row: row[0].count("/")):
            (self.dst / path).mkdir(exist_ok=True, parents=True)
            os.chmod(self.dst / path, metadata[2])
            self.owners[path] = metadata[:2]
        self.destination = VirtualOwners(self.dst, self.owners)

    def tearDown(self):
        self.source.close()
        self.destination.close()
        self.temp.cleanup()

    @staticmethod
    def write_plist(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(plistlib.dumps(value, fmt=plistlib.FMT_BINARY))

    def check(self):
        return guest.compare_data(self.source, self.destination, ["authored.service"])

    def assert_bad(self, code):
        result = self.check()
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertIn(code, {row["code"] for row in result["errors"]})
        return result

    def test_exact_copy_and_authored_tweaks_metadata_only(self):
        result = self.check()
        self.assertEqual(result["status"], "PASSED")
        self.assertTrue(result["activation_applicable"])
        self.assertEqual(result["validated_tweak_files"], 11)
        self.assertNotIn("PRIVATE_FILE_BYTES", json.dumps(result))
        self.assertNotIn("DO_NOT_REPORT_THIS_VALUE", json.dumps(result))

    def test_same_size_same_time_content_change(self):
        path = self.dst / "same-content.bin"
        st = path.stat()
        path.write_bytes(b"x" * st.st_size)
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
        self.assert_bad("copied_file_digest")

    def test_missing_and_unexplained_data_entries(self):
        (self.dst / "same-content.bin").unlink()
        self.assert_bad("missing_data_entry")
        (self.dst / "mobile/Library/Preferences/not-authorized.bin").write_bytes(b"extra")
        self.assert_bad("unexpected_data_entry")

    def test_symlinks_are_compared_without_following(self):
        (self.dst / "absolute-link").unlink()
        (self.dst / "absolute-link").symlink_to("/another/never/read/path")
        self.assert_bad("copied_symlink_target")

    def test_split_and_merged_hardlink_groups(self):
        path = self.dst / "linked.bin"
        data = path.read_bytes()
        path.unlink()
        path.write_bytes(data)
        self.assert_bad("hardlink_equivalence")
        path.unlink()
        os.link(self.dst / "ordinary.bin", path)
        (self.dst / "same-content.bin").unlink()
        os.link(self.dst / "ordinary.bin", self.dst / "same-content.bin")
        self.assert_bad("hardlink_equivalence")

    def test_external_source_hardlink_does_not_change_within_tree_relationships(self):
        os.link(self.src / "ordinary.bin", self.root / "outside-copied-tree.bin")
        self.assertEqual((self.src / "ordinary.bin").stat().st_nlink, 3)
        self.assertEqual((self.dst / "ordinary.bin").stat().st_nlink, 2)
        self.assertEqual(self.check()["status"], "PASSED")

    def test_independent_authored_plist_contract(self):
        # Literal expectations from the pinned scripts, not expected_changes.
        expected = {
            "mobile/Library/Preferences/com.apple.migration.plist": {
                "LastSystemVersion": "23G90", "DMUserDataDisposition": {"SyntheticDidUpgrade": False, "buildVersion": "23G90"}},
            self.pref: {"PrivateUnrelatedValue": "DO_NOT_REPORT_THIS_VALUE", "ExistingBool": True,
                "BKNoWatchdogs": True, "SBMinimumLockscreenIdleTime": 60,
                "FBLaunchWatchdogExceptions": {"com.apple.purplebuddy": 100.0}, "MCForceShowCloudConfigurationUI": False},
            "mobile/Library/Preferences/com.apple.purplebuddy.plist": {
                "SetupDone": True, "SetupFinishedAllSteps": True, "SetupVersion": 11, "daemonizeNeedsToRun": False},
            "mobile/Library/Preferences/com.apple.purplebuddy.notbackedup.plist": {
                "ShouldRunDiagnosticsMiniBuddy": False, "ShouldRunHSA2MiniBuddy": False,
                "ShouldRunKeychainSyncMiniBuddy": False, "ShouldRunMesaMiniBuddy": False,
                "ShouldRunPaymentMiniBuddy": False, "ShouldRunStandardMiniBuddy": False, "SilentICDPUpgrade": False},
            "mobile/Library/Preferences/com.apple.managedconfiguration.notbackedup.plist": {
                "LockdownActivationIndicatesCloudConfigurationAvailable": False},
            "mobile/Library/Preferences/com.apple.Accessibility.plist": {"HomeButtonAssistantPreference": 2},
            "mobile/Library/UserConfigurationProfiles/UserSettings.plist": {"restrictedValue": {"maxInactivity": {"value": 300}}},
            self.effective: {"restrictedValue": {"maxInactivity": {"value": 300, "extra": True}}, "untouched": 17},
            "keybags/systembag.kb": {"KeyBagKeys": b"SWEET"},
            "db/com.apple.xpc.launchd/disabled.plist": {"authored.service": True},
            self.activation + "/Library/internal/data_ark.plist": {
                "-ActivationState": "Activated", "-BrickState": False, "-BuildVersion": "23G90", "-ProductVersion": "26.6.2",
                "-DataMigrationCompleted": True, "-PreSydroDataMigrationCompleted": True},
        }
        for path, literal in expected.items():
            with self.subTest(path=path):
                self.assertEqual(guest.typed(plistlib.loads((self.dst / path).read_bytes())), guest.typed(literal))
                root_owned = path.startswith(("keybags/", "db/"))
                self.assertEqual(self.owners[path], (0, 0) if root_owned else (501, 501))
                mode = 0o644 if "UserConfigurationProfiles/" in path or path.startswith("db/") else 0o600
                self.assertEqual(stat.S_IMODE((self.dst / path).stat().st_mode), mode)
        self.assertEqual(stat.S_IMODE((self.dst / "keybags").stat().st_mode), 0o700)

    def test_user_setting_replaces_only_exact_nested_dictionary(self):
        path = "mobile/Library/UserConfigurationProfiles/UserSettings.plist"
        self.write_plist(self.src / path, {"restrictedValue": {"maxInactivity": {"value": 60, "remove": True},
                                                                  "other": {"value": 7}}, "preserve": "source"})
        changes, _, _ = guest.expected_changes(self.source, self.source.inventory(), ["authored.service"], "23G90", "26.6.2")
        self.assertEqual(guest.typed(changes[path]["value"]), guest.typed({
            "restrictedValue": {"maxInactivity": {"value": 300}, "other": {"value": 7}}, "preserve": "source"}))

    def test_owner_and_mode_refusals(self):
        self.owners[self.pref] = (0, 0)
        self.assert_bad("tweaked_file_metadata")
        self.owners[self.pref] = (501, 501)
        os.chmod(self.dst / "same-content.bin", 0o777)
        self.assert_bad("copied_entry_metadata")

    def test_unrelated_plist_keys_and_strict_types(self):
        path = self.dst / self.pref
        data = plistlib.loads(path.read_bytes())
        data["PrivateUnrelatedValue"] = "ALTERED"
        self.write_plist(path, data)
        self.assert_bad("tweaked_plist_semantics")
        data["PrivateUnrelatedValue"] = "DO_NOT_REPORT_THIS_VALUE"
        data["BKNoWatchdogs"] = 1  # Equality with True must not be accepted.
        self.write_plist(path, data)
        self.assert_bad("tweaked_plist_semantics")
        self.assertNotEqual(guest.typed({"x": 300}), guest.typed({"x": 300.0}))

    def test_existing_malformed_source_is_not_an_empty_dictionary(self):
        (self.src / self.pref).write_bytes(b"invalid source plist")
        with self.assertRaisesRegex(guest.AuditError, "plist_parse_failed"):
            self.check()

    def test_missing_optional_existing_outputs_and_activation_copy(self):
        (self.dst / self.effective).unlink()
        self.assert_bad("missing_data_entry")
        shutil.rmtree(self.dst / self.activation)
        self.assert_bad("missing_data_entry")

    def test_no_activation_waiver_when_source_has_no_container(self):
        shutil.rmtree(self.src / self.activation)
        self.assert_bad("unexpected_data_entry")

    def test_no_directory_or_hfs_metadata_blanket_waiver(self):
        (self.dst / ".journal").write_bytes(b"unclassified")
        self.assert_bad("unexpected_data_entry")

    def test_validated_journals_do_not_waive_ordinary_copy_or_other_internal_entries(self):
        volume = AuthoredJournalVolume()
        for name, body in JournalFiles(volume.info).bodies.items():
            (self.dst / name).write_bytes(body)

        class MountedJournalMetadata(VirtualOwners):
            def inventory(inner):
                rows = super().inventory()
                for name, cnid in ((".journal", 16), (".journal_info_block", 17)):
                    rows[name].update(ino=cnid, uid=0, gid=0, mode=0)
                return rows

        self.destination.close()
        self.destination = MountedJournalMetadata(self.dst, self.owners)

        def mapping(fd, operation, body):
            if operation == 2:
                return struct.pack("=i", 4096)
            self.assertEqual(operation, 1)
            name = Path(os.readlink("/proc/self/fd/" + str(fd))).name
            start, count = (130, 2048) if name == ".journal" else (129, 1)
            logical = struct.unpack("=i", body)[0]
            return struct.pack("=i", start + logical if logical < count else 0)

        with mock.patch.object(guest.fcntl, "ioctl", side_effect=mapping):
            result = guest.compare_data(self.source, self.destination, ["authored.service"], data_volume=volume)
            self.assertEqual(result["status"], "PASSED")
            self.assertEqual(result["journal_metadata"]["status"], "PASSED")
            (self.dst / "same-content.bin").write_bytes(b"changed")
            (self.dst / ".journal.extra").write_bytes(b"unclassified")
            result = guest.compare_data(self.source, self.destination, ["authored.service"], data_volume=volume)
            self.assertEqual(result["status"], "INCOMPLETE")
            self.assertTrue({"copied_file_digest", "unexpected_data_entry"} <= {e["code"] for e in result["errors"]})

    def test_metadata_symlink_and_fd_rejection_cleanup(self):
        path = self.dst / self.pref
        path.unlink()
        path.symlink_to(self.src / self.pref)
        self.assert_bad("tweaked_file_metadata")
        before = len(list(Path("/proc/self/fd").iterdir()))
        with self.assertRaisesRegex(guest.AuditError, "not_regular"):
            self.destination.open("mobile")
        self.assertEqual(len(list(Path("/proc/self/fd").iterdir())), before)


class HostBoundaries(unittest.TestCase):
    def test_missing_arguments_have_no_side_effects(self):
        with mock.patch.object(host, "execute") as execute, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(host.main([]), 2)
        execute.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["status"], "INCOMPLETE")

    def test_frozen_source_mismatch_refuses_before_import(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in host.SOURCES:
                (root / name).write_text("raise AssertionError('must never import mismatched source')\n")
            with self.assertRaisesRegex(ValueError, "differs from preparation"):
                host.frozen_runner(root, {name: "0" * 64 for name in host.SOURCES})

    def test_frozen_sources_load_exact_dependencies_without_stale_modules(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            origin = Path(host.__file__).parent
            expected = {}
            for name in host.SOURCES:
                body = (origin / name).read_bytes()
                (root / name).write_bytes(body)
                expected[name] = hashlib.sha256(body).hexdigest()
            before = {name[:-3]: sys.modules.get(name[:-3]) for name in host.SOURCES}
            loaded = host.frozen_runner(root, expected)
            self.assertEqual(Path(loaded.__file__), root / "prepare_ios26.py")
            self.assertEqual(Path(loaded.cold.__file__), root / "cold_boot_ios26.py")
            self.assertEqual(len(loaded.cold.CASES), 17)
            self.assertTrue({"core", "core-no-argument-buffers"} <= loaded.cold.CASES)
            self.assertIsNot(loaded.cold, prep.cold)
            self.assertEqual(before, {name: sys.modules.get(name) for name in before})
            self.assertFalse((root / "__pycache__").exists())

    def state(self, root):
        source = Path(host.__file__).parent
        prep_work = root / "prep"
        prep_work.mkdir()
        (prep_work / "owner.lock").touch()
        fake_cold = types.SimpleNamespace(utc=prep.cold.utc, require_phone=mock.Mock(), subreaper=mock.Mock())
        fake = types.SimpleNamespace(cold=fake_cold, refuse_live_children=mock.Mock(), atomic_json=prep.atomic_json,
            digest=prep.digest, helper_command=prep.helper_command, safe_return_tar=prep.safe_return_tar,
            file_record=prep.file_record, vm_success=prep.vm_success, cleanup_signals=prep.cleanup_signals)
        return {"prep": fake, "guest": guest, "prep_work": prep_work, "work": root / "audit",
            "disk": prep_work / "root26g.qcow2", "public": {"session": {"schema": 1}},
            "bodies": {name: (source / name).read_bytes() for name in host.AUDIT_SOURCES},
            "policy": {"schema": 1, "trim_labels": ["authored.service"]},
            "plan": {"session": {"helper_ram_mib": 2048, "helper_vcpus": 4, "package": str(root / "package"),
                                  "tooling": str(root / "tools")}}}

    def successful_vm(self, state, attempt, argv, env):
        policy = json.loads((attempt / "expected-policy.json").read_text())
        report = {"schema": 1, "kind": "ios26_readonly_partition_audit", "status": "PARTITION_AUDIT_PASSED",
            "readonly_attachment": True, "errors": [], "cleanup_errors": [], "gpt": {"status": "PASSED", "disk_bytes": guest.DISK_BYTES},
            "system": {"status": "PASSED", "build": "23G90", "version": "26.6.2"},
            "data_copy": {"status": "PASSED", "errors": [], "checked_unchanged_files": 1,
                "journal_metadata": {"status": "PASSED", "state": "authored_uninitialized_need_init", "jib_flags": 5,
                    "initialized_journals_allowed": False, "files": {".journal": {}, ".journal_info_block": {}},
                    "catalog": {"status": "PASSED", "node_bytes": 8192, "extent_overflow_allowed": False,
                        "records": {".journal": {}, ".journal_info_block": {}}}}},
            "fsck": {name: guest.fsck_verdict(0, CLEAN) for name in ("iOSRoot", "Data")},
            "audit_nonce": policy["audit_nonce"], "policy_sha256": guest.digest(guest.json_bytes(policy))}
        files = {"audit/result.json": json.dumps(report).encode(), "audit/fsck-system.txt": CLEAN.encode(),
                 "audit/fsck-data.txt": CLEAN.encode()}
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for name, body in files.items():
                item = tarfile.TarInfo(name)
                item.size = len(body)
                archive.addfile(item, io.BytesIO(body))
        with (attempt / "out.raw").open("r+b") as stream:
            stream.write(data.getvalue())
        disk_drive = [arg for arg in argv if arg.startswith("file=" + str(state["disk"]) + ",")]
        self.assertEqual(len(disk_drive), 1)
        self.assertIn("readonly=on", disk_drive[0])
        self.assertEqual(env["ASOFT_NATIVE_EL0_REQUIRED"], "1")
        self.assertNotIn("ASOFT_NATIVE_EL0_TPIDRRO", env)
        return {"out_sizes": [len(data.getvalue())], "done_codes": [0], "natural_exit": True,
                "witnesses": {"native_initialization": True, "native_execution": True, "fatal_markers": []},
                "cleanup": {"exit_code": 0, "echild": True, "forced_qemu": False, "forced_descendants": False, "errors": []}}

    def test_owned_success_collects_real_tar_and_preserves_prep(self):
        with tempfile.TemporaryDirectory() as directory:
            state = self.state(Path(directory))
            before = {p.name: p.read_bytes() for p in state["prep_work"].iterdir()}
            state["prep"].supervise_vm = lambda plan, stage, attempt, argv, env, args: self.successful_vm(state, attempt, argv, env)
            with mock.patch.object(host, "unchanged_inputs") as unchanged:
                result = host.execute(state, host.parser().parse_args([]))
            self.assertEqual(result["status"], "PARTITION_AUDIT_PASSED")
            self.assertEqual(unchanged.call_count, 2)
            self.assertTrue((state["work"] / "a1/files/audit/fsck-system.txt").is_file())
            self.assertEqual(before, {p.name: p.read_bytes() for p in state["prep_work"].iterdir()})
            output = state["work"] / "a1/files/audit"
            report = json.loads((output / "result.json").read_text())
            journal = report["data_copy"]["journal_metadata"]
            catalog = journal.pop("catalog")
            (output / "result.json").write_text(json.dumps(report))
            policy = json.loads((state["work"] / "a1/expected-policy.json").read_text())
            with self.assertRaisesRegex(ValueError, "missing exact journal catalog-fork"):
                host.guest_pass(guest, output, policy)
            journal["catalog"] = catalog
            del report["data_copy"]["journal_metadata"]
            (output / "result.json").write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "missing exact pre-firstboot journal"):
                host.guest_pass(guest, output, policy)

    def test_changed_disk_after_success_cannot_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            state = self.state(Path(directory))
            state["prep"].supervise_vm = lambda plan, stage, attempt, argv, env, args: self.successful_vm(state, attempt, argv, env)
            with mock.patch.object(host, "unchanged_inputs", side_effect=[None, ValueError("disk changed")]):
                result = host.execute(state, host.parser().parse_args([]))
            self.assertEqual(result["status"], "INCOMPLETE")
            self.assertIn("disk changed", result["identity_error"])

    def test_vm_failure_still_records_full_final_identity_check(self):
        with tempfile.TemporaryDirectory() as directory:
            state = self.state(Path(directory))
            state["prep"].supervise_vm = mock.Mock(side_effect=RuntimeError("native completion missing"))
            with mock.patch.object(host, "unchanged_inputs") as unchanged:
                result = host.execute(state, host.parser().parse_args([]))
            self.assertEqual(result["status"], "INCOMPLETE")
            self.assertEqual(unchanged.call_args.args[1], True)
            self.assertTrue((state["work"] / "result.json").is_file())

    def test_lock_conflict_creates_no_audit_work(self):
        import fcntl
        with tempfile.TemporaryDirectory() as directory:
            state = self.state(Path(directory))
            with (state["prep_work"] / "owner.lock").open("rb") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaisesRegex(ValueError, "another running process"):
                    with host.own_audit(state):
                        self.fail("must not own conflicting preparation")
            self.assertFalse(state["work"].exists())


if __name__ == "__main__":
    unittest.main()
