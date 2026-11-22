"""Read only the exact completed header diagnostic's compact result binding."""
import hashlib
import json
import os
from pathlib import Path
import stat

BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
SOURCE = BASE / 'run-ios26-hfs-header-diagnostic-resume2.py'
SOURCE_PIN = {'bytes': 22740, 'sha256': 'e79c0fbc472ae2a875164565802feffc4fad0a630571970f6e68d7251801bdcd'}
RESULT = BASE / 'ios26-hfs-header-diagnostic-resume2/result.json'


def read(path, limit):
    assert path.resolve(strict=True) == path, 'noncanonical input'
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as f:
        a = os.fstat(f.fileno())
        assert stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and a.st_uid == 0 and a.st_size <= limit, 'input identity differs'
        body = f.read(limit + 1)
        z = os.fstat(f.fileno())
    assert len(body) == a.st_size <= limit and (a.st_dev, a.st_ino, a.st_size, a.st_mtime_ns, a.st_ctime_ns) == (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns), 'input changed during read'
    return body


assert os.geteuid() == 0, 'root metadata reader required'
source = read(SOURCE, SOURCE_PIN['bytes'])
assert {'bytes': len(source), 'sha256': hashlib.sha256(source).hexdigest()} == SOURCE_PIN, 'diagnostic source differs'
body = read(RESULT, 65536)
r = json.loads(body)
assert r.get('schema') == 1 and r.get('kind') == 'readonly_hfs_header_diagnostic' and r.get('status') == 'READONLY_HFS_HEADERS_OBSERVED', 'completed diagnostic required'
assert r.get('source') == {'path': str(SOURCE), **SOURCE_PIN} and len(r.get('headers', [])) == 8 and len(r.get('tool_commands', [])) == 8, 'exact source and eight headers required'
assert all(x.get('reaped') is True and x.get('forced') is False and x.get('exit_code') == 0 and not x.get('cleanup_error') for x in r['tool_commands']), 'tool cleanup differs'
assert all(r.get(k) is True for k in ('diagnostic_only', 'disk_identities_unchanged', 'bound_metadata_unchanged', 'bound_tooling_unchanged')), 'preservation differs'
assert all(r.get(k) is False for k in ('inspection_success_claimed', 'guest_vm_started', 'mounted', 'replayed', 'repaired', 'fsck_run', 'full_disk_hashes_recomputed')), 'diagnostic boundary differs'
assert r.get('error') is None and r.get('preservation_error') is None, 'diagnostic error retained'
assert read(RESULT, 65536) == body and read(SOURCE, SOURCE_PIN['bytes']) == source, 'bound input changed'
d = hashlib.sha256(body)
print(json.dumps({'schema': 1, 'status': 'HFS_HEADER_RESULT_BINDING_READY', 'readonly': True, 'diagnostic_status': r['status'], 'result': {'path': str(RESULT), 'bytes': len(body), 'sha256': d.hexdigest(), 'digest_bytes': list(d.digest())}, 'headers': 8, 'source': SOURCE_PIN, 'inspection_success_claimed': False, 'full_disk_hashes_recomputed': False}, separators=(',', ':')), flush=True)
