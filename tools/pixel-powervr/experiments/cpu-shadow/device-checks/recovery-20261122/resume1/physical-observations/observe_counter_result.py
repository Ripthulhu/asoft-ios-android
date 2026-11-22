"""Read the pinned successful firstboot guard's selected counter metadata."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import stat

p = Path('/data/local/tmp/pixel-firstboot-guard-e9cc754-resume1/result.json')
if p.resolve(strict=True) != p:
    raise ValueError('noncanonical guard result')
with os.fdopen(os.open(p, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as f:
    s = os.fstat(f.fileno())
    if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or s.st_size != 33910:
        raise ValueError('guard result identity differs')
    body = f.read(33911)
if len(body) != 33910 or hashlib.sha256(body).hexdigest() != '8d2731493b0ccdad2056677e56774f11718d9d01fb35e895023963d98847f8e3':
    raise ValueError('guard result bytes differ')
result = json.loads(body)
if result.get('status') != 'GUARDED_FIRSTBOOT_COMPLETE' or result.get('checkpoint_accepted_by_guard') is not True:
    raise ValueError('firstboot not accepted')
print('PINNED FIRSTBOOT COUNTER RESULT', datetime.datetime.now(datetime.timezone.utc).isoformat())
for event in result['post_stop_blockstats']:
    print('stop_event', json.dumps({k: event.get(k) for k in ('status', 'stop_acknowledged', 'failed_io_counters_zero', 'stop_internal_flush_return_observed', 'error')}))
    print('counter_check', json.dumps(event.get('counter_check'), separators=(',', ':')))
for event in result['supervision']:
    print('supervision', json.dumps({k: event.get(k) for k in ('stage', 'status', 'original_supervision_status', 'guest_sync_answered', 'error')}))
print('readonly_counter_observation_complete')
