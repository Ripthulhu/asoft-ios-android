#!/usr/bin/env python3
"""Detach exactly one reviewed preflight owner and return immediately.

No audit execution, wait, poll, signal, subreaper or process-group cleanup.
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
SOURCE = BASE / 'run-ios26-saved-inspection-resume5.py'
INSTALL = BASE / 'saved-inspection-resume5-install.json'
LAUNCH = BASE / 'ios26-saved-inspection-resume5-preflight-launch.json'
LOG = BASE / 'ios26-saved-inspection-resume5-preflight-wrapper.log'
OWNER = BASE / 'ios26-saved-inspection-resume5-owner'
WORK = Path('/data/local/tmp/pixel-saved-audit-e9cc754-resume5')
PYTHON = '/data/data/com.termux/files/usr/bin/python'
SOURCE_BYTES = 60564
SOURCE_SHA256 = 'dbb570dc9b3354a5d7c4eb218883ab22f25afe24757c429e46cc7c04de1baa63'
COMMAND = [PYTHON, '-I', '-B', str(SOURCE), '--preflight']


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


def launch():
    if not (type(SOURCE_BYTES) is int and 0 < SOURCE_BYTES <= 256 << 10 and
            type(SOURCE_SHA256) is str and len(SOURCE_SHA256) == 64 and
            all(value in '0123456789abcdef' for value in SOURCE_SHA256)):
        raise ValueError('UNRELEASED: exact reviewed resume5 owner source required')
    if os.geteuid() != 0 or BASE.resolve(strict=True) != BASE or not BASE.is_dir():
        raise ValueError('root and canonical existing transfer directory required')
    for path in (LAUNCH, LOG, OWNER, WORK):
        if os.path.lexists(path):
            raise FileExistsError('fresh preflight path required; preserve ' + str(path))
    source = read(SOURCE, SOURCE_BYTES)
    source_sha = hashlib.sha256(source).hexdigest()
    if len(source) != SOURCE_BYTES or source_sha != SOURCE_SHA256:
        raise ValueError('installed owner source differs from reviewed bytes')
    install_bytes = read(INSTALL, 16384)
    install = json.loads(install_bytes)
    if (install.get('schema') != 1 or install.get('kind') != 'saved_inspection_resume5_sources_install' or
            install.get('execution_started') is not False or type(install.get('files')) is not list or
            sum(row == {'path': SOURCE.name, 'bytes': SOURCE_BYTES, 'sha256': SOURCE_SHA256}
                for row in install['files']) != 1):
        raise ValueError('source installation receipt differs')
    receipt_fd = os.open(LAUNCH, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    receipt = {'schema': 1, 'kind': 'detached_saved_firstboot_preflight_owner', 'started_utc': utc(),
               'status': 'LAUNCH_INCOMPLETE', 'command': COMMAND, 'wrapper': None,
               'launcher': process(os.getpid()), 'source_sha256': source_sha,
               'install_receipt_sha256': hashlib.sha256(install_bytes).hexdigest(),
               'wrapper_log': str(LOG), 'stdin': 'DEVNULL', 'stderr': 'STDOUT',
               'start_new_session': True, 'preflight_accepted': False, 'inspection_execution_requested': False}
    child = None
    try:
        log_fd = os.open(LOG, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(log_fd, 'wb') as stream:
            child = subprocess.Popen(COMMAND, stdin=subprocess.DEVNULL, stdout=stream,
                                     stderr=subprocess.STDOUT, start_new_session=True, close_fds=True)
        receipt['wrapper'] = process(child.pid)
        receipt['status'] = 'PREFLIGHT_OWNER_LAUNCHED'
        if (receipt['wrapper']['session'] != child.pid or receipt['wrapper']['process_group'] != child.pid):
            raise ValueError('detached wrapper session identity differs')
    except BaseException as exc:
        receipt['status'] = 'LAUNCH_INCOMPLETE'
        receipt['error'] = type(exc).__name__ + ': ' + str(exc)
        if child is not None:
            receipt['spawned_wrapper_pid'] = child.pid
        # Never signal or wait here. A spawned wrapper may already own the
        # preflight; inspect this receipt and its own receipts before recovery.
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
        return 0 if receipt['status'] == 'PREFLIGHT_OWNER_LAUNCHED' else 2
    except Exception as exc:
        print(json.dumps({'schema': 1, 'status': 'PREFLIGHT_LAUNCH_REFUSED_OR_INCOMPLETE',
                          'error': type(exc).__name__ + ': ' + str(exc),
                          'preserve_existing_artifacts': True}), flush=True)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
