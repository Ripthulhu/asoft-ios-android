#!/usr/bin/env python3
"""Read the retained post-stop QMP metadata only; no live QMP or process action."""
import argparse
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
parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--compact', action='store_true')
args = parser.parse_args()
if not args.compact:
    print('post_stop_blockstats=' + rendered, flush=True)
else:
    nodes = []; truncated = [False]
    def scalar(value):
        if type(value) is str: return value if len(value) <= 240 else value[:240] + '<truncated>'
        return value if value is None or type(value) in (bool, int, float) else '<' + type(value).__name__ + '>'
    def walk(value, location, depth=0):
        if depth > 32 or len(nodes) >= 128: truncated[0] = True; return
        if type(value) is not dict:
            nodes.append({'at': location, 'shape': type(value).__name__}); return
        stats = value.get('stats'); stats = stats if type(stats) is dict else {}
        nodes.append({'at': location, **{k: scalar(value.get(k)) for k in ('device', 'node-name', 'qdev')},
                      **{k: scalar(stats[k]) if k in stats else '<missing>' for k in ('failed_wr_operations', 'failed_flush_operations')},
                      'failed_wr_type': type(stats['failed_wr_operations']).__name__ if 'failed_wr_operations' in stats else 'missing',
                      'failed_flush_type': type(stats['failed_flush_operations']).__name__ if 'failed_flush_operations' in stats else 'missing',
                      **{k: {'value': scalar(stats[k]), 'type': type(stats[k]).__name__} for k in ('account-failed', 'account_failed') if k in stats}})
        for key in ('parent', 'backing'):
            if key in value: walk(value[key], location + '.' + key, depth + 1)
    for index, event in enumerate(events):
        if type(event) is not dict:
            print('event', index, 'shape=', type(event).__name__); continue
        print('event', index, json.dumps({k: scalar(event.get(k)) for k in ('status', 'stop_acknowledged', 'failed_io_counters_zero', 'stop_internal_flush_return_observed', 'error')}, separators=(',', ':')))
        stats = event.get('post_stop_blockstats')
        print('response', index, 'type=', type(stats).__name__, 'length=', len(stats) if type(stats) in (list, dict) else None)
        if type(stats) is list:
            for position, row in enumerate(stats[:129]): walk(row, str(index) + '[' + str(position) + ']')
            if len(stats) > 128: truncated[0] = True
        else: walk(stats, str(index) + '[response]')
    for row in nodes: print('node', json.dumps(row, separators=(',', ':')))
    print('projected_nodes=', len(nodes), 'truncated=', truncated[0], 'raw_events_remain_in_hash_bound_phone_file=true', flush=True)
