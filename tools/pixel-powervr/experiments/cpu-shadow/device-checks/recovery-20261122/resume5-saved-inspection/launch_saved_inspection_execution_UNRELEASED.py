#!/usr/bin/env python3
"""Detach the reviewed saved-inspection execution owner after accepted preflight checks.

No direct VM launch, wait, poll, signal, subreaper or process-group cleanup.
The detached wrapper is the inspector's parent and owns its wait/cleanup.
"""
import argparse
import datetime
import re
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import time

BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
SOURCE = BASE / 'run-ios26-saved-inspection-resume5.py'
INSTALL = BASE / 'saved-inspection-resume5-install.json'
LAUNCH = BASE / 'ios26-saved-inspection-resume5-execute-launch.json'
LOG = BASE / 'ios26-saved-inspection-resume5-execute-wrapper.log'
OWNER = BASE / 'ios26-saved-inspection-resume5-owner'
WORK = Path('/data/local/tmp/pixel-saved-audit-e9cc754-resume5')
PYTHON = '/data/data/com.termux/files/usr/bin/python'
SOURCE_BYTES = None
SOURCE_SHA256 = None
PREFLIGHT_SHA256 = None
PREFLIGHT_BYTES = None
COMMAND = [PYTHON, '-I', '-B', str(SOURCE), '--execute', '--preflight-sha256', PREFLIGHT_SHA256, '--preflight-bytes', str(PREFLIGHT_BYTES)]
PREFLIGHT_LAUNCH = BASE / 'ios26-saved-inspection-resume5-preflight-launch.json'
TRANSFER_MANIFEST_SHA256 = None
INSTALLED_FILES = None


MONITOR_SOURCE = BASE / 'run-ios26-saved-inspection-resume5-observer-procstat1.py'
MONITOR_OUT = BASE / 'ios26-saved-inspection-resume5-observer-procstat1'
MONITOR_LAUNCH = BASE / 'ios26-saved-inspection-resume5-observer-procstat1-launch.json'
MONITOR_PIN = None
MONITOR_BOUNDS = {'total_seconds': 9000,
 'launch_wait_seconds': 600,
 'post_exit_seconds': 5,
 'process_identities': 128,
 'events': 10000,
 'proc_directory_entries': 4096,
 'proc_numeric_entries': 2048,
 'discovery_read_bytes': 4194304,
 'discovery_scan_ms': 1000,
 'discovery_interval_ms': 1000,
 'event_bytes': 8388608,
 'metadata_bytes': 4194304,
 'summary_bytes': 262144,
 'status_bytes': 65536,
 'total_output_bytes': 9437184,
 'steady_interval_ms': 200,
 'burst_interval_ms': 20,
 'burst_seconds': 2,
 'heartbeat_seconds': 1}
PREP_SESSION = Path('/data/local/tmp/pixel-prep-e9cc754/session.json')


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def read(path, limit):
    if path.resolve(strict=True) != path:
        raise ValueError('noncanonical input: ' + str(path))
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
            raise ValueError('nonordinary or oversized input: ' + str(path))
        body = stream.read(limit + 1)
        if len(body) > limit:
            raise ValueError('input exceeded bound: ' + str(path))
        return body


def process(pid):
    with (Path('/proc') / str(pid) / 'stat').open('rb') as stream:
        raw = stream.read(4097)
    if len(raw) > 4096:
        raise ValueError('process stat exceeded bound')
    fields = raw[raw.rfind(b')') + 2:].split()
    return {'pid': pid, 'starttime': int(fields[19]), 'state': fields[0].decode('ascii'),
            'parent_pid': int(fields[1]), 'process_group': int(fields[2]), 'session': int(fields[3])}


