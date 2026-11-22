"""Firstboot counter/sync refusals through original checkpoint and cleanup code.

Only authored metadata/qcow headers and mocked VM/QMP I/O are used.
No guest, mount, GPU or phone operations occur.
"""
import contextlib
import copy
import io
import json
from pathlib import Path
import struct
import tempfile
import types
import unittest
from unittest import mock

import guard_ios26_firstboot as guard


def stats():
    return [{"device": "root", "node-name": "overlay", "qdev": "/machine/peripheral-anon/device[0]/virtio-backend",
             "stats": {"failed_wr_operations": 0, "failed_flush_operations": 0},
             "parent": {"node-name": "overlay-file", "stats": {"failed_wr_operations": 0, "failed_flush_operations": 0}},
             "backing": {"node-name": "partition", "stats": {"failed_wr_operations": 0, "failed_flush_operations": 0}}}]


def blocks():
    return [{"device": "root", "qdev": "/machine/peripheral-anon/device[0]/virtio-backend",
             "type": "unknown", "locked": False, "removable": False,
             "inserted": {"node-name": "overlay", "ro": False}}]


def default_floppy():
    return ({"device": "floppy0", "stats": {"failed_wr_operations": 0, "failed_flush_operations": 0}},
            {"device": "floppy0", "type": "unknown", "locked": False, "removable": True})


