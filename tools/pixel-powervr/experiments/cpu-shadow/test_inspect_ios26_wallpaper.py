"""Offline saved-wallpaper adapter/collection tests; no guest, mount or phone."""
import contextlib
import fcntl
import io
import json
from pathlib import Path
import tarfile
import tempfile
import types
import unittest
from unittest import mock

import audit_ios26_partition_guest as auditor
import audit_ios26_apps as apps
import inspect_ios26_firstboot_guest as raw
import inspect_ios26_wallpaper as host
import inspect_ios26_wallpaper_guest as guest
import prepare_ios26 as prep
from test_audit_ios26_partition import CLEAN


def raw_result(policy, passed=True):
    return {"schema": 1, "kind": "ios26_saved_firstboot_inspection",
            "status": "SAVED_FIRSTBOOT_INSPECTION_PASSED" if passed else "INCOMPLETE",
            "errors": [] if passed else [{"code": "nonempty_journal"}], "cleanup_errors": [],
            "readonly_attachments": True, "raw_metadata_unchanged": passed,
            "mounted": False, "replayed": False, "repaired": False,
            "inspection_nonce": policy["inspection_nonce"], "policy_sha256": prep.digest(policy),
            "gpt": {"status": "PASSED", "disk_bytes": host.DISK_BYTES},
            "baseline_gpt": {"status": "PASSED", "disk_bytes": host.DISK_BYTES},
            "journals": {name: {"status": "PASSED", "journal": {"status": "PASSED", "state": "INITIALIZED_EMPTY"}}
                         for name in ("iOSRoot", "Data")},
            "fsck": {name: auditor.fsck_verdict(0, CLEAN) for name in ("iOSRoot", "Data")}}


class Adapter(unittest.TestCase):
    def policy(self):
        return {"schema": 1, "kind": "ios26_saved_wallpaper_inspection", "inspection_nonce": "1" * 32,
                "raw_guest_sha256": guest.RAW_SHA256, "partition_guest_sha256": guest.PARTITION_SHA256}

    def test_exact_reviewed_implementations_load(self):
        self.assertEqual(host.sha((Path(host.__file__).parent / "guard_ios26_wallpaper.py").read_bytes()), host.GUARD_SHA256)
        self.assertEqual(guest.sha(Path(raw.__file__).read_bytes()), guest.RAW_SHA256)
        self.assertEqual(guest.sha(Path(auditor.__file__).read_bytes()), guest.PARTITION_SHA256)
        self.assertTrue(callable(guest.load(raw.__file__, guest.RAW_SHA256).inspect_disks))

    def test_adapter_records_new_context_and_exact_raw_implementation(self):
        policy = self.policy()
        implementation = types.SimpleNamespace(inspect_disks=mock.Mock(return_value=raw_result(policy)))
        result = guest.inspect(implementation, auditor, "/dev/vda", "/dev/vdb", policy, Path("/authored/out"))
        implementation.inspect_disks.assert_called_once_with(auditor, "/dev/vda", "/dev/vdb", policy, Path("/authored/out"))
        self.assertEqual(result["kind"], "ios26_saved_wallpaper_inspection")
        self.assertEqual(result["status"], "SAVED_WALLPAPER_INSPECTION_PASSED")
        self.assertEqual(result["raw_implementation"]["returned_status"], "SAVED_FIRSTBOOT_INSPECTION_PASSED")
        self.assertEqual(result["raw_implementation"]["guest_sha256"], guest.RAW_SHA256)

    def test_nonempty_unknown_and_cleanup_failure_remain_incomplete(self):
        policy = self.policy()
        for code in ("nonempty_journal", "unsupported_journal_cursor", "detach_loop"):
            value = raw_result(policy, False)
            value["errors"] = [{"code": code}]
            implementation = types.SimpleNamespace(inspect_disks=lambda *args: value)
            result = guest.inspect(implementation, auditor, "current", "baseline", policy, Path("unused"))
            self.assertEqual(result["status"], "INCOMPLETE")
            self.assertEqual(result["errors"], [{"code": code}])

    def test_changed_dependency_never_executes_and_wrong_policy_never_delegates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "changed.py"
            path.write_text("raise AssertionError('must not execute unverified source')\n")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                guest.load(path, guest.RAW_SHA256)
        policy = self.policy()
        policy["raw_guest_sha256"] = "0" * 64
        implementation = types.SimpleNamespace(inspect_disks=mock.Mock())
        with self.assertRaisesRegex(ValueError, "policy mismatch"):
            guest.inspect(implementation, auditor, "current", "baseline", policy, Path("unused"))
        implementation.inspect_disks.assert_not_called()


