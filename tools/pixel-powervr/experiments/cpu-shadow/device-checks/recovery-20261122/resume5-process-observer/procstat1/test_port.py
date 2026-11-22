"""Verify a path/pin-only port of the independently reviewed observer."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
OLD = HERE.parents[1] / 'resume4-process-observer/procstat1'


class NormalizeScope(ast.NodeTransformer):
    def visit_Constant(self, node):
        if isinstance(node.value, str):
            node.value = node.value.replace('pixel-saved-checks-resume5', 'pixel-saved-checks-resume3').replace('resume5', 'resume4').replace('RESUME5', 'RESUME4')
        return node


def assignments(tree):
    return {t.id: node for node in tree.body if isinstance(node, ast.Assign)
            for t in node.targets if isinstance(t, ast.Name)}


class ReviewedPort(unittest.TestCase):
    def assert_only_bindings_changed(self, name, pins):
        before = ast.parse((OLD / name).read_bytes())
        after = NormalizeScope().visit(ast.parse((HERE / name).read_bytes()))
        original, revised = assignments(before), assignments(after)
        for pin in pins:
            revised[pin].value = copy.deepcopy(original[pin].value)
        self.assertEqual(ast.dump(before, include_attributes=False), ast.dump(after, include_attributes=False))

    def test_observer_algorithm_and_bounds_equal_reviewed_revision(self):
        self.assert_only_bindings_changed('observe_processes.py', {'OWNER_SOURCE_PIN'})

    def test_detached_launcher_lifecycle_equal_reviewed_revision(self):
        self.assert_only_bindings_changed('launch_observer.py', {'SOURCE_PIN'})

    def test_ready_identity_heartbeat_and_wait_gates_equal_reviewed_revision(self):
        self.assert_only_bindings_changed('observe_ready.py', {'SOURCE_PIN', 'PREFLIGHT_SHA256', 'PREFLIGHT_BYTES'})

    def test_final_reader_keeps_corrected_missing_vs_empty_cleanup_semantics(self):
        self.assert_only_bindings_changed('projection-pin1/observe_status.py', {'SOURCE_PIN'})

    def test_source_transfer_builder_preserves_exclusive_install_behavior(self):
        self.assert_only_bindings_changed('build_transport.py', {'OWNER_PIN'})

    def test_additive_runtime_finalizer_keeps_actual_preflight_binding(self):
        self.assert_only_bindings_changed('finalize_runtime.py', set())

    def test_projection_command_builder_is_unchanged(self):
        self.assert_only_bindings_changed('projection-pin1/build_projection.py', set())

    def test_fresh_target_scope_and_owner_source_are_exact(self):
        spec = importlib.util.spec_from_file_location('ported_scope', HERE / 'observe_processes.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        base = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
        self.assertEqual(module.OWNER, base / 'ios26-saved-inspection-resume5-owner')
        self.assertEqual(module.OUT, base / 'ios26-saved-inspection-resume5-observer-procstat1')
        self.assertEqual(module.WORK, Path('/data/local/tmp/pixel-saved-audit-e9cc754-resume5'))
        self.assertEqual(module.OWNER_SOURCE, base / 'run-ios26-saved-inspection-resume5.py')
        self.assertEqual(module.COMMAND[3], '/data/local/tmp/pixel-saved-checks-resume5/inspect_ios26_firstboot.py')
        self.assertEqual(module.COMMAND[5], '/data/local/tmp/pixel-firstboot-guard-e9cc754-resume1')
        if module.OWNER_SOURCE_PIN is None:
            self.assertFalse((HERE / 'source-transfer').exists())
            self.assertFalse((HERE / 'transfer-manifest.json').exists())
        else:
            body = (HERE.parents[1] / 'resume5-saved-inspection/run_saved_inspection_owner.py').read_bytes()
            self.assertEqual(module.OWNER_SOURCE_PIN, {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()})

    def test_runtime_wrappers_require_actual_fresh_preflight_binding(self):
        build = assignments(ast.parse((HERE / 'build_transport.py').read_bytes()))
        ready = assignments(ast.parse((HERE / 'observe_ready.py').read_bytes()))
        digest, count = [ast.literal_eval(build[k].value) for k in ('PREFLIGHT_SHA', 'PREFLIGHT_BYTES')]
        self.assertEqual([ast.literal_eval(ready[k].value) for k in ('PREFLIGHT_SHA256', 'PREFLIGHT_BYTES')], [digest, count])
        runtime = [HERE / (name + suffix) for name in ('launch-observer', 'observe-ready')
                   for suffix in ('.py', '.command.txt')]
        if digest is None or count is None:
            self.assertIsNone(digest)
            self.assertIsNone(count)
            self.assertTrue(all(not path.exists() for path in runtime))
        else:
            binding = json.loads((HERE / 'preflight-binding.json').read_text())
            self.assertEqual(binding['stdout'], {'bytes': count, 'sha256': digest})
            self.assertTrue(binding['observed_utc'])
            self.assertTrue(all(path.is_file() for path in runtime))


if __name__ == '__main__':
    unittest.main(verbosity=2)
