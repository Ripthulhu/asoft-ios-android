"""Regression checks for the actual pin typo and hidden early-refusal boundary."""
from pathlib import Path
import ast
import copy
import json
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


def definitions(path):
    scope = {'__name__': 'test_definitions', '__file__': str(path)}
    exec(compile(path.read_bytes(), str(path), 'exec'), scope)
    return scope


class DigestAndOwnerTests(unittest.TestCase):
    def test_actual_digest_arrays_derive_corrected_pin(self):
        build = definitions(HERE / 'build_owner_revision.py')
        actual = json.loads((HERE.parent / 'resume3-saved-inspection/physical-observations/prior-observer-pins-170717.json').read_bytes())
        for row in actual['files'].values():
            self.assertEqual(build['digest_from_decimal'](row), {'bytes': row['bytes'], 'sha256': row['sha256']})
        self.assertEqual(build['digest_from_decimal'](actual['files']['exit.json'])['sha256'],
                         '4af8f8a2feeb3e8103bfaf61c8393aa58f94c9ea01e32f06e51bbaee3cdbb920')

    def test_historical_well_formed_hex_typo_is_rejected(self):
        build = definitions(HERE / 'build_owner_revision.py')
        actual = json.loads((HERE.parent / 'resume3-saved-inspection/physical-observations/prior-observer-pins-170717.json').read_bytes())
        row = copy.deepcopy(actual['files']['exit.json'])
        row['sha256'] = build['OLD_EXIT_SHA256']
        with self.assertRaisesRegex(ValueError, 'differs from decimal bytes'):
            build['digest_from_decimal'](row)

    def test_digest_shape_is_required(self):
        build = definitions(HERE / 'build_owner_revision.py')
        for values in ([0] * 31, [0] * 31 + [True], [0] * 31 + [256]):
            with self.assertRaisesRegex(ValueError, '32 decimal'):
                build['digest_from_decimal']({'bytes': 478, 'sha256': '0' * 64, 'digest_bytes': values})

    def test_all_owner_functions_and_inspector_bindings_unchanged(self):
        prior_path = HERE.parent / 'resume3-saved-inspection/run_saved_inspection_owner.py'
        current_path = HERE / 'run_saved_inspection_owner.py'
        functions = lambda path: {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(path.read_bytes()).body
                                 if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        self.assertEqual(functions(prior_path), functions(current_path))
        prior, current = definitions(prior_path), definitions(current_path)
        for name in ('INSPECTOR', 'INSPECTOR_SOURCE_PINS', 'FIRSTBOOT_SUCCESS_PINS', 'PREVIOUS_FAILURE_PINS'):
            self.assertEqual(prior[name], current[name])
        expected_command = [str(current['WORK']) if value == str(prior['WORK']) else value for value in prior['COMMAND']]
        self.assertEqual(expected_command, current['COMMAND'])
        changed = [key for key in prior['RESUME2_PRESERVATION_PINS']
                   if prior['RESUME2_PRESERVATION_PINS'][key] != current['RESUME2_PRESERVATION_PINS'][key]]
        self.assertEqual(changed, ['/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume2-observer-procstat1/exit.json'])
        self.assertNotEqual(prior['OWNER'], current['OWNER'])
        self.assertNotEqual(prior['WORK'], current['WORK'])


class MissingExitTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.query = definitions(HERE / 'observe_preflight.py')
        self.query['SOURCE'] = self.base / 'run-owner.py'
        self.query['LAUNCH'] = self.base / 'launch.json'
        self.query['LOG'] = self.base / 'wrapper.log'
        self.live = {}
        self.owner = self.base / 'owner'
        self.command = ['/fixed/python', '-I', '-B', '/fixed/inspector.py']
        def require(value, message):
            if not value:
                raise ValueError(message)
        def read(path, limit):
            body = path.read_bytes()
            require(len(body) <= limit, 'bound exceeded')
            return body
        self.module = {'require': require, 'read_bytes': read, 'OWNER': self.owner,
                       'WORK': self.base / 'work', 'PYTHON': '/fixed/python', 'COMMAND': self.command,
                       'identity': lambda pid: self.live.get(pid),
                       'prerequisites': lambda: self.fail('pending/refusal diagnostic must not call prerequisites')}
        self.wrapper = {'pid': 6603, 'starttime': 9193748, 'session': 6603, 'process_group': 6603}

    def launch(self):
        value = {'schema': 1, 'kind': 'detached_saved_firstboot_preflight_owner',
                 'status': 'PREFLIGHT_OWNER_LAUNCHED', 'started_utc': '2026-11-22T17:01:52+00:00',
                 'command': ['/fixed/python', '-I', '-B', str(self.query['SOURCE']), '--preflight'],
                 'source_sha256': self.query['SOURCE_SHA256'], 'wrapper_log': str(self.query['LOG']),
                 'start_new_session': True, 'inspection_execution_requested': False,
                 'preflight_accepted': False, 'wrapper': self.wrapper}
        self.query['LAUNCH'].write_text(json.dumps(value))
        return value

    def report(self):
        value = self.query['without_exit'](self.module)
        self.assertIs(value['accepted'], False)
        self.assertIs(value['readonly'], True)
        return value

    def test_exact_early_refusal_is_explicit(self):
        self.launch()
        error = 'ValueError: preserved resume2 evidence changed: /fixed/exit.json'
        self.query['LOG'].write_text(json.dumps({'schema': 1, 'status': 'OWNER_REFUSED', 'error': error}) + '\n')
        value = self.report()
        self.assertEqual(value['status'], 'SAVED_INSPECTION_PREFLIGHT_OWNER_REFUSED')
        self.assertEqual(value['owner_refusal']['error'], error)
        self.assertIs(value['wrapper_present'], False)
        self.assertIs(value['owner_directory_present'], False)
        self.assertIsNone(value['runner_present'])

    def test_pending_requires_recorded_wrapper_present(self):
        self.launch()
        self.live[6603] = {'pid': 6603, 'starttime': 9193748}
        self.assertEqual(self.report()['status'], 'SAVED_INSPECTION_PREFLIGHT_PENDING')

    def test_ended_without_exit_is_not_pending(self):
        self.launch()
        self.query['LOG'].write_bytes(b'')
        self.assertEqual(self.report()['status'], 'SAVED_INSPECTION_PREFLIGHT_EXIT_RECEIPT_MISSING')

    def test_reused_pid_is_not_the_recorded_wrapper(self):
        self.launch()
        self.live[6603] = {'pid': 6603, 'starttime': 9193749}
        self.assertEqual(self.report()['status'], 'SAVED_INSPECTION_PREFLIGHT_EXIT_RECEIPT_MISSING')

    def test_not_launched_and_missing_evidence_are_distinct(self):
        self.assertEqual(self.report()['status'], 'SAVED_INSPECTION_PREFLIGHT_NOT_LAUNCHED')
        self.query['LOG'].write_bytes(b'')
        self.assertEqual(self.report()['status'], 'SAVED_INSPECTION_PREFLIGHT_LAUNCH_EVIDENCE_MISSING')

    def test_live_runner_without_wrapper_is_explicit(self):
        self.launch()
        self.owner.mkdir()
        runner = {'pid': 6604, 'starttime': 9193749}
        (self.owner / 'preflight-owner.json').write_text(json.dumps({'schema': 1, 'command': self.command,
            'wrapper': {'pid': 6603, 'starttime': 9193748}, 'runner': runner}))
        self.live[6604] = runner
        value = self.report()
        self.assertEqual(value['status'], 'SAVED_INSPECTION_PREFLIGHT_OWNER_ABSENT_RUNNER_PRESENT')
        self.assertIs(value['runner_present'], True)

    def test_wrong_launch_source_binding_refuses(self):
        launch = self.launch()
        launch['source_sha256'] = '0' * 64
        self.query['LAUNCH'].write_text(json.dumps(launch))
        with self.assertRaisesRegex(ValueError, 'launch binding differs'):
            self.report()


if __name__ == '__main__':
    unittest.main()
