"""Focused synthetic proof/phase tests. No phone, image, VM or GPU is accessed."""
import contextlib
import copy
import fcntl
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'run_apps_prep_owner_UNRELEASED.py'


def load():
    spec = importlib.util.spec_from_file_location('apps_prep_fixture', SOURCE)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.m = m = load()
        self.tmp = tempfile.TemporaryDirectory(prefix='apps-prep-')
        self.addCleanup(self.tmp.cleanup)
        self.root = root = Path(self.tmp.name)
        for name in ('BASE', 'PREP', 'RUNNER', 'GUARD_WORK', 'INSPECTOR', 'INSPECTION', 'INSPECTION_OWNER', 'APPS'):
            path = root / name.lower()
            path.mkdir()
            setattr(m, name, path)
        m.OWNER = m.BASE / 'new-owner'
        m.APPS_WORK = root / 'new-apps-audit'
        m.APPS_INSTALL = m.BASE / 'apps-install.json'
        m.INSPECTION_SOURCE = m.BASE / 'inspection-owner.py'
        m.GUARD = root / 'guard.py'
        m.PARTITION_GUEST = root / 'partition-guest.py'
        for text in m.expected_success_paths():
            path = Path(text)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{}\n')
        self.startup = {'schema': 1, 'started_utc': 'synthetic-start', 'command': m.INSPECTION_COMMAND,
                        'wrapper': {'pid': 999999990, 'starttime': 1}, 'runner': {'pid': 999999991, 'starttime': 2}}
        save(m.INSPECTION_OWNER / 'command.json', m.INSPECTION_COMMAND)
        save(m.INSPECTION_OWNER / 'owner.json', self.startup)
        save(m.INSPECTION / 'result.json', {'schema': 1, 'status': 'SAVED_FIRSTBOOT_INSPECTION_PASSED'})
        self.exited = dict(self.startup, finished_utc='synthetic-finish', exit_code=0, owner_exit_code=0,
                           accepted=True, runner_started=True, runner_reaped=True, forced_runner=False,
                           wrapper_error=None, cleanup_errors=[],
                           inspection_result_sha256=m.sha((m.INSPECTION / 'result.json').read_bytes()))
        save(m.INSPECTION_OWNER / 'exit.json', self.exited)
        save(m.INSPECTION / 'a1/vm.child.json', {'pid': 999999992, 'start_ticks': 3})
        save(m.INSPECTION / 'inspection-session.json', {
            'prep_work': str(m.PREP), 'runner_dir': str(m.RUNNER), 'source_directory': str(m.INSPECTOR),
            'guard_source': str(m.GUARD), 'guard_work': str(m.GUARD_WORK), 'partition_guest_source': str(m.PARTITION_GUEST)})
        self.session = {'runner_sources': m.FROZEN, 'helper_ram_mib': 2048, 'helper_vcpus': 4,
                        'guest_ram_gib': 3, 'native_required': True, 'tcg_retry': False, 'package': '/synthetic/package'}
        m.SESSION_DIGEST = m.digest(self.session)
        save(m.PREP / 'session.json', self.session)
        (m.PREP / 'owner.lock').touch()
        (m.PREP / 'attempts').mkdir()
        (m.PREP / 'checkpoints').mkdir()
        for name in ('04-0001', '07-0001', '07-0002', '07-0003', '07-0004'):
            (m.PREP / 'attempts' / name).mkdir()
        m.APP_SOURCES = {}
        m.SOURCE_HASHES = {}
        for name in ('audit_ios26_apps.py', 'audit_ios26_apps_guest.py'):
            path = m.APPS / name
            body = ('# synthetic ' + name + '\n').encode()
            path.write_bytes(body)
            m.APP_SOURCES[name] = {'bytes': len(body), 'sha256': m.sha(body)}
            m.SOURCE_HASHES[path] = m.sha(body)
        save(m.APPS_INSTALL, {'schema': 1, 'kind': 'resume1_apps_auditor_sources_install',
             'source_directory': str(m.APPS), 'execution_started': False,
             'files': [{'path': name, **pin} for name, pin in m.APP_SOURCES.items()]})
        self.inv = {'completed': [], 'rows': {}, 'hashes': {}, 'artifacts': {}}
        self.extend_inventory(m.FIRSTBOOT_STAGES)
        self.plan = self.make_plan(False)
        self.prior = {'files': {}, 'firstboot_checkpoints': dict(self.inv['hashes']), 'fixture': 'accepted saved proof'}
        parsed = types.SimpleNamespace(execute=False, allow_network=False, allow_guest_boots=False,
                   helper_seconds=m.HELPER_SECONDS, helper_ram_mib=2048, helper_vcpus=4,
                   max_log_mib=64, min_free_mib=1536, min_available_mib=512)
        self.prep = types.SimpleNamespace(parser=lambda: types.SimpleNamespace(parse_args=lambda _: parsed),
                                         preflight=mock.Mock(side_effect=lambda _: copy.deepcopy(self.plan)))
        self.inspector = types.SimpleNamespace(checkpoint_inventory=mock.Mock(side_effect=lambda *_: copy.deepcopy(self.inv)),
                                              preflight=mock.Mock(side_effect=AssertionError('whole inspector preflight must not run')))
        self.guard = types.SimpleNamespace(load_frozen=mock.Mock(return_value=self.prep))
        self.apps = types.SimpleNamespace(
            approved_module=lambda path: (self.guard if path == m.GUARD else self.inspector, b'synthetic'),
            checkpoint_inventory=mock.Mock(side_effect=lambda *_: copy.deepcopy(self.inv)),
            saved_inspection=mock.Mock(side_effect=lambda *_: copy.deepcopy(self.prior)),
            preflight=mock.Mock(side_effect=AssertionError('whole app audit preflight must not run')))
        self.module_patch = mock.patch.object(m, 'module_from', return_value=self.apps)
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)
        self.uid_patch = mock.patch.object(m.os, 'geteuid', return_value=0)
        self.uid_patch.start()
        self.addCleanup(self.uid_patch.stop)
        self.pin_all()

    def pin_all(self):
        m = self.m
        m.INSPECTION_SUCCESS_PINS = {path: {'bytes': Path(path).stat().st_size, 'sha256': m.sha(Path(path).read_bytes())}
                                     for path in m.expected_success_paths()}

    def extend_inventory(self, stages):
        m = self.m
        for stage in stages:
            previous = next(reversed(self.inv['hashes'].values()), None)
            record = {'schema': 1, 'status': 'STAGE_COMPLETE', 'stage': stage, 'artifacts': {},
                      'session_sha256': m.SESSION_DIGEST, 'previous_sha256': previous,
                      'attempt': str(m.PREP / 'attempts' / ('07-0004' if stage == 'ios26-firstboot' else m.NEXT_ATTEMPTS.get(stage, '04-0001')))}
            path = m.PREP / 'checkpoints' / (stage + '.json')
            save(path, record)
            self.inv['completed'].append(stage)
            self.inv['rows'][stage] = record
            self.inv['hashes'][str(path)] = m.sha(path.read_bytes())

    def make_plan(self, final):
        m = self.m
        return {'schema': 1, 'status': 'PREFLIGHT_READY', 'work': str(m.PREP), 'session': self.session,
                'completed': list(self.inv['completed']), 'artifacts': {}, 'remaining': [] if final else m.NEXT_STAGES,
                'through': 'ios26-apps', 'helper_smoke': False, 'network_stages': [], 'guest_boot_stages': [],
                'execution_verified': False, **m.NO_BOOT}

    def test_unreleased_both_modes_refuse_before_reads_or_actions(self):
        self.m.INSPECTION_SUCCESS_PINS = None
        for argv in (['--preflight'], ['--execute'], ['--execute', '--preflight-sha256', '0' * 64, '--preflight-bytes', '1']):
            with self.subTest(argv=argv), mock.patch.object(self.m, 'prerequisites') as read, \
                    mock.patch.object(self.m.subprocess, 'Popen') as spawn, contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(self.m.main(argv), 2)
                self.assertIn('unreleased', out.getvalue())
                read.assert_not_called()
                spawn.assert_not_called()
        self.assertFalse(self.m.OWNER.exists())

    def test_exact_fourteen_pin_schema_required(self):
        self.assertEqual(len(self.m.expected_success_paths()), 14)
        self.m.require_finalized()
        self.m.INSPECTION_SUCCESS_PINS.pop(next(iter(self.m.INSPECTION_SUCCESS_PINS)))
        with self.assertRaisesRegex(ValueError, 'fourteen'):
            self.m.require_finalized()

    def test_changed_observed_result_refuses_before_loading_validator(self):
        (self.m.INSPECTION / 'result.json').write_text('changed\n')
        with self.assertRaisesRegex(ValueError, 'changed bound input'):
            self.m.prerequisites()
        self.apps.saved_inspection.assert_not_called()

    def test_rebound_failed_outer_receipt_still_refuses(self):
        self.exited['accepted'] = False
        save(self.m.INSPECTION_OWNER / 'exit.json', self.exited)
        self.pin_all()
        with self.assertRaisesRegex(ValueError, 'has not accepted'):
            self.m.prerequisites()

    def test_matching_inspection_identity_refuses(self):
        with mock.patch.object(self.m, 'identity', return_value=self.startup['wrapper']):
            with self.assertRaisesRegex(ValueError, 'still present'):
                self.m.prerequisites()

    def test_new_or_later_attempt_refuses_initial_boundary(self):
        (self.m.PREP / 'attempts/08-0001').mkdir()
        with self.assertRaisesRegex(ValueError, 'unexpected later attempt'):
            self.m.prerequisites()

    def test_counter1_install_receipt_required(self):
        value = self.m.read_json(self.m.APPS_INSTALL)
        value['execution_started'] = True
        save(self.m.APPS_INSTALL, value)
        with self.assertRaisesRegex(ValueError, 'installation receipt differs'):
            self.m.prerequisites()

    def test_same_existing_validator_receives_eight_then_eleven_prefix(self):
        initial, _ = self.m.read_state(False)
        self.assertEqual(self.apps.saved_inspection.call_args.args[6]['completed'], self.m.FIRSTBOOT_STAGES)
        self.inspector.checkpoint_inventory.assert_called_once()
        self.apps.checkpoint_inventory.assert_not_called()
        for name in self.m.NEXT_ATTEMPTS.values():
            (self.m.PREP / 'attempts' / name).mkdir()
        self.extend_inventory(self.m.NEXT_STAGES)
        self.plan = self.make_plan(True)
        actual, _ = self.m.read_state(True)
        self.assertEqual(self.apps.saved_inspection.call_args.args[6]['completed'], self.m.FIRSTBOOT_STAGES + self.m.NEXT_STAGES)
        self.apps.checkpoint_inventory.assert_called_once()
        for key in ('inputs', 'firstboot_checkpoints', 'prior_evidence', 'past_attempts'):
            self.assertEqual(initial[key], actual[key])
        self.apps.preflight.assert_not_called()
        self.inspector.preflight.assert_not_called()

    def test_plan_with_guest_or_network_or_wrong_remaining_is_rejected(self):
        for key, value in (('guest_boot_stages', ['ios26-firstboot']), ('network_stages', ['ios26-fetch']),
                           ('remaining', ['ios26-gpu']), ('through', 'ios26-gpu')):
            with self.subTest(key=key):
                plan = dict(self.plan, **{key: value})
                with self.assertRaisesRegex(ValueError, 'exact native helper boundary'):
                    self.m.validate_plan(plan, self.session, self.inv, False)

    def helper_fixture(self):
        m = self.m
        stage = 'ios26-persona'
        attempt = m.PREP / 'attempts/08-0001'
        attempt.mkdir()
        artifact = {'path': 'attempts/08-0001/files/root26g.qcow2', 'fixture': True}
        checkpoint = {'attempt': str(attempt), 'artifacts': {'root26g.qcow2': artifact}}
        save(attempt / 'stage-result.json', checkpoint)
        save(attempt / 'stage-inputs.json', {'stage': stage, 'session_sha256': m.SESSION_DIGEST, 'inputs': {}})
        vm = {'schema': 1, 'stage': stage, 'status': 'VM_OBSERVATION_COMPLETE', 'natural_exit': True,
              'done_codes': [0], 'cleanup': {'exit_code': 0, 'echild': True, 'forced_qemu': False,
                                           'forced_descendants': [], 'errors': []},
              'witnesses': {'native_initialization': True, 'native_execution': True, 'fatal_markers': []}, **m.NO_BOOT}
        save(attempt / 'vm-result.json', vm)
        save(attempt / 'vm.child.json', {'pid': 999999993, 'start_ticks': 4})
        save(attempt / 'launch.json', {'deadline_seconds': m.HELPER_SECONDS,
             'command': ['/synthetic/package/qemu-system-aarch64', '-m', '2048M', '-smp', '4'],
             'environment': {'ASOFT_NATIVE_EL0': '1', 'ASOFT_NATIVE_EL0_REQUIRED': '1', 'ASOFT_NATIVE_EL0_STUBS': '8'}})
        prep = types.SimpleNamespace(vm_success=lambda *_: True, verify_artifact=lambda record, root: root / record['path'])
        inventory = copy.deepcopy(self.inv)
        inventory['rows'][stage] = checkpoint
        inventory['session'] = self.session
        return prep, stage, inventory, attempt, vm

    def test_helper_requires_native_clean_reap_even_if_frozen_predicate_mocked_true(self):
        prep, stage, inventory, attempt, vm = self.helper_fixture()
        self.m.validate_helper(prep, stage, inventory)
        vm['cleanup']['forced_qemu'] = True
        save(attempt / 'vm-result.json', vm)
        with self.assertRaisesRegex(ValueError, 'natural native completion'):
            self.m.validate_helper(prep, stage, inventory)

    def test_helper_rejects_foreign_stage_inputs(self):
        prep, stage, inventory, attempt, _ = self.helper_fixture()
        save(attempt / 'stage-inputs.json', {'stage': stage, 'session_sha256': 'foreign', 'inputs': {}})
        with self.assertRaisesRegex(ValueError, 'own predecessor prefix'):
            self.m.validate_helper(prep, stage, inventory)

    def test_helper_rejects_ios_native_tls_contract(self):
        prep, stage, inventory, attempt, _ = self.helper_fixture()
        launch = self.m.read_json(attempt / 'launch.json')
        launch['environment']['ASOFT_NATIVE_EL0_TPIDRRO'] = '1'
        save(attempt / 'launch.json', launch)
        with self.assertRaisesRegex(ValueError, 'native launch contract'):
            self.m.validate_helper(prep, stage, inventory)

    def test_final_acceptance_rejects_changed_prior_evidence(self):
        initial = {'inputs': {'old': 'good'}, 'firstboot_checkpoints': {}, 'prior_evidence': {}, 'past_attempts': []}
        actual = dict(initial, inputs={'old': 'changed'})
        with mock.patch.object(self.m, 'read_state', return_value=(actual, {})):
            with self.assertRaisesRegex(ValueError, 'earlier evidence changed'):
                self.m.accept_result(initial)

    def final_fixture(self):
        current = self.m.prerequisites()
        for name in self.m.NEXT_ATTEMPTS.values():
            (self.m.PREP / 'attempts' / name).mkdir()
        self.extend_inventory(self.m.NEXT_STAGES)
        self.plan = self.make_plan(True)
        save(self.m.PREP / 'result.json', {'schema': 1, 'status': 'PREPARATION_CHECKPOINT',
             'completed': self.m.FIRSTBOOT_STAGES + self.m.NEXT_STAGES, 'stage': 'ios26-apps',
             'attempt': str(self.m.PREP / 'attempts/10-0001'), 'finished_utc': 'synthetic-finish', **self.m.NO_BOOT})
        self.apps.full_inputs = mock.Mock(return_value=[{'synthetic': index} for index in range(6)])
        return current

    def test_final_acceptance_keeps_original_lock_through_full_chain_check(self):
        current = self.final_fixture()

        def checked_chain(*_args):
            with (self.m.PREP / 'owner.lock').open('rb') as stream:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return [{'synthetic': index} for index in range(6)]

        self.apps.full_inputs.side_effect = checked_chain
        with mock.patch.object(self.m, 'validate_helper', return_value={'synthetic': 'validated'}) as helpers:
            acceptance = self.m.accept_result(current)
        self.assertEqual(helpers.call_count, 3)
        self.assertEqual(set(acceptance['helper_files']), set(self.m.NEXT_STAGES))
        self.assertFalse(acceptance['app_copy_audit_passed'])
        self.assertFalse(acceptance['gpu_path_complete'])
        with (self.m.PREP / 'owner.lock').open('rb') as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_final_acceptance_rechecks_inventory_after_lock_acquisition(self):
        current = self.final_fixture()
        self.apps.checkpoint_inventory.side_effect = [copy.deepcopy(self.inv), {'changed': True}]
        with mock.patch.object(self.m, 'validate_helper') as helpers:
            with self.assertRaisesRegex(ValueError, 'boundary changed before final acceptance'):
                self.m.accept_result(current)
        helpers.assert_not_called()
        self.apps.full_inputs.assert_not_called()


