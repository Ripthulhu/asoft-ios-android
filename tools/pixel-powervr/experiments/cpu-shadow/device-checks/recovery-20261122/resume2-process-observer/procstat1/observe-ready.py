#!/usr/bin/env python3
"""Read-only projection of the actual fresh, live observer readiness."""
import hashlib
import json
import os
from pathlib import Path
import stat
import time
import types

BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
SOURCE = BASE / 'run-ios26-saved-inspection-resume2-observer-procstat1.py'
SOURCE_PIN = {'bytes': 37878, 'sha256': 'a49ec9b11ba0fefda03e2a688e86422df53851c9ec146f21591961da20104bd2'}
PREFLIGHT_SHA256 = '84b31f4f08744f6adeb20ab5af308b1d10c839803c051d4bba577201a4ad3760'
PREFLIGHT_BYTES = 9070
OUT = BASE / 'ios26-saved-inspection-resume2-observer-procstat1'
LAUNCH = BASE / 'ios26-saved-inspection-resume2-observer-procstat1-launch.json'

if os.geteuid() != 0 or BASE.resolve(strict=True) != BASE or SOURCE.resolve(strict=True) != SOURCE:
    raise ValueError('root and canonical source/base required')
with os.fdopen(os.open(SOURCE, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
    info = os.fstat(stream.fileno())
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1 or info.st_size != SOURCE_PIN['bytes']:
        raise ValueError('observer source metadata differs')
    body = stream.read(SOURCE_PIN['bytes'] + 1)
if len(body) != SOURCE_PIN['bytes'] or hashlib.sha256(body).hexdigest() != SOURCE_PIN['sha256']:
    raise ValueError('observer source differs')
m = types.ModuleType('verified_observer_ready_reader')
m.__file__ = str(SOURCE)
exec(compile(body, str(SOURCE), 'exec'), m.__dict__)
bound = m.prerequisites(PREFLIGHT_SHA256, PREFLIGHT_BYTES)
ready, ready_pin = m.read_json(OUT / 'ready.json')
status, status_pin = m.read_json(OUT / 'status.json')
launch, launch_pin = m.read_json(LAUNCH)
expected_source = {'path': str(SOURCE), **SOURCE_PIN}
probe = ready.get('discovery_probe', {})
scan = probe.get('scan', {})
m.require(probe.get('method') == 'bounded_numeric_proc_stat' and probe.get('self_identity_verified') is True and
          probe.get('unrelated_metadata_exported') is False and
          0 < scan.get('numeric_entries', 0) <= m.BOUNDS['proc_numeric_entries'] and
          0 < scan.get('read_bytes', 0) <= m.BOUNDS['discovery_read_bytes'] and
          0 <= scan.get('duration_ms', -1) <= m.BOUNDS['discovery_scan_ms'], 'numeric proc discovery readiness probe differs')
m.require(ready.get('schema') == 1 and ready.get('kind') == 'saved_inspection_process_observer_ready' and
          ready.get('status') == 'READY' and ready.get('source') == expected_source and
          ready.get('scope') == m.SCOPE and ready.get('bounds') == m.BOUNDS and
          ready.get('output_directory') == str(OUT) and ready.get('diagnostic_only') is True and
          ready.get('independent_session') is True and ready.get('target_execution_absent_at_ready') is True and
          ready.get('preflight') == bound['preflight'] and ready.get('inspection_owner_source') == bound['inspection_owner_source'],
          'ready receipt does not bind the exact fresh preflight and scope')
identity = ready['observer']
live = m.Proc().snapshot(identity['pid'])
m.require(m.key(live) == m.key(identity) and live['pid'] == live['pgrp'] == live['session'] and live['state'] not in 'ZXxTt',
          'ready observer is no longer the live detached process')
expected_command = [m.PYTHON, '-I', '-B', str(SOURCE), '--preflight-sha256', PREFLIGHT_SHA256,
                    '--preflight-bytes', str(PREFLIGHT_BYTES)]
cmdline = m.Proc().bounded(Path('/proc') / str(identity['pid']) / 'cmdline', 4096)
m.require(cmdline.split(b'\0') == [value.encode() for value in expected_command] + [b''], 'live observer command differs')
m.require(launch.get('schema') == 1 and launch.get('kind') == 'detached_saved_inspection_process_observer' and
          launch.get('status') == 'PROCESS_OBSERVER_LAUNCHED' and launch.get('command') == expected_command and
          launch.get('source') == expected_source and m.key(launch['observer']) == m.key(identity) and
          launch.get('start_new_session') is True and launch.get('diagnostic_only') is True and
          launch.get('inspection_execution_requested') is False, 'observer launch receipt differs')
now = time.monotonic_ns()
age = (now - status['heartbeat_monotonic_ns']) / 1e9
remaining = m.BOUNDS['launch_wait_seconds'] - (now - ready['ready_monotonic_ns']) / 1e9
m.require(status.get('schema') == 1 and status.get('kind') == 'saved_inspection_process_observer_status' and
          status.get('status') == 'RUNNING' and status.get('phase') == 'WAITING_FOR_EXECUTION_OWNER' and
          status.get('observer') == identity and status.get('source_sha256') == SOURCE_PIN['sha256'] and
          status.get('ready_sha256') == ready_pin['sha256'] and status.get('scope') == m.SCOPE and
          status.get('output_directory') == str(OUT) and 0 <= age <= 5 and remaining > 5 and
          not os.path.lexists(OUT / 'exit.json'), 'observer heartbeat/readiness expired or scope changed')
print(json.dumps({'schema': 1, 'status': 'PROCESS_OBSERVER_READY_VERIFIED', 'observed_utc': m.utc(),
    'ready': dict(ready_pin, digest_bytes=list(bytes.fromhex(ready_pin['sha256']))),
    'observer': identity, 'live_relation': {k: live[k] for k in ('pid', 'start_ticks', 'ppid', 'pgrp', 'session', 'state')},
    'source': expected_source, 'launch': launch_pin, 'preflight': bound['preflight'],
    'heartbeat_age_seconds': age, 'launch_wait_remaining_seconds': remaining,
    'sample_count': status['sample_count'], 'diagnostic_only': True,
    'discovery_probe': probe, 'discovery': status['discovery'],
    'inspection_execution_requested': False}, indent=2), flush=True)
