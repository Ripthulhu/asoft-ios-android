"""Read-only hashes of the five already identified, closed result metadata files."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import stat

BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
WORK = Path('/data/local/tmp/pixel-saved-audit-e9cc754-resume2')
FILES = [
    (BASE / 'ios26-saved-inspection-resume2-owner/exit.json', 906),
    (WORK / 'result.json', 3705),
    (WORK / 'a1/vm-result.json', 1266),
    (WORK / 'a1/files/inspection/result.json', 1972),
    (WORK / 'a1/expected-policy.json', 271),
]
if os.geteuid() != 0:
    raise ValueError('root required')
rows = []
for index, (path, expected_size) in enumerate(FILES):
    if path.resolve(strict=True) != path:
        raise ValueError('noncanonical metadata path')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_uid != 0 or before.st_nlink != 1 or before.st_size != expected_size:
            raise ValueError('metadata size or ownership changed')
        body = stream.read(expected_size + 1)
        after = os.fstat(stream.fileno())
    current = path.stat()
    signature = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
    if len(body) != expected_size or not signature(before) == signature(after) == signature(current):
        raise ValueError('metadata changed during read')
    value = json.loads(body)
    if not isinstance(value, dict):
        raise ValueError('expected metadata object')
    digest = hashlib.sha256(body)
    rows.append((index, expected_size, digest.hexdigest(), list(digest.digest())))
print('GUEST BOUNDARY METADATA HASHES; READ ONLY')
print('observed_utc=' + datetime.datetime.now(datetime.timezone.utc).isoformat())
for index, size, hexdigest, digest_bytes in rows:
    print('index=' + str(index) + ' bytes=' + str(size))
    print(hexdigest)
    print(json.dumps(digest_bytes, separators=(',', ':')))
