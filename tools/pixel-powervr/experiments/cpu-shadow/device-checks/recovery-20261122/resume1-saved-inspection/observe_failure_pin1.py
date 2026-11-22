"""Read-only metadata for the failed saved inspection; never export guest logs."""
import argparse
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import stat

SOURCE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-saved-inspection-resume1.py')
SOURCE_BYTES = 25168
SOURCE_SHA256 = '87526ee42417108f46a8ca03b3fece1cd154f2c439a9c6492f20c97fd6981bb9'
PREFLIGHT_PIN = {'bytes': 9070, 'sha256': '84b31f4f08744f6adeb20ab5af308b1d10c839803c051d4bba577201a4ad3760'}
EXPECTED_WRAPPER = {'pid': 12027, 'starttime': 8432383}
EXPECTED_INSPECTOR = {'pid': 12044, 'starttime': 8432415}
EXPECTED_VM = {'pid': 13326, 'start_ticks': 8442942}


def ordinary(path, limit):
    if path.resolve(strict=True) != path:
        raise ValueError('noncanonical input: ' + str(path))
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > limit:
            raise ValueError('nonordinary or oversized input: ' + str(path))
        body = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    if len(body) > limit or len(body) != before.st_size or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('input changed during observation: ' + str(path))
    return body


def owner_module():
    if os.geteuid() != 0:
        raise ValueError('root observation required')
    body = ordinary(SOURCE, SOURCE_BYTES)
    if len(body) != SOURCE_BYTES or hashlib.sha256(body).hexdigest() != SOURCE_SHA256:
        raise ValueError('reviewed owner source differs')
    namespace = {'__name__': 'reviewed_saved_inspection_owner', '__file__': str(SOURCE)}
    exec(compile(body, str(SOURCE), 'exec'), namespace)
    return namespace


