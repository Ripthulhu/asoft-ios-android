"""Authored metadata fixtures only; no phone, VM, mount, tool or Apple bytes."""
import ast
import base64
import contextlib
import copy
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shlex
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
R5 = HERE.parent
CPU = R5.parents[2]
sys.path.insert(0, str(CPU))
import inspect_ios26_firstboot as canonical_host
import inspect_ios26_firstboot_guest as canonical_guest
import audit_ios26_partition_guest as partition
from test_inspect_ios26_firstboot import RawDisk
import test_inspect_ios26_firstboot as firstboot_fixtures
from test_audit_ios26_partition import CLEAN


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


status = load(HERE / 'observe_inspection.py', 'status_projection')
journals = load(HERE / 'observe_journals.py', 'journal_projection')
fsck = load(HERE / 'observe_fsck.py', 'fsck_projection')
sha = lambda value: hashlib.sha256(value).hexdigest()
json_bytes = lambda value: (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


class MetadataFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        current, baseline = firstboot_fixtures.RootInitializedFromAuthored.disks()
        cls.root_row = canonical_guest.inspect_volume(current, baseline,
            canonical_guest.ROOT_BASE, canonical_guest.ROOT_BYTES, 'iOSRoot')
        base, sectors, _ = partition.PARTITIONS[1]
        cls.data_row = canonical_guest.inspect_volume(RawDisk(True), RawDisk(), base * 512, sectors * 512, 'Data')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.owner, self.work = self.root / 'owner', self.root / 'work'
        self.owner.mkdir()
        self.files = self.work / 'a1/files/inspection'
        self.files.mkdir(parents=True)
        self.m = vars(load(R5 / 'run_saved_inspection_owner.py', 'fixture_owner_' + str(id(self))))
        self.m.update(OWNER=self.owner, WORK=self.work, INSPECTOR=CPU,
                      COMMAND=['fixture-python', '-I', '-B', str(CPU / 'inspect_ios26_firstboot.py')],
                      SOURCE_HASHES={CPU / 'inspect_ios26_firstboot.py': sha((CPU / 'inspect_ios26_firstboot.py').read_bytes())},
                      identity=lambda pid: None, refuse_live_children=mock.Mock())
        self.anchor = self.root / 'unchanged-input.json'
        self.anchor.write_bytes(b'authored input\n')
        self.current = {'inputs': {str(self.anchor): sha(self.anchor.read_bytes())}}
        self.expected = {'schema': 1, 'partition_guest_source': str(CPU / 'audit_ios26_partition_guest.py'),
                         'partition_guest_sha256': fsck.PARTITION_SHA256}
        self.policy = {'inspection_nonce': '1' * 32, 'inspection_session_sha256': self.m['digest'](self.expected),
                       'partition_guest_sha256': fsck.PARTITION_SHA256}
        self.guest = {'schema': 1, 'kind': 'ios26_saved_firstboot_inspection', 'status': 'SAVED_FIRSTBOOT_INSPECTION_PASSED',
            'errors': [], 'cleanup_errors': [], 'readonly_attachments': True, 'raw_metadata_unchanged': True,
            'mounted': False, 'replayed': False, 'repaired': False, 'inspection_nonce': self.policy['inspection_nonce'],
            'policy_sha256': self.m['digest'](self.policy),
            'gpt': {'status': 'PASSED', 'disk_bytes': canonical_host.DISK_BYTES},
            'baseline_gpt': {'status': 'PASSED', 'disk_bytes': canonical_host.DISK_BYTES},
            'journals': {'iOSRoot': copy.deepcopy(self.root_row), 'Data': copy.deepcopy(self.data_row)},
            'fsck': {name: partition.fsck_verdict(0, CLEAN) for name in ('iOSRoot', 'Data')}}
        self.native = {'native_initialization': True, 'native_execution': True, 'native_svc_final': True, 'fatal_markers': []}
        self.cleanup = {'exit_code': 0, 'echild': True, 'forced_qemu': False, 'forced_descendants': [], 'errors': []}
        self.start = {'schema': 1, 'command': self.m['COMMAND'] + ['--execute'], 'started_utc': 'authored-start',
                      'wrapper': {'pid': 411, 'starttime': 100}, 'runner': {'pid': 412, 'starttime': 101}}
        self.end = {**self.start, 'exit_code': 0, 'owner_exit_code': 0, 'accepted': True, 'runner_started': True,
                    'runner_reaped': True, 'forced_runner': False, 'wrapper_error': None, 'cleanup_errors': [], 'finished_utc': 'authored-finish'}
        self.save(self.owner / 'preflight.json', {'inspection_session': self.expected})
        self.save(self.owner / 'prerequisites.json', self.current)
        self.save(self.owner / 'owner.json', self.start)
        self.save(self.owner / 'command.json', self.start['command'])
        self.save(self.work / 'inspection-session.json', self.expected)
        self.save(self.work / 'a1/expected-policy.json', self.policy)
        self.save(self.work / 'a1/vm-result.json', {'status': 'VM_OBSERVATION_COMPLETE', 'error': None,
            'witnesses': self.native, 'cleanup': self.cleanup, 'natural_exit': True})
        self.save(self.work / 'a1/vm.child.json', {'pid': 413, 'start_ticks': 102})
        self.save(self.work / 'a1/launch.json', {'fixture': 'native launch'})
        for name in ('fsck-system.txt', 'fsck-data.txt'):
            (self.files / name).write_text(CLEAN)
        self.refresh()

    def tearDown(self):
        self.temp.cleanup()

    def save(self, path, value):
        path.write_bytes(json_bytes(value))

    def refresh(self):
        self.save(self.files / 'result.json', self.guest)
        outputs = {}
        for name in ('result.json', 'fsck-system.txt', 'fsck-data.txt'):
            path = self.files / name
            if path.exists():
                body = path.read_bytes()
                outputs['inspection/' + name] = {'path': str(path.relative_to(self.work)), 'bytes': len(body), 'sha256': sha(body)}
        self.result = {'schema': 1, 'status': 'SAVED_FIRSTBOOT_INSPECTION_PASSED',
            'inspection_session_sha256': self.m['digest'](self.expected), 'full_backing_chain_unchanged': True,
            'preparation_and_guard_unchanged': True, 'natural_exit': True, 'error': None, 'identity_error': None,
            'native_witnesses': self.native, 'cleanup': self.cleanup, 'boot_complete': False, 'gpu_path_complete': False,
            'app_gate_changed': False, 'outputs': outputs, 'guest_result': self.guest,
            'launch': {'path': str(self.work / 'a1/launch.json'), 'sha256': sha((self.work / 'a1/launch.json').read_bytes())}}
        self.save(self.work / 'result.json', self.result)
        self.save(self.work / 'a1/inspection-result.json', self.result)
        self.end['inspection_result_sha256'] = sha((self.work / 'result.json').read_bytes())
        self.save(self.owner / 'exit.json', self.end)

    def preservation(self, _m):
        for path, pin in self.current['inputs'].items():
            if sha(Path(path).read_bytes()) != pin:
                raise ValueError('fixture input changed')
        return {'bound_inputs_unchanged': True, 'resume4_jib_pins_unchanged': 11, 'error': None}

    def context(self, module=fsck):
        with mock.patch.object(module, 'input_preservation', side_effect=self.preservation):
            return module.completed_context(self.m)

    def test_real_canonical_transition_and_both_fsck_logs_validate(self):
        value = self.context()
        self.assertTrue(value['accepted'] and value['canonical_pass'])
        self.assertEqual(value['guest']['journals']['iOSRoot']['header_classification']['state'],
                         'ROOT_AUTHORED_NEEDINIT_TO_INITIALIZED_EMPTY')
        self.m['refuse_live_children'].assert_called_once_with()

    def test_missing_transition_is_refused_even_when_outer_receipt_says_accepted(self):
        self.guest['journals']['iOSRoot']['header_classification'].pop('jib_transition')
        self.refresh()
        with self.assertRaises(ValueError):
            self.context()

    def test_changed_unfiltered_fsck_log_is_refused(self):
        (self.files / 'fsck-data.txt').write_text(CLEAN + '\nRepair was requested\n')
        self.refresh()
        with self.assertRaises(ValueError):
            self.context()

    def test_missing_fsck_log_is_refused(self):
        (self.files / 'fsck-system.txt').unlink()
        self.refresh()
        with self.assertRaises(FileNotFoundError):
            self.context()

    def test_forced_or_unaccepted_outer_receipt_is_refused(self):
        for key, value in (('accepted', False), ('forced_runner', True), ('runner_reaped', False)):
            with self.subTest(key=key):
                altered = {**self.end, key: value}
                self.save(self.owner / 'exit.json', altered)
                with self.assertRaises(ValueError):
                    self.context()

    def test_recorded_live_process_is_refused(self):
        self.m['identity'] = lambda pid: self.start['wrapper'] if pid == 411 else None
        with self.assertRaises(ValueError):
            self.context()

    def test_wrong_canonical_source_pin_is_refused(self):
        self.m['SOURCE_HASHES'][CPU / 'inspect_ios26_firstboot.py'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'validator changed'):
            self.context()

    def test_changed_guest_metadata_after_validation_is_refused(self):
        original = fsck.bound_module
        def wrapped(m, path, expected):
            value = original(m, path, expected)
            if path.name == 'inspect_ios26_firstboot.py':
                delegated = value.guest_pass
                def validate(*args):
                    result = delegated(*args)
                    path = self.files / 'result.json'
                    path.write_bytes(path.read_bytes() + b'\n')
                    return result
                value.guest_pass = validate
            return value
        with mock.patch.object(fsck, 'bound_module', side_effect=wrapped), self.assertRaisesRegex(ValueError, 'metadata changed'):
            self.context()

    def test_changed_bound_input_after_validation_is_refused(self):
        original = fsck.bound_module
        def wrapped(m, path, expected):
            value = original(m, path, expected)
            if path.name == 'inspect_ios26_firstboot.py':
                delegated = value.guest_pass
                def validate(*args):
                    result = delegated(*args)
                    self.anchor.write_bytes(b'changed input\n')
                    return result
                value.guest_pass = validate
            return value
        with mock.patch.object(fsck, 'bound_module', side_effect=wrapped), self.assertRaisesRegex(ValueError, 'fixture input changed'):
            self.context()

    def test_selected_views_preserve_false_proofs_and_omit_private_fields(self):
        value = self.context()
        value['guest']['private_file_inventory'] = ['PRIVATE_SENTINEL']
        value['guest']['journals']['iOSRoot']['raw_jib'] = 'PRIVATE_SENTINEL'
        for view in ('root', 'data', 'fsck'):
            module = fsck if view == 'fsck' else journals
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                module.render(value, view)
            output = stream.getvalue()
            self.assertNotIn('PRIVATE_SENTINEL', output)
            self.assertNotIn(CLEAN, output)
            self.assertLess(len(output.encode()), 3600)
            if view == 'root':
                selected = json.loads(output.splitlines()[1])['iOSRoot']
                self.assertIs(selected['header_classification']['baseline_jib_identical'], False)
                self.assertIs(selected['header_classification']['baseline_journal_metadata_identical'], False)
                self.assertEqual(selected['header_classification']['jib_transition']['cleared_mask'], 4)


class ScopeAndTransport(unittest.TestCase):
    def test_missing_metadata_stays_unavailable(self):
        self.assertIsNone(journals.journal_projection(None))
        self.assertIsNone(journals.fields(None, ('status',)))
        self.assertIsNone(fsck.codes(None))
        with self.assertRaises(ValueError):
            fsck.codes([{'message': 'private guest diagnostic'}])

    def test_proof_views_share_identical_acceptance_and_preservation_functions(self):
        def functions(name):
            return {n.name: ast.dump(n) for n in ast.parse((HERE / name).read_text()).body if isinstance(n, ast.FunctionDef)}
        a, b, c = functions('observe_inspection.py'), functions('observe_journals.py'), functions('observe_fsck.py')
        for name in ('load_owner', 'input_preservation'):
            self.assertEqual(a[name], b[name])
            self.assertEqual(a[name], c[name])
        for name in ('completed_context', 'bound_module', 'fields'):
            self.assertEqual(b[name], c[name])

    def test_all_seven_commands_decode_exact_sources_and_keep_bounds(self):
        manifest = json.loads((HERE / 'query-manifest.json').read_bytes())
        self.assertEqual(len(manifest['queries']), 7)
        for row in manifest['queries']:
            command = (HERE / row['command']['path']).read_bytes()
            source = (HERE / row['source']['path']).read_bytes()
            self.assertLessEqual(len(command), 6000)
            self.assertEqual(sha(command), row['command']['sha256'])
            self.assertEqual(sha(source), row['source']['sha256'])
            argv = shlex.split(command.decode())
            self.assertEqual(argv[:4], ['/data/data/com.termux/files/usr/bin/python', '-I', '-B', '-c'])
            self.assertEqual(argv[5:], row['arguments'])
            tree = ast.parse(argv[4])
            encoded = next(n.args[0].value for n in ast.walk(tree) if isinstance(n, ast.Call) and
                           isinstance(n.func, ast.Attribute) and n.func.attr == 'b64decode')
            self.assertEqual(gzip.decompress(base64.b64decode(encoded, validate=True)), source)


if __name__ == '__main__':
    unittest.main()
