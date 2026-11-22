#!/usr/bin/env python3
"""Focused synthetic identity/genealogy and bounded receipt tests; no phone."""
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('observer_test_target', HERE / 'observe_processes.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def row(pid, start=None, ppid=1, comm='python', executable=None, state='S'):
    return {'pid': pid, 'start_ticks': start or pid * 10, 'ppid': ppid, 'pgrp': 10, 'session': 10,
            'state': state, 'comm': comm, 'threads': 1, 'tgid': pid, 'status_ppid': ppid,
            'pending': {'SigPnd': '0000000000000000', 'ShdPnd': '0000000000000000'},
            'kill_pending': False, 'executable': executable, 'parent_changed_during_snapshot': False}


class FakeProc:
    def __init__(self, rows=(), edges=None):
        self.rows = {r['pid']: copy.deepcopy(r) for r in rows}
        self.edges = edges or {}
        self.children_calls = []
        self.relations = {p: {k: r[k] for k in ('pid', 'start_ticks', 'ppid')} for p, r in self.rows.items()}

    def stat(self, pid):
        if pid not in self.rows:
            raise FileNotFoundError(pid)
        return copy.deepcopy(self.rows[pid])

    snapshot = stat

    def children(self, parent):
        self.children_calls.append(parent['pid'])
        return [M.small_identity(self.rows[pid]) for pid in self.edges.get(parent['pid'], ())]

    def refresh_discovery(self, force=False):
        return {'index': 1, 'numeric_entries': len(self.rows), 'read_bytes': 100,
                'duration_ms': 1, 'failures': {'vanished': 0, 'unreadable': 0, 'malformed': 0}} if force else None

    def discovery_summary(self):
        return {'method': 'bounded_numeric_proc_stat', 'scans': 1, 'unavailable_stat_reads': 0}


class Parsing(unittest.TestCase):
    def test_stat_comm_parentheses_and_offsets(self):
        fields = ['S', '7', '8', '9'] + ['0'] * 16
        fields[17], fields[19] = '3', '98765'
        got = M.parse_stat(('12 (name ) with space) ' + ' '.join(fields)).encode(), 12)
        self.assertEqual((got['ppid'], got['pgrp'], got['session'], got['threads'], got['start_ticks']), (7, 8, 9, 3, 98765))
        self.assertEqual(got['comm'], 'name ) with space')

    def test_stat_wrong_pid_and_short_rejected(self):
        for body in (b'13 (x) S 1 1 1', b'12 missing parentheses', b'x' * 4097):
            with self.assertRaises(ValueError):
                M.parse_stat(body, 12)

    def test_pending_sigkill_and_leader_check(self):
        body = b'Pid:\t12\nTgid:\t12\nPPid:\t7\nSigPnd:\t00000000\nShdPnd:\t00000100\n'
        self.assertTrue(M.parse_status(body, 12)['kill_pending'])
        with self.assertRaises(ValueError):
            M.parse_status(body.replace(b'Tgid:\t12', b'Tgid:\t11'), 12)

    def test_owner_identity_requires_exact_positive_schema(self):
        self.assertEqual(M.from_owner({'pid': 1, 'starttime': 2}), {'pid': 1, 'start_ticks': 2})
        for value in ({'pid': True, 'starttime': 2}, {'pid': 1, 'start_ticks': 2}, {'pid': 1, 'starttime': 0}):
            with self.assertRaises(ValueError):
                M.from_owner(value)


class Genealogy(unittest.TestCase):
    def make_graph(self, rows, edges=None):
        proc, events = FakeProc(rows, edges), []
        graph = M.Graph(proc, lambda kind, **v: events.append({'kind': kind, **v}), {'pid': 99, 'start_ticks': 990})
        return proc, graph, events

    def test_delayed_native_name_promotes_only_qemu_descendant(self):
        proc, graph, events = self.make_graph([row(10), row(11, ppid=10, executable=M.QEMU),
            row(12, ppid=11, executable=M.QEMU), row(13, ppid=10, comm='asoft-stubfac', executable=M.QEMU)], {10: [11, 13], 11: [12]})
        graph.anchor({'pid': 10, 'start_ticks': 100}, 'inspector')
        graph.anchor({'pid': 11, 'start_ticks': 110}, 'qemu', {'pid': 10, 'start_ticks': 100}, M.QEMU)
        graph.sample()
        self.assertEqual(graph.rows[(12, 120)]['role'], 'descendant')
        self.assertEqual(graph.rows[(13, 130)]['role'], 'descendant')
        proc.rows[12]['comm'] = 'asoft-stubfac'
        graph.sample()
        self.assertEqual(graph.rows[(12, 120)]['role'], 'native_factory')
        self.assertTrue(any(e['kind'] == 'native_role_observed' for e in events))

    def test_worker_adoption_keeps_prior_genealogy(self):
        proc, graph, events = self.make_graph([row(10), row(11, ppid=10, executable=M.QEMU),
            row(12, ppid=11, comm='asoft-stubfac', executable=M.QEMU),
            row(13, ppid=12, comm='asoft-stub0', executable=M.QEMU)], {10: [11], 11: [12], 12: [13]})
        graph.anchor({'pid': 10, 'start_ticks': 100}, 'inspector')
        graph.anchor({'pid': 11, 'start_ticks': 110}, 'qemu', {'pid': 10, 'start_ticks': 100}, M.QEMU)
        graph.sample()
        del proc.rows[11], proc.rows[12]
        proc.rows[13]['ppid'] = proc.rows[13]['status_ppid'] = 10
        proc.edges = {10: [13]}
        graph.sample()
        worker = graph.rows[(13, 130)]
        self.assertEqual(worker['role'], 'native_worker')
        self.assertEqual(worker['first_observed_parent'], {'pid': 12, 'start_ticks': 120})
        self.assertEqual(worker['last']['ppid'], 10)
        self.assertTrue(any(e['kind'] == 'process_change' and e['identity']['pid'] == 13 for e in events))

    def test_pid_reuse_does_not_inherit_ownership(self):
        proc, graph, events = self.make_graph([row(10), row(11, ppid=10)], {10: [11]})
        graph.anchor({'pid': 10, 'start_ticks': 100}, 'inspector')
        graph.sample()
        proc.rows[11] = row(11, start=999, ppid=1, comm='asoft-stub0', executable=M.QEMU)
        proc.edges = {}
        graph.sample()
        self.assertFalse(graph.rows[(11, 110)]['present'])
        self.assertNotIn((11, 999), graph.rows)
        self.assertTrue(any(e['kind'] == 'identity_reused' for e in events))

    def test_owner_siblings_and_unrelated_names_are_not_discovered(self):
        proc, graph, _ = self.make_graph([row(9), row(10, ppid=9), row(99, comm='asoft-stub0', executable=M.QEMU)], {9: [10, 99]})
        graph.anchor({'pid': 9, 'start_ticks': 90}, 'inspection_owner')
        graph.anchor({'pid': 10, 'start_ticks': 100}, 'inspector', {'pid': 9, 'start_ticks': 90})
        graph.sample()
        self.assertNotIn(9, proc.children_calls)
        self.assertNotIn((99, 990), graph.rows)

    def test_observer_inside_target_tree_is_rejected(self):
        proc, graph, _ = self.make_graph([row(10), row(99, ppid=10)], {10: [99]})
        graph.anchor({'pid': 10, 'start_ticks': 100}, 'inspector')
        with self.assertRaisesRegex(ValueError, 'observer entered'):
            graph.sample()

    def test_live_qemu_wrong_executable_rejected_but_zombie_explicit(self):
        proc, graph, events = self.make_graph([row(11, ppid=10, executable='/wrong')])
        with self.assertRaisesRegex(ValueError, 'live QEMU executable'):
            graph.anchor({'pid': 11, 'start_ticks': 110}, 'qemu', {'pid': 10, 'start_ticks': 100}, M.QEMU)
        proc.rows[11].update(state='Z', executable=None)
        self.assertTrue(graph.anchor({'pid': 11, 'start_ticks': 110}, 'qemu', {'pid': 10, 'start_ticks': 100}, M.QEMU))
        self.assertFalse(next(e for e in events if e['kind'] == 'anchor_executable')['verified'])

    def test_process_limit_stops_before_extra_record(self):
        _, graph, _ = self.make_graph([])
        with patch.dict(M.BOUNDS, {'process_identities': 1}):
            graph.add(row(10), 'inspector')
            with self.assertRaises(M.BoundExceeded):
                graph.add(row(11), 'descendant')
        self.assertEqual(len(graph.rows), 1)

    def test_normal_state_changes_counted_and_kill_pending_logged(self):
        proc, graph, events = self.make_graph([row(10)])
        graph.anchor({'pid': 10, 'start_ticks': 100}, 'inspector')
        proc.rows[10]['state'] = 'R'
        graph.sample()
        self.assertEqual(graph.routine_state_changes, 1)
        proc.rows[10]['kill_pending'] = True
        graph.sample()
        self.assertEqual(sum(e['kind'] == 'process_change' for e in events), 1)

    def test_outside_ancestry_and_start_order(self):
        proc = FakeProc([row(99, start=90, ppid=1), row(1, start=1, ppid=0)])
        self.assertTrue(M.outside_inspector(proc, {'pid': 99, 'start_ticks': 90}, {'pid': 10, 'start_ticks': 100}))
        proc.rows[99]['ppid'] = 10
        proc.rows[10] = row(10)
        with self.assertRaisesRegex(ValueError, 'descendant subtree'):
            M.outside_inspector(proc, {'pid': 99, 'start_ticks': 90}, {'pid': 10, 'start_ticks': 100})


class PublicationAndBounds(unittest.TestCase):
    def test_initial_unstable_read_recovers_and_reports(self):
        pending, events = {}, []
        emit = lambda kind, **v: events.append(kind)
        with patch.object(M, 'read_json', side_effect=[M.UnstableRead('writing'), ({'schema': 1}, {'sha256': 'a'})]):
            with self.assertRaises(M.ReceiptPending):
                M.poll_json(Path('/receipt'), pending, 0, emit)
            self.assertEqual(M.poll_json(Path('/receipt'), pending, 0.1, emit)[0], {'schema': 1})
        self.assertEqual(events, ['receipt_publication_gap', 'receipt_publication_recovered'])
        self.assertEqual(pending, {})

    def test_stable_malformed_receipt_rejected_within_bound(self):
        pending = {}
        with patch.object(M, 'read_json', side_effect=json.JSONDecodeError('bad', '{', 1)):
            with self.assertRaises(M.ReceiptPending):
                M.poll_json(Path('/receipt'), pending, 0, lambda *a, **k: None)
            with self.assertRaisesRegex(ValueError, 'two seconds'):
                M.poll_json(Path('/receipt'), pending, 2.1, lambda *a, **k: None)

    def test_other_stable_validation_error_is_not_retried(self):
        with patch.object(M, 'read_json', side_effect=ValueError('not ordinary')):
            with self.assertRaisesRegex(ValueError, 'not ordinary'):
                M.poll_json(Path('/receipt'), {}, 0, lambda *a, **k: None)

    def test_event_bound_preserves_exact_prior_bytes(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(M, 'OUT', Path(directory)), patch.dict(M.BOUNDS, {'events': 1}):
            events = M.Events()
            try:
                events.emit('one')
                with self.assertRaises(M.BoundExceeded):
                    events.emit('two')
                events.flush()
                body = (Path(directory) / 'events.jsonl').read_bytes()
                self.assertEqual((len(body), M.sha(body)), (events.bytes, events.hash.hexdigest()))
                self.assertEqual(events.count, 1)
            finally:
                events.stream.close()

    def test_own_json_bound_rejects_before_creating_file(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(M, 'OUT', Path(directory)):
            with self.assertRaises(M.BoundExceeded):
                M.write_json('huge.json', {'x': 'large'}, limit=1)
            self.assertFalse((Path(directory) / 'huge.json').exists())

    def test_observer_contains_no_target_action_or_launch_calls(self):
        tree = ast.parse((HERE / 'observe_processes.py').read_text())
        banned = {'kill', 'killpg', 'waitpid', 'waitid', 'ptrace', 'Popen', 'fork', 'execv', 'execve'}
        calls = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
        self.assertFalse(calls & banned)

    def test_output_component_caps_fit_total_including_atomic_temporary(self):
        maximum = M.BOUNDS['event_bytes'] + (256 << 10) + (16 << 10) + M.BOUNDS['summary_bytes'] + 2 * M.BOUNDS['status_bytes'] + (16 << 10)
        self.assertLess(maximum, M.BOUNDS['total_output_bytes'])


class Lifecycle(unittest.TestCase):
    def test_self_stat_discovery_probe_refuses_before_output_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'observer'
            selfrow = row(99)
            selfrow.update(pgrp=99, session=99)
            proc = FakeProc([selfrow])
            proc.relations = {}
            with patch.object(M, 'OUT', output), patch.object(M, 'Proc', return_value=proc), \
                 patch.object(M, 'prerequisites', return_value={}), patch.object(M.os, 'getpid', return_value=99):
                with self.assertRaisesRegex(ValueError, 'numeric proc stat discovery probe'):
                    M.run('a' * 64, 1)
            self.assertFalse(output.exists())

    def run_fixture(self, execution=True, oversized=False):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        output = Path(temporary.name) / 'observer'
        clock = [1.0]
        selfrow = row(99, start=90, ppid=1)
        selfrow.update(pgrp=99, session=99)
        proc = FakeProc([selfrow, row(1, start=1, ppid=0), row(10, ppid=1), row(11, ppid=10), row(12, ppid=11, executable=M.QEMU)], {11: [12]})
        if oversized:
            proc.rows[12]['comm'] = 'x' * 300000
        source = (HERE / 'observe_processes.py').read_bytes()
        source_pin = {'path': str(HERE / 'observe_processes.py'), 'bytes': len(source), 'sha256': M.sha(source)}
        startup = {'schema': 1, 'command': M.SCOPE['inspection_command'], 'wrapper': {'pid': 10, 'starttime': 100},
                   'runner': {'pid': 11, 'starttime': 110}, 'started_utc': 'fixture'}
        exited = dict(startup, finished_utc='fixture-finished', accepted=False, exit_code=2, owner_exit_code=2)
        def read_json(path):
            name = str(path)
            if not execution:
                raise FileNotFoundError(name)
            if path == M.OWNER / 'owner.json': value = startup
            elif path == M.OWNER / 'command.json': value = M.SCOPE['inspection_command']
            elif path == M.OWNER / 'exit.json': value = exited
            elif path == M.WORK / 'a1/vm.child.json': value = {'pid': 12, 'start_ticks': 120}
            elif path == M.WORK / 'a1/launch.json': value = {'command': [M.QEMU], 'environment': {'ASOFT_NATIVE_EL0_REQUIRED': '1'}}
            else: raise FileNotFoundError(name)
            body = json.dumps(value).encode()
            return copy.deepcopy(value), {'path': name, 'bytes': len(body), 'sha256': M.sha(body)}
        bound = {'preflight': {'path': '/fixture', 'bytes': 1, 'sha256': 'a' * 64, 'exit_sha256': 'b' * 64},
                 'inspection_owner_source': {'path': str(M.OWNER_SOURCE), **M.OWNER_SOURCE_PIN}, 'bound_inputs': []}
        with patch.object(M, 'OUT', output), patch.object(M, 'Proc', return_value=proc), patch.object(M, 'prerequisites', return_value=bound), \
             patch.object(M, 'file_bytes', return_value=source), patch.object(M, 'read_json', side_effect=read_json), \
             patch.object(M.os, 'getpid', return_value=99), patch.object(M.time, 'monotonic', side_effect=lambda: clock[0]), \
             patch.object(M.time, 'monotonic_ns', side_effect=lambda: int(clock[0] * 1e9)), \
             patch.object(M.time, 'sleep', side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)), \
             patch.dict(M.BOUNDS, {'launch_wait_seconds': 0.1, 'post_exit_seconds': 0.1}):
            code = M.run('a' * 64, 1)
        return code, json.loads((output / 'exit.json').read_text()), json.loads((output / 'summary.json').read_text()), json.loads((output / 'status.json').read_text())

    def test_observation_completion_is_independent_of_inspection_rejection(self):
        code, exited, summary, status = self.run_fixture()
        self.assertEqual(code, 0)
        self.assertEqual(exited['status'], 'OBSERVATION_FINISHED')
        self.assertFalse(summary['inspection_outer_exit']['accepted'])
        self.assertTrue(status['compact_final_status'])

    def test_owner_wait_timeout_writes_bounded_final_receipts(self):
        code, exited, summary, status = self.run_fixture(execution=False)
        self.assertEqual(code, 2)
        self.assertIn('launch-wait deadline', summary['errors'][0])
        self.assertEqual(status['phase'], 'FINISHED')

    def test_status_and_summary_caps_still_write_compact_exit(self):
        code, exited, summary, status = self.run_fixture(oversized=True)
        self.assertEqual(code, 2)
        self.assertTrue(summary['full_process_summary_omitted_for_bound'])
        self.assertTrue(status['compact_final_status'])
        self.assertLess(len(json.dumps(exited)), 16 << 10)


class PreflightBinding(unittest.TestCase):
    def fixture(self, mutate=None, live=False, work=False):
        public = {'schema': 1, 'status': 'PREFLIGHT_READY', 'inspection_session': {
            'guard_work': '/data/local/tmp/pixel-firstboot-guard-e9cc754-resume1'}}
        startup = {'schema': 1, 'command': M.COMMAND, 'wrapper': {'pid': 10, 'starttime': 100},
                   'runner': {'pid': 11, 'starttime': 110}, 'started_utc': 'fixture'}
        exited = dict(startup, finished_utc='fixture-end', accepted=True, exit_code=0, owner_exit_code=0,
                      runner_started=True, runner_reaped=True, forced_runner=False, wrapper_error=None,
                      cleanup_errors=[], stdout_sha256='a' * 64)
        if mutate:
            mutate(exited)
        def read_json(path):
            value = {'preflight.json': public, 'preflight-owner.json': startup,
                     'preflight-exit.json': exited, 'preflight-command.json': M.COMMAND}[path.name]
            return value, {'path': str(path), 'bytes': 9070 if path.name == 'preflight.json' else 100,
                           'sha256': 'a' * 64 if path.name == 'preflight.json' else 'b' * 64}
        source = b'fixture source'
        source_pin = {'bytes': len(source), 'sha256': M.sha(source)}
        proc = FakeProc([row(11)] if live else [])
        with patch.object(M.os, 'geteuid', return_value=0), patch.object(M.Path, 'resolve', lambda p, strict=False: p), \
             patch.object(M, 'file_bytes', return_value=source), patch.object(M, 'OWNER_SOURCE_PIN', source_pin), \
             patch.object(M, 'read_json', side_effect=read_json), patch.object(M.os.path, 'lexists', side_effect=lambda p: work and p == M.WORK):
            return M.prerequisites('a' * 64, 9070, proc)

    def test_actual_accepted_preflight_binds_five_ordinary_inputs(self):
        bound = self.fixture()
        self.assertEqual(len(bound['bound_inputs']), 5)
        self.assertEqual(bound['preflight']['bytes'], 9070)

    def test_rejected_preflight_cannot_release_observer(self):
        with self.assertRaisesRegex(ValueError, 'preflight has not accepted'):
            self.fixture(lambda exited: exited.update(accepted=False))

    def test_unreaped_preflight_identity_cannot_release_observer(self):
        with self.assertRaisesRegex(ValueError, 'preflight process remains'):
            self.fixture(live=True)

    def test_existing_inspection_work_cannot_release_observer(self):
        with self.assertRaisesRegex(ValueError, 'work already exists'):
            self.fixture(work=True)


class NumericDiscovery(unittest.TestCase):
    def write_stat(self, root, pid, parent, start=None, comm='fixture'):
        directory = root / str(pid)
        directory.mkdir()
        fields = ['S', str(parent), '1', '1'] + ['0'] * 16
        fields[17], fields[19] = '1', str(start or pid * 10)
        (directory / 'stat').write_text(f'{pid} ({comm}) ' + ' '.join(fields))

    def test_numeric_cache_discards_unrelated_names_and_reuses_single_scan(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_stat(root, 10, 1)
            self.write_stat(root, 11, 10)
            self.write_stat(root, 12, 1, comm='unrelated-private-name')
            (root / 'version').write_text('not a process')
            proc = M.Proc(root)
            scan = proc.refresh_discovery(force=True)
            self.assertEqual(scan['numeric_entries'], 3)
            self.assertEqual(set(proc.relations[12]), {'pid', 'start_ticks', 'ppid'})
            self.assertNotIn('unrelated-private-name', repr(proc.relations) + repr(scan))
            self.assertEqual(proc.children({'pid': 10, 'start_ticks': 100}), [{'pid': 11, 'start_ticks': 110}])
            self.assertIsNone(proc.refresh_discovery())
            self.assertEqual(proc.scan_count, 1)

    def test_stale_child_start_cannot_inherit_cached_parent_edge(self):
        proc = FakeProc([row(10), row(11, start=999, ppid=10)])
        proc.children = lambda parent: [{'pid': 11, 'start_ticks': 110}] if parent['pid'] == 10 else []
        events = []
        graph = M.Graph(proc, lambda kind, **v: events.append({'kind': kind, **v}), {'pid': 99, 'start_ticks': 990})
        graph.anchor({'pid': 10, 'start_ticks': 100}, 'inspector')
        graph.sample()
        self.assertNotIn((11, 999), graph.rows)
        self.assertTrue(any('identity changed' in e.get('error', '') for e in events))

    def test_numeric_entry_bound_and_disappearing_stat_are_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_stat(root, 10, 1)
            (root / '11').mkdir()
            proc = M.Proc(root)
            scan = proc.refresh_discovery(force=True)
            self.assertEqual(scan['failures']['vanished'], 1)
            self.assertFalse(scan['complete_at_sampling_times'])
            with patch.dict(M.BOUNDS, {'proc_numeric_entries': 1}):
                with self.assertRaisesRegex(M.BoundExceeded, 'numeric entry'):
                    proc.refresh_discovery(force=True)

    def test_discovery_read_and_elapsed_bounds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_stat(root, 10, 1)
            proc = M.Proc(root)
            with patch.dict(M.BOUNDS, {'discovery_read_bytes': 1}):
                with self.assertRaisesRegex(M.BoundExceeded, 'byte bound'):
                    proc.refresh_discovery(force=True)
            with patch.object(M.time, 'monotonic_ns', side_effect=[1, 2000000001]):
                with self.assertRaisesRegex(M.BoundExceeded, 'duration bound'):
                    proc.refresh_discovery(force=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
