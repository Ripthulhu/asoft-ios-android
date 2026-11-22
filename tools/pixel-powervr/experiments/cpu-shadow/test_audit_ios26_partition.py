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
            "data_copy": {"status": "PASSED", "errors": [], "checked_unchanged_files": 1},
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
