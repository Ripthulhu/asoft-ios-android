"""Focused resume5 release/preservation tests; no device or image access."""
from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
import ast
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import struct
import types
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent


def load(path):
    spec = importlib.util.spec_from_file_location('fixture_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def body(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def pin(value):
    return {'bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest()}


class UnreleasedBoundaryTests(unittest.TestCase):
    def test_both_owner_modes_refuse_before_io(self):
        owner = load(HERE / 'run_saved_inspection_owner_UNRELEASED.py')
        self.assertIsNone(owner.INSPECTOR_SOURCE_PINS)
        for mode in ('--preflight', '--execute'):
            with self.subTest(mode=mode), ExitStack() as stack:
                for name in ('read_bytes', 'canonical', 'previous_failure_inputs', 'resume2_failure_inputs', 'resume4_failure_inputs'):
                    stack.enter_context(patch.object(owner, name, side_effect=AssertionError('unexpected I/O')))
                stack.enter_context(patch.object(owner.os, 'geteuid', side_effect=AssertionError('unexpected identity query')))
                stack.enter_context(redirect_stdout(io.StringIO()))
                self.assertEqual(owner.main([mode]), 2)

    def test_both_launchers_refuse_before_io(self):
        preflight = load(HERE / 'launch_saved_inspection_preflight_UNRELEASED.py')
        execution = load(HERE / 'launch_saved_inspection_execution_UNRELEASED.py')
        for module in (preflight, execution):
            with self.subTest(module=module.__name__), ExitStack() as stack:
                stack.enter_context(patch.object(module, 'read', side_effect=AssertionError('unexpected read')))
                stack.enter_context(patch.object(module.os, 'geteuid', side_effect=AssertionError('unexpected identity query')))
                stack.enter_context(patch.object(module.subprocess, 'Popen', side_effect=AssertionError('unexpected child')))
                with self.assertRaisesRegex(ValueError, 'UNRELEASED'):
                    module.launch() if module is preflight else module.launch(types.SimpleNamespace())

    def test_lifecycle_resources_acceptance_and_older_pins_unchanged(self):
        old = ast.parse((HERE.parent / 'resume4-saved-inspection/run_saved_inspection_owner.py').read_bytes())
        new = ast.parse((HERE / 'run_saved_inspection_owner_UNRELEASED.py').read_bytes())
        old_functions = {node.name: ast.dump(node) for node in old.body if isinstance(node, ast.FunctionDef)}
        new_functions = {node.name: ast.dump(node) for node in new.body if isinstance(node, ast.FunctionDef)}
        for name, value in old_functions.items():
            if name != 'prerequisites':
                self.assertEqual(new_functions[name], value, name)
        for name in ('PREVIOUS_FAILURE_PINS', 'RESUME2_PRESERVATION_PINS', 'FIRSTBOOT_SUCCESS_PINS'):
            values = []
            for tree in (old, new):
                values.append(next(ast.dump(node.value) for node in tree.body if isinstance(node, ast.Assign) and
                                   any(isinstance(target, ast.Name) and target.id == name for target in node.targets)))
            self.assertEqual(*values)

    def test_preservation_fragment_has_no_execution_or_image_open_calls(self):
        tree = ast.parse((HERE / 'resume4_preservation_fragment.py').read_bytes())
        forbidden = {'Popen', 'run', 'run_tool', 'main', 'extract_jibs', 'prepare_images', 'qcow_chain', 'kill', 'terminate'}
        calls = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
        self.assertFalse(calls & forbidden)


class PreservedJibTests(unittest.TestCase):
    def setUp(self):
        self.m = load(HERE / 'run_saved_inspection_owner_UNRELEASED.py')
        self.d = load(HERE.parent / 'resume4-saved-inspection/jib-diagnostic/inspect_root_jib.py')
        self.d.load_bound_owner = lambda: types.SimpleNamespace(OWNER=self.m.RESUME4_OWNER,
            WORK=self.m.RESUME4_WORK, INSPECTOR=Path('/data/local/tmp/pixel-saved-checks-resume3'))
        self.images = [self.m.PREP / 'saved.qcow2', self.m.PREP / 'baseline.qcow2']
        self.inspected = {'backing_chain': [{'identity': {'path': str(path)}, 'record': {'fixture': index}}
                                           for index, path in enumerate(self.images)]}
        self.d.check_metadata = lambda _: ({}, deepcopy(self.inspected), {})
        self.layouts = [{'image': name, 'volume_offset': 2048 * 512, 'volume_bytes': self.d.ROOT_BYTES,
                         'block_bytes': 4096, 'jib_block': 257, 'virtual_offset': 2101248, 'bytes': 4096}
                        for name in ('saved', 'baseline')]
        self.d.load_header_layouts = lambda *_: deepcopy(self.layouts)
        self.tooling = Path('/data/local/tmp/pixel-tools-1528a782')
        self.tool = self.tooling / 'tools/qemu-img'
        self.plan = self.d.read_plan(self.images, self.layouts, self.tool)
        baseline = bytearray(4096)
        struct.pack_into('>I', baseline, 0, 5)
        struct.pack_into('>QQ', baseline, 36, 1056768, 8388608)
        saved = bytearray(baseline)
        struct.pack_into('>I', saved, 0, 1)
        self.blocks = [bytes(saved), bytes(baseline)]
        self.evidence = {Path(name): b'{}\n' for name in self.m.RESUME4_PRESERVATION_PINS}
        self.evidence[self.m.JIB_SOURCE] = b'# inert source fixture; validated helpers are supplied in memory\n'
        rows = []
        for index, planned in enumerate(self.plan):
            raw = self.blocks[index // 8][(index % 8) * 512:(index % 8 + 1) * 512]
            self.evidence[Path(planned['output'])] = raw
            command = {'label': planned['label'], 'command': planned['command'], 'pid': None,
                       'exit_code': None, 'reaped': False, 'forced': False}
            row = {**command, 'pid': 12300 + index, 'exit_code': 0, 'reaped': True,
                   'output_bytes': 0, 'output_sha256': hashlib.sha256(b'').hexdigest()}
            self.evidence[self.m.JIB_WORK / (planned['label'] + '.command.json')] = body(command)
            self.evidence[self.m.JIB_WORK / (planned['label'] + '.exit.json')] = body(row)
            self.evidence[self.m.JIB_WORK / (planned['label'] + '.stdout')] = b''
            rows.append(row)
        for name, raw in zip(('saved', 'baseline'), self.blocks):
            self.evidence[self.m.JIB_WORK / (name + '-jib.bin')] = raw
        self.evidence[self.m.JIB_WORK / 'session.json'] = b'{"synthetic_test_fixture":true}\n'
        self.result = {'schema': 1, 'kind': 'readonly_root_jib_diagnostic',
            'status': 'READONLY_ROOT_JIB_COMPARISON_OBSERVED', 'source': {'path': str(self.m.JIB_SOURCE), **pin(self.evidence[self.m.JIB_SOURCE])},
            'root_layouts': deepcopy(self.layouts), 'limits': self.d.LIMITS, 'actual_failed_inspection_pins': 9,
            'previous_full_hash_records': [row['record'] for row in self.inspected['backing_chain']],
            'diagnostic_only': True, 'disk_identities_unchanged': True, 'bound_metadata_unchanged': True,
            'bound_tooling_unchanged': True, 'recorded_inspection_processes_absent': True,
            'inspection_success_claimed': False, 'difference_classified_as_safe': False,
            'guest_vm_started': False, 'fsck_run': False, 'mounted': False, 'replayed': False,
            'repaired': False, 'journal_pointer_followed': False, 'raw_bytes_exported': False,
            'full_disk_hashes_recomputed': False, 'error': None, 'preservation_error': None,
            'owner': {'pid': 123, 'starttime': 456}, 'tool': {'path': str(self.tool), **self.d.TOOL_PIN},
            'capability': {'path': str(self.d.CAPABILITY_RESULT), **self.d.CAPABILITY_PIN, 'passed': True},
            'tool_commands': rows, 'jibs': [self.d.decode_jib(raw, layout) for raw, layout in zip(self.blocks, self.layouts)],
            'comparison': self.d.compare_jibs(*self.blocks)}

    def run_check(self, corrupt=None, absent=None, flock_error=None):
        self.evidence[self.m.JIB_WORK / 'result.json'] = body(self.result)
        self.m.RESUME4_PRESERVATION_PINS = {name: pin(self.evidence[Path(name)]) for name in self.m.RESUME4_PRESERVATION_PINS}
        self.d.RECEIPT_PINS = {name: value for name, value in self.m.RESUME4_PRESERVATION_PINS.items()
                              if name not in (str(self.m.JIB_SOURCE), str(self.m.JIB_WORK / 'result.json'))}
        if corrupt:
            corrupt(self.evidence)
        with ExitStack() as stack:
            stack.enter_context(patch.object(self.m, 'read_bytes', side_effect=lambda path, limit=4 << 20: self.evidence[path]))
            stack.enter_context(patch.object(self.m, 'read_json', return_value={'tooling': str(self.tooling)}))
            stack.enter_context(patch.object(self.m, 'canonical', side_effect=lambda path: path))
            stack.enter_context(patch.object(self.m, 'absent', side_effect=absent))
            stack.enter_context(patch.object(self.m.types, 'ModuleType', return_value=self.d))
            stack.enter_context(patch.object(self.m.os, 'open', return_value=99))
            stack.enter_context(patch.object(self.m.os, 'fstat', return_value=types.SimpleNamespace(st_mode=stat.S_IFREG | 0o600)))
            close = stack.enter_context(patch.object(self.m.os, 'close'))
            stack.enter_context(patch.object(self.m.fcntl, 'flock', side_effect=flock_error))
            try:
                return self.m.resume4_failure_inputs()
            finally:
                if flock_error:
                    close.assert_called_once_with(99)

    def test_exact_retained_transition_is_preserved_without_running_tools(self):
        inputs = self.run_check()
        self.assertEqual(inputs[str(self.m.JIB_WORK / 'saved-jib.bin')], hashlib.sha256(self.blocks[0]).hexdigest())
        self.assertEqual(inputs[str(self.m.JIB_WORK / 'baseline-jib.bin')], hashlib.sha256(self.blocks[1]).hexdigest())
        self.assertTrue(all(str(Path(row['output'])) in inputs for row in self.plan))
        self.assertTrue(all(name in inputs for name in self.m.RESUME4_PRESERVATION_PINS))

    def test_changed_pinned_result_refuses(self):
        def corrupt(evidence):
            evidence[self.m.JIB_WORK / 'result.json'] += b' '
        with self.assertRaisesRegex(ValueError, 'preserved resume4/JIB evidence changed'):
            self.run_check(corrupt=corrupt)

    def test_missing_false_or_true_boundary_flags_refuse(self):
        for key in ('recorded_inspection_processes_absent', 'journal_pointer_followed', 'difference_classified_as_safe'):
            original = self.result.pop(key)
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'preservation or scope differs'):
                self.run_check()
            self.result[key] = original

    def test_forced_tool_cleanup_refuses(self):
        self.result['tool_commands'][0]['forced'] = True
        with self.assertRaisesRegex(ValueError, 'extraction was not clean'):
            self.run_check()

    def test_changed_retained_sector_refuses(self):
        def corrupt(evidence):
            evidence[Path(self.plan[0]['output'])] = bytes([255]) + bytes(511)
        with self.assertRaisesRegex(ValueError, 'complete JIB differs from its sectors'):
            self.run_check(corrupt=corrupt)

    def test_changed_child_exit_receipt_refuses(self):
        def corrupt(evidence):
            evidence[self.m.JIB_WORK / 's0.exit.json'] = b'{}\n'
        with self.assertRaisesRegex(ValueError, 'child exit differs'):
            self.run_check(corrupt=corrupt)

    def test_live_diagnostic_identity_refuses(self):
        def present(*_):
            raise ValueError('diagnostic identity still present')
        with self.assertRaisesRegex(ValueError, 'identity still present'):
            self.run_check(absent=present)

    def test_held_prior_lock_refuses_and_closes_own_fd(self):
        with self.assertRaises(BlockingIOError):
            self.run_check(flock_error=BlockingIOError('held prior lock'))


if __name__ == '__main__':
    unittest.main()
