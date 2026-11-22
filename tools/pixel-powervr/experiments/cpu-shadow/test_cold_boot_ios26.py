#!/usr/bin/env python3
"""Authored-file and process-control tests; never execute QEMU or access a GPU."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

spec = importlib.util.spec_from_file_location("cold_boot", Path(__file__).with_name("cold_boot_ios26.py"))
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)


def node(name, values=None, children=()):
    values = {"name": name.encode() + b"\0", **(values or {})}
    output = struct.pack("<II", len(values), len(children))
    for key, value in values.items():
        output += key.encode().ljust(32, b"\0") + struct.pack("<I", len(value))
        output += value + b"\0" * (-len(value) % 4)
    return output + b"".join(children)


def authored_tree(scale=3):
    base, size = 0x100000000, 4 << 30
    return node("device-tree", children=[
        node("chosen", {"dram-size": struct.pack("<Q", size), "display-scale": struct.pack("<I", scale)}),
        node("memory", {"reg": struct.pack("<QQ", base, size)}),
        node("product", children=[node("util", {"reg": struct.pack("<QQ", base + size, 4096)})]),
        node("cpus", children=[node("cpu" + str(i), {"timebase-frequency": struct.pack("<Q", 19_200_000)})
                                for i in range(4)]),
    ])


def qcow(path, backing=None):
    header = bytearray(104)
    header[:4] = b"QFI\xfb"
    name = str(backing).encode() if backing is not None else b""
    struct.pack_into(">IQI", header, 4, 3, 104 if name else 0, len(name))
    struct.pack_into(">Q", header, 24, 32 << 30)
    path.write_bytes(header + name)


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="cold-boot-test-")
        self.root = Path(self.temporary.name)
        self.assets, self.package, self.results = (self.root / name for name in ("assets", "package", "qualification"))
        for directory in (self.assets, self.package, self.results, self.package / "lib"):
            directory.mkdir()
        for name in ("bootkc", "sptm", "txm", "rd-shell.hfs", "root26m.tc"):
            (self.assets / name).write_bytes(b"authored test input, not Apple data\n")
        (self.assets / boot.TREE).write_bytes(authored_tree())
        qcow(self.assets / "root26r.qcow2")
        self.image_tool = self.root / "qemu-img-not-executed"
        self.image_tool.write_text("this is not an executable guest tool\n")
        self.image_tool.chmod(0o755)
        qemu = self.package / "qemu-system-aarch64"
        qemu.write_bytes(b"authored placeholder, never executed\n")
        qemu.chmod(0o755)
        (self.package / "lib/libexample.so").write_bytes(b"not a real library\n")
        checksums = {p.relative_to(self.package).as_posix(): boot.sha(p)
                     for p in self.package.rglob("*") if p.is_file()}
        (self.package / "SHA256SUMS").write_text("".join(digest + "  " + name + "\n"
                                                        for name, digest in checksums.items()))
        cases = []
        for name in sorted(boot.CASES):
            folder = self.results / name
            folder.mkdir()
            log = folder / "output.log"
            log.write_text("authored harness-test placeholder\n")
            cases.append({"case": name, "passed": True, "log_sha256": boot.sha(log)})
        next(case for case in cases if case["case"] == "probe")["probe"] = {
            "checks_passed": 127, "backend": "system_cpu_shadow"}
        self.qualification = self.results / "qualification.json"
        self.qualification.write_text(json.dumps({
            "all_cases_passed": True, "package_rechecked": True, "package_sha256": checksums,
            "cases": cases, "device": {"ro.build.fingerprint": "authored-test-only"}}))
        self.options = ["--assets", str(self.assets), "--package", str(self.package),
                        "--qualification", str(self.qualification), "--qemu-img", str(self.image_tool),
                        "--run-dir", str(self.root / "run"), "--min-free-mib", "1"]

    def tearDown(self):
        self.temporary.cleanup()

    def preflight(self, extra=()):
        return boot.preflight(boot.parser().parse_args([*self.options, *extra]))

    def test_no_arguments_is_incomplete_and_no_process(self):
        with patch.object(boot.subprocess, "Popen") as popen, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(boot.main([]), 2)
        popen.assert_not_called()
        report = json.loads(output.getvalue())
        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertFalse(report["guest_started"])

    def test_missing_assets_with_boot_never_starts_or_creates_run(self):
        (self.assets / "bootkc").unlink()
        with patch.object(boot.subprocess, "Popen") as popen, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(boot.main([*self.options, "--boot"]), 2)
        popen.assert_not_called()
        self.assertIn("bootkc", json.loads(output.getvalue())["blockers"][0])
        self.assertFalse((self.root / "run").exists())

    def test_complete_preflight_is_read_only_and_launch_uses_overlay(self):
        before = {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with patch.object(boot.subprocess, "Popen") as popen:
            report = self.preflight()
        popen.assert_not_called()
        self.assertEqual(report["status"], "PREFLIGHT_READY", report)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        self.assertFalse((self.root / "run").exists())
        argv, env = boot.command(report["plan"], 17)
        drive = argv[argv.index("-drive") + 1]
        self.assertIn("/run/coldboot-overlay.qcow2", drive)
        self.assertNotIn(str(self.assets), drive)
        self.assertNotIn("-loadvm", argv)
        self.assertIn(boot.CPU, argv)
        self.assertEqual(env["ASOFT_NATIVE_EL0_TPIDRRO"], "1")
        self.assertEqual(env["ASOFT_NATIVE_EL0_REQUIRED"], "1")
        self.assertEqual(env["ASOFT_FRAME_FD"], "17")
        for excluded in ("ASOFT_NATIVE_EL0_TPIDRRO_TRAP", "ASOFT_GUEST_RAM_FD", "ASOFT_NATIVE_EL0_OFF_FILE",
                         "VK_DRIVER_FILES", "VK_ICD_FILENAMES", "LD_PRELOAD"):
            self.assertNotIn(excluded, env)

    def test_refuses_older_suite_without_swap(self):
        report = json.loads(self.qualification.read_text())
        report["cases"] = [case for case in report["cases"] if case["case"] != "native-swap"]
        self.qualification.write_text(json.dumps(report))
        self.assertIn("native-swap", self.preflight()["blockers"][0])

    def test_old_fifteen_cases_or_either_missing_core_case_are_refused(self):
        original = json.loads(self.qualification.read_text())
        self.assertEqual(len(original["cases"]), 17)
        for omitted in ({"core", "core-no-argument-buffers"}, {"core"}, {"core-no-argument-buffers"}):
            with self.subTest(omitted=omitted):
                report = dict(original)
                report["cases"] = [case for case in original["cases"] if case["case"] not in omitted]
                self.qualification.write_text(json.dumps(report))
                with patch.object(boot.subprocess, "Popen") as popen:
                    result = self.preflight()
                popen.assert_not_called()
                self.assertEqual(result["status"], "INCOMPLETE")
                for name in omitted:
                    self.assertIn(name, result["blockers"][0])
                self.assertFalse((self.root / "run").exists())

    def test_seventeen_case_success_requires_matching_core_logs(self):
        self.assertEqual(self.preflight()["status"], "PREFLIGHT_READY")
        for name in ("core", "core-no-argument-buffers"):
            with self.subTest(case=name):
                log = self.results / name / "output.log"
                original = log.read_bytes()
                log.write_bytes(b"unmatched authored core evidence\n")
                try:
                    result = self.preflight()
                    self.assertEqual(result["status"], "INCOMPLETE")
                    self.assertIn("log mismatch: " + name, result["blockers"][0])
                finally:
                    log.write_bytes(original)

    def test_refuses_changed_package_or_case_log(self):
        (self.results / "native-swap/output.log").write_text("changed\n")
        self.assertIn("log mismatch", self.preflight()["blockers"][0])
        (self.package / "qemu-system-aarch64").write_bytes(b"changed")
        self.assertIn("checksum mismatch", self.preflight()["blockers"][0])

    def test_malformed_qualification_is_explicit_incomplete(self):
        self.qualification.write_text('{"cases":{"probe":true}}')
        report = self.preflight()
        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertIn("cases must be objects", report["blockers"][0])

    def test_null_nested_probe_and_device_are_explicit_incomplete(self):
        original = json.loads(self.qualification.read_text())
        for value in (None, []):
            report = json.loads(json.dumps(original))
            next(case for case in report["cases"] if case["case"] == "probe")["probe"] = value
            self.qualification.write_text(json.dumps(report))
            self.assertEqual(self.preflight()["status"], "INCOMPLETE")
            report = json.loads(json.dumps(original))
            report["device"] = value
            self.qualification.write_text(json.dumps(report))
            self.assertEqual(self.preflight()["status"], "INCOMPLETE")

    def test_refuses_existing_output_and_mismatched_screen(self):
        (self.root / "run").mkdir()
        self.assertIn("must be new", self.preflight()["blockers"][0])
        (self.root / "run").rmdir()
        self.assertIn("display scale differs", self.preflight(["--scale", "2"])["blockers"][0])

    def test_backing_overlay_and_existing_tree_tool_preserve_sources(self):
        report = self.preflight()
        self.assertEqual(report["status"], "PREFLIGHT_READY", report)
        plan = report["plan"]
        originals = {str(p): p.read_bytes() for p in self.assets.iterdir()}
        (self.root / "run").mkdir()
        actual_run_tool, observed = boot.run_tool, []
        def tools(argv, env, timeout=30):
            observed.append(argv)
            if argv[0] == str(self.image_tool):
                if argv[1] == "info":
                    return json.dumps([{"filename": plan["source_disk"], "format": "qcow2"}])
                self.assertEqual(argv[1:7], ["create", "-f", "qcow2", "-F", "qcow2", "-b"])
                qcow(Path(argv[-1]), argv[-2])
                return "created authored overlay\n"
            return actual_run_tool(argv, env, timeout)
        with patch.object(boot, "run_tool", side_effect=tools):
            boot.prepare_run(plan)
        self.assertEqual(originals, {str(p): p.read_bytes() for p in self.assets.iterdir()})
        result = (self.root / "run/device-tree").read_bytes()
        self.assertEqual(result, boot.expected_tree(authored_tree(), 3, 3))
        properties = boot.tree_properties(result)
        for path, props in properties.items():
            if "/cpus/" in path:
                self.assertEqual(struct.unpack_from("<Q", result, props["timebase-frequency"][0])[0], 38_400_000)
        self.assertIn("--timebase", observed[-1])
        self.assertEqual(boot.qcow_chain(self.root / "run/coldboot-overlay.qcow2")[1]["path"],
                         str(self.assets / "root26r.qcow2"))

    def test_qcow_cycle_is_rejected(self):
        source = self.assets / "root26r.qcow2"
        qcow(source, source)
        self.assertIn("cyclic", self.preflight()["blockers"][0])

    def test_package_change_during_preparation_prevents_launch(self):
        report = self.preflight()
        self.assertEqual(report["status"], "PREFLIGHT_READY", report)
        args = boot.parser().parse_args(self.options)
        def changed_prepare(plan):
            (self.package / "qemu-system-aarch64").write_bytes(b"changed after preflight")
        with patch.object(boot, "require_phone"), patch.object(boot, "subreaper"), \
                patch.object(boot, "prepare_run", side_effect=changed_prepare), \
                patch.object(boot.subprocess, "Popen") as popen:
            result = boot.boot(report, args)
        popen.assert_not_called()
        self.assertFalse(result["guest_started"])
        self.assertFalse(result["package_rechecked_after_run"])
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertIn("checksum mismatch", result["error"])

    def test_qemu_debug_log_is_counted_and_reads_are_bounded(self):
        run = self.root / "run"
        run.mkdir()
        (run / "qemu.log").write_bytes(b"debug" * 100)
        (run / "serial.txt").write_bytes(b"serial")
        (run / "coldboot-overlay.qcow2").write_bytes(b"not a log")
        self.assertEqual(boot.storage_report(run, boot.parser().parse_args(self.options))["log_bytes"], 506)
        self.assertEqual(boot.read_log(run / "qemu.log", 10), "debugdebug")

    def test_late_log_overflow_or_lost_marker_prevents_observed_status(self):
        run = self.root / "run"
        run.mkdir()
        args = boot.parser().parse_args([*self.options, "--max-log-mib", "1"])
        (run / "qemu-stderr.txt").write_text("startup\n")
        (run / "serial.txt").write_text("ready\n")
        result = {"stop_reason": "requested_witnesses_observed", "changed_originals": [],
                  "package_rechecked_after_run": True, "owner_cleanup_errors": [],
                  "witnesses": {"serial_markers_found": ["ready"], "fatal_markers": [],
                                "native_initialization": True, "native_execution": True,
                                "gpu_execution": True, "frame_captured": True},
                  "cleanup": {"stop_flushed": True, "echild": True, "exit_code": 0,
                              "forced_qemu": False, "forced_descendants": [], "errors": []},
                  "final_storage": boot.storage_report(run, args)}
        self.assertEqual(boot.witness_status(result, ["ready"]), "WITNESSES_OBSERVED")
        result["witnesses"]["serial_markers_found"] = []
        self.assertEqual(boot.witness_status(result, ["ready"]), "INCOMPLETE")
        result["witnesses"]["serial_markers_found"] = ["ready"]
        with (run / "qemu-stderr.txt").open("ab") as output:
            output.write(b"x" * (1 << 20) + b"panic(cpu 0)\n")
        self.assertNotIn("panic(cpu", boot.read_log(run / "qemu-stderr.txt", 1 << 20))
        result["final_storage"] = boot.storage_report(run, args)
        self.assertEqual(result["final_storage"]["evidence_truncated"], ["qemu-stderr.txt"])
        self.assertEqual(boot.witness_status(result, ["ready"]), "INCOMPLETE")

    def test_initialization_and_unrelated_text_are_not_positive_witnesses(self):
        text = "native-el0: required initialization ready mode=stubs; guest execution not yet observed\n"
        result = boot.evidence(text, "boot log", [], [])
        self.assertTrue(result["native_initialization"])
        self.assertFalse(result["native_execution"])
        self.assertFalse(result["gpu_execution"])
        text += "el-sample t=30s all: el0-nat 1.0% | native 44 ms handler 2 ms entry 1 ms enters 100 fills 12\n"
        text += "vresearch-pvg-reims: frame 1 shown (presents: guest 1, host 1)\n"
        text += "vresearch-pvg-reims: cpu-shadow chunks=1 views=1 prepared=2 finished=2 uploaded=16384 scattered=0\n"
        result = boot.evidence(text, "authored marker", [{"stable": True, "nonuniform": True}], ["authored marker"])
        self.assertTrue(result["native_execution"])
        self.assertTrue(result["gpu_execution"])
        self.assertTrue(result["frame_captured"])
        self.assertEqual(result["serial_markers_found"], ["authored marker"])
        self.assertIn("panic(", boot.evidence(text, "panic(test)", [], [])["fatal_markers"])

    def test_frame_capture_retains_authored_pixels(self):
        import mmap
        memory = mmap.mmap(-1, 8)
        try:
            memory[:] = bytes([0, 0, 255, 255, 0, 255, 0, 255])
            record = boot.frame_capture(memory, 2, 1, self.root / "frame.png")
            self.assertTrue(record["stable"])
            self.assertTrue(record["nonuniform"])
            self.assertTrue((self.root / "frame.png").read_bytes().startswith(b"\x89PNG"))
        finally:
            memory.close()

    def test_alpha_only_variation_does_not_count_as_nonuniform_frame(self):
        import mmap
        memory = mmap.mmap(-1, 8)
        try:
            memory[:] = bytes([0, 0, 0, 0, 0, 0, 0, 255])
            record = boot.frame_capture(memory, 2, 1, self.root / "frame.png")
            self.assertTrue(record["stable"])
            self.assertFalse(record["nonuniform"])
            self.assertFalse((self.root / "frame.png").exists())
        finally:
            memory.close()


class ProcessTests(unittest.TestCase):
    @staticmethod
    def child(ignore=False):
        action = "signal.SIG_IGN" if ignore else "lambda *_: sys.exit(0)"
        script = "import signal,sys,time; signal.signal(signal.SIGTERM," + action + "); print('ready',flush=True); time.sleep(60)"
        child = subprocess.Popen([sys.executable, "-c", script], stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, start_new_session=True)
        if child.stdout.readline() != b"ready\n":
            raise AssertionError("authored child did not start")
        child.stdout.close()
        return child

    def test_orderly_stop_then_quit_then_reap(self):
        child = self.child()
        commands = []
        class FakeQmp:
            def call(self, name, seconds):
                commands.append(name)
                if name == "quit":
                    child.send_signal(signal.SIGTERM)
                return {}
            def close(self):
                commands.append("close")
        try:
            record = boot.shutdown(child, FakeQmp(), lambda: commands.append("capture"), exit_seconds=1)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()
        self.assertEqual(commands, ["stop", "capture", "quit", "close"])
        self.assertTrue(record["stop_flushed"])
        self.assertTrue(record["echild"])
        self.assertFalse(record["forced_qemu"])
        self.assertEqual(record["exit_code"], 0)

    def test_failed_stop_and_capture_still_quit_then_kill_owned_group(self):
        child = self.child(ignore=True)
        commands = []
        class FakeQmp:
            def call(self, name, seconds):
                commands.append(name)
                if name == "stop":
                    raise TimeoutError("authored timeout")
                return {}
            def close(self):
                commands.append("close")
        def failed_capture():
            raise OSError("authored disk-full condition")
        try:
            record = boot.shutdown(child, FakeQmp(), failed_capture, exit_seconds=0.02)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()
        self.assertEqual(commands, ["stop", "quit", "close"])
        self.assertFalse(record["stop_flushed"])
        self.assertTrue(record["forced_qemu"])
        self.assertTrue(record["echild"])
        self.assertEqual(record["exit_code"], -signal.SIGKILL)
        self.assertEqual(len(record["errors"]), 2)

    def test_encoding_or_memory_error_still_quits_and_reaps(self):
        for failure in (zlib.error("authored compression failure"), MemoryError("authored allocation failure")):
            with self.subTest(failure=type(failure).__name__):
                child, commands = self.child(), []
                class FakeQmp:
                    def call(self, name, seconds):
                        commands.append(name)
                        if name == "quit":
                            child.send_signal(signal.SIGTERM)
                        return {}
                    def close(self):
                        commands.append("close")
                def failed_capture():
                    raise failure
                try:
                    record = boot.shutdown(child, FakeQmp(), failed_capture, exit_seconds=1)
                finally:
                    if child.poll() is None:
                        child.kill()
                        child.wait()
                self.assertEqual(commands, ["stop", "quit", "close"])
                self.assertEqual(record["exit_code"], 0)
                self.assertTrue(record["echild"])
                self.assertFalse(record["forced_qemu"])
                self.assertIn("frame capture:", record["errors"][0])

    def test_qmp_protocol_handles_events_and_matching_response_ids(self):
        # This executor disallows even AF_UNIX sockets. Exercise framing/events
        # with a byte-stream transport; actual QMP transport remains a phone gate.
        class AuthoredSocket:
            def __init__(self):
                self.buffer = b'{"QMP":{"version":{}}}\r\n'
                self.requests, self.closed = [], False
            def settimeout(self, seconds):
                pass
            def connect(self, path):
                self.path = path
            def sendall(self, data):
                request = json.loads(data)
                self.requests.append(request["execute"])
                self.buffer += b'{"event":"STOP"}\r\n'
                self.buffer += json.dumps({"return": {}, "id": request["id"]}).encode() + b"\r\n"
            def recv(self, size):
                # Deliberately split JSON and CRLF across multiple reads.
                result, self.buffer = self.buffer[:7], self.buffer[7:]
                return result
            def close(self):
                self.closed = True
        transport, transcript = AuthoredSocket(), []
        with patch.object(boot.socket, "socket", return_value=transport):
            client = boot.Qmp(Path("/authored/qmp.sock"), transcript)
            self.assertEqual(client.call("stop", 1), {})
            client.close()
        self.assertTrue(transport.closed)
        self.assertEqual(transport.requests, ["qmp_capabilities", "stop"])
        self.assertEqual(len(transcript), 2)


if __name__ == "__main__":
    unittest.main()
