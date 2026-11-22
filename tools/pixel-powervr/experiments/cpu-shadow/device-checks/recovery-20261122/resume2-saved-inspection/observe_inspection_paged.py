"""Read-only saved-inspection status and, after acceptance, fourteen input pins."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import stat

SOURCE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-saved-inspection-resume2.py')
SOURCE_BYTES = 35799
SOURCE_SHA256 = '445f16736ff3f0c4aca2f9d825f4b71b9264bc24b177fe3a8281ca9c6e0f1e0b'
PREFLIGHT_PIN = {'bytes': 9070, 'sha256': '84b31f4f08744f6adeb20ab5af308b1d10c839803c051d4bba577201a4ad3760'}  # Physically observed accepted preflight.


def load_owner():
    if os.geteuid() != 0 or SOURCE.resolve(strict=True) != SOURCE:
        raise ValueError('root and canonical reviewed source required')
    with os.fdopen(os.open(SOURCE, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != SOURCE_BYTES:
            raise ValueError('owner source metadata differs')
        body = stream.read(SOURCE_BYTES + 1)
    if len(body) != SOURCE_BYTES or hashlib.sha256(body).hexdigest() != SOURCE_SHA256:
        raise ValueError('reviewed owner source differs')
    namespace = {'__name__': 'reviewed_saved_inspection_owner', '__file__': str(SOURCE)}
    exec(compile(body, str(SOURCE), 'exec'), namespace)
    return namespace


def optional(m, path):
    return m['read_json'](path) if path.exists() else {}


def process(m, value, key='starttime'):
    if not value:
        return {'recorded': False}
    expected = {'pid': value['pid'], 'starttime': value[key]}
    actual = m['identity'](expected['pid'])
    return {'recorded': True, 'expected': expected, 'present': actual == expected, 'absent': actual != expected}



def input_preservation(m):
    """Check metadata and reviewed source bytes without running or adopting a child."""
    owner, raw, require = m['OWNER'], m['read_bytes'], m['require']
    preflight_body = raw(owner / 'preflight.json')
    require(len(preflight_body) == PREFLIGHT_PIN['bytes'] and
            hashlib.sha256(preflight_body).hexdigest() == PREFLIGHT_PIN['sha256'], 'actual new preflight changed')
    current = m['read_json'](owner / 'prerequisites.json')
    m['validate_preflight'](json.loads(preflight_body), current)
    for path, expected in m['SOURCE_HASHES'].items():
        require(hashlib.sha256(raw(path)).hexdigest() == expected, 'reviewed runtime or inspector source changed')
    previous = m['previous_failure_inputs']()
    require(all(current['inputs'].get(path) == expected for path, expected in previous.items()),
            'prior failure preservation was not bound by fresh preflight')
    for path, expected in current['inputs'].items():
        require(hashlib.sha256(raw(Path(path))).hexdigest() == expected, 'bound input changed: ' + path)
    return {'preflight_stdout_unchanged': True, 'reviewed_sources_unchanged': True,
            'bound_inputs_unchanged': True, 'resume1_failure_pins_unchanged': len(previous),
            'prior_recorded_identities_absent': True, 'error': None}


def status(m):
    owner, work, base = m['OWNER'], m['WORK'], m['BASE']
    start, end = optional(m, owner / 'owner.json'), optional(m, owner / 'exit.json')
    child = optional(m, work / 'a1/vm.child.json')
    vm, result = optional(m, work / 'a1/vm-result.json'), optional(m, work / 'result.json')
    launched = optional(m, base / 'ios26-saved-inspection-resume2-execute-launch.json')
    witnesses = vm.get('witnesses', {})
    try:
        preservation = input_preservation(m)
    except Exception as exc:
        preservation = {'bound_inputs_unchanged': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    summary = {'schema': 1, 'status': 'SAVED_INSPECTION_OBSERVATION_ONLY', 'readonly': True,
      'observed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'launch_status': launched.get('status'), 'inspection_work_present': work.exists(),
      'input_preservation': preservation,
      'wrapper': process(m, start.get('wrapper') or launched.get('wrapper')),
      'inspector': process(m, start.get('runner')), 'qemu': process(m, child, 'start_ticks'),
      'outer_exit': {k: end.get(k) for k in ('exit_code', 'owner_exit_code', 'accepted', 'runner_reaped',
                    'forced_runner', 'wrapper_error', 'cleanup_errors', 'inspection_result_sha256')},
      'vm': {k: vm.get(k) for k in ('status', 'started_utc', 'finished_utc', 'elapsed_seconds', 'natural_exit', 'done_codes', 'out_sizes', 'error', 'cleanup')},
      'native': {k: witnesses.get(k) for k in ('native_initialization', 'native_execution', 'native_svc_final', 'fatal_markers')},
      'inspection': {k: result.get(k) for k in ('status', 'started_utc', 'finished_utc', 'elapsed_seconds', 'natural_exit', 'full_backing_chain_unchanged',
                    'preparation_and_guard_unchanged', 'error', 'identity_error', 'boot_complete', 'gpu_path_complete', 'app_gate_changed')}}
    path = base / 'ios26-saved-inspection-resume2-execute-wrapper.log'
    if path.exists() and path.stat().st_size <= 16384:
        try:
            refusal = m['read_json'](path)
            if refusal.get('status') == 'OWNER_REFUSED':
                summary['owner_refusal'] = refusal.get('error')
        except (json.JSONDecodeError, UnicodeError):
            pass
    print(json.dumps(summary, separators=(',', ':')), flush=True)


def pins(m, page=None):
    require, read, raw, absent = (m[k] for k in ('require', 'read_json', 'read_bytes', 'absent'))
    require(type(PREFLIGHT_PIN) is dict and set(PREFLIGHT_PIN) == {'bytes', 'sha256'},
            'unreleased binding collector requires actual accepted preflight pin')
    owner, work, base = m['OWNER'], m['WORK'], m['BASE']
    input_preservation(m)
    preflight_body = raw(owner / 'preflight.json')
    require(len(preflight_body) == PREFLIGHT_PIN['bytes'] and
            hashlib.sha256(preflight_body).hexdigest() == PREFLIGHT_PIN['sha256'], 'preflight binding changed')
    current = read(owner / 'prerequisites.json')
    m['validate_preflight'](json.loads(preflight_body), current)
    start, end = read(owner / 'owner.json'), read(owner / 'exit.json')
    command = m['COMMAND'] + ['--execute']
    require(start.get('schema') == end.get('schema') == 1 and
            start.get('command') == end.get('command') == read(owner / 'command.json') == command and
            all(start.get(k) == end.get(k) for k in ('started_utc', 'wrapper', 'runner')) and
            end.get('exit_code') == end.get('owner_exit_code') == 0 and end.get('accepted') is True and
            end.get('runner_started') is True and end.get('runner_reaped') is True and
            end.get('forced_runner') is False and end.get('wrapper_error') is None and
            end.get('cleanup_errors') == [] and end.get('finished_utc'), 'inspection owner did not accept and cleanly reap')
    for key in ('wrapper', 'runner'):
        absent(start[key], 'inspection ' + key)
    launched = read(base / 'ios26-saved-inspection-resume2-execute-launch.json')
    expected_outer = [m['PYTHON'], '-I', '-B', str(SOURCE), '--execute', '--preflight-sha256',
                      PREFLIGHT_PIN['sha256'], '--preflight-bytes', str(PREFLIGHT_PIN['bytes'])]
    require(launched.get('schema') == 1 and launched.get('status') == 'SAVED_INSPECTION_EXECUTION_OWNER_LAUNCHED' and
            launched.get('kind') == 'detached_saved_firstboot_execution_owner' and
            launched.get('command') == expected_outer and launched.get('source_sha256') == SOURCE_SHA256 and
            launched.get('preflight_accepted') is True and launched.get('inspection_execution_requested') is True and
            launched.get('start_new_session') is True and
            {k: launched.get('wrapper', {}).get(k) for k in ('pid', 'starttime')} == start['wrapper'],
            'execution launch disagrees with accepted inspection owner')
    evidence = launched.get('accepted_preflight_evidence', {})
    require(evidence.get('preflight_stdout_sha256') == PREFLIGHT_PIN['sha256'] and
            type(evidence.get('metadata_sha256')) is dict and
            str(owner / 'prerequisites.json') in evidence['metadata_sha256'], 'preflight evidence absent')
    for path, pin in evidence['metadata_sha256'].items():
        require(hashlib.sha256(raw(Path(path))).hexdigest() == pin, 'preflight metadata changed')
    for path, pin in m['FIRSTBOOT_SUCCESS_PINS'].items():
        body = raw(Path(path))
        require(len(body) == pin['bytes'] and hashlib.sha256(body).hexdigest() == pin['sha256'],
                'successful firstboot input changed')
    accepted_sha = m['accept_result'](current)
    require(end.get('inspection_result_sha256') == accepted_sha, 'accepted result disagrees with owner exit')
    paths = [SOURCE, *(owner / n for n in ('command.json', 'owner.json', 'exit.json')),
             *(work / n for n in ('inspection-session.json', 'result.json')),
             *(work / 'a1' / n for n in ('inspection-result.json', 'expected-policy.json', 'launch.json', 'vm-result.json', 'vm.child.json')),
             *(work / 'a1/files/inspection' / n for n in ('result.json', 'fsck-system.txt', 'fsck-data.txt'))]
    rows = []
    for path in paths:
        body = raw(path, 4 << 20)
        digest = hashlib.sha256(body)
        rows.append({'path': str(path), 'bytes': len(body), 'sha256': digest.hexdigest(), 'digest_bytes': list(digest.digest())})
    print(json.dumps({'schema': 1, 'status': 'SAVED_INSPECTION_SUCCESS_BINDING_READY', 'readonly': True,
          'observed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'files': len(rows),
          'owner_accepted': True, 'runner_reaped': True, 'recorded_processes_absent': True,
          'inspection_result_sha256': accepted_sha, 'page': page, 'pages': 3}, separators=(',', ':')), flush=True)
    selected = rows if page is None else rows[page * 5:(page + 1) * 5]
    for index, row in enumerate(selected, start=0 if page is None else page * 5):
        print(json.dumps({'index': index, **row}, separators=(',', ':')), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pins', action='store_true')
    parser.add_argument('--page', type=int, choices=range(3))
    args = parser.parse_args()
    if args.page is not None and not args.pins:
        parser.error('--page requires --pins')
    owner = load_owner()
    pins(owner, args.page) if args.pins else status(owner)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'schema': 1, 'status': 'SAVED_INSPECTION_OBSERVATION_REFUSED', 'readonly': True,
                          'error': type(exc).__name__ + ': ' + str(exc)}, separators=(',', ':')), flush=True)
        raise SystemExit(2)
