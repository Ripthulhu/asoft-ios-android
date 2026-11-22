#!/usr/bin/env python3
"""Authored inputs and mocked owners only; no QEMU, guest, GPU or mounts."""
import contextlib
import copy
import fcntl
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

import guard_ios26_coldboot as guard
import guard_ios26_firstboot as firstguard
import guard_ios26_wallpaper as wallpaper_guard
import inspect_ios26_wallpaper as wallpaper_inspector
import inspect_ios26_wallpaper_guest as wallpaper_guest
import audit_ios26_apps as app
import audit_ios26_partition_guest as auditor
import prepare_ios26 as prep
from test_audit_ios26_partition import CLEAN
from test_inspect_ios26_wallpaper import raw_result


HERE = Path(__file__).parent


def node(name, values=None, children=()):
    values = {"name": name.encode() + b"\0", **(values or {})}
    out = struct.pack("<II", len(values), len(children))
    for key, value in values.items():
        out += key.encode().ljust(32, b"\0") + struct.pack("<I", len(value)) + value + b"\0" * (-len(value) % 4)
    return out + b"".join(children)


def authored_tree():
    base, size = 0x100000000, 4 << 30
    return node("device-tree", children=[
        node("chosen", {"dram-size": struct.pack("<Q", size), "display-scale": struct.pack("<I", 3)}),
        node("memory", {"reg": struct.pack("<QQ", base, size)}),
        node("product", children=[node("util", {"reg": struct.pack("<QQ", base + size, 4096)})]),
        node("cpus", children=[node("cpu" + str(i), {"timebase-frequency": struct.pack("<Q", 19_200_000)})
                                for i in range(4)])])


def mem(mib):
    return f"MemTotal:       8388608 kB\nMemAvailable:   {mib * 1024} kB\nSwapFree: 1 kB\n".encode()


def qcow(path, backing=None):
    body = bytearray(131072)
    body[:4] = b"QFI\xfb"
    name = str(backing).encode() if backing else b""
    struct.pack_into(">IQI", body, 4, 3, 104 if name else 0, len(name))
    struct.pack_into(">Q", body, 24, guard.DISK_BYTES)
    body[104:104 + len(name)] = name
    path.write_bytes(body)


