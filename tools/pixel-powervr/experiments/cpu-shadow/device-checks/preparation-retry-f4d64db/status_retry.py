#!/usr/bin/env python3
"""Read-only status snapshot of the recorded f4d64db rootfs retry.

No subprocesses, signals, writes, locks, mounts, image reads or log reads.
Exit 0 means the observation completed, never that preparation passed.
"""
import sys

sys.dont_write_bytecode = True

import argparse
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat

WORK = Path('/data/local/tmp/pixel-prep-e9cc754')
OWNER = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-disks-retry-f4d64db')
OWNER_SHA = '46db915626179ad8ab55fc7ce3ec0fb002410a6d888c69576b1d1fd9ae68675e'
SESSION_SHA = '406cfe4a378840d8fc4d8d2e02043bb5655322d4e7fbb415400ad3a6090b50c8'
SESSION_DIGEST = '9ce5f5b8e4953ac54fddd854c5b4a606c2b9866814af6b1d520c2b590e987a6b'
LAUNCH_SHA = '5e103e9e9e7a933fd60f21afb20e91fbdfc78bc49c3b8d9f8502579fd90cf983'
STAGES = ('shared-fetch', 'shared-unpack', 'shared-build', 'ios26-fetch',
          'ios26-decrypt', 'ios26-rootfs', 'ios26-partition')
PREFIX_SHA = (
    'd15e96de8a605839d2ea6d3c77d8696a9ede8ef89ec8b5c3935f368e63c17feb',
    '86a7195eeb373f579db8480ead1225eb4f2aef7a28dff84e8d063abbf2ef8d03',
    'f3257edeea736ac95280c4bdfc40a7716b16f399b29a76418b4591e2d08fb2e9',
    '2351f01e061c97d9ad4b9d8a86b9090be8fbaa0db4c19e11d1894d5ea368539d',
    'b64ddbb674272a968c35b29538ed957a41faf386fb46350ae7964fd9ed238255',
)
MAX_JSON = 256 * 1024
MAX_ENTRIES = 128
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def stamp(ns):
    return datetime.datetime.fromtimestamp(ns / 1e9, datetime.timezone.utc).isoformat()


def clip(value, limit=1000):
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + ' [truncated]'
    return value if value is None or type(value) in (bool, int, float) else '[unexpected type]'


def finding(report, code, detail):
    if len(report['findings']) < 32:
        report['findings'].append({'code': code, 'detail': clip(str(detail), 500)})
    else:
        report['additional_findings_omitted'] = True


