#!/usr/bin/env python3
"""Test run.py with a local fake ADB. ALL replies and binaries are synthetic.

No phone, actual ADB, Vulkan driver, root access, or device connection is used.
The runner receives an explicit path to our fake executable for every case.
Temporary fixtures are removed after success unless --keep-output is specified;
failures retain command traces and reports for inspection. The host-timeout case
shortens the subprocess deadline to 0.1 seconds instead of waiting 75 seconds.
"""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--keep-output', action='store_true',
                    help='Retain synthetic fixtures, command traces, and reports')
args = parser.parse_args()
SOURCE = Path(__file__).resolve().parents[1] / 'run.py'
if not SOURCE.is_file():
    parser.error('Expected run.py in the parent of this tests directory')
LAB = Path(tempfile.mkdtemp(prefix='powervr-runner-mock-'))
REMOTE = '/data/local/tmp/pixel-powervr.FAKE123'
FAKE_ADB = '#!' + sys.executable + '\n' + r'''
import json, os, sys, time
args = sys.argv[1:]
with open(os.environ['FAKE_ADB_LOG'], 'a') as log:
    log.write(json.dumps(args) + '\n')
scenario = os.environ['FAKE_ADB_SCENARIO']
remote = '/data/local/tmp/pixel-powervr.FAKE123'
if args == ['devices']:
    print('List of devices attached\nFAKE_PIXEL\tdevice')
    if scenario in {'multiple', 'multiple_explicit'}:
        print('FAKE_OTHER\tdevice')
    sys.exit(0)
if args[:2] != ['-s', 'FAKE_PIXEL']:
    print('UNEXPECTED DEVICE SELECTION', args)
    sys.exit(97)
args = args[2:]
if args[0] == 'push':
    print('FAKE push: no real device or file transfer')
    sys.exit(1 if scenario == 'push_failure' else 0)
if args[0] != 'shell':
    print('UNEXPECTED ADB COMMAND', args)
    sys.exit(98)
cmd = args[1]
if cmd.startswith('mktemp '):
    if scenario == 'bad_mktemp':
        print('/data/local/tmp/pixel-powervr.FAKE123/../../other')
    elif scenario == 'extra_mktemp':
        print(remote + '\nUNEXPECTED LINE')
    elif scenario == 'shell_mktemp':
        print(remote + '; echo injected')
    else:
        print(remote)
elif cmd.startswith('chmod ') or cmd == 'rm -rf ' + remote:
    pass
elif cmd.startswith('sh ') or cmd.startswith("su -c 'sh "):
    print('FAKE diagnostic output; no device inspected')
elif cmd == 'su -c id':
    if scenario == 'root_denied':
        print('su: permission denied (synthetic)')
        sys.exit(1)
    print('uid=0(root) gid=0(root) (synthetic)')
elif '/tile_image_probe --shader-dir ' in cmd:
    if scenario == 'remote_timeout':
        print('FAKE remote timeout')
        sys.exit(124)
    if scenario == 'segfault':
        print('FAKE Segmentation fault')
        sys.exit(139)
    if scenario == 'abort':
        print('FAKE Aborted')
        sys.exit(134)
    if scenario == 'internal_timeout':
        print('FAIL: synthetic GPU wait exceeded 5 s; exiting without destroying in-flight resources')
        sys.exit(1)
    if scenario == 'host_timeout':
        print('FAKE waiting for host timeout', flush=True)
        time.sleep(1)
    if scenario == 'unsupported':
        print('UNSUPPORTED synthetic feature missing')
        sys.exit(2)
    if scenario == 'tile_unexpected3':
        print('SYNTHETIC undocumented tile status 3')
        sys.exit(3)
    print('PASS synthetic tile result; not hardware evidence')
elif cmd.endswith('/dmabuf_probe') or cmd.endswith("/dmabuf_probe'"):
    if scenario == 'dmabuf_internal_timeout' and not cmd.startswith('su '):
        print('RESULT=FAIL: CPU_TO_GPU fence: VK_TIMEOUT (2); terminating without freeing potentially in-flight Vulkan resources')
        sys.exit(1)
    if scenario == 'blocked':
        print('RESULT=BLOCKED: synthetic missing udmabuf')
        sys.exit(2)
    if scenario == 'dmabuf_unsupported3':
        print('RESULT=UNSUPPORTED: synthetic memory import unavailable')
        sys.exit(3)
    print('RESULT=PASS: synthetic DMA-BUF result; not hardware evidence')
else:
    print('UNEXPECTED SHELL COMMAND', cmd)
    sys.exit(99)
'''

