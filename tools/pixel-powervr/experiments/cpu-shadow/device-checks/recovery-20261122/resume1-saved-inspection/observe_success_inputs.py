#!/usr/bin/env python3
"""Read-only selected pin observation, only after accepted resume1 firstboot."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import stat

BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
OWNER = BASE / 'ios26-firstboot-owner-resume1'
WORK = Path('/data/local/tmp/pixel-firstboot-guard-e9cc754-resume1')
PREP = Path('/data/local/tmp/pixel-prep-e9cc754')


def read(path):
    if path.resolve(strict=True) != path:
        raise ValueError('noncanonical input')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 4 << 20:
            raise ValueError('nonordinary or oversized input')
        body = stream.read((4 << 20) + 1)
    if len(body) > 4 << 20:
        raise ValueError('input exceeded bound')
    return body


def main():
    try:
        owner = json.loads(read(OWNER / 'owner.json'))
        exited = json.loads(read(OWNER / 'exit.json'))
        guard = json.loads(read(WORK / 'result.json'))
        if (exited.get('accepted') is not True or exited.get('exit_code') != 0 or exited.get('owner_exit_code') != 0 or
                exited.get('guard_reaped') is not True or exited.get('forced_guard') is not False or
                exited.get('wrapper_error') is not None or exited.get('cleanup_errors') != [] or
                guard.get('status') != 'GUARDED_FIRSTBOOT_COMPLETE' or guard.get('checkpoint_accepted_by_guard') is not True or
                guard.get('actual_attempt', {}).get('attempt') != str(PREP / 'attempts/07-0004')):
            raise ValueError('resume1 firstboot is not accepted and cleanly reaped')
        for key in ('wrapper', 'guard'):
            identity = owner[key]
            path = Path('/proc') / str(identity['pid']) / 'stat'
            try:
                raw = path.read_bytes()
                ticks = int(raw[raw.rfind(b')') + 2:].split()[19])
                if ticks == identity['starttime']:
                    raise ValueError('firstboot ' + key + ' is still present')
            except FileNotFoundError:
                pass
        files = [BASE / 'run-ios26-firstboot-owner-resume1.py', BASE / 'run-ios26-firstboot-memfd-adapter-resume1.py',
                 *(OWNER / name for name in ('owner.json', 'command.json', 'exit.json')),
                 *(WORK / name for name in ('guard-session.json', 'guard-observations.json', 'result.json')),
                 PREP / 'checkpoints/ios26-firstboot.json']
        pins = {}
        for path in files:
            body = read(path)
            digest = hashlib.sha256(body).digest()
            pins[str(path)] = {'bytes': len(body), 'sha256': digest.hex(), 'digest_bytes': list(digest)}
        print(json.dumps({'schema': 1, 'status': 'SAVED_INSPECTION_BINDING_READY', 'readonly': True,
                          'observed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'files': pins}, indent=2))
        return 0
    except Exception as error:
        print(json.dumps({'schema': 1, 'status': 'SAVED_INSPECTION_NOT_READY', 'readonly': True,
                          'error': type(error).__name__ + ': ' + str(error)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
