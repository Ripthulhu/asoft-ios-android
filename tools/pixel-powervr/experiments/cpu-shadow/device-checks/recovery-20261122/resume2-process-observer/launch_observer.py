#!/usr/bin/env python3
"""Launch one independently owned diagnostic observer after actual preflight.

This launcher never creates the inspection owner or changes any target process.
The observer alone owns its files and finite deadline. No target signal or wait.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import types

BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
SOURCE = BASE / 'run-ios26-saved-inspection-resume2-observer.py'
SOURCE_PIN = {'bytes': 33930, 'sha256': '26125291eebced96468511cc060a95623315aba14e2fd8b63cd6056fed27b192'}
INSTALL = BASE / 'resume2-process-observer-install.json'
LAUNCH = BASE / 'ios26-saved-inspection-resume2-observer-launch.json'
LOG = BASE / 'ios26-saved-inspection-resume2-observer-wrapper.log'
OUT = BASE / 'ios26-saved-inspection-resume2-observer'
PYTHON = '/data/data/com.termux/files/usr/bin/python'


def source_bytes(path, limit):
    import stat
    if path.resolve(strict=True) != path:
        raise ValueError('noncanonical source/install path')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        a = os.fstat(stream.fileno())
        if not stat.S_ISREG(a.st_mode) or a.st_uid != 0 or a.st_nlink != 1 or a.st_size > limit:
            raise ValueError('nonordinary, non-root-owned or oversized source/install file')
        body = stream.read(limit + 1)
        b = os.fstat(stream.fileno())
    if len(body) != a.st_size or (a.st_dev, a.st_ino, a.st_size, a.st_mtime_ns, a.st_ctime_ns) != (b.st_dev, b.st_ino, b.st_size, b.st_mtime_ns, b.st_ctime_ns):
        raise ValueError('source/install changed during read')
    return body


def launch(preflight_sha256, preflight_bytes):
    if os.geteuid() != 0 or BASE.resolve(strict=True) != BASE:
        raise ValueError('root and canonical transfer base required')
    for path in (OUT, LAUNCH, LOG):
        if os.path.lexists(path):
            raise FileExistsError('fresh observer path required; preserve ' + str(path))
    body = source_bytes(SOURCE, SOURCE_PIN['bytes'])
    if len(body) != SOURCE_PIN['bytes'] or hashlib.sha256(body).hexdigest() != SOURCE_PIN['sha256']:
        raise ValueError('observer source differs from reviewed bytes')
    self_path = Path(__file__).resolve(strict=True)
    self_body = source_bytes(self_path, 64 << 10)
    self_pin = {'path': self_path.name, 'bytes': len(self_body), 'sha256': hashlib.sha256(self_body).hexdigest()}
    install_body = source_bytes(INSTALL, 32 << 10)
    install = json.loads(install_body)
    if (install.get('schema') != 1 or install.get('kind') != 'resume2_process_observer_sources_install' or
            install.get('execution_started') is not False or
            install.get('files') != [{'path': SOURCE.name, **SOURCE_PIN}, self_pin]):
        raise ValueError('observer installation receipt differs')
    monitor = types.ModuleType('verified_process_observer')
    monitor.__file__ = str(SOURCE)
    exec(compile(body, str(SOURCE), 'exec'), monitor.__dict__)
    bound = monitor.prerequisites(preflight_sha256, preflight_bytes)
    command = [PYTHON, '-I', '-B', str(SOURCE), '--preflight-sha256', preflight_sha256,
               '--preflight-bytes', str(preflight_bytes)]
    receipt = {'schema': 1, 'kind': 'detached_saved_inspection_process_observer',
               'status': 'LAUNCH_INCOMPLETE', 'started_utc': monitor.utc(), 'command': command,
               'launcher': monitor.Proc().snapshot(os.getpid()), 'observer': None,
               'source': {'path': str(SOURCE), **SOURCE_PIN}, 'launcher_source': self_pin,
               'preflight': bound['preflight'], 'inspection_owner_source': bound['inspection_owner_source'],
               'install_sha256': monitor.sha(install_body), 'output_directory': str(OUT),
               'wrapper_log': str(LOG), 'start_new_session': True, 'diagnostic_only': True,
               'inspection_execution_requested': False}
    fd = os.open(LAUNCH, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    child = None
    try:
        with os.fdopen(os.open(LOG, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
            child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
                                     start_new_session=True, close_fds=True)
        receipt['observer'] = monitor.Proc().snapshot(child.pid)
        if receipt['observer']['session'] != child.pid or receipt['observer']['pgrp'] != child.pid:
            raise ValueError('observer is not a separate session leader')
        receipt['status'] = 'PROCESS_OBSERVER_LAUNCHED'
    except BaseException as error:
        receipt['error'] = type(error).__name__ + ': ' + str(error)[:500]
        if child is not None:
            receipt['spawned_observer_pid'] = child.pid
        # Preserve receipts and let the bounded observer finish independently.
    finally:
        receipt['finished_utc'] = monitor.utc()
        with os.fdopen(fd, 'w') as stream:
            json.dump(receipt, stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        directory = os.open(BASE, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight-sha256', required=True)
    parser.add_argument('--preflight-bytes', required=True, type=int)
    args = parser.parse_args(argv)
    try:
        receipt = launch(args.preflight_sha256, args.preflight_bytes)
        print(json.dumps(receipt, indent=2), flush=True)
        return 0 if receipt['status'] == 'PROCESS_OBSERVER_LAUNCHED' else 2
    except Exception as error:
        print(json.dumps({'status': 'OBSERVER_LAUNCH_REFUSED_OR_INCOMPLETE',
                          'error': type(error).__name__ + ': ' + str(error)[:500],
                          'preserve_existing_artifacts': True, 'diagnostic_only': True}), flush=True)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
