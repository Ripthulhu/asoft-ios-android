#!/usr/bin/env python3
"""Detach the reviewed saved-inspection execution owner after accepted preflight checks.

No direct VM launch, wait, poll, signal, subreaper or process-group cleanup.
The detached wrapper is the inspector's parent and owns its wait/cleanup.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess

BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
SOURCE = BASE / 'run-ios26-saved-inspection-resume1.py'
INSTALL = BASE / 'saved-inspection-resume1-install.json'
LAUNCH = BASE / 'ios26-saved-inspection-resume1-execute-launch.json'
LOG = BASE / 'ios26-saved-inspection-resume1-execute-wrapper.log'
OWNER = BASE / 'ios26-saved-inspection-resume1-owner'
WORK = Path('/data/local/tmp/pixel-saved-audit-e9cc754-resume1')
PYTHON = '/data/data/com.termux/files/usr/bin/python'
SOURCE_BYTES = 25168
SOURCE_SHA256 = '87526ee42417108f46a8ca03b3fece1cd154f2c439a9c6492f20c97fd6981bb9'
PREFLIGHT_SHA256 = '84b31f4f08744f6adeb20ab5af308b1d10c839803c051d4bba577201a4ad3760'
PREFLIGHT_BYTES = 9070
COMMAND = [PYTHON, '-I', '-B', str(SOURCE), '--execute', '--preflight-sha256', PREFLIGHT_SHA256, '--preflight-bytes', str(PREFLIGHT_BYTES)]
PREFLIGHT_LAUNCH = BASE / 'ios26-saved-inspection-resume1-preflight-launch.json'
TRANSFER_MANIFEST_SHA256 = 'cc5cb704e57d274676130c4fcb634cd4ace5232bb9be83a059548cbb60022ce4'
INSTALLED_FILES = [{'path': 'run-ios26-saved-inspection-resume1.py', 'bytes': 25168, 'sha256': '87526ee42417108f46a8ca03b3fece1cd154f2c439a9c6492f20c97fd6981bb9'}, {'path': 'launch-ios26-saved-inspection-resume1-preflight.py', 'bytes': 5926, 'sha256': 'e4b78fbb504ba044426c0a3feea1ae6dfec8b740f48f3d267be43a7b58e26fda'}]


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


def launch():
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
    if (install.get('schema') != 1 or install.get('kind') != 'saved_inspection_resume1_sources_install' or
            install.get('files') != INSTALLED_FILES or install.get('manifest_sha256') != TRANSFER_MANIFEST_SHA256 or
            install.get('execution_started') is not False):
        raise ValueError('source installation receipt differs')
    accepted_preflight = checked_preflight(source, hashlib.sha256(install_bytes).hexdigest())
    receipt_fd = os.open(LAUNCH, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    receipt = {'schema': 1, 'kind': 'detached_saved_firstboot_execution_owner', 'started_utc': utc(),
               'status': 'LAUNCH_INCOMPLETE', 'command': COMMAND, 'wrapper': None,
               'launcher': process(os.getpid()), 'source_sha256': source_sha,
               'install_receipt_sha256': hashlib.sha256(install_bytes).hexdigest(),
               'wrapper_log': str(LOG), 'stdin': 'DEVNULL', 'stderr': 'STDOUT',
               'start_new_session': True, 'preflight_accepted': True, 'inspection_execution_requested': True,
               'accepted_preflight_evidence': accepted_preflight}
    child = None
    try:
        log_fd = os.open(LOG, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(log_fd, 'wb') as stream:
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


def main():
    try:
        receipt = launch()
        print(json.dumps(receipt, indent=2), flush=True)
        return 0 if receipt['status'] == 'SAVED_INSPECTION_EXECUTION_OWNER_LAUNCHED' else 2
    except Exception as exc:
        print(json.dumps({'schema': 1, 'status': 'SAVED_INSPECTION_EXECUTION_LAUNCH_REFUSED_OR_INCOMPLETE',
                          'error': type(exc).__name__ + ': ' + str(exc),
                          'preserve_existing_artifacts': True}), flush=True)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
