"""Exercise generated source-only transport in a fresh local directory, never run installed code."""
from pathlib import Path
import contextlib
import hashlib
import io
import json
import os
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parent
PHONE_BASE = '/data/local/tmp/pixel-gpu-transfer-sxtv33sh'
PHONE_INSPECTOR = '/data/local/tmp/pixel-saved-checks-resume3'


class SourceTransferTests(unittest.TestCase):
    def exercise(self, step_name, manifest_name, inspector):
        steps = json.loads((ROOT / step_name).read_text())
        manifest = json.loads((ROOT / manifest_name).read_text())
        with tempfile.TemporaryDirectory(prefix='resume3-transfer-', dir='/workspace/scratch/cabc3496f6f0') as directory:
            base = Path(directory).resolve() / 'base'
            base.mkdir()
            target = Path(directory).resolve() / 'inspector' if inspector else base
            sources = []
            for row in steps:
                body = (ROOT / (row['name'] + '.py')).read_bytes()
                self.assertEqual(hashlib.sha256(body).hexdigest(), row['source_sha256'])
                # Test-only paths and effective-owner UID adapt the root-phone script to this non-root scratch process.
                source = body.decode().replace(PHONE_BASE, str(base)).replace(PHONE_INSPECTOR, str(Path(directory).resolve() / 'inspector'))
                source = source.replace('os.geteuid()!=0', 'os.geteuid()!=' + str(os.geteuid())).replace('a.st_uid!=0', 'a.st_uid!=' + str(os.geteuid()))
                sources.append(source)
                with contextlib.redirect_stdout(io.StringIO()):
                    exec(compile(source, row['name'], 'exec'), {'__name__': '__main__'})
            for row in manifest['files']:
                body = (target / row['path']).read_bytes()
                self.assertEqual(len(body), row['bytes'])
                self.assertEqual(hashlib.sha256(body).hexdigest(), row['sha256'])
            before = {p: p.read_bytes() for p in target.iterdir() if p.is_file()}
            with self.assertRaises((ValueError, FileExistsError)), contextlib.redirect_stdout(io.StringIO()):
                exec(compile(sources[0], 'repeated-begin', 'exec'), {'__name__': '__main__'})
            self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_fresh_inspector_directory_and_existing_target_refusal(self):
        self.exercise('inspector-transport-steps.json', 'inspector-transfer-manifest.json', True)

    def test_outer_source_pair_and_existing_target_refusal(self):
        self.exercise('transport-steps.json', 'transfer-manifest.json', False)

    def test_unreleased_owner_refuses_missing_source_pins(self):
        value = types.ModuleType('unreleased_owner')
        source = ROOT / 'run_saved_inspection_owner_UNRELEASED.py'
        value.__file__ = str(source)
        exec(compile(source.read_bytes(), str(source), 'exec'), value.__dict__)
        with self.assertRaisesRegex(ValueError, 'independently reviewed revised inspector pins required'):
            value.require_finalized()


if __name__ == '__main__':
    unittest.main(verbosity=2)
