#!/usr/bin/env python3
"""Build, never execute, a command from the actual reviewed monitor-ready projection."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex

HERE = Path(__file__).resolve().parent
PHONE_SOURCE = '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/launch-ios26-saved-inspection-resume4-execute-procstat1.py'
SOURCE_PIN = {'bytes': 22309, 'sha256': 'fda158506174594a01366d2c6fb2d1a4d7628fca783ef89d7e0a8d5c490306f5'}
MONITOR_SOURCE = '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-saved-inspection-resume4-observer-procstat1.py'
MONITOR_PIN = {'bytes': 37877, 'sha256': '949da38590f86d827e6b9fb2f261e785e89b4e3cfe1efdbfbea60354cd281ed9'}
READY_PATH = '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume4-observer-procstat1/ready.json'
PREFLIGHT_PATH = '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume4-owner/preflight.json'
PREFLIGHT_PIN = {'bytes': 9069, 'sha256': 'd68aa23ba833c8939ace08005c573f11764c104bbbae29a5f0285677c7239bf6'}


def require(condition, text):
    if not condition:
        raise ValueError(text)


def construct(observation):
    require(observation.get('schema') == 1 and observation.get('status') == 'PROCESS_OBSERVER_READY_VERIFIED' and
            observation.get('diagnostic_only') is True and observation.get('inspection_execution_requested') is False and
            observation.get('observed_utc') and observation.get('independent_review_pending') is False and
            observation.get('independent_review'), 'actual independently reviewed ready projection required')
    ready, identity = observation['ready'], observation['observer']
    require(ready.get('path') == READY_PATH and type(ready.get('bytes')) is int and 0 < ready['bytes'] <= 16 << 10 and
            type(ready.get('sha256')) is str and re.fullmatch('[0-9a-f]{64}', ready['sha256']) is not None and
            type(ready.get('digest_bytes')) is list and len(ready['digest_bytes']) == 32 and
            all(type(x) is int and 0 <= x <= 255 for x in ready['digest_bytes']) and
            bytes(ready['digest_bytes']).hex() == ready['sha256'], 'actual ready byte/digest binding differs')
    require(set(identity) == {'pid', 'start_ticks'} and all(type(identity[k]) is int and identity[k] > 0 for k in identity),
            'actual monitor identity required')
    live = observation['live_relation']
    require({k: live.get(k) for k in identity} == identity and live.get('pgrp') == live.get('session') == identity['pid'] and
            live.get('state') not in ('Z', 'X', 'x', 'T', 't', None), 'actual independent live monitor relation differs')
    require(observation.get('source') == {'path': MONITOR_SOURCE, **MONITOR_PIN} and
            all(observation.get('preflight', {}).get(k) == v for k, v in {'path': PREFLIGHT_PATH, **PREFLIGHT_PIN}.items()),
            'observed source or actual fresh preflight differs')
    source = (HERE / 'launch_saved_inspection_execution.py').read_bytes()
    require({'bytes': len(source), 'sha256': hashlib.sha256(source).hexdigest()} == SOURCE_PIN, 'finalized launcher source changed')
    loader = '''import hashlib,os,stat
from pathlib import Path
p=Path(PHONE_SOURCE)
if os.geteuid()!=0 or p.resolve(strict=True)!=p: raise ValueError('root canonical execution launcher required')
with os.fdopen(os.open(p,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
 s=os.fstat(f.fileno())
 if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_uid!=0 or s.st_size!=SOURCE_BYTES: raise ValueError('execution launcher metadata differs')
 b=f.read(SOURCE_BYTES+1)
if len(b)!=SOURCE_BYTES or hashlib.sha256(b).hexdigest()!=SOURCE_SHA: raise ValueError('execution launcher source differs')
exec(compile(b,str(p),'exec'),{'__name__':'__main__','__file__':str(p)})
'''.replace('PHONE_SOURCE', repr(PHONE_SOURCE)).replace('SOURCE_BYTES', str(SOURCE_PIN['bytes'])).replace('SOURCE_SHA', repr(SOURCE_PIN['sha256']))
    argv = ['/data/data/com.termux/files/usr/bin/python', '-I', '-B', '-c', loader,
            '--monitor-ready-sha256', ready['sha256'], '--monitor-ready-bytes', str(ready['bytes']),
            '--monitor-pid', str(identity['pid']), '--monitor-start-ticks', str(identity['start_ticks'])]
    command = shlex.join(argv) + '\n'
    require(len(command.encode()) <= 6000, 'command exceeds transport bound')
    return command


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('actual_ready_observation', type=Path)
    args = parser.parse_args()
    raw = args.actual_ready_observation.read_bytes()
    observation = json.loads(raw)
    command = construct(observation)
    record = {'schema': 1, 'actual_observation_path': str(args.actual_ready_observation.resolve()),
              'actual_observation_sha256': hashlib.sha256(raw).hexdigest(),
              'ready': observation['ready'], 'observer': observation['observer'], 'launcher': SOURCE_PIN,
              'command': {'bytes': len(command.encode()), 'sha256': hashlib.sha256(command.encode()).hexdigest()},
              'phone_execution_performed_by_builder': False}
    for name, body in [('launch-execution.command.txt', command), ('execution-ready-binding.json', json.dumps(record, indent=2) + '\n')]:
        path = HERE / name
        if path.exists():
            require(path.read_text() == body, 'preserve different existing ' + str(path))
        else:
            with path.open('x') as stream:
                stream.write(body)
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
