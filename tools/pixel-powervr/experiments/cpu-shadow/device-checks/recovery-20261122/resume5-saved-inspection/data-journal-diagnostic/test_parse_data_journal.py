"""Synthetic-only mutation tests of the isolated Data journal structure parser."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import unittest
from unittest import mock


SOURCE = Path(__file__).with_name("parse_data_journal.py")
SPEC = importlib.util.spec_from_file_location("data_journal_probe", SOURCE)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)

JOURNAL = 8388608
START = 512
END = 614400
LIST = 49152
VOLUME = 17179869184


def fixture_checksum(body):
    # Independent fixture encoding: truncate both operands to C uint32 width.
    accumulator = 0
    modulus = 1 << 32
    for octet in body:
        shifted = (accumulator * 256) % modulus
        added = (accumulator + octet) % modulus
        accumulator = shifted ^ added
    return 0xFFFFFFFF ^ accumulator


def fix_header(body):
    struct.pack_into("<I", body, 36, 0)
    struct.pack_into("<I", body, 36, fixture_checksum(body[:44]))


def fix_list(body, offset=START):
    struct.pack_into("<I", body, offset + 8, 0)
    struct.pack_into("<I", body, offset + 8, fixture_checksum(body[offset:offset + 32]))


def fixture(records=None, *, journal_sequence=0x4C535453):
    """Produce full fixed-size synthetic bytes, filling only declared payloads.

    Record specs contain (flags, sequence, entries), entry=(target,size,fill).
    Last entry size=None consumes exactly the remaining declared active region.
    All input is synthetic and no fixture contains device content.
    """
    if records is None:
        records = [(3, 100, [(80, None, 0x41)])]
    body = bytearray(JOURNAL)
    struct.pack_into("<IIQQQiIiI", body, 0, 0x4A4E4C78, 0x12345678,
                     START, END, JOURNAL, LIST, 0, 512, journal_sequence)
    fix_header(body)
    offsets = []
    cursor = START
    for record_no, (flags, sequence, entries) in enumerate(records):
        offsets.append(cursor)
        header = bytearray(bytes([0x5A]) * LIST)
        payloads = []
        for entry_no, (target, size, fill) in enumerate(entries, 1):
            if size is None:
                assert record_no == len(records) - 1 and entry_no == len(entries)
                size = END - cursor - LIST - sum(map(len, payloads))
            payload = bytes([fill]) * size
            payloads.append(payload)
            value = fixture_checksum(payload) if target != -1 else 0
            assert value != 0 or target == -1
            struct.pack_into("<qiI", header, 16 + 16 * entry_no, target, size, value)
        used = LIST + sum(map(len, payloads))
        struct.pack_into("<HHiIi", header, 0, 3071, len(entries) + 1, used, 0, flags)
        # Nonzero opaque pointer is intentional. It must never be followed or
        # exported; the size remains0 and sequence occupies the final uint32.
        struct.pack_into("<QiI", header, 16, 0x1122334455667788, 0, sequence)
        struct.pack_into("<I", header, 8, fixture_checksum(header[:32]))
        body[cursor:cursor + LIST] = header
        payload = b"".join(payloads)
        body[cursor + LIST:cursor + used] = payload
        cursor += used
    assert cursor == END
    return body, offsets


def analyze(body, *, digest=None, volume_bytes=VOLUME):
    raw = bytes(body)
    return probe.analyze_journal(
        raw, volume_bytes=volume_bytes,
        expected_header_sha256=digest or hashlib.sha256(raw[:512]).hexdigest())


class JournalStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.one, _ = fixture()
        cls.multi, cls.offsets = fixture([
            (3, 100, [(80, 512, 0x21), (-1, 512, 0xEE)]),
            (1, 100, [(81, 1024, 0x22)]),
            (3, 101, [(82, None, 0x23)]),
        ])

    def check_code(self, body, code, **kwargs):
        result = analyze(body, **kwargs)
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(result["code"], code)
        self.assertFalse(result["checks"]["complete_active_interval"])
        for key in ("replay_performed", "filesystem_accepted", "inspection_accepted",
                    "raw_payload_exported", "target_block_numbers_exported", "entry0_pointer_followed"):
            self.assertIs(result[key], False)
        return result

    def test_single_record_exact_count_and_payload_coverage(self):
        result = analyze(self.one)
        self.assertEqual(result["status"], "STRUCTURE_DIAGNOSIS_COMPLETE")
        self.assertEqual(result["counts"]["entries_seen"], 1)
        self.assertEqual(result["counts"]["live_entries"], 1)
        self.assertEqual(result["counts"]["payload_checksums_verified"], 1)
        self.assertEqual(result["counts"]["payload_bytes_consumed"], END - START - LIST)
        self.assertEqual(result["counts"]["active_bytes_consumed"], END - START)
        self.assertEqual(result["records"][0]["num_blocks"], 2)
        self.assertTrue(all(result["checks"].values()))

    def test_multiple_lists_killed_entry_and_sequence_boundary(self):
        result = analyze(self.multi)
        self.assertEqual(result["status"], "STRUCTURE_DIAGNOSIS_COMPLETE")
        counts = result["counts"]
        self.assertEqual((counts["completed_lists"], counts["live_entries"], counts["killed_entries"]), (3, 3, 1))
        self.assertEqual((counts["transaction_starts"], counts["continuation_lists"], counts["sequence_increments"]), (2, 1, 1))
        self.assertEqual(counts["killed_payload_bytes"], 512)
        self.assertEqual(counts["payload_checksums_verified"], 3)
        self.assertEqual([row["journal_offset"] for row in result["records"]], self.offsets)

    def test_no_payload_pointers_targets_or_sequence_values_exported(self):
        body = bytearray(self.one)
        secret = b"SYNTHETIC_PRIVATE_PAYLOAD_DO_NOT_EXPORT"
        payload_at = START + LIST
        body[payload_at:payload_at + len(secret)] = secret
        size = END - payload_at
        struct.pack_into("<I", body, START + 44, fixture_checksum(body[payload_at:payload_at + size]))
        result = analyze(body)
        self.assertEqual(result["status"], "STRUCTURE_DIAGNOSIS_COMPLETE")
        encoded = json.dumps(result, sort_keys=True)
        self.assertNotIn(secret.decode(), encoded)
        self.assertNotIn(str(0x1122334455667788), encoded)
        self.assertNotIn(str(0x4C535453), encoded)
        for key in ("bnum", "target_offset", "sequence_num", "payload", "pointer"):
            self.assertNotIn('"' + key + '"', encoded)
        self.assertLess(len(encoded), 128 << 10)
        self.assertEqual(result, analyze(body))

    def test_input_exact_size_and_immutable_type(self):
        for body in (b"", bytes(self.one[:-1]), bytes(self.one) + b"x", self.one, memoryview(self.one), "x"):
            with self.subTest(type=type(body).__name__, size=len(body)):
                result = probe.analyze_journal(body, volume_bytes=VOLUME, expected_header_sha256="0" * 64)
                self.assertEqual(result["code"], "journal_input_type_or_size")

    def test_volume_size_cannot_expand_target_scope(self):
        for value in (VOLUME + 512, VOLUME - 512, True, str(VOLUME)):
            self.check_code(self.one, "unsupported_volume_size", volume_bytes=value)

    def test_header_expected_digest_type_format_and_binding(self):
        for digest in (None, 1, "g" * 64, "a" * 63, "A" * 64):
            result = probe.analyze_journal(bytes(self.one), volume_bytes=VOLUME,
                                           expected_header_sha256=digest)
            self.assertEqual(result["code"], "invalid_expected_header_digest")
        self.check_code(self.one, "bound_header_digest_mismatch", digest="0" * 64)

    def test_journal_header_checksum_is_verified(self):
        body = bytearray(self.one)
        body[36] ^= 1
        self.check_code(body, "journal_header_checksum_mismatch")

    def test_unknown_endian_empty_wrapped_or_changed_header_profiles_refuse(self):
        mutations = [(0, "<I", 0x4A484452), (4, "<I", 0x78563412),
                     (8, "<Q", END), (16, "<Q", START),
                     (24, "<Q", JOURNAL - 512), (32, "<i", 4096), (40, "<i", 4096)]
        for offset, fmt, value in mutations:
            with self.subTest(offset=offset, value=value):
                body = bytearray(self.one)
                struct.pack_into(fmt, body, offset, value)
                fix_header(body)
                self.check_code(body, "unsupported_journal_header_profile")

    def test_header_sequence_has_no_invented_transaction_binding(self):
        body = bytearray(self.one)
        struct.pack_into("<I", body, 44, 0)
        # Offset44 is outside the44-byte journal-header checksum.
        result = analyze(body)
        self.assertEqual(result["status"], "STRUCTURE_DIAGNOSIS_COMPLETE")
        self.assertFalse(result["limitations"]["header_sequence_bound_to_first_or_last_transaction"])

    def test_list_header_checksum_covers_reserved_entry(self):
        body = bytearray(self.one)
        body[START + 16] ^= 1
        result = self.check_code(body, "list_header_checksum_mismatch")
        self.assertEqual(result["counts"]["entries_seen"], 0)

    def test_num_blocks_includes_reserved_entry(self):
        body = bytearray(self.one)
        struct.pack_into("<H", body, START + 2, 1)
        fix_list(body)
        self.check_code(body, "list_payload_size_sum_mismatch")

    def test_bad_list_count_and_capacity_refuse_before_entry_reads(self):
        for max_blocks, num_blocks in ((0, 2), (3072, 2), (3071, 0), (1, 2), (3071, 3072)):
            with self.subTest(max_blocks=max_blocks, num_blocks=num_blocks):
                body = bytearray(self.one)
                struct.pack_into("<HH", body, START, max_blocks, num_blocks)
                fix_list(body)
                result = self.check_code(body, "invalid_list_entry_count")
                self.assertEqual(result["counts"]["entries_seen"], 0)

    def test_bytes_used_negative_short_unaligned_and_beyond_active_refuse(self):
        for used in (-1, LIST - 512, LIST + 1, END - START + 512):
            body = bytearray(self.one)
            struct.pack_into("<i", body, START + 4, used)
            fix_list(body)
            self.check_code(body, "invalid_list_bytes_used")

    def test_payload_size_negative_zero_unaligned_or_too_large_refuses(self):
        for size in (-512, 0, 513, END - START):
            body = bytearray(self.one)
            struct.pack_into("<i", body, START + 40, size)
            self.check_code(body, "invalid_or_out_of_range_payload_size")

    def test_payload_sizes_must_sum_to_bytes_used(self):
        body = bytearray(self.one)
        size = END - START - LIST - 512
        struct.pack_into("<iI", body, START + 40, size,
                         fixture_checksum(body[START + LIST:START + LIST + size]))
        self.check_code(body, "list_payload_size_sum_mismatch")

    def test_live_targets_are_signed_bounded_volume_sector_numbers(self):
        for target, code in ((-2, "unsupported_negative_target"),
                             (VOLUME // 512, "live_target_outside_volume"),
                             ((1 << 63) - 1, "live_target_outside_volume")):
            body = bytearray(self.one)
            struct.pack_into("<q", body, START + 32, target)
            self.check_code(body, code)

    def test_target_range_end_allows_exact_volume_end_only(self):
        body = bytearray(self.one)
        size = END - START - LIST
        target = (VOLUME - size) // 512
        struct.pack_into("<q", body, START + 32, target)
        self.assertEqual(analyze(body)["status"], "STRUCTURE_DIAGNOSIS_COMPLETE")
        struct.pack_into("<q", body, START + 32, target + 1)
        self.check_code(body, "live_target_outside_volume")

    def test_corrupt_live_payload_fails_without_export(self):
        body = bytearray(self.one)
        body[START + LIST + 17] ^= 1
        result = self.check_code(body, "live_payload_checksum_mismatch")
        self.assertEqual(result["counts"]["payload_checksums_verified"], 0)

    def test_missing_live_payload_checksum_is_unavailable_not_valid(self):
        body = bytearray(self.one)
        struct.pack_into("<I", body, START + 44, 0)
        result = self.check_code(body, "live_payload_checksum_unavailable")
        self.assertEqual(result["counts"]["payload_checksums_unavailable"], 1)
        self.assertIsNone(result["checks"]["all_live_payload_checksums_valid"])

    def test_killed_payload_still_consumes_space_but_is_not_checked_or_targeted(self):
        body = bytearray(self.multi)
        body[START + LIST + 512] ^= 1
        result = analyze(body)
        self.assertEqual(result["status"], "STRUCTURE_DIAGNOSIS_COMPLETE")
        self.assertEqual(result["counts"]["payload_checksums_verified"], 3)
        self.assertFalse(result["limitations"]["killed_payload_checksums_evaluated"])

    def test_unknown_or_disabled_checksum_flags_are_incomplete(self):
        for flags, code in ((4, "unsupported_list_flags"), (-1, "unsupported_list_flags"),
                            (0, "payload_checksums_not_enabled"), (2, "payload_checksums_not_enabled")):
            body = bytearray(self.one)
            struct.pack_into("<i", body, START + 12, flags)
            fix_list(body)
            self.check_code(body, code)

    def test_reserved_entry_size_is_not_a_payload(self):
        body = bytearray(self.one)
        struct.pack_into("<i", body, START + 24, 512)
        fix_list(body)
        self.check_code(body, "unsupported_reserved_entry_size")

    def test_zero_transaction_sequence_is_explicitly_unsupported(self):
        body = bytearray(self.one)
        struct.pack_into("<I", body, START + 28, 0)
        fix_list(body)
        self.check_code(body, "unsupported_zero_transaction_sequence")

    def test_first_record_requires_first_header(self):
        body = bytearray(self.one)
        struct.pack_into("<i", body, START + 12, 1)
        fix_list(body)
        self.check_code(body, "sequence_or_first_header_inconsistent")

    def test_continuation_and_new_transaction_sequences_are_distinct(self):
        for record, sequence, flags in ((1, 101, 1), (1, 100, 3), (2, 102, 3), (2, 101, 1)):
            with self.subTest(record=record, sequence=sequence, flags=flags):
                body = bytearray(self.multi)
                offset = self.offsets[record]
                struct.pack_into("<I", body, offset + 28, sequence)
                struct.pack_into("<i", body, offset + 12, flags)
                fix_list(body, offset)
                self.check_code(body, "sequence_or_first_header_inconsistent")

    def test_trailing_active_bytes_do_not_trigger_inactive_scan(self):
        body = bytearray(self.one)
        used = END - START - 512
        size = used - LIST
        struct.pack_into("<i", body, START + 4, used)
        struct.pack_into("<iI", body, START + 40, size,
                         fixture_checksum(body[START + LIST:START + LIST + size]))
        fix_list(body)
        result = self.check_code(body, "list_header_outside_active_interval")
        self.assertEqual(result["counts"]["completed_lists"], 1)

    def test_inactive_region_changes_do_not_create_transactions(self):
        body = bytearray(self.one)
        body[END:END + LIST] = bytes([0xDA]) * LIST
        self.assertEqual(analyze(body), analyze(self.one))

    def test_secondary_bounded_list_and_entry_caps_refuse(self):
        with mock.patch.object(probe, "MAX_LISTS", 1):
            self.check_code(self.multi, "list_count_limit")
        with mock.patch.object(probe, "MAX_ENTRIES", 0):
            result = self.check_code(self.one, "entry_count_limit")
            self.assertEqual(result["counts"]["entries_seen"], 0)

    def test_checksum_known_vectors_and_unsigned_byte_semantics(self):
        # Empty/one-byte vectors have direct arithmetic expectations. The
        # high-byte case catches signed-char interpretation; the long vector
        # was separately checked with a standalone unsigned32 C implementation.
        for body, expected in ((b"", 0xFFFFFFFF), (b"a", 0xFFFFFF9E),
                               (b"\xff", 0xFFFFFF00), (b"abc", 4288569049),
                               (bytes(range(256)), 1092524671)):
            self.assertEqual(probe.checksum(body), expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
