"""Offline journal/receipt refusals and owned-helper collection.

No VM, GPU, mounts, phone access, downloads or Apple image bytes are used.
"""
import builtins
import contextlib
import copy
import fcntl
import io
import json
import os
from pathlib import Path
import stat
import struct
import tarfile
import tempfile
import types
import unittest
from unittest import mock

import audit_ios26_partition_guest as auditor
import guard_ios26_firstboot as guard
import inspect_ios26_firstboot as host
import inspect_ios26_firstboot_guest as guest
import prepare_ios26 as prep
from test_audit_ios26_partition import CLEAN, SparseDisk


# Literal 44-byte source-algorithm vectors, checksum field included. These do
# not use the implementation under test to manufacture their passing oracle.
VECTORS = {
    "<": bytes.fromhex("784c4e4a7856341200020000000000000002000000000000000080000000000000100000f92aba0900020000"),
    ">": bytes.fromhex("4a4e4c781234567800000000000002000000000000000200000000000080000000001000871858f900000200"),
}


def journal_header(order="<", **changes):
    body = bytearray(VECTORS[order].ljust(512, b"\0"))
    offsets = {"magic": (0, "I"), "marker": (4, "I"), "start": (8, "Q"), "end": (16, "Q"),
               "size": (24, "Q"), "block_header": (32, "I"), "header": (40, "I")}
    for name, value in changes.items():
        offset, code = offsets[name]
        struct.pack_into(order + code, body, offset, value)
    if changes:
        struct.pack_into(order + "I", body, 36, guest.checksum(body))
    return bytes(body)


class JournalHeader(unittest.TestCase):
    def test_source_literal_both_endian_headers(self):
        for order, expected in (("<", 0x09BA2AF9), (">", 0x871858F9)):
            with self.subTest(order=order):
                body = journal_header(order)
                self.assertEqual(guest.checksum(body), expected)
                result = guest.initialized_header(body, {"bytes": 8 << 20})
                self.assertEqual(result["state"], "INITIALIZED_EMPTY")
                self.assertEqual(result["start"], result["end"])

    def test_checksum_does_not_cover_sequence_number_or_padding(self):
        body = bytearray(journal_header())
        body[44:] = b"\xa7" * (512 - 44)
        self.assertEqual(guest.checksum(body), 0x09BA2AF9)
        self.assertEqual(guest.initialized_header(body, {"bytes": 8 << 20})["status"], "PASSED")

    def test_bad_checksum_is_not_waived_by_empty_cursors(self):
        body = bytearray(journal_header())
        body[36] ^= 1
        with self.assertRaisesRegex(guest.InspectionError, "journal_header_checksum"):
            guest.initialized_header(body, {"bytes": 8 << 20})

    def test_magic_endian_and_short_reads(self):
        for body in (journal_header(magic=0), journal_header(marker=0),
                     VECTORS[">"][:4] + journal_header()[4:], journal_header()[:44]):
            with self.subTest(prefix=body[:8].hex()):
                with self.assertRaises(guest.InspectionError):
                    guest.initialized_header(body, {"bytes": 8 << 20})

    def test_nonempty_and_unsupported_cursors_keep_numeric_metadata(self):
        for fields, code in (({"end": 1024}, "nonempty_journal"),
                             ({"start": 8 << 20, "end": 8 << 20}, "unsupported_journal_cursor"),
                             ({"start": 0, "end": 0}, "unsupported_journal_cursor"),
                             ({"start": 513, "end": 513}, "unsupported_journal_cursor"),
                             ({"start": (1 << 64) - 1, "end": (1 << 64) - 1}, "unsupported_journal_cursor")):
            with self.subTest(fields=fields):
                with self.assertRaisesRegex(guest.InspectionError, code) as raised:
                    guest.initialized_header(journal_header(**fields), {"bytes": 8 << 20})
                self.assertEqual(raised.exception.metadata["end"], fields["end"])
                self.assertIn("header_sha256", raised.exception.metadata)

    def test_journal_header_and_block_list_sizes(self):
        for fields in ({"size": 16 << 20}, {"header": 4096}, {"header": 0},
                       {"block_header": 0}, {"block_header": 513}, {"block_header": 1 << 20}):
            with self.subTest(fields=fields):
                with self.assertRaises(guest.InspectionError):
                    guest.initialized_header(journal_header(**fields), {"bytes": 8 << 20})
        # A valid non-typical size is not refused merely for exceeding 16KiB.
        self.assertEqual(guest.initialized_header(journal_header(block_header=32768),
                                                  {"bytes": 8 << 20})["status"], "PASSED")