class Collection(unittest.TestCase):
    def state(self, root):
        original = root / "prep"
        original.mkdir()
        (original / "owner.lock").touch()
        origin = Path(host.__file__).parent
        fake = types.SimpleNamespace(cold=types.SimpleNamespace(utc=prep.cold.utc, require_phone=mock.Mock(), subreaper=mock.Mock()),
            refuse_live_children=mock.Mock(), atomic_json=prep.atomic_json, digest=prep.digest, helper_command=prep.helper_command,
            safe_return_tar=prep.safe_return_tar, file_record=prep.file_record, vm_success=prep.vm_success, cleanup_signals=prep.cleanup_signals)
        return {"prep": fake, "auditor": auditor, "app": apps, "prep_work": original, "work": root / "inspection",
            "disk": original / "wallpaper.qcow2", "baseline": original / "gpu.qcow2", "receipt": {"authored": "fixture"},
            "bodies": {name: (origin / name).read_bytes() for name in host.SOURCES},
            "raw_body": Path(raw.__file__).read_bytes(), "partition_body": Path(auditor.__file__).read_bytes(),
            "plan": {"session": {"helper_ram_mib": 2048, "helper_vcpus": 4,
                                  "package": str(root / "package"), "tooling": str(root / "tools")}}}

    def returned(self, state, attempt, argv, env, passed=True, mutate=None, omit=None, native=True):
        policy = json.loads((attempt / "expected-policy.json").read_text())
        implementation = types.SimpleNamespace(inspect_disks=lambda *args: raw_result(policy, passed))
        result = guest.inspect(implementation, auditor, "current", "baseline", policy, Path("unused"))
        if mutate:
            mutate(result)
        files = {"inspection/result.json": json.dumps(result).encode()}
        if passed:
            files.update({"inspection/fsck-system.txt": CLEAN.encode(), "inspection/fsck-data.txt": CLEAN.encode()})
        if omit:
            del files[omit]
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for name, body in files.items():
                entry = tarfile.TarInfo(name)
                entry.size = len(body)
                archive.addfile(entry, io.BytesIO(body))
        with (attempt / "out.raw").open("r+b") as stream:
            stream.write(data.getvalue())
        for key in ("disk", "baseline"):
            drive = [arg for arg in argv if arg.startswith("file=" + str(state[key]) + ",")]
            self.assertEqual(len(drive), 1)
            self.assertIn("readonly=on", drive[0])
        self.assertEqual(env["ASOFT_NATIVE_EL0_REQUIRED"], "1")
        self.assertNotIn("ASOFT_NATIVE_EL0_TPIDRRO", env)
        return {"out_sizes": [len(data.getvalue())], "done_codes": [0], "natural_exit": True,
            "witnesses": {"native_initialization": True, "native_execution": native, "fatal_markers": []},
            "cleanup": {"exit_code": 0, "echild": True, "forced_qemu": False, "forced_descendants": [], "errors": []}}

    def test_actual_safe_tar_collection_keeps_original_records_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            state = self.state(Path(directory))
            before = {p.name: p.read_bytes() for p in state["prep_work"].iterdir()}
            state["prep"].supervise_vm = lambda p, s, a, argv, env, args: self.returned(state, a, argv, env)
            with mock.patch.object(host, "unchanged_inputs") as unchanged:
                result = host.execute(state, host.parser().parse_args([]))
            self.assertEqual(result["status"], "SAVED_WALLPAPER_INSPECTION_PASSED")
            self.assertEqual(unchanged.call_args_list, [mock.call(state, True), mock.call(state, True)])
            self.assertTrue((state["work"] / "a1/files/inspection/fsck-data.txt").is_file())
            self.assertEqual(before, {p.name: p.read_bytes() for p in state["prep_work"].iterdir()})

    def test_guest_classification_failure_is_retained_without_filesystem_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            state = self.state(Path(directory))
            state["prep"].supervise_vm = lambda p, s, a, argv, env, args: self.returned(state, a, argv, env, False)
            with mock.patch.object(host, "unchanged_inputs"):
                result = host.execute(state, host.parser().parse_args([]))
            self.assertEqual(result["status"], "INCOMPLETE")
            self.assertEqual(result["guest_result"]["errors"], [{"code": "nonempty_journal"}])
            self.assertEqual(set(result["outputs"]), {"inspection/result.json"})

    def test_claimed_success_requires_matching_nonce_policy_dependencies_and_both_logs(self):
        cases = ((lambda r: r.update(inspection_nonce="0" * 32), None),
                 (lambda r: r.update(policy_sha256="0" * 64), None),
                 (lambda r: r["raw_implementation"].update(guest_sha256="0" * 64), None),
                 (None, "inspection/fsck-data.txt"))
        for mutate, omit in cases:
            with self.subTest(omit=omit, mutate=mutate), tempfile.TemporaryDirectory() as directory:
                state = self.state(Path(directory))
                state["prep"].supervise_vm = lambda p, s, a, argv, env, args: self.returned(state, a, argv, env, mutate=mutate, omit=omit)
                with mock.patch.object(host, "unchanged_inputs"):
                    result = host.execute(state, host.parser().parse_args([]))
                self.assertEqual(result["guest_result"]["status"], "SAVED_WALLPAPER_INSPECTION_PASSED")
                self.assertEqual(result["status"], "INCOMPLETE")

    def test_native_failure_and_changed_backing_each_independently_refuse(self):
        for fail_native in (False, True):
            with self.subTest(fail_native=fail_native), tempfile.TemporaryDirectory() as directory:
                state = self.state(Path(directory))
                state["prep"].supervise_vm = lambda p, s, a, argv, env, args: self.returned(state, a, argv, env, native=not fail_native)
                final = None if fail_native else ValueError("authored backing identity failure")
                with mock.patch.object(host, "unchanged_inputs", side_effect=[None, final]) as unchanged:
                    result = host.execute(state, host.parser().parse_args([]))
                self.assertEqual(result["status"], "INCOMPLETE")
                self.assertEqual(unchanged.call_count, 2)
                if fail_native:
                    self.assertTrue(result["full_disk_chain_unchanged"])
                else:
                    self.assertIn("backing identity failure", result["identity_error"])

    def test_lock_conflict_creates_no_new_work(self):
        with tempfile.TemporaryDirectory() as directory:
            state = self.state(Path(directory))
            with (state["prep_work"] / "owner.lock").open("rb") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaisesRegex(ValueError, "another owner"):
                    with host.own_inspection(state):
                        self.fail("conflicting preparation accepted")
            self.assertFalse(state["work"].exists())

    def test_malformed_empty_descendant_boolean_cannot_grant_native_credit(self):
        with tempfile.TemporaryDirectory() as directory:
            state = self.state(Path(directory))
            def observed(p, s, a, argv, env, args):
                result = self.returned(state, a, argv, env)
                result["cleanup"]["forced_descendants"] = False
                self.assertTrue(prep.vm_success(result, True))
                return result
            state["prep"].supervise_vm = observed
            with mock.patch.object(host, "unchanged_inputs"):
                result = host.execute(state, host.parser().parse_args([]))
            self.assertEqual(result["status"], "INCOMPLETE")
            self.assertNotIn("outputs", result)


