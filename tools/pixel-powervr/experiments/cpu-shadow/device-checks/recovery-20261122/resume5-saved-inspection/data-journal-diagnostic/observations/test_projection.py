"""Narrow synthetic reader/finalizer checks; no phone or native operations."""
import ast
import base64
import contextlib
import copy
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent


def load(name):
    path = ROOT / name
    spec = importlib.util.spec_from_file_location('checked_' + path.stem, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class ProjectionTests(unittest.TestCase):
    def test_unbound_readers_refuse_before_any_file_read(self):
        for name in ('observe_result_pin_UNRELEASED.py', 'observe_data_journal_UNRELEASED.py'):
            m = load(name)
            with mock.patch.object(m, 'read') as read:
                with self.assertRaisesRegex(ValueError, 'UNRELEASED'):
                    m.inspect_result()
                read.assert_not_called()

    def test_source_only_binding_cannot_release_detailed_mode(self):
        m = load('observe_data_journal_UNRELEASED.py')
        m.SOURCE_PIN = {'bytes': 10, 'sha256': '1' * 64}
        with mock.patch.object(m, 'read') as read:
            with self.assertRaisesRegex(ValueError, 'actual observed result'):
                m.inspect_result()
            read.assert_not_called()

    def test_child_reap_forcing_absence_and_pid_reuse_refuse(self):
        m = load('observe_result_pin_UNRELEASED.py')
        rows = [{'label': label, 'pid': 300 + i, 'exit_code': 0, 'reaped': True, 'forced': False}
                for i, label in enumerate(('primary', 'alternate', 'jib', 'journal'))]
        owner = types.SimpleNamespace(identity=lambda pid: None)
        m.check_children(rows, owner)
        for key, bad in (('reaped', False), ('forced', True), ('exit_code', 2),
                         ('pid', True), ('cleanup_error', 'incomplete')):
            changed = copy.deepcopy(rows); changed[0][key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError):
                m.check_children(changed, owner)
        with self.assertRaisesRegex(ValueError, 'currently occupied'):
            m.check_children(rows, types.SimpleNamespace(identity=lambda pid: {'pid': pid, 'starttime': 999}))
        changed = copy.deepcopy(rows); changed[1]['pid'] = changed[0]['pid']
        with self.assertRaises(ValueError):
            m.check_children(changed, owner)

    def test_pending_output_does_not_claim_liveness_or_completion(self):
        m = load('observe_result_pin_UNRELEASED.py')
        m.SOURCE_PIN = {'bytes': 10, 'sha256': '1' * 64}
        output = io.StringIO()
        state = {'output_directory_present': True, 'session_present': True}
        owner = types.SimpleNamespace(utc=lambda: 'SYNTHETIC')
        with mock.patch.object(m, 'inspect_result', return_value=(None, owner, None, state)), \
             contextlib.redirect_stdout(output):
            m.main()
        result = json.loads(output.getvalue())
        self.assertEqual(result['status'], 'DATA_JOURNAL_RESULT_NOT_PRESENT')
        self.assertIs(result['owner_state_known'], False)
        self.assertIs(result['completion_claimed'], False)
        self.assertIs(result['native_tool_or_guest_started'], False)

    def test_pin_output_keeps_decimal_digest_and_nonacceptance_fields(self):
        m = load('observe_result_pin_UNRELEASED.py')
        m.SOURCE_PIN = {'bytes': 10, 'sha256': '1' * 64}
        owner = types.SimpleNamespace(utc=lambda: 'SYNTHETIC')
        result = {'status': 'READONLY_DATA_JOURNAL_DIAGNOSTIC_OBSERVED',
                  'analysis': {'status': 'INCOMPLETE', 'code': 'unsupported_zero_transaction_sequence'}}
        pin = {'bytes': 77, 'sha256': hashlib.sha256(b'SYNTHETIC_RECEIPT').hexdigest()}
        output = io.StringIO()
        with mock.patch.object(m, 'inspect_result', return_value=(None, owner, result, pin)), \
             contextlib.redirect_stdout(output):
            m.main()
        lines = output.getvalue().splitlines()
        fields = json.loads(lines[0])
        self.assertEqual(fields['parser_status'], 'INCOMPLETE')
        self.assertIs(fields['retained_payloads_reverified'], False)
        self.assertIs(fields['pure_parser_recomputed'], False)
        self.assertIs(fields['inspection_success_claimed'], False)
        self.assertEqual(lines[2], 'result_sha256=' + pin['sha256'])
        self.assertEqual(bytes(json.loads(lines[3].split('=', 1)[1])).hex(), pin['sha256'])

    def test_read_rejects_symlink_hardlink_and_oversized_input(self):
        m = load('observe_result_pin_UNRELEASED.py')
        original_fstat = os.fstat
        def root_owned_stat(fd):
            actual = original_fstat(fd)
            values = {key: getattr(actual, key) for key in
                      ('st_mode', 'st_nlink', 'st_size', 'st_dev', 'st_ino', 'st_mtime_ns', 'st_ctime_ns')}
            return types.SimpleNamespace(st_uid=0, **values)
        with tempfile.TemporaryDirectory() as name:
            root = Path(name).resolve(); source = root / 'ordinary'; source.write_bytes(b'abc')
            # The executor is unprivileged; emulate only the phone's required
            # owner field while retaining actual inode/link/size/type checks.
            with mock.patch.object(m.os, 'fstat', side_effect=root_owned_stat):
                self.assertEqual(m.read(source, 3), b'abc')
                with self.assertRaises(ValueError):
                    m.read(source, 2)
                link = root / 'symlink'; link.symlink_to(source)
                with self.assertRaises(ValueError):
                    m.read(link, 3)
                hard = root / 'hard'; os.link(source, hard)
                with self.assertRaises(ValueError):
                    m.read(source, 3)

    def test_shared_binding_validation_and_absence_helpers_are_identical(self):
        def functions(name):
            return {node.name: ast.dump(node, include_attributes=False)
                    for node in ast.parse((ROOT / name).read_bytes()).body if isinstance(node, ast.FunctionDef)}
        a = functions('observe_result_pin_UNRELEASED.py')
        b = functions('observe_data_journal_UNRELEASED.py')
        for name in ('require', 'sha', 'pin_ok', 'read', 'validate_completed', 'check_children'):
            self.assertEqual(a[name], b[name], name)

    def test_detailed_reader_has_no_native_or_write_calls(self):
        tree = ast.parse((ROOT / 'observe_data_journal_UNRELEASED.py').read_bytes())
        called = {ast.unparse(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}
        for forbidden in ('subprocess.Popen', 'subprocess.run', 'os.kill', 'os.waitpid', 'd.main',
                          'd.extract_data', 'd.run_tool', 'd.save', 'd.save_json'):
            self.assertNotIn(forbidden, called)
        self.assertIn('d.verify_preservation', called)
        self.assertIn('d.validate_parser_analysis', called)
        self.assertIn('parser.analyze_journal', called)

    def test_source_binding_changes_only_constant_and_commands_decode_exactly(self):
        m = load('build_projection.py')
        template = (ROOT / 'observe_result_pin_UNRELEASED.py').read_bytes()
        source = m.bind(template, {'SOURCE_PIN': m.HOST_PIN})
        actual = (ROOT / 'source-binding/observe_result_pin.py').read_bytes()
        self.assertEqual(source, actual)
        cmd = m.command(source, 'pin')
        self.assertEqual(cmd, (ROOT / 'source-binding/observe-result-pin.command.txt').read_bytes())
        loader = shlex.split(cmd.decode())[-1]
        tree = ast.parse(loader)
        encoded = next(node.args[0].value for node in ast.walk(tree) if isinstance(node, ast.Call) and
                       isinstance(node.func, ast.Attribute) and node.func.attr == 'b64decode')
        self.assertEqual(gzip.decompress(base64.b64decode(encoded, validate=True)), actual)
        self.assertIn(hashlib.sha256(actual).hexdigest(), loader)
        self.assertLessEqual(len(cmd), 6000)

    def test_bounded_detailed_pages_keep_all_fields_and_require_actual_pins(self):
        m = load('build_projection.py')
        source = m.bind((ROOT / 'observe_data_journal_UNRELEASED.py').read_bytes(),
                        {'SOURCE_PIN': m.HOST_PIN, 'RESULT_PIN': {'bytes': 9999, 'sha256': '2' * 64}})
        for mode, page in [('summary', 0)] + [('records', i) for i in range(4)]:
            cmd = m.command(source, mode, page)
            self.assertLessEqual(len(cmd), 6000)
            self.assertIn(repr(mode), shlex.split(cmd.decode())[-1])
        detailed = load('observe_data_journal_UNRELEASED.py')
        detailed.SOURCE_PIN = m.HOST_PIN
        detailed.RESULT_PIN = {'bytes': 9999, 'sha256': '2' * 64}
        detailed.PAGE = 4
        with self.assertRaisesRegex(ValueError, 'bounded projection'):
            detailed.finalized()

    def test_finalizer_rejects_unreviewed_evidence_and_bad_decimal_digest(self):
        m = load('build_projection.py')
        with tempfile.TemporaryDirectory() as name:
            root = Path(name).resolve(); observations = root / 'observations'; observations.mkdir()
            selected = root / 'selected.json'
            selected.write_text(json.dumps({'independently_reviewed': False}))
            with mock.patch.object(m, 'ROOT', observations), mock.patch.object(m, 'reviewed_source'), \
                 mock.patch.object(m, 'save_fresh') as save:
                with self.assertRaisesRegex(ValueError, 'independent review'):
                    m.finalize(selected)
                save.assert_not_called()
            digest = hashlib.sha256(b'SYNTHETIC_RESULT').hexdigest()
            value = {'independently_reviewed': True, 'independent_review': 'review.json',
                     'status': 'DATA_JOURNAL_RESULT_BINDING_READY',
                     'diagnostic_status': 'READONLY_DATA_JOURNAL_DIAGNOSTIC_OBSERVED', 'readonly': True,
                     'source': {'path': m.SOURCE, **m.HOST_PIN}, 'forced_tool_children': [],
                     'tool_commands': 4, 'retained_read_count': 4,
                     'result': {'path': m.RESULT, 'bytes': 100, 'sha256': digest, 'digest_bytes': [0] * 32}}
            for key in ('owner_absent', 'owned_child_pids_absent', 'all_own_tool_children_reaped',
                        'recorded_inspection_processes_absent', 'disk_identities_unchanged',
                        'bound_metadata_unchanged', 'bound_tooling_unchanged', 'owned_child_exit_receipts_verified'):
                value[key] = True
            for key in ('whole_image_hashes_recomputed', 'raw_bytes_exported', 'private_file_inventories_exported',
                        'inspection_success_claimed', 'filesystem_consistency_claimed', 'replay_safety_claimed',
                        'native_tool_or_guest_started', 'actual_result_bound_before_query',
                        'retained_payloads_reverified', 'pure_parser_recomputed'):
                value[key] = False
            selected.write_text(json.dumps(value)); (root / 'review.json').write_text('{}')
            with mock.patch.object(m, 'ROOT', observations), mock.patch.object(m, 'reviewed_source'), \
                 mock.patch.object(m, 'save_fresh') as save:
                with self.assertRaisesRegex(ValueError, 'all32'):
                    m.finalize(selected)
                save.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