def directory(path):
    """Open each absolute path component without following a symlink."""
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('nonabsolute or noncanonical path')
    fd = os.open('/', DIR_FLAGS)
    try:
        for part in path.parts[1:]:
            child = os.open(part, DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def bounded_bytes(path, limit):
    parent = directory(path.parent)
    fd = None
    try:
        fd = os.open(path.name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK,
                     dir_fd=parent)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise ValueError('not a bounded regular file')
        body = bytearray()
        while len(body) <= limit:
            chunk = os.read(fd, min(65536, limit + 1 - len(body)))
            if not chunk:
                break
            body.extend(chunk)
        if len(body) > limit:
            raise ValueError('file exceeded read bound')
        after = os.fstat(fd)
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError('file changed in place during snapshot read')
        return bytes(body), after
    finally:
        if fd is not None:
            os.close(fd)
        os.close(parent)


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError('nonfinite JSON number')


def finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('nonfinite JSON number')
    return result


def metadata(path, report, optional=False):
    try:
        body, info = bounded_bytes(path, MAX_JSON)
        data = json.loads(body, object_pairs_hook=unique_pairs, parse_constant=invalid_constant,
                          parse_float=finite_float)
        if not isinstance(data, dict):
            raise ValueError('metadata root is not an object')
        return {'state': 'read', 'data': data, 'sha256': hashlib.sha256(body).hexdigest(),
                'mtime_utc': stamp(info.st_mtime_ns)}
    except FileNotFoundError:
        if not optional:
            finding(report, 'metadata_missing', str(path))
        return {'state': 'missing'}
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        finding(report, 'metadata_unreadable', f'{path}: {type(exc).__name__}: {exc}')
        return {'state': 'unreadable'}


def process(identity, report, label, start_key='starttime'):
    if (not isinstance(identity, dict) or type(identity.get('pid')) is not int
            or identity['pid'] <= 0 or type(identity.get(start_key)) is not int
            or identity[start_key] <= 0):
        finding(report, 'invalid_process_identity', label)
        return {'state': 'identity_unreadable', 'live': None}
    pid, expected = identity['pid'], identity[start_key]
    row = {'pid': pid, 'recorded_start_ticks': expected, 'live': None}
    try:
        body, _ = bounded_bytes(Path('/proc') / str(pid) / 'stat', 16384)
        if not body.startswith(str(pid).encode() + b' ('):
            raise ValueError('wrong PID stat record')
        fields = body.rsplit(b')', 1)[1].split()
        actual = int(fields[19])
        state, ppid = fields[0].decode('ascii'), int(fields[1])
        if actual <= 0 or ppid < 0 or re.fullmatch(r'[A-Za-z]', state) is None:
            raise ValueError('invalid process stat fields')
        row.update(observed_start_ticks=actual, kernel_state=state, ppid=ppid)
        if actual != expected:
            row.update(state='pid_reused', live=False)
        elif state in ('Z', 'X', 'x'):
            row.update(state='exited_or_zombie', live=False)
        else:
            row.update(state='identity_matches', live=True)
    except FileNotFoundError:
        row.update(state='absent', live=False)
    except (OSError, ValueError, UnicodeError, IndexError) as exc:
        finding(report, 'proc_unreadable', f'{label} PID {pid}: {type(exc).__name__}: {exc}')
        row['state'] = 'unreadable'
    return row


def entries(path, report):
    fd = None
    try:
        fd = directory(path)
        result = []
        with os.scandir(fd) as stream:
            for index, entry in enumerate(stream):
                if index >= MAX_ENTRIES:
                    raise ValueError('directory entry bound exceeded')
                result.append((entry.name, entry.is_dir(follow_symlinks=False)))
        return result
    except (OSError, ValueError) as exc:
        finding(report, 'directory_unreadable', f'{path}: {type(exc).__name__}: {exc}')
        return []
    finally:
        if fd is not None:
            os.close(fd)


def checkpoint_prefix(report):
    session = metadata(WORK / 'session.json', report)
    session_ok = session.get('sha256') == SESSION_SHA
    if session['state'] == 'read' and not session_ok:
        finding(report, 'session_identity_changed', 'session.json differs from recorded retry')
    rows, prefix, previous, gap = [], [], None, not session_ok
    for index, name in enumerate(STAGES):
        item = metadata(WORK / 'checkpoints' / (name + '.json'), report, optional=index >= 5)
        row = {'stage': name, 'state': item['state']}
        if item['state'] != 'read':
            gap = True
        else:
            data = item['data']
            good = (type(data.get('schema')) is int and data['schema'] == 1
                    and data.get('stage') == name and data.get('status') == 'STAGE_COMPLETE'
                    and data.get('session_sha256') == SESSION_DIGEST
                    and data.get('previous_sha256') == previous
                    and isinstance(data.get('artifacts'), dict) and bool(data['artifacts'])
                    and all(data.get(k) is False for k in ('boot_complete', 'gpu_path_complete', 'app_gate_changed')))
            if index < 5:
                good = good and item['sha256'] == PREFIX_SHA[index]
            else:
                attempt = data.get('attempt')
                pattern = re.escape(str(WORK / 'attempts')) + f'/{index:02d}-[0-9]{{4}}'
                good = good and isinstance(attempt, str) and re.fullmatch(pattern, attempt) is not None
                if good:
                    good = int(attempt.rsplit('-', 1)[1]) >= (2 if index == 5 else 1)
            row.update(sha256=item['sha256'], recorded_status=clip(data.get('status')),
                       attempt=clip(data.get('attempt')), finished_utc=clip(data.get('finished_utc')))
            if not good or gap:
                row['state'] = 'invalid_or_noncontiguous'
                finding(report, 'checkpoint_prefix_unverified', name)
                gap = True
            else:
                prefix.append(name)
            previous = item['sha256']
        rows.append(row)
    for name, _ in entries(WORK / 'checkpoints', report):
        if name.endswith('.json') and name not in {stage + '.json' for stage in STAGES}:
            finding(report, 'checkpoint_outside_retry_boundary', name)
    return {'scope': 'recorded metadata chain only; image bytes and filesystem state not verified',
            'session_matches': session_ok, 'contiguous_prefix': prefix, 'records': rows}


def allocation(path, report):
    parent = None
    try:
        parent = directory(path.parent)
        info = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('not a regular file; no image opened')
        return {'path': str(path), 'state': 'observed', 'file_bytes': info.st_size,
                'allocated_bytes': info.st_blocks * 512, 'mtime_utc': stamp(info.st_mtime_ns)}
    except FileNotFoundError:
        return {'path': str(path), 'state': 'missing'}
    except (OSError, ValueError) as exc:
        finding(report, 'allocation_unreadable', f'{path}: {type(exc).__name__}: {exc}')
        return {'path': str(path), 'state': 'unreadable'}
    finally:
        if parent is not None:
            os.close(parent)


def option(argv, name):
    positions = [i for i, value in enumerate(argv) if value == name]
    if len(positions) != 1 or positions[0] + 1 >= len(argv):
        raise ValueError('missing or repeated launch option ' + name)
    return clip(argv[positions[0] + 1], 128)


def attempt_snapshot(name, report):
    path = WORK / 'attempts' / name
    result = {'attempt': name, 'association': 'directory snapshot; ownership is checked separately'}
    launch = metadata(path / 'launch.json', report, optional=True)
    result['launch'] = {'state': launch['state']}
    if launch['state'] == 'read':
        try:
            data = launch['data']; argv = data['command']; env = data['environment']
            if (not isinstance(argv, list) or len(argv) > 256
                    or not all(isinstance(x, str) and len(x) <= 4096 for x in argv)
                    or not isinstance(env, dict) or type(data.get('deadline_seconds')) is not int):
                raise ValueError('invalid launch metadata shape')
            selected = {'state': 'read', 'mtime_utc': launch['mtime_utc'], 'sha256': launch['sha256'],
                        'deadline_seconds': data['deadline_seconds'], 'ram': option(argv, '-m'),
                        'vcpus': option(argv, '-smp'), 'native_required': clip(env.get('ASOFT_NATIVE_EL0_REQUIRED')),
                        'native_stubs': clip(env.get('ASOFT_NATIVE_EL0_STUBS'))}
            result['launch'] = selected
            if (selected['deadline_seconds'], selected['ram'], selected['vcpus'],
                    selected['native_required'], selected['native_stubs']) != (21600, '2048M', '4', '1', '8'):
                finding(report, 'launch_settings_differ_from_retry', name)
            if name == '05-0002' and launch['sha256'] != LAUNCH_SHA:
                finding(report, 'recorded_retry_launch_changed', name)
        except (KeyError, ValueError, TypeError) as exc:
            finding(report, 'launch_metadata_invalid', f'{name}: {exc}')
            result['launch']['state'] = 'invalid'
    child = metadata(path / 'vm.child.json', report, optional=True)
    result['child'] = (process(child['data'], report, name + ' QEMU', 'start_ticks')
                       if child['state'] == 'read' else {'state': child['state'], 'live': None})
    vm = metadata(path / 'vm-result.json', report, optional=True)
    result['vm_snapshot'] = {'state': vm['state']}
    if vm['state'] == 'read':
        data = vm['data']; witnesses = data.get('witnesses', {})
        expected_stage = 'ios26-rootfs' if name.startswith('05-') else 'ios26-partition'
        valid = (type(data.get('schema')) is int and data['schema'] == 1
                 and data.get('stage') == expected_stage and isinstance(data.get('status'), str)
                 and isinstance(data.get('started_utc'), str) and type(data.get('natural_exit')) is bool
                 and isinstance(data.get('witnesses'), dict))
        if not valid:
            finding(report, 'vm_snapshot_schema_invalid', name)
        if not isinstance(witnesses, dict):
            finding(report, 'vm_witnesses_invalid', name)
            witnesses = {}
        selected = {k: clip(data.get(k)) for k in ('stage', 'status', 'started_utc', 'finished_utc',
                    'elapsed_seconds', 'natural_exit', 'error', 'boot_complete', 'gpu_path_complete', 'app_gate_changed')}
        selected.update(state='read' if valid else 'invalid', metadata_mtime_utc=vm['mtime_utc'], error_field_present='error' in data,
                        scope='atomic file snapshot; may change immediately after read',
                        witnesses={k: clip(witnesses.get(k)) for k in ('native_initialization', 'native_execution',
                                   'native_sampler', 'native_svc_final', 'gpu_execution', 'frame_captured')})
        cleanup = data.get('cleanup')
        selected['cleanup_present'] = isinstance(cleanup, dict)
        if isinstance(cleanup, dict):
            selected['cleanup'] = {k: clip(cleanup.get(k)) for k in ('exit_code', 'echild', 'forced_qemu')}
        result['vm_snapshot'] = selected
    disk = 'root26.qcow2' if name.startswith('05-') else 'root26g.qcow2'
    result['allocation'] = [allocation(path / 'files' / disk, report), allocation(path / 'out.raw', report)]
    return result


def resources(report):
    result = {'observed_utc': utc()}
    try:
        body, _ = bounded_bytes(Path('/proc/meminfo'), 65536)
        values = re.findall(rb'^MemAvailable:\s+([0-9]+) kB$', body, re.M)
        if len(values) != 1:
            raise ValueError('missing or repeated MemAvailable')
        result['mem_available_bytes'] = int(values[0]) * 1024
    except (OSError, ValueError) as exc:
        finding(report, 'memory_unreadable', f'{type(exc).__name__}: {exc}')
    fd = None
    try:
        fd = directory(WORK); info = os.fstatvfs(fd)
        result['work_free_bytes'] = info.f_bavail * info.f_frsize
    except OSError as exc:
        finding(report, 'free_space_unreadable', f'{type(exc).__name__}: {exc}')
    finally:
        if fd is not None:
            os.close(fd)
    return result


def observe():
    report = {'schema': 1, 'kind': 'recorded_retry_read_only_status_snapshot', 'started_utc': utc(),
              'work': str(WORK), 'owner_directory': str(OWNER), 'findings': [],
              'scope': 'observation only; no preparation, filesystem, boot or GPU pass is granted'}
    owner = metadata(OWNER / 'owner.json', report)
    report['owner_record'] = {'state': owner['state'], 'identity_matches': owner.get('sha256') == OWNER_SHA}
    processes = {}
    if owner['state'] == 'read' and owner['sha256'] == OWNER_SHA:
        report['owner_record']['started_utc'] = clip(owner['data'].get('started_utc'))
        for name in ('wrapper', 'runner'):
            processes[name] = process(owner['data'].get(name), report, name)
    elif owner['state'] == 'read':
        finding(report, 'owner_identity_changed', 'owner.json differs from recorded retry; owner PIDs not queried')
    report['owner_processes'] = processes
    receipt = metadata(OWNER / 'exit.json', report, optional=True)
    report['exit_receipt'] = {'state': receipt['state']}
    if receipt['state'] == 'read':
        data = receipt['data']
        report['exit_receipt'].update({k: clip(data.get(k)) for k in ('started_utc', 'finished_utc', 'exit_code',
                    'wrapper_error', 'forced_runner', 'runner_started', 'runner_reaped', 'requires_owned_process_recheck')})
        valid = (report['owner_record']['identity_matches'] and type(data.get('schema')) is int
                 and data['schema'] == 1 and data.get('command') == owner['data'].get('command')
                 and data.get('started_utc') == owner['data'].get('started_utc')
                 and isinstance(data.get('finished_utc'), str) and bool(data['finished_utc'])
                 and 'exit_code' in data and (data['exit_code'] is None or type(data['exit_code']) is int)
                 and 'wrapper_error' in data and (data['wrapper_error'] is None or isinstance(data['wrapper_error'], str))
                 and all(type(data.get(k)) is bool for k in
                         ('forced_runner', 'runner_started', 'runner_reaped', 'requires_owned_process_recheck'))
                 and isinstance(data.get('cleanup_errors'), list)
                 and all(isinstance(x, str) for x in data['cleanup_errors']))
        if not valid:
            report['exit_receipt']['state'] = 'invalid_or_unbound'
            finding(report, 'exit_receipt_invalid_or_unbound', 'receipt does not match the recorded owner/schema')
        errors = data.get('cleanup_errors')
        if isinstance(errors, list):
            report['exit_receipt']['cleanup_errors'] = [clip(x, 500) for x in errors[:8]]
            report['exit_receipt']['cleanup_errors_truncated'] = len(errors) > 8
    live = [name for name, row in processes.items() if row.get('live') is True]
    uncertain = not processes or any(row.get('live') is None for row in processes.values())
    exit_state = report['exit_receipt']['state']
    if exit_state == 'read':
        report['owner_state'] = ('exit_recorded_owner_still_live' if live else
                                 'exit_recorded_liveness_unverified' if uncertain else 'exit_recorded')
    elif live:
        report['owner_state'] = 'owner_live_exit_receipt_' + exit_state
    elif uncertain:
        report['owner_state'] = 'owner_liveness_unverified_exit_receipt_' + exit_state
    else:
        report['owner_state'] = 'owner_not_live_exit_receipt_' + exit_state
    if receipt['state'] == 'missing' and not live:
        finding(report, 'exit_receipt_missing', 'no exit receipt; missing/unknown owners do not establish completion')
    report['checkpoints'] = checkpoint_prefix(report)
    latest = {}
    for name, is_dir in entries(WORK / 'attempts', report):
        match = re.fullmatch(r'(05|06)-([0-9]{4})', name)
        if not match:
            continue
        stage, number = match[1], int(match[2])
        if not is_dir:
            finding(report, 'attempt_not_directory', name)
        elif number >= (2 if stage == '05' else 1) and name > latest.get(stage, ''):
            latest[stage] = name
    report['latest_attempts'] = [attempt_snapshot(name, report) for _, name in sorted(latest.items())]
    if latest.get('05') != '05-0002':
        finding(report, 'recorded_retry_attempt_not_latest', '05-0002 is absent or a newer rootfs attempt exists')
    if latest.get('06') not in (None, '06-0001'):
        finding(report, 'newer_partition_attempt', 'latest partition directory differs from the first retry partition attempt')
    top = metadata(WORK / 'result.json', report, optional=True)
    report['work_result'] = {'state': top['state'], 'scope': 'may describe a previous boundary, not the active attempt'}
    if top['state'] == 'read':
        report['work_result'].update({k: clip(top['data'].get(k)) for k in
                                     ('status', 'stage', 'attempt', 'started_utc', 'finished_utc', 'error')})
    report['resources'] = resources(report)
    report['finished_utc'] = utc()
    return report


def human(report):
    q = lambda value: json.dumps(value, ensure_ascii=True)
    print('Retry snapshot ' + report['finished_utc'] + ' (observation only; no pass verdict)')
    print('Owner: ' + report['owner_state'] + '; exit receipt: ' + report['exit_receipt']['state'])
    for name, row in report['owner_processes'].items():
        print(f"  {name}: PID {row.get('pid')} start {row.get('recorded_start_ticks')} "
              f"{row['state']} kernel={row.get('kernel_state', '?')}")
    if report['exit_receipt']['state'] == 'read':
        print('  Recorded exit=' + q(report['exit_receipt'].get('exit_code'))
              + ' finished=' + q(report['exit_receipt'].get('finished_utc'))
              + ' reaped=' + q(report['exit_receipt'].get('runner_reaped'))
              + ' forced=' + q(report['exit_receipt'].get('forced_runner'))
              + ' wrapper_error=' + q(report['exit_receipt'].get('wrapper_error'))
              + ' cleanup_errors=' + q(report['exit_receipt'].get('cleanup_errors')))
    prefix = report['checkpoints']['contiguous_prefix']
    print(f"Checkpoint metadata prefix: {len(prefix)}/7; latest=" + (prefix[-1] if prefix else 'unverified'))
    if not report['latest_attempts']:
        print('Attempts: no new 05/06 directories observed.')
    for item in report['latest_attempts']:
        launch, vm, child = item['launch'], item['vm_snapshot'], item['child']
        print(item['attempt'] + ': launch=' + launch['state'] + ' deadline=' + q(launch.get('deadline_seconds'))
              + ' -m=' + q(launch.get('ram')) + ' -smp=' + q(launch.get('vcpus'))
              + ' child=' + q(child.get('pid')) + '/' + q(child.get('recorded_start_ticks'))
              + ' ' + child['state'])
        print('  VM snapshot=' + vm['state'] + ' status=' + q(vm.get('status')) + ' started=' + q(vm.get('started_utc'))
              + ' sample_mtime=' + q(vm.get('metadata_mtime_utc'))
              + ' elapsed=' + q(vm.get('elapsed_seconds')) + 's')
        witnesses = vm.get('witnesses', {})
        print('  Native init/exec/sample/final=' + '/'.join(q(witnesses.get(k)) for k in
              ('native_initialization', 'native_execution', 'native_sampler', 'native_svc_final'))
              + ' error=' + (q(vm.get('error')) if vm.get('error_field_present') else '[absent]')
              + ' cleanup=' + q(vm.get('cleanup_present')))
        for disk in item['allocation']:
            print('  ' + Path(disk['path']).name + ': ' + disk['state']
                  + (f" file={disk['file_bytes']} allocated={disk['allocated_bytes']} bytes"
                     if disk['state'] == 'observed' else ''))
    resources_now = report['resources']
    print('Current resources: MemAvailable=' + q(resources_now.get('mem_available_bytes'))
          + ' bytes; work free=' + q(resources_now.get('work_free_bytes')) + ' bytes')
    top = report['work_result']
    print('Top-level result (may be stale): ' + q(top.get('status')) + ' ' + q(top.get('stage'))
          + ' attempt=' + q(top.get('attempt')) + ' error=' + q(top.get('error')))
    for item in report['findings']:
        print('Finding ' + item['code'] + ': ' + q(item['detail']))
    if report.get('additional_findings_omitted'):
        print('Finding limit reached; further findings omitted.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='print selected bounded metadata as JSON')
    args = parser.parse_args()
    report = observe()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False))
    else:
        human(report)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
