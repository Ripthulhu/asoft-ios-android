"""Offline wallpaper checkpoint/cleanup and immutable ancestry tests."""
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

import guard_ios26_firstboot as first
import guard_ios26_wallpaper as guard
import audit_ios26_apps as apps
import audit_ios26_apps_guest as apps_guest
import audit_ios26_partition_guest as auditor
import prepare_ios26 as prep_module
from test_audit_ios26_apps import approved_journal, passing_guest, native_result, CLEAN
from test_guard_ios26_firstboot import FakeChild, stats, blocks, default_floppy


def qcow(path, backing=None):
    body = bytearray(131072)
    body[:4] = b"QFI\xfb"
    name = str(backing).encode() if backing else b""
    struct.pack_into(">IQI", body, 4, 3, 104 if name else 0, len(name))
    struct.pack_into(">Q", body, 24, guard.DISK_BYTES)
    body[104:104 + len(name)] = name
    path.write_bytes(body)


class WallpaperCheckpoint(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        source = Path(first.__file__).parent
        hashes = {name: first.sha((source / name).read_bytes()) for name in first.FROZEN}
        self.prep = first.load_frozen(source, hashes)
        self.patches = contextlib.ExitStack()
        for module, name in ((self.prep.cold, "require_phone"), (self.prep.cold, "subreaper"),
                             (self.prep, "recheck"), (self.prep, "refuse_live_children")):
            self.patches.enter_context(mock.patch.object(module, name))
        self.reaped = self.patches.enter_context(mock.patch.object(self.prep.cold, "reap_owned",
            return_value={"echild": True, "forced_descendants": []}))
        self.patches.enter_context(mock.patch.object(self.prep.shutil, "disk_usage", return_value=types.SimpleNamespace(free=64 << 30)))
        self.work = self.root / "prep"
        self.work.mkdir()
        for name in ("attempts", "checkpoints", "inputs"):
            (self.work / name).mkdir()
        session = {"schema": 1, "kind": "standalone_ios26_preparation", "runner_sources": hashes}
        self.prep.atomic_json(self.work / "session.json", session)
        previous_disk, per_stage = None, {}
        for index, (stage, logical) in enumerate(guard.DISKS[:6]):
            path = self.work / "inputs" / (str(index) + ".qcow2")
            qcow(path, previous_disk)
            per_stage[stage] = {logical: self.prep.file_record(path, self.work)}
            previous_disk = path
        self.tc = self.work / "inputs/gpu.tc"
        self.tc.write_bytes(b"authored trustcache fixture")
        per_stage[guard.PREDECESSOR]["root26-gpu.tc"] = self.prep.file_record(self.tc, self.work)
        before = list(self.prep.stages.STAGES[:self.prep.stages.STAGES.index(guard.STAGE)])
        previous, artifacts = None, {}
        for stage in before:
            row = {"schema": 1, "stage": stage, "status": "STAGE_COMPLETE", "session_sha256": self.prep.digest(session),
                   "previous_sha256": previous, "artifacts": per_stage.get(stage, {})}
            path = self.work / "checkpoints" / (stage + ".json")
            self.prep.atomic_json(path, row)
            previous = self.prep.cold.sha(path)
            artifacts.update(row["artifacts"])
        self.plan = {"work": str(self.work), "session": session, "completed": before, "remaining": [guard.STAGE],
            "through": guard.STAGE, "network_stages": [], "guest_boot_stages": [guard.STAGE], "helper_smoke": False,
            "artifacts": artifacts}
        inventory = guard.checkpoint_inventory(self.prep, self.work, session, guard.PREDECESSOR)
        source_copy = self.root / "wallpaper-guard-source.py"
        source_copy.write_bytes(Path(guard.__file__).read_bytes())
        self.evidence = self.root / "app-audit-metadata.json"
        self.evidence.write_text('{"authored":"receipt fixture"}\n')
        receipt = {"guard_source": str(source_copy), "guard_source_sha256": guard.sha(source_copy.read_bytes()),
            "prep_session_sha256": self.prep.cold.sha(self.work / "session.json"), "runner_dir": str(source),
            "frozen_sources": hashes, "bound_files": {str(self.evidence): self.prep.cold.sha(self.evidence)},
            "checkpoints": inventory["hashes"], "input_disk_chain": guard.full_disks(self.prep, self.work, inventory),
            "prior_input_chains": [], "input_identities": {n: self.prep.cold.readonly_identity(self.prep.source_path(self.plan, n)) for n in artifacts}}
        self.state = {"prep": self.prep, "firstguard": first, "prep_work": self.work, "plan": self.plan,
            "runner_args": self.prep.parser().parse_args(["--allow-guest-boots"]), "work": self.root / "guard",
            "receipt": receipt, "events": [], "supervision": []}
        self.old = {p.name: p.read_bytes() for p in (self.work / "checkpoints").iterdir()}
        self.response, self.query_error, self.sync = stats(), None, True
        self.block_response, self.block_query_error = blocks(), None
        self.gpu, self.frame, self.settled, self.milestone = True, True, True, True
        self.calls, self.children = [], []
        self.change_evidence = False

        def qmp_call(qmp, name, seconds):
            self.calls.append(name)
            row = {"request": {"execute": name, "id": len(self.calls)}}
            qmp.transcript.append(row)
            if name == "query-blockstats":
                if self.query_error:
                    raise self.query_error
                value = self.response
                if self.change_evidence:
                    self.evidence.write_text("changed authored evidence")
            elif name == "query-block":
                if self.block_query_error:
                    raise self.block_query_error
                value = self.block_response
            else:
                value = {}
            row["response"] = {"return": value, "id": len(self.calls)}
            return value
        self.patches.enter_context(mock.patch.object(self.prep.cold.Qmp, "call", qmp_call))
        self.patches.enter_context(mock.patch.object(self.prep.cold.Qmp, "close"))

        def supervise(plan, stage, attempt, argv, env, args, frame=None):
            child = FakeChild()
            self.children.append(child)
            qmp = object.__new__(self.prep.cold.Qmp)
            qmp.transcript = []
            cleanup = self.prep.cold.shutdown(child, qmp)
            result = {"stage": stage, "cleanup": cleanup, "qmp": qmp.transcript, "guest_sync_answered": self.sync,
                "milestone": self.milestone, "settled": self.settled,
                "witnesses": {"native_initialization": True, "native_execution": True, "fatal_markers": [],
                              "gpu_execution": self.gpu, "frame_captured": self.frame}}
            result["status"] = "VM_OBSERVATION_COMPLETE" if self.prep.vm_success(result, False) else "INCOMPLETE"
            self.prep.atomic_json(attempt / "vm-result.json", result)
            if result["status"] != "VM_OBSERVATION_COMPLETE":
                raise RuntimeError("original wallpaper acceptance refused")
            return result
        self.patches.enter_context(mock.patch.object(self.prep, "supervise_vm", supervise))

        def stage(plan, name, attempt, args):
            self.prep.atomic_json(attempt / "launch.json", {"command": ["authored mocked wallpaper", "-device", "virtio-blk-pci,drive=root"], "environment": {}})
            self.prep.supervise_vm(plan, name, attempt, [], {}, args, (1, None))
            qcow(attempt / "files/root.qcow2", self.prep.source_path(plan, "root26-gpu.qcow2"))
            (attempt / "files/root.tc").write_bytes(self.tc.read_bytes())
            return ["root.qcow2", "root.tc"]
        self.patches.enter_context(mock.patch.object(self.prep, "guest_stage", stage))

    def tearDown(self):
        self.patches.close()
        self.temp.cleanup()

    def failure_clean(self, result):
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertFalse(result["checkpoint_accepted_by_guard"])
        self.assertFalse((self.work / "checkpoints/ios26-wallpaper.json").exists())
        self.assertEqual(self.calls[-1], "quit")
        self.assertTrue(all(c.waited for c in self.children))
        self.reaped.assert_called()
        self.assertEqual(self.old, {p.name: p.read_bytes() for p in (self.work / "checkpoints").iterdir()})

    def test_original_checkpoint_requires_sync_counters_and_existing_gpu_contract(self):
        original_call, original_supervisor = self.prep.cold.Qmp.call, self.prep.supervise_vm
        result = guard.execute(self.state)
        self.assertEqual(result["status"], "GUARDED_WALLPAPER_COMPLETE")
        self.assertTrue(result["checkpoint_accepted_by_guard"])
        self.assertEqual(len(result["output_disk_chain"]), 7)
        self.assertEqual(self.calls, ["stop", "query-blockstats", "query-block", "quit"])
        event = result["post_stop_blockstats"][0]
        self.assertEqual(event["post_stop_blockstats"], self.response)
        self.assertEqual(event["post_stop_blocks"], self.block_response)
        self.assertIs(self.prep.cold.Qmp.call, original_call)
        self.assertIs(self.prep.supervise_vm, original_supervisor)
        self.assertFalse(result["boot_complete"])

    def test_write_failure_blocks_original_checkpoint_and_reaps(self):
        self.response[0]["stats"]["failed_wr_operations"] = 1
        self.failure_clean(guard.execute(self.state))

    def test_backing_flush_failure_blocks_checkpoint_and_reaps(self):
        self.response[0]["backing"]["stats"]["failed_flush_operations"] = 1
        self.failure_clean(guard.execute(self.state))

    def test_missing_stats_blocks_checkpoint_and_reaps(self):
        self.response = []
        self.failure_clean(guard.execute(self.state))

    def test_query_timeout_blocks_checkpoint_and_reaps(self):
        self.query_error = TimeoutError("authored stats timeout")
        self.failure_clean(guard.execute(self.state))

    def test_block_query_timeout_preserves_stats_and_blocks_checkpoint(self):
        self.block_query_error = TimeoutError("authored block inventory timeout")
        result = guard.execute(self.state)
        self.failure_clean(result)
        event = result["post_stop_blockstats"][0]
        self.assertTrue(event["stop_acknowledged"])
        self.assertEqual(event["post_stop_blockstats"], self.response)
        self.assertNotIn("post_stop_blocks", event)
        self.assertIn("authored block inventory timeout", event["error"])

    def test_qualified_empty_floppy_requires_both_inventory_witnesses(self):
        floppy_stats, floppy_block = default_floppy()
        self.response.append(floppy_stats)
        self.block_response.append(floppy_block)
        context, result, recorded = self.accepted_context()
        event = result["post_stop_blockstats"][0]
        self.assertTrue(event["counter_check"]["empty_floppy0_confirmed"])
        self.assertEqual(event["counter_check"]["backends_checked"], 2)
        guard.guard_acceptance(context, self.state["work"], self.state["receipt"], result, recorded)

    def test_floppy_with_medium_blocks_checkpoint_and_reaps(self):
        floppy_stats, floppy_block = default_floppy()
        self.response.append(floppy_stats)
        floppy_block["inserted"] = {"node-name": "unexpected-medium", "ro": True}
        self.block_response.append(floppy_block)
        self.failure_clean(guard.execute(self.state))

    def test_empty_floppy_failed_counter_blocks_checkpoint_and_reaps(self):
        floppy_stats, floppy_block = default_floppy()
        floppy_stats["stats"]["failed_flush_operations"] = 1
        self.response.append(floppy_stats)
        self.block_response.append(floppy_block)
        self.failure_clean(guard.execute(self.state))

    def test_mismatched_backend_inventories_block_checkpoint_and_reap(self):
        self.response.append(default_floppy()[0])
        self.failure_clean(guard.execute(self.state))

    def test_missing_sync_blocks_after_original_success_before_checkpoint(self):
        self.sync = False
        result = guard.execute(self.state)
        self.failure_clean(result)
        self.assertEqual(result["actual_attempt"]["vm-result.json"]["status"], "VM_OBSERVATION_COMPLETE")

    def test_gpu_failure_remains_an_original_failure(self):
        self.gpu = False
        self.failure_clean(guard.execute(self.state))

    def test_frame_failure_remains_an_original_failure(self):
        self.frame = False
        self.failure_clean(guard.execute(self.state))

    def test_settling_failure_remains_an_original_failure(self):
        self.settled = False
        self.failure_clean(guard.execute(self.state))

    def test_milestone_failure_remains_an_original_failure(self):
        self.milestone = False
        self.failure_clean(guard.execute(self.state))

    def test_changed_prior_evidence_during_stats_prevents_checkpoint(self):
        self.change_evidence = True
        self.failure_clean(guard.execute(self.state))

    def test_receipt_write_failure_still_quits_and_reaps(self):
        original = guard.observations
        def fail_once(state):
            if state["events"] and not state.get("test_failed"):
                state["test_failed"] = True
                raise OSError("authored receipt write failure")
            return original(state)
        with mock.patch.object(guard, "observations", fail_once):
            self.failure_clean(guard.execute(self.state))

    def test_postcheckpoint_collection_failure_is_never_adopted(self):
        with mock.patch.object(guard, "collect_attempt", side_effect=ValueError("authored late evidence failure")):
            result = guard.execute(self.state)
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertFalse(result["checkpoint_accepted_by_guard"])
        self.assertTrue(result["original_wallpaper_checkpoint_present"])
        self.assertTrue((self.work / "checkpoints/ios26-wallpaper.json").is_file())

    def test_extra_stage_or_already_completed_wallpaper_is_refused(self):
        guard.require_boundary(self.prep, self.plan)
        for changed in (dict(self.plan, remaining=[guard.STAGE, "ios26-locale"]),
                        dict(self.plan, completed=self.plan["completed"] + [guard.STAGE], remaining=[])):
            with self.assertRaises(ValueError):
                guard.require_boundary(self.prep, changed)
        (self.work / "checkpoints/ios26-locale.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "exact requested"):
            guard.execute(self.state)
        self.assertFalse(self.state["work"].exists())

    def test_full_hash_detects_deep_backing_mutation(self):
        inventory = guard.checkpoint_inventory(self.prep, self.work, self.plan["session"], guard.PREDECESSOR)
        backing = self.work / inventory["rows"]["ios26-firstboot"]["artifacts"]["root26g.qcow2"]["path"]
        with backing.open("r+b") as stream:
            stream.seek(100000)
            stream.write(b"x")
        with self.assertRaisesRegex(ValueError, "full disk/backing"):
            guard.full_disks(self.prep, self.work, inventory)

    def test_app_prefix_does_not_gain_gpu_checkpoint_or_new_artifact(self):
        inventory = guard.checkpoint_inventory(self.prep, self.work, self.plan["session"], guard.PREDECESSOR)
        app_prefix = guard.prefix(inventory, "ios26-apps")
        self.assertNotIn(guard.PREDECESSOR, app_prefix["rows"])
        self.assertNotIn("root26-gpu.qcow2", app_prefix["artifacts"])
        self.assertEqual(app_prefix["completed"][-1], "ios26-apps")

    def accepted_context(self):
        receipt = self.state["receipt"]
        receipt.update(schema=1, kind="ios26_wallpaper_execution_guard", prep_work=str(self.work),
            guard_source=str(Path(guard.__file__).resolve()), guard_source_sha256=guard.sha(Path(guard.__file__).read_bytes()),
            apps_audit={"files": receipt["bound_files"], "work": "authored fixture"}, equivalent_frozen_runner_argv=["authored fixture"])
        result = guard.execute(self.state)
        inventory = guard.checkpoint_inventory(self.prep, self.work, self.plan["session"], guard.STAGE)
        context = dict(self.state, inventory=inventory, disk_chain=guard.full_disks(self.prep, self.work, inventory),
            runner=Path(receipt["runner_dir"]), apps_audit=receipt["apps_audit"], app_receipt={"input_chains": []},
            equivalent_argv=receipt["equivalent_frozen_runner_argv"])
        recorded = json.loads((self.state["work"] / "guard-observations.json").read_text())
        return context, result, recorded

    def test_saved_inspector_accepts_only_actual_complete_guard_attempt(self):
        context, result, recorded = self.accepted_context()
        bound = guard.guard_acceptance(context, self.state["work"], self.state["receipt"], result, recorded)
        self.assertEqual(len(bound), 8)
        self.assertIn(str(Path(guard.__file__).resolve()), bound)
        self.assertEqual(len(context["disk_chain"]), 7)

    def test_original_checkpoint_cannot_be_adopted_after_failed_guard(self):
        context, result, recorded = self.accepted_context()
        result.update(status="INCOMPLETE", checkpoint_accepted_by_guard=False)
        with self.assertRaisesRegex(ValueError, "exact successful"):
            guard.guard_acceptance(context, self.state["work"], self.state["receipt"], result, recorded)
        self.assertTrue((self.work / "checkpoints/ios26-wallpaper.json").exists())

    def test_counter_receipt_without_new_block_inventory_is_not_adopted(self):
        context, result, recorded = self.accepted_context()
        del result["post_stop_blockstats"][0]["post_stop_blocks"]
        del recorded["post_stop_blockstats"][0]["post_stop_blocks"]
        with self.assertRaisesRegex(ValueError, "block inventory"):
            guard.guard_acceptance(context, self.state["work"], self.state["receipt"], result, recorded)

    def test_guard_prefix_cannot_silently_acquire_wallpaper_credit(self):
        context, result, recorded = self.accepted_context()
        receipt = copy.deepcopy(self.state["receipt"])
        receipt["checkpoints"] = context["inventory"]["hashes"]
        result["guard_session_sha256"] = self.prep.digest(receipt)
        with self.assertRaisesRegex(ValueError, "exact successful"):
            guard.guard_acceptance(context, self.state["work"], receipt, result, recorded)

    def test_rehashed_actual_trace_and_sync_cannot_disagree_with_guard(self):
        context, result, recorded = self.accepted_context()
        attempt = Path(result["actual_attempt"]["attempt"])
        original = (attempt / "vm-result.json").read_bytes()
        for kind in ("stats", "blocks", "missing-blocks", "reordered-blocks", "duplicate-blocks", "block-error", "sync"):
            with self.subTest(kind=kind):
                changed = copy.deepcopy(result)
                vm = json.loads(original)
                if kind == "stats":
                    vm["qmp"][1]["response"]["return"][0]["stats"]["failed_wr_operations"] = 1
                elif kind == "blocks":
                    vm["qmp"][2]["response"]["return"][0]["inserted"]["node-name"] = "different-node"
                elif kind == "missing-blocks":
                    del vm["qmp"][2]
                elif kind == "reordered-blocks":
                    vm["qmp"][1], vm["qmp"][2] = vm["qmp"][2], vm["qmp"][1]
                elif kind == "duplicate-blocks":
                    vm["qmp"].insert(2, copy.deepcopy(vm["qmp"][2]))
                elif kind == "block-error":
                    vm["qmp"][2]["response"]["error"] = {"class": "GenericError", "desc": "authored failure"}
                else:
                    vm["guest_sync_answered"] = False
                self.prep.atomic_json(attempt / "vm-result.json", vm)
                body = (attempt / "vm-result.json").read_bytes()
                changed["actual_attempt"]["vm-result.json"] = vm
                changed["actual_attempt"]["files"]["vm-result.json"] = {"bytes": len(body), "sha256": guard.sha(body)}
                with self.assertRaises(ValueError):
                    guard.guard_acceptance(context, self.state["work"], self.state["receipt"], changed, recorded)


class AppAuditReceipt(unittest.TestCase):
    """Validate the new receipt glue with real committed guest/fsck validators."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work, self.audit = self.root / "prep", self.root / "apps-audit"
        self.work.mkdir(); self.audit.mkdir()
        source = Path(apps.__file__).parent
        self.tools = self.root / "tools"
        self.tools.mkdir()
        (self.tools / "setup").mkdir(); (self.tools / "helper").mkdir()
        authored_script, authored_helper = b"authored script fixture\n", b"authored compressed-helper identity fixture"
        (self.tools / "setup/fixture.sh").write_bytes(authored_script)
        (self.tools / "helper/initrd.gz").write_bytes(authored_helper)
        # Exercise receipt/hash checking against small authored utility inputs.
        # Production loads the separately pinned immutable module, so these
        # test-only constant substitutions cannot change its approval set.
        patcher = mock.patch.object(apps, "SCRIPT_SHA256", {"fixture.sh": guard.sha(authored_script)})
        patcher.start(); self.addCleanup(patcher.stop)
        patcher = mock.patch.object(apps, "INITRD_SHA256", guard.sha(authored_helper))
        patcher.start(); self.addCleanup(patcher.stop)
        session = {"runner_sources": {"authored": "fixture"}, "runtime": {"archive": "authored"},
            "qualification": {"qualification_sha256": "1" * 64}, "tooling_manifest_sha256": "2" * 64,
            "helper_ram_mib": 2048, "helper_vcpus": 4, "tooling": str(self.tools)}
        prep_module.atomic_json(self.work / "session.json", session)
        names = list(prep_module.stages.STAGES[:prep_module.stages.STAGES.index(guard.PREDECESSOR) + 1])
        rows = {name: {"artifacts": {}} for name in names}
        rows["ios26-decrypt"]["artifacts"][apps.OS_LOGICAL] = {"bytes": 1024, "path": "authored-os"}
        inventory = guard.prefix({"completed": names, "rows": rows,
            "hashes": {str(self.work / "checkpoints" / (name + ".json")): str(index) for index, name in enumerate(names)}}, guard.PREDECESSOR)
        self.prior = {"files": {}, "approved_system_journal": approved_journal()}
        self.inputs = [{"identity": {"authored": "original six inputs"}, "record": {}}]
        self.bodies = {n: (source / n).read_bytes() for n in apps.SOURCES}
        self.state = {"prep": prep_module, "plan": {"session": session}, "prep_work": self.work,
            "inventory": inventory, "runner": source, "auditor": auditor, "app_guest": apps_guest}
        scripts = {str(self.tools / "setup" / n): h for n, h in apps.SCRIPT_SHA256.items()}
        self.receipt = {"schema": 1, "kind": "ios26_apps_copy_audit", "prep_work": str(self.work), "runner_dir": str(source),
            "prep_session_sha256": guard.sha((self.work / "session.json").read_bytes()), "frozen_sources": session["runner_sources"],
            "through": apps.STAGE, "checkpoints": guard.prefix(inventory, apps.STAGE)["hashes"],
            "input_chains": self.inputs, "prior_evidence": self.prior, "source_directory": str(source),
            "auditor_sources": guard.APP_AUDITOR_SOURCES.copy(),
            "dependency_sources": {"partition_guest_sha256": apps.APPROVED["audit_ios26_partition_guest.py"],
                                   "firstboot_guest_sha256": apps.APPROVED["inspect_ios26_firstboot_guest.py"]},
            "script_files": scripts, "runtime": session["runtime"], "qualification_sha256": "1" * 64,
            "tooling_manifest_sha256": "2" * 64, "helper_initrd_sha256": apps.INITRD_SHA256,
            "helper_ram_mib": 2048, "helper_vcpus": 4, "readonly_inputs": True, "replay_allowed": False,
            "repair_allowed": False, "native_required": True, "tcg_retry": False,
            "bounds": {"helper_seconds": 7200, "max_log_mib": 64, "min_free_mib": 1536, "min_available_mib": 512}}
        self.attempt = self.audit / "a1"
        (self.attempt / "files/apps-audit").mkdir(parents=True)
        policy = {"schema": 1, "audit_nonce": "a" * 32, "apps_audit_session_sha256": prep_module.digest(self.receipt),
            **self.receipt["dependency_sources"], "os_bytes": 1024, "approved_system_journal": self.prior["approved_system_journal"]}
        raw = passing_guest(policy)
        for name, value in (("expected-policy.json", policy), ("launch.json", {"command": ["authored helper fixture"]}),
                            ("files/apps-audit/result.json", raw)):
            prep_module.atomic_json(self.attempt / name, value)
        for name in ("fsck-activation.txt", "fsck-apps.txt"):
            (self.attempt / "files/apps-audit" / name).write_text(CLEAN)
        (self.attempt / "files/apps-audit/apfs-mount.txt").write_bytes(apps_guest.APFS_LOG_HEADER)
        native = native_result()
        vm = {"stage": "apps-copy-audit", "status": "VM_OBSERVATION_COMPLETE", "natural_exit": True,
              "witnesses": native["native_witnesses"], "cleanup": native["cleanup"], "done_codes": [0], "out_sizes": [10240]}
        prep_module.atomic_json(self.attempt / "vm-result.json", vm)
        self.result = {"schema": 1, "status": "APP_COPY_AUDIT_PASSED", "apps_audit_session_sha256": prep_module.digest(self.receipt),
            "full_input_chains_unchanged": True, "preparation_and_prior_evidence_unchanged": True, **native,
            "attempt": str(self.attempt), "guest_result": raw,
            "launch": {"path": str(self.attempt / "launch.json"), "sha256": guard.sha((self.attempt / "launch.json").read_bytes())},
            "outputs": {n: prep_module.file_record(self.attempt / "files" / n, self.audit) for n in apps.OUTPUTS}}
        for path, data in ((self.audit / "apps-audit-session.json", self.receipt), (self.audit / "result.json", self.result),
                           (self.attempt / "apps-audit-result.json", self.result)):
            prep_module.atomic_json(path, data)

    def check(self):
        return guard.app_audit_acceptance(apps, self.state, self.audit, self.receipt, self.result, self.prior, self.inputs, self.bodies)

    def test_final_sources_match_approved_commit_and_original_prefix_is_preserved(self):
        self.assertEqual({n: guard.sha(b) for n, b in self.bodies.items()}, guard.APP_AUDITOR_SOURCES)
        identity = self.check()
        self.assertEqual(len(identity["checkpoints"]), 11)
        self.assertNotIn(str(self.work / "checkpoints/ios26-gpu.json"), identity["checkpoints"])
        self.assertEqual(identity["source_hashes"], guard.APP_AUDITOR_SOURCES)

    def test_receipt_cannot_claim_gpu_prefix_or_changed_input_union(self):
        for name, value in (("checkpoints", self.state["inventory"]["hashes"]), ("input_chains", []),
                            ("native_required", False), ("auditor_sources", {})):
            with self.subTest(name=name):
                old = self.receipt[name]; self.receipt[name] = value
                with self.assertRaisesRegex(ValueError, "exact original apps prefix"):
                    self.check()
                self.receipt[name] = old

    def test_failed_guard_or_wrong_native_cleanup_or_raw_output_is_not_adopted(self):
        for kind in ("status", "forced", "output"):
            with self.subTest(kind=kind):
                original = copy.deepcopy(self.result)
                if kind == "status": self.result["status"] = "INCOMPLETE"
                elif kind == "forced": self.result["cleanup"]["forced_descendants"] = False
                else: (self.attempt / "files/apps-audit/apfs-mount.txt").write_bytes(b"changed authored metadata")
                with self.assertRaises(ValueError): self.check()
                self.result = original

    def test_missing_inputs_and_unapproved_source_refuse_without_execution(self):
        with self.assertRaisesRegex(ValueError, "required"):
            guard.preflight(guard.parser().parse_args([]))
        self.receipt["auditor_sources"] = {}
        prep_module.atomic_json(self.audit / "apps-audit-session.json", self.receipt)
        with mock.patch.object(guard, "module_from") as execute_source:
            with self.assertRaisesRegex(ValueError, "approved committed"):
                guard.context(self.audit, guard.PREDECESSOR)
            execute_source.assert_not_called()


if __name__ == "__main__":
    unittest.main()
