#!/usr/bin/env python3
"""Focused evidence-projection tests; no device, logs, or process actions."""
import ast
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('projection_target', HERE / 'observe_status.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class Projection(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
