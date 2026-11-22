#!/usr/bin/env python3
"""Bounded read-only resource/path/live-observer projection after launch refusal."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat


def readiness():
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
    SOURCE = BASE / 'run-ios26-saved-inspection-resume5-observer-procstat1.py'
    SOURCE_PIN = {'bytes': 37877, 'sha256': '478b8b9179443ae3b60e921bd65933cd64a0cd1c209bf9e8327c541fe72f65de'}
    PREFLIGHT_SHA256 = '4630b5dc921d3bee52d4805cc829e3624144b763d27b53937443e43c69db44f6'
    PREFLIGHT_BYTES = 9069
    OUT = BASE / 'ios26-saved-inspection-resume5-observer-procstat1'
    LAUNCH = BASE / 'ios26-saved-inspection-resume5-observer-procstat1-launch.json'
    
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
    m.require(ready_pin['bytes'] == 3841 and ready_pin['sha256'] == '7e22ccf73c349f9c396a54cba434ec98a93fef0a44028a0856f3ebfd39be5f51' and
              identity == {'pid': 31097, 'start_ticks': 10563710}, 'actual released READY or identity differs')
    return {'status': 'LIVE_WAITING_READY_VERIFIED', 'observer': identity,
            'live_relation': {k: live[k] for k in ('pid', 'start_ticks', 'ppid', 'pgrp', 'session', 'state')},
            'ready': ready_pin, 'heartbeat_age_seconds': age, 'launch_wait_remaining_seconds': remaining,
            'heartbeat_utc': status['heartbeat_utc'], 'sample_count': status['sample_count'],
            'source_sha256': SOURCE_PIN['sha256'], 'preflight_sha256': PREFLIGHT_SHA256,
            'inspection_execution_requested': False}


def main():
    base = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
    owner = base / 'ios26-saved-inspection-resume5-owner'
    work = Path('/data/local/tmp/pixel-saved-audit-e9cc754-resume5')
    launcher = base / 'launch-ios26-saved-inspection-resume5-execute-procstat1.py'
    if os.geteuid() != 0 or base.resolve(strict=True) != base or launcher.resolve(strict=True) != launcher:
        raise ValueError('root canonical released execution source required')
    with os.fdopen(os.open(launcher, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1 or info.st_size != 22650:
            raise ValueError('released execution source metadata differs')
        body = stream.read(22651)
    if len(body) != 22650 or hashlib.sha256(body).hexdigest() != 'ade71fbc25294f8a5b14f93a8df0c0f14ebdd4bdd699e7ca2ccba004edeb5aab':
        raise ValueError('released execution source differs')
    with Path('/proc/meminfo').open('rb') as stream:
        memory_body = stream.read(65537)
    if len(memory_body) > 65536:
        raise ValueError('meminfo exceeds bound')
    memory = {}
    for name in ('MemTotal', 'MemAvailable', 'SwapTotal', 'SwapFree'):
        values = re.findall(rb'^' + name.encode() + rb':\s+(\d+) kB$', memory_body, re.M)
        if len(values) != 1:
            raise ValueError('required memory field unavailable: ' + name)
        memory[name + '_bytes'] = int(values[0]) * 1024
    paths = [work, base / 'ios26-saved-inspection-resume5-execute-launch.json',
             base / 'ios26-saved-inspection-resume5-execute-wrapper.log',
             *(owner / name for name in ('command.json', 'owner.json', 'exit.json', 'run.log'))]
    existing = {str(path): os.path.lexists(path) for path in paths}
    storage = os.statvfs('/data/local/tmp/pixel-prep-e9cc754')
    result = {'schema': 1, 'status': 'READONLY_LAUNCH_REFUSAL_RESOURCE_OBSERVATION',
              'observed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'memory': memory, 'required_MemAvailable_bytes': 2816 << 20,
              'current_memory_floor_met': memory['MemAvailable_bytes'] >= 2816 << 20,
              'storage_free_bytes': storage.f_bavail * storage.f_frsize,
              'execution_paths_exist': existing, 'all_execution_paths_absent': not any(existing.values()),
              'execution_launcher_sha256': hashlib.sha256(body).hexdigest(),
              'observer_readiness': None, 'observer_readiness_error': None,
              'readonly': True, 'launch_requested': False, 'memory_action_requested': False}
    try:
        result['observer_readiness'] = readiness()
    except Exception as exc:
        result['observer_readiness_error'] = (type(exc).__name__ + ': ' + str(exc))[:512]
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