class CounterSchema(unittest.TestCase):
    def test_every_node_has_zero_typed_counters(self):
        result = guard.failed_io_counters(stats(), blocks())
        self.assertEqual(result["nodes_checked"], 3)
        self.assertTrue(result["failed_io_counters_zero"])
        self.assertFalse(result["stop_internal_flush_return_observed"])

    def test_missing_nonzero_wrong_types_and_nested_failures(self):
        bad = [None, {}, [], [stats()[0], stats()[0]], [{"stats": stats()[0]["stats"]}]]
        for key, value in (("failed_wr_operations", 1), ("failed_flush_operations", 1),
                           ("failed_wr_operations", -1), ("failed_wr_operations", False),
                           ("failed_flush_operations", "0"), ("failed_flush_operations", 0.0)):
            item = stats()
            item[0]["stats"][key] = value
            bad.append(item)
        for child in ("parent", "backing"):
            item = stats()
            item[0][child]["stats"]["failed_wr_operations"] = 1
            bad.append(item)
        item = stats()
        del item[0]["stats"]["failed_flush_operations"]
        bad.append(item)
        item = stats()
        item[0]["parent"] = None
        bad.append(item)
        for value in bad:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    guard.failed_io_counters(value, blocks())

    def test_cyclic_or_excessive_graph_is_not_followed(self):
        item = stats()
        item[0]["parent"] = item[0]
        with self.assertRaises(ValueError):
            guard.failed_io_counters(item, blocks())

    def test_observed_five_node_shape_needs_separate_empty_floppy_witness(self):
        # Authored projection of the saved 07-0002 reply. The query-block data
        # is synthetic: that failed attempt never issued query-block.
        returned, inventory = stats(), blocks()
        returned[0]["node-name"] = inventory[0]["inserted"]["node-name"] = "#block121"
        returned[0]["parent"]["node-name"] = "#block043"
        returned[0]["backing"]["node-name"] = "#block328"
        returned[0]["backing"]["parent"] = {"node-name": "#block252", "stats": {
            "failed_wr_operations": 0, "failed_flush_operations": 0}}
        floppy_stats, floppy_block = default_floppy()
        returned.append(floppy_stats); inventory.append(floppy_block)
        with self.assertRaises(ValueError):
            guard.failed_io_counters(returned, None)
        result = guard.failed_io_counters(returned, inventory)
        self.assertEqual(result["nodes_checked"], 5)
        self.assertEqual(result["backend_devices"], ["floppy0", "root"])
        self.assertTrue(result["empty_floppy0_confirmed"])
        self.assertEqual([row["location"] for row in result["nodes"]],
                         ["root", "root.parent", "root.backing", "root.backing.parent", "floppy0"])
        self.assertEqual(guard.failed_io_counters(list(reversed(returned)), list(reversed(inventory))), result)

    def test_only_one_root_and_the_known_optional_floppy_are_allowed(self):
        root, root_block = stats()[0], blocks()[0]
        floppy, floppy_block = default_floppy()
        bad = [(None, blocks()), (stats(), None), (stats(), []), ([floppy], [floppy_block]),
               ([root, root], [root_block, root_block]), ([root, floppy, floppy], [root_block, floppy_block]),
               (stats(), [root_block, floppy_block]), ([root, floppy], blocks()),
               ([root, dict(floppy, device="floppy1")], [root_block, dict(floppy_block, device="floppy1")]),
               ([root, dict(floppy, device="")], [root_block, dict(floppy_block, device="")])]
        for returned, inventory in bad:
            with self.subTest(returned=returned, inventory=inventory), self.assertRaises(ValueError):
                guard.failed_io_counters(returned, inventory)

    def test_floppy_cannot_hide_a_node_device_medium_or_wrong_typed_flag(self):
        mutations = [("stats", "node-name", "hidden"), ("stats", "qdev", "attached"),
                     ("stats", "parent", {}), ("stats", "backing", {}), ("stats", "driver-specific", {}),
                     ("block", "inserted", {}), ("block", "qdev", "attached"),
                     ("block", "locked", True), ("block", "removable", False),
                     ("block", "locked", 0), ("block", "removable", 1)]
        for target, key, value in mutations:
            returned, inventory = stats(), blocks()
            floppy_stats, floppy_block = default_floppy()
            (floppy_stats if target == "stats" else floppy_block)[key] = value
            returned.append(floppy_stats); inventory.append(floppy_block)
            with self.subTest(target=target, key=key, value=value), self.assertRaises(ValueError):
                guard.failed_io_counters(returned, inventory)

    def test_floppy_failed_counters_are_never_skipped(self):
        for name in ("failed_wr_operations", "failed_flush_operations"):
            for value in (1, -1, False, 0.0, "0", None):
                returned, inventory = stats(), blocks()
                floppy_stats, floppy_block = default_floppy()
                if value is None:
                    del floppy_stats["stats"][name]
                else:
                    floppy_stats["stats"][name] = value
                returned.append(floppy_stats); inventory.append(floppy_block)
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    guard.failed_io_counters(returned, inventory)

    def test_root_must_match_a_named_attached_writable_inserted_node(self):
        for mutate in (lambda s, b: s[0].pop("node-name"), lambda s, b: s[0].pop("qdev"),
                       lambda s, b: b[0].pop("inserted"), lambda s, b: b[0].update(qdev="other"),
                       lambda s, b: b[0]["inserted"].update(**{"node-name": "other"}),
                       lambda s, b: b[0]["inserted"].update(ro=True),
                       lambda s, b: b[0]["inserted"].update(ro=0)):
            returned, inventory = stats(), blocks()
            mutate(returned, inventory)
            with self.assertRaises(ValueError):
                guard.failed_io_counters(returned, inventory)


class FakeChild:
    def __init__(self):
        self.returncode = None
        self.pid = 99999999
        self.waited = False

    def poll(self):
        return self.returncode

    def wait(self, timeout):
        self.waited = True
        self.returncode = 0
        return 0


