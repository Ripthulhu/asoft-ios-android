#!/usr/bin/env python3
"""Detach the byte-verified firstboot owner after its read-only prerequisite checks.

No direct VM launch, wait, poll, signal, subreaper or process-group cleanup.
The detached wrapper is the unchanged guard's parent and owns its wait/cleanup.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess

BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
SOURCE = BASE / 'run-ios26-firstboot-owner-ebbc9c0.py'
INSTALL = BASE / 'ios26-firstboot-owner-ebbc9c0-install.json'
LAUNCH = BASE / 'ios26-firstboot-owner-ebbc9c0-launch.json'
LOG = BASE / 'ios26-firstboot-owner-ebbc9c0-wrapper.log'
OWNER = BASE / 'ios26-firstboot-owner-ebbc9c0'
WORK = Path('/data/local/tmp/pixel-firstboot-guard-e9cc754')
PYTHON = '/data/data/com.termux/files/usr/bin/python'
SOURCE_BYTES = 18957
SOURCE_SHA256 = '605f194f89cc59dd4025e587a0fc2239920b0850e089943bca9e9ea0656eee57'
COMMAND = [PYTHON, '-I', '-B', str(SOURCE), '--execute']


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
    if os.geteuid() != 0 or BASE.resolve(strict=True) != BASE or not BASE.is_dir():
        raise ValueError('root and canonical existing transfer directory required')
    for path in (LAUNCH, LOG, OWNER, WORK):
        if os.path.lexists(path):
            raise FileExistsError('fresh firstboot owner path required; preserve ' + str(path))
    source = read(SOURCE, SOURCE_BYTES)
    source_sha = hashlib.sha256(source).hexdigest()
    if len(source) != SOURCE_BYTES or source_sha != SOURCE_SHA256:
        raise ValueError('installed owner source differs from reviewed bytes')
    install_bytes = read(INSTALL, 16384)
    install = json.loads(install_bytes)
    if (install.get('schema') != 1 or install.get('kind') != 'firstboot_outer_owner_source_install' or
            install.get('source') != str(SOURCE) or install.get('bytes') != SOURCE_BYTES or
            install.get('sha256') != SOURCE_SHA256 or install.get('execution_started') is not False):
        raise ValueError('source installation receipt differs')
    namespace = {'__name__': 'reviewed_firstboot_owner', '__file__': str(SOURCE)}
    exec(compile(source, str(SOURCE), 'exec'), namespace)
    checked = namespace['prerequisites']()  # Read-only metadata/identity/resource gates; no guard preflight rerun.
    receipt_fd = os.open(LAUNCH, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    receipt = {'schema': 1, 'kind': 'detached_firstboot_execution_owner', 'started_utc': utc(),
               'status': 'LAUNCH_INCOMPLETE', 'command': COMMAND, 'wrapper': None,
               'launcher': process(os.getpid()), 'source_sha256': source_sha,
               'install_receipt_sha256': hashlib.sha256(install_bytes).hexdigest(),
               'wrapper_log': str(LOG), 'stdin': 'DEVNULL', 'stderr': 'STDOUT',
               'start_new_session': True, 'accepted_preflight_sha256': namespace['PREFLIGHT_SHA'], 'resources': checked['resources'],
               'firstboot_execution_requested': True}
    child = None
    try:
        log_fd = os.open(LOG, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(log_fd, 'wb') as stream:
            child = subprocess.Popen(COMMAND, stdin=subprocess.DEVNULL, stdout=stream,
                                     stderr=subprocess.STDOUT, start_new_session=True, close_fds=True)
        receipt['wrapper'] = process(child.pid)
        receipt['status'] = 'FIRSTBOOT_OWNER_LAUNCHED'
        if (receipt['wrapper']['session'] != child.pid or receipt['wrapper']['process_group'] != child.pid):
            raise ValueError('detached wrapper session identity differs')
    except BaseException as exc:
        receipt['status'] = 'LAUNCH_INCOMPLETE'
        receipt['error'] = type(exc).__name__ + ': ' + str(exc)
        if child is not None:
            receipt['spawned_wrapper_pid'] = child.pid
        # Never signal or wait here. A spawned wrapper may already own the
        # firstboot; inspect this receipt and its own receipts before recovery.
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
        return 0 if receipt['status'] == 'FIRSTBOOT_OWNER_LAUNCHED' else 2
    except Exception as exc:
        print(json.dumps({'schema': 1, 'status': 'FIRSTBOOT_LAUNCH_REFUSED_OR_INCOMPLETE',
                          'error': type(exc).__name__ + ': ' + str(exc),
                          'preserve_existing_artifacts': True}), flush=True)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
