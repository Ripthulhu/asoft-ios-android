"""Local-only wrapper generation with synthetic pins and fresh temporary output."""
import ast
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import finalize_runtime as target
from test_transport import decode_command


class RuntimeFinalizer(unittest.TestCase):
    def fixture(self, directory, accepted=True):
        path = directory / 'synthetic-observation.json'
        path.write_text(json.dumps({'status': 'ACTUAL_RESUME5_PREFLIGHT_ACCEPTED', 'accepted': accepted,
            'observed_utc': 'synthetic-offline-fixture', 'stdout': {'bytes': 1234, 'sha256': 'a' * 64}}) + '\n')
        return path

    def test_missing_or_rejected_observation_creates_no_output(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            output = base / 'runtime'
            for body in ({}, {'status': 'ACTUAL_RESUME5_PREFLIGHT_ACCEPTED', 'accepted': False,
                             'observed_utc': 'synthetic', 'stdout': {'bytes': 1234, 'sha256': 'a' * 64}}):
                binding = base / 'binding.json'
                binding.write_text(json.dumps(body))
                with patch.object(target, 'OUT', output), self.assertRaises(ValueError):
                    target.build(binding)
                self.assertFalse(output.exists())

    def test_generation_only_binds_two_constants_and_exact_bounded_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            output = base / 'runtime'
            binding = self.fixture(base)
            before = {p: p.read_bytes() for p in (target.HERE / 'observe_ready.py', target.HERE / 'build_transport.py',
                      target.HERE / 'observe_processes.py', target.HERE / 'launch_observer.py')}
            with patch.object(target, 'OUT', output), contextlib.redirect_stdout(io.StringIO()):
                target.build(binding)
            self.assertEqual(before, {p: p.read_bytes() for p in before})
            tree = ast.parse((output / 'observe_ready.py').read_text())
            pins = {t.id: ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                    for t in node.targets if isinstance(t, ast.Name) and t.id in ('PREFLIGHT_SHA256', 'PREFLIGHT_BYTES')}
            self.assertEqual(pins, {'PREFLIGHT_SHA256': 'a' * 64, 'PREFLIGHT_BYTES': 1234})
            for command in output.glob('*.command.txt'):
                self.assertLessEqual(command.stat().st_size, 6000)
                self.assertEqual(decode_command(command), command.with_name(command.name.replace('.command.txt', '.py')).read_bytes())

    def test_existing_runtime_checkpoint_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            output = base / 'runtime'
            output.mkdir()
            marker = output / 'retained'
            marker.write_bytes(b'preserve')
            with patch.object(target, 'OUT', output), self.assertRaises(FileExistsError):
                target.build(self.fixture(base))
            self.assertEqual(list(output.iterdir()), [marker])
            self.assertEqual(marker.read_bytes(), b'preserve')


if __name__ == '__main__':
    unittest.main(verbosity=2)
