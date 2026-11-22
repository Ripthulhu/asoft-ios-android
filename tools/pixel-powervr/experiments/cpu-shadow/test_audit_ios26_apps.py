"""Authored host fixtures only: no mounts, VM, phone, downloads or Apple bytes."""
import builtins
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import plistlib
import shutil
import stat
import struct
import tarfile
import tempfile
import types
import unittest
from unittest import mock

import audit_ios26_apps as host
import audit_ios26_apps_guest as guest
import audit_ios26_partition_guest as auditor
import guard_ios26_firstboot as guard
import inspect_ios26_firstboot as inspector_host
import inspect_ios26_firstboot_guest as inspector_guest
import prepare_ios26 as prep
from test_audit_ios26_partition import CLEAN
from test_inspect_ios26_firstboot import RawDisk, journal_header


PAYLOAD = b"authored application fixture\n"
VERSION_BODY = plistlib.dumps({"ProductBuildVersion": "23G90", "ProductVersion": "26.6.2", "Fixture": True})


def file(path, body=PAYLOAD, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    path.chmod(mode)


class OwnershipView(guest.Tree):
    """Only lstat ownership is virtualized; reads, modes and links are real."""
    def __init__(self, root, new=(), changes=None):
        super().__init__(root)
        self.new, self.changes = set(new), changes or {}

    def inventory(self, budget):
        result = super().inventory(budget)
        for path, node in result.items():
            node.update(uid=0, gid=0)
            if path in self.new:
                node["gid"] = 80
            node.update(self.changes.get(path, {}))
        return result

    def checksum(self, path, expected):
        # The ownership transformations above are tested by the comparator;
        # the file descriptor check still binds actual host inode/size/bytes.
        return super().checksum(path, guest.metadata(self.lstat(path)))


class AppCopy(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source, self.before, self.after = (self.root / n for n in ("source", "before", "after"))
        for path in (self.source, self.before, self.after):
            path.mkdir(mode=0o755)
        for path in (self.before, self.after):
            file(path / "Existing.app/file")
            os.link(path / "Existing.app/file", path / "Existing.app/hard")
            file(path / "ordinary-marker", b"old top-level entry")
        file(self.source / "Existing.app/file", b"source differs: predecessor must be preserved")
        for path in (self.source, self.after):
            file(path / "New.app/file")
            os.link(path / "New.app/file", path / "New.app/hard")
            file(path / "New.app/empty", b"")
            os.symlink("../../../../outside", path / "New.app/escape")
            os.symlink("file", path / "New.app/link")
        (self.after / "New.app").chmod(0o775)
        for name in guest.SKIP:
            file(self.source / name / "not-copied", b"authored excluded bundle")

    def tearDown(self):
        self.temp.cleanup()

    def run_compare(self, changes=None, new=("New.app",)):
        with OwnershipView(self.source) as source, OwnershipView(self.before) as before, \
                OwnershipView(self.after, new, changes) as after:
            return guest.compare_apps(source, before, after)

    def test_full_copy_preservation_and_exact_two_skips(self):
        result = self.run_compare()
        self.assertEqual(result["status"], "PASSED")
        self.assertEqual(result["new_bundles"], ["New.app"])
        self.assertEqual(result["preserved_source_name_matches"], ["Existing.app"])
        self.assertEqual(set(result["explicit_source_skips"]), guest.SKIP)
        self.assertEqual(result["new_files"], 3)
        self.assertEqual(result["hardlink_groups"], 2)
        self.assertFalse(result["global_nlink_compared"])

    def test_same_size_same_mtime_content_change_is_detected(self):
        path = self.after / "New.app/file"
        before = path.stat()
        path.write_bytes(b"x" * len(PAYLOAD))
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertIn("file_contents", {e["code"] for e in self.run_compare()["errors"]})

    def test_missing_extra_and_unexpected_skipped_bundle_fail(self):
        (self.after / "New.app/empty").unlink()
        file(self.after / "New.app/unexpected")
        file(self.after / "AppleVisionProApp.app/file")
        result = self.run_compare()
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual({e["code"] for e in result["errors"]}, {"missing_entry", "unexpected_entry"})

    def test_existing_skipped_bundle_is_preserved(self):
        for path in (self.before, self.after):
            file(path / "AppleVisionProApp.app/old")
        self.assertEqual(self.run_compare()["status"], "PASSED")
        (self.after / "AppleVisionProApp.app/old").write_bytes(b"changed")
        self.assertEqual(self.run_compare()["status"], "INCOMPLETE")

    def test_existing_apps_are_checked_against_predecessor_not_source(self):
        (self.after / "Existing.app/file").write_bytes((self.source / "Existing.app/file").read_bytes())
        self.assertEqual(self.run_compare()["status"], "INCOMPLETE")

    def test_owner_mode_root_and_nested_changes_fail(self):
        for changes in ({"New.app": {"gid": 0}}, {"New.app/file": {"uid": 501}},
                        {"New.app/link": {"gid": 80}}, {"Existing.app": {"mode": 0o775}},
                        {"": {"uid": 501}}):
            with self.subTest(changes=changes):
                self.assertIn("entry_metadata", {e["code"] for e in self.run_compare(changes)["errors"]})
        (self.after / "New.app").chmod(0o755)
        self.assertEqual(self.run_compare()["status"], "INCOMPLETE")

    def test_setid_new_files_and_directories_are_explicitly_unsupported(self):
        for relative in ("New.app", "New.app/file"):
            path = self.source / relative
            before = stat.S_IMODE(path.stat().st_mode)
            path.chmod(before | 0o2000)
            with self.subTest(relative=relative), self.assertRaisesRegex(guest.AppsError, "source_setid"):
                self.run_compare()
            path.chmod(before)

    def test_dangling_destination_and_source_root_symlink_are_refused(self):
        shutil.rmtree(self.after / "New.app")
        os.symlink("missing", self.after / "New.app")
        with self.assertRaisesRegex(guest.AppsError, "destination_bundle_not_directory"):
            self.run_compare()
        (self.after / "New.app").unlink()
        shutil.rmtree(self.source / "New.app")
        os.symlink("Existing.app", self.source / "New.app")
        with self.assertRaisesRegex(guest.AppsError, "source_bundle_name_or_type"):
            self.run_compare()

    def test_source_unknown_names_and_special_nodes_fail(self):
        for name in ("-option.app", ".hidden.app", "unexpected.txt"):
            file(self.source / name / "file")
            with self.subTest(name=name), self.assertRaisesRegex(guest.AppsError, "source_bundle_name_or_type"):
                self.run_compare()
            shutil.rmtree(self.source / name)
        os.mkfifo(self.source / "New.app/fifo")
        with self.assertRaisesRegex(guest.AppsError, "unsupported_entry_type"):
            self.run_compare()

    def test_symlink_text_is_preserved_without_following_escaping_target(self):
        self.assertEqual(self.run_compare()["status"], "PASSED")
        link = self.after / "New.app/escape"
        link.unlink()
        os.symlink("/different-target", link)
        self.assertIn("symlink_text", {e["code"] for e in self.run_compare()["errors"]})

    def test_missing_required_hardlink_is_not_waived_by_equal_bytes(self):
        path = self.after / "New.app/hard"
        path.unlink()
        file(path)
        self.assertIn("hardlink_relationships", {e["code"] for e in self.run_compare()["errors"]})

    def test_cross_bundle_source_links_are_split_by_copy_invocation(self):
        for root in (self.source, self.after):
            (root / "Another.app").mkdir()
        os.link(self.source / "New.app/file", self.source / "Another.app/file")
        file(self.after / "Another.app/file")
        (self.after / "Another.app").chmod(0o775)
        self.assertEqual(self.run_compare(new=("New.app", "Another.app"))["status"], "PASSED")
        (self.after / "Another.app/file").unlink()
        os.link(self.after / "New.app/file", self.after / "Another.app/file")
        result = self.run_compare(new=("New.app", "Another.app"))
        self.assertIn("hardlink_relationships", {e["code"] for e in result["errors"]})

    def test_cross_alias_to_preexisting_file_is_rejected(self):
        for name in ("file", "hard"):
            path = self.after / "New.app" / name
            path.unlink()
            os.link(self.after / "Existing.app/file", path)
        self.assertIn("hardlink_relationships", {e["code"] for e in self.run_compare()["errors"]})

    def test_source_and_predecessor_external_nlink_counts_are_not_compared(self):
        os.link(self.before / "Existing.app/file", self.root / "outside-predecessor")
        os.link(self.source / "New.app/file", self.root / "outside-source")
        self.assertEqual(self.run_compare()["status"], "PASSED")

    def test_linked_symlinks_are_refused_in_source_preexisting_and_current(self):
        for tree, bundle in ((self.source, "New.app"), (self.before, "Existing.app"), (self.after, "Existing.app")):
            first, second = tree / bundle / "linked-sym", tree / bundle / "linked-sym-alias"
            os.symlink("file", first)
            os.link(first, second, follow_symlinks=False)
            self.assertEqual(first.lstat().st_nlink, 2)
            with self.subTest(tree=tree.name), self.assertRaisesRegex(guest.AppsError, "linked_symlink_unsupported"):
                self.run_compare()
            second.unlink(); first.unlink()

    def test_no_new_copy_reports_preservation_without_new_copy_credit(self):
        shutil.rmtree(self.source / "New.app")
        shutil.rmtree(self.after / "New.app")
        result = self.run_compare(new=())
        self.assertEqual(result["status"], "PASSED")
        self.assertFalse(result["new_copy_exercised"])
        self.assertEqual(result["new_files"], 0)


class ReadOnlyTree(unittest.TestCase):
    def test_parent_symlink_and_final_symlink_cannot_be_read_as_regular(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file(root / "real/data")
            os.symlink("real", root / "alias")
            os.symlink("real/data", root / "file-alias")
            with guest.Tree(root) as tree:
                for path in ("alias/data", "file-alias"):
                    with self.subTest(path=path), self.assertRaises(OSError):
                        tree.read(path)
                for path in ("../real/data", "real/../real/data"):
                    with self.assertRaises(guest.AppsError):
                        tree.read(path)

    def test_entry_depth_and_byte_bounds_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file(root / "a/b/c")
            with guest.Tree(root) as tree:
                for name, value in (("MAX_ENTRIES", 2), ("MAX_DEPTH", 1), ("MAX_BYTES", 2)):
                    with self.subTest(name=name), mock.patch.object(guest, name, value), self.assertRaises(guest.AppsError):
                        tree.inventory(guest.Budget())

    def test_exact_version_plist_bytes_and_types(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "System/Library/CoreServices/SystemVersion.plist"
            file(path, VERSION_BODY)
            with guest.Tree(root) as tree:
                result = guest.version_identity(tree)
                self.assertEqual(result["sha256"], guest.sha(VERSION_BODY))
                for body in (b"not a plist", plistlib.dumps({"ProductBuildVersion": "23G91", "ProductVersion": "26.6.2"}),
                             plistlib.dumps({"ProductBuildVersion": 23, "ProductVersion": "26.6.2"})):
                    path.write_bytes(body)
                    with self.assertRaises(guest.AppsError):
                        guest.version_identity(tree)

    def test_repeated_directory_identity_is_refused_without_global_nlink_comparison(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "child").mkdir()
            original_fstat, original_stat = os.fstat, os.stat
            identity = root.stat().st_ino
            def alias(st):
                if not stat.S_ISDIR(st.st_mode): return st
                result = list(st); result[1] = identity
                return os.stat_result(result)
            with guest.Tree(root) as tree, mock.patch.object(guest.os, "fstat", side_effect=lambda fd: alias(original_fstat(fd))), \
                    mock.patch.object(guest.os, "stat", side_effect=lambda *a, **kw: alias(original_stat(*a, **kw))), \
                    self.assertRaisesRegex(guest.AppsError, "directory_alias_unsupported"):
                tree.inventory(guest.Budget())


class JournalAndMountPolicy(unittest.TestCase):
    def fixture(self, initialized=False):
        disk = RawDisk(initialized)
        start, sectors, _ = auditor.PARTITIONS[0]
        base, size = start * 512, sectors * 512
        approved = inspector_guest.inspect_volume(disk, RawDisk(), base, size)
        return disk, base, size, approved

    def test_needinit_journal_can_survive_legitimate_linux_header_updates(self):
        disk, base, size, approved = self.fixture()
        disk.change(base + 1024 + 20, b"\x01")
        result = guest.inspect_journal(inspector_guest, disk, base, size, approved)
        self.assertEqual(result["journal"]["state"], "AUTHORED_UNINITIALIZED_JOURNAL_PRESERVED")
        self.assertFalse(result["journal"]["whole_volume_unchanged_claimed"])

    def test_changed_nonempty_or_dirty_journal_state_is_refused(self):
        for variant in ("nonempty", "jib", "dirty"):
            disk, base, size, approved = self.fixture(True)
            offset = base + approved["journal_info"]["offset"]
            if variant == "nonempty":
                disk.change(offset, journal_header(end=1024))
            elif variant == "jib":
                disk.change(base + approved["journal_info"]["jib_offset"] + 80, b"x")
            else:
                disk.change(base + 1024 + 4, struct.pack(">I", 1 << 13))
            with self.subTest(variant=variant), self.assertRaises((guest.AppsError, inspector_guest.InspectionError)):
                guest.inspect_journal(inspector_guest, disk, base, size, approved)

    def test_apfs_options_are_exact_and_do_not_guess_foreground_or_lax_flags(self):
        self.assertEqual(guest.apfs_command(Path("source.dmg"), Path("os")),
                         ["apfs-fuse", "-o", "ro,nosuid,nodev,noexec,allow_other", "source.dmg", "os"])

    def test_real_mountinfo_shape_requires_readonly_and_expected_filesystem(self):
        line = "40 1 0:42 / /owned/os ro,nosuid,nodev,noexec,relatime - fuse.apfs-fuse apfs-fuse rw,user_id=0,group_id=0\n"
        with mock.patch.object(Path, "read_text", return_value=line):
            self.assertEqual(guest.readonly_mount(Path("/owned/os"), "apfs")["type"], "fuse.apfs-fuse")
        for bad in (line.replace("ro,nosuid", "rw,nosuid"), line.replace("fuse.apfs-fuse", "ext4"),
                    line + line, line.replace("apfs-fuse rw", "unexpected rw")):
            with mock.patch.object(Path, "read_text", return_value=bad), self.assertRaises(guest.AppsError):
                guest.readonly_mount(Path("/owned/os"), "apfs")


def native_result():
    # Exact cleanup shape observed in the preserved physical helper result.
    return {"natural_exit": True,
            "cleanup": {"exit_code": 0, "echild": True, "errors": [], "forced_qemu": False, "forced_descendants": []},
            "native_witnesses": {"native_initialization": True, "native_execution": True, "fatal_markers": []}}


class NativeGate(unittest.TestCase):
    def test_actual_empty_descendant_list_passes(self):
        host.require_native(native_result())

    def test_false_missing_forced_unclean_or_non_native_cannot_pass(self):
        for section, name, value in (("cleanup", "forced_descendants", False), ("cleanup", "forced_descendants", [123]),
                ("cleanup", "forced_descendants", None), ("cleanup", "echild", False), ("cleanup", "forced_qemu", True),
                ("cleanup", "exit_code", 1), ("native_witnesses", "native_execution", False),
                ("native_witnesses", "fatal_markers", ["fatal"])):
            result = native_result()
            result[section][name] = value
            with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                host.require_native(result)
        result = native_result()
        result["natural_exit"] = False
        with self.assertRaises(ValueError):
            host.require_native(result)


def checkpoint_fixture(root):
    (root / "checkpoints").mkdir()
    session, previous = {"authored": "session"}, None
    for index, stage in enumerate(prep.stages.STAGES[:prep.stages.STAGES.index(host.STAGE) + 1]):
        name = "root26g.qcow2" if stage in ("ios26-partition", "ios26-firstboot", "ios26-persona") else stage + ".fixture"
        row = {"schema": 1, "status": "STAGE_COMPLETE", "stage": stage, "session_sha256": prep.digest(session),
               "previous_sha256": previous, "artifacts": {name: {"path": str(index) + "/artifact", "bytes": 1, "sha256": "0" * 64}}}
        path = root / "checkpoints" / (stage + ".json")
        prep.atomic_json(path, row)
        previous = prep.cold.sha(path)
    return session


class PrefixAndBacking(unittest.TestCase):
    def test_exact_apps_boundary_and_earlier_artifact_versions_remain_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inventory = host.checkpoint_inventory(prep, root, checkpoint_fixture(root))
            firstboot = host.prefix_inventory(inventory, "ios26-firstboot")
            partition = host.prefix_inventory(inventory, "ios26-partition")
            self.assertEqual(firstboot["artifacts"]["root26g.qcow2"]["path"], "7/artifact")
            self.assertEqual(partition["artifacts"]["root26g.qcow2"]["path"], "6/artifact")
            self.assertEqual(inventory["artifacts"]["root26g.qcow2"]["path"], "8/artifact")
            self.assertEqual(len(firstboot["hashes"]), 8)
            (root / "checkpoints/ios26-gpu.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "exactly"):
                host.checkpoint_inventory(prep, root, {"authored": "session"})

    def test_broken_checkpoint_link_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = checkpoint_fixture(root)
            path = root / "checkpoints/ios26-persona.json"
            row = json.loads(path.read_text()); row["previous_sha256"] = "1" * 64
            prep.atomic_json(path, row)
            with self.assertRaisesRegex(ValueError, "checkpoint chain"):
                host.checkpoint_inventory(prep, root, session)

    def chain(self, root):
        rows, artifacts, last = {}, {}, None
        pairs = (("ios26-partition", "root26g.qcow2"), ("ios26-firstboot", "root26g.qcow2"),
                 ("ios26-persona", "root26g.qcow2"), ("ios26-activation", "root26-activation.qcow2"),
                 (host.STAGE, "root26-apps.qcow2"))
        for index, (stage, logical) in enumerate(pairs):
            name = str(index) + ".qcow2"
            body = bytearray(131072); body[:4] = b"QFI\xfb"
            backing = b"" if last is None else last.encode()
            struct.pack_into(">IQI", body, 4, 3, 104 if backing else 0, len(backing))
            struct.pack_into(">Q", body, 24, host.DISK_BYTES)
            body[104:104 + len(backing)] = backing
            (root / name).write_bytes(body)
            record = prep.file_record(root / name, root)
            rows[stage] = {"artifacts": {logical: record}}
            artifacts[logical] = record
            last = name
        file(root / "original.dmg", b"authored non-Apple source image fixture")
        source = prep.file_record(root / "original.dmg", root)
        rows["ios26-decrypt"] = {"artifacts": {host.OS_LOGICAL: source}}
        artifacts[host.OS_LOGICAL] = source
        return {"rows": rows, "artifacts": artifacts}

    def test_every_actual_backing_member_and_os_is_hashed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); inventory = self.chain(root)
            self.assertEqual(len(host.full_inputs(prep, root, inventory)), 6)
            target = root / "0.qcow2"; before = target.stat()
            with target.open("r+b") as stream:
                stream.seek(100000); stream.write(b"x")
            os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
            with self.assertRaisesRegex(ValueError, "full input/backing"):
                host.full_inputs(prep, root, inventory)

    def test_changed_backing_names_and_original_os_are_rejected(self):
        for mutation in ("chain", "source"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); inventory = self.chain(root)
                if mutation == "chain":
                    inventory["rows"][host.STAGE]["artifacts"]["root26-apps.qcow2"]["backing_chain"].pop()
                else:
                    (root / "original.dmg").write_bytes(b"different authored source")
                with self.assertRaises(ValueError):
                    host.full_inputs(prep, root, inventory)


def approved_journal():
    start, sectors, _ = auditor.PARTITIONS[0]
    return inspector_guest.inspect_volume(RawDisk(), RawDisk(), start * 512, sectors * 512)


def passing_guest(policy):
    start, sectors, _ = auditor.PARTITIONS[0]
    journal = guest.inspect_journal(inspector_guest, RawDisk(), start * 512, sectors * 512,
                                    policy["approved_system_journal"])
    version = {"status": "PASSED", "build": "23G90", "version": "26.6.2",
               "path": "System/Library/CoreServices/SystemVersion.plist", "bytes": len(VERSION_BODY),
               "sha256": guest.sha(VERSION_BODY)}
    mounts = {n: {"root": "/", "options": ["ro", "nosuid", "nodev", "noexec"],
                  "type": "hfsplus", "device": "7:1", "source": "/dev/loop1"} for n in ("activation", "apps")}
    mounts["os"] = dict(mounts["apps"], type="fuse.apfs-fuse", source="apfs-fuse")
    return {"schema": 1, "kind": "ios26_apps_copy_audit", "status": "APP_COPY_AUDIT_PASSED",
            "errors": [], "cleanup_errors": [], "readonly_inputs": True, "raw_metadata_unchanged": True,
            "replayed": False, "repaired": False, "audit_nonce": policy["audit_nonce"], "policy_sha256": prep.digest(policy),
            "readonly_mounts": mounts, "systems": {n: copy.deepcopy(version) for n in ("os", "activation", "apps")},
            "gpt": {n: {"status": "PASSED", "disk_bytes": host.DISK_BYTES} for n in ("activation", "apps")},
            "journals": {n: copy.deepcopy(journal) for n in ("activation", "apps")},
            "fsck": {n: auditor.fsck_verdict(0, CLEAN) for n in ("activation", "apps")},
            "comparison": {"status": "PASSED", "errors": [], "source_bundles": 1, "checked_files": 1,
                           "unexplained_entries_allowed": False, "global_nlink_compared": False,
                           "comparison_sha256": guest.sha(PAYLOAD)}}


class HostCollection(unittest.TestCase):
    def state(self, root):
        source = Path(host.__file__).parent
        original = root / "prep"
        original.mkdir(); (original / "owner.lock").touch()
        fake = types.SimpleNamespace(cold=types.SimpleNamespace(utc=prep.cold.utc, require_phone=mock.Mock(), subreaper=mock.Mock()),
            refuse_live_children=mock.Mock(), atomic_json=prep.atomic_json, digest=prep.digest,
            helper_command=prep.helper_command, safe_return_tar=prep.safe_return_tar, file_record=prep.file_record,
            vm_success=prep.vm_success, cleanup_signals=prep.cleanup_signals)
        dependencies = {"partition_guest_sha256": host.sha(Path(auditor.__file__).read_bytes()),
                        "firstboot_guest_sha256": host.sha(Path(inspector_guest.__file__).read_bytes())}
        return {"prep": fake, "guest": guest, "auditor": auditor, "prep_work": original, "work": root / "audit",
                "apps": original / "apps.qcow2", "activation": original / "activation.qcow2", "os": original / "original.dmg",
                "receipt": {"dependency_sources": dependencies, "prior_evidence": {"approved_system_journal": approved_journal()}},
                "inventory": {"artifacts": {host.OS_LOGICAL: {"bytes": 1024}}},
                "bodies": {n: (source / n).read_bytes() for n in host.SOURCES},
                "partition_body": Path(auditor.__file__).read_bytes(), "firstboot_body": Path(inspector_guest.__file__).read_bytes(),
                "plan": {"session": {"helper_ram_mib": 2048, "helper_vcpus": 4,
                                      "package": str(root / "package"), "tooling": str(root / "tools")}}}

    def return_tar(self, state, attempt, argv, env, mutate=None, omit=None, vm_mutate=None):
        policy = json.loads((attempt / "expected-policy.json").read_text())
        result = passing_guest(policy)
        if mutate:
            mutate(result)
        files = {"apps-audit/result.json": json.dumps(result).encode(), "apps-audit/fsck-activation.txt": CLEAN.encode(),
                 "apps-audit/fsck-apps.txt": CLEAN.encode(), "apps-audit/apfs-mount.txt": guest.APFS_LOG_HEADER}
        if omit:
            del files[omit]
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for name, body in files.items():
                item = tarfile.TarInfo(name); item.size = len(body)
                archive.addfile(item, io.BytesIO(body))
        with (attempt / "out.raw").open("r+b") as stream:
            stream.write(data.getvalue())
        for name in ("apps", "activation", "os"):
            drive = [arg for arg in argv if arg.startswith("file=" + str(state[name]) + ",")]
            self.assertEqual(len(drive), 1)
            self.assertIn("readonly=on", drive[0])
        self.assertEqual(env["ASOFT_NATIVE_EL0_REQUIRED"], "1")
        self.assertNotIn("ASOFT_NATIVE_EL0_TPIDRRO", env)
        native = native_result()
        vm = {"out_sizes": [len(data.getvalue())], "done_codes": [0], "natural_exit": True,
              "witnesses": native["native_witnesses"], "cleanup": native["cleanup"]}
        if vm_mutate:
            vm_mutate(vm)
        return vm

    def test_owned_success_extracts_real_tar_and_preserves_original(self):
        with tempfile.TemporaryDirectory() as directory:
            state = self.state(Path(directory))
            before = {p.name: p.read_bytes() for p in state["prep_work"].iterdir()}
            state["prep"].supervise_vm = lambda p, s, a, argv, env, args: self.return_tar(state, a, argv, env)
            with mock.patch.object(host, "unchanged_inputs") as unchanged:
                result = host.execute(state, host.parser().parse_args([]))
            self.assertEqual(result["status"], "APP_COPY_AUDIT_PASSED")
            self.assertEqual(set(result["outputs"]), host.OUTPUTS)
            self.assertEqual(unchanged.call_args_list, [mock.call(state, True), mock.call(state, True)])
            self.assertEqual(before, {p.name: p.read_bytes() for p in state["prep_work"].iterdir()})
            self.assertEqual(json.loads((state["work"] / "a1/apps-audit-result.json").read_text()), result)

    def test_claimed_pass_with_wrong_policy_writable_mount_or_missing_log_fails(self):
        cases = ((lambda r: r.update(audit_nonce="0" * 32), None),
                 (lambda r: r.update(policy_sha256="0" * 64), None),
                 (lambda r: r["readonly_mounts"]["os"].update(options=["rw"]), None),
                 (lambda r: r["comparison"].update(errors=[{"code": "file_contents"}]), None),
                 (lambda r: r["systems"]["os"].update(sha256="0" * 64), None),
                 (None, "apps-audit/fsck-apps.txt"), (None, "apps-audit/apfs-mount.txt"))
        for mutate, omit in cases:
            with self.subTest(omit=omit), tempfile.TemporaryDirectory() as directory:
                state = self.state(Path(directory))
                state["prep"].supervise_vm = lambda p, s, a, argv, env, args: self.return_tar(state, a, argv, env, mutate, omit)
                with mock.patch.object(host, "unchanged_inputs"):
                    result = host.execute(state, host.parser().parse_args([]))
                self.assertEqual(result["status"], "INCOMPLETE")
                self.assertIn("guest_result", result)

    def test_vm_failure_and_final_backing_change_are_independent_refusals(self):
        for failed_vm in (False, True):
            with self.subTest(failed_vm=failed_vm), tempfile.TemporaryDirectory() as directory:
                state = self.state(Path(directory))
                state["prep"].supervise_vm = (mock.Mock(side_effect=RuntimeError("authored helper failure")) if failed_vm else
                    lambda p, s, a, argv, env, args: self.return_tar(state, a, argv, env))
                with mock.patch.object(host, "unchanged_inputs", side_effect=[None, None if failed_vm else ValueError("backing changed")]):
                    result = host.execute(state, host.parser().parse_args([]))
                self.assertEqual(result["status"], "INCOMPLETE")
                if failed_vm:
                    self.assertTrue(result["full_input_chains_unchanged"])
                    self.assertIn("authored helper failure", result["error"])
                else:
                    self.assertIn("backing changed", result["identity_error"])

    def test_forced_or_non_native_helper_does_not_grant_output_credit(self):
        for mutation in (lambda v: v.update(natural_exit=False), lambda v: v["cleanup"].update(forced_descendants=[123]),
                         lambda v: v["witnesses"].update(native_execution=False), lambda v: v.update(done_codes=[1])):
            with tempfile.TemporaryDirectory() as directory:
                state = self.state(Path(directory))
                state["prep"].supervise_vm = lambda p, s, a, argv, env, args: self.return_tar(state, a, argv, env, vm_mutate=mutation)
                with mock.patch.object(host, "unchanged_inputs"):
                    result = host.execute(state, host.parser().parse_args([]))
                self.assertEqual(result["status"], "INCOMPLETE")
                self.assertNotIn("outputs", result)

    def test_busy_original_lock_creates_no_audit_directory(self):
        import fcntl
        with tempfile.TemporaryDirectory() as directory:
            state = self.state(Path(directory))
            with (state["prep_work"] / "owner.lock").open("rb") as stream:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaisesRegex(ValueError, "owned"):
                    with host.own_audit(state):
                        self.fail("busy lock accepted")
            self.assertFalse(state["work"].exists())


class SavedInspectionPrefix(unittest.TestCase):
    """Exercise new prefix glue with unchanged reviewed primitive verifiers."""
    def fixture(self, root):
        work, inspection, guard_work = root / "prep", root / "inspection", root / "guard"
        for path in (work, inspection, guard_work): path.mkdir()
        checkpoint_fixture(work)
        session = {"authored": "session", "runner_sources": {"frozen": "hash"}, "runtime": {"archive": "authored"},
                   "tooling_manifest_sha256": "t" * 64, "qualification": {"qualification_sha256": "q" * 64}}
        prep.atomic_json(work / "session.json", session)
        # The new glue receives a verified inventory; exact file-chain parsing
        # and actual disk hashing are exercised separately above.
        inventory = host.checkpoint_inventory(prep, work, {"authored": "session"})
        firstboot = host.prefix_inventory(inventory, "ios26-firstboot")
        partition = host.prefix_inventory(inventory, "ios26-partition")
        source = Path(host.__file__).parent
        audit_source = root / "partition-source"
        audit_source.mkdir()
        audit_hashes = {}
        for name in ("audit_ios26_partition.py", "audit_ios26_partition_guest.py"):
            shutil.copyfile(source / name, audit_source / name)
            audit_hashes[name] = prep.cold.sha(audit_source / name)
        audit = {"work": str(root / "partition-audit"), "source_directory": str(audit_source), "files": {},
                 "checkpoints": partition["hashes"], "source_hashes": audit_hashes}
        (root / "partition-audit").mkdir()
        guard_receipt = {"partition_audit": audit, "frozen_input_identities": {}}
        guard_result = {"checkpoint": {"path": str(work / "checkpoints/ios26-firstboot.json"), "sha256": "authored"}}
        for name, value in (("guard-session.json", guard_receipt), ("result.json", guard_result), ("guard-observations.json", {})):
            prep.atomic_json(guard_work / name, value)
        bound = {str(guard_work / name): prep.cold.sha(guard_work / name) for name in ("guard-session.json", "result.json", "guard-observations.json")}
        chain = [{"record": {"path": "immutable-firstboot"}}]
        receipt = {"schema": 1, "kind": "ios26_saved_firstboot_inspection", "prep_work": str(work), "runner_dir": str(source),
            "prep_session_sha256": prep.cold.sha(work / "session.json"), "frozen_sources": session["runner_sources"],
            "guard_work": str(guard_work), "guard_source": str(source / "guard_ios26_firstboot.py"),
            "guard_files": bound, "guard_checkpoint": guard_result["checkpoint"], "partition_audit": audit,
            "checkpoints": firstboot["hashes"], "runtime": session["runtime"], "tooling_manifest_sha256": session["tooling_manifest_sha256"],
            "qualification_sha256": session["qualification"]["qualification_sha256"], "readonly": True,
            "mounts_allowed": False, "replay_allowed": False, "repair_allowed": False, "native_required": True, "tcg_retry": False,
            "backing_chain": chain, "source_directory": str(source),
            "partition_guest_source": str(audit_source / "audit_ios26_partition_guest.py"),
            "partition_guest_sha256": host.APPROVED["audit_ios26_partition_guest.py"],
            "inspector_sources": {n: host.APPROVED[n] for n in ("inspect_ios26_firstboot.py", "inspect_ios26_firstboot_guest.py")}}
        prep.atomic_json(inspection / "inspection-session.json", receipt)
        attempt = inspection / "a1"; attempt.mkdir(); (attempt / "files/inspection").mkdir(parents=True)
        policy = {"inspection_nonce": "1" * 32, "inspection_session_sha256": prep.digest(receipt),
                  "partition_guest_sha256": receipt["partition_guest_sha256"]}
        raw = {"schema": 1, "kind": "ios26_saved_firstboot_inspection", "status": "SAVED_FIRSTBOOT_INSPECTION_PASSED",
            "errors": [], "cleanup_errors": [], "readonly_attachments": True, "raw_metadata_unchanged": True,
            "mounted": False, "replayed": False, "repaired": False, "inspection_nonce": policy["inspection_nonce"],
            "policy_sha256": prep.digest(policy), "gpt": {"status": "PASSED", "disk_bytes": host.DISK_BYTES},
            "baseline_gpt": {"status": "PASSED", "disk_bytes": host.DISK_BYTES},
            "journals": {n: approved_journal() for n in ("iOSRoot", "Data")},
            "fsck": {n: auditor.fsck_verdict(0, CLEAN) for n in ("iOSRoot", "Data")}}
        prep.atomic_json(attempt / "files/inspection/result.json", raw)
        for n in ("system", "data"): (attempt / ("files/inspection/fsck-" + n + ".txt")).write_text(CLEAN)
        prep.atomic_json(attempt / "expected-policy.json", policy)
        prep.atomic_json(attempt / "launch.json", {"command": ["authored helper"]})
        native = native_result()
        vm = {"natural_exit": True, "witnesses": native["native_witnesses"], "cleanup": native["cleanup"], "done_codes": [0], "out_sizes": [1]}
        prep.atomic_json(attempt / "vm-result.json", vm)
        result = {"schema": 1, "status": "SAVED_FIRSTBOOT_INSPECTION_PASSED", "inspection_session_sha256": prep.digest(receipt),
            "full_backing_chain_unchanged": True, "preparation_and_guard_unchanged": True, **native,
            "attempt": str(attempt), "guest_result": raw,
            "launch": {"path": str(attempt / "launch.json"), "sha256": prep.cold.sha(attempt / "launch.json")},
            "outputs": {"inspection/" + n: prep.file_record(attempt / "files/inspection" / n, inspection)
                        for n in ("result.json", "fsck-system.txt", "fsck-data.txt")}}
        prep.atomic_json(inspection / "result.json", result)
        prep.atomic_json(attempt / "inspection-result.json", result)
        fake_inspector = types.SimpleNamespace(guard_acceptance=mock.Mock(return_value=bound), full_chain=mock.Mock(return_value=chain),
                                              guest_pass=inspector_host.guest_pass)
        fake_guard = types.SimpleNamespace(audit_identity=mock.Mock(return_value=audit))
        return [fake_inspector, fake_guard, prep, inspection, receipt, result, inventory, {"work": str(work)}, session]

    def test_success_uses_old_prefix_while_current_boundary_remains_apps(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.fixture(Path(directory))
            result = host.saved_inspection(*args)
            passed_prefix = args[0].guard_acceptance.call_args.args[6]
            self.assertEqual(passed_prefix["completed"][-1], "ios26-firstboot")
            self.assertEqual(passed_prefix["artifacts"]["root26g.qcow2"]["path"], "7/artifact")
            old_plan = args[1].audit_identity.call_args.args[4]
            self.assertEqual(old_plan["completed"][-1], "ios26-partition")
            self.assertEqual(args[6]["completed"][-1], host.STAGE)
            self.assertEqual(result["approved_system_journal"], approved_journal())

    def test_later_prefix_failed_receipt_or_changed_prior_output_is_not_adopted(self):
        for kind in ("prefix", "status", "raw", "missing-log"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                args = self.fixture(Path(directory))
                if kind == "prefix": args[4]["checkpoints"] = args[6]["hashes"]
                elif kind == "status": args[5]["status"] = "INCOMPLETE"
                elif kind == "raw": (args[3] / "a1/files/inspection/result.json").write_text("{}")
                else: (args[3] / "a1/files/inspection/fsck-data.txt").unlink()
                with self.assertRaises((ValueError, FileNotFoundError)):
                    host.saved_inspection(*args)

    def test_old_partition_host_source_is_rechecked_after_collection(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.fixture(Path(directory))
            prior = host.saved_inspection(*args)
            source = Path(host.__file__).parent
            work = Path(args[4]["prep_work"])
            receipt = {"prep_session_sha256": prep.cold.sha(work / "session.json"),
                       "runner_dir": str(source), "frozen_sources": {}, "checkpoints": args[6]["hashes"],
                       "prior_evidence": prior, "script_files": {}, "source_directory": str(source),
                       "auditor_sources": {n: prep.cold.sha(source / n) for n in host.SOURCES}, "input_chains": []}
            state = {"prep": prep, "receipt": receipt, "prep_work": work, "plan": {"session": args[8]}}
            with mock.patch.object(host, "checkpoint_inventory", return_value=args[6]):
                host.unchanged_inputs(state, False)
                old_host = Path(args[4]["partition_audit"]["source_directory"]) / "audit_ios26_partition.py"
                old_host.write_bytes(old_host.read_bytes() + b"\n")
                with self.assertRaisesRegex(ValueError, "bound prerequisite evidence/source"):
                    host.unchanged_inputs(state, False)


class GuestProcedure(unittest.TestCase):
    def run_guest(self, writable=False, fsck_bad=False, apfs_rw=False, cleanup_bad=False):
        class Disk(RawDisk):
            def close(self): pass
        class FakeTree:
            def __init__(self, *args, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def lstat(self, name): return types.SimpleNamespace(st_mode=stat.S_IFDIR)
            def child(self, name): return FakeTree()
        calls, mounts, loops = [], {}, {}
        disks = {"/dev/vda": Disk(), "/dev/vdb": Disk()}

        def command(argv, *args, **kwargs):
            calls.append(argv)
            if argv[:2] == ["blockdev", "--getro"]:
                return "0" if writable and argv[2] == "/dev/vdc" else "1"
            if argv[:2] == ["blockdev", "--getsize64"]:
                return str(1024 if argv[2] == "/dev/vdc" else loops.get(argv[2], auditor.DISK_BYTES))
            if argv[0] == "losetup" and "--find" in argv:
                self.assertIn("--read-only", argv)
                loop = "/dev/loop" + str(len(loops))
                loops[loop] = int(argv[argv.index("--sizelimit") + 1])
                return loop
            if argv[0] == "mount":
                self.assertEqual(argv[:5], ["mount", "-t", "hfsplus", "-o", "ro,nosuid,nodev,noexec"])
                mounts[argv[-1]] = {"root": "/", "options": ["ro", "nosuid", "nodev", "noexec"],
                                    "type": "hfsplus", "device": "7:0", "source": argv[-2]}
                return ""
            if argv[0] in ("umount", "fusermount"):
                if cleanup_bad and argv[0] == "fusermount":
                    raise auditor.AuditError("authored_cleanup_failure")
                mounts.pop(argv[-1], None)
                return ""
            if argv[:2] == ["losetup", "--detach"]:
                return ""
            self.fail("unreviewed or mutating command: " + repr(argv))

        def process(argv, **kwargs):
            calls.append(argv)
            self.assertEqual(kwargs["stdin"], guest.subprocess.DEVNULL)
            self.assertEqual(kwargs["preexec_fn"], guest.bounded_log)
            if argv[0] == "fsck.hfsplus":
                self.assertEqual(argv[:3], ["fsck.hfsplus", "-f", "-n"])
                kwargs["stdout"].write((CLEAN + ("No checking performed\n" if fsck_bad else "")).encode())
            elif argv[0] == "apfs-fuse":
                self.assertEqual(argv, guest.apfs_command(Path(argv[-2]), Path(argv[-1])))
                mounts[argv[-1]] = {"root": "/", "options": ["rw" if apfs_rw else "ro", "nosuid", "nodev", "noexec"],
                                    "type": "fuse.apfs-fuse", "device": "0:42", "source": "apfs-fuse"}
            else:
                self.fail("unreviewed subprocess: " + repr(argv))
            return types.SimpleNamespace(returncode=0)

        original_open, original_stat, original_resolve = builtins.open, os.stat, Path.resolve
        def raw_open(path, *args, **kwargs):
            if path in disks:
                self.assertEqual(args, ("rb",))
                self.assertEqual(kwargs, {"buffering": 0})
                return disks[path]
            return original_open(path, *args, **kwargs)
        def device_stat(path, *args, **kwargs):
            if str(path).startswith(("/dev/vd", "/dev/loop")):
                return types.SimpleNamespace(st_mode=stat.S_IFBLK, st_rdev=os.makedev(7, 0))
            return original_stat(path, *args, **kwargs)
        version = {"status": "PASSED", "path": "System/Library/CoreServices/SystemVersion.plist",
                   "build": "23G90", "version": "26.6.2", "bytes": len(VERSION_BODY), "sha256": guest.sha(VERSION_BODY)}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def owned_workspace(**kwargs):
                path = root / "owned-mounts"; path.mkdir(); return str(path)
            with mock.patch.object(auditor, "command", side_effect=command), mock.patch.object(auditor, "ensure_unmounted"), \
                    mock.patch.object(guest.subprocess, "run", side_effect=process), mock.patch("builtins.open", side_effect=raw_open), \
                    mock.patch.object(guest.os, "stat", side_effect=device_stat), \
                    mock.patch.object(Path, "resolve", lambda p, **kwargs: p if str(p).startswith("/dev/vd") else original_resolve(p, **kwargs)), \
                    mock.patch.object(guest, "mounted_at", side_effect=lambda target: mounts.get(str(target))), \
                    mock.patch.object(guest.tempfile, "mkdtemp", side_effect=owned_workspace), mock.patch.object(guest, "Tree", FakeTree), \
                    mock.patch.object(guest, "version_identity", return_value=version), \
                    mock.patch.object(guest, "compare_apps", return_value={"status": "PASSED"}):
                result = guest.audit_disks(auditor, inspector_guest, "/dev/vda", "/dev/vdb", "/dev/vdc",
                    {"schema": 1, "audit_nonce": "1" * 32, "os_bytes": 1024, "approved_system_journal": approved_journal()}, root)
            if not writable and not fsck_bad:
                self.assertTrue((root / "apfs-mount.txt").read_bytes().startswith(guest.APFS_LOG_HEADER))
            self.assertFalse((root / "owned-mounts").exists())
        return result, calls

    def test_actual_journal_checks_and_readonly_commands_complete_with_cleanup(self):
        result, calls = self.run_guest()
        self.assertEqual(result["status"], "APP_COPY_AUDIT_PASSED")
        fscks = [i for i, argv in enumerate(calls) if argv[0] == "fsck.hfsplus"]
        mounts = [i for i, argv in enumerate(calls) if argv[0] == "mount"]
        self.assertEqual(len(fscks), 2)
        self.assertLess(max(fscks), min(mounts))
        self.assertEqual(len([c for c in calls if c[:2] == ["losetup", "--detach"]]), 2)

    def test_writable_input_or_unclean_fsck_prevents_all_mounts(self):
        for mode in ("writable", "fsck_bad"):
            result, calls = self.run_guest(**{mode: True})
            self.assertEqual(result["status"], "INCOMPLETE")
            self.assertFalse(any(c[0] in ("mount", "apfs-fuse") for c in calls))

    def test_writable_apfs_or_failed_unmount_cannot_pass(self):
        for mode in ("apfs_rw", "cleanup_bad"):
            result, calls = self.run_guest(**{mode: True})
            self.assertEqual(result["status"], "INCOMPLETE")
            self.assertTrue(any(c[0] == "fusermount" for c in calls))
            self.assertEqual(len([c for c in calls if c[:2] == ["losetup", "--detach"]]), 2)
            if mode == "cleanup_bad":
                self.assertIn("unmount_apfs", result["cleanup_errors"])


if __name__ == "__main__":
    unittest.main()