class PreflightRefusals(unittest.TestCase):
    def test_missing_arguments_or_weakened_bounds_create_nothing(self):
        with self.assertRaisesRegex(ValueError, "required"):
            host.preflight(host.parser().parse_args([]))
        for option, value in (("--min-available-mib", "511"), ("--min-free-mib", "1535"),
                              ("--inspection-seconds", "0"), ("--max-log-mib", "65")):
            with self.subTest(option=option), self.assertRaisesRegex(ValueError, "bounds"):
                host.preflight(host.parser().parse_args(["--guard-work", "/unused", "--work", "/unused-new", option, value]))

    def test_unapproved_guard_never_executes_or_creates_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            guarded = root / "guard"; guarded.mkdir()
            source = root / "unreviewed.py"
            source.write_text("raise AssertionError('must not execute')\n")
            prep.atomic_json(guarded / "guard-session.json", {"guard_source": str(source), "guard_source_sha256": host.sha(source.read_bytes())})
            for name in ("result.json", "guard-observations.json"):
                prep.atomic_json(guarded / name, {})
            with mock.patch.object(host, "module_from") as execute_source:
                with self.assertRaisesRegex(ValueError, "approved immutable"):
                    host.preflight(host.parser().parse_args(["--guard-work", str(guarded), "--work", str(root / "inspection")]))
                execute_source.assert_not_called()
            self.assertFalse((root / "inspection").exists())


if __name__ == "__main__":
    unittest.main()
