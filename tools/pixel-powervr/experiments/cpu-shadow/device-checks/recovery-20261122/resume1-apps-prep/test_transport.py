"""Decode every bounded source-only command without executing a phone command."""
import ast
import base64
import gzip
import hashlib
import json
from pathlib import Path
import shlex
import unittest

HERE = Path(__file__).resolve().parent
PACKAGE = HERE / 'package'
TRANSFER = PACKAGE / 'app-auditor-transfer'


def sha(body):
    return hashlib.sha256(body).hexdigest()


class SourceTransportTests(unittest.TestCase):
    def test_all_nine_commands_decode_to_exact_preserved_source(self):
        steps = json.loads((PACKAGE / 'app-auditor-transport-steps.json').read_bytes())
        self.assertEqual(len(steps), 9)
        for row in steps:
            with self.subTest(name=row['name']):
                command = (TRANSFER / (row['name'] + '.command.txt')).read_bytes()
                source = (TRANSFER / (row['name'] + '.py')).read_bytes()
                self.assertEqual((len(command), sha(command)), (row['command_bytes'], row['command_sha256']))
                self.assertLessEqual(len(command), 6000)
                words = shlex.split(command.decode())
                self.assertEqual(words[:4], ['/data/data/com.termux/files/usr/bin/python', '-I', '-B', '-c'])
                self.assertEqual(len(words), 5)
                loader = ast.parse(words[4])
                encoded = ast.literal_eval(loader.body[1].value.args[0].args[0])
                decoded = gzip.decompress(base64.b64decode(encoded, validate=True))
                self.assertEqual(decoded, source)
                self.assertEqual((len(source), sha(source)), (row['source_bytes'], row['source_sha256']))

    def test_chunks_reconstruct_only_exact_reviewed_app_source_pair(self):
        manifest = json.loads((PACKAGE / 'app-auditor-transfer-manifest.json').read_bytes())
        parts = []
        for index, row in enumerate(manifest['chunks']):
            code = ast.parse((TRANSFER / f'{index + 1:02d}-chunk-{index:02d}.py').read_text())
            assignments = [node for node in code.body if isinstance(node, ast.Assign) and
                           len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'body']
            self.assertEqual(len(assignments), 1)
            body = ast.literal_eval(assignments[0].value)
            self.assertEqual((len(body), sha(body)), (row['bytes'], row['sha256']))
            parts.append(body)
        encoded = b''.join(parts)
        self.assertEqual((len(encoded), sha(encoded)), (manifest['encoded_bytes'], manifest['encoded_sha256']))
        bundle = gzip.decompress(base64.b64decode(encoded, validate=True))
        self.assertEqual((len(bundle), sha(bundle)), (manifest['bundle_bytes'], manifest['bundle_sha256']))
        value = json.loads(bundle)
        self.assertEqual(value['kind'], 'resume1_apps_auditor_sources')
        self.assertEqual([row['path'] for row in value['files']], ['audit_ios26_apps.py', 'audit_ios26_apps_guest.py'])
        self.assertEqual([{key: row[key] for key in ('path', 'bytes', 'sha256')} for row in value['files']], manifest['files'])
        for row in value['files']:
            source = (PACKAGE / 'app-auditor' / row['path']).read_bytes()
            self.assertEqual(row['body'].encode(), source)
            self.assertEqual((len(source), sha(source)), (row['bytes'], row['sha256']))

    def test_install_scripts_have_no_process_or_vm_launch(self):
        for path in TRANSFER.glob('*.py'):
            tree = ast.parse(path.read_text())
            imports = {name.name for node in ast.walk(tree) if isinstance(node, ast.Import) for name in node.names}
            self.assertFalse(imports & {'subprocess', 'runpy', 'ctypes', 'socket'})
            calls = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
            self.assertFalse(calls & {'system', 'popen', 'fork', 'execv', 'execve', 'spawnv', 'Popen', 'kill', 'killpg'})
            self.assertNotIn('run_apps_prep_owner', path.read_text())


if __name__ == '__main__':
    unittest.main()
