"""Focused result binding and output-scope tests with in-memory evidence only."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import types
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.p = load('observe_jibs_UNRELEASED')
        self.source = b'# inert source fixture; all helpers are supplied in memory\n'
        self.source_pin = {'bytes': len(self.source), 'sha256': hashlib.sha256(self.source).hexdigest()}
        self.out = Path('/fixture-output')
        self.raw = [bytes(4096), bytes([1]) + bytes(4095)]
        self.layouts = [{'image': 'saved'}, {'image': 'baseline'}]
        self.rows = [dict(image=name, bytes=4096, sha256=hashlib.sha256(body).hexdigest(),
                          virtual_offset=2101248, jib_block=257, flags=1, flags_hex='0x00000001',
                          journal_offset=1056768, journal_bytes=8388608,
                          private_signature='synthetic-should-not-be-exported',
                          uuid='synthetic-should-not-be-exported')
                     for name, body in zip(('saved', 'baseline'), self.raw)]
        self.comparison = {'equal': False, 'differing_bytes': 1, 'range_count': 1,
                           'ranges': [{'start': 0, 'end': 1, 'private': 'synthetic'}],
                           'omitted_ranges': 0, 'ranges_truncated': False, 'private': 'synthetic',
                           'range_limit': 128, 'offset_convention': 'JIB-relative half-open intervals',
                           'raw_byte_values_exported': False, 'difference_classified_as_safe': False}
        self.plan = [{'label': 'j' + str(index), 'output': str(self.out / ('j' + str(index) + '.bin')),
                      'command': ['fixed-read', str(index)]} for index in range(16)]
        self.m = types.SimpleNamespace(absent=lambda *_: None, canonical=lambda path: path,
            read_json=lambda _: {'tooling': '/fixture-tools'}, PREP=Path('/fixture-prep'), utc=lambda: 'fixture UTC')
        self.d = types.ModuleType('fixture_diagnostic')
        self.d.OUT = self.out
        self.d.LIMITS = {'result_bytes': 65536}
        self.d.TOOL_PIN = {'bytes': 1, 'sha256': '0' * 64}
        self.d.load_bound_owner = lambda: self.m
        self.d.check_metadata = lambda _: ({}, {'backing_chain': [
            {'identity': {'path': '/fixture-saved'}}, {'identity': {'path': '/fixture-baseline'}}]}, {})
        self.d.load_header_layouts = lambda *_: deepcopy(self.layouts)
        self.d.read_plan = lambda *_: deepcopy(self.plan)
        self.d.decode_jib = lambda body, layout: deepcopy(self.rows[0 if layout['image'] == 'saved' else 1])
        self.d.compare_jibs = lambda *_: deepcopy(self.comparison)
        self.result = {'schema': 1, 'kind': 'readonly_root_jib_diagnostic',
            'status': 'READONLY_ROOT_JIB_COMPARISON_OBSERVED',
            'source': {'path': str(self.p.SOURCE), **self.source_pin},
            'diagnostic_only': True, 'disk_identities_unchanged': True,
            'bound_metadata_unchanged': True, 'bound_tooling_unchanged': True,
            'recorded_inspection_processes_absent': True,
            'inspection_success_claimed': False, 'guest_vm_started': False, 'mounted': False,
            'replayed': False, 'repaired': False, 'fsck_run': False, 'full_disk_hashes_recomputed': False,
            'journal_pointer_followed': False, 'raw_bytes_exported': False, 'difference_classified_as_safe': False,
            'error': None, 'preservation_error': None, 'owner': {'pid': 123, 'starttime': 456},
            'root_layouts': deepcopy(self.layouts), 'tool': {'path': '/fixture-tools/tools/qemu-img', **self.d.TOOL_PIN},
            'tool_commands': [dict(label=row['label'], command=row['command'], exit_code=0,
                                   reaped=True, forced=False) for row in self.plan],
            'jibs': deepcopy(self.rows), 'comparison': deepcopy(self.comparison)}

    def bound_collect(self, mutate_bytes=None):
        body = (json.dumps(self.result) + '\n').encode()
        self.p.SOURCE_PIN = self.source_pin
        self.p.RESULT_PIN = {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}
        evidence = {self.p.SOURCE: self.source, self.out / 'result.json': body,
                    self.out / 'saved-jib.bin': self.raw[0], self.out / 'baseline-jib.bin': self.raw[1]}
        for index, row in enumerate(self.plan):
            block = self.raw[index // 8]
            evidence[Path(row['output'])] = block[(index % 8) * 512:(index % 8 + 1) * 512]
        if mutate_bytes:
            mutate_bytes(evidence)
        with patch.object(self.p, 'read', side_effect=lambda path, limit: evidence[path]), \
                patch.object(self.p.os, 'geteuid', return_value=0), \
                patch.object(self.p.types, 'ModuleType', return_value=self.d):
            return self.p.collect()

    def test_unbound_projection_refuses_before_any_read_or_identity_query(self):
        with patch.object(self.p, 'read', side_effect=AssertionError('unexpected read')), \
                patch.object(self.p.os, 'geteuid', side_effect=AssertionError('unexpected identity query')):
            with self.assertRaisesRegex(ValueError, 'unreleased'):
                self.p.collect()
            self.p.SOURCE_PIN = self.source_pin
            with self.assertRaisesRegex(ValueError, 'unreleased'):
                self.p.collect()

    def test_successful_projection_uses_explicit_scalar_allowlist(self):
        projected = self.bound_collect()
        text = json.dumps(projected)
        self.assertNotIn('synthetic-should-not-be-exported', text)
        self.assertNotIn('private', text)
        self.assertNotIn('"uuid"', text)
        self.assertEqual(projected['comparison']['ranges'], [{'start': 0, 'end': 1}])
        self.assertIs(projected['raw_jib_bytes_exported'], False)
        self.assertIs(projected['journal_state_evaluated'], False)
        self.assertIs(projected['inspection_success_claimed'], False)

    def test_changed_result_hash_refuses_before_scalar_projection(self):
        def corrupt(evidence):
            evidence[self.out / 'result.json'] += b' '
        with self.assertRaisesRegex(ValueError, 'actual completed diagnostic result differs'):
            self.bound_collect(corrupt)

    def test_incomplete_result_cannot_be_projected_as_complete(self):
        self.result['status'] = 'INCOMPLETE'
        with self.assertRaisesRegex(ValueError, 'completed diagnostic/source differs'):
            self.bound_collect()

    def test_missing_preservation_or_success_claim_refuses(self):
        del self.result['bound_metadata_unchanged']
        with self.assertRaisesRegex(ValueError, 'recorded preservation differs'):
            self.bound_collect()
        self.result['bound_metadata_unchanged'] = True
        self.result['inspection_success_claimed'] = True
        with self.assertRaisesRegex(ValueError, 'diagnostic boundary differs'):
            self.bound_collect()

    def test_changed_command_or_forced_cleanup_refuses(self):
        self.result['tool_commands'][0]['command'] = ['different']
        with self.assertRaisesRegex(ValueError, 'actual owned extraction command differs'):
            self.bound_collect()
        self.result['tool_commands'][0]['command'] = self.plan[0]['command']
        self.result['tool_commands'][0]['forced'] = True
        with self.assertRaisesRegex(ValueError, 'actual owned extraction command differs'):
            self.bound_collect()

    def test_sector_reassembly_mismatch_refuses(self):
        def corrupt(evidence):
            evidence[Path(self.plan[0]['output'])] = bytes([255]) + bytes(511)
        with self.assertRaisesRegex(ValueError, 'complete JIB differs'):
            self.bound_collect(corrupt)

    def test_retained_comparison_mismatch_refuses(self):
        self.result['comparison']['equal'] = True
        with self.assertRaisesRegex(ValueError, 'scalar comparison differ'):
            self.bound_collect()

    def test_live_diagnostic_owner_refuses(self):
        def still_present(*_):
            raise ValueError('owned diagnostic still present')
        self.m.absent = still_present
        with self.assertRaisesRegex(ValueError, 'still present'):
            self.bound_collect()

    def test_unbound_receipt_reader_refuses_before_any_read(self):
        reader = load('observe_jib_result_pin_UNRELEASED')
        with patch.object(reader, 'read', side_effect=AssertionError('unexpected read')), \
                patch.object(reader.os, 'geteuid', side_effect=AssertionError('unexpected identity query')):
            with self.assertRaisesRegex(ValueError, 'unreleased'):
                reader.main()

    def test_both_readers_refuse_missing_or_wrong_new_boundary_fields(self):
        fields = {'recorded_inspection_processes_absent': True, 'journal_pointer_followed': False,
                  'raw_bytes_exported': False, 'difference_classified_as_safe': False}
        for field, expected in fields.items():
            for wrong in (None, not expected):
                with self.subTest(field=field, wrong=wrong):
                    if wrong is None:
                        del self.result[field]
                    else:
                        self.result[field] = wrong
                    with self.assertRaises(ValueError):
                        self.bound_collect()
                    reader = load('observe_jib_result_pin_UNRELEASED')
                    reader.SOURCE_PIN = self.source_pin
                    self.d.OUT = reader.RESULT.parent
                    body = json.dumps(self.result).encode()
                    evidence = {reader.SOURCE: self.source, reader.RESULT: body}
                    with patch.object(reader, 'read', side_effect=lambda path, limit: evidence[path]), \
                            patch.object(reader.os, 'geteuid', return_value=0), \
                            patch.object(reader.types, 'ModuleType', return_value=self.d):
                        with self.assertRaises(ValueError):
                            reader.main()
                    self.d.OUT = self.out
                    self.result[field] = expected


class LocalFinalizerTests(unittest.TestCase):
    """Synthetic binding fixtures stay in a temporary directory, never this package."""

    def setUp(self):
        self.f = load('finalize_jib_projection')
        self.temp = tempfile.TemporaryDirectory(prefix='jib-projection-finalizer-test-')
        self.root = Path(self.temp.name)
        self.f.ROOT = self.root
        source = b'# inert synthetic finalizer fixture\n'
        source_pin = {'bytes': len(source), 'sha256': hashlib.sha256(source).hexdigest()}
        source_row = {'path': self.f.BASE + '/run-ios26-root-jib-diagnostic-resume4.py', **source_pin}
        (self.root / 'inspect_root_jib.py').write_bytes(source)
        (self.root / 'transport-build.json').write_text(json.dumps({'source': source_row}))
        self.draft = (HERE / 'observe_jibs_UNRELEASED.py').read_bytes()
        (self.root / 'observe_jibs_UNRELEASED.py').write_bytes(self.draft)
        (self.root / 'synthetic-review.json').write_text('{"synthetic_unit_test_fixture":true}\n')
        digest = hashlib.sha256(b'synthetic test receipt')
        self.observed = {'kind': 'selected_physical_root_jib_diagnostic_observation',
            'independently_reviewed': True, 'independent_review': 'synthetic-review.json',
            'status': 'ROOT_JIB_RESULT_BINDING_READY', 'diagnostic_status': 'READONLY_ROOT_JIB_COMPARISON_OBSERVED',
            'readonly': True, 'jibs': 2, 'tool_commands': 16, 'all_own_tool_children_reaped': True,
            'forced_tool_children': [], 'disk_identities_unchanged': True, 'bound_metadata_unchanged': True,
            'bound_tooling_unchanged': True, 'recorded_inspection_processes_absent': True,
            'inspection_success_claimed': False, 'full_disk_hashes_recomputed': False,
            'journal_pointer_followed': False, 'difference_classified_as_safe': False,
            'raw_bytes_exported': False, 'raw_jib_bytes_exported': False, 'error': None,
            'preservation_error': None, 'source': source_row,
            'result': {'path': self.f.BASE + '/ios26-root-jib-diagnostic-resume4/result.json',
                       'bytes': len(b'synthetic test receipt'), 'sha256': digest.hexdigest(),
                       'digest_bytes': list(digest.digest())}}

    def tearDown(self):
        self.temp.cleanup()

    def finalize(self):
        path = self.root / 'synthetic-observation.json'
        path.write_text(json.dumps(self.observed))
        return self.f.finalize(path)

    def test_two_pin_delta_is_additive_and_commands_are_bounded(self):
        record = self.finalize()
        self.assertEqual((self.root / 'observe_jibs_UNRELEASED.py').read_bytes(), self.draft)
        self.assertEqual(record['only_executable_delta'], 'SOURCE_PIN and RESULT_PIN')
        self.assertEqual(len(record['commands']), 5)
        self.assertTrue(all(row['bytes'] <= 6000 for row in record['commands']))
        with self.assertRaises(FileExistsError):
            self.finalize()

    def test_unreviewed_observation_refuses_before_output(self):
        self.observed['independently_reviewed'] = False
        with self.assertRaises(AssertionError):
            self.finalize()
        self.assertFalse((self.root / 'result-binding').exists())

    def test_hex_decimal_disagreement_refuses_before_output(self):
        self.observed['result']['digest_bytes'][0] ^= 1
        with self.assertRaisesRegex(AssertionError, 'decimal digest differ'):
            self.finalize()
        self.assertFalse((self.root / 'result-binding').exists())

    def test_source_mismatch_refuses_before_output(self):
        self.observed['source']['sha256'] = '0' * 64
        with self.assertRaisesRegex(AssertionError, 'actual diagnostic source differs'):
            self.finalize()
        self.assertFalse((self.root / 'result-binding').exists())

    def test_failed_diagnostic_refuses_before_output(self):
        self.observed['diagnostic_status'] = 'INCOMPLETE'
        with self.assertRaises(AssertionError):
            self.finalize()
        self.assertFalse((self.root / 'result-binding').exists())


if __name__ == '__main__':
    unittest.main()
