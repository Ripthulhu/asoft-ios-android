#!/usr/bin/env python3
"""Check the core builder's committed-source gate without compiling or executing C."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from build_core_fixture import BUILDERS, FIXTURE, source_snapshot


class SourceGate(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="pixel-core-source-gate-")
        self.source = Path(self.temporary.name)
        self.git("init", "--quiet")
        self.git("config", "core.hooksPath", os.devnull)
        self.inputs = {FIXTURE + ".c": b"/* Authored test data; never compiled. */\n",
                       FIXTURE + ".py": b"# Authored generator test data; never executed.\n"}
        self.inputs.update({BUILDERS + "/" + name: b"# Authored builder test data.\n"
                            for name in ("__init__.py", "abi.py", "resources_build.py", "scenario.py")})
        for name, data in self.inputs.items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.git("add", "--", *self.inputs)
        self.commit()

    def tearDown(self):
        self.temporary.cleanup()

    def git(self, *arguments):
        return subprocess.check_output(["git", "--no-optional-locks", "-C", str(self.source),
                                        *arguments], stderr=subprocess.PIPE)

    def commit(self):
        self.git("-c", "user.name=Fixture Test", "-c", "user.email=fixture@example.invalid",
                 "commit", "--quiet", "--no-gpg-sign", "-m", "Authored source gate test")

    def test_committed_inputs_have_exact_hashes(self):
        snapshot = source_snapshot(self.source)
        self.assertEqual(snapshot["commit"], self.git("rev-parse", "HEAD").decode().strip())
        self.assertEqual(set(snapshot["files"]), set(self.inputs))
        for name, data in self.inputs.items():
            self.assertEqual(snapshot["files"][name]["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual(snapshot["files"][name]["bytes"], len(data))

    def test_uncommitted_c_source_is_refused(self):
        (self.source / (FIXTURE + ".c")).write_bytes(b"changed source\n")
        with self.assertRaisesRegex(RuntimeError, "committed bytes"):
            source_snapshot(self.source)

    def test_staged_generator_is_refused(self):
        name = FIXTURE + ".py"
        (self.source / name).write_bytes(b"# changed generator\n")
        self.git("add", "--", name)
        with self.assertRaisesRegex(RuntimeError, "committed bytes"):
            source_snapshot(self.source)

    def test_untracked_builder_is_refused(self):
        (self.source / BUILDERS / "unexpected.py").write_bytes(b"# new import\n")
        with self.assertRaisesRegex(RuntimeError, "committed inventory"):
            source_snapshot(self.source)

    def test_missing_builder_is_refused(self):
        (self.source / BUILDERS / "abi.py").unlink()
        with self.assertRaisesRegex(RuntimeError, "committed inventory"):
            source_snapshot(self.source)

    def test_symlink_builder_is_refused(self):
        path = self.source / BUILDERS / "abi.py"
        path.unlink()
        path.symlink_to("scenario.py")
        with self.assertRaisesRegex(RuntimeError, "regular file"):
            source_snapshot(self.source)

    def test_head_change_invalidates_snapshot(self):
        before = source_snapshot(self.source)
        (self.source / "README").write_bytes(b"unrelated committed change\n")
        self.git("add", "--", "README")
        self.commit()
        self.assertNotEqual(source_snapshot(self.source), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
