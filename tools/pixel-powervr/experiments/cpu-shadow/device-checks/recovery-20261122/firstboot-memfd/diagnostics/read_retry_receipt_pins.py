#!/usr/bin/env python3
"""Read only the completed memfd1 retry metadata; print byte/hash identities."""
import datetime
import hashlib
import os
from pathlib import Path
import stat

base = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
work = Path('/data/local/tmp/pixel-firstboot-guard-e9cc754-memfd1')
attempt = Path('/data/local/tmp/pixel-prep-e9cc754/attempts/07-0002')
paths = {
    'owner_exit': base / 'ios26-firstboot-owner-memfd1/exit.json',
    'guard_result': work / 'result.json',
    'guard_observations': work / 'guard-observations.json',
    'adapter_owner': base / 'ios26-firstboot-memfd1-adapter-execute.owner.json',
    'adapter_exit': base / 'ios26-firstboot-memfd1-adapter-execute.exit.json',
    'attempt_launch': attempt / 'launch.json',
    'attempt_vm_result': attempt / 'vm-result.json',
}
print('RETRY RECEIPT PINS', datetime.datetime.now(datetime.timezone.utc).isoformat())
print('observation_only=true live_qmp_called=false')
for label, path in paths.items():
    if path.resolve(strict=True) != path:
        raise ValueError('noncanonical metadata path')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 2 << 20:
            raise ValueError('nonordinary or oversized metadata')
        body = source.read((2 << 20) + 1)
    if len(body) > 2 << 20:
        raise ValueError('metadata exceeded bound')
    digest = hashlib.sha256(body).hexdigest()
    print(label + ' bytes=' + str(len(body)))
    print('sha_a=' + digest[:32])
    print('sha_b=' + digest[32:])
