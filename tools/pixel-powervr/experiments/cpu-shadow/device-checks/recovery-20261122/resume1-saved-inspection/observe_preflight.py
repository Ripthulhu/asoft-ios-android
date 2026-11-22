"""Read-only acceptance and pins for the actual saved-inspection preflight."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import stat

SOURCE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-saved-inspection-resume1.py')
SOURCE_BYTES = 25168
SOURCE_SHA256 = '87526ee42417108f46a8ca03b3fece1cd154f2c439a9c6492f20c97fd6981bb9'


def main():
    if os.geteuid() != 0 or SOURCE.resolve(strict=True) != SOURCE:
        raise ValueError('root and canonical reviewed source required')
    with os.fdopen(os.open(SOURCE, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != SOURCE_BYTES:
            raise ValueError('owner source metadata differs')
        source = stream.read(SOURCE_BYTES + 1)
    if len(source) != SOURCE_BYTES or hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError('reviewed source differs')
    module = {'__name__': 'reviewed_saved_inspection_owner', '__file__': str(SOURCE)}
    exec(compile(source, str(SOURCE), 'exec'), module)
    owner = module['OWNER']
    require, read, absent = module['require'], module['read_json'], module['absent']
    if not (owner / 'preflight-exit.json').exists():
        print(json.dumps({'status': 'SAVED_INSPECTION_PREFLIGHT_PENDING', 'readonly': True,
                          'observed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}, separators=(',', ':')))
        return
    current = module['prerequisites']()
    require(read(owner / 'prerequisites.json') == current, 'preflight inputs changed')
    start, end = read(owner / 'preflight-owner.json'), read(owner / 'preflight-exit.json')
    body = module['read_bytes'](owner / 'preflight.json')
    require(start.get('schema') == end.get('schema') == 1 and
            start.get('command') == end.get('command') == read(owner / 'preflight-command.json') == module['COMMAND'] and
            all(start.get(k) == end.get(k) for k in ('started_utc', 'wrapper', 'runner')) and
            end.get('exit_code') == end.get('owner_exit_code') == 0 and
            end.get('accepted') is True and end.get('runner_started') is True and end.get('runner_reaped') is True and
            end.get('forced_runner') is False and end.get('wrapper_error') is None and end.get('cleanup_errors') == [] and
            end.get('finished_utc') and hashlib.sha256(body).hexdigest() == end.get('stdout_sha256'),
            'preflight did not accept and cleanly reap')
    for name in ('wrapper', 'runner'):
        absent(start[name], 'preflight ' + name)
    public = json.loads(body)
    module['validate_preflight'](public, current)
    require(not any(os.path.lexists(owner / n) for n in ('command.json', 'owner.json', 'exit.json', 'run.log')),
            'execution already has an artifact; preserve it')
    print(json.dumps({'schema': 1, 'status': 'SAVED_INSPECTION_PREFLIGHT_BINDING_READY', 'readonly': True,
          'observed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'preflight_status': public['status'], 'accepted': True, 'exit_code': 0, 'owner_exit_code': 0,
          'runner_reaped': True, 'forced_runner': False, 'wrapper_absent': True, 'runner_absent': True,
          'work_absent': True, 'inputs_unchanged': True, 'execution_started': False,
          'preflight': {'path': str(owner / 'preflight.json'), 'bytes': len(body),
                        'sha256': hashlib.sha256(body).hexdigest(),
                        'digest_bytes': list(hashlib.sha256(body).digest())}}, separators=(',', ':')), flush=True)


try:
    main()
except Exception as exc:
    print(json.dumps({'schema': 1, 'status': 'SAVED_INSPECTION_PREFLIGHT_BINDING_REFUSED', 'readonly': True,
                      'error': type(exc).__name__ + ': ' + str(exc)}, separators=(',', ':')), flush=True)
    raise SystemExit(2)
