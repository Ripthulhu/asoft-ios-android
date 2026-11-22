#!/usr/bin/env python3
"""Read-only projection of native PID diagnostics from the failed inspection.

No guest serial log or raw stderr line is printed. Known native source log
formats are converted to a bounded list of numeric fields for one target PID.
Missing matching logs do not identify the process or establish a benign exit.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat

PATH = Path('/data/local/tmp/pixel-saved-audit-e9cc754-resume1/a1/qemu-stderr.txt')
TARGET_PID = 13344
MAX_BYTES = 64 << 20
MAX_MATCHES = 64
NATIVE_SOURCE_SHA256 = 'a6c9a6110f6a34ddfdab5a4ce29bd1ecf176692de9f1d4f7546078734b0ca598'
PATTERNS = (
    ('worker_signalled', rb'^native-el0: stub (?P<stub>\d+) \(pid (?P<pid>\d+)\) killed by signal (?P<signal>\d+)(?: \(core\))?\s*$', False),
    ('worker_exited', rb'^native-el0: stub (?P<stub>\d+) \(pid (?P<pid>\d+)\) exited with (?P<exit_code>\d+)\s*$', False),
    ('slot_owner_mismatch', rb'^native-el0: slot (?P<stub>\d+)/(?P<vcpu>\d+) owned by pid (?P<owner_pid>\d+), stub pid (?P<stub_pid>\d+)\s*$', False),
    ('worker_signal_error', rb'^native-el0: tgkill stub (?P<stub>\d+) \(pid (?P<pid>\d+) tid (?P<tid>\d+)\):', True),
    ('worker_wait_10s', rb'^native-el0: vCPU (?P<vcpu>\d+) waits 10 s on stub (?P<stub>\d+) \(pid (?P<pid>\d+) tid (?P<tid>\d+)\):', True),
)
COMPILED = [(kind, re.compile(pattern), prefix) for kind, pattern, prefix in PATTERNS]
POOL = re.compile(rb'^native-el0: stubs (?P<configured>\d+) spawned (?P<spawned>\d+) bound (?P<bound>\d+) evictions (?P<evictions>\d+) inval-waits (?P<invalidation_waits>\d+) \(slow (?P<slow>\d+), timeouts (?P<timeouts>\d+)\)\s*$')


def identity(info):
    return {'device': info.st_dev, 'inode': info.st_ino, 'bytes': info.st_size,
            'mtime_ns': info.st_mtime_ns, 'ctime_ns': info.st_ctime_ns}


def project(line):
    for kind, pattern, prefix in COMPILED:
        match = pattern.match(line) if prefix else pattern.fullmatch(line)
        if match:
            fields = {key: int(value) for key, value in match.groupdict().items()}
            return {'kind': kind, **fields}
    return None


def main():
    if PATH.resolve(strict=True) != PATH:
        raise ValueError('noncanonical failed-inspection stderr path')
    matches, pool, native_mentions, pid_format_lines, overlong_lines = [], None, 0, 0, 0
    digest, offset, continuation = hashlib.sha256(), 0, False
    with os.fdopen(os.open(PATH, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > MAX_BYTES:
            raise ValueError('stderr is not bounded ordinary evidence')
        while True:
            part = stream.readline(4097)
            if not part:
                break
            digest.update(part)
            offset_before, offset = offset, offset + len(part)
            if offset > MAX_BYTES:
                raise ValueError('stderr grew past bound')
            if not continuation:
                row = project(part)
                if row is not None:
                    pid_format_lines += 1
                    if TARGET_PID in [value for key, value in row.items() if key in ('pid', 'owner_pid', 'stub_pid')]:
                        if len(matches) >= MAX_MATCHES:
                            raise ValueError('matching native PID diagnostics exceeded bound')
                        matches.append({'byte_offset': offset_before, **row})
                if part.startswith(b'native-el0:') and re.search(rb'(?<!\d)' + str(TARGET_PID).encode() + rb'(?!\d)', part):
                    native_mentions += 1
                summary = POOL.fullmatch(part)
                if summary:
                    pool = {key: int(value) for key, value in summary.groupdict().items()}
                if len(part) == 4097 and not part.endswith(b'\n'):
                    overlong_lines += 1
            continuation = not part.endswith(b'\n')
        after = os.fstat(stream.fileno())
    if identity(before) != identity(after) or identity(PATH.stat()) != identity(before) or offset != before.st_size:
        raise ValueError('stderr identity changed while reading')
    result = {'schema': 1, 'status': 'READONLY_NATIVE_PID_OBSERVATION',
              'observed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'source': str(PATH), 'source_identity': identity(before), 'source_sha256': digest.hexdigest(),
              'target_pid': TARGET_PID, 'native_format_source_sha256': NATIVE_SOURCE_SHA256,
              'matching_native_pid_fields': matches, 'recognized_pid_format_lines': pid_format_lines,
              'native_lines_mentioning_target': native_mentions, 'latest_pool_summary': pool,
              'overlong_lines_not_fully_projected': overlong_lines,
              'factory_startup_pid_not_logged_by_this_native_source': True,
              'no_match_does_not_classify_process': True,
              'raw_guest_or_stderr_lines_printed': False, 'process_signal_requested': False,
              'boot_complete': False, 'gpu_path_complete': False, 'app_gate_changed': False}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