class RawDisk(SparseDisk):
    """Sparse authored byte ranges, with zero-fill reads and no disk image."""
    def __init__(self, initialized=False):
        super().__init__()
        for start, sectors, _ in auditor.PARTITIONS:
            base, size = start * 512, sectors * 512
            bitmap = size // 4096 // 8
            jib = 1 + bitmap // 4096
            header = bytearray(512)
            struct.pack_into(">HHIII", header, 0, 0x4858, 5, (1 << 13) | (1 << 8), 0x4846534A, jib)
            struct.pack_into(">II", header, 40, 4096, size // 4096)
            struct.pack_into(">QII", header, 112, bitmap, bitmap, bitmap // 4096)
            struct.pack_into(">II", header, 128, 1, bitmap // 4096)
            self.blocks[base + 1024] = bytes(header)
            self.blocks[base + size - 1024] = bytes(header)
            # Independent formatter layout from makehfs.c WriteJournalInfo.
            info = bytearray(4096)
            struct.pack_into(">I", info, 0, 1 if initialized else 5)
            struct.pack_into(">QQ", info, 36, (jib + 1) * 4096, 8 << 20)
            info[180:512] = b"\xdb" * 332
            self.blocks[base + jib * 4096] = bytes(info)
            if initialized:
                self.blocks[base + (jib + 1) * 4096] = journal_header()

    def read(self, size):
        output = bytearray(size)
        left, right = self.position, self.position + size
        for offset, body in self.blocks.items():
            begin, end = max(left, offset), min(right, offset + len(body))
            if begin < end:
                output[begin - left:end - left] = body[begin - offset:end - offset]
        self.position += size
        return bytes(output)

    def change(self, offset, body):
        # Mutations may replace a subset of an existing authored range.
        for start, old in list(self.blocks.items()):
            if start <= offset and offset + len(body) <= start + len(old):
                value = bytearray(old)
                value[offset - start:offset - start + len(body)] = body
                self.blocks[start] = bytes(value)
                return
        self.blocks[offset] = bytes(body)


class RawJournals(unittest.TestCase):
    def geometry(self, index=1):
        start, sectors, _ = auditor.PARTITIONS[index]
        return start * 512, sectors * 512

    def test_both_exact_formatter_needinit_states_match_predecessor(self):
        for index in (0, 1):
            with self.subTest(index=index):
                result = guest.inspect_volume(RawDisk(), RawDisk(), *self.geometry(index))
                self.assertEqual(result["journal"]["state"], "UNTOUCHED_AUTHORED_NEEDINIT")
                self.assertTrue(result["journal"]["journal_all_zero"])

    def test_initialized_inactive_payload_has_no_zero_requirement(self):
        disk = RawDisk(True)
        base, size = self.geometry()
        journal = base + (2 + size // 4096 // 8 // 4096) * 4096
        disk.change(journal + 4096, b"authored old transaction bytes")
        result = guest.inspect_volume(disk, RawDisk(), base, size)
        self.assertEqual(result["journal"]["state"], "INITIALIZED_EMPTY")
        self.assertFalse(result["journal"]["inactive_payload_examined"])

    def test_needinit_nonzero_and_initialized_baseline_are_refused(self):
        base, size = self.geometry()
        journal = base + (2 + size // 4096 // 8 // 4096) * 4096
        disk = RawDisk()
        disk.change(journal + (8 << 20) - 1, b"\x01")
        with self.assertRaisesRegex(guest.InspectionError, "needinit_journal_not_zero"):
            guest.inspect_volume(disk, RawDisk(), base, size)
        with self.assertRaisesRegex(guest.InspectionError, "needinit_not_exact_authored_jib"):
            guest.inspect_volume(RawDisk(), RawDisk(True), base, size)

    def test_needinit_padding_and_volume_header_changes_are_refused(self):
        base, size = self.geometry()
        jib = base + (1 + size // 4096 // 8 // 4096) * 4096
        disk = RawDisk()
        disk.change(jib + 200, b"\0")
        with self.assertRaisesRegex(guest.InspectionError, "needinit_not_exact_authored_jib"):
            guest.inspect_volume(disk, RawDisk(), base, size)
        disk = RawDisk()
        disk.change(base + 1024 + 20, b"\x01")
        with self.assertRaisesRegex(guest.InspectionError, "needinit_volume_headers_changed"):
            guest.inspect_volume(disk, RawDisk(), base, size)

    def test_header_disagreement_and_jib_range_or_flags_fail(self):
        base, size = self.geometry()
        jib = base + (1 + size // 4096 // 8 // 4096) * 4096
        for offset, body in ((base + size - 1024 + 12, struct.pack(">I", 200)),
                             (jib, struct.pack(">I", 7)), (jib + 36, struct.pack(">Q", size - 4096)),
                             (jib + 44, struct.pack(">Q", (1 << 64) - 1))):
            disk = RawDisk()
            disk.change(offset, body)
            with self.subTest(offset=offset):
                with self.assertRaises(guest.InspectionError):
                    guest.inspect_volume(disk, RawDisk(), base, size)

    def test_metadata_extents_cannot_alias_discovered_journal(self):
        base, size = self.geometry()
        disk = RawDisk(True)
        journal_block = 2 + size // 4096 // 8 // 4096
        for header in (base + 1024, base + size - 1024):
            disk.change(header + 192, struct.pack(">QII", 4096, 4096, 1))
            disk.change(header + 208, struct.pack(">II", journal_block, 1))
        with self.assertRaisesRegex(guest.InspectionError, "metadata_journal_overlap"):
            guest.inspect_volume(disk, RawDisk(), base, size)


class GuestProtocol(unittest.TestCase):
    def run_guest(self, disk=None, fsck_text=CLEAN, detach_failure=False):
        current, baseline = disk or RawDisk(True), RawDisk()
        commands, fsck_calls = [], []
        loops = {}

        def command(argv, seconds=30):
            commands.append(argv)
            if argv[:2] == ["blockdev", "--getro"]:
                return "1"
            if argv[:2] == ["blockdev", "--getsize64"]:
                return str(loops.get(argv[2], auditor.DISK_BYTES))
            if argv[0] == "losetup" and "--find" in argv:
                self.assertIn("--read-only", argv)
                loop = "/dev/loop" + str(len(loops))
                loops[loop] = int(argv[argv.index("--sizelimit") + 1])
                return loop
            if argv[:2] == ["losetup", "--detach"]:
                if detach_failure:
                    raise auditor.AuditError("authored_detach_failure")
                return ""
            self.fail("Unexpected utility, including any mount/replay command: " + repr(argv))

        def fsck(argv, **kwargs):
            self.assertEqual(argv[:3], ["fsck.hfsplus", "-f", "-n"])
            fsck_calls.append(argv)
            kwargs["stdout"].write(fsck_text.encode())
            return types.SimpleNamespace(returncode=0)

        real_open, real_stat = builtins.open, os.stat
        def raw_open(path, *args, **kwargs):
            if path in ("/dev/vda", "/dev/vdb"):
                self.assertEqual(args, ("rb",))
                return contextlib.nullcontext(current if path == "/dev/vda" else baseline)
            return real_open(path, *args, **kwargs)

        def device_stat(path, *args, **kwargs):
            if str(path) in ("/dev/vda", "/dev/vdb"):
                return types.SimpleNamespace(st_mode=stat.S_IFBLK)
            return real_stat(path, *args, **kwargs)

        with tempfile.TemporaryDirectory() as directory, mock.patch.object(auditor, "command", side_effect=command), \
                mock.patch.object(auditor, "ensure_unmounted"), mock.patch.object(guest.subprocess, "run", side_effect=fsck), \
                mock.patch("builtins.open", side_effect=raw_open), mock.patch.object(guest.os, "stat", side_effect=device_stat), \
                mock.patch.object(Path, "resolve", lambda p, **kwargs: p):
            result = guest.inspect_disks(auditor, "/dev/vda", "/dev/vdb",
                {"schema": 1, "inspection_nonce": "1" * 32}, Path(directory))
        return result, commands, fsck_calls

    def test_actual_raw_checks_precede_both_readonly_fscks_and_detach(self):
        result, commands, checks = self.run_guest()
        self.assertEqual(result["status"], "SAVED_FIRSTBOOT_INSPECTION_PASSED")
        self.assertEqual(len(checks), 2)
        self.assertEqual([c for c in commands if c[:2] == ["losetup", "--detach"]],
                         [["losetup", "--detach", "/dev/loop1"], ["losetup", "--detach", "/dev/loop0"]])

    def test_nonempty_second_journal_runs_no_fsck_and_retains_metadata(self):
        disk = RawDisk(True)
        start, sectors, _ = auditor.PARTITIONS[1]
        offset = start * 512 + (2 + sectors * 512 // 4096 // 8 // 4096) * 4096
        disk.change(offset, journal_header(end=1024))
        result, _, checks = self.run_guest(disk)
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(checks, [])
        self.assertEqual(result["journals"]["Data"]["metadata"]["end"], 1024)

    def test_bad_fsck_and_loop_cleanup_failure_cannot_pass(self):
        for text, failure in ((CLEAN + "No checking performed\n", False), (CLEAN, True)):
            result, commands, checks = self.run_guest(fsck_text=text, detach_failure=failure)
            self.assertEqual(result["status"], "INCOMPLETE")
            self.assertEqual(len(checks), 2)
            self.assertEqual(len([c for c in commands if c[:2] == ["losetup", "--detach"]]), 2)


def zero_counters():
    return [{"device": "root", "stats": {"failed_wr_operations": 0, "failed_flush_operations": 0}}]


class GuardReceipts(unittest.TestCase):
    def fixture(self, root):
        work, guard_work = root / "prep", root / "guard"
        work.mkdir(); guard_work.mkdir()
        (work / "checkpoints").mkdir(); (work / "attempts").mkdir()
        attempt = work / "attempts/07-0001"
        attempt.mkdir()
        session = {"runner_sources": {"source": "hash"}}
        prep.atomic_json(work / "session.json", session)
        checkpoint = {"stage": host.STAGE, "attempt": str(attempt)}
        checkpoint_path = work / "checkpoints/ios26-firstboot.json"
        prep.atomic_json(checkpoint_path, checkpoint)
        receipt = {"schema": 1, "kind": "ios26_firstboot_execution_guard", "guard_source_sha256": host.GUARD_SHA256,
            "prep_work": str(work), "prep_session_sha256": prep.cold.sha(work / "session.json"),
            "frozen_sources": session["runner_sources"], "frozen_input_identities": {}}
        counters = zero_counters()
        event = {"status": "COUNTERS_CHECKED", "stop_acknowledged": True, "failed_io_counters_zero": True,
                 "counter_check": guard.failed_io_counters(counters), "post_stop_blockstats": counters,
                 "stop_internal_flush_return_observed": False}
        observed = {"stage": host.STAGE, "status": "GUARDED_SUPERVISION_PASSED", "attempt": str(attempt),
                    "original_supervision_status": "VM_OBSERVATION_COMPLETE", "guest_sync_answered": True}
        launch = {"command": ["qemu", "-device", "virtio-blk-pci,drive=root"]}
        vm = {"stage": host.STAGE, "status": "VM_OBSERVATION_COMPLETE", "guest_sync_answered": True,
              "milestone": True, "settled": True,
              "cleanup": {"exit_code": 0, "echild": True, "stop_flushed": True, "errors": []},
              "witnesses": {"native_initialization": True, "native_execution": True, "fatal_markers": []},
              "qmp": [{"request": {"execute": name}, "response": {"return": counters if name == "query-blockstats" else {}}}
                      for name in ("stop", "query-blockstats", "quit")]}
        actual = {"attempt": str(attempt), "files": {}, "launch.json": launch, "vm-result.json": vm}
        for name, value in (("stage-inputs.json", {"stage": host.STAGE, "session_sha256": prep.digest(session), "inputs": {}}),
                            ("stage-result.json", checkpoint), ("launch.json", launch), ("vm-result.json", vm)):
            prep.atomic_json(attempt / name, value)
            body = (attempt / name).read_bytes()
            actual["files"][name] = {"sha256": host.sha(body), "bytes": len(body)}
        result = {"schema": 1, "status": "GUARDED_FIRSTBOOT_COMPLETE", "guard_session_sha256": prep.digest(receipt),
                  "checkpoint_accepted_by_guard": True, "original_firstboot_checkpoint_present": True,
                  "bound_inputs_unchanged": True, "checkpoint": {"path": str(checkpoint_path), "sha256": prep.cold.sha(checkpoint_path)},
                  "post_stop_blockstats": [event], "supervision": [observed], "actual_attempt": actual}
        observations = {"schema": 1, "post_stop_blockstats": [event], "supervision": [observed]}
        for name, value in (("guard-session.json", receipt), ("result.json", result), ("guard-observations.json", observations)):
            prep.atomic_json(guard_work / name, value)
        inventory = {"rows": {host.STAGE: checkpoint}, "hashes": {str(checkpoint_path): prep.cold.sha(checkpoint_path)}}
        return [guard, prep, guard_work, receipt, result, observations, inventory, work, session]

    def test_exact_approved_source_and_matching_receipt_pass(self):
        self.assertEqual(host.sha(Path(guard.__file__).read_bytes()), host.GUARD_SHA256)
        with tempfile.TemporaryDirectory() as directory:
            args = self.fixture(Path(directory))
            bound = host.guard_acceptance(*args)
            self.assertEqual(len(bound), 7)

    def test_checkpoint_present_does_not_waive_failed_or_unaccepted_guard(self):
        for key, value in (("status", "INCOMPLETE"), ("checkpoint_accepted_by_guard", False),
                           ("bound_inputs_unchanged", False), ("guard_session_sha256", "0" * 64)):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                args = self.fixture(Path(directory))
                args[4][key] = value
                with self.assertRaisesRegex(ValueError, "successful guard"):
                    host.guard_acceptance(*args)

    def test_changed_guard_attempt_log_or_checkpoint_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.fixture(Path(directory))
            path = Path(args[4]["actual_attempt"]["attempt"]) / "vm-result.json"
            path.write_bytes(path.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "metadata changed"):
                host.guard_acceptance(*args)
        with tempfile.TemporaryDirectory() as directory:
            args = self.fixture(Path(directory))
            args[6]["hashes"][args[4]["checkpoint"]["path"]] = "0" * 64
            with self.assertRaisesRegex(ValueError, "successful guard"):
                host.guard_acceptance(*args)

    def test_guard_observations_sync_and_counters_are_mandatory(self):
        for mutation in (lambda a: a[5].update(schema=0),
                         lambda a: a[4]["supervision"][0].update(guest_sync_answered=False),
                         lambda a: a[4]["post_stop_blockstats"][0]["post_stop_blockstats"][0]["stats"].update(failed_flush_operations=1)):
            with tempfile.TemporaryDirectory() as directory:
                args = self.fixture(Path(directory))
                mutation(args)
                with self.assertRaises(ValueError):
                    host.guard_acceptance(*args)


class BackingIdentity(unittest.TestCase):
    def chain(self, root):
        def qcow(path, backing=None):
            data = bytearray(131072)
            data[:4] = b"QFI\xfb"
            name = b"" if backing is None else backing.encode()
            struct.pack_into(">IQI", data, 4, 3, 104 if name else 0, len(name))
            struct.pack_into(">Q", data, 24, host.DISK_BYTES)
            data[104:104 + len(name)] = name
            path.write_bytes(data)
        qcow(root / "partition.qcow2")
        qcow(root / "saved.qcow2", "partition.qcow2")
        baseline, current = (prep.file_record(root / name, root) for name in ("partition.qcow2", "saved.qcow2"))
        return current, {"rows": {"ios26-partition": {"artifacts": {"root26g.qcow2": baseline}},
                                  host.STAGE: {"artifacts": {"root26g.qcow2": current}}}, "prior": {"root26g.qcow2": baseline}}

    def test_every_backing_member_is_fully_hashed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record, inventory = self.chain(root)
            chain = host.full_chain(prep, root, record, inventory)
            self.assertEqual(len(chain), 2)
            baseline = root / "partition.qcow2"
            before = baseline.stat()
            with baseline.open("r+b") as stream:
                stream.seek(100000)  # Beyond readonly_identity's 64KiB witness.
                stream.write(b"x")
            os.utime(baseline, ns=(before.st_atime_ns, before.st_mtime_ns))
            with self.assertRaisesRegex(ValueError, "full backing-chain"):
                host.full_chain(prep, root, record, inventory)

    def test_missing_or_different_predecessor_and_geometry_fail(self):
        for mutate in (lambda r, i, p: i["prior"]["root26g.qcow2"].update(path="elsewhere.qcow2"),
                       lambda r, i, p: r.update(backing_chain=["saved.qcow2"]),
                       lambda r, i, p: (p / "partition.qcow2").unlink()):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                record, inventory = self.chain(root)
                mutate(record, inventory, root)
                with self.assertRaises((ValueError, FileNotFoundError)):
                    host.full_chain(prep, root, record, inventory)


class CheckpointBoundary(unittest.TestCase):
    def fixture(self, root):
        (root / "checkpoints").mkdir()
        session, previous = {"authored": "session"}, None
        for stage in prep.stages.STAGES[:8]:
            artifacts = {}
            if stage in ("ios26-partition", host.STAGE):
                artifacts = {"root26g.qcow2": {"path": stage + "/root26g.qcow2"}}
            row = {"schema": 1, "status": "STAGE_COMPLETE", "stage": stage,
                   "session_sha256": prep.digest(session), "previous_sha256": previous, "artifacts": artifacts}
            target = root / "checkpoints" / (stage + ".json")
            prep.atomic_json(target, row)
            previous = prep.cold.sha(target)
        return session

    def test_partition_prefix_retains_its_own_artifact_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = self.fixture(root)
            result = host.checkpoint_inventory(prep, root, session)
            self.assertEqual(result["prior"]["root26g.qcow2"]["path"], "ios26-partition/root26g.qcow2")
            self.assertEqual(result["artifacts"]["root26g.qcow2"]["path"], "ios26-firstboot/root26g.qcow2")
            self.assertEqual(result["completed"], list(prep.stages.STAGES[:8]))

    def test_missing_firstboot_later_checkpoint_and_broken_chain_are_refused(self):
        for change in ("missing", "later", "chain"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                session = self.fixture(root)
                firstboot = root / "checkpoints/ios26-firstboot.json"
                if change == "missing":
                    firstboot.unlink()
                elif change == "later":
                    (root / "checkpoints/ios26-persona.json").write_text("{}")
                else:
                    row = json.loads(firstboot.read_text())
                    row["previous_sha256"] = "0" * 64
                    prep.atomic_json(firstboot, row)
                with self.assertRaises(ValueError):
                    host.checkpoint_inventory(prep, root, session)


class HostCollection(unittest.TestCase):
    def state(self, root):
        source = Path(host.__file__).parent
        original = root / "prep"
        original.mkdir()
        (original / "owner.lock").touch()
        fake = types.SimpleNamespace(cold=types.SimpleNamespace(utc=prep.cold.utc, require_phone=mock.Mock(), subreaper=mock.Mock()),
            refuse_live_children=mock.Mock(), atomic_json=prep.atomic_json, digest=prep.digest,
            helper_command=prep.helper_command, safe_return_tar=prep.safe_return_tar, file_record=prep.file_record,
            vm_success=prep.vm_success, cleanup_signals=prep.cleanup_signals)
        return {"prep": fake, "guest": guest, "auditor": auditor, "prep_work": original, "work": root / "inspection",
                "disk": original / "saved.qcow2", "baseline": original / "partition.qcow2",
                "receipt": {"partition_guest_sha256": host.sha(Path(auditor.__file__).read_bytes())},
                "bodies": {n: (source / n).read_bytes() for n in host.SOURCES},
                "dependency_body": Path(auditor.__file__).read_bytes(),
                "plan": {"session": {"helper_ram_mib": 2048, "helper_vcpus": 4,
                                      "package": str(root / "package"), "tooling": str(root / "tools")}}}

    def return_tar(self, state, attempt, argv, env, complete=True, mutate=None, omit=None):
        policy = json.loads((attempt / "expected-policy.json").read_text())
        result = {"schema": 1, "kind": "ios26_saved_firstboot_inspection", "status": "SAVED_FIRSTBOOT_INSPECTION_PASSED",
                  "errors": [], "cleanup_errors": [], "readonly_attachments": True, "raw_metadata_unchanged": True,
                  "mounted": False, "replayed": False, "repaired": False, "inspection_nonce": policy["inspection_nonce"],
                  "policy_sha256": prep.digest(policy), "gpt": {"status": "PASSED", "disk_bytes": host.DISK_BYTES},
                  "baseline_gpt": {"status": "PASSED", "disk_bytes": host.DISK_BYTES},
                  "journals": {n: {"status": "PASSED", "journal": {"status": "PASSED", "state": "INITIALIZED_EMPTY"}}
                               for n in ("iOSRoot", "Data")},
                  "fsck": {n: auditor.fsck_verdict(0, CLEAN) for n in ("iOSRoot", "Data")}}
        if not complete:
            result.update(status="INCOMPLETE", errors=[{"code": "nonempty_journal"}])
        if mutate:
            mutate(result)
        files = {"inspection/result.json": json.dumps(result).encode()}
        if complete:
            files.update({"inspection/fsck-system.txt": CLEAN.encode(), "inspection/fsck-data.txt": CLEAN.encode()})
        if omit:
            del files[omit]
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for name, body in files.items():
                item = tarfile.TarInfo(name)
                item.size = len(body)
                archive.addfile(item, io.BytesIO(body))
        with (attempt / "out.raw").open("r+b") as stream:
            stream.write(data.getvalue())
        for name in ("disk", "baseline"):
            drive = [arg for arg in argv if arg.startswith("file=" + str(state[name]) + ",")]
            self.assertEqual(len(drive), 1)
            self.assertIn("readonly=on", drive[0])
        self.assertEqual(env["ASOFT_NATIVE_EL0_REQUIRED"], "1")
        self.assertNotIn("ASOFT_NATIVE_EL0_TPIDRRO", env)
        return {"out_sizes": [len(data.getvalue())], "done_codes": [0], "natural_exit": True,
                "witnesses": {"native_initialization": True, "native_execution": True, "fatal_markers": []},
                "cleanup": {"exit_code": 0, "echild": True, "forced_qemu": False, "forced_descendants": [], "errors": []}}

    def test_real_safe_tar_extraction_and_original_lock_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            state = self.state(Path(directory))
            state["prep"].supervise_vm = lambda p, s, a, argv, env, args: self.return_tar(state, a, argv, env)
            before = {p.name: p.read_bytes() for p in state["prep_work"].iterdir()}
            with mock.patch.object(host, "unchanged_inputs") as unchanged:
                result = host.execute(state, host.parser().parse_args([]))
            self.assertEqual(result["status"], "SAVED_FIRSTBOOT_INSPECTION_PASSED")
            self.assertEqual(unchanged.call_args_list, [mock.call(state, True), mock.call(state, True)])
            self.assertTrue((state["work"] / "a1/files/inspection/fsck-data.txt").is_file())
            self.assertEqual(before, {p.name: p.read_bytes() for p in state["prep_work"].iterdir()})

    def test_incomplete_guest_evidence_is_retained_without_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            state = self.state(Path(directory))
            state["prep"].supervise_vm = lambda p, s, a, argv, env, args: self.return_tar(state, a, argv, env, False)
            with mock.patch.object(host, "unchanged_inputs"):
                result = host.execute(state, host.parser().parse_args([]))
            self.assertEqual(result["status"], "INCOMPLETE")
            self.assertEqual(result["guest_result"]["errors"], [{"code": "nonempty_journal"}])
            self.assertEqual(set(result["outputs"]), {"inspection/result.json"})

    def test_postcheck_backing_change_or_vm_failure_cannot_pass(self):
        for failed_vm in (False, True):
            with self.subTest(failed_vm=failed_vm), tempfile.TemporaryDirectory() as directory:
                state = self.state(Path(directory))
                state["prep"].supervise_vm = (mock.Mock(side_effect=RuntimeError("native helper failed")) if failed_vm else
                    lambda p, s, a, argv, env, args: self.return_tar(state, a, argv, env))
                final_check = None if failed_vm else ValueError("backing changed")
                with mock.patch.object(host, "unchanged_inputs", side_effect=[None, final_check]) as unchanged:
                    result = host.execute(state, host.parser().parse_args([]))
                self.assertEqual(result["status"], "INCOMPLETE")
                self.assertEqual(unchanged.call_count, 2)
                if failed_vm:
                    self.assertIn("native helper failed", result["error"])
                    self.assertTrue(result["full_backing_chain_unchanged"])
                else:
                    self.assertIn("backing changed", result["identity_error"])

    def test_claimed_guest_success_requires_fresh_policy_and_both_logs(self):
        cases = ((lambda result: result.update(inspection_nonce="0" * 32), None),
                 (lambda result: result.update(policy_sha256="0" * 64), None),
                 (None, "inspection/fsck-data.txt"))
        for mutate, omit in cases:
            with self.subTest(omit=omit, mutate=mutate), tempfile.TemporaryDirectory() as directory:
                state = self.state(Path(directory))
                state["prep"].supervise_vm = lambda p, s, a, argv, env, args: self.return_tar(
                    state, a, argv, env, mutate=mutate, omit=omit)
                with mock.patch.object(host, "unchanged_inputs"):
                    result = host.execute(state, host.parser().parse_args([]))
                self.assertEqual(result["guest_result"]["status"], "SAVED_FIRSTBOOT_INSPECTION_PASSED")
                self.assertEqual(result["status"], "INCOMPLETE")

    def test_lock_conflict_and_default_preflight_do_not_start_or_write(self):
        with tempfile.TemporaryDirectory() as directory:
            state = self.state(Path(directory))
            with (state["prep_work"] / "owner.lock").open("rb") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaisesRegex(ValueError, "still owned"):
                    with host.own_inspection(state):
                        self.fail("conflicting lock accepted")
            self.assertFalse(state["work"].exists())
            with mock.patch.object(host, "preflight", return_value=state), mock.patch.object(host, "execute") as execute, \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(host.main([]), 0)
            execute.assert_not_called()
            self.assertFalse(state["work"].exists())


if __name__ == "__main__":
    unittest.main()
