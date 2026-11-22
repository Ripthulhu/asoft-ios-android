#!/usr/bin/env python3
"""Synthetic orchestration checks: no QEMU, GPU, Apple image, network or Android execution."""
import contextlib
import io
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

import prepare_ios26 as prep
import prepare_ios26_stages as stages


def qcow(path, backing=None):
    header = bytearray(104)
    header[:4] = b"QFI\xfb"
    name = str(backing).encode() if backing else b""
    struct.pack_into(">IQI", header, 4, 3, 104 if name else 0, len(name))
    struct.pack_into(">Q", header, 24, 32 << 30)
    path.write_bytes(header + name)


def authored_manifest():
    files = {key: {"url": "https://example.invalid/" + key, "sha256": "a" * 64}
             for key in ("sysroot", "dtFixup", "gpuPlugin", "fcsKeys")}
    cloud = [{"name": name, "bytes": 512} for name in (
        "kernelcache.research.vphone600", "Firmware/sptm.vresearch1.release.im4p",
        "Firmware/txm.iphoneos.research.im4p", "Firmware/all_flash/DeviceTree.vphone600ap.im4p",
        "RAM.dmg", "Firmware/RAM.dmg.trustcache", "GPU.dmg.aea", "Firmware/GPU.dmg.aea.trustcache")]
    iphone = [{"name": name, "bytes": 512, "method": 0, "crc32": "12345678"} for name in
              ("OS.dmg.aea", "SYS.dmg.aea", "APP.dmg", "Firmware/OS.dmg.aea.trustcache",
               "Firmware/SYS.dmg.aea.trustcache", "Firmware/APP.dmg.trustcache")]
    return {"format": 1, "shared": {"files": files,
            "vars": {"RAMDISK": "RAM.dmg", "IMG": "GPU.dmg", "BUNDLE": "GPU.bundle", "PLUGIN": "plugin.dylib"},
            "sources": {"cloudos": {"url": "https://example.invalid/cloud", "members": cloud}}},
            "os": {"ios26": {"build": "23G90", "vars": {"OS": "OS.dmg", "SYSOS": "SYS.dmg", "APPOS": "APP.dmg"},
            "sources": {"cloudos": {"members": cloud}, "iphone": {"url": "https://example.invalid/iphone", "bytes": 4096, "members": iphone}},
            "dscPatches": {"posterBoard": ["--test", "one"], "lockLongPress": ["--test", "two"], "aod": ["--test", "three"],
                           "files": ["dsc.0", "dsc.1", "dsc.2"]}}}}


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="p26-")
        self.root = Path(self.temp.name)
        self.package, self.results, self.tooling, self.work = [self.root / n for n in ("pkg", "proof", "tools", "work")]
        for path in (self.package / "lib", self.results, self.tooling):
            path.mkdir(parents=True)
        (self.package / "qemu-system-aarch64").write_text("AUTHORED NONEXECUTABLE PLACEHOLDER\n")
        (self.package / "lib/libplaceholder.so").write_text("AUTHORED NOT A LIBRARY\n")
        self.archive_hash, self.header_hash = "a" * 64, "b" * 64
        (self.package / "core-fixture-build.json").write_text(json.dumps({
            "library": {"sha256": self.archive_hash}, "header": {"sha256": self.header_hash}}))
        (self.package / "qemu-build.json").write_text(json.dumps({
            "runtime_archive_sha256": self.archive_hash, "runtime_header_sha256": self.header_hash}))
        checksums = {p.relative_to(self.package).as_posix(): prep.cold.sha(p) for p in self.package.rglob("*") if p.is_file()}
        (self.package / "SHA256SUMS").write_text("".join(sha + "  " + name + "\n" for name, sha in checksums.items()))
        cases = []
        for name in sorted(prep.cold.CASES):
            path = self.results / name / "output.log"
            path.parent.mkdir()
            path.write_text("AUTHORED NONPHYSICAL PROTOCOL FIXTURE\n")
            row = {"case": name, "passed": True, "log_sha256": prep.cold.sha(path)}
            if name == "probe":
                row["probe"] = {"checks_passed": 127, "backend": "system_cpu_shadow"}
            cases.append(row)
        self.qualification = self.results / "qualification.json"
        self.qualification.write_text(json.dumps({"all_cases_passed": True, "package_rechecked": True,
            "package_sha256": checksums, "cases": cases, "device": {"ro.build.fingerprint": "AUTHORED-NOT-A-PHONE"}}))
        self.manifest = authored_manifest()
        names = [*prep.TOOL_ENTRIES.values(), "setup/phone/prelude.sh", "setup/phone/locale.py",
                 "setup/steps/ios26/test.sh", "setup/scripts/ios26/test.py"]
        names += ["setup/phone/jobs/" + s + ".sh" for s in stages.STAGES
                  if s not in stages.NETWORK | stages.GUEST_BOOTS | {"ios26-pack"}]
        for name in names:
            path = self.tooling / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# authored test placeholder\n")
        (self.tooling / "setup/asoft-setup.json").write_text(json.dumps(self.manifest))
        self.tools_hash = self.write_tool_manifest()
        self.options = ["--package", str(self.package), "--qualification", str(self.qualification),
                        "--tooling", str(self.tooling), "--tooling-sha256", self.tools_hash, "--work", str(self.work)]
        self.args = prep.parser().parse_args(self.options)

    def tearDown(self):
        self.temp.cleanup()

    def write_tool_manifest(self):
        files = {p.relative_to(self.tooling).as_posix(): {"bytes": p.stat().st_size, "sha256": prep.cold.sha(p),
                 "mode": stat.S_IMODE(p.stat().st_mode)} for p in self.tooling.rglob("*")
                 if p.is_file() and p.name != "tooling-manifest.json"}
        manifest = {"schema": 1, "kind": "standalone_ios26_preparation_tools", "requires_qualified_qemu": True,
                    "entrypoints": prep.TOOL_ENTRIES, "files": files}
        path = self.tooling / "tooling-manifest.json"
        path.write_text(json.dumps(manifest))
        return prep.cold.sha(path)

    def plan(self, extra=()):
        return prep.preflight(prep.parser().parse_args([*self.options, *extra]))

    def initialize(self):
        plan = self.plan()
        with prep.exclusive_session(plan):
            pass
        return plan

    def checkpoint(self, plan, stage, records):
        completed = plan["completed"]
        previous = prep.cold.sha(self.work / "checkpoints" / (completed[-1] + ".json")) if completed else None
        row = {"schema": 1, "stage": stage, "session_sha256": prep.digest(plan["session"]),
               "previous_sha256": previous, "status": "STAGE_COMPLETE", "artifacts": records}
        prep.atomic_json(self.work / "checkpoints" / (stage + ".json"), row)
        plan["artifacts"].update(records)
        plan["completed"].append(stage)

    def test_no_arguments_launches_nothing(self):
        with patch.object(prep.subprocess, "Popen") as popen, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(prep.main([]), 2)
        popen.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["status"], "INCOMPLETE")

    def test_valid_default_preflight_is_read_only_and_stops_before_first_boot(self):
        before = {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with patch.object(prep.subprocess, "Popen") as popen:
            plan = self.plan()
        popen.assert_not_called()
        self.assertFalse(self.work.exists())
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        self.assertEqual(plan["remaining"][-1], "ios26-partition")
        self.assertEqual(plan["guest_boot_stages"], [])
        self.assertEqual(plan["session"]["helper_ram_mib"], 2048)

    def test_old_fifteen_case_report_and_changed_log_refused(self):
        original = json.loads(self.qualification.read_text())
        report = dict(original, cases=[r for r in original["cases"] if r["case"] not in {"core", "core-no-argument-buffers"}])
        self.qualification.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, "core"):
            self.plan()
        self.qualification.write_text(json.dumps(original))
        (self.results / "core/output.log").write_text("changed")
        with self.assertRaisesRegex(ValueError, "log mismatch"):
            self.plan()

    def test_tool_receipt_contents_extras_and_symlinks_refused(self):
        with self.assertRaisesRegex(ValueError, "receipt"):
            self.plan(["--tooling-sha256", "c" * 64])
        (self.tooling / "unexpected").write_text("x")
        with self.assertRaisesRegex(ValueError, "unchecked"):
            self.plan()
        (self.tooling / "unexpected").unlink()
        target = self.tooling / "helper/Image16k.gz"
        target.unlink()
        target.symlink_to(self.package / "qemu-system-aarch64")
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.plan()

    def test_core_qemu_archive_identity_is_required(self):
        record = json.loads((self.package / "qemu-build.json").read_text())
        record["runtime_archive_sha256"] = "c" * 64
        (self.package / "qemu-build.json").write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, "different runtime"):
            prep.same_runtime(self.package)

    def test_execution_requires_explicit_network_and_boot_flags_before_process(self):
        with patch.object(prep.cold, "require_phone") as phone:
            with self.assertRaisesRegex(ValueError, "allow-network"):
                prep.execute(self.plan(), self.args)
            args = prep.parser().parse_args([*self.options, "--through", "ios26-pack", "--allow-network"])
            with self.assertRaisesRegex(ValueError, "allow-guest-boots"):
                prep.execute(prep.preflight(args), args)
        phone.assert_not_called()
        self.assertFalse(self.work.exists())

    def test_memory_gate_uses_available_not_total_and_never_changes_ram(self):
        with patch.object(prep, "mem_available_mib", return_value=3174):
            self.assertEqual(prep.require_memory(2048), 3174)
            with self.assertRaisesRegex(ValueError, "3840"):
                prep.require_memory(3072)

    def test_exclusive_lock_and_session_input_change(self):
        plan = self.initialize()
        with prep.exclusive_session(plan):
            with self.assertRaisesRegex(ValueError, "another preparation owner"):
                with prep.exclusive_session(plan):
                    self.fail("acquired conflicting lock")
        changed = dict(plan["session"], helper_ram_mib=4096)
        with self.assertRaisesRegex(ValueError, "inputs/configuration changed"):
            prep.load_checkpoints(self.work, changed)

    def test_checkpoint_resume_verifies_full_artifact_and_sequence(self):
        plan = self.initialize()
        attempt = prep.next_attempt(plan, "shared-fetch")
        artifact = prep.output_path(attempt, "downloads/test")
        artifact.write_bytes(b"authored checkpoint data")
        record = prep.file_record(artifact, self.work)
        self.checkpoint(plan, "shared-fetch", {"downloads/test": record})
        loaded, complete = prep.load_checkpoints(self.work, plan["session"])
        self.assertEqual(complete, ["shared-fetch"])
        self.assertEqual(loaded["downloads/test"], record)
        artifact.write_bytes(b"authored checkpoint DATa")
        with self.assertRaisesRegex(ValueError, "artifact changed"):
            prep.load_checkpoints(self.work, plan["session"])

    def test_checkpoint_cannot_jump_a_stage_or_import_external_disk(self):
        plan = self.initialize()
        self.checkpoint(plan, "shared-unpack", {})
        with self.assertRaisesRegex(ValueError, "sequence"):
            prep.load_checkpoints(self.work, plan["session"])
        external = self.root / "external.qcow2"
        qcow(external)
        owned = self.work / "attempts/owned.qcow2"
        qcow(owned, external)
        with self.assertRaisesRegex(ValueError, "backing disk escapes"):
            prep.file_record(owned, self.work)

    def test_only_incomplete_input_operations_resume_the_same_attempt(self):
        plan = self.initialize()
        first = prep.next_attempt(plan, "shared-fetch")
        prep.atomic_json(first / "stage-inputs.json", {"stage": "shared-fetch", "session_sha256": prep.digest(plan["session"]), "inputs": {}})
        self.assertEqual(first, prep.next_attempt(plan, "shared-fetch"))
        one = prep.next_attempt(plan, "shared-build")
        prep.atomic_json(one / "stage-inputs.json", {"stage": "shared-build", "session_sha256": prep.digest(plan["session"]), "inputs": {}})
        self.assertNotEqual(one, prep.next_attempt(plan, "shared-build"))
        (first / "members.log").write_text("old failure")
        self.assertEqual(prep.operation_name(first, "members"), "members-2")

    def test_partial_resume_refuses_symlinked_files_root(self):
        plan = self.initialize()
        attempt = prep.next_attempt(plan, "shared-fetch")
        prep.atomic_json(attempt / "stage-inputs.json", {"stage": "shared-fetch", "session_sha256": prep.digest(plan["session"]), "inputs": {}})
        outside = self.root / "outside"
        outside.mkdir()
        (attempt / "files").rmdir()
        (attempt / "files").symlink_to(outside, target_is_directory=True)
        with patch.object(prep, "java_input") as java:
            with self.assertRaisesRegex(ValueError, "symlink"):
                prep.next_attempt(plan, "shared-fetch")
            with self.assertRaisesRegex(ValueError, "symlink"):
                prep.output_path(attempt, "new-download")
        java.assert_not_called()
        self.assertEqual(list(outside.iterdir()), [])

    def test_decrypt_attempt_never_reuses_unverified_plaintext_prefix(self):
        plan = self.initialize()
        first = prep.next_attempt(plan, "ios26-decrypt")
        prep.atomic_json(first / "stage-inputs.json", {"stage": "ios26-decrypt", "session_sha256": prep.digest(plan["session"]), "inputs": {}})
        old = prep.output_path(first, "os/SYS.dmg")
        old.write_bytes(b"damaged existing plaintext")
        Path(str(old) + ".progress").write_text("1 100 " + "0" * 64 + " 24 99")
        second = prep.next_attempt(plan, "ios26-decrypt")
        self.assertNotEqual(first, second)
        self.assertFalse((second / "files/os/SYS.dmg").exists())
        self.assertEqual(old.read_bytes(), b"damaged existing plaintext")

    def test_download_sidecar_symlink_or_hardlink_is_refused_before_reuse(self):
        plan = self.initialize()
        attempt = prep.next_attempt(plan, "shared-fetch")
        prep.atomic_json(attempt / "stage-inputs.json", {"stage": "shared-fetch", "session_sha256": prep.digest(plan["session"]), "inputs": {}})
        outside = self.root / "preserve"
        outside.write_bytes(b"must remain unchanged")
        sidecar = attempt / "files/input.part"
        for mode in ("symlink", "hardlink"):
            with self.subTest(mode=mode):
                if mode == "symlink":
                    sidecar.symlink_to(outside)
                else:
                    os.link(outside, sidecar)
                with self.assertRaises(ValueError):
                    prep.next_attempt(plan, "shared-fetch")
                self.assertEqual(outside.read_bytes(), b"must remain unchanged")
                sidecar.unlink()

    def test_stale_child_record_never_kills_an_unrelated_pid(self):
        plan = self.initialize()
        attempt = prep.next_attempt(plan, "shared-fetch")
        identity = {"pid": 987654321, "start_ticks": 123}
        prep.atomic_json(attempt / "one.child.json", identity)
        with patch.object(prep, "process_identity", return_value=identity), patch.object(prep.os, "kill") as kill:
            with self.assertRaisesRegex(ValueError, "still alive"):
                prep.refuse_live_children(self.work)
        kill.assert_not_called()
        with patch.object(prep, "process_identity", return_value={"pid": 987654321, "start_ticks": 456}):
            prep.refuse_live_children(self.work)

    def test_recipe_mutations_are_new_disks_or_overlays(self):
        for stage in stages.STAGES:
            if stage in stages.NETWORK | stages.GUEST_BOOTS | {"ios26-pack"}:
                continue
            recipe = stages.job(stage, self.manifest)
            self.assertTrue(all(d["mode"] in {"ro", "new", "overlay"} for d in recipe["disks"]))
        for stage in ("ios26-persona", "ios26-locale"):
            self.assertEqual(stages.job(stage, self.manifest)["disks"][0]["mode"], "overlay")
        self.assertEqual(stages.boot_inputs("ios26-firstboot")["kernel"], "cloud/kernelcache.research.vphone600.decompressed")
        self.assertEqual(stages.boot_inputs("ios26-wallpaper")["settle_seconds"], 360)

    def test_overlay_creation_preserves_source_bytes_and_absolute_chain(self):
        plan = self.initialize()
        base = self.work / "attempts/base.qcow2"
        qcow(base)
        original = base.read_bytes()
        attempt = prep.next_attempt(plan, "ios26-persona")
        observed = []
        def create(plan_arg, argv, directory, name, args, seconds=60):
            observed.append(argv)
            qcow(Path(argv[-1]), argv[argv.index("-b") + 1])
        with patch.object(prep, "image_tool", side_effect=create):
            output = prep.create_disk(plan, attempt, "root26g.qcow2", self.args, source=base)
        self.assertEqual(base.read_bytes(), original)
        self.assertNotEqual(output, base)
        self.assertEqual(observed[0][observed[0].index("-b") + 1], str(base))

    def test_native_helper_command_has_no_fallback_or_inherited_gpu_override(self):
        plan = self.plan()
        argv, env = prep.helper_command(plan, self.root / "run", [])
        self.assertIn("memory-backend-memfd,id=m0,size=2048M,share=on", argv)
        self.assertIn("cortex-a76,x-host-counter=on,cntfrq=38400000", argv)
        self.assertIn(str(self.tooling / "helper/Image16k.gz"), argv)
        self.assertEqual(env["ASOFT_NATIVE_EL0_REQUIRED"], "1")
        for name in ("ASOFT_VIRT_REIMS_TEST", "ASOFT_NATIVE_EL0_TPIDRRO", "ASOFT_NATIVE_EL0_TPIDRRO_TRAP", "VK_ICD_FILENAMES", "LD_PRELOAD", "ASOFT_GUEST_RAM_FD"):
            self.assertNotIn(name, env)

    def test_return_tar_is_complete_contained_and_expected(self):
        raw = self.root / "returned.raw"
        with tarfile.open(raw, "w") as archive:
            info = tarfile.TarInfo("returned/data")
            info.size = 5
            archive.addfile(info, io.BytesIO(b"hello"))
        output = self.root / "returned"
        output.mkdir()
        prep.safe_return_tar(raw, raw.stat().st_size, output, ["returned"])
        self.assertEqual((output / "returned/data").read_bytes(), b"hello")
        for bad in ("../escape", "/absolute", "unexpected"):
            with self.subTest(bad=bad):
                with tarfile.open(raw, "w") as archive:
                    info = tarfile.TarInfo(bad)
                    info.size = 1
                    archive.addfile(info, io.BytesIO(b"x"))
                with self.assertRaises(ValueError):
                    prep.safe_return_tar(raw, raw.stat().st_size, output, ["returned"])

    def test_return_tar_links_truncation_empty_and_missing_outputs_are_refused(self):
        for kind in ("symlink", "truncated", "empty", "missing"):
            with self.subTest(kind=kind):
                raw = self.root / (kind + ".tar")
                with tarfile.open(raw, "w") as archive:
                    info = tarfile.TarInfo("returned")
                    if kind == "symlink":
                        info.type, info.linkname = tarfile.SYMTYPE, "../escaped"
                        archive.addfile(info)
                    elif kind == "empty":
                        archive.addfile(info)
                    elif kind == "truncated":
                        info.size = 9000
                        archive.addfile(info, io.BytesIO(b"x" * 9000))
                output = self.root / (kind + "-out")
                output.mkdir()
                size = 9216 if kind == "truncated" else raw.stat().st_size
                with self.assertRaises(ValueError):
                    prep.safe_return_tar(raw, size, output, ["returned"])

    def test_oversized_extension_header_is_refused_before_tarfile_can_allocate(self):
        raw = self.root / "oversized.raw"
        header = tarfile.TarInfo("././@LongLink")
        header.type = tarfile.GNUTYPE_LONGNAME
        header.size = 1 << 30
        with raw.open("wb") as stream:
            stream.write(header.tobuf())
            stream.truncate(2 << 30)
        output = self.root / "tar-out"
        output.mkdir()
        with patch.object(prep.tarfile, "open") as parse:
            with self.assertRaisesRegex(ValueError, "longname"):
                prep.safe_return_tar(raw, 10240, output, ["returned"])
        parse.assert_not_called()
        self.assertEqual(list(output.iterdir()), [])

    def test_native_flags_or_done_marker_alone_never_complete_helper(self):
        good = {"natural_exit": True, "done_codes": [0],
                "cleanup": {"exit_code": 0, "echild": True, "forced_qemu": False, "forced_descendants": [], "errors": []},
                "witnesses": {"native_initialization": True, "native_execution": True, "fatal_markers": []}}
        self.assertTrue(prep.vm_success(good, True))  # Natural poweroff needs no QMP stop acknowledgment.
        for patch_value in ({"natural_exit": False}, {"done_codes": [1]}, {"done_codes": [0, 0]}, {"error": "timeout"},
                            {"witnesses": {"native_initialization": True, "native_execution": False, "fatal_markers": []}},
                            {"cleanup": dict(good["cleanup"], forced_qemu=True)}):
            self.assertFalse(prep.vm_success(dict(good, **patch_value), True))

    def test_wallpaper_requires_gpu_visible_frame_saved_disk_and_settling(self):
        good = {"stage": "ios26-wallpaper", "milestone": True, "settled": True,
                "cleanup": {"exit_code": 0, "echild": True, "stop_flushed": True},
                "witnesses": {"native_initialization": True, "native_execution": True, "fatal_markers": [],
                              "gpu_execution": True, "frame_captured": True}}
        self.assertTrue(prep.vm_success(good, False))
        for name in ("gpu_execution", "frame_captured", "native_execution"):
            self.assertFalse(prep.vm_success(dict(good, witnesses=dict(good["witnesses"], **{name: False})), False))
        self.assertFalse(prep.vm_success(dict(good, cleanup=dict(good["cleanup"], stop_flushed=False)), False))
        self.assertFalse(prep.vm_success(dict(good, settled=False), False))

    def test_script_fill_preserves_shell_variables_but_rejects_missing_placeholders(self):
        self.assertEqual(stages.fill("echo ${A} {TIMEBASE}", {"TIMEBASE": 38400000}), "echo ${A} 38400000")
        with self.assertRaisesRegex(ValueError, "unresolved"):
            stages.fill("echo {MISSING}", {})

    def test_console_echo_cannot_satisfy_split_markers(self):
        console = prep.GuestConsole(self.root / "not-used")
        fake = Mock()
        fake.recv.side_effect = BlockingIOError()
        console.socket = fake
        with patch.object(prep.os, "urandom", return_value=b"12345678"):
            console.send("echo hello")
        wire = fake.sendall.call_args.args[0]
        start, end = console.pending
        self.assertNotIn(start, wire)
        self.assertNotIn(end, wire)
        console.buffer = wire
        self.assertIsNone(console.poll())
        console.buffer += start + b"\r\nhello\r\n" + end
        self.assertIn("hello", console.poll())

    def test_console_flood_yields_to_owner_bounds(self):
        console = prep.GuestConsole(self.root / "not-used")
        console.socket = Mock()
        console.socket.recv.return_value = b"x" * 65536
        self.assertIsNone(console.poll())
        self.assertEqual(console.socket.recv.call_count, 4)
        self.assertEqual(len(console.buffer), 4 * 65536)

    def test_android_adapter_inherits_only_runtime_whitelist_and_requires_result_file(self):
        plan = self.initialize()
        attempt = prep.next_attempt(plan, "shared-fetch")
        observed = []
        def process(argv, env, directory, name, seconds, args):
            observed.append(env)
            request = json.loads(Path(argv[-1]).read_text())
            result = Path(request["result_file"])
            result.parent.mkdir(parents=True)
            result.write_text('{"schema":1,"status":"COMPLETE"}')
            return ""  # Completion does not depend on app_process stdout.
        inherited = {"BOOTCLASSPATH": "/apex/authored/test.jar", "ANDROID_ROOT": "/system",
                     "LD_PRELOAD": "untrusted.so", "CLASSPATH": "untrusted.dex", "ASOFT_NATIVE_EL0": "0"}
        with patch.dict(prep.os.environ, inherited, clear=True), patch.object(prep, "run_process", side_effect=process):
            prep.java_input(plan, {"op": "url"}, attempt, "input", self.args)
        self.assertEqual(observed[0]["BOOTCLASSPATH"], inherited["BOOTCLASSPATH"])
        self.assertEqual(observed[0]["CLASSPATH"], str(self.tooling / "java/classes.dex"))
        self.assertNotIn("LD_PRELOAD", observed[0])
        self.assertNotIn("ASOFT_NATIVE_EL0", observed[0])
        with patch.dict(prep.os.environ, {}, clear=True), patch.object(prep, "run_process") as process:
            with self.assertRaisesRegex(ValueError, "BOOTCLASSPATH"):
                prep.java_input(plan, {"op": "url"}, attempt, "second", self.args)
        process.assert_not_called()

    def test_empty_adapter_exit_zero_never_counts_as_complete(self):
        plan = self.initialize()
        attempt = prep.next_attempt(plan, "shared-fetch")
        with patch.dict(prep.os.environ, {"BOOTCLASSPATH": "test"}), patch.object(prep, "run_process", return_value=""):
            with self.assertRaisesRegex(ValueError, "no complete result"):
                prep.java_input(plan, {"op": "url"}, attempt, "input", self.args)

    def test_helper_smoke_is_separate_nonce_bound_and_has_no_setup_checkpoints(self):
        args = prep.parser().parse_args([*self.options, "--helper-smoke"])
        plan = prep.preflight(args)
        self.assertEqual(plan["remaining"], [])
        self.assertEqual(plan["network_stages"], [])
        self.assertEqual(plan["guest_boot_stages"], [])
        self.assertFalse(self.work.exists())
        def vm(plan_arg, stage, attempt, argv, env, options):
            self.assertEqual(stage, "helper-smoke")
            self.assertEqual(options.smoke_seconds, 180)
            expected = json.loads((attempt / "expected.json").read_text())
            with tarfile.open(attempt / "in.tar") as archive:
                script = archive.extractfile("run.sh").read().decode()
                self.assertIn(expected["nonce"], script)
                self.assertNotIn("Apple", script)
            raw = attempt / "out.raw"
            data = json.dumps(expected).encode()
            with tarfile.open(raw, "w") as archive:
                info = tarfile.TarInfo("smoke-result.json")
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
            return {"out_sizes": [raw.stat().st_size]}
        with patch.object(prep, "supervise_vm", side_effect=vm), patch.object(prep, "recheck"), patch.object(prep, "java_input") as java:
            result = prep.helper_smoke(plan, args)
        java.assert_not_called()
        self.assertEqual(result["status"], "HELPER_SMOKE_PASSED")
        self.assertEqual(result["result"]["page_size"], 16384)
        self.assertFalse(result["boot_complete"])
        self.assertFalse((self.work / "checkpoints").exists())
        prep.load_checkpoints(self.work, plan["session"])
        with self.assertRaisesRegex(ValueError, "inputs/configuration"):
            self.plan()  # A real preparation session cannot adopt this smoke workdir.

    def test_helper_smoke_refuses_wrong_returned_page_size(self):
        args = prep.parser().parse_args([*self.options, "--helper-smoke"])
        plan = prep.preflight(args)
        def vm(plan_arg, stage, attempt, argv, env, options):
            expected = json.loads((attempt / "expected.json").read_text())
            expected["page_size"] = 4096
            raw = attempt / "out.raw"
            data = json.dumps(expected).encode()
            with tarfile.open(raw, "w") as archive:
                info = tarfile.TarInfo("smoke-result.json")
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
            return {"out_sizes": [raw.stat().st_size]}
        with patch.object(prep, "supervise_vm", side_effect=vm), patch.object(prep, "recheck"):
            with self.assertRaisesRegex(ValueError, "page-size"):
                prep.helper_smoke(plan, args)
        self.assertEqual(json.loads((self.work / "result.json").read_text())["status"], "INCOMPLETE")
        self.assertFalse((self.work / "checkpoints").exists())

    def test_tool_cleanup_reaps_even_on_exit_race_and_final_wait_timeout(self):
        child = Mock(pid=987654321, returncode=None)
        child.poll.return_value = None
        child.terminate.side_effect = ProcessLookupError()
        child.wait.side_effect = subprocess.TimeoutExpired("authored-tool", 5)
        with patch.object(prep.os, "killpg", side_effect=ProcessLookupError()), patch.object(prep.cold, "reap_owned", return_value={"echild": True, "forced_descendants": []}) as reap:
            result = prep.finish_process(child)
        reap.assert_called_once()
        self.assertEqual(child.wait.call_count, 2)
        self.assertTrue(result["echild"])
        self.assertTrue(result["forced_process"])
        self.assertTrue(any("final wait" in item for item in result["errors"]))

    def test_final_elapsed_time_refreshes_after_fast_natural_exit(self):
        plan = self.plan()
        cleanup = {"exit_code": 0, "echild": True, "forced_qemu": False, "forced_descendants": [], "errors": []}
        for name, polls, clock in (("no-poll", [0, 0], [100.0, 105.25]),
                                   ("one-poll", [None, 0, 0], [100.0, 101.0, 105.25])):
            with self.subTest(name=name):
                attempt = self.root / name
                attempt.mkdir()
                child = Mock(pid=987654321, returncode=0)
                child.poll.side_effect = polls
                def spawn(*_, **kwargs):
                    kwargs["stdout"].write(b"native-el0: required initialization ready mode=stubs;\n"
                                           b"native-el0: enters 3 svc 2\n")
                    (attempt / "serial.txt").write_text("ASOFT: out 10240\nASOFT: done 0\n")
                    return child
                with contextlib.ExitStack() as stack:
                    stack.enter_context(patch.object(prep.subprocess, "Popen", side_effect=spawn))
                    stack.enter_context(patch.object(prep, "process_identity", return_value=None))
                    stack.enter_context(patch.object(prep, "require_memory"))
                    stack.enter_context(patch.object(prep, "mem_available_mib", return_value=3174))
                    stack.enter_context(patch.object(prep, "recheck"))
                    stack.enter_context(patch.object(prep, "process_bounds", return_value={"within_bounds": True}))
                    stack.enter_context(patch.object(prep.cold, "shutdown", return_value=cleanup))
                    stack.enter_context(patch.object(prep.time, "monotonic", side_effect=clock))
                    stack.enter_context(patch.object(prep.time, "sleep"))
                    stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                    result = prep.supervise_vm(plan, "helper-smoke", attempt, ["authored-never-executed"], {}, self.args)
                self.assertEqual(result["status"], "VM_OBSERVATION_COMPLETE")
                self.assertEqual(result["elapsed_seconds"], 5.25)
                self.assertEqual(json.loads((attempt / "vm-result.json").read_text())["elapsed_seconds"], 5.25)


if __name__ == "__main__":
    unittest.main()
