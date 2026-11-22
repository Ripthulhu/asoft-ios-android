"""Focused offline checks for the independent observer execution boundary.

Synthetic receipts and mocked /proc/Popen only; no phone, VM or guest execution.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'launch_saved_inspection_execution.py'


def sha(body):
    return hashlib.sha256(body).hexdigest()


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        spec = importlib.util.spec_from_file_location('execution_candidate', SOURCE)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        m, base = self.m, Path(self.tmp.name)
        for name, path in {
            'BASE': base, 'SOURCE': base / 'owner.py', 'INSTALL': base / 'install.json',
            'LAUNCH': base / 'execute-launch.json', 'LOG': base / 'execute.log',
            'OWNER': base / 'owner', 'WORK': base / 'new-work',
            'MONITOR_SOURCE': base / 'observer.py', 'MONITOR_OUT': base / 'observer',
            'MONITOR_LAUNCH': base / 'observer-launch.json', 'PREP_SESSION': base / 'session.json',
        }.items():
            setattr(m, name, path)
        m.OWNER.mkdir()
        m.MONITOR_OUT.mkdir()
        m.SOURCE.write_bytes(b'# synthetic owner source\n')
        m.SOURCE_BYTES, m.SOURCE_SHA256 = m.SOURCE.stat().st_size, sha(m.SOURCE.read_bytes())
        m.MONITOR_SOURCE.write_bytes(b'# synthetic observer source\n')
        m.MONITOR_PIN = {'bytes': m.MONITOR_SOURCE.stat().st_size, 'sha256': sha(m.MONITOR_SOURCE.read_bytes())}
        self.identity = {'pid': 101, 'start_ticks': 12345}
        self.process_row = {'pid': 101, 'start_ticks': 12345, 'ppid': 1, 'pgrp': 101, 'session': 101, 'state': 'S'}
        self.live = {'pid': 101, 'starttime': 12345, 'parent_pid': 1, 'process_group': 101, 'session': 101, 'state': 'S'}
        self.source_pin = {'path': str(m.MONITOR_SOURCE), **m.MONITOR_PIN}
        self.owner_source = {'path': str(m.SOURCE), 'bytes': m.SOURCE_BYTES, 'sha256': m.SOURCE_SHA256}
        self.inspector_command = [m.PYTHON, '-I', '-B', '/unchanged/inspector.py', '--guard-work', '/accepted/resume1', '--work', str(m.WORK)]
        self.write(m.PREP_SESSION, {'package': str(base / 'qualified-runtime')})
        self.write(m.OWNER / 'prerequisites.json', {'inputs': {str(m.PREP_SESSION): sha(m.PREP_SESSION.read_bytes())}})
        self.write(m.OWNER / 'preflight-command.json', self.inspector_command)
        self.accepted = {'metadata_sha256': {
            str(m.OWNER / 'prerequisites.json'): sha((m.OWNER / 'prerequisites.json').read_bytes()),
            str(m.OWNER / 'preflight-command.json'): sha((m.OWNER / 'preflight-command.json').read_bytes()),
            str(m.OWNER / 'preflight-exit.json'): 'e' * 64,
        }}
        self.preflight = {'path': str(m.OWNER / 'preflight.json'), 'bytes': m.PREFLIGHT_BYTES,
                          'sha256': m.PREFLIGHT_SHA256, 'exit_sha256': 'e' * 64}
        self.scope = {'inspection_owner_directory': str(m.OWNER), 'inspection_work': str(m.WORK),
            'inspection_command': self.inspector_command + ['--execute'],
            'qemu_child_record': str(m.WORK / 'a1/vm.child.json'),
            'qemu_executable': str(base / 'qualified-runtime/qemu-system-aarch64'),
            'native_factory_name': 'asoft-stubfac', 'native_worker_name_pattern': '^asoft-stub[0-9]+$', 'metadata_only': True,
            'discovery_method': 'bounded_numeric_proc_stat'}
        self.now = 1_000_000_000_000
        self.ready = {'schema': 1, 'kind': 'saved_inspection_process_observer_ready', 'status': 'READY',
            'ready_utc': 'synthetic', 'ready_monotonic_ns': self.now - 30_000_000_000,
            'observer': self.identity, 'observer_process': self.process_row, 'source': self.source_pin,
            'output_directory': str(m.MONITOR_OUT), 'scope': self.scope, 'bounds': copy.deepcopy(m.MONITOR_BOUNDS),
            'inspection_owner_source': self.owner_source, 'preflight': self.preflight,
            'discovery_probe': {'method': 'bounded_numeric_proc_stat', 'self_identity_verified': True, 'unrelated_metadata_exported': False,
                'scan': {'directory_entries': 950, 'numeric_entries': 900, 'readable_entries': 898, 'read_bytes': 250000, 'duration_ms': 70.1}},
            'independent_session': True, 'target_execution_absent_at_ready': True, 'diagnostic_only': True}
        self.args = argparse.Namespace(monitor_ready_sha256='', monitor_ready_bytes=0, monitor_pid=101, monitor_start_ticks=12345)
        self.pin_ready()
        self.heartbeat = {'schema': 1, 'kind': 'saved_inspection_process_observer_status', 'status': 'RUNNING',
            'phase': 'WAITING_FOR_EXECUTION_OWNER', 'heartbeat_utc': 'synthetic',
            'heartbeat_monotonic_ns': self.now - 1_000_000_000,
            'observer': self.identity, 'source_sha256': m.MONITOR_PIN['sha256'], 'ready_sha256': self.args.monitor_ready_sha256,
            'output_directory': str(m.MONITOR_OUT), 'scope': self.scope, 'diagnostic_only': True}
        self.write(m.MONITOR_OUT / 'status.json', self.heartbeat)
        self.observer_command = [m.PYTHON, '-I', '-B', str(m.MONITOR_SOURCE), '--preflight-sha256', m.PREFLIGHT_SHA256,
                                 '--preflight-bytes', str(m.PREFLIGHT_BYTES)]
        self.launched = {'schema': 1, 'kind': 'detached_saved_inspection_process_observer', 'status': 'PROCESS_OBSERVER_LAUNCHED',
            'command': self.observer_command, 'observer': self.process_row, 'source': self.source_pin,
            'preflight': self.preflight, 'inspection_owner_source': self.owner_source, 'output_directory': str(m.MONITOR_OUT),
            'start_new_session': True, 'diagnostic_only': True, 'inspection_execution_requested': False, 'finished_utc': 'synthetic'}
        self.write(m.MONITOR_LAUNCH, self.launched)
        self.write(m.INSTALL, {'schema': 1, 'kind': 'saved_inspection_resume2_sources_install',
            'files': m.INSTALLED_FILES, 'manifest_sha256': m.TRANSFER_MANIFEST_SHA256, 'execution_started': False})
        for target, value in [('process', self.live), ('cmdline', self.observer_command)]:
            patch = mock.patch.object(m, target, return_value=value)
            setattr(self, target + '_mock', patch.start())
            self.addCleanup(patch.stop)
        patch = mock.patch.object(m.time, 'monotonic_ns', return_value=self.now)
        patch.start()
        self.addCleanup(patch.stop)

    def write(self, path, value):
        path.write_text(json.dumps(value, sort_keys=True) + '\n')

    def pin_ready(self):
        self.write(self.m.MONITOR_OUT / 'ready.json', self.ready)
        body = (self.m.MONITOR_OUT / 'ready.json').read_bytes()
        self.args.monitor_ready_bytes, self.args.monitor_ready_sha256 = len(body), sha(body)
        if hasattr(self, 'heartbeat'):
            self.heartbeat['ready_sha256'] = self.args.monitor_ready_sha256
            self.write(self.m.MONITOR_OUT / 'status.json', self.heartbeat)

    def check(self):
        return self.m.checked_monitor(self.args, self.accepted)

    def test_valid_independent_observer_and_reparenting_are_accepted(self):
        self.ready['observer_process']['ppid'] = 999
        self.pin_ready()
        result = self.check()
        self.assertEqual(result['ready']['sha256'], self.args.monitor_ready_sha256)
        self.assertEqual(result['observer_process']['parent_pid'], 1)
        self.assertEqual(result['heartbeat_age_ns'], 1_000_000_000)
        self.assertEqual(self.process_mock.call_count, 2)

    def test_unobserved_or_changed_ready_bytes_are_rejected(self):
        self.args.monitor_ready_sha256 = '0' * 64
        with self.assertRaisesRegex(ValueError, 'ready bytes differ'):
            self.check()

    def test_repinning_wrong_scope_or_preflight_does_not_bypass_gate(self):
        for field, changed in [('scope', dict(self.scope, inspection_work='/wrong')),
                               ('preflight', dict(self.preflight, exit_sha256='a' * 64)),
                               ('bounds', dict(self.m.MONITOR_BOUNDS, total_seconds=999999)),
                               ('discovery_probe', {'method': 'bounded_numeric_proc_stat', 'self_identity_verified': False, 'unrelated_metadata_exported': False})]:
            with self.subTest(field=field):
                original = self.ready[field]
                self.ready[field] = changed
                self.pin_ready()
                with self.assertRaisesRegex(ValueError, 'READY contract'):
                    self.check()
                self.ready[field] = original
                self.pin_ready()

    def test_excessive_or_missing_discovery_probe_bounds_are_rejected(self):
        original = copy.deepcopy(self.ready['discovery_probe'])
        for field, value in [('directory_entries', 4097), ('numeric_entries', 2049), ('read_bytes', 4194305),
                             ('readable_entries', 0), ('duration_ms', 1000.1), ('duration_ms', -1)]:
            with self.subTest(field=field, value=value):
                self.ready['discovery_probe'] = copy.deepcopy(original)
                self.ready['discovery_probe']['scan'][field] = value
                self.pin_ready()
                with self.assertRaisesRegex(ValueError, 'READY contract'):
                    self.check()
        self.ready['discovery_probe'] = {'method': 'task_children_file', 'self_identity_verified': True}
        self.pin_ready()
        with self.assertRaisesRegex(ValueError, 'READY contract'):
            self.check()

    def test_changed_bound_session_or_source_is_rejected(self):
        self.m.PREP_SESSION.write_text('{"package":"/wrong"}')
        with self.assertRaisesRegex(ValueError, 'preparation session changed'):
            self.check()
        self.m.MONITOR_SOURCE.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'observer source differs'):
            self.check()

    def test_reused_zombie_or_wrong_session_pid_is_rejected(self):
        for changed in [dict(self.live, starttime=54321), dict(self.live, state='Z'), dict(self.live, state='T'), dict(self.live, state='t'), dict(self.live, session=1)]:
            with self.subTest(changed=changed):
                self.process_mock.return_value = changed
                with self.assertRaisesRegex(ValueError, 'PID was reused'):
                    self.check()

    def test_wrong_live_command_is_rejected(self):
        self.cmdline_mock.return_value = [self.m.PYTHON, '/other-observer.py']
        with self.assertRaisesRegex(ValueError, 'command line differs'):
            self.check()

    def test_identity_change_during_validation_is_rejected(self):
        self.process_mock.side_effect = [self.live, dict(self.live, starttime=54321)]
        with self.assertRaisesRegex(ValueError, 'identity changed during'):
            self.check()

    def test_stale_future_and_expiring_heartbeats_are_rejected(self):
        for age, ready_age in [(6_000_000_000, 30_000_000_000), (-1, 30_000_000_000),
                               (1_000_000_000, 596_000_000_000)]:
            with self.subTest(age=age, ready_age=ready_age):
                self.ready['ready_monotonic_ns'] = self.now - ready_age
                self.pin_ready()
                self.heartbeat['heartbeat_monotonic_ns'] = self.now - age
                self.write(self.m.MONITOR_OUT / 'status.json', self.heartbeat)
                with self.assertRaisesRegex(ValueError, 'heartbeat is stale'):
                    self.check()

    def test_finished_observer_is_rejected(self):
        self.write(self.m.MONITOR_OUT / 'exit.json', {'status': 'finished'})
        with self.assertRaisesRegex(ValueError, 'already finished'):
            self.check()

    def test_nonwaiting_heartbeat_or_mismatched_launch_is_rejected(self):
        self.heartbeat['phase'] = 'OBSERVING'
        self.write(self.m.MONITOR_OUT / 'status.json', self.heartbeat)
        with self.assertRaisesRegex(ValueError, 'heartbeat contract'):
            self.check()
        self.launched['observer'] = dict(self.process_row, start_ticks=987)
        self.write(self.m.MONITOR_LAUNCH, self.launched)
        with self.assertRaisesRegex(ValueError, 'recorded observer identity'):
            self.check()

    def test_unreleased_source_refuses_before_any_file_read(self):
        self.m.MONITOR_PIN = None
        with mock.patch.object(self.m, 'read') as read:
            with self.assertRaisesRegex(ValueError, 'UNRELEASED'):
                self.m.launch(self.args)
        read.assert_not_called()
        self.assertFalse(self.m.LAUNCH.exists())

    def test_bad_ready_refuses_before_execution_artifacts_or_popen(self):
        self.args.monitor_ready_sha256 = '0' * 64
        with mock.patch.object(self.m, 'checked_preflight', return_value=self.accepted), \
                mock.patch.object(self.m.os, 'geteuid', return_value=0), \
                mock.patch.object(self.m.subprocess, 'Popen') as popen:
            with self.assertRaisesRegex(ValueError, 'ready bytes differ'):
                self.m.launch(self.args)
        popen.assert_not_called()
        self.assertFalse(self.m.LAUNCH.exists())
        self.assertFalse(self.m.LOG.exists())

    def test_second_readiness_failure_preserves_receipt_without_popen(self):
        proof = self.check()
        with mock.patch.object(self.m, 'checked_preflight', return_value=self.accepted), \
                mock.patch.object(self.m.os, 'geteuid', return_value=0), \
                mock.patch.object(self.m, 'checked_monitor', side_effect=[proof, ValueError('observer no longer ready')]), \
                mock.patch.object(self.m.subprocess, 'Popen') as popen:
            result = self.m.launch(self.args)
        popen.assert_not_called()
        self.assertEqual(result['status'], 'LAUNCH_INCOMPLETE')
        self.assertIsNone(result['wrapper'])
        self.assertEqual(json.loads(self.m.LAUNCH.read_text())['process_observer_evidence'], proof)


if __name__ == '__main__':
    unittest.main(verbosity=2)
