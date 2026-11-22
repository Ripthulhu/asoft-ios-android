#!/usr/bin/env python3
"""Read the retained post-stop QMP metadata only; no live QMP or process action."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import stat

def read(path, limit):
    if path.resolve(strict=True) != path: raise ValueError('noncanonical metadata path')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
            raise ValueError('nonordinary or oversized metadata')
        body = source.read(limit + 1)
    if len(body) > limit: raise ValueError('metadata exceeded bound')
    return body


work = Path('/data/local/tmp/pixel-firstboot-guard-e9cc754-memfd1')
body = read(work / 'guard-observations.json', 131072)
result_body = read(work / 'result.json', 2 << 20)
record = json.loads(body)
if record.get('schema') != 1: raise ValueError('unexpected observations schema')
events = record.get('post_stop_blockstats')
if type(events) is not list or len(events) > 4: raise ValueError('unexpected bounded event inventory')
rendered = json.dumps(events, separators=(',', ':'), ensure_ascii=True)
if len(rendered) > 32768: raise ValueError('event projection exceeded output bound')
print('SAVED COUNTER EVENTS', datetime.datetime.now(datetime.timezone.utc).isoformat())
print('work=' + str(work))
for label, raw in (('observations', body), ('guard_result', result_body)):
    digest = hashlib.sha256(raw).hexdigest()
    print(label + '_bytes=' + str(len(raw)))
    print(label + '_sha_a=' + digest[:32])
    print(label + '_sha_b=' + digest[32:])
print('event_count=' + str(len(events)) + ' observation_only=true live_qmp_called=false')
print('post_stop_blockstats=' + rendered, flush=True)