class PackedInputs(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cg-")
        self.root = Path(self.temp.name)
        self.work = self.root / "prep"
        self.work.mkdir()
        for name in ("checkpoints", "attempts", "inputs"):
            (self.work / name).mkdir()
        (self.work / "owner.lock").touch()
        self.session = {"schema": 1, "kind": "standalone_ios26_preparation", "native_required": True,
            "tcg_retry": False, "guest_ram_gib": 3, "timebase_hz": 38_400_000,
            "runner_sources": {name: guard.sha((HERE / name).read_bytes()) for name in firstguard.FROZEN},
            "runtime": {"archive_sha256": "1" * 64, "header_sha256": "2" * 64},
            "qualification": {"qualification_sha256": "3" * 64}, "tooling_manifest_sha256": "4" * 64,
            "helper_ram_mib": 2048, "helper_vcpus": 4, "package": str(self.root / "package"), "tooling": str(self.root / "tooling")}
        prep.atomic_json(self.work / "session.json", self.session)
        self.per_stage = {name: {} for name in prep.stages.STAGES}
        for i, logical in enumerate(guard.PACK_FILES):
            path = self.work / "inputs" / (str(i) + ".authored")
            path.write_bytes(authored_tree() if logical.startswith("dtree-") else ("authored " + logical).encode())
            stage = "ios26-wallpaper" if logical == "root.tc" else "shared-build"
            self.per_stage[stage][logical] = prep.file_record(path, self.work)
        previous = None
        for index, (stage, logical) in enumerate((*wallpaper_guard.DISKS, ("ios26-locale", "root.qcow2"))):
            path = self.work / "inputs" / (str(index) + ".qcow2")
            qcow(path, previous)
            self.per_stage[stage][logical] = prep.file_record(path, self.work)
            previous = path
        self.locale = previous
        self.attempt = self.work / "attempts/14-0001"
        self.assets = self.attempt / "files/ios26"
        self.assets.mkdir(parents=True)
        for logical, name in guard.PACK_FILES.items():
            source_stage = "ios26-wallpaper" if logical == "root.tc" else "shared-build"
            record = self.per_stage[source_stage][logical]
            (self.assets / name).write_bytes((self.work / record["path"]).read_bytes())
        qcow(self.assets / "root26s-aod.qcow2")
        prep.atomic_json(self.assets / "install.json", {"format": 1, "what": "ios26", "build": "23G90",
            "prepared_by": "standalone native-required stages", "session_sha256": prep.digest(self.session),
            "created_utc": "authored fixture", **guard.NO_BOOT})
        self.per_stage[guard.STAGE] = {"ios26/" + path.name: prep.file_record(path, self.work) for path in self.assets.iterdir()}
        previous = None
        for name in prep.stages.STAGES:
            row = {"schema": 1, "status": "STAGE_COMPLETE", "stage": name, "session_sha256": prep.digest(self.session),
                   "previous_sha256": previous, "artifacts": self.per_stage[name], "attempt": str(self.attempt) if name == guard.STAGE else "authored unused"}
            path = self.work / "checkpoints" / (name + ".json")
            prep.atomic_json(path, row)
            previous = prep.cold.sha(path)
        self.inventory = guard.checkpoint_inventory(prep, self.work, self.session)
        self.wallpaper = wallpaper_guard.prefix(self.inventory, wallpaper_guard.STAGE)
        self.chain = wallpaper_guard.full_disks(prep, self.work, self.wallpaper)

    def tearDown(self):
        self.temp.cleanup()

    def packed(self):
        return guard.packed_inputs(prep, self.work, self.inventory, self.chain)

    def state(self):
        packed = self.packed()
        source = self.root / "authored-prior-host-source.py"
        source.write_text("# authored prior host fixture\n")
        receipt = {"bound_files": {str(source): guard.sha(source.read_bytes())}, "checkpoints": self.inventory["hashes"],
                   "input_bindings": packed["bindings"], "prior_input_identities": {}, "packed": packed}
        return {"prep": prep, "prep_work": self.work, "work": self.root / "guard", "plan": {"session": self.session}, "receipt": receipt}

    def test_standalone_pack_and_complete_actual_eight_member_locale_ancestry(self):
        before = {str(path): path.read_bytes() for path in self.work.rglob("*") if path.is_file()}
        packed = self.packed()
        self.assertEqual(len(packed["files"]), 9)
        self.assertEqual(len(packed["locale_chain"]), 8)
        self.assertEqual(len(packed["packed_disk"]["record"]["backing_chain"]), 1)
        self.assertEqual(packed["locale_chain"][1:], self.chain)
        self.assertEqual(before, {str(path): path.read_bytes() for path in self.work.rglob("*") if path.is_file()})

    def test_old_prefixes_remain_shorter_when_pack_and_locale_exist(self):
        expected = {"ios26-partition": 7, "ios26-firstboot": 8, "ios26-apps": 11, "ios26-wallpaper": 13, "ios26-pack": 15}
        for through, count in expected.items():
            with self.subTest(through=through):
                selected = wallpaper_guard.prefix(self.inventory, through)
                self.assertEqual(len(selected["completed"]), count)
                self.assertEqual(len(selected["hashes"]), count)
                self.assertEqual(selected["completed"][-1], through)
                self.assertNotIn("ios26/root26s-aod.qcow2", selected["artifacts"] if through != guard.STAGE else {})
        with self.assertRaisesRegex(ValueError, "only GPU or wallpaper"):
            wallpaper_guard.checkpoint_inventory(prep, self.work, self.session, guard.STAGE)

    def test_through_pack_inventory_refuses_gaps_extras_and_changed_parent(self):
        path = self.work / "checkpoints/ios26-pack.json"
        original = path.read_bytes()
        path.unlink()
        with self.assertRaisesRegex(ValueError, "through-pack boundary"):
            guard.checkpoint_inventory(prep, self.work, self.session)
        path.write_bytes(original)
        extra = path.with_name("invented.json")
        extra.write_text("{}")
        with self.assertRaisesRegex(ValueError, "through-pack boundary"):
            guard.checkpoint_inventory(prep, self.work, self.session)
        extra.unlink()
        row = json.loads(original)
        row["previous_sha256"] = "0" * 64
        prep.atomic_json(path, row)
        with self.assertRaisesRegex(ValueError, "checkpoint chain"):
            guard.checkpoint_inventory(prep, self.work, self.session)

    def test_complete_boundary_still_requires_the_exact_authored_fifteen_stages(self):
        altered = (*prep.stages.STAGES[:-2], "invented-locale", guard.STAGE)
        with patch.object(prep.stages, "STAGES", altered):
            with self.assertRaisesRegex(ValueError, "stage order changed"):
                guard.checkpoint_inventory(prep, self.work, self.session)

    def test_copy_mismatch_is_refused_even_with_consistent_new_output_record(self):
        path = self.assets / "bootkc"
        path.write_bytes(b"different authored copied bytes")
        self.inventory["rows"][guard.STAGE]["artifacts"]["ios26/bootkc"] = prep.file_record(path, self.work)
        with self.assertRaisesRegex(ValueError, "differs from its prepared source"):
            self.packed()

    def test_packed_assets_refuse_extra_symlink_and_hardlink(self):
        extra = self.assets / "unrecorded"
        extra.write_bytes(b"extra")
        with self.assertRaisesRegex(ValueError, "nine ordinary"):
            self.packed()
        extra.unlink()
        path = self.assets / "bootkc"
        original = path.read_bytes()
        path.unlink()
        outside = self.root / "other"
        outside.write_bytes(original)
        path.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "nine ordinary"):
            self.packed()
        path.unlink()
        os.link(outside, path)
        with self.assertRaisesRegex(ValueError, "nine ordinary"):
            self.packed()

    def test_final_pack_cannot_retain_a_backing_file(self):
        path = self.assets / "root26s-aod.qcow2"
        qcow(path, self.locale)
        self.inventory["rows"][guard.STAGE]["artifacts"]["ios26/root26s-aod.qcow2"] = prep.file_record(path, self.work)
        with self.assertRaisesRegex(ValueError, "standalone"):
            self.packed()

    def test_locale_cannot_skip_the_inspected_wallpaper_disk(self):
        qcow(self.locale, Path(self.chain[1]["identity"]["path"]))
        self.inventory["rows"]["ios26-locale"]["artifacts"]["root.qcow2"] = prep.file_record(self.locale, self.work)
        with self.assertRaisesRegex(ValueError, "locale backing chain"):
            self.packed()

    def test_packed_virtual_geometry_and_install_session_are_bound(self):
        path = self.assets / "root26s-aod.qcow2"
        with path.open("r+b") as stream:
            stream.seek(24)
            stream.write(struct.pack(">Q", 32 << 30))
        self.inventory["rows"][guard.STAGE]["artifacts"]["ios26/root26s-aod.qcow2"] = prep.file_record(path, self.work)
        with self.assertRaisesRegex(ValueError, "virtual geometry"):
            self.packed()
        qcow(path)
        self.inventory["rows"][guard.STAGE]["artifacts"]["ios26/root26s-aod.qcow2"] = prep.file_record(path, self.work)
        path = self.assets / "install.json"
        value = json.loads(path.read_text())
        value["session_sha256"] = "0" * 64
        prep.atomic_json(path, value)
        self.inventory["rows"][guard.STAGE]["artifacts"]["ios26/install.json"] = prep.file_record(path, self.work)
        with self.assertRaisesRegex(ValueError, "install identity"):
            self.packed()

    def test_after_run_full_hash_detects_bytes_beyond_the_fast_identity_prefix(self):
        state = self.state()
        target = Path(self.chain[-1]["identity"]["path"])
        before = prep.cold.readonly_identity(target)
        with target.open("r+b") as stream:
            stream.seek(100000)
            stream.write(b"changed authored tail")
        real_identity = prep.cold.readonly_identity
        def unchanged_fast(path):
            return before if Path(path) == target else real_identity(path)
        with patch.object(prep.cold, "readonly_identity", side_effect=unchanged_fast):
            with self.assertRaisesRegex(ValueError, "full packed/retained input bytes"):
                guard.unchanged_inputs(state, True)

    def test_prior_host_source_change_is_still_detected_after_pack(self):
        state = self.state()
        with patch.object(prep, "recheck"):
            guard.unchanged_inputs(state, True)
        Path(next(iter(state["receipt"]["bound_files"]))).write_text("# changed prior source\n")
        with self.assertRaisesRegex(ValueError, "bound source"):
            guard.unchanged_inputs(state, False)

    def test_preparation_lock_conflict_creates_nothing_and_never_rechecks_or_launches(self):
        state = self.state()
        with (self.work / "owner.lock").open("rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with patch.object(guard, "unchanged_inputs") as unchanged, self.assertRaisesRegex(ValueError, "another owner"):
                with guard.own_coldboot(state):
                    self.fail("must not acquire")
        unchanged.assert_not_called()
        self.assertFalse(state["work"].exists())


class WallpaperBinding(unittest.TestCase):
    def setUp(self):
        PackedInputs.setUp(self)
        self.inspection = self.root / "saved-wallpaper"
        self.a1 = self.inspection / "a1"
        self.output = self.a1 / "files/inspection"
        self.output.mkdir(parents=True)
        self.old_guard_work = self.root / "wallpaper-guard"
        self.old_guard_work.mkdir()
        self.guard_files = {}
        for name in ("guard-session.json", "result.json", "guard-observations.json"):
            path = self.old_guard_work / name
            path.write_text('{"authored":"previous guard metadata fixture"}\n')
            self.guard_files[str(path)] = guard.sha(path.read_bytes())
        prior = self.root / "authored-app-proof.json"
        prior.write_text('{"authored":"already validated app proof fixture"}\n')
        self.context = {"prep": prep, "plan": {"session": self.session}, "prep_work": self.work, "runner": HERE,
            "wallpaper_inspector": wallpaper_inspector, "wallpaper_guard": wallpaper_guard,
            "wallpaper_inventory": self.wallpaper, "wallpaper_chain": self.chain,
            "wallpaper_guard_source": HERE / "guard_ios26_wallpaper.py", "wallpaper_guard_work": self.old_guard_work,
            "wallpaper_guard_result": {"checkpoint": {"path": str(self.work / "checkpoints/ios26-wallpaper.json"),
                "sha256": self.inventory["hashes"][str(self.work / "checkpoints/ios26-wallpaper.json")]}},
            "apps_audit": {"files": {str(prior): guard.sha(prior.read_bytes())}}, "app": app, "auditor": auditor,
            "raw_source": HERE / "inspect_ios26_firstboot_guest.py", "partition_source": HERE / "audit_ios26_partition_guest.py"}
        self.receipt = {"schema": 1, "kind": "ios26_saved_wallpaper_inspection", "prep_work": str(self.work),
            "runner_dir": str(HERE), "prep_session_sha256": prep.cold.sha(self.work / "session.json"),
            "frozen_sources": self.session["runner_sources"], "guard_work": str(self.old_guard_work),
            "guard_source": str(self.context["wallpaper_guard_source"]), "guard_source_sha256": wallpaper_inspector.GUARD_SHA256,
            "wallpaper_guard_files": self.guard_files, "guard_checkpoint": self.context["wallpaper_guard_result"]["checkpoint"],
            "apps_audit": self.context["apps_audit"], "checkpoints": self.wallpaper["hashes"], "disk_chain": self.chain,
            "baseline": self.chain[1], "source_directory": str(HERE),
            "inspector_sources": {name: guard.WALLPAPER_SOURCES[name] for name in wallpaper_inspector.SOURCES},
            "dependency_files": {str(self.context["raw_source"]): wallpaper_inspector.RAW_SHA256,
                str(self.context["partition_source"]): wallpaper_inspector.PARTITION_SHA256,
                str(self.context["wallpaper_guard_source"]): wallpaper_inspector.GUARD_SHA256},
            "runtime": self.session["runtime"], "qualification_sha256": self.session["qualification"]["qualification_sha256"],
            "tooling_manifest_sha256": self.session["tooling_manifest_sha256"],
            "readonly": True, "mounts_allowed": False, "replay_allowed": False, "repair_allowed": False,
            "native_required": True, "tcg_retry": False, "helper_ram_mib": 2048, "helper_vcpus": 4,
            "bounds": {"helper_seconds": 7200, "max_log_mib": 64, "min_free_mib": 1536, "min_available_mib": 512}, **guard.NO_BOOT}
        self.policy = {"schema": 1, "kind": "ios26_saved_wallpaper_inspection", "inspection_nonce": "1" * 32,
            "inspection_session_sha256": prep.digest(self.receipt), "raw_guest_sha256": wallpaper_inspector.RAW_SHA256,
            "partition_guest_sha256": wallpaper_inspector.PARTITION_SHA256}
        prep.atomic_json(self.a1 / "expected-policy.json", self.policy)
        raw = types.SimpleNamespace(inspect_disks=lambda *args: raw_result(self.policy))
        checked = wallpaper_guest.inspect(raw, auditor, "authored", "authored", self.policy, self.output)
        prep.atomic_json(self.output / "result.json", checked)
        (self.output / "fsck-system.txt").write_text(CLEAN)
        (self.output / "fsck-data.txt").write_text(CLEAN)
        disks = [{"path": self.a1 / "in.tar", "format": "raw", "readonly": True, "serial": "in"},
            {"path": self.a1 / "out.raw", "format": "raw", "readonly": False, "serial": "out"},
            {"path": Path(self.chain[0]["identity"]["path"]), "format": "qcow2", "readonly": True, "serial": "d0"},
            {"path": Path(self.chain[1]["identity"]["path"]), "format": "qcow2", "readonly": True, "serial": "d1"}]
        argv, env = prep.helper_command(self.context["plan"], self.a1, disks)
        prep.atomic_json(self.a1 / "launch.json", {"command": argv, "environment": env, "deadline_seconds": 7200})
        self.vm = {"stage": "saved-wallpaper-inspection", "status": "VM_OBSERVATION_COMPLETE", "natural_exit": True,
            "done_codes": [0], "out_sizes": [10240],
            "witnesses": {"native_initialization": True, "native_execution": True, "fatal_markers": []},
            "cleanup": {"exit_code": 0, "echild": True, "forced_qemu": False, "forced_descendants": [], "errors": []}}
        prep.atomic_json(self.a1 / "vm-result.json", self.vm)
        self.result = {"schema": 1, "status": "SAVED_WALLPAPER_INSPECTION_PASSED", "attempt": str(self.a1),
            "inspection_session_sha256": prep.digest(self.receipt), "natural_exit": True,
            "native_witnesses": self.vm["witnesses"], "cleanup": self.vm["cleanup"],
            "full_disk_chain_unchanged": True, "preparation_and_prior_evidence_unchanged": True,
            "launch": {"path": str(self.a1 / "launch.json"), "sha256": prep.cold.sha(self.a1 / "launch.json")},
            "outputs": {"inspection/" + path.name: prep.file_record(path, self.inspection) for path in self.output.iterdir()},
            "guest_result": checked, **guard.NO_BOOT}
        self.persist()

    def tearDown(self):
        PackedInputs.tearDown(self)

    def persist(self):
        prep.atomic_json(self.inspection / "inspection-session.json", self.receipt)
        prep.atomic_json(self.inspection / "result.json", self.result)
        prep.atomic_json(self.a1 / "inspection-result.json", self.result)

    def accept(self):
        return guard.wallpaper_inspection_acceptance(self.context, self.inspection, self.receipt, self.result, self.guard_files)

    def test_exact_inspection_retains_older_prefix_and_all_sources_and_raw_outputs(self):
        proof = self.accept()
        self.assertEqual(proof["checkpoints"], self.wallpaper["hashes"])
        self.assertNotEqual(proof["checkpoints"], self.inventory["hashes"])
        for name in wallpaper_inspector.SOURCES:
            self.assertEqual(proof["files"][str(HERE / name)], guard.WALLPAPER_SOURCES[name])
        self.assertIn(str(self.output / "fsck-system.txt"), proof["files"])
        self.assertIn(str(self.a1 / "vm-result.json"), proof["files"])
        self.assertIn(str(self.context["partition_source"]), proof["files"])

    def test_claiming_through_pack_scope_for_old_inspection_is_refused(self):
        self.receipt["checkpoints"] = self.inventory["hashes"]
        self.persist()
        with self.assertRaisesRegex(ValueError, "original prefix"):
            self.accept()

    def test_wrong_baseline_or_unreviewed_inspector_pair_is_refused(self):
        original = copy.deepcopy(self.receipt)
        self.receipt["baseline"] = self.chain[2]
        with self.assertRaisesRegex(ValueError, "original prefix"):
            self.accept()
        self.receipt = original
        self.receipt["inspector_sources"]["inspect_ios26_wallpaper.py"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "original prefix"):
            self.accept()

    def test_incomplete_native_forced_cleanup_and_boolean_descendant_shape_fail(self):
        for mutate in (lambda r: r.update(natural_exit=False), lambda r: r["native_witnesses"].update(native_execution=False),
                       lambda r: r["cleanup"].update(forced_qemu=True), lambda r: r["cleanup"].update(forced_descendants=False)):
            with self.subTest(mutate=mutate):
                before = copy.deepcopy(self.result)
                mutate(self.result)
                self.persist()
                with self.assertRaisesRegex(ValueError, "native natural completion"):
                    self.accept()
                self.result = before

    def test_readonly_attachment_change_fails_even_when_launch_hash_is_updated(self):
        path = self.a1 / "launch.json"
        value = json.loads(path.read_text())
        value["command"] = [arg.replace("readonly=on", "readonly=off") for arg in value["command"]]
        prep.atomic_json(path, value)
        self.result["launch"]["sha256"] = prep.cold.sha(path)
        self.persist()
        with self.assertRaisesRegex(ValueError, "read-only/native attachments"):
            self.accept()

    def test_actual_vm_result_cannot_be_replaced_by_success_summary(self):
        self.vm["done_codes"] = [7]
        prep.atomic_json(self.a1 / "vm-result.json", self.vm)
        with self.assertRaisesRegex(ValueError, "actual native completion"):
            self.accept()

    def test_fresh_nonce_and_raw_diagnostics_still_required_with_self_consistent_hashes(self):
        path = self.output / "result.json"
        value = json.loads(path.read_text())
        value["inspection_nonce"] = "2" * 32
        prep.atomic_json(path, value)
        self.result["outputs"]["inspection/result.json"] = prep.file_record(path, self.inspection)
        self.result["guest_result"] = value
        self.persist()
        with self.assertRaisesRegex(ValueError, "another attempt"):
            self.accept()

    def test_missing_fsck_and_changed_prior_metadata_are_independent_refusals(self):
        original = self.result["outputs"].pop("inspection/fsck-data.txt")
        self.persist()
        with self.assertRaisesRegex(ValueError, "output inventory"):
            self.accept()
        self.result["outputs"]["inspection/fsck-data.txt"] = original
        self.persist()
        Path(next(iter(self.guard_files))).write_text('{"authored":"changed earlier guard"}\n')
        with self.assertRaisesRegex(ValueError, "changed during validation"):
            self.accept()

    def test_changed_unapproved_source_is_never_imported(self):
        path = self.root / "unapproved.py"
        path.write_text("raise AssertionError('must never execute')\n")
        with self.assertRaisesRegex(ValueError, "unreviewed prerequisite"):
            guard.approved_module(path, guard.WALLPAPER_SOURCES["inspect_ios26_wallpaper.py"])

    def test_reviewed_source_pins_match_all_three_committed_wallpaper_files(self):
        for name, expected in guard.WALLPAPER_SOURCES.items():
            self.assertEqual(guard.sha((HERE / name).read_bytes()), expected)
        self.assertEqual(guard.sha((HERE / "cold_boot_ios26.py").read_bytes()), guard.COLD_SHA256)
        self.assertEqual(guard.sha((HERE / "cold_boot_dt.py").read_bytes()), guard.DT_SHA256)


class FinalVerdict(unittest.TestCase):
    def fixture(self, root, original_status="WITNESSES_OBSERVED", expect=True, memory_pass=True, durable=True):
        original_work = root / "prep"
        original_work.mkdir()
        (original_work / "owner.lock").touch()
        work = root / "guard"
        cold = guard.module_from((HERE / "cold_boot_ios26.py").read_bytes(), HERE / "cold_boot_ios26.py")
        plan = {"package": str(root / "package"), "run_dir": str(work / "cold"), "assets": str(root / "assets"),
                "frame_size": [1179, 2556], "trustcache": str(root / "tc"), "ram_gib": 3, "scale": 3}
        command, env = cold.command(plan, 17)
        observed = guard.MemoryObservations(lambda: mem(4096))
        observed.launch_attempts = 1
        observed.prelaunch_passed = observed.sample("prelaunch", 3840)["passed"]
        observed.sample("storage_report", 512)
        observed.launch_command = {"command": command, "environment": env, "frozen_command_unchanged": True}
        if not memory_pass:
            observed.latch("authored transient low-memory fixture", "storage_report")
        marker = "explicit authored witness"
        original = {"schema": 1, "status": original_status, "guest_started": True, "stop_reason": "requested_witnesses_observed",
            "package_rechecked_after_run": True, "witnesses": {"serial_markers_found": [marker], "fatal_markers": [],
                "native_initialization": True, "native_execution": True, "gpu_execution": True, "frame_captured": True},
            "cleanup": {"stop_flushed": True, "echild": True, "exit_code": 0, "forced_qemu": False,
                "forced_descendants": [], "errors": []}, "final_storage": {"within_bounds": True, "evidence_truncated": []}, **guard.NO_BOOT}
        def owned_result(preflight, args):
            # This fixture stands in for the already-tested frozen owner. No
            # process or frame is created in the final-verdict unit tests.
            run = Path(plan["run_dir"])
            run.mkdir()
            prep.atomic_json(run / "launch.json", {"command": command, "environment": env})
            if durable:
                prep.atomic_json(run / "result.json", original)
            return original
        cold.boot = owned_result
        fake = types.SimpleNamespace(cold=cold, atomic_json=prep.atomic_json, digest=prep.digest,
            cleanup_signals=prep.cleanup_signals, refuse_live_children=Mock())
        state = {"prep": fake, "prep_work": original_work, "work": work, "receipt": {"authored": "guard receipt"},
            "cold_preflight": {"plan": plan}, "cold_args": types.SimpleNamespace(expect_serial=[marker] if expect else [])}
        return state, observed

    def test_original_success_memory_and_full_postcheck_are_all_required_under_lock(self):
        for original_status, memory_pass, changed, expected in (("WITNESSES_OBSERVED", True, False, "WITNESSES_OBSERVED"),
                ("INCOMPLETE", True, False, "INCOMPLETE"), ("WITNESSES_OBSERVED", False, False, "INCOMPLETE"),
                ("WITNESSES_OBSERVED", True, True, "INCOMPLETE")):
            with self.subTest(original=original_status, memory=memory_pass, changed=changed), tempfile.TemporaryDirectory(prefix="cg-") as directory:
                state, observed = self.fixture(Path(directory), original_status, memory_pass=memory_pass)
                calls = []
                def recheck(current, full):
                    self.assertIs(current, state)
                    with (state["prep_work"] / "owner.lock").open("rb") as lock:
                        with self.assertRaises(BlockingIOError):
                            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    calls.append(full)
                    if changed and len(calls) == 2:
                        raise ValueError("authored changed backing input")
                with patch.object(guard, "MemoryObservations", return_value=observed), patch.object(guard, "unchanged_inputs", side_effect=recheck):
                    result = guard.execute(state)
                self.assertEqual(result["status"], expected)
                self.assertEqual(calls, [True, True])
                self.assertEqual(result["original_witness_status"], original_status)
                self.assertEqual(json.loads((state["work"] / "result.json").read_text()), result)
                self.assertEqual(guard.sha((state["work"] / "memory-observations.json").read_bytes()), result["memory_observations"]["sha256"])
                self.assertFalse(result["boot_complete"])
                self.assertFalse(result["gpu_path_complete"])
                if changed:
                    self.assertFalse(result["all_bound_inputs_unchanged"])

    def test_empty_markers_and_missing_durable_original_result_cannot_get_guard_credit(self):
        for expect, durable in ((False, True), (True, False)):
            with self.subTest(expect=expect, durable=durable), tempfile.TemporaryDirectory(prefix="cg-") as directory:
                state, observed = self.fixture(Path(directory), expect=expect, durable=durable)
                with patch.object(guard, "MemoryObservations", return_value=observed), patch.object(guard, "unchanged_inputs"):
                    result = guard.execute(state)
                self.assertEqual(result["status"], "INCOMPLETE")
                self.assertIn("error", result)

    def test_default_missing_inputs_remains_read_only_and_starts_nothing(self):
        with (patch.object(subprocess, "Popen") as popen, patch.object(guard, "execute") as execute,
              contextlib.redirect_stdout(io.StringIO()) as output):
            self.assertEqual(guard.main([]), 2)
        popen.assert_not_called()
        execute.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["status"], "INCOMPLETE")


