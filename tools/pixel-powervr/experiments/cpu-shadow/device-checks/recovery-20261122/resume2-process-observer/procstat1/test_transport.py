#!/usr/bin/env python3
"""Exact command/bundle reconstruction and temporary-directory install replay."""
import ast
import base64
import contextlib
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
PHONE = '/data/local/tmp/pixel-gpu-transfer-sxtv33sh'


def sha(body):
    return hashlib.sha256(body).hexdigest()


def decode_command(path):
    body = path.read_bytes()
    parts = shlex.split(body.decode())
    if parts[:4] != ['/data/data/com.termux/files/usr/bin/python', '-I', '-B', '-c']:
        raise ValueError('unexpected command wrapper')
    tree = ast.parse(parts[4])
    encoded = [node.args[0].value for node in ast.walk(tree) if isinstance(node, ast.Call) and
               isinstance(node.func, ast.Attribute) and node.func.attr == 'b64decode']
    if len(encoded) != 1:
        raise ValueError('unexpected compressed command')
    return gzip.decompress(base64.b64decode(encoded[0], validate=True))


class Transport(unittest.TestCase):
    def test_all_shell_commands_are_bounded_exact_reviewed_source(self):
        commands = list((HERE / 'source-transfer').glob('*.command.txt')) + list(HERE.glob('*.command.txt'))
        self.assertGreaterEqual(len(commands), 9)
        for path in commands:
            with self.subTest(path=path.name):
                self.assertLessEqual(len(path.read_bytes()), 6000)
                self.assertEqual(decode_command(path), path.with_name(path.name.replace('.command.txt', '.py')).read_bytes())

    def test_chunks_reconstruct_exact_two_sources(self):
        manifest = json.loads((HERE / 'transfer-manifest.json').read_text())
        chunks = []
        for n, record in enumerate(manifest['chunks']):
            tree = ast.parse((HERE / 'source-transfer' / f'{n + 1:02d}-chunk-{n:02d}.py').read_bytes())
            body = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign) and
                        any(isinstance(t, ast.Name) and t.id == 'body' for t in node.targets))
            self.assertEqual((len(body), sha(body)), (record['bytes'], record['sha256']))
            chunks.append(body)
        encoded = b''.join(chunks)
        self.assertEqual((len(encoded), sha(encoded)), (manifest['encoded_bytes'], manifest['encoded_sha256']))
        body = gzip.decompress(base64.b64decode(encoded, validate=True))
        self.assertEqual((len(body), sha(body)), (manifest['bundle_bytes'], manifest['bundle_sha256']))
        bundle = json.loads(body)
        self.assertEqual([record['path'] for record in bundle['files']], [r['path'] for r in manifest['files']])
        for row, local in zip(bundle['files'], ('observe_processes.py', 'launch_observer.py')):
            self.assertEqual(row['body'].encode(), (HERE / local).read_bytes())

    def test_install_only_replay_in_fresh_temporary_directory(self):
        scripts = sorted((HERE / 'source-transfer').glob('*.py'))
        manifest = json.loads((HERE / 'transfer-manifest.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            owner = (HERE.parents[1] / 'resume2-saved-inspection/run_saved_inspection_owner.py').read_bytes()
            self.assertEqual((len(owner), sha(owner)), (35799, manifest['inspection_owner_source']['sha256']))
            (base / 'run-ios26-saved-inspection-resume2.py').write_bytes(owner)
            def local_source(path):
                # Only the host location/uid gates are substituted for this replay.
                # Payloads and all hashes remain the exact retained phone bytes.
                return path.read_text().replace("BASE=Path('" + PHONE + "')", 'BASE=Path(' + repr(str(base)) + ')').replace(
                    'os.geteuid()!=0', 'os.geteuid()!=' + str(os.geteuid())).replace('a.st_uid!=0', 'a.st_uid!=' + str(os.geteuid()))
            with contextlib.redirect_stdout(io.StringIO()):
                for path in scripts:
                    exec(compile(local_source(path), str(path), 'exec'), {'__name__': 'offline_transport_replay'})
            install = json.loads((base / 'resume2-process-observer-procstat1-install.json').read_text())
            self.assertFalse(install['execution_started'])
            self.assertFalse(install['inspection_started'])
            self.assertEqual(install['files'], manifest['files'])
            for row in manifest['files']:
                body = (base / row['path']).read_bytes()
                self.assertEqual((len(body), sha(body)), (row['bytes'], row['sha256']))
            self.assertFalse((base / 'ios26-saved-inspection-resume2-observer-procstat1').exists())
            self.assertFalse((base / 'ios26-saved-inspection-resume2-observer-procstat1-launch.json').exists())
            with self.assertRaises(ValueError):
                exec(compile(local_source(scripts[-1]), str(scripts[-1]), 'exec'), {'__name__': 'offline_repeat_refusal'})
            for row in manifest['files']:
                self.assertEqual(sha((base / row['path']).read_bytes()), row['sha256'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