def preflight_receipts(namespace, current, install_sha):
    """Check the already accepted phase before creating any execution artifact."""
    require, evidence = namespace['require'], {}

    def record(path):
        body = read(path, 2 << 20)
        evidence[str(path)] = hashlib.sha256(body).hexdigest()
        if path == owner / 'preflight.json':
            require(len(body) == PREFLIGHT_BYTES and evidence[str(path)] == PREFLIGHT_SHA256,
                    'actual observed preflight binding differs')
        return json.loads(body)

    owner = namespace['OWNER']
    command = namespace['COMMAND']
    require(record(owner / 'prerequisites.json') == current, 'accepted preflight inputs changed')
    exited = record(owner / 'preflight-exit.json')
    startup = record(owner / 'preflight-owner.json')
    public = record(owner / 'preflight.json')
    require(exited.get('schema') == 1 and exited.get('command') == command and
            record(owner / 'preflight-command.json') == command and
            exited.get('exit_code') == exited.get('owner_exit_code') == 0 and
            exited.get('accepted') is True and exited.get('runner_started') is True and
            exited.get('runner_reaped') is True and exited.get('forced_runner') is False and
            exited.get('wrapper_error') is None and exited.get('cleanup_errors') == [] and
            exited.get('finished_utc') and startup.get('command') == command and
            startup.get('started_utc') == exited.get('started_utc') and
            all(startup.get(k) == exited.get(k) for k in ('wrapper', 'runner')) and
            evidence[str(owner / 'preflight.json')] == exited.get('stdout_sha256'),
            'missing, failed or mismatched accepted preflight receipt')
    namespace['absent'](startup['wrapper'], 'preflight wrapper')
    namespace['absent'](startup['runner'], 'preflight inspector')
    namespace['validate_preflight'](public, current)
    detached = record(PREFLIGHT_LAUNCH)
    process_record = detached.get('wrapper', {})
    require(detached.get('schema') == 1 and detached.get('status') == 'PREFLIGHT_OWNER_LAUNCHED' and
            detached.get('kind') == 'detached_saved_firstboot_preflight_owner' and
            detached.get('command') == [PYTHON, '-I', '-B', str(SOURCE), '--preflight'] and
            detached.get('start_new_session') is True and detached.get('inspection_execution_requested') is False and
            detached.get('source_sha256') == SOURCE_SHA256 and
            detached.get('install_receipt_sha256') == install_sha and
            {k: process_record.get(k) for k in ('pid', 'starttime')} == startup['wrapper'] and
            process_record.get('process_group') == process_record.get('session') == startup['wrapper']['pid'],
            'detached preflight launch differs from accepted owner or installed source')
    return {'metadata_sha256': evidence, 'wrapper': startup['wrapper'], 'inspector': startup['runner'],
            'preflight_stdout_sha256': exited['stdout_sha256'], 'finished_utc': exited['finished_utc']}


def checked_preflight(source, install_sha):
    # The bytes are verified above before compilation. The main guard remains
    # false, so only the reviewed wrapper's definitions are loaded. Reuse its
    # exact read-only prerequisite and receipt validators; start no process.
    namespace = {'__name__': 'reviewed_saved_inspection_outer_owner', '__file__': str(SOURCE)}
    exec(compile(source, str(SOURCE), 'exec'), namespace)
    current = namespace['prerequisites']()
    accepted = preflight_receipts(namespace, current, install_sha)
    namespace['resources']()
    return accepted


def require(condition, message):
    if not condition:
        raise ValueError(message)


def require_release():
    require(type(SOURCE_BYTES) is int and 0 < SOURCE_BYTES <= 256 << 10 and
            type(SOURCE_SHA256) is str and re.fullmatch('[0-9a-f]{64}', SOURCE_SHA256) is not None and
            type(TRANSFER_MANIFEST_SHA256) is str and re.fullmatch('[0-9a-f]{64}', TRANSFER_MANIFEST_SHA256) is not None and
            type(INSTALLED_FILES) is list and len(INSTALLED_FILES) == 2,
            'UNRELEASED: exact reviewed owner and source installation bindings required')
    require(type(PREFLIGHT_SHA256) is str and re.fullmatch('[0-9a-f]{64}', PREFLIGHT_SHA256) is not None and
            type(PREFLIGHT_BYTES) is int and 0 < PREFLIGHT_BYTES <= 2 << 20,
            'UNRELEASED: actual fresh resume5 preflight required')
    require(type(MONITOR_PIN) is dict and set(MONITOR_PIN) == {'bytes', 'sha256'} and
            type(MONITOR_PIN['bytes']) is int and 0 < MONITOR_PIN['bytes'] <= 64 << 10 and
            type(MONITOR_PIN['sha256']) is str and re.fullmatch('[0-9a-f]{64}', MONITOR_PIN['sha256']) is not None,
            'UNRELEASED: exact reviewed observer source required')


def cmdline(pid):
    with (Path('/proc') / str(pid) / 'cmdline').open('rb') as stream:
        body = stream.read(4097)
    require(0 < len(body) <= 4096 and body.endswith(b'\0'), 'invalid bounded observer command line')
    return [part.decode('utf-8') for part in body[:-1].split(b'\0')]