class ColdPlan(unittest.TestCase):
    def setUp(self):
        PackedInputs.setUp(self)

    def tearDown(self):
        PackedInputs.tearDown(self)

    def test_readonly_preflight_derives_only_exact_packed_aod_and_fixed_ram(self):
        packed = guard.packed_inputs(prep, self.work, self.inventory, self.chain)
        self.session["qualification_file"] = str(self.root / "qualification.json")
        self.session["qualification"] = {"qualification_sha256": "3" * 64, "authored": "already validated runtime"}
        work = self.root / "final"
        calls = []
        def cold_preflight(args):
            calls.append(copy.deepcopy(args))
            self.assertEqual(args.run_dir, work)
            self.assertFalse(args.run_dir.exists())
            self.assertTrue(args.run_dir.parent.is_dir())
            plan = {"source_disk": packed["packed_disk"]["identity"]["path"], "disk_chain": [packed["packed_disk"]["identity"]],
                "ram_gib": args.ram_gib, "scale": args.scale, "qualification": self.session["qualification"],
                "package": args.package, "assets": str(args.assets), "run_dir": str(args.run_dir),
                "frame_size": [1179, 2556], "trustcache": str(args.assets / "root26s-aod.tc")}
            return {"status": "PREFLIGHT_READY", "plan": plan}
        cold = types.SimpleNamespace(parser=prep.cold.parser, command=prep.cold.command, preflight=cold_preflight)
        fake_prep = types.SimpleNamespace(cold=cold)
        context = {"prep": fake_prep, "plan": {"session": self.session}, "prep_work": self.work, "runner": HERE,
            "inventory": self.inventory, "packed": packed, "app_inputs": [], "apps_audit": {"authored": "validated"},
            "prior_evidence": {"frozen_input_identities": {}}, "wallpaper_inspection": {"source_directory": str(HERE), "files": {}},
            "wallpaper_guard": types.SimpleNamespace(output_roots=lambda state: {self.work}),
            "wallpaper_guard_work": self.root / "previous-guard", "wallpaper_guard_source": HERE / "guard_ios26_wallpaper.py"}
        inspection = self.root / "previous-inspection"
        inspection.mkdir()
        before = {str(path): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        args = guard.parser().parse_args(["--wallpaper-inspection-work", str(inspection), "--work", str(work),
                                         "--expect-serial", "explicit authored marker"])
        with patch.object(guard, "preparation_context", return_value=context), patch.object(subprocess, "Popen") as popen:
            state = guard.preflight(args)
        popen.assert_not_called()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].assets, Path(packed["assets"]))
        self.assertEqual(calls[0].variant, "aod")
        self.assertEqual((calls[0].ram_gib, calls[0].scale), (3, 3))
        self.assertEqual(state["cold_args"].run_dir, work / "cold")
        self.assertEqual(state["receipt"]["expected_serial"], ["explicit authored marker"])
        self.assertFalse(work.exists())
        self.assertEqual(before, {str(path): path.read_bytes() for path in self.root.rglob("*") if path.is_file()})


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="final-cold-guard-")
        self.root = Path(self.temp.name)
        self.cold = guard.module_from((HERE / "cold_boot_ios26.py").read_bytes(), HERE / "cold_boot_ios26.py")
        self.plan = {"package": str(self.root / "package"), "run_dir": str(self.root / "run"),
                     "assets": str(self.root / "assets"), "frame_size": [1179, 2556],
                     "trustcache": str(self.root / "tc"), "dtree": str(self.root / "tree"),
                     "ram_gib": 3, "scale": 3, "disk_chain": [], "input_identities": []}
        Path(self.plan["dtree"]).write_bytes(authored_tree())
        self.run = Path(self.plan["run_dir"])
        self.run.mkdir()
        self.write_tree()
        self.observed = guard.MemoryObservations(lambda: mem(3840))
        self.delegate = types.SimpleNamespace(Popen=Mock(return_value=object()), DEVNULL=subprocess.DEVNULL,
            STDOUT=subprocess.STDOUT, PIPE=subprocess.PIPE, TimeoutExpired=subprocess.TimeoutExpired,
            SubprocessError=subprocess.SubprocessError)
        self.proxy = guard.LaunchProxy(self.delegate, self.cold, self.plan, self.observed)

    def tearDown(self):
        self.temp.cleanup()

    def write_tree(self):
        original = Path(self.plan["dtree"]).read_bytes()
        (self.run / "input-device-tree").write_bytes(original)
        (self.run / "device-tree").write_bytes(self.cold.expected_tree(original, 3, 3))

    def launch(self, argv=None, **replace):
        expected, env = self.cold.command(self.plan, 17)
        kwargs = {"env": env, "stdin": self.delegate.DEVNULL, "stdout": object(),
                  "stderr": self.delegate.STDOUT, "pass_fds": (17,), "start_new_session": True,
                  "preexec_fn": lambda: None}
        kwargs.update(replace)
        return self.proxy.Popen(expected if argv is None else argv, **kwargs)

    def test_strict_meminfo_and_exact_floor_boundaries(self):
        self.assertEqual(guard.mem_available_kib(mem(3840)), 3840 * 1024)
        self.assertEqual(guard.mem_available_kib(b"MemAvailable:\t524288\tkB\n"), 512 * 1024)
        invalid = [b"", b"MemTotal: 99 kB\n", b"MemAvailable: 1 kB\nMemAvailable: 2 kB\n",
                   b"MemAvailable: 512 MB\n", b"MemAvailable: -1 kB\n", b"MemAvailable: 1.5 kB\n",
                   b" MemAvailable: 524288 kB\n", b"MemAvailable: 524288 kB extra\n",
                   b"MemAvailable: 9007199254740992 kB\n", b"MemAvailable: \xff kB\n"]
        for body in invalid:
            with self.subTest(body=body), self.assertRaises((ValueError, UnicodeError)):
                guard.mem_available_kib(body)
        observed = guard.MemoryObservations(lambda: b"MemAvailable: 524287 kB\n")
        self.assertFalse(observed.sample("storage_report", 512)["passed"])

    def test_actual_qualified_command_is_unchanged_and_only_its_spawn_is_guarded(self):
        original, _ = self.cold.command(self.plan, 17)
        sentinel = self.delegate.Popen.return_value
        self.assertIs(self.launch(), sentinel)
        actual = self.delegate.Popen.call_args.args[0]
        self.assertEqual(actual, original)
        self.assertNotIn("-m", actual)  # vresearch allocates from the validated ADT.
        self.assertEqual(self.observed.launch_tree["ram_bytes"], 3 << 30)
        self.assertTrue(self.observed.launch_command["frozen_command_unchanged"])
        self.assertTrue(self.observed.prelaunch_passed)
        self.assertEqual(self.proxy.PIPE, subprocess.PIPE)
        self.proxy.Popen(["/authored/qemu-img", "info"], env={})
        self.assertEqual(self.observed.launch_attempts, 1)
        self.assertEqual(self.delegate.Popen.call_count, 2)

    def test_no_post_spawn_observation_can_lose_the_returned_child(self):
        class Opaque:
            def __getattribute__(self, key):
                raise AssertionError("no child inspection inside Popen wrapper: " + key)
        child = Opaque()
        order = []
        def reader():
            order.append("memory")
            return mem(3840)
        def popen(*args, **kwargs):
            order.append("spawn")
            self.observed.reader = lambda: (_ for _ in ()).throw(AssertionError("read after spawn"))
            return child
        self.observed.reader = reader
        self.delegate.Popen.side_effect = popen
        self.assertIs(self.launch(), child)
        self.assertEqual(order, ["memory", "spawn"])

    def test_insufficient_or_unreadable_prelaunch_never_spawns(self):
        for reader in (lambda: mem(3839), lambda: b"MemTotal: 1 kB\n",
                       lambda: (_ for _ in ()).throw(OSError("authored read error"))):
            with self.subTest(reader=reader):
                self.observed = guard.MemoryObservations(reader)
                self.proxy = guard.LaunchProxy(self.delegate, self.cold, self.plan, self.observed)
                with self.assertRaisesRegex(ValueError, "fresh MemAvailable"):
                    self.launch()
                self.assertIsNotNone(self.observed.violation)
        self.delegate.Popen.assert_not_called()

    def test_wrong_or_changed_tree_and_ram_are_refused_before_memory_or_spawn(self):
        for mutate in (lambda: self.plan.update(ram_gib=4), lambda: self.plan.update(ram_gib=True),
                       lambda: self.plan.update(scale=2),
                       lambda: (self.run / "device-tree").write_bytes(authored_tree()),
                       lambda: (self.run / "input-device-tree").write_bytes(b"changed copy")):
            with self.subTest(mutate=mutate):
                self.plan.update(ram_gib=3, scale=3)
                self.write_tree()
                self.observed = guard.MemoryObservations(lambda: (_ for _ in ()).throw(AssertionError("too early")))
                self.proxy = guard.LaunchProxy(self.delegate, self.cold, self.plan, self.observed)
                mutate()
                with self.assertRaises(ValueError):
                    self.launch()
                self.assertEqual(self.observed.sample_count, 0)
        self.delegate.Popen.assert_not_called()

    def test_exact_argv_env_owner_and_single_launch_are_required(self):
        command, env = self.cold.command(self.plan, 17)
        cases = [([*command, "-m", "4G"], {}), (None, {"env": dict(env, ASOFT_NATIVE_EL0_REQUIRED="0")}),
                 (None, {"pass_fds": (17, 18)}), (None, {"start_new_session": False}),
                 (None, {"shell": True}), (None, {"cwd": str(self.root)})]
        for argv, kwargs in cases:
            with self.subTest(kwargs=kwargs, argv=argv):
                self.observed = guard.MemoryObservations(lambda: mem(3840))
                self.proxy = guard.LaunchProxy(self.delegate, self.cold, self.plan, self.observed)
                with self.assertRaises(ValueError):
                    self.launch(argv, **kwargs)
        self.delegate.Popen.assert_not_called()
        self.observed = guard.MemoryObservations(lambda: mem(3840))
        self.proxy = guard.LaunchProxy(self.delegate, self.cold, self.plan, self.observed)
        self.launch()
        with self.assertRaisesRegex(ValueError, "exactly one"):
            self.launch()
        self.assertEqual(self.delegate.Popen.call_count, 1)

    def test_runtime_failure_latches_through_recovered_final_sample(self):
        self.launch()
        reader = Mock(side_effect=[mem(512), mem(511), mem(4096)])
        self.observed.reader = reader
        args = types.SimpleNamespace(min_free_mib=1, max_log_mib=64)
        original_popen = subprocess.Popen
        with guard.installed_memory_hooks(self.cold, self.plan, self.observed):
            self.assertIs(subprocess.Popen, original_popen)
            good = self.cold.storage_report(self.run, args)
            bad = self.cold.storage_report(self.run, args)
            final = self.cold.storage_report(self.run, args)
        self.assertTrue(good["within_bounds"])
        self.assertFalse(bad["within_bounds"])
        self.assertFalse(final["within_bounds"])
        self.assertEqual(final["memory"]["violation"], bad["memory"]["violation"])
        self.assertFalse(self.observed.report()["passed"])

    def test_storage_read_errors_nonraise_and_do_not_erase_original_limits(self):
        args = types.SimpleNamespace(min_free_mib=1, max_log_mib=64)
        for reader in (lambda: b"MemAvailable: 1 MB\n", lambda: (_ for _ in ()).throw(OSError("gone"))):
            observed = guard.MemoryObservations(reader)
            with guard.installed_memory_hooks(self.cold, self.plan, observed):
                self.assertFalse(self.cold.storage_report(self.run, args)["within_bounds"])
        original = self.cold.storage_report
        for report in ({"within_bounds": False, "free_bytes": 0}, OSError("storage unavailable")):
            self.cold.storage_report = Mock(side_effect=report) if isinstance(report, Exception) else Mock(return_value=report)
            with guard.installed_memory_hooks(self.cold, self.plan, guard.MemoryObservations(lambda: mem(1024))):
                self.assertFalse(self.cold.storage_report(self.run, args)["within_bounds"])
        self.cold.storage_report = original

    def test_pre_shutdown_sampler_always_delegates_and_hooks_restore(self):
        old_subprocess, old_storage = self.cold.subprocess, self.cold.storage_report
        shutdown = self.cold.shutdown = Mock(return_value={"authored": "original cleanup"})
        observed = guard.MemoryObservations(lambda: (_ for _ in ()).throw(KeyboardInterrupt()))
        with self.assertRaisesRegex(RuntimeError, "body error"):
            with guard.installed_memory_hooks(self.cold, self.plan, observed):
                self.assertEqual(self.cold.shutdown("child", "qmp", capture="frame"), {"authored": "original cleanup"})
                raise RuntimeError("body error")
        shutdown.assert_called_once_with("child", "qmp", capture="frame")
        self.assertIs(self.cold.subprocess, old_subprocess)
        self.assertIs(self.cold.storage_report, old_storage)
        self.assertIs(self.cold.shutdown, shutdown)
        self.assertIsNotNone(observed.violation)

    def test_original_owner_cleans_assigned_child_after_memory_stop(self):
        for path in self.run.iterdir():
            path.unlink()
        self.run.rmdir()
        events = []
        child = types.SimpleNamespace(pid=12345, returncode=None, poll=lambda: None)
        def waited(timeout):
            events.append("wait")
            child.returncode = 0
            return 0
        child.wait = waited
        self.delegate.Popen = Mock(return_value=child)
        self.cold.subprocess = self.delegate
        self.cold.require_phone = Mock()
        self.cold.subreaper = Mock()
        self.cold.reap_owned = Mock(side_effect=lambda: events.append("reap") or {"echild": True, "forced_descendants": []})
        self.cold.prepare_run = Mock(side_effect=lambda plan: self.write_tree())
        self.cold.recheck_package = Mock()
        # This host Python omits Linux seal constants. Only the fixture mocks
        # sealing; the frozen owner and physical execution are unchanged.
        self.cold.fcntl = types.SimpleNamespace(fcntl=Mock(), F_ADD_SEALS=1033,
            F_SEAL_GROW=4, F_SEAL_SHRINK=2, F_SEAL_SEAL=1)
        args = types.SimpleNamespace(seconds=30, expect_serial=["AUTHORED ONLY"], min_free_mib=1, max_log_mib=64)
        observed = guard.MemoryObservations(Mock(side_effect=[mem(3840), mem(511), mem(4096), mem(4096)]))
        with guard.installed_memory_hooks(self.cold, self.plan, observed), contextlib.redirect_stdout(io.StringIO()):
            result = self.cold.boot({"plan": self.plan}, args)
        self.assertEqual(self.delegate.Popen.call_count, 1)
        self.assertEqual(events, ["wait", "reap"])
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertTrue(result["guest_started"])
        self.assertEqual(result["stop_reason"], "storage_bound")
        self.assertTrue(result["cleanup"]["echild"])
        self.assertFalse(result["final_storage"]["within_bounds"])
        self.assertEqual(result["final_storage"]["memory"]["violation"]["phase"], "storage_report")

    def test_memory_success_does_not_invent_or_replace_original_witnesses(self):
        w = {"serial_markers_found": ["explicit authored marker"], "fatal_markers": [],
             "native_initialization": True, "native_execution": True, "gpu_execution": True, "frame_captured": True}
        result = {"witnesses": w, "stop_reason": "requested_witnesses_observed", "package_rechecked_after_run": True,
            "final_storage": {"within_bounds": True, "evidence_truncated": []},
            "cleanup": {"stop_flushed": True, "echild": True, "exit_code": 0, "forced_qemu": False,
                        "forced_descendants": [], "errors": []}}
        self.assertEqual(self.cold.witness_status(result, w["serial_markers_found"]), "WITNESSES_OBSERVED")
        self.assertEqual(self.cold.witness_status(result, []), "INCOMPLETE")
        for field in ("native_initialization", "native_execution", "gpu_execution", "frame_captured"):
            w[field] = False
            self.assertEqual(self.cold.witness_status(result, w["serial_markers_found"]), "INCOMPLETE")
            w[field] = True
        result["final_storage"]["within_bounds"] = False
        self.assertEqual(self.cold.witness_status(result, w["serial_markers_found"]), "INCOMPLETE")


if __name__ == "__main__":
    unittest.main()
