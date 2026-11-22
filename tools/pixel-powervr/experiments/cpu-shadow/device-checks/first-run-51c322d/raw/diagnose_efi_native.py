#!/usr/bin/env python3
"""Run the unaffected authored cases after an ordering-witness probe failure.

This is a partial diagnostic and can never qualify the package or enable a capability.
"""
import ctypes
import importlib.util
import json
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
installed = json.loads((root / 'installed.json').read_text())
assert installed['status'] == 'GPU_TEST_PACKAGE_VERIFIED_NOT_EXECUTED'
package = Path(installed['package'])
spec = importlib.util.spec_from_file_location('verified_device_runner', package / 'run_device_tests.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
checksums = {}
for line in (package / 'SHA256SUMS').read_text().splitlines():
    digest, name = line.split('  ', 1)
    path = package / name
    assert path.resolve().is_relative_to(package) and runner.sha(path) == digest
    checksums[name] = digest
assert runner.sha(package / 'qemu-system-aarch64') == installed['qemu_sha256']
libc = ctypes.CDLL(None, use_errno=True)
if libc.prctl(36, 1, 0, 0, 0):
    raise OSError(ctypes.get_errno(), 'cannot own diagnostic descendants')
out = root / 'diagnostics-efi-native-51c322d'
out.mkdir(mode=0o700)
env = {'PATH': '/system/bin', 'LD_LIBRARY_PATH': str(package / 'lib'),
       'REIMS_VGPU_CPU_SHADOW': '1', 'REIMS_VGPU_LOG': 'info'}
qualifier = str(package / 'cpu_shadow_qualification')
cases = [
    ('fixed', [qualifier, 'fixed', str(package / 'cpu-shadow-fixed.air')], ['CPU_SHADOW_FIXED_COMPLETE'], 45),
    ('rebind', [qualifier, 'rebind'], ['CPU_SHADOW_REBIND_COMPLETE'], 45),
    ('heap', [qualifier, 'heap'], ['CPU_SHADOW_HEAP_COMPLETE addresses=stable'], 45),
    ('arguments', [qualifier, 'arguments', str(package / 'cpu-shadow-arguments.air')], ['CPU_SHADOW_ARGUMENTS_COMPLETE handles=texture_and_sampler'], 45),
    ('dynamic-rebind', [qualifier, 'dynamic-rebind', str(package / 'cpu-shadow-dynamic-rebind.air')], ['CPU_SHADOW_DYNAMIC_REBIND_COMPLETE residency_only=true'], 45),
    ('tile', [qualifier, 'tile', str(package / 'cpu-shadow-tile-vertex.air'), str(package / 'cpu-shadow-tile-fragment.air')], ['RESULT=REIMS_CPU_SHADOW_TILE_PASS'], 45),
    ('efi', [str(package / 'efi-memfd-integration')], ['"status":"EFI_CPU_SHADOW_PASS"', '"frames_checked":3', '"fragmented":false'], 40),
    ('efi-fragmented', [str(package / 'efi-memfd-integration'), '--fragmented'], ['"status":"EFI_CPU_SHADOW_PASS"', '"frames_checked":3', '"fragmented":true'], 40),
    ('native', [str(package / 'native-efi-owner'), str(package), str(out / 'native-guest')], ['NATIVE_EFI_INTEGRATION_PASS', 'frames=2', 'ECHILD=1'], 55),
]
result = {'scope': 'partial authored EFI/native diagnostics after failed probe and tile witnesses',
          'gpu_path_complete': False, 'all_cases_passed': False, 'android_apk': False,
          'package': str(package), 'package_sha256': checksums,
          'probe_failure_report': str(root / 'qualification-51c322d/qualification.json'),
          'excluded_timing_witness_cases': ['probe', 'alias', 'fragmented', 'chunk-boundary', 'lifetime', 'fixed', 'rebind', 'heap', 'arguments', 'dynamic-rebind', 'tile'],
          'cases': []}
cases = cases[-3:]
for name, command, expected, seconds in cases:
    record = runner.run_case(name, command, env, out, expected, seconds)
    result['cases'].append(record)
    runner.save(out / 'diagnostics.json', result)
    print(json.dumps({'case': name, 'passed': record['passed'], 'exit_code': record['exit_code'], 'log': str(out / name / 'output.log')}), flush=True)
    if not record['passed']:
        print('PARTIAL_DIAGNOSTICS_STOPPED case=' + name, flush=True)
        raise SystemExit(1)
for name, digest in checksums.items():
    assert runner.sha(package / name) == digest
result['selected_cases_passed'] = True
result['package_rechecked'] = True
runner.save(out / 'diagnostics.json', result)
print('PARTIAL_DIAGNOSTICS_PASSED cases=3 qualification=false', flush=True)