def discovery_probe_validated(probe):
    """Validate the bounded discovery capability actually tested before READY."""
    if (type(probe) is not dict or probe.get('method') != 'bounded_numeric_proc_stat' or
            probe.get('self_identity_verified') is not True or probe.get('unrelated_metadata_exported') is not False):
        return False
    scan = probe.get('scan')
    if type(scan) is not dict:
        return False
    return (all(type(scan.get(k)) is int for k in ('directory_entries', 'numeric_entries', 'readable_entries', 'read_bytes')) and
            0 < scan['readable_entries'] <= scan['numeric_entries'] <= MONITOR_BOUNDS['proc_numeric_entries'] and
            scan['numeric_entries'] <= scan['directory_entries'] <= MONITOR_BOUNDS['proc_directory_entries'] and
            0 < scan['read_bytes'] <= MONITOR_BOUNDS['discovery_read_bytes'] and
            type(scan.get('duration_ms')) in (int, float) and 0 <= scan['duration_ms'] <= MONITOR_BOUNDS['discovery_scan_ms'])


def checked_monitor(args, accepted_preflight):
    """Read only. Bind actual READY bytes, live independent identity and fresh heartbeat."""
    require(type(args.monitor_ready_sha256) is str and
            re.fullmatch('[0-9a-f]{64}', args.monitor_ready_sha256) is not None and
            type(args.monitor_ready_bytes) is int and 0 < args.monitor_ready_bytes <= 16 << 10 and
            type(args.monitor_pid) is int and args.monitor_pid > 1 and
            type(args.monitor_start_ticks) is int and args.monitor_start_ticks > 0,
            'actual observed monitor ready hash, size and identity required')
    require(MONITOR_OUT.resolve(strict=True) == MONITOR_OUT and MONITOR_OUT.is_dir(),
            'canonical observer output directory required')
    for name in ('exit.json', 'summary.json'):
        require(not os.path.lexists(MONITOR_OUT / name), 'observer has already finished')
    source = read(MONITOR_SOURCE, MONITOR_PIN['bytes'])
    source_pin = {'path': str(MONITOR_SOURCE), 'bytes': len(source), 'sha256': hashlib.sha256(source).hexdigest()}
    require(source_pin == {'path': str(MONITOR_SOURCE), **MONITOR_PIN}, 'installed observer source differs')
    ready_body = read(MONITOR_OUT / 'ready.json', 16 << 10)
    ready_pin = {'path': str(MONITOR_OUT / 'ready.json'), 'bytes': len(ready_body),
                 'sha256': hashlib.sha256(ready_body).hexdigest()}
    require(ready_pin['bytes'] == args.monitor_ready_bytes and ready_pin['sha256'] == args.monitor_ready_sha256,
            'actual observed monitor ready bytes differ')
    ready = json.loads(ready_body)
    identity = {'pid': args.monitor_pid, 'start_ticks': args.monitor_start_ticks}
    source_owner = {'path': str(SOURCE), 'bytes': SOURCE_BYTES, 'sha256': SOURCE_SHA256}
    metadata = accepted_preflight['metadata_sha256']

    def bound_json(path):
        body = read(path, 2 << 20)
        require(hashlib.sha256(body).hexdigest() == metadata[str(path)], 'accepted preflight metadata changed')
        return json.loads(body)

    current = bound_json(OWNER / 'prerequisites.json')
    command = bound_json(OWNER / 'preflight-command.json')
    session_body = read(PREP_SESSION, 2 << 20)
    require(hashlib.sha256(session_body).hexdigest() == current['inputs'][str(PREP_SESSION)],
            'bound preparation session changed')
    session = json.loads(session_body)
    require(type(session.get('package')) is str and Path(session['package']).is_absolute(),
            'bound runtime package path missing')
    scope = {'inspection_owner_directory': str(OWNER), 'inspection_work': str(WORK),
             'inspection_command': command + ['--execute'], 'qemu_child_record': str(WORK / 'a1/vm.child.json'),
             'qemu_executable': str(Path(session['package']) / 'qemu-system-aarch64'),
             'native_factory_name': 'asoft-stubfac', 'native_worker_name_pattern': '^asoft-stub[0-9]+$',
             'metadata_only': True, 'discovery_method': 'bounded_numeric_proc_stat'}
    preflight = {'path': str(OWNER / 'preflight.json'), 'bytes': PREFLIGHT_BYTES, 'sha256': PREFLIGHT_SHA256,
                 'exit_sha256': metadata[str(OWNER / 'preflight-exit.json')]}
    require(ready.get('schema') == 1 and ready.get('kind') == 'saved_inspection_process_observer_ready' and
            ready.get('status') == 'READY' and ready.get('observer') == identity and ready.get('ready_utc') and
            ready.get('source') == source_pin and ready.get('output_directory') == str(MONITOR_OUT) and
            ready.get('scope') == scope and ready.get('bounds') == MONITOR_BOUNDS and
            ready.get('inspection_owner_source') == source_owner and ready.get('preflight') == preflight and
            discovery_probe_validated(ready.get('discovery_probe')) and
            ready.get('independent_session') is True and ready.get('target_execution_absent_at_ready') is True and
            ready.get('diagnostic_only') is True, 'observer READY contract differs')

    def recorded_process(row):
        require(type(row) is dict and {k: row.get(k) for k in identity} == identity and
                row.get('session') == row.get('pgrp') == identity['pid'] and row.get('state') not in ('Z', 'X', 'x', 'T', 't', None),
                'recorded observer identity or detached session differs')

    recorded_process(ready.get('observer_process'))
    observer_command = [PYTHON, '-I', '-B', str(MONITOR_SOURCE), '--preflight-sha256', PREFLIGHT_SHA256,
                        '--preflight-bytes', str(PREFLIGHT_BYTES)]
    launched_body = read(MONITOR_LAUNCH, 64 << 10)
    launched = json.loads(launched_body)
    require(launched.get('schema') == 1 and launched.get('kind') == 'detached_saved_inspection_process_observer' and
            launched.get('status') == 'PROCESS_OBSERVER_LAUNCHED' and launched.get('command') == observer_command and
            launched.get('source') == source_pin and launched.get('preflight') == preflight and
            launched.get('inspection_owner_source') == source_owner and launched.get('output_directory') == str(MONITOR_OUT) and
            launched.get('start_new_session') is True and launched.get('diagnostic_only') is True and
            launched.get('inspection_execution_requested') is False and launched.get('finished_utc') and
            not launched.get('error'), 'detached observer launch differs')
    recorded_process(launched.get('observer'))
    live = process(identity['pid'])
    require(live['starttime'] == identity['start_ticks'] and
            live['process_group'] == live['session'] == identity['pid'] and live['state'] not in ('Z', 'X', 'x', 'T', 't'),
            'observer PID was reused, exited or lost its independent session')
    require(cmdline(identity['pid']) == observer_command, 'live observer command line differs')
    heartbeat_body = read(MONITOR_OUT / 'status.json', MONITOR_BOUNDS['status_bytes'])
    heartbeat = json.loads(heartbeat_body)
    require(heartbeat.get('schema') == 1 and heartbeat.get('kind') == 'saved_inspection_process_observer_status' and
            heartbeat.get('status') == 'RUNNING' and heartbeat.get('phase') == 'WAITING_FOR_EXECUTION_OWNER' and
            heartbeat.get('observer') == identity and heartbeat.get('source_sha256') == MONITOR_PIN['sha256'] and
            heartbeat.get('ready_sha256') == ready_pin['sha256'] and heartbeat.get('output_directory') == str(MONITOR_OUT) and
            heartbeat.get('scope') == scope and heartbeat.get('diagnostic_only') is True and
            heartbeat.get('heartbeat_utc'), 'observer heartbeat contract differs')
    now = time.monotonic_ns()
    ready_ns, heartbeat_ns = ready.get('ready_monotonic_ns'), heartbeat.get('heartbeat_monotonic_ns')
    require(type(ready_ns) is type(heartbeat_ns) is int and 0 < ready_ns <= heartbeat_ns <= now and
            now - heartbeat_ns <= 5_000_000_000 and
            now - ready_ns <= (MONITOR_BOUNDS['launch_wait_seconds'] - 5) * 1_000_000_000,
            'observer heartbeat is stale or its owner-wait deadline is too close')
    latest = process(identity['pid'])
    require(latest['starttime'] == identity['start_ticks'] and latest['process_group'] == latest['session'] == identity['pid'] and
            latest['state'] not in ('Z', 'X', 'x', 'T', 't'), 'observer identity changed during readiness validation')
    for name in ('exit.json', 'summary.json'):
        require(not os.path.lexists(MONITOR_OUT / name), 'observer finished during readiness validation')
    return {'ready': ready_pin, 'source': source_pin, 'observer': identity, 'observer_process': latest,
            'preflight': preflight, 'scope': scope, 'bounds': MONITOR_BOUNDS, 'discovery_probe': ready['discovery_probe'],
            'launch_receipt_sha256': hashlib.sha256(launched_body).hexdigest(),
            'heartbeat_sha256': hashlib.sha256(heartbeat_body).hexdigest(),
            'heartbeat_monotonic_ns': heartbeat_ns, 'checked_monotonic_ns': now,
            'ready_age_ns': now - ready_ns, 'heartbeat_age_ns': now - heartbeat_ns,
            'diagnostic_only': True}


