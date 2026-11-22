#!/usr/bin/env python3
"""Pure, bounded structure diagnosis of the retained resume5 Data journal.

This module has no file, process, device, replay or write interface. The caller
owns receipt/source binding and immutable extraction. A completed diagnosis is
not a filesystem check, a replay recommendation or inspection acceptance.

Supported profile: modern Apple HFS JNLx, little endian, the observed nonwrapped
active interval, modern checksum/first-header flags and nonzero transaction
sequences. The exact implementation basis and narrower supported conditions
are documented in PARSER.md. Unknown cases remain INCOMPLETE.
"""
import hashlib
import re
import struct


SCHEMA = 1
FORMAT = "apple_hfs_modern_nonwrapped_le_d1bac2f"
JOURNAL_BYTES = 8 << 20
VOLUME_BYTES = 16 << 30
SECTOR_BYTES = 512
BLOCK_LIST_BYTES = 49152
ACTIVE_START = 512
ACTIVE_END = 614400
ACTIVE_BYTES = ACTIVE_END - ACTIVE_START
MAGIC = 0x4A4E4C78
ENDIAN_MAGIC = 0x12345678
HEADER_CHECKSUM_BYTES = 44
LIST_CHECKSUM_BYTES = 32
LIST_PREFIX_BYTES = 16
ENTRY_BYTES = 16
ENTRY_CAPACITY = BLOCK_LIST_BYTES // ENTRY_BYTES - 1
MAX_LISTS = 16
MAX_ENTRIES = 4096
CHECK_CHECKSUMS = 1
FIRST_HEADER = 2
ACTUAL_HEADER_SHA256 = "f9bd83c96acbaba80a2d24b09731ef6f39ae78cc922cbca9d65c774716c2a66f"
SOURCE_COMMIT = "d1bac2f062e6e9c0dfcce302d9aacb10173d0eea"


class DiagnosisError(Exception):
    """A fixed public code and bounded positions; never carry input values."""

    def __init__(self, code, record_index=None, entry_index=None, journal_offset=None):
        self.code = code
        self.record_index = record_index
        self.entry_index = entry_index
        self.journal_offset = journal_offset
        super().__init__(code)


def require(condition, code, record_index=None, entry_index=None, journal_offset=None):
    if not condition:
        raise DiagnosisError(code, record_index, entry_index, journal_offset)


def checksum(body):
    """Apple's bytewise 32-bit checksum; no byte order conversion of input."""
    value = 0
    for byte in body:
        value = ((value << 8) ^ (value + byte)) & 0xFFFFFFFF
    return (~value) & 0xFFFFFFFF


def checksum_with_zero(body, length, field_offset):
    copy = bytearray(body[:length])
    copy[field_offset:field_offset + 4] = bytes(4)
    return checksum(copy)


def new_result():
    return {
        "schema": SCHEMA,
        "kind": "data_journal_structure_diagnosis",
        "status": "INCOMPLETE",
        "code": None,
        "readonly": True,
        "format": FORMAT,
        "scope": {
            "journal_bytes": JOURNAL_BYTES,
            "volume_bytes": VOLUME_BYTES,
            "sector_bytes": SECTOR_BYTES,
            "block_list_bytes": BLOCK_LIST_BYTES,
            "active_start": ACTIVE_START,
            "active_end": ACTIVE_END,
            "active_bytes": ACTIVE_BYTES,
            "entry_capacity": ENTRY_CAPACITY,
            "max_lists": MAX_LISTS,
            "max_entries": MAX_ENTRIES,
            "nonwrapped_only": True,
        },
        "checks": {
            "header_hash_matches": None,
            "journal_header_checksum_valid": None,
            "header_profile_matches": None,
            "complete_active_interval": False,
            "all_list_header_checksums_valid": None,
            "all_live_payload_checksums_valid": None,
            "all_live_target_ranges_valid": None,
            "sequence_and_first_header_consistent": None,
            "bytes_used_matches_payloads": None,
        },
        "counts": {
            "list_headers_seen": 0,
            "list_headers_verified": 0,
            "completed_lists": 0,
            "entries_seen": 0,
            "live_entries": 0,
            "killed_entries": 0,
            "live_target_ranges_verified": 0,
            "payload_checksums_verified": 0,
            "payload_checksums_unavailable": 0,
            "payload_bytes_consumed": 0,
            "live_payload_bytes": 0,
            "killed_payload_bytes": 0,
            "transaction_starts": 0,
            "continuation_lists": 0,
            "sequence_increments": 0,
            "active_bytes_consumed": 0,
        },
        "records": [],
        "failure": None,
        "limitations": {
            "known_guest_kernel_source_identity": False,
            "header_sequence_is_outside_header_checksum": True,
            "header_sequence_bound_to_first_or_last_transaction": False,
            "target_numbers_have_no_independent_checksum": True,
            "killed_payload_checksums_evaluated": False,
            "inactive_journal_region_interpreted": False,
            "transaction_replay_order_or_coalescing_evaluated": False,
            "filesystem_semantics_evaluated": False,
        },
        "replay_performed": False,
        "filesystem_accepted": False,
        "inspection_accepted": False,
        "raw_payload_exported": False,
        "target_block_numbers_exported": False,
        "entry0_pointer_followed": False,
    }


