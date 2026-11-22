"""Read-only acceptance and pins for the actual saved-inspection preflight."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import stat

SOURCE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-saved-inspection-resume4.py')
SOURCE_BYTES = 48469
SOURCE_SHA256 = 'c5cc01768be23c0a7e3ad1364cb89a3dd8562288ac3c51f5eaef35ce7c039f10'
LAUNCH = SOURCE.parent / 'ios26-saved-inspection-resume4-preflight-launch.json'
LOG = SOURCE.parent / 'ios26-saved-inspection-resume4-preflight-wrapper.log'


def without_exit(module):
    """Classify only fixed launch/log/start metadata; never rerun prerequisites."""
    require, read = module['require'], module['read_bytes']
    owner, work = module['OWNER'], module['WORK']
    report = {'schema': 1, 'readonly': True, 'accepted': False,
              'observed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'owner_directory_present': os.path.lexists(owner),
              'work_present': os.path.lexists(work), 'preflight_exit_present': False,
              'preflight_owner_present': os.path.lexists(owner / 'preflight-owner.json'),
              'wrapper': None, 'wrapper_present': None, 'runner': None, 'runner_present': None,
              'wrapper_log': None, 'owner_refusal': None}
    if not os.path.lexists(LAUNCH):
        report['status'] = ('SAVED_INSPECTION_PREFLIGHT_LAUNCH_EVIDENCE_MISSING'
                            if os.path.lexists(LOG) or report['owner_directory_present'] or report['work_present']
                            else 'SAVED_INSPECTION_PREFLIGHT_NOT_LAUNCHED')
        return report
    launch_body = read(LAUNCH, 16384)
    launch = json.loads(launch_body)
    expected_command = [module['PYTHON'], '-I', '-B', str(SOURCE), '--preflight']
    require(launch.get('schema') == 1 and launch.get('kind') == 'detached_saved_firstboot_preflight_owner' and
            launch.get('command') == expected_command and launch.get('source_sha256') == SOURCE_SHA256 and
            launch.get('wrapper_log') == str(LOG) and launch.get('start_new_session') is True and
            launch.get('inspection_execution_requested') is False and launch.get('preflight_accepted') is False,
            'fresh preflight launch binding differs')
    report['launch_receipt'] = {'path': str(LAUNCH), 'bytes': len(launch_body),
                                'sha256': hashlib.sha256(launch_body).hexdigest(),
                                'status': launch.get('status'), 'started_utc': launch.get('started_utc')}
    wrapper = launch.get('wrapper')
    if wrapper is not None:
        require(type(wrapper) is dict and type(wrapper.get('pid')) is int and wrapper['pid'] > 0 and
                type(wrapper.get('starttime')) is int and wrapper['starttime'] > 0 and
                wrapper.get('process_group') == wrapper['pid'] and wrapper.get('session') == wrapper['pid'],
                'recorded detached wrapper identity differs')
        report['wrapper'] = {name: wrapper[name] for name in ('pid', 'starttime')}
        report['wrapper_present'] = module['identity'](wrapper['pid']) == report['wrapper']
    if report['preflight_owner_present']:
        start = json.loads(read(owner / 'preflight-owner.json', 16384))
        require(start.get('schema') == 1 and start.get('command') == module['COMMAND'] and
                start.get('wrapper') == report['wrapper'], 'preflight runner start binding differs')
        runner = start.get('runner')
        require(type(runner) is dict and set(runner) == {'pid', 'starttime'} and
                type(runner['pid']) is int and runner['pid'] > 0 and
                type(runner['starttime']) is int and runner['starttime'] > 0,
                'recorded preflight runner identity differs')
        report['runner'] = runner
        report['runner_present'] = module['identity'](runner['pid']) == runner
    if os.path.lexists(LOG):
        body = read(LOG, 16384)
        report['wrapper_log'] = {'path': str(LOG), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}
        try:
            value = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            value = None
        if (type(value) is dict and value.get('schema') == 1 and value.get('status') == 'OWNER_REFUSED' and
                type(value.get('error')) is str and 0 < len(value['error']) <= 2048):
            report['owner_refusal'] = {'status': 'OWNER_REFUSED', 'error': value['error']}
    if report['owner_refusal'] is not None:
        report['status'] = 'SAVED_INSPECTION_PREFLIGHT_OWNER_REFUSED'
    elif launch.get('status') != 'PREFLIGHT_OWNER_LAUNCHED':
        report['status'] = 'SAVED_INSPECTION_PREFLIGHT_LAUNCH_INCOMPLETE'
    elif report['wrapper_present'] is True:
        report['status'] = 'SAVED_INSPECTION_PREFLIGHT_PENDING'
    elif report['runner_present'] is True:
        report['status'] = 'SAVED_INSPECTION_PREFLIGHT_OWNER_ABSENT_RUNNER_PRESENT'
    else:
        report['status'] = 'SAVED_INSPECTION_PREFLIGHT_EXIT_RECEIPT_MISSING'
    return report


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
        print(json.dumps(without_exit(module), separators=(',', ':')), flush=True)
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


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'schema': 1, 'status': 'SAVED_INSPECTION_PREFLIGHT_BINDING_REFUSED', 'readonly': True,
                          'error': type(exc).__name__ + ': ' + str(exc)}, separators=(',', ':')), flush=True)
        raise SystemExit(2)
