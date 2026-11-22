#!/usr/bin/env python3
"""Host-only extraction boundary tests; no Android process or Apple input."""
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from extract_prep_tools import (RELEASE_SHA, copy_verified, extract, release_record,
                                validate_plan)
from prep_tools_common import (APK, ENTRYPOINTS, PAYLOAD_NAMES, elf_info, load_json,
                               record_valid, regular_under, relpath)


class ExtractionBoundaries(unittest.TestCase):
    def setUp(self):
        self.release = release_record()
        self.plan = {
            "schema": 1, "kind": "standalone_ios26_preparation_plan", "apk": APK,
            "release_manifest_sha256": RELEASE_SHA, "entrypoints": ENTRYPOINTS,
            "requires_qualified_qemu": True, "provenance": {},
            "files": copy.deepcopy(self.release["files"]),
        }
        for name in PAYLOAD_NAMES:
            self.plan["files"][name] = {
                "bytes": 0, "sha256": hashlib.sha256(b"").hexdigest(),
                "mode": 0o755 if name == "lib/libunpack.so" else 0o444 if name == "java/classes.dex" else 0o644,
                "origin": {"kind": "payload", "path": "payload/" + name},
            }

    def test_exact_whitelist(self):
        validate_plan(self.plan, self.release)
        self.assertEqual(len(self.release["files"]), 99)
        self.assertEqual(len(self.plan["files"]), 121)
        self.assertNotIn("lib/libqemu.so", self.plan["files"])
        self.assertEqual(self.plan["files"]["lib/libunpack.so"]["origin"]["kind"], "payload")

    def test_reject_unapproved_or_missing_files(self):
        for name in ("lib/libqemu.so", "lib/libqemu26.so", "Apple.img", "setup/scripts/ios16/boot.sh"):
            plan = copy.deepcopy(self.plan)
            plan["files"][name] = copy.deepcopy(plan["files"]["java/classes.dex"])
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_plan(plan, self.release)
        del self.plan["files"]["lib/libcurl.so"]
        with self.assertRaises(ValueError):
            validate_plan(self.plan, self.release)

    def test_release_member_identity_is_immutable(self):
        for key, value in (("bytes", 5), ("sha256", "0" * 64), ("mode", 0o644),
                           ("origin", {"kind": "apk", "member": "lib/arm64-v8a/libqemu.so"})):
            plan = copy.deepcopy(self.plan)
            plan["files"]["tools/qemu-img"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_plan(plan, self.release)

    def test_payload_cannot_select_other_files_or_old_jni(self):
        for origin in ({"kind": "payload", "path": "../libunpack.so"},
                       {"kind": "payload", "path": "/tmp/libunpack.so"},
                       {"kind": "apk", "member": "lib/arm64-v8a/libunpack.so"}):
            plan = copy.deepcopy(self.plan)
            plan["files"]["lib/libunpack.so"]["origin"] = origin
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                validate_plan(plan, self.release)

    def test_dex_is_read_only_before_loading(self):
        for mode in (0o644, 0o755):
            plan = copy.deepcopy(self.plan)
            plan["files"]["java/classes.dex"]["mode"] = mode
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                validate_plan(plan, self.release)

    def test_paths_are_normalized_and_relative(self):
        for name in ("", "/a", "../a", "a/../b", "a//b", "a/./b", "a\\b", "a\x00b", "a\nb"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                relpath(name)
        self.assertEqual(relpath("setup/phone/jobs/shared-build.sh"), "setup/phone/jobs/shared-build.sh")

    def test_reject_bool_size_and_unsafe_modes(self):
        for update in ({"bytes": True}, {"bytes": -1}, {"sha256": "x" * 64},
                       {"mode": 0o4755}, {"mode": 0o777}, {"mode": True}):
            record = {"bytes": 0, "sha256": "0" * 64, "mode": 0o644, **update}
            with self.subTest(update=update), self.assertRaises(ValueError):
                record_valid(record)

    def test_duplicate_json_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text('{"files": {}, "files": {}}')
            with self.assertRaises(ValueError):
                load_json(path)

    def test_payload_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "real").mkdir()
            (root / "real/file").write_bytes(b"checked")
            (root / "link").symlink_to(root / "real", target_is_directory=True)
            with self.assertRaises(ValueError):
                regular_under(root, "link/file")
            (root / "leaf").symlink_to(root / "real/file")
            with self.assertRaises(ValueError):
                regular_under(root, "leaf")

    def test_copy_verifies_length_hash_and_stays_nonexecutable(self):
        record = {"bytes": 4, "sha256": hashlib.sha256(b"good").hexdigest(), "mode": 0o755}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copy_verified(io.BytesIO(b"good"), root / "good", record)
            self.assertEqual((root / "good").stat().st_mode & 0o777, 0o600)
            for index, data in enumerate((b"bad!", b"goo", b"good extra")):
                with self.subTest(data=data), self.assertRaises(ValueError):
                    copy_verified(io.BytesIO(data), root / str(index), record)

    def test_existing_output_is_preserved_before_reading_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            out = root / "out"
            out.mkdir()
            (out / "sentinel").write_bytes(b"preserve")
            with self.assertRaises(ValueError):
                extract(root / "missing.apk", root / "missing.json", "0" * 64, out)
            self.assertEqual((out / "sentinel").read_bytes(), b"preserve")
            self.assertEqual(sorted(path.name for path in root.iterdir()), ["out"])

    def test_wrong_plan_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "plan.json"
            path.write_text(json.dumps(self.plan))
            with self.assertRaises(ValueError):
                extract(root / "missing.apk", path, "0" * 64, root / "out")
            self.assertFalse((root / "out").exists())
            self.assertEqual(sorted(p.name for p in root.iterdir()), ["plan.json"])

    def test_non_elf_cannot_be_a_dependency(self):
        for content in (b"", b"not an elf" * 10, b"\x7fELF\x01\x01\x01" + bytes(200)):
            with self.subTest(content=content[:8]), self.assertRaises(ValueError):
                elf_info(content)


if __name__ == "__main__":
    unittest.main()
