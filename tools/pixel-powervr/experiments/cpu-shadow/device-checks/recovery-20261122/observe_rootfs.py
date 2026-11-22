"""Bounded, read-only observation of the existing native rootfs attempt."""
import datetime
import json
import os
import re
import stat
from pathlib import Path

attempt = Path('/data/local/tmp/pixel-prep-e9cc754/attempts/05-0002')
pid, expected_start, limit = 28210, 5491577, 262144

def proc_stat():
    fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    return {'state': fields[0], 'utime': int(fields[11]),
            'stime': int(fields[12]), 'threads': int(fields[17]),
            'start': int(fields[19])}

def tail(name):
    fd = os.open(attempt / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise RuntimeError('not a regular log file')
        offset = max(0, info.st_size - limit)
        stream.seek(offset)
        data = stream.read(limit)
    if offset:
        data = data.split(b'\n', 1)[-1]
    return data.decode('utf-8', 'replace').replace('\r', ''), {
        'bytes': info.st_size, 'mtime_ns': info.st_mtime_ns,
        'tail_offset': offset, 'tail_bytes': len(data)}

report = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
try:
    before = proc_stat()
    if before['start'] == expected_start:
        io_text = Path(f'/proc/{pid}/io').read_text()
        io_values = {key: int(value) for key, value in re.findall(
            r'^(rchar|wchar|read_bytes|write_bytes):\s+(\d+)$', io_text, re.M)}
        after = proc_stat()
        if after['start'] == expected_start:
            report['process'] = after
            report['io'] = io_values
        else:
            report['identity'] = 'changed during read'
    else:
        report['identity'] = 'mismatch; counters omitted'
except (OSError, ValueError, IndexError):
    report['identity'] = 'process unavailable'

serial, serial_meta = tail('serial.txt')
stderr, stderr_meta = tail('qemu-stderr.txt')
report['serial'] = serial_meta
report['stderr'] = stderr_meta
report['progress'] = re.findall(
    r'^ASOFT: progress (\d+) copying iOS onto its disk'
    r'(?: \((\d+\.\d+) GB so far\))?\s*$', serial, re.M)[-3:]
report['phases'] = re.findall(
    r'^(\d\d:\d\d:\d\d) copying /tmp/mkroot26/(sysos|appos|os)'
    r'(?:/root)? -> /[^\n]*$', serial, re.M)[-3:]
report['trustcache'] = bool(re.search(
    r'^ASOFT: progress 97 its trust cache\s*$', serial, re.M))
report['done'] = re.findall(r'^ASOFT: done (-?\d+)\s*$', serial, re.M)
report['out'] = re.findall(r'^ASOFT: out (\d+)\s*$', serial, re.M)
report['samples'] = re.findall(
    r'^el-sample t=(\d+)s all:[^\n]*\| native (\d+) ms[^\n]*? enters (\d+)',
    stderr, re.M)[-3:]
report['native_final'] = re.findall(
    r'^native-el0: enters (\d+) svc (\d+)', stderr, re.M)[-2:]
info = (attempt / 'files/root26.qcow2').stat()
report['container'] = {'bytes': info.st_size, 'allocated': info.st_blocks * 512,
                       'mtime_ns': info.st_mtime_ns}
print('PROGRESS_SNAPSHOT_BEGIN')
for key, value in report.items():
    print(key + ': ' + json.dumps(value, separators=(',', ':')))
print('PROGRESS_SNAPSHOT_END')