def launch(args):
    require_release()
    if os.geteuid() != 0 or BASE.resolve(strict=True) != BASE or not BASE.is_dir():
        raise ValueError('root and canonical existing transfer directory required')
    for path in (LAUNCH, LOG, WORK, *(OWNER / name for name in ('command.json', 'owner.json', 'exit.json', 'run.log'))):
        if os.path.lexists(path):
            raise FileExistsError('fresh execution path required; preserve ' + str(path))
    source = read(SOURCE, SOURCE_BYTES)
    source_sha = hashlib.sha256(source).hexdigest()
    if len(source) != SOURCE_BYTES or source_sha != SOURCE_SHA256:
        raise ValueError('installed owner source differs from reviewed bytes')
    install_bytes = read(INSTALL, 16384)
    install = json.loads(install_bytes)
    if (install.get('schema') != 1 or install.get('kind') != 'saved_inspection_resume5_sources_install' or
            install.get('files') != INSTALLED_FILES or install.get('manifest_sha256') != TRANSFER_MANIFEST_SHA256 or
            install.get('execution_started') is not False):
        raise ValueError('source installation receipt differs')
    accepted_preflight = checked_preflight(source, hashlib.sha256(install_bytes).hexdigest())
    monitor_evidence = checked_monitor(args, accepted_preflight)
    receipt_fd = os.open(LAUNCH, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    receipt = {'schema': 1, 'kind': 'detached_saved_firstboot_execution_owner', 'started_utc': utc(),
               'status': 'LAUNCH_INCOMPLETE', 'command': COMMAND, 'wrapper': None,
               'launcher': process(os.getpid()), 'source_sha256': source_sha,
               'install_receipt_sha256': hashlib.sha256(install_bytes).hexdigest(),
               'wrapper_log': str(LOG), 'stdin': 'DEVNULL', 'stderr': 'STDOUT',
               'start_new_session': True, 'preflight_accepted': True, 'inspection_execution_requested': True,
               'accepted_preflight_evidence': accepted_preflight, 'process_observer_evidence': monitor_evidence}
    child = None
    try:
        log_fd = os.open(LOG, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(log_fd, 'wb') as stream:
            receipt['process_observer_launch_recheck'] = checked_monitor(args, accepted_preflight)
            child = subprocess.Popen(COMMAND, stdin=subprocess.DEVNULL, stdout=stream,
                                     stderr=subprocess.STDOUT, start_new_session=True, close_fds=True)
        receipt['wrapper'] = process(child.pid)
        receipt['status'] = 'SAVED_INSPECTION_EXECUTION_OWNER_LAUNCHED'
        if (receipt['wrapper']['session'] != child.pid or receipt['wrapper']['process_group'] != child.pid):
            raise ValueError('detached wrapper session identity differs')
    except BaseException as exc:
        receipt['status'] = 'LAUNCH_INCOMPLETE'
        receipt['error'] = type(exc).__name__ + ': ' + str(exc)
        if child is not None:
            receipt['spawned_wrapper_pid'] = child.pid
        # Never signal or wait here. A spawned wrapper may already own the
        # inspection; inspect this receipt and its own receipts before recovery.
    finally:
        receipt['finished_utc'] = utc()
        try:
            with os.fdopen(receipt_fd, 'w', closefd=False) as stream:
                json.dump(receipt, stream, indent=2)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            directory = os.open(BASE, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            os.close(receipt_fd)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--monitor-ready-sha256', required=True)
    parser.add_argument('--monitor-ready-bytes', required=True, type=int)
    parser.add_argument('--monitor-pid', required=True, type=int)
    parser.add_argument('--monitor-start-ticks', required=True, type=int)
    args = parser.parse_args(argv)
    try:
        receipt = launch(args)
        print(json.dumps(receipt, indent=2), flush=True)
        return 0 if receipt['status'] == 'SAVED_INSPECTION_EXECUTION_OWNER_LAUNCHED' else 2
    except Exception as exc:
        print(json.dumps({'schema': 1, 'status': 'SAVED_INSPECTION_EXECUTION_LAUNCH_REFUSED_OR_INCOMPLETE',
                          'error': type(exc).__name__ + ': ' + str(exc),
                          'preserve_existing_artifacts': True}), flush=True)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