def observe():
    m = owner_module()
    require, absent = m['require'], m['absent']
    base, owner, work = m['BASE'], m['OWNER'], m['WORK']
    cached = {}

    def raw(path):
        if path not in cached:
            cached[path] = ordinary(path, 4 << 20)
        return cached[path]

    def read(path):
        return json.loads(raw(path))

    preflight = raw(owner / 'preflight.json')
    require(len(preflight) == PREFLIGHT_PIN['bytes'] and hashlib.sha256(preflight).hexdigest() == PREFLIGHT_PIN['sha256'],
            'accepted preflight changed')
    current = read(owner / 'prerequisites.json')
    m['validate_preflight'](json.loads(preflight), current)
    for path, pin in current['inputs'].items():
        require(hashlib.sha256(raw(Path(path))).hexdigest() == pin, 'prior source or firstboot input changed')
    for path, pin in m['FIRSTBOOT_SUCCESS_PINS'].items():
        body = raw(Path(path))
        require(len(body) == pin['bytes'] and hashlib.sha256(body).hexdigest() == pin['sha256'], 'successful firstboot binding changed')
    for path, pin in m['SOURCE_HASHES'].items():
        require(hashlib.sha256(raw(path)).hexdigest() == pin, 'immutable source changed')

    start, end = read(owner / 'owner.json'), read(owner / 'exit.json')
    command = m['COMMAND'] + ['--execute']
    require(start.get('schema') == end.get('schema') == 1 and
            start.get('command') == end.get('command') == read(owner / 'command.json') == command and
            all(start.get(k) == end.get(k) for k in ('started_utc', 'wrapper', 'runner')) and
            start.get('wrapper') == EXPECTED_WRAPPER and start.get('runner') == EXPECTED_INSPECTOR and
            end.get('exit_code') == end.get('owner_exit_code') == 2 and end.get('accepted') is False and
            end.get('runner_started') is True and end.get('runner_reaped') is True and end.get('forced_runner') is False and
            end.get('wrapper_error') == 'ValueError: inspector exited 2' and end.get('cleanup_errors') == [] and
            end.get('inspection_result_sha256') is None and end.get('finished_utc'), 'final failed owner receipt differs')
    absent(EXPECTED_WRAPPER, 'failed inspection wrapper')
    absent(EXPECTED_INSPECTOR, 'failed inspection child')
    child = read(work / 'a1/vm.child.json')
    require(child == EXPECTED_VM, 'recorded VM identity differs')
    absent(child, 'failed inspection VM', 'start_ticks')

    launch_path = base / 'ios26-saved-inspection-resume1-execute-launch.json'
    launched = read(launch_path)
    outer = [m['PYTHON'], '-I', '-B', str(SOURCE), '--execute', '--preflight-sha256',
             PREFLIGHT_PIN['sha256'], '--preflight-bytes', str(PREFLIGHT_PIN['bytes'])]
    require(launched.get('schema') == 1 and launched.get('status') == 'SAVED_INSPECTION_EXECUTION_OWNER_LAUNCHED' and
            launched.get('kind') == 'detached_saved_firstboot_execution_owner' and launched.get('command') == outer and
            launched.get('source_sha256') == SOURCE_SHA256 and launched.get('preflight_accepted') is True and
            launched.get('inspection_execution_requested') is True and launched.get('start_new_session') is True and
            {k: launched.get('wrapper', {}).get(k) for k in ('pid', 'starttime')} == EXPECTED_WRAPPER,
            'failed execution launch binding differs')
    require(hashlib.sha256(raw(base / 'saved-inspection-resume1-install.json')).hexdigest() ==
            launched.get('install_receipt_sha256'), 'source installation receipt changed')
    evidence = launched.get('accepted_preflight_evidence', {})
    require(evidence.get('preflight_stdout_sha256') == PREFLIGHT_PIN['sha256'] and
            type(evidence.get('metadata_sha256')) is dict and
            str(owner / 'prerequisites.json') in evidence['metadata_sha256'], 'accepted preflight evidence missing')
    for path, pin in evidence['metadata_sha256'].items():
        require(hashlib.sha256(raw(Path(path))).hexdigest() == pin, 'accepted preflight metadata changed')

    result = read(work / 'result.json')
    require(result == read(work / 'a1/inspection-result.json') and result.get('schema') == 1 and
            result.get('status') == 'INCOMPLETE' and result.get('full_backing_chain_unchanged') is True and
            result.get('preparation_and_guard_unchanged') is True and result.get('identity_error') is None and
            result.get('error') == 'RuntimeError: VM stage incomplete; see ' + str(work / 'a1/vm-result.json') and
            all(result.get(k) is False for k in ('boot_complete', 'gpu_path_complete', 'app_gate_changed')) and
            read(work / 'inspection-session.json') == json.loads(preflight)['inspection_session'] and
            result.get('inspection_session_sha256') == m['digest'](json.loads(preflight)['inspection_session']),
            'final failed inspection or preservation receipt differs')
    vm = read(work / 'a1/vm-result.json')
    cleanup, witness = vm.get('cleanup', {}), vm.get('witnesses', {})
    require(vm.get('stage') == 'saved-firstboot-inspection' and vm.get('status') == 'INCOMPLETE' and
            vm.get('natural_exit') is True and vm.get('error') is None and
            cleanup.get('stop_flushed') is False and cleanup.get('quit_acknowledged') is False and
            cleanup.get('forced_qemu') is False and cleanup.get('errors') == [] and cleanup.get('exit_code') == 0 and
            cleanup.get('echild') is True and cleanup.get('forced_descendants') == [13344] and
            all(witness.get(k) is True for k in ('native_initialization', 'native_execution', 'native_svc_final')) and
            witness.get('fatal_markers') == [], 'observed VM failure or native evidence differs')

    paths = [SOURCE,
             *(base / name for name in ('saved-inspection-resume1-install.json',
               'ios26-saved-inspection-resume1-preflight-launch.json', 'ios26-saved-inspection-resume1-execute-launch.json')),
             *(owner / name for name in ('prerequisites.json', 'preflight-command.json', 'preflight-owner.json',
               'preflight-exit.json', 'preflight.json', 'command.json', 'owner.json', 'exit.json')),
             *(work / name for name in ('inspection-session.json', 'result.json')),
             *(work / 'a1' / name for name in ('inspection-result.json', 'expected-policy.json', 'launch.json', 'vm-result.json', 'vm.child.json'))]
    pins = []
    for index, path in enumerate(paths):
        body = raw(path)
        digest = hashlib.sha256(body)
        pins.append({'index': index, 'path': str(path), 'bytes': len(body),
                     'sha256': digest.hexdigest(), 'digest_bytes': list(digest.digest())})

    inventory = []
    for directory in (owner, work, work / 'a1', work / 'a1/files'):
        require(directory.resolve(strict=True) == directory, 'noncanonical inventory directory')
        for path in sorted(directory.iterdir()):
            info = path.lstat()
            require(not stat.S_ISLNK(info.st_mode), 'inventory symlink refused')
            kind = ('directory' if stat.S_ISDIR(info.st_mode) else 'file' if stat.S_ISREG(info.st_mode) else
                    'socket' if stat.S_ISSOCK(info.st_mode) else 'fifo' if stat.S_ISFIFO(info.st_mode) else 'other')
            row = {'path': str(path), 'kind': kind, 'bytes': info.st_size}
            if path.suffix in ('.log', '.txt') and stat.S_ISREG(info.st_mode):
                body = ordinary(path, 64 << 20)
                row['bytes'] = len(body)
                row['sha256'] = hashlib.sha256(body).hexdigest()
                row['contents_exported'] = False
            inventory.append(row)
    wrapper_log = base / 'ios26-saved-inspection-resume1-execute-wrapper.log'
    body = ordinary(wrapper_log, 64 << 20)
    inventory.append({'path': str(wrapper_log), 'kind': 'file', 'bytes': len(body),
                      'sha256': hashlib.sha256(body).hexdigest(), 'contents_exported': False})
    for path, body in cached.items():
        require(ordinary(path, 4 << 20) == body, 'metadata changed during failure collection')

    summary = {'schema': 1, 'status': 'SAVED_INSPECTION_FAILURE_EVIDENCE_READY', 'readonly': True,
      'observed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'accepted': False,
      'saved_inspection_passed': False, 'prior_inputs_unchanged': True, 'disk_hashes_recomputed_by_this_observer': False,
      'preservation_basis': 'completed immutable inspector reports full_backing_chain_unchanged and preparation_and_guard_unchanged',
      'source_sha256': SOURCE_SHA256, 'preflight': PREFLIGHT_PIN,
      'wrapper': EXPECTED_WRAPPER, 'inspector': EXPECTED_INSPECTOR, 'qemu': EXPECTED_VM,
      'recorded_identities_absent': True, 'forced_descendant_pids': [13344],
      'forced_descendant_start_ticks_recorded': False, 'forced_pid_current_identity': m['identity'](13344),
      'owner_exit': {k: end.get(k) for k in ('started_utc', 'finished_utc', 'exit_code', 'owner_exit_code',
                    'accepted', 'runner_reaped', 'forced_runner', 'wrapper_error', 'cleanup_errors')},
      'inspection': {k: result.get(k) for k in ('status', 'started_utc', 'finished_utc', 'elapsed_seconds', 'error',
                    'identity_error', 'full_backing_chain_unchanged', 'preparation_and_guard_unchanged')},
      'vm': {k: vm.get(k) for k in ('stage', 'status', 'started_utc', 'finished_utc', 'elapsed_seconds', 'natural_exit',
                    'done_codes', 'out_sizes', 'error', 'cleanup', 'witnesses')},
      'pin_count': len(pins), 'pin_pages': math.ceil(len(pins) / 5), 'guest_log_contents_exported': False,
      'no_signal_or_process_launch_or_write': True}
    return summary, pins, inventory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pin-page', type=int, choices=range(4))
    args = parser.parse_args()
    summary, pins, inventory = observe()
    if args.pin_page is None:
        print(json.dumps(summary, separators=(',', ':')), flush=True)
        for row in inventory:
            print(json.dumps({'inventory': row}, separators=(',', ':')), flush=True)
    else:
        first = args.pin_page * 5
        print(json.dumps({k: summary[k] for k in ('schema', 'status', 'readonly', 'observed_utc', 'accepted',
                          'recorded_identities_absent', 'pin_count', 'pin_pages')} | {'page': args.pin_page}, separators=(',', ':')), flush=True)
        for row in pins[first:first + 5]:
            print(json.dumps(row, separators=(',', ':')), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'schema': 1, 'status': 'SAVED_INSPECTION_FAILURE_EVIDENCE_REFUSED', 'readonly': True,
                          'error': type(exc).__name__ + ': ' + str(exc)}, separators=(',', ':')), flush=True)
        raise SystemExit(2)
