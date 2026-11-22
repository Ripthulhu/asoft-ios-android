#!/usr/bin/env python3
"""Bounded read-only preflight observation; reads no guest/serial/VM logs."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat

BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
SOURCE = BASE / 'run-ios26-partition-audit-ebbc9c0.py'
INSTALL = BASE / 'ios26-partition-audit-ebbc9c0-install.json'
LAUNCH = BASE / 'ios26-partition-audit-ebbc9c0-preflight-launch.json'
WRAPPER_LOG = BASE / 'ios26-partition-audit-ebbc9c0-preflight-wrapper.log'
OWNER = BASE / 'ios26-partition-audit-ebbc9c0-owner'
PREP = Path('/data/local/tmp/pixel-prep-e9cc754')
RUNNER = Path('/data/local/tmp/pixel-prep-runner-f4d64db')
AUDITOR = Path('/data/local/tmp/pixel-boot-checks-ebbc9c0/auditor')
WORK = Path('/data/local/tmp/pixel-audit-e9cc754')
PYTHON = '/data/data/com.termux/files/usr/bin/python'
SOURCE_BYTES = 18144
SOURCE_SHA256 = 'af4b1478e37b52cf223bc86bf41df2c23f83d31dd5de287cfaabe64d0983bfe7'
OUTER_COMMAND = [PYTHON, '-I', '-B', str(SOURCE), '--preflight']
AUDITOR_COMMAND = [PYTHON, '-B', str(AUDITOR / 'audit_ios26_partition.py'),
                   '--prep-work', str(PREP), '--runner-dir', str(RUNNER), '--work', str(WORK)]
STAGES = ['shared-fetch', 'shared-unpack', 'shared-build', 'ios26-fetch',
          'ios26-decrypt', 'ios26-rootfs', 'ios26-partition']


def bounded(path, limit):
    if path.resolve(strict=True) != path:
        raise ValueError('noncanonical metadata path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
            raise ValueError('nonordinary or oversized metadata')
        body = stream.read(limit + 1)
        if len(body) > limit:
            raise ValueError('metadata exceeded bound')
    return body


def read_record(path, limit=2 << 20):
    result = {'path': str(path), 'exists': os.path.lexists(path)}
    if not result['exists']:
        return result, None
    try:
        body = bounded(path, limit)
        result.update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        return result, json.loads(body)
    except Exception as exc:
        result['read_error'] = (type(exc).__name__ + ': ' + str(exc))[:384]
        return result, None


def dictionary(value):
    return value if type(value) is dict else {}


def scalar(value):
    if value is None or type(value) in (bool, int, float):
        return value
    if type(value) is str:
        return value[:512]
    return '<non-scalar>'


def select(value, names):
    value = dictionary(value)
    return {name: scalar(value[name]) for name in names if name in value}


def identity(record):
    record = dictionary(record)
    pid, starttime = record.get('pid'), record.get('starttime')
    if type(pid) is not int or not 0 < pid < 1 << 31 or type(starttime) is not int or starttime < 0:
        return {'recorded': False, 'identity_absent': False}
    result = {'recorded': True, 'expected': {'pid': pid, 'starttime': starttime}}
    try:
        with (Path('/proc') / str(pid) / 'stat').open('rb') as stream:
            raw = stream.read(4097)
        if len(raw) > 4096:
            raise ValueError('process stat exceeded bound')
        fields = raw[raw.rfind(b')') + 2:].split()
        current = {'pid': pid, 'starttime': int(fields[19]), 'state': fields[0].decode('ascii'),
                   'parent_pid': int(fields[1]), 'process_group': int(fields[2]), 'session': int(fields[3])}
        matches = current['starttime'] == starttime
        result.update(current=current, identity_present=matches, identity_absent=not matches,
                      pid_occupied_by_other_identity=not matches)
    except FileNotFoundError:
        result.update(current=None, identity_present=False, identity_absent=True,
                      pid_occupied_by_other_identity=False)
    except Exception as exc:
        result.update(identity_absent=False, read_error=(type(exc).__name__ + ': ' + str(exc))[:384])
    return result


def source_record():
    result = {'path': str(SOURCE), 'exists': os.path.lexists(SOURCE), 'expected_sha256': SOURCE_SHA256}
    try:
        body = bounded(SOURCE, SOURCE_BYTES)
        result.update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        result['matches_reviewed_source'] = len(body) == SOURCE_BYTES and result['sha256'] == SOURCE_SHA256
    except Exception as exc:
        result.update(matches_reviewed_source=False, read_error=(type(exc).__name__ + ': ' + str(exc))[:384])
    return result


def resources():
    result = {'fresh_helper_min_available_bytes': 2816 << 20}
    try:
        with Path('/proc/meminfo').open('rb') as stream:
            data = stream.read(65537)
        if len(data) > 65536:
            raise ValueError('meminfo exceeded bound')
        match = re.search(rb'^MemAvailable:\s+(\d+) kB$', data, re.M)
        if match is None:
            raise ValueError('MemAvailable missing')
        result['mem_available_bytes'] = int(match[1]) * 1024
        result['fresh_helper_memory_floor_met_at_observation'] = result['mem_available_bytes'] >= 2816 << 20
        disk = os.statvfs(BASE)
        result['free_bytes'] = disk.f_bavail * disk.f_frsize
    except Exception as exc:
        result['read_error'] = (type(exc).__name__ + ': ' + str(exc))[:384]
    return result


def observe():
    result = {'schema': 1, 'observed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'observation_only': True, 'audit_pass_claimed': False,
              'execution_prerequisites_rechecked': False, 'source': source_record(),
              'resources': resources(), 'audit_work_exists': os.path.lexists(WORK)}
    install_meta, install = read_record(INSTALL, 16384)
    install_meta['selected'] = select(install, ('kind', 'installed_utc', 'source', 'bytes', 'sha256', 'execution_started'))
    result['installation'] = install_meta
    launch_meta, launched = read_record(LAUNCH, 32768)
    launched = dictionary(launched)
    launch_meta['selected'] = select(launched, ('status', 'started_utc', 'finished_utc', 'source_sha256',
                       'install_receipt_sha256', 'start_new_session', 'audit_execution_requested', 'error'))
    launch_meta['exact_outer_command'] = launched.get('command') == OUTER_COMMAND
    launch_meta['wrapper'] = identity(launched.get('wrapper'))
    result['detached_launch'] = launch_meta
    owner_meta, owner = read_record(OWNER / 'preflight-owner.json', 32768)
    owner = dictionary(owner)
    owner_meta['selected'] = select(owner, ('schema', 'started_utc'))
    owner_meta['exact_auditor_command'] = owner.get('command') == AUDITOR_COMMAND
    owner_meta['wrapper'] = identity(owner.get('wrapper'))
    owner_meta['auditor'] = identity(owner.get('runner'))
    result['preflight_owner'] = owner_meta
    exit_meta, exited = read_record(OWNER / 'preflight-exit.json', 32768)
    exited = dictionary(exited)
    exit_meta['selected'] = select(exited, ('started_utc', 'finished_utc', 'exit_code', 'owner_exit_code',
                        'accepted', 'runner_started', 'runner_reaped', 'forced_runner', 'wrapper_error',
                        'stdout_sha256', 'requires_owned_process_recheck'))
    exit_meta['cleanup_errors_empty'] = exited.get('cleanup_errors') == []
    exit_meta['exact_auditor_command'] = exited.get('command') == AUDITOR_COMMAND
    result['preflight_exit'] = exit_meta
    public_meta, public = read_record(OWNER / 'preflight.json')
    public, session = dictionary(public), dictionary(dictionary(public).get('session'))
    checkpoints = dictionary(session.get('checkpoints'))
    public_meta['selected'] = select(public, ('schema', 'status', 'work', 'execution_verified',
                              'boot_complete', 'gpu_path_complete', 'app_gate_changed'))
    public_meta['session_selected'] = select(session, ('kind', 'prep_work', 'runner_dir', 'prep_session_sha256',
                                      'readonly', 'native_required', 'tcg_retry', 'policy_sha256', 'tooling_manifest_sha256'))
    public_meta['checkpoint_count'] = len(checkpoints)
    public_meta['exact_seven_checkpoint_names'] = set(checkpoints) == {
        str(PREP / 'checkpoints' / (stage + '.json')) for stage in STAGES}
    public_meta['stdout_hash_matches_exit_receipt'] = (
        type(public_meta.get('sha256')) is str and public_meta.get('sha256') == exited.get('stdout_sha256'))
    result['preflight_output'] = public_meta
    command_meta, saved_command = read_record(OWNER / 'preflight-command.json', 16384)
    result['command_receipt'] = dict(command_meta, exact_auditor_command=saved_command == AUDITOR_COMMAND)
    # Only parse the outer wrapper's bounded JSON refusal, never guest or VM logs.
    refusal_meta, refusal = read_record(WRAPPER_LOG, 16384)
    result['wrapper_output'] = {k: v for k, v in refusal_meta.items() if k != 'read_error'}
    if dictionary(refusal).get('status') == 'OWNER_REFUSED':
        result['wrapper_output']['selected_refusal'] = select(refusal, ('status', 'error'))
    absent = all(row.get('identity_absent') is True for row in
                 (launch_meta['wrapper'], owner_meta['wrapper'], owner_meta['auditor']))
    consistent = bool(result['source']['matches_reviewed_source'] and
        launched.get('status') == 'PREFLIGHT_OWNER_LAUNCHED' and launch_meta['exact_outer_command'] and
        saved_command == AUDITOR_COMMAND and owner.get('command') == exited.get('command') == AUDITOR_COMMAND and
        owner.get('started_utc') == exited.get('started_utc') and
        all(owner.get(k) == exited.get(k) for k in ('wrapper', 'runner')) and
        exited.get('exit_code') == exited.get('owner_exit_code') == 0 and exited.get('accepted') is True and
        exited.get('runner_started') is True and exited.get('runner_reaped') is True and
        exited.get('forced_runner') is False and exited.get('wrapper_error') is None and
        exited.get('cleanup_errors') == [] and exited.get('finished_utc') and
        public_meta['stdout_hash_matches_exit_receipt'] and public.get('status') == 'PREFLIGHT_READY' and
        public.get('work') == str(WORK) and public.get('execution_verified') is False and
        public_meta['exact_seven_checkpoint_names'] and session.get('readonly') is True and
        session.get('native_required') is True and session.get('tcg_retry') is False and
        all(public.get(k) is False for k in ('boot_complete', 'gpu_path_complete', 'app_gate_changed')))
    result['saved_preflight_receipt_consistent'] = consistent
    result['recorded_preflight_identities_absent'] = absent
    running = any(row.get('identity_present') is True for row in
                  (launch_meta['wrapper'], owner_meta['wrapper'], owner_meta['auditor']))
    result['status'] = ('PREFLIGHT_RUNNING_OR_FINALIZING' if running else
                        'PREFLIGHT_COMPLETE_ACCEPTED' if consistent and absent else
                        'PREFLIGHT_EXIT_REQUIRES_REVIEW' if exit_meta['exists'] else
                        'PREFLIGHT_OWNER_ABSENT_WITHOUT_COMPLETION' if launch_meta['wrapper'].get('identity_absent') else
                        'PREFLIGHT_NOT_OBSERVED')
    return result


if __name__ == '__main__':
    print(json.dumps(observe(), indent=2), flush=True)