SCENARIOS = [
    'success', 'root_denied', 'multiple', 'multiple_explicit', 'bad_mktemp',
    'extra_mktemp', 'shell_mktemp', 'remote_timeout', 'segfault', 'abort',
    'internal_timeout', 'dmabuf_internal_timeout', 'host_timeout',
    'checksum', 'keep_remote', 'no_root', 'push_failure', 'unsupported', 'blocked',
    'tile_unexpected3', 'dmabuf_unsupported3',
]
source = SOURCE.read_bytes()
summaries = []
for scenario in SCENARIOS:
    folder = LAB / scenario
    package = folder / 'package'
    (package / 'bin').mkdir(parents=True)
    (package / 'run.py').write_bytes(source)
    (package / 'collect_device.sh').write_text('# synthetic diagnostic fixture\n')
    artifacts = ('tile_image_probe', 'dmabuf_probe', 'tile_image.vert.spv', 'tile_image.frag.spv')
    manifest = []
    for name in artifacts:
        contents = ('SYNTHETIC FIXTURE ONLY ' + name).encode()
        (package / 'bin' / name).write_bytes(contents)
        manifest.append(hashlib.sha256(contents).hexdigest() + '  bin/' + name)
    (package / 'SHA256SUMS').write_text('\n'.join(manifest) + '\n')
    if scenario == 'checksum':
        (package / 'bin' / 'tile_image_probe').write_bytes(b'CORRUPTED SYNTHETIC FIXTURE')
    adb = folder / 'adb'
    adb.write_text(FAKE_ADB)
    adb.chmod(0o755)
    log = folder / 'adb.jsonl'
    report = folder / 'report.txt'
    os.environ['FAKE_ADB_LOG'] = str(log)
    os.environ['FAKE_ADB_SCENARIO'] = scenario
    spec = importlib.util.spec_from_file_location('runner_' + scenario, package / 'run.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if scenario == 'host_timeout':
        real_capture = module.capture
        def shortened_capture(command, timeout=120):
            if 'shell' in command and '/tile_image_probe --shader-dir ' in command[-1]:
                return real_capture(command, 0.1)
            return real_capture(command, timeout)
        module.capture = shortened_capture
    sys.argv = ['run.py', '--adb', str(adb), '--output', str(report)]
    if scenario == 'multiple_explicit':
        sys.argv += ['--serial', 'FAKE_PIXEL']
    if scenario == 'keep_remote':
        sys.argv += ['--keep-remote']
    if scenario == 'no_root':
        sys.argv += ['--no-root']
    stdout = io.StringIO()
    error = ''
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stdout):
        try:
            rc = module.main()
        except Exception as exc:
            rc = 1
            error = type(exc).__name__ + ': ' + str(exc)
    (folder / 'console.txt').write_text(stdout.getvalue() + '\n' + error + '\n')
    calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    commands = [call[3] for call in calls if len(call) == 4 and call[2] == 'shell']
    cleanups = [cmd for cmd in commands if cmd.startswith('rm ')]
    gpu = [cmd for cmd in commands if cmd.startswith('timeout ') or cmd.startswith("su -c 'timeout ")]
    root = [cmd for cmd in commands if cmd.startswith('su ')]
    expected_stop = scenario in {'remote_timeout', 'segfault', 'abort', 'internal_timeout', 'host_timeout', 'tile_unexpected3'}
    problems = []
    if expected_stop and (rc != 1 or len(gpu) != 1):
        problems.append('did not stop after first failing GPU probe')
    if scenario == 'dmabuf_internal_timeout' and (rc != 1 or len(gpu) != 2):
        problems.append('did not stop after DMA-BUF internal fence timeout')
    no_remote = scenario in {'multiple', 'bad_mktemp', 'extra_mktemp', 'shell_mktemp', 'checksum'}
    expected_cleanup = [] if no_remote or scenario == 'keep_remote' else ['rm -rf ' + REMOTE]
    if cleanups != expected_cleanup:
        problems.append('cleanup not exactly scoped as expected')
    if scenario == 'checksum' and calls:
        problems.append('ADB invoked despite checksum failure')
    if scenario == 'multiple' and calls != [['devices']]:
        problems.append('device actions despite ambiguous device selection')
    if scenario in {'bad_mktemp', 'extra_mktemp', 'shell_mktemp'} and len(calls) != 2:
        problems.append('device actions after untrusted mktemp output')
    if scenario in {'root_denied', 'no_root'} and (len(gpu) != 2 or len(root) != (1 if scenario == 'root_denied' else 0)):
        problems.append('root denial/no-root handling incorrect')
    if scenario in {'success', 'multiple_explicit', 'keep_remote', 'blocked', 'unsupported', 'dmabuf_unsupported3'} and (rc or len(gpu) != 3):
        problems.append('successful/capability-limited flow incorrect')
    if scenario == 'push_failure' and (rc != 1 or gpu):
        problems.append('push failure did not stop GPU work')
    text = report.read_text() if report.exists() else ''
    if any('exit_code: ' + str(code) + '\n' in text for code in (97, 98, 99)):
        problems.append('fake ADB received an unexpected command or device')
    if scenario == 'root_denied' and 'ROOT_RUN_SKIPPED' not in text:
        problems.append('root denial missing report marker')
    if scenario == 'host_timeout' and 'HOST_TIMEOUT' not in text:
        problems.append('host timeout missing report marker')
    summary = dict(scenario=scenario, runner_rc=rc, adb_calls=len(calls),
                   gpu_commands=len(gpu), cleanup=cleanups, problems=problems,
                   error=error)
    summaries.append(summary)
    print(json.dumps(summary))
summary_path = LAB / 'summary.json'
failures = sum(bool(row['problems']) for row in summaries)
summary = {'all_outputs_synthetic': True,
    'runner_sha256': hashlib.sha256(source).hexdigest(),
    'total_scenarios': len(SCENARIOS), 'passed_scenarios': len(SCENARIOS) - failures,
    'failed_scenarios': failures, 'results': summaries}
summary_path.write_text(json.dumps(summary, indent=2) + '\n')
print('ALL_OUTPUTS_SYNTHETIC=true')
print('RUNNER_SHA256=' + summary['runner_sha256'])
print('TOTAL_SCENARIOS=' + str(summary['total_scenarios']))
print('PASSED_SCENARIOS=' + str(summary['passed_scenarios']))
print('FAILED_BEHAVIOR_SCENARIOS=' + str(failures))
if failures or args.keep_output:
    print('HARNESS_DIR=' + str(LAB))
    print('SUMMARY=' + str(summary_path))
else:
    shutil.rmtree(LAB)
    print('TEMPORARY_FIXTURES_REMOVED=true')
raise SystemExit(1 if failures else 0)
