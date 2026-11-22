import datetime
import json
import os
import time
from pathlib import Path

root = Path('/proc')
me = os.getpid()
limit = 8192
names = []
with os.scandir(root) as entries:
    for entry in entries:
        if entry.name.isascii() and entry.name.isdecimal():
            names.append(entry.name)
            if len(names) > limit:
                raise ValueError('process count exceeds bounded probe')
start = time.monotonic()
readable = vanished = denied = malformed = 0
for name in names:
    try:
        with open(root / name / 'stat', 'rb') as stream:
            raw = stream.read(4097)
        end = raw.rfind(b')')
        fields = raw[end + 2:].split()
        if len(raw) > 4096 or end < 1 or len(fields) < 20:
            malformed += 1
        else:
            int(fields[1]); int(fields[19])
            readable += 1
    except (FileNotFoundError, ProcessLookupError):
        vanished += 1
    except PermissionError:
        denied += 1
    except ValueError:
        malformed += 1
elapsed = time.monotonic() - start
self_raw = (root / str(me) / 'stat').read_text()
self_fields = self_raw[self_raw.rfind(')') + 2:].split()
status = dict(line.split(':', 1) for line in (root / str(me) / 'status').read_text().splitlines() if ':' in line)
print(json.dumps({
    'status': 'OBSERVER_PROC_STAT_SURFACE_READY' if denied == malformed == 0 else 'OBSERVER_PROC_STAT_SURFACE_GAPS',
    'observed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'query_pid': me,
    'query_start_ticks': int(self_fields[19]),
    'query_parent_matches': int(self_fields[1]) == os.getppid(),
    'numeric_process_count': len(names),
    'readable_stat_count': readable,
    'vanished_stat_count': vanished,
    'denied_stat_count': denied,
    'malformed_stat_count': malformed,
    'scan_milliseconds': round(elapsed * 1000, 3),
    'pid_tgid_match': int(status['Pid']) == int(status['Tgid']) == me,
    'required_pending_fields_present': all(k in status for k in ('SigPnd', 'ShdPnd')),
    'scope': 'aggregate stat-scan counts and self identity only; no writes or signals'
}, separators=(',', ':')))
