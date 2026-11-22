"""Synthetic receipt and tiny-child tests; no phone, VM, disk image or GPU."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


class OwnerTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('saved_owner_fixture', HERE / 'run_saved_inspection_owner_UNRELEASED.py')
        self.m = m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        self.tmp = tempfile.TemporaryDirectory(prefix='saved-')
        self.addCleanup(self.tmp.cleanup)
        self.root = root = Path(self.tmp.name)
        m.BASE, m.PREP, m.RUNNER, m.INSPECTOR, m.GUARD_WORK = [root / n for n in ('base', 'prep', 'runner', 'inspector', 'guard')]
        m.WORK = root / 'work'
        m.OWNER = m.BASE / 'owner'
        m.FIRSTBOOT_OWNER = m.BASE / 'firstboot'
        m.FIRSTBOOT_SOURCE = m.BASE / 'firstboot-owner.py'
        m.FIRSTBOOT_ADAPTER = m.BASE / 'adapter.py'
        m.GUARD_SOURCE = root / 'guard.py'
        m.FIRSTBOOT_COMMAND = ['synthetic-firstboot-adapter', '--execute']
        for p in (m.BASE, m.PREP, m.RUNNER, m.INSPECTOR, m.GUARD_WORK, m.FIRSTBOOT_OWNER,
                  m.PREP / 'checkpoints', m.PREP / 'attempts', m.PREP / 'attempts/07-0004'):
            p.mkdir()
        (m.PREP / 'owner.lock').touch()
        m.SOURCE_HASHES = {}
        sources = [m.GUARD_SOURCE,
                   *(m.INSPECTOR / n for n in ('inspect_ios26_firstboot.py', 'inspect_ios26_firstboot_guest.py')),
                   *(m.RUNNER / n for n in ('prepare_ios26.py', 'prepare_ios26_stages.py', 'cold_boot_ios26.py', 'cold_boot_dt.py'))]
        for path in sources + [m.FIRSTBOOT_SOURCE, m.FIRSTBOOT_ADAPTER]:
            path.write_text('# Synthetic source ' + path.name + '\n')
            if path in sources:
                m.SOURCE_HASHES[path] = m.sha(path.read_bytes())
        session = {'fixture': 'saved-firstboot-owner'}
        m.SESSION_DIGEST = m.digest(session)
        save(m.PREP / 'session.json', session)
        previous = None
        for i, stage in enumerate(m.STAGES):
            record = {'schema': 1, 'status': 'STAGE_COMPLETE', 'stage': stage,
                      'session_sha256': m.SESSION_DIGEST, 'previous_sha256': previous,
                      'attempt': str(m.PREP / 'attempts' / ('07-0004' if stage == 'ios26-firstboot' else '%02d-0001' % i))}
            path = m.PREP / 'checkpoints' / (stage + '.json')
            save(path, record)
            previous = m.sha(path.read_bytes())
        attempt = m.PREP / 'attempts/07-0004'
        files = {}
        for name in ('stage-inputs.json', 'launch.json', 'vm-result.json', 'stage-result.json'):
            path = attempt / name
            save(path, {'synthetic': name})
            files[name] = {'bytes': path.stat().st_size, 'sha256': m.sha(path.read_bytes())}
        self.first = {'schema': 1, 'started_utc': 'synthetic-start', 'command': m.FIRSTBOOT_COMMAND,
                      'wrapper': {'pid': 999999990, 'starttime': 1}, 'guard': {'pid': 999999991, 'starttime': 2}}
        save(m.FIRSTBOOT_OWNER / 'owner.json', self.first)
        save(m.FIRSTBOOT_OWNER / 'command.json', m.FIRSTBOOT_COMMAND)
        save(m.GUARD_WORK / 'guard-session.json', {'synthetic': 'accepted session'})
        save(m.GUARD_WORK / 'guard-observations.json', {'synthetic': 'accepted observations'})
        self.guard = {'schema': 1, 'status': 'GUARDED_FIRSTBOOT_COMPLETE', 'checkpoint_accepted_by_guard': True,
                      'bound_inputs_unchanged': True, 'original_firstboot_checkpoint_present': True,
                      'actual_attempt': {'attempt': str(attempt), 'files': files},
                      'checkpoint': {'path': str(m.PREP / 'checkpoints/ios26-firstboot.json'), 'sha256': previous},
                      'boot_complete': False, 'gpu_path_complete': False, 'app_gate_changed': False}
        save(m.GUARD_WORK / 'result.json', self.guard)
        self.exited = dict(self.first, finished_utc='synthetic-finish', exit_code=0, owner_exit_code=0, accepted=True,
                           guard_started=True, guard_reaped=True, forced_guard=False, wrapper_error=None, cleanup_errors=[],
                           acceptance={'attempt': str(attempt), 'result_sha256': m.sha((m.GUARD_WORK / 'result.json').read_bytes()),
                                       'checkpoint_sha256': previous,
                                       'guard_session_file_sha256': m.sha((m.GUARD_WORK / 'guard-session.json').read_bytes()),
                                       'guard_observations_sha256': m.sha((m.GUARD_WORK / 'guard-observations.json').read_bytes())})
        save(m.FIRSTBOOT_OWNER / 'exit.json', self.exited)
        self.pin_all()
        self.uid = mock.patch.object(m.os, 'geteuid', return_value=0)
        self.uid.start()
        self.addCleanup(self.uid.stop)
        self.current = m.prerequisites()
        self.public = {'schema': 1, 'status': 'PREFLIGHT_READY', 'boot_complete': False,
                       'gpu_path_complete': False, 'app_gate_changed': False, 'inspection_session': {
            'schema': 1, 'kind': 'ios26_saved_firstboot_inspection', 'prep_work': str(m.PREP), 'runner_dir': str(m.RUNNER),
            'prep_session_sha256': self.current['inputs'][str(m.PREP / 'session.json')], 'checkpoints': self.current['checkpoints'],
            'guard_files': self.current['guard_files'], 'guard_work': str(m.GUARD_WORK), 'guard_source': str(m.GUARD_SOURCE),
            'guard_source_sha256': m.SOURCE_HASHES[m.GUARD_SOURCE], 'source_directory': str(m.INSPECTOR),
            'inspector_sources': {p.name: h for p, h in m.SOURCE_HASHES.items() if p.parent == m.INSPECTOR},
            'frozen_sources': {p.name: h for p, h in m.SOURCE_HASHES.items() if p.parent == m.RUNNER},
            'readonly': True, 'native_required': True, 'tcg_retry': False, 'mounts_allowed': False,
            'replay_allowed': False, 'repair_allowed': False, 'boot_complete': False, 'gpu_path_complete': False, 'app_gate_changed': False,
            'helper_ram_mib': 2048, 'bounds': {'helper_seconds': 7200, 'max_log_mib': 64, 'min_free_mib': 1536, 'min_available_mib': 512},
            'backing_chain': [{'synthetic': 'saved'}, {'synthetic': 'predecessor'}]}}
        save(root / 'public.json', self.public)
        stub = root / 'stub.py'
        stub.write_text('import pathlib,sys\np=pathlib.Path(__file__).parent\nwith (p/"calls").open("a") as f: f.write(str("--execute" in sys.argv)+"\\n")\nprint((p/"public.json").read_text())\n')
        m.COMMAND = [sys.executable, '-I', '-B', str(stub)]

    def pin_all(self):
        m = self.m
        m.FIRSTBOOT_SUCCESS_PINS = {s: {'bytes': Path(s).stat().st_size, 'sha256': m.sha(Path(s).read_bytes())}
                                   for s in m.expected_success_paths()}

    def invoke(self, argv):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            result = self.m.main(argv)
        return result, output.getvalue()

    def preflight(self):
        code, output = self.invoke(['--preflight'])
        self.assertEqual(code, 0, output)
        # main() is called in this test process; represent the separate exited
        # outer wrapper used by actual detached phase invocations.
        for name in ('preflight-owner.json', 'preflight-exit.json'):
            value = self.m.read_json(self.m.OWNER / name)
            value['wrapper'] = {'pid': 999999992, 'starttime': 3}
            save(self.m.OWNER / name, value)
        body = (self.m.OWNER / 'preflight.json').read_bytes()
        return ['--execute', '--preflight-sha256', self.m.sha(body), '--preflight-bytes', str(len(body))]

    def test_unreleased_refuses_without_output_creation(self):
        self.m.FIRSTBOOT_SUCCESS_PINS = None
        code, output = self.invoke(['--preflight'])
        self.assertEqual(code, 2)
        self.assertIn('unreleased', output)
        self.assertFalse(self.m.OWNER.exists())
        self.assertFalse(self.m.WORK.exists())

    def test_valid_metadata_preflight_stays_read_only(self):
        self.assertEqual(self.m.prerequisites(), self.current)
        self.m.validate_preflight(self.public, self.current)
        self.assertFalse(self.m.WORK.exists())

    def test_changed_firstboot_source_refuses(self):
        self.m.FIRSTBOOT_SOURCE.write_text('changed\n')
        with self.assertRaisesRegex(ValueError, 'changed bound input'):
            self.m.prerequisites()

    def test_rebound_nonaccepted_owner_still_refuses(self):
        self.exited['accepted'] = False
        save(self.m.FIRSTBOOT_OWNER / 'exit.json', self.exited)
        self.pin_all()
        with self.assertRaisesRegex(ValueError, 'has not accepted'):
            self.m.prerequisites()

    def test_wrong_attempt_still_refuses(self):
        self.guard['actual_attempt']['attempt'] = str(self.m.PREP / 'attempts/07-0003')
        save(self.m.GUARD_WORK / 'result.json', self.guard)
        self.pin_all()
        with self.assertRaisesRegex(ValueError, 'actual 07-0004'):
            self.m.prerequisites()

    def test_live_old_wrapper_refuses(self):
        with mock.patch.object(self.m, 'identity', return_value=self.first['wrapper']):
            with self.assertRaisesRegex(ValueError, 'still present'):
                self.m.prerequisites()

    def test_preflight_child_cleanly_reaped(self):
        self.preflight()
        exited = self.m.read_json(self.m.OWNER / 'preflight-exit.json')
        self.assertTrue(exited['accepted'])
        self.assertTrue(exited['runner_reaped'])
        self.assertFalse(exited['forced_runner'])
        self.assertEqual(exited['cleanup_errors'], [])
        self.assertEqual((self.root / 'calls').read_text(), 'False\n')
        self.assertFalse(self.m.WORK.exists())

    def test_bad_preflight_is_preserved_and_unaccepted(self):
        self.public['status'] = 'INCOMPLETE'
        save(self.root / 'public.json', self.public)
        code, _ = self.invoke(['--preflight'])
        self.assertEqual(code, 2)
        exited = self.m.read_json(self.m.OWNER / 'preflight-exit.json')
        self.assertFalse(exited['accepted'])
        self.assertTrue(exited['runner_reaped'])
        self.assertTrue((self.m.OWNER / 'preflight.json').exists())
        self.assertFalse(self.m.WORK.exists())

    def test_missing_actual_preflight_pin_refuses_execute(self):
        self.preflight()
        code, output = self.invoke(['--execute'])
        self.assertEqual(code, 2)
        self.assertIn('actual observed preflight', output)
        self.assertFalse((self.m.OWNER / 'command.json').exists())

    def test_wrong_actual_preflight_pin_refuses_execute(self):
        args = self.preflight()
        args[2] = '0' * 64
        code, output = self.invoke(args)
        self.assertEqual(code, 2)
        self.assertIn('pin differs', output)
        self.assertFalse((self.m.OWNER / 'command.json').exists())

    def test_correct_pin_can_spawn_once_with_mocked_result_validation(self):
        args = self.preflight()
        with mock.patch.object(self.m, 'resources'), mock.patch.object(self.m, 'accept_result', return_value='synthetic-result'):
            code, output = self.invoke(args)
        self.assertEqual(code, 0, output)
        exited = self.m.read_json(self.m.OWNER / 'exit.json')
        self.assertTrue(exited['accepted'])
        self.assertTrue(exited['runner_reaped'])
        self.assertEqual((self.root / 'calls').read_text(), 'False\nTrue\n')
        with mock.patch.object(self.m, 'resources'), mock.patch.object(self.m, 'accept_result', return_value='synthetic-result'):
            code, _ = self.invoke(args)
        self.assertEqual(code, 2)
        self.assertEqual((self.root / 'calls').read_text(), 'False\nTrue\n')

    def successful_inspection_fixture(self):
        m = self.m
        m.OWNER.mkdir()
        save(m.OWNER / 'preflight.json', self.public)
        m.WORK.mkdir()
        attempt = m.WORK / 'a1'
        attempt.mkdir()
        returned = attempt / 'files/inspection'
        returned.mkdir(parents=True)
        guest = {'status': 'SAVED_FIRSTBOOT_INSPECTION_PASSED', 'errors': [], 'cleanup_errors': [],
                 'raw_metadata_unchanged': True, 'readonly_attachments': True,
                 'mounted': False, 'replayed': False, 'repaired': False}
        save(returned / 'result.json', guest)
        for name in ('fsck-system.txt', 'fsck-data.txt'):
            (returned / name).write_text('Synthetic complete accepted filesystem diagnostic\n')
        outputs = {}
        for path in returned.iterdir():
            outputs['inspection/' + path.name] = {'path': path.relative_to(m.WORK).as_posix(),
                                                   'bytes': path.stat().st_size, 'sha256': m.sha(path.read_bytes())}
        expected = self.public['inspection_session']
        save(m.WORK / 'inspection-session.json', expected)
        save(attempt / 'vm.child.json', {'pid': 999999993, 'start_ticks': 4})
        result = {'schema': 1, 'status': 'SAVED_FIRSTBOOT_INSPECTION_PASSED',
                  'inspection_session_sha256': m.digest(expected), 'full_backing_chain_unchanged': True,
                  'preparation_and_guard_unchanged': True, 'natural_exit': True,
                  'native_witnesses': {'native_initialization': True, 'native_execution': True, 'fatal_markers': []},
                  'cleanup': {'exit_code': 0, 'echild': True, 'forced_qemu': False, 'forced_descendants': [], 'errors': []},
                  'boot_complete': False, 'gpu_path_complete': False, 'app_gate_changed': False,
                  'outputs': outputs, 'guest_result': guest}
        save(m.WORK / 'result.json', result)
        return result

    def test_accept_result_requires_clean_unchanged_saved_files(self):
        self.successful_inspection_fixture()
        self.assertEqual(self.m.accept_result(self.current), self.m.sha((self.m.WORK / 'result.json').read_bytes()))
        (self.m.WORK / 'a1/files/inspection/fsck-system.txt').write_text('Changed\n')
        with self.assertRaisesRegex(ValueError, 'returned file differs'):
            self.m.accept_result(self.current)

    def test_accept_result_rejects_forced_cleanup(self):
        value = self.successful_inspection_fixture()
        value['cleanup']['forced_qemu'] = True
        save(self.m.WORK / 'result.json', value)
        with self.assertRaisesRegex(ValueError, 'complete unchanged native'):
            self.m.accept_result(self.current)

    def test_accept_result_rejects_changed_firstboot(self):
        self.successful_inspection_fixture()
        self.m.FIRSTBOOT_SOURCE.write_text('Changed\n')
        with self.assertRaisesRegex(ValueError, 'bound firstboot/source/checkpoint changed'):
            self.m.accept_result(self.current)


if __name__ == '__main__':
    unittest.main()