class GuardedCheckpoint(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.origin = Path(guard.__file__).parent
        self.hashes = {name: guard.sha((self.origin / name).read_bytes()) for name in guard.FROZEN}
        self.prep = guard.load_frozen(self.origin, self.hashes)
        self.patches = contextlib.ExitStack()
        self.patches.enter_context(mock.patch.object(self.prep.cold, "require_phone"))
        self.patches.enter_context(mock.patch.object(self.prep.cold, "subreaper"))
        self.reaped = self.patches.enter_context(mock.patch.object(self.prep.cold, "reap_owned",
            return_value={"echild": True, "forced_descendants": False}))
        self.patches.enter_context(mock.patch.object(self.prep, "recheck"))
        self.patches.enter_context(mock.patch.object(self.prep, "refuse_live_children"))
        self.patches.enter_context(mock.patch.object(self.prep.shutil, "disk_usage",
                                                     return_value=types.SimpleNamespace(free=64 << 30)))
        self.prep_work = self.root / "prep"
        self.prep_work.mkdir()
        (self.prep_work / "attempts").mkdir()
        (self.prep_work / "checkpoints").mkdir()
        (self.prep_work / "inputs").mkdir()
        self.session = {"schema": 1, "kind": "standalone_ios26_preparation", "runner_sources": self.hashes,
            "runtime": {"archive_sha256": "a" * 64, "header_sha256": "b" * 64},
            "qualification": {"qualification_sha256": "c" * 64}, "tooling_manifest_sha256": "d" * 64}
        self.prep.atomic_json(self.prep_work / "session.json", self.session)
        self.disk = self.prep_work / "inputs/root26g.qcow2"
        self.qcow(self.disk)
        self.disk_record = self.prep.file_record(self.disk, self.prep_work)
        self.prefix = list(self.prep.stages.STAGES[:self.prep.stages.STAGES.index(guard.STAGE)])
        previous = None
        for stage in self.prefix:
            path = self.prep_work / "checkpoints" / (stage + ".json")
            self.prep.atomic_json(path, {"schema": 1, "stage": stage, "status": "STAGE_COMPLETE",
                "session_sha256": self.prep.digest(self.session), "previous_sha256": previous,
                "artifacts": {"root26g.qcow2": self.disk_record} if stage == "ios26-partition" else {}})
            previous = self.prep.cold.sha(path)
        self.old_checkpoints = {p.name: p.read_bytes() for p in (self.prep_work / "checkpoints").iterdir()}
        self.plan = {"work": str(self.prep_work), "session": self.session, "completed": self.prefix[:],
            "remaining": [guard.STAGE], "through": guard.STAGE, "network_stages": [],
            "guest_boot_stages": [guard.STAGE], "helper_smoke": False, "artifacts": {"root26g.qcow2": self.disk_record}}
        self.audit_work, self.auditor_dir = self.root / "audit", self.root / "auditor"
        self.make_audit()
        audit = guard.audit_identity(self.prep, self.audit_work, self.auditor_dir, self.session,
                                    self.plan, self.prep_work, self.origin)
        self.source = self.root / "guard-source.py"
        self.source.write_bytes(Path(guard.__file__).read_bytes())
        self.receipt = {"schema": 1, "guard_source_sha256": guard.sha(self.source.read_bytes()),
            "prep_session_sha256": guard.sha((self.prep_work / "session.json").read_bytes()),
            "runner_dir": str(self.origin), "frozen_sources": self.hashes, "partition_audit": audit,
            "frozen_input_identities": {"root26g.qcow2": self.prep.cold.readonly_identity(self.disk)}}
        self.state = {"prep": self.prep, "prep_work": self.prep_work, "plan": self.plan,
            "runner_args": self.prep.parser().parse_args(["--allow-guest-boots"]), "work": self.root / "guard-output",
            "receipt": self.receipt, "source": self.source, "events": [], "supervision": []}
        self.response, self.block_response, self.sync, self.query_error = stats(), blocks(), True, None
        self.block_query_error = None
        self.change_source_at_query = False
        self.calls, self.children, self.transcripts = [], [], []

        def qmp_call(qmp, name, seconds):
            self.calls.append(name)
            row = {"request": {"execute": name, "id": len(self.calls)}}
            qmp.transcript.append(row)
            if name == "query-blockstats":
                if self.query_error:
                    raise self.query_error
                answer = self.response
                if self.change_source_at_query:
                    self.source.write_bytes(b"changed authored guard source")
            elif name == "query-block":
                if self.block_query_error:
                    raise self.block_query_error
                answer = self.block_response
            else:
                answer = {}
            row["response"] = {"return": answer, "id": len(self.calls)}
            return answer
        self.patches.enter_context(mock.patch.object(self.prep.cold.Qmp, "call", qmp_call))
        self.patches.enter_context(mock.patch.object(self.prep.cold.Qmp, "close"))

        def delegate_supervision(plan, stage, attempt, argv, env, args, frame=None):
            child = FakeChild()
            self.children.append(child)
            qmp = object.__new__(self.prep.cold.Qmp)
            qmp.transcript = []
            self.transcripts.append(qmp.transcript)
            # Real frozen shutdown + success predicate, with synthetic I/O only.
            cleanup = self.prep.cold.shutdown(child, qmp)
            result = {"stage": stage, "cleanup": cleanup, "qmp": qmp.transcript,
                "guest_sync_answered": self.sync, "milestone": True, "settled": True,
                "witnesses": {"native_initialization": True, "native_execution": True, "fatal_markers": []}}
            result["status"] = "VM_OBSERVATION_COMPLETE" if self.prep.vm_success(result, False) else "INCOMPLETE"
            self.prep.atomic_json(attempt / "vm-result.json", result)
            if result["status"] != "VM_OBSERVATION_COMPLETE":
                raise RuntimeError("original frozen VM success predicate refused")
            return result
        self.patches.enter_context(mock.patch.object(self.prep, "supervise_vm", delegate_supervision))

        def guest_stage(plan, stage, attempt, args):
            argv, env = ["authored-mocked-vm"], {"ASOFT_NATIVE_EL0_REQUIRED": "1"}
            self.prep.atomic_json(attempt / "launch.json", {"command": argv, "environment": env})
            self.prep.supervise_vm(plan, stage, attempt, argv, env, args, (1, None))
            self.qcow(attempt / "files/root26g.qcow2")
            return ["root26g.qcow2"]
        self.patches.enter_context(mock.patch.object(self.prep, "guest_stage", guest_stage))

    def tearDown(self):
        self.patches.close()
        self.temp.cleanup()

    @staticmethod
    def qcow(path):
        header = bytearray(104)
        header[:4] = b"QFI\xfb"
        struct.pack_into(">I", header, 4, 3)
        struct.pack_into(">Q", header, 24, 51_541_704_704)
        path.write_bytes(header)

    def make_audit(self):
        self.audit_work.mkdir()
        self.auditor_dir.mkdir()
        for name in guard.AUDITOR:
            (self.auditor_dir / name).write_bytes(b"# authored audit-source fixture\n")
        files = self.audit_work / "a1/files/audit"
        files.mkdir(parents=True)
        text = "authored unfiltered fsck fixture\n"
        guest = {"status": "PARTITION_AUDIT_PASSED", "readonly_attachment": True, "errors": [], "cleanup_errors": [],
                 "data_copy": {"status": "PASSED", "errors": []}, "fsck": {n: {
                     "status": "PASSED", "exit_code": 0, "diagnostic_sha256": guard.sha(text.encode())} for n in ("iOSRoot", "Data")}}
        self.prep.atomic_json(files / "result.json", guest)
        for name in ("fsck-system.txt", "fsck-data.txt"):
            (files / name).write_text(text)
        audited = {"schema": 1, "kind": "standalone_ios26_partition_audit", "readonly": True,
            "native_required": True, "tcg_retry": False, "prep_work": str(self.prep_work), "runner_dir": str(self.origin),
            "prep_session_sha256": guard.sha((self.prep_work / "session.json").read_bytes()),
            "frozen_runner_sources": self.hashes, "runtime": self.session["runtime"],
            "qualification_sha256": self.session["qualification"]["qualification_sha256"],
            "tooling_manifest_sha256": self.session["tooling_manifest_sha256"],
            "auditor_sources": {n: guard.sha((self.auditor_dir / n).read_bytes()) for n in guard.AUDITOR},
            "checkpoints": {str(self.prep_work / "checkpoints" / n): guard.sha(b) for n, b in self.old_checkpoints.items()},
            "disk": self.disk_record, "disk_identity": self.prep.cold.readonly_identity(self.disk)}
        self.prep.atomic_json(self.audit_work / "audit-session.json", audited)
        result = {"schema": 1, "status": "PARTITION_AUDIT_PASSED", "session_sha256": self.prep.digest(audited),
            "disk_unchanged": True, "preparation_records_unchanged": True, "natural_exit": True,
            "cleanup": {"exit_code": 0, "echild": True, "errors": [], "forced_qemu": False, "forced_descendants": False},
            "native_witnesses": {"native_initialization": True, "native_execution": True, "fatal_markers": []},
            "guest_result": guest, "outputs": {"audit/" + n: self.prep.file_record(files / n, self.audit_work)
                for n in ("result.json", "fsck-system.txt", "fsck-data.txt")}}
        self.prep.atomic_json(self.audit_work / "result.json", result)

    def assert_failure_clean(self, result):
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertFalse(result["checkpoint_accepted_by_guard"])
        self.assertFalse((self.prep_work / "checkpoints/ios26-firstboot.json").exists())
        self.assertTrue(all(child.waited for child in self.children))
        self.reaped.assert_called()
        self.assertEqual(self.calls[-1], "quit")
        for name, before in self.old_checkpoints.items():
            self.assertEqual((self.prep_work / "checkpoints" / name).read_bytes(), before)

    def test_zero_counters_sync_and_unchanged_inputs_allow_original_checkpoint(self):
        original_call, original_supervisor = self.prep.cold.Qmp.call, self.prep.supervise_vm
        result = guard.execute(self.state)
        self.assertEqual(result["status"], "GUARDED_FIRSTBOOT_COMPLETE")
        self.assertTrue(result["checkpoint_accepted_by_guard"])
        self.assertEqual(self.calls, ["stop", "query-blockstats", "query-block", "quit"])
        self.assertEqual(self.transcripts[0][1]["response"]["return"], self.response)
        self.assertEqual(self.transcripts[0][2]["response"]["return"], self.block_response)
        self.assertEqual(result["actual_attempt"]["launch.json"]["command"], ["authored-mocked-vm"])
        self.assertIs(self.prep.cold.Qmp.call, original_call)
        self.assertIs(self.prep.supervise_vm, original_supervisor)
        self.assertFalse(result["boot_complete"])
        self.assertFalse(result["gpu_path_complete"])

    def test_failed_write_counters_prevent_original_checkpoint_and_still_reap(self):
        self.response[0]["stats"]["failed_wr_operations"] = 1
        result = guard.execute(self.state)
        self.assert_failure_clean(result)
        vm = result["actual_attempt"]["vm-result.json"]
        self.assertFalse(vm["cleanup"]["stop_flushed"])
        self.assertTrue(vm["cleanup"]["errors"])
        self.assertEqual(self.calls, ["stop", "query-blockstats", "query-block", "quit"])

    def test_nested_failed_flush_prevents_original_checkpoint(self):
        self.response[0]["backing"]["stats"]["failed_flush_operations"] = 1
        self.assert_failure_clean(guard.execute(self.state))

    def test_missing_or_malformed_stats_prevent_original_checkpoint(self):
        self.response = []
        self.assert_failure_clean(guard.execute(self.state))

    def test_stats_timeout_preserves_quit_and_reap(self):
        self.query_error = TimeoutError("authored query timeout")
        self.assert_failure_clean(guard.execute(self.state))

    def test_block_identity_timeout_preserves_stats_quit_and_reap(self):
        self.block_query_error = TimeoutError("authored block inventory timeout")
        result = guard.execute(self.state)
        self.assert_failure_clean(result)
        self.assertEqual(self.calls, ["stop", "query-blockstats", "query-block", "quit"])
        self.assertEqual(result["post_stop_blockstats"][0]["post_stop_blockstats"], self.response)
        self.assertNotIn("post_stop_blocks", result["post_stop_blockstats"][0])

    def test_confirmed_empty_default_floppy_allows_original_checkpoint(self):
        floppy_stats, floppy_block = default_floppy()
        self.response.append(floppy_stats); self.block_response.append(floppy_block)
        result = guard.execute(self.state)
        self.assertEqual(result["status"], "GUARDED_FIRSTBOOT_COMPLETE")
        self.assertTrue(result["post_stop_blockstats"][0]["counter_check"]["empty_floppy0_confirmed"])

    def test_floppy_failed_counter_refuses_checkpoint_and_still_reaps(self):
        floppy_stats, floppy_block = default_floppy()
        floppy_stats["stats"]["failed_flush_operations"] = 1
        self.response.append(floppy_stats); self.block_response.append(floppy_block)
        self.assert_failure_clean(guard.execute(self.state))

    def test_inserted_floppy_medium_refuses_checkpoint_and_still_reaps(self):
        floppy_stats, floppy_block = default_floppy()
        floppy_block["inserted"] = {"node-name": "unexpected-medium", "ro": True}
        self.response.append(floppy_stats); self.block_response.append(floppy_block)
        self.assert_failure_clean(guard.execute(self.state))

    def test_missing_sync_refuses_after_original_vm_completion_before_checkpoint(self):
        self.sync = False
        result = guard.execute(self.state)
        self.assert_failure_clean(result)
        self.assertEqual(result["actual_attempt"]["vm-result.json"]["status"], "VM_OBSERVATION_COMPLETE")
        self.assertEqual(result["supervision"][0]["status"], "INCOMPLETE")

    def test_changed_bound_source_during_stats_prevents_checkpoint(self):
        self.change_source_at_query = True
        result = guard.execute(self.state)
        self.assert_failure_clean(result)
        self.assertIn("guard source changed", result["identity_error"])

    def test_changed_audit_source_refuses_before_work_or_launch(self):
        (self.auditor_dir / guard.AUDITOR[1]).write_text("changed source\n")
        with self.assertRaisesRegex(ValueError, "auditor source changed"):
            guard.execute(self.state)
        self.assertFalse(self.state["work"].exists())
        self.assertEqual(self.calls, [])

    def test_changed_audit_result_cannot_be_adopted(self):
        path = self.audit_work / "result.json"
        result = json.loads(path.read_text())
        result["status"] = "INCOMPLETE"
        self.prep.atomic_json(path, result)
        with self.assertRaisesRegex(ValueError, "audit/preparation record changed"):
            guard.execute(self.state)
        self.assertFalse(self.state["work"].exists())

    def test_audit_raw_result_must_match_success_receipt(self):
        path = self.audit_work / "a1/files/audit/result.json"
        path.write_text("{}\n")
        with self.assertRaises(ValueError):
            guard.audit_identity(self.prep, self.audit_work, self.auditor_dir, self.session,
                                 self.plan, self.prep_work, self.origin)

    def test_existing_firstboot_or_future_stage_is_never_noop_success(self):
        for completed, remaining in ((self.prefix + [guard.STAGE], []),
                                      (self.prefix, [guard.STAGE, "ios26-persona"])):
            plan = dict(self.plan, completed=completed, remaining=remaining)
            with self.assertRaisesRegex(ValueError, "exactly the partition boundary"):
                guard.require_boundary(self.prep, plan)
        (self.prep_work / "checkpoints/ios26-firstboot.json").write_text("{}\n")
        with self.assertRaisesRegex(ValueError, "boundary changed"):
            guard.execute(self.state)
        self.assertFalse(self.state["work"].exists())

    def test_guard_receipt_write_failure_still_calls_quit_and_blocks_checkpoint(self):
        original = guard.observations
        def fail_first_stop_receipt(state):
            if state["events"] and not state.get("failed_test_write"):
                state["failed_test_write"] = True
                raise OSError("authored guard receipt write failure")
            return original(state)
        with mock.patch.object(guard, "observations", fail_first_stop_receipt):
            self.assert_failure_clean(guard.execute(self.state))

    def test_post_commit_collection_failure_does_not_adopt_or_delete_checkpoint(self):
        with mock.patch.object(guard, "collect_attempt", side_effect=ValueError("authored late collection failure")):
            result = guard.execute(self.state)
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertFalse(result["checkpoint_accepted_by_guard"])
        self.assertTrue(result["original_firstboot_checkpoint_present"])
        self.assertTrue((self.prep_work / "checkpoints/ios26-firstboot.json").is_file())
        self.assertEqual(self.calls, ["stop", "query-blockstats", "query-block", "quit"])


class NoAction(unittest.TestCase):
    def test_default_missing_inputs_does_not_execute(self):
        with mock.patch.object(guard, "execute") as execute, contextlib.redirect_stdout(io.StringIO()) as captured:
            self.assertEqual(guard.main([]), 2)
        execute.assert_not_called()
        self.assertEqual(json.loads(captured.getvalue())["status"], "INCOMPLETE")

    def test_mismatched_frozen_source_never_imports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in guard.FROZEN:
                (root / name).write_text("raise AssertionError('never execute mismatched bytes')\n")
            with self.assertRaisesRegex(ValueError, "frozen source hash mismatch"):
                guard.load_frozen(root, {name: "0" * 64 for name in guard.FROZEN})


if __name__ == "__main__":
    unittest.main()
