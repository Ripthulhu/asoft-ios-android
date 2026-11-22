"""Focused owner tests using synthetic metadata and a tiny Python child only.

No phone paths, auditor module, package, firmware, QEMU, or GPU is executed.
"""
import contextlib
import fcntl
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import unittest
from unittest import mock

STAGING = Path(__file__).resolve().parent


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


class OwnerTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('audit_owner_fixture', STAGING / 'run_partition_audit.py')
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        m = self.m
        self.root = STAGING / 't'
        self.root.mkdir()
        self.addCleanup(shutil.rmtree, self.root)
        m.BASE, m.PREP, m.RUNNER, m.AUDITOR, m.WORK = [self.root / p for p in ('b', 'p', 'r', 'a', 'w')]
        m.WORK = STAGING / 'w'
        self.addCleanup(lambda: shutil.rmtree(m.WORK) if m.WORK.exists() else None)
        m.OWNER, m.PREVIOUS = m.BASE / 'new', m.BASE / 'old'
        for p in (m.BASE, m.PREP, m.RUNNER, m.AUDITOR, m.PREVIOUS, m.PREP / 'checkpoints', m.PREP / 'attempts'):
            p.mkdir()
        (m.PREP / 'owner.lock').touch()
        names = [(m.RUNNER, n) for n in ('prepare_ios26.py', 'prepare_ios26_stages.py', 'cold_boot_ios26.py', 'cold_boot_dt.py')]
        names += [(m.AUDITOR, n) for n in ('audit_ios26_partition.py', 'audit_ios26_partition_guest.py')]
        names += [(m.BASE, 'run-ios26-disks-retry-f4d64db.py')]
        m.SOURCE_HASHES = {}
        for folder, name in names:
            path = folder / name
            path.write_text('# Synthetic source: ' + name + '\n')
            m.SOURCE_HASHES[path] = m.sha(path.read_bytes())
        command = ['synthetic-previous-owner', '--execute']
        prior = {'schema': 1, 'started_utc': '2026-11-22T06:43:51+00:00', 'command': command,
                 'wrapper': {'pid': 999999991, 'starttime': 1}, 'runner': {'pid': 999999992, 'starttime': 2}}
        save(m.PREVIOUS / 'owner.json', prior)
        save(m.PREVIOUS / 'command.json', command)
        save(m.PREVIOUS / 'exit.json', dict(prior, finished_utc='2026-11-22T12:00:00+00:00',
             exit_code=0, runner_started=True, runner_reaped=True, forced_runner=False, wrapper_error=None, cleanup_errors=[]))
        m.PREVIOUS_OWNER_SHA = m.sha((m.PREVIOUS / 'owner.json').read_bytes())
        m.PREVIOUS_COMMAND_SHA = m.sha((m.PREVIOUS / 'command.json').read_bytes())
        session = {'fixture': 'seven completed stages'}
        m.SESSION_SHA = m.digest(session)
        save(m.PREP / 'session.json', session)
        previous = None
        self.cleanup = {'exit_code': 0, 'echild': True, 'forced_qemu': False, 'forced_descendants': [], 'errors': []}
        self.witnesses = {'native_initialization': True, 'native_execution': True, 'fatal_markers': []}
        for index, stage in enumerate(m.STAGES):
            attempt = m.PREP / 'attempts' / ('%02d-0001' % index)
            attempt.mkdir()
            record = {'schema': 1, 'status': 'STAGE_COMPLETE', 'stage': stage, 'session_sha256': m.SESSION_SHA,
                      'previous_sha256': previous, 'artifacts': {}, 'attempt': str(attempt)}
            path = m.PREP / 'checkpoints' / (stage + '.json')
            save(path, record)
            previous = m.sha(path.read_bytes())
            if stage in ('ios26-rootfs', 'ios26-partition'):
                save(attempt / 'vm-result.json', {'schema': 1, 'status': 'VM_OBSERVATION_COMPLETE', 'stage': stage,
                     'natural_exit': True, 'done_codes': [0], 'finished_utc': '2026-11-22T12:00:00+00:00',
                     'cleanup': self.cleanup, 'witnesses': self.witnesses})
        save(m.PREP / 'result.json', {'status': 'PREPARATION_CHECKPOINT', 'completed': m.STAGES,
             'stage': 'ios26-partition', 'finished_utc': '2026-11-22T12:00:00+00:00',
             'boot_complete': False, 'gpu_path_complete': False, 'app_gate_changed': False})
        self.uid = mock.patch.object(m.os, 'geteuid', return_value=0)
        self.uid.start()
        self.addCleanup(self.uid.stop)
        current = m.prerequisites()
        session = {'schema': 1, 'kind': 'standalone_ios26_partition_audit', 'prep_work': str(m.PREP),
                   'runner_dir': str(m.RUNNER), 'prep_session_sha256': current['inputs'][str(m.PREP / 'session.json')],
                   'checkpoints': current['checkpoints'], 'readonly': True, 'native_required': True, 'tcg_retry': False,
                   'auditor_sources': {p.name: h for p, h in m.SOURCE_HASHES.items() if p.parent == m.AUDITOR},
                   'frozen_runner_sources': {p.name: h for p, h in m.SOURCE_HASHES.items() if p.parent == m.RUNNER}}
        self.public = {'schema': 1, 'status': 'PREFLIGHT_READY', 'work': str(m.WORK), 'session': session,
                       'execution_verified': False, 'boot_complete': False, 'gpu_path_complete': False, 'app_gate_changed': False}
        save(self.root / 'public.json', self.public)
        save(self.root / 'accepted.json', {'schema': 1, 'status': 'PARTITION_AUDIT_PASSED',
             'session_sha256': m.digest(session), 'disk_unchanged': True, 'preparation_records_unchanged': True,
             'natural_exit': True, 'native_witnesses': self.witnesses, 'cleanup': self.cleanup,
             'boot_complete': False, 'gpu_path_complete': False, 'app_gate_changed': False})
        stub = self.root / 'stub.py'
        stub.write_text('''import json, pathlib, sys
p = pathlib.Path(__file__).parent
with (p / 'calls.txt').open('a') as f:
    f.write(('execute' if '--execute' in sys.argv else 'preflight') + '\\n')
public = json.loads((p / 'public.json').read_text())
if '--execute' in sys.argv:
    work = pathlib.Path(public['work'])
    work.mkdir()
    (work / 'audit-session.json').write_text(json.dumps(public['session']))
    (work / 'result.json').write_bytes((p / 'accepted.json').read_bytes())
    print((work / 'result.json').read_text())
else:
    print(json.dumps(public))
''')
        m.COMMAND = [sys.executable, '-B', str(stub)]

    def run_main(self, mode):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.m.main([mode])

    def complete_preflight(self):
        self.assertEqual(self.run_main('--preflight'), 0)
        # Model the completed preflight wrapper's absence at the next CLI call.
        for name in ('preflight-owner.json', 'preflight-exit.json'):
            path = self.m.OWNER / name
            value = self.m.read_json(path)
            value['wrapper'] = {'pid': 999999993, 'starttime': 3}
            save(path, value)

    def refuse_without_spawn(self, mode='--preflight'):
        with mock.patch.object(self.m.subprocess, 'Popen') as popen:
            self.assertEqual(self.run_main(mode), 2)
            popen.assert_not_called()

    def test_successful_two_phase_receipts_and_no_relaunch(self):
        self.complete_preflight()
        self.assertFalse(self.m.WORK.exists())
        self.assertEqual(self.run_main('--execute'), 0)
        receipt = self.m.read_json(self.m.OWNER / 'exit.json')
        self.assertTrue(receipt['accepted'])
        self.assertTrue(receipt['runner_reaped'])
        self.assertEqual(receipt['command'], self.m.COMMAND + ['--execute'])
        self.assertEqual((self.root / 'calls.txt').read_text(), 'preflight\nexecute\n')
        before = {p.name: p.read_bytes() for p in self.m.OWNER.iterdir()}
        self.refuse_without_spawn('--execute')
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.m.OWNER.iterdir()})

    def test_active_previous_identity_refuses(self):
        original = self.m.identity
        with mock.patch.object(self.m, 'identity', side_effect=lambda pid:
                {'pid': pid, 'starttime': 1} if pid == 999999991 else original(pid)):
            self.refuse_without_spawn()
        self.assertFalse(self.m.OWNER.exists())

    def test_partial_boundary_refuses(self):
        (self.m.PREP / 'checkpoints/ios26-partition.json').unlink()
        self.refuse_without_spawn()
        self.assertFalse(self.m.OWNER.exists())

    def test_prior_forced_cleanup_refuses(self):
        path = self.m.PREVIOUS / 'exit.json'
        value = self.m.read_json(path)
        value['forced_runner'] = True
        save(path, value)
        self.refuse_without_spawn()

    def test_partition_native_failure_refuses(self):
        path = self.m.PREP / 'attempts/06-0001/vm-result.json'
        value = self.m.read_json(path)
        value['witnesses']['native_execution'] = False
        save(path, value)
        self.refuse_without_spawn()

    def test_locked_preparation_refuses(self):
        with (self.m.PREP / 'owner.lock').open('rb') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.refuse_without_spawn()

    def test_unreaped_preparation_child_refuses(self):
        current = self.m.identity(os.getpid())
        save(self.m.PREP / 'attempts/06-0001/vm.child.json',
             {'pid': current['pid'], 'start_ticks': current['starttime']})
        self.refuse_without_spawn()

    def test_changed_source_refuses(self):
        (self.m.AUDITOR / 'audit_ios26_partition.py').write_text('# changed\n')
        self.refuse_without_spawn()

    def test_preflight_output_tampering_refuses_execution(self):
        self.complete_preflight()
        path = self.m.OWNER / 'preflight.json'
        path.write_text(path.read_text() + '\n')
        self.refuse_without_spawn('--execute')
        self.assertFalse(self.m.WORK.exists())

    def test_existing_receipt_directory_is_preserved(self):
        self.m.OWNER.mkdir()
        (self.m.OWNER / 'keep').write_bytes(b'preserve')
        self.refuse_without_spawn()
        self.assertEqual((self.m.OWNER / 'keep').read_bytes(), b'preserve')

    def test_failed_preflight_never_authorizes_execute(self):
        self.public['status'] = 'INCOMPLETE'
        save(self.root / 'public.json', self.public)
        self.assertEqual(self.run_main('--preflight'), 2)
        self.assertFalse(self.m.read_json(self.m.OWNER / 'preflight-exit.json')['accepted'])
        self.refuse_without_spawn('--execute')
        self.assertEqual((self.root / 'calls.txt').read_text(), 'preflight\n')

    def test_interruption_only_signals_and_reaps_direct_child(self):
        class Child:
            pid, returncode = 999999994, None

            def __init__(self):
                self.calls = []

            def wait(self, timeout=None):
                self.calls.append(('wait', timeout))
                if timeout is None:
                    raise InterruptedError('synthetic owner interruption')
                if timeout == 60:
                    raise subprocess.TimeoutExpired('synthetic', timeout)
                self.returncode = -9
                return self.returncode

            def poll(self):
                return self.returncode

            def send_signal(self, number):
                self.calls.append(('signal', number))

            def kill(self):
                self.calls.append(('kill', None))

        child = Child()
        self.m.OWNER.mkdir()
        with mock.patch.object(self.m.subprocess, 'Popen', return_value=child), \
             mock.patch.object(self.m, 'identity', side_effect=lambda pid: {'pid': pid, 'starttime': 1}):
            self.assertEqual(self.m.run_phase(True, {}), 2)
        self.assertEqual(child.calls, [('wait', None), ('signal', signal.SIGTERM), ('wait', 60),
                                       ('kill', None), ('wait', 30)])
        receipt = self.m.read_json(self.m.OWNER / 'exit.json')
        self.assertTrue(receipt['forced_runner'])
        self.assertTrue(receipt['runner_reaped'])
        self.assertFalse(receipt['accepted'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