class LifecycleTests(unittest.TestCase):
    """Each owner invocation and its tiny runner are real separate Python processes."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='apps-phase-')
        self.addCleanup(self.tmp.cleanup)
        self.root = root = Path(self.tmp.name)
        self.owner = root / 'owner'
        self.plan = {'schema': 1, 'status': 'PREFLIGHT_READY', 'fixture': 'synthetic native helper plan'}
        save(root / 'current.json', {'plan': self.plan})
        save(root / 'public.json', self.plan)
        save(root / 'control.json', {})
        stub = root / 'runner.py'
        stub.write_text('''import json,pathlib,sys,time
p=pathlib.Path(__file__).parent
c=json.loads((p/'control.json').read_text())
with (p/'calls.txt').open('a') as f: f.write(str('--execute' in sys.argv)+'\\n')
if c.get('sleep'): time.sleep(c['sleep'])
print((p/'public.json').read_text(),flush=True)
raise SystemExit(c.get('exit',0))
''')
        self.driver = root / 'driver.py'
        self.driver.write_text(f'''import importlib.util,json,pathlib,sys
s=importlib.util.spec_from_file_location('owner_fixture',{str(SOURCE)!r})
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
p=pathlib.Path({str(root)!r})
m.OWNER=p/'owner'
m.COMMAND=[sys.executable,'-I','-B',str(p/'runner.py')]
m.require_finalized=lambda: None
m.prerequisites=lambda: json.loads((p/'current.json').read_text())
def resources():
 if json.loads((p/'control.json').read_text()).get('resource_failure'): raise ValueError('synthetic resource gate')
m.resources=resources
m.accept_result=lambda current: {{'fixture':'synthetic accepted helper records'}}
m.PREFLIGHT_SECONDS=json.loads((p/'control.json').read_text()).get('deadline',10)
raise SystemExit(m.main())
''')

    def invoke(self, args):
        return subprocess.run([sys.executable, '-I', '-B', str(self.driver), *args], capture_output=True, text=True, timeout=15)

    def preflight(self):
        result = self.invoke(['--preflight'])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        m = load()
        body = (self.owner / 'preflight.json').read_bytes()
        return ['--execute', '--preflight-sha256', m.sha(body), '--preflight-bytes', str(len(body))]

    def test_actual_preflight_child_and_wrapper_are_reaped(self):
        self.preflight()
        m = load()
        receipt = json.loads((self.owner / 'preflight-exit.json').read_text())
        self.assertTrue(receipt['accepted'])
        self.assertTrue(receipt['runner_reaped'])
        self.assertIsNone(m.identity(receipt['runner']['pid']))
        self.assertIsNone(m.identity(receipt['wrapper']['pid']))
        self.assertEqual((self.root / 'calls.txt').read_text(), 'False\n')

    def test_bad_preflight_retained_without_acceptance(self):
        save(self.root / 'public.json', {'status': 'INCOMPLETE'})
        result = self.invoke(['--preflight'])
        self.assertEqual(result.returncode, 2)
        receipt = json.loads((self.owner / 'preflight-exit.json').read_text())
        self.assertFalse(receipt['accepted'])
        self.assertTrue(receipt['runner_reaped'])
        self.assertTrue((self.owner / 'preflight.json').exists())

    def test_wrong_preflight_pin_blocks_execution_without_receipt(self):
        args = self.preflight()
        args[2] = '0' * 64
        result = self.invoke(args)
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.owner / 'command.json').exists())
        self.assertEqual((self.root / 'calls.txt').read_text(), 'False\n')

    def test_execution_with_observed_preflight_can_start_once(self):
        args = self.preflight()
        result = self.invoke(args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        receipt = json.loads((self.owner / 'exit.json').read_text())
        self.assertTrue(receipt['accepted'])
        self.assertTrue(receipt['runner_reaped'])
        self.assertEqual(self.invoke(args).returncode, 2)
        self.assertEqual((self.root / 'calls.txt').read_text(), 'False\nTrue\n')

    def test_resource_gate_refuses_before_execution_command(self):
        args = self.preflight()
        save(self.root / 'control.json', {'resource_failure': True})
        result = self.invoke(args)
        self.assertEqual(result.returncode, 2)
        self.assertIn('synthetic resource gate', result.stdout)
        self.assertFalse((self.owner / 'command.json').exists())
        self.assertEqual((self.root / 'calls.txt').read_text(), 'False\n')

    def test_nonzero_runner_exit_cannot_accept(self):
        args = self.preflight()
        save(self.root / 'control.json', {'exit': 7})
        self.assertEqual(self.invoke(args).returncode, 2)
        receipt = json.loads((self.owner / 'exit.json').read_text())
        self.assertFalse(receipt['accepted'])
        self.assertTrue(receipt['runner_reaped'])
        self.assertEqual(receipt['exit_code'], 7)

    def test_timeout_reaps_only_owned_child_and_retains_failure(self):
        save(self.root / 'control.json', {'deadline': 0.1, 'sleep': 60})
        self.assertEqual(self.invoke(['--preflight']).returncode, 2)
        m = load()
        receipt = json.loads((self.owner / 'preflight-exit.json').read_text())
        self.assertFalse(receipt['accepted'])
        self.assertTrue(receipt['runner_reaped'])
        self.assertIn('deadline', receipt['wrapper_error'])
        self.assertIsNone(m.identity(receipt['runner']['pid']))


if __name__ == '__main__':
    unittest.main()
