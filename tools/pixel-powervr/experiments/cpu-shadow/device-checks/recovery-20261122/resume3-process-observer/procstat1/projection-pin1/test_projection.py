#!/usr/bin/env python3
"""Focused evidence-projection tests; no device, logs, or process actions."""
import ast
import base64
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import types
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('projection_target', HERE / 'observe_status.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class Projection(unittest.TestCase):
    def collect_fixture(self, vm):
        identity = {'pid': 99, 'start_ticks': 100}
        source = {'path': str(M.SOURCE), **M.SOURCE_PIN}
        scope, bounds = {}, {'process_identities': 128, 'event_bytes': 8 << 20, 'events': 10000}
        def pin(name, value):
            body = json.dumps(value).encode()
            return {'path': str(M.OUT / name), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}
        ready = {'schema': 1, 'kind': 'saved_inspection_process_observer_ready', 'source': source,
                 'scope': scope, 'bounds': bounds, 'output_directory': str(M.OUT), 'diagnostic_only': True, 'observer': identity}
        ready_pin = pin('ready.json', ready)
        status = {'schema': 1, 'kind': 'saved_inspection_process_observer_status', 'observer': identity,
                  'ready_sha256': ready_pin['sha256'], 'source_sha256': M.SOURCE_PIN['sha256'], 'scope': scope,
                  'output_directory': str(M.OUT), 'status': 'OBSERVATION_FINISHED', 'phase': 'FINISHED',
                  'heartbeat_monotonic_ns': 1, 'sample_count': 1, 'sample_gaps': 0, 'read_gaps': 0,
                  'discovery': {}, 'tracked_identities': 0, 'events': {}, 'live': []}
        summary = {'schema': 1, 'observer': identity, 'ready': ready_pin, 'source': source, 'scope': scope,
                   'bounds': bounds, 'status': status['status'], 'processes': [], 'owner_receipt': None,
                   'qemu_receipt_identity': None, 'errors': [], 'remaining_observed_identities': [],
                   'inspection_outer_exit': None, 'qemu_identity_observed_alive_or_zombie': False,
                   'events': {'path': str(M.OUT / 'events.jsonl'), 'bytes': 0, 'count': 0, 'sha256': hashlib.sha256(b'').hexdigest()}}
        exited = {'schema': 1, 'observer': identity, 'summary': pin('summary.json', summary), 'status': status['status'], 'exit_code': 0}
        values = {'ready.json': ready, 'status.json': status, 'summary.json': summary, 'exit.json': exited, 'vm-result.json': vm}
        def read_json(path):
            value = values[path.name]
            return value, pin(path.name, value)
        def require(condition, message):
            if not condition: raise ValueError(message)
        proc = Mock()
        proc.snapshot.side_effect = FileNotFoundError()
        module = types.SimpleNamespace(SCOPE=scope, BOUNDS=bounds, WORK=Path('/fixture'), UnstableRead=RuntimeError,
            read_json=read_json, require=require, Proc=lambda: proc, utc=lambda: 'fixture',
            key=lambda r: (r['pid'], r['start_ticks']), file_bytes=lambda *args: b'',
            sha=lambda b: hashlib.sha256(b).hexdigest())
        with patch.object(M, 'load_observer', return_value=module), patch.object(M.os.path, 'lexists', return_value=True):
            return M.collect(final=True)

    def test_missing_or_null_forced_field_is_unavailable_and_unclassified(self):
        for cleanup in ({}, {'forced_descendants': None}):
            with self.subTest(cleanup=cleanup):
                value = self.collect_fixture({'cleanup': cleanup})
                self.assertFalse(value['forced_descendants_available'])
                self.assertIsNone(value['forced_pid_projection'])

    def test_present_empty_forced_list_is_explicitly_available(self):
        value = self.collect_fixture({'cleanup': {'forced_descendants': []}})
        self.assertTrue(value['forced_descendants_available'])
        self.assertEqual(value['forced_pid_projection']['mappings'], [])

    def test_invalid_forced_schema_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'invalid bounded forced'):
            self.collect_fixture({'cleanup': {'forced_descendants': 'unknown'}})

    def row(self, start=22):
        return {'identity': {'pid': 12, 'start_ticks': start}, 'role': 'native_worker',
                'first_observed_parent': {'pid': 11, 'start_ticks': 21}, 'present': False,
                'last': {'ppid': 10, 'state': 'Z', 'comm': 'asoft-stub0', 'kill_pending': False,
                         'pending': {'SigPnd': '0', 'ShdPnd': '0'}}, 'last_monotonic_ns': 99}

    def test_unmatched_forced_pid_remains_unclassified(self):
        result = M.forced_projection({'processes': [self.row()]}, [999], [])
        mapping = result['mappings'][0]
        self.assertEqual(mapping['classification'], 'unclassified')
        self.assertEqual(mapping['matching_observed_identities'], [])

    def test_pid_reuse_retains_both_identities_and_does_not_choose_role(self):
        result = M.forced_projection({'processes': [self.row(22), self.row(44)]}, [12], [])
        mapping = result['mappings'][0]
        self.assertEqual(mapping['classification'], 'ambiguous_pid_reuse')
        self.assertEqual(len(mapping['matching_observed_identities']), 2)
        self.assertTrue(mapping['cleanup_receipt_does_not_supply_start_ticks'])

    def test_event_projection_keeps_early_role_and_late_states_with_omissions(self):
        events = [{'event': 'process_change', 'identity': {'pid': 12, 'start_ticks': 22},
                   'utc': 'fixture', 'monotonic_ns': n, 'snapshot': {'ppid': 10, 'state': 'S', 'kill_pending': False}}
                  for n in range(25)]
        result = M.forced_projection({'processes': [self.row()]}, [12], events)
        match = result['mappings'][0]['matching_observed_identities'][0]
        self.assertEqual((match['selected_event_count'], match['events_omitted']), (12, 13))
        self.assertEqual([e['monotonic_ns'] for e in match['events']], [0, 1, 2] + list(range(16, 25)))
        self.assertEqual((match['last_parent_pid'], match['last_state']), (10, 'Z'))

    def test_forced_list_projection_cap_is_explicit(self):
        result = M.forced_projection({'processes': []}, list(range(1, 21)), [])
        self.assertEqual((result['projected_forced_pid_count'], result['forced_pids_omitted']), (16, 4))

    def test_atomic_status_retry_is_finite(self):
        class Unstable(ValueError): pass
        module = Mock()
        module.UnstableRead = Unstable
        module.read_json.side_effect = Unstable('replaced')
        with self.assertRaisesRegex(ValueError, 'three bounded reads'):
            M.stable_json(module, Path('/fixture'))
        self.assertEqual(module.read_json.call_count, 3)

    def test_projector_has_no_mutating_or_target_action_calls(self):
        tree = ast.parse((HERE / 'observe_status.py').read_text())
        banned = {'kill', 'killpg', 'waitpid', 'waitid', 'ptrace', 'Popen', 'fork', 'unlink',
                  'mkdir', 'write_text', 'write_bytes', 'write_json', 'chmod', 'rename', 'replace'}
        calls = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
        self.assertFalse(calls & banned)

    def test_terminal_projection_has_explicit_sixty_nine_line_cap(self):
        pin = {'bytes': 100, 'sha256': 'a' * 64}
        events = [{'event': 'process_change', 'identity': {'pid': 12, 'start_ticks': 22},
                   'utc': 'fixture', 'monotonic_ns': n, 'snapshot': {'ppid': 10, 'state': 'S', 'kill_pending': False}}
                  for n in range(20)]
        mapping = M.forced_projection({'processes': [self.row()]}, [12] * 16, events)
        value = {'status': 'OBSERVATION_FINISHED', 'observed_utc': 'fixture', 'observer': {'pid': 99, 'start_ticks': 1},
            'observer_presence': {'same_identity_present': False}, 'phase': 'FINISHED', 'heartbeat_age_seconds': 1,
            'sample_count': 2, 'sampling_gaps': 0, 'read_gaps': 0, 'discovery': {}, 'source': pin, 'ready': pin,
            'exit': pin, 'summary': pin, 'events': pin, 'inspection_outer_exit': {'accepted': False, 'exit_code': 2},
            'summary_errors': [], 'remaining_observed_identities': [], 'forced_pid_projection': mapping}
        text = M.compact(value)
        self.assertEqual(len(text.splitlines()), 69)
        self.assertIn('native_worker', text)
        self.assertIn('Additional selected rows omitted', text)

    def test_generated_query_sources_are_ast_equivalent_to_reviewed_reader(self):
        expected = ast.dump(ast.parse((HERE / 'observe_status.py').read_text()), include_attributes=False)
        for name in ('observe-status', 'observe-final', 'observe-final-json'):
            tree = ast.parse((HERE / (name + '.py')).read_text())
            normalized = ast.Module(body=tree.body[2:], type_ignores=[])
            self.assertEqual(ast.dump(normalized, include_attributes=False), expected)

    def test_all_query_commands_decode_exactly_and_fit_six_thousand_bytes(self):
        for path in HERE.glob('*.command.txt'):
            self.assertLessEqual(len(path.read_bytes()), 6000)
            args = shlex.split(path.read_text())
            self.assertEqual(args[:4], ['/data/data/com.termux/files/usr/bin/python', '-I', '-B', '-c'])
            tree = ast.parse(args[4])
            encoded = next(node.args[0].value for node in ast.walk(tree) if isinstance(node, ast.Call) and
                           isinstance(node.func, ast.Attribute) and node.func.attr == 'b64decode')
            body = gzip.decompress(base64.b64decode(encoded, validate=True))
            self.assertEqual(body, path.with_name(path.name.replace('.command.txt', '.py')).read_bytes())


if __name__ == '__main__':
    unittest.main(verbosity=2)