def validate_header(body, expected_sha256, result):
    require(type(expected_sha256) is str and
            re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is not None,
            "invalid_expected_header_digest")
    header = body[:SECTOR_BYTES]
    matches = hashlib.sha256(header).hexdigest() == expected_sha256
    result["checks"]["header_hash_matches"] = matches
    require(matches, "bound_header_digest_mismatch")

    # The checksum covers bytes0..43; sequence_num at44 is deliberately not
    # used to assert a relationship to any transaction sequence.
    magic, endian, start, end, size, block_bytes, stored, header_bytes = struct.unpack_from(
        "<IIQQQiIi", header)
    valid_checksum = stored == checksum_with_zero(header, HEADER_CHECKSUM_BYTES, 36)
    result["checks"]["journal_header_checksum_valid"] = valid_checksum
    require(valid_checksum, "journal_header_checksum_mismatch")
    profile = (magic == MAGIC and endian == ENDIAN_MAGIC and
               size == JOURNAL_BYTES and header_bytes == SECTOR_BYTES and
               block_bytes == BLOCK_LIST_BYTES and
               start == ACTIVE_START and end == ACTIVE_END)
    result["checks"]["header_profile_matches"] = profile
    require(profile, "unsupported_journal_header_profile")


def analyze_journal(journal_bytes, *, volume_bytes, expected_header_sha256):
    """Return only bounded scalar facts; malformed/unsupported input is INCOMPLETE.

    Exact bytes are required, so the parser cannot race mutation of its input.
    The production caller must explicitly supply the independently bound actual
    header digest. Tests may supply a digest of a synthetic header in the same
    narrow format; no acceptance path consumes this result.
    """
    result = new_result()
    counts = result["counts"]
    checks = result["checks"]
    try:
        require(type(journal_bytes) is bytes and len(journal_bytes) == JOURNAL_BYTES,
                "journal_input_type_or_size")
        require(type(volume_bytes) is int and volume_bytes == VOLUME_BYTES,
                "unsupported_volume_size")
        validate_header(journal_bytes, expected_header_sha256, result)
        cursor = ACTIVE_START
        previous_sequence = None
        while cursor < ACTIVE_END:
            index = len(result["records"])
            require(index < MAX_LISTS, "list_count_limit", index, journal_offset=cursor)
            require(cursor % SECTOR_BYTES == 0 and
                    BLOCK_LIST_BYTES <= ACTIVE_END - cursor,
                    "list_header_outside_active_interval", index, journal_offset=cursor)
            block = memoryview(journal_bytes)[cursor:cursor + BLOCK_LIST_BYTES]
            max_blocks, num_blocks, bytes_used, stored_checksum, flags = struct.unpack_from(
                "<HHiIi", block)
            row = {
                "index": index,
                "journal_offset": cursor,
                "max_blocks": max_blocks,
                "num_blocks": num_blocks,
                "bytes_used": bytes_used,
                "flags": flags,
                "list_header_checksum_valid": None,
                "sequence_and_first_header_consistent": None,
                "bytes_used_matches_payloads": None,
                "live_entries": 0,
                "killed_entries": 0,
                "payload_checksums_verified": 0,
                "payload_checksums_unavailable": 0,
                "payload_bytes_consumed": 0,
                "status": "INCOMPLETE",
            }
            result["records"].append(row)
            counts["list_headers_seen"] += 1
            valid = stored_checksum == checksum_with_zero(block, LIST_CHECKSUM_BYTES, 8)
            row["list_header_checksum_valid"] = valid
            require(valid, "list_header_checksum_mismatch", index, journal_offset=cursor)
            counts["list_headers_verified"] += 1
            require(1 <= max_blocks <= ENTRY_CAPACITY and
                    1 <= num_blocks <= max_blocks and
                    LIST_PREFIX_BYTES + num_blocks * ENTRY_BYTES <= BLOCK_LIST_BYTES,
                    "invalid_list_entry_count", index, journal_offset=cursor)
            require(counts["entries_seen"] + num_blocks - 1 <= MAX_ENTRIES,
                    "entry_count_limit", index, journal_offset=cursor)
            require(BLOCK_LIST_BYTES <= bytes_used <= ACTIVE_END - cursor and
                    bytes_used % SECTOR_BYTES == 0,
                    "invalid_list_bytes_used", index, journal_offset=cursor)
            require(flags >= 0 and flags & ~(CHECK_CHECKSUMS | FIRST_HEADER) == 0,
                    "unsupported_list_flags", index, journal_offset=cursor)
            require(flags & CHECK_CHECKSUMS != 0, "payload_checksums_not_enabled",
                    index, journal_offset=cursor)

            # Entry0's bnum is an opaque serialized pointer in the producer.
            # Never parse it, use it as a disk offset, or put it in the report.
            reserved_size, sequence = struct.unpack_from("<iI", block, 24)
            require(reserved_size == 0, "unsupported_reserved_entry_size",
                    index, journal_offset=cursor)
            require(sequence != 0, "unsupported_zero_transaction_sequence",
                    index, journal_offset=cursor)
            first_header = bool(flags & FIRST_HEADER)
            if previous_sequence is None:
                coherent = first_header
            elif first_header:
                coherent = sequence == ((previous_sequence + 1) & 0xFFFFFFFF)
            else:
                coherent = sequence == previous_sequence
            row["sequence_and_first_header_consistent"] = coherent
            require(coherent, "sequence_or_first_header_inconsistent",
                    index, journal_offset=cursor)
            if first_header:
                counts["transaction_starts"] += 1
                if previous_sequence is not None:
                    counts["sequence_increments"] += 1
            else:
                counts["continuation_lists"] += 1

            payload_cursor = cursor + BLOCK_LIST_BYTES
            record_end = cursor + bytes_used
            for entry in range(1, num_blocks):
                number, size, payload_checksum = struct.unpack_from(
                    "<qiI", block, LIST_PREFIX_BYTES + entry * ENTRY_BYTES)
                counts["entries_seen"] += 1
                require(size > 0 and size % SECTOR_BYTES == 0 and
                        size <= record_end - payload_cursor,
                        "invalid_or_out_of_range_payload_size", index, entry, payload_cursor)
                require(number >= 0 or number == -1, "unsupported_negative_target",
                        index, entry, payload_cursor)
                if number == -1:
                    row["killed_entries"] += 1
                    counts["killed_entries"] += 1
                    counts["killed_payload_bytes"] += size
                else:
                    row["live_entries"] += 1
                    counts["live_entries"] += 1
                    # Python integer arithmetic cannot overflow; check before
                    # checksum work and never expose number or derived target.
                    target = number * SECTOR_BYTES
                    require(target < volume_bytes and size <= volume_bytes - target,
                            "live_target_outside_volume", index, entry, payload_cursor)
                    counts["live_target_ranges_verified"] += 1
                    if payload_checksum == 0:
                        counts["payload_checksums_unavailable"] += 1
                        row["payload_checksums_unavailable"] += 1
                        raise DiagnosisError("live_payload_checksum_unavailable",
                                             index, entry, payload_cursor)
                    payload = memoryview(journal_bytes)[payload_cursor:payload_cursor + size]
                    require(checksum(payload) == payload_checksum,
                            "live_payload_checksum_mismatch", index, entry, payload_cursor)
                    counts["payload_checksums_verified"] += 1
                    row["payload_checksums_verified"] += 1
                    counts["live_payload_bytes"] += size
                payload_cursor += size
                row["payload_bytes_consumed"] += size
                counts["payload_bytes_consumed"] += size
            row["bytes_used_matches_payloads"] = payload_cursor == record_end
            require(payload_cursor == record_end, "list_payload_size_sum_mismatch",
                    index, journal_offset=cursor)
            row["status"] = "STRUCTURE_OBSERVED"
            counts["completed_lists"] += 1
            cursor = record_end
            counts["active_bytes_consumed"] = cursor - ACTIVE_START
            previous_sequence = sequence

        require(cursor == ACTIVE_END and counts["completed_lists"] > 0,
                "active_interval_not_fully_consumed")
        for name in ("complete_active_interval", "all_list_header_checksums_valid",
                     "all_live_payload_checksums_valid", "all_live_target_ranges_valid",
                     "sequence_and_first_header_consistent", "bytes_used_matches_payloads"):
            checks[name] = True
        result["status"] = "STRUCTURE_DIAGNOSIS_COMPLETE"
        result["code"] = "supported_nonempty_structure_observed"
    except DiagnosisError as exc:
        result["code"] = exc.code
        result["failure"] = {
            "code": exc.code,
            "record_index": exc.record_index,
            "entry_index": exc.entry_index,
            "journal_offset": exc.journal_offset,
        }
    return result
