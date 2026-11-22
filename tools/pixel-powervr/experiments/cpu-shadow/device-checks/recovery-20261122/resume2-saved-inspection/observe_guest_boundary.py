"""Read-only classified guest-result projection after the actual clean-VM failure."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat

BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
SOURCE = BASE / 'run-ios26-saved-inspection-resume2.py'
SOURCE_BYTES = 35799
SOURCE_SHA = '445f16736ff3f0c4aca2f9d825f4b71b9264bc24b177fe3a8281ca9c6e0f1e0b'
PREFLIGHT_PIN = {'bytes': 9070, 'sha256': '84b31f4f08744f6adeb20ab5af308b1d10c839803c051d4bba577201a4ad3760'}
EXPECTED_WRAPPER = {'pid': 13387, 'starttime': 8827282}
EXPECTED_ERROR = 'ValueError: guest inspection incomplete; retained metadata classifies the boundary'


def load_owner():
    if os.geteuid() != 0 or SOURCE.resolve(strict=True) != SOURCE:
        raise ValueError('root canonical reviewed source required')
    with os.fdopen(os.open(SOURCE, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != SOURCE_BYTES:
            raise ValueError('owner source metadata differs')
        body = stream.read(SOURCE_BYTES + 1)
    if len(body) != SOURCE_BYTES or hashlib.sha256(body).hexdigest() != SOURCE_SHA:
        raise ValueError('reviewed owner source differs')
    m = {'__name__': 'readonly_bound_inspection_owner', '__file__': str(SOURCE)}
    exec(compile(body, str(SOURCE), 'exec'), m)
    return m


def codes(values):
    if type(values) is not list or len(values) > 16:
        raise ValueError('classified code list exceeds bound')
    output = []
    for value in values:
        row = value if type(value) is dict else {'code': value}
        chosen = {k: row[k] for k in ('code', 'type') if k in row}
        if not chosen or any(type(x) is not str or re.fullmatch('[A-Za-z0-9_]{1,100}', x) is None for x in chosen.values()):
            raise ValueError('unexpected classified code shape')
        output.append(chosen)
    return output


def fields(row, names):
    if type(row) is not dict:
        raise ValueError('classified metadata row must be an object')
    result = {}
    for key in names:
        if key not in row:
            continue
        value = row[key]
        if type(value) in (bool, int, float) or value is None:
            result[key] = value
        elif type(value) is str and len(value) <= 100 and re.fullmatch('[A-Za-z0-9_]+', value):
            result[key] = value
        else:
            raise ValueError('unexpected bounded classified scalar: ' + key)
    return result


def main():
    m = load_owner()
    require, raw, read, absent = (m[k] for k in ('require', 'read_bytes', 'read_json', 'absent'))
    owner, work = m['OWNER'], m['WORK']
    current = read(owner / 'prerequisites.json')
    public = raw(owner / 'preflight.json')
    require(len(public) == PREFLIGHT_PIN['bytes'] and m['sha'](public) == PREFLIGHT_PIN['sha256'], 'actual preflight changed')
    m['validate_preflight'](json.loads(public), current)
    previous = m['previous_failure_inputs']()
    require(all(current['inputs'].get(path) == pin for path, pin in previous.items()), 'prior failure was not bound')
    for path, pin in current['inputs'].items():
        require(m['sha'](raw(Path(path))) == pin, 'bound input changed')
    for path, pin in m['SOURCE_HASHES'].items():
        require(m['sha'](raw(path)) == pin, 'reviewed inspector/runtime source changed')
    start, end = read(owner / 'owner.json'), read(owner / 'exit.json')
    command = m['COMMAND'] + ['--execute']
    require(start.get('schema') == end.get('schema') == 1 and start.get('wrapper') == EXPECTED_WRAPPER and
            start.get('command') == end.get('command') == read(owner / 'command.json') == command and
            all(start.get(k) == end.get(k) for k in ('started_utc', 'wrapper', 'runner')) and
            end.get('exit_code') == end.get('owner_exit_code') == 2 and end.get('accepted') is False and
            end.get('runner_started') is True and end.get('runner_reaped') is True and end.get('forced_runner') is False and
            end.get('wrapper_error') == 'ValueError: inspector exited 2' and end.get('cleanup_errors') == [] and end.get('finished_utc'),
            'actual failed owner is not complete and cleanly reaped')
    for key in ('wrapper', 'runner'):
        absent(start[key], 'inspection ' + key)
    result_body = raw(work / 'result.json')
    require(result_body == raw(work / 'a1/inspection-result.json'), 'two returned host results differ')
    result = json.loads(result_body)
    require(result.get('schema') == 1 and result.get('status') == 'INCOMPLETE' and result.get('error') == EXPECTED_ERROR and
            result.get('full_backing_chain_unchanged') is True and result.get('preparation_and_guard_unchanged') is True and
            result.get('identity_error') is None and all(result.get(k) is False for k in ('boot_complete', 'gpu_path_complete', 'app_gate_changed')),
            'actual failed inspection boundary differs')
    vm_path = work / 'a1/vm-result.json'
    vm = read(vm_path)
    cleanup, witnesses = vm.get('cleanup', {}), vm.get('witnesses', {})
    require(vm.get('status') == 'VM_OBSERVATION_COMPLETE' and vm.get('natural_exit') is True and vm.get('error') is None and
            cleanup.get('exit_code') == 0 and cleanup.get('echild') is True and cleanup.get('forced_qemu') is False and
            cleanup.get('forced_descendants') == [] and cleanup.get('errors') == [] and
            all(witnesses.get(k) is True for k in ('native_initialization', 'native_execution', 'native_svc_final')) and
            witnesses.get('fatal_markers') == [], 'VM/native/cleanup boundary differs')
    child = read(work / 'a1/vm.child.json')
    absent(child, 'inspection QEMU', 'start_ticks')
    guest_path = work / 'a1/files/inspection/result.json'
    guest_body = raw(guest_path)
    guest = json.loads(guest_body)
    require(result.get('guest_result') == guest, 'retained guest result differs from the host result')
    policy = read(work / 'a1/expected-policy.json')
    nonce_matches = None
    if 'inspection_nonce' in guest and 'inspection_nonce' in policy:
        nonce_matches = (all(type(row['inspection_nonce']) is str and re.fullmatch('[0-9a-f]{32}', row['inspection_nonce']) is not None
                             for row in (guest, policy)) and guest['inspection_nonce'] == policy['inspection_nonce'])
    policy_matches = None
    if 'policy_sha256' in guest:
        policy_matches = (type(guest['policy_sha256']) is str and re.fullmatch('[0-9a-f]{64}', guest['policy_sha256']) is not None and
                          guest['policy_sha256'] == m['digest'](policy))
    baseline_matches = None
    if 'gpt' in guest and 'baseline_gpt' in guest:
        baseline_matches = (all(type(guest[key]) is dict and type(guest[key].get('disk_bytes')) is int and
                                guest[key]['disk_bytes'] > 0 and type(guest[key].get('status')) is str
                                for key in ('gpt', 'baseline_gpt')) and guest['gpt'] == guest['baseline_gpt'])
    journals, fsck = {}, {}
    for name in ('iOSRoot', 'Data'):
        row = guest.get('journals', {}).get(name)
        if row is not None:
            item = fields(row, ('status', 'code'))
            for key, names in (
                ('metadata', ('endian', 'magic', 'endian_marker', 'start', 'end', 'bytes', 'block_header_bytes', 'header_bytes', 'checksum', 'computed_checksum', 'checksum_bytes', 'header_sha256')),
                ('journal_info', ('flags', 'jib_offset', 'offset', 'bytes', 'jib_sha256')),
                ('journal', ('status', 'state', 'endian', 'start', 'end', 'bytes', 'block_header_bytes', 'header_bytes', 'checksum', 'checksum_bytes', 'flags', 'journal_bytes', 'baseline_headers_identical', 'baseline_jib_identical', 'journal_all_zero'))):
                if key in row:
                    item[key] = fields(row[key], names)
            journals[name] = item
        row = guest.get('fsck', {}).get(name)
        if row is not None:
            fsck[name] = dict(fields(row, ('status', 'exit_code', 'diagnostic_sha256')), reasons=codes(row['reasons']) if 'reasons' in row else None)
    pins = []
    for path in (owner / 'exit.json', work / 'result.json', vm_path, guest_path, work / 'a1/expected-policy.json'):
        body = raw(path)
        pins.append({'path': str(path), 'bytes': len(body), 'sha256': m['sha'](body)})
    diagnostics = {}
    for name in ('fsck-system.txt', 'fsck-data.txt'):
        path = work / 'a1/files/inspection' / name
        if os.path.lexists(path):
            m['canonical'](path)
            info = path.stat()
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= 4 << 20, 'nonordinary diagnostic file')
            diagnostics[name] = {'present': True, 'bytes': info.st_size}
        else:
            diagnostics[name] = {'present': False}
    print(json.dumps({'schema': 1, 'status': 'SAVED_INSPECTION_GUEST_BOUNDARY_PROJECTION', 'readonly': True,
          'observed_utc': m['utc'](), 'owner_accepted': False, 'owner_runner_qemu_absent': True,
          'identities': {'wrapper': start['wrapper'], 'inspector': start['runner'], 'qemu': child},
          'bound_inputs_unchanged': True, 'resume1_failure_pins_unchanged': len(previous),
          'native_vm_complete_clean_unforced': True, 'host_error': result['error'],
          'guest': dict(fields(guest, ('schema', 'kind', 'status', 'readonly_attachments', 'raw_metadata_unchanged', 'mounted', 'replayed', 'repaired', 'boot_complete', 'gpu_path_complete', 'elapsed_seconds')),
                        policy_nonce_matches=nonce_matches,
                        policy_digest_matches=policy_matches,
                        errors=codes(guest['errors']) if 'errors' in guest else None,
                        cleanup_errors=codes(guest['cleanup_errors']) if 'cleanup_errors' in guest else None,
                        gpt=fields(guest['gpt'], ('status', 'disk_bytes')) if 'gpt' in guest else None,
                        baseline_gpt_matches=baseline_matches, journals=journals, fsck=fsck),
          'known_diagnostics': diagnostics, 'metadata_pins': pins,
          'raw_logs_exported': False, 'private_file_inventories_exported': False, 'inspection_success_claimed': False},
          separators=(',', ':')), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'schema': 1, 'status': 'GUEST_BOUNDARY_PROJECTION_REFUSED', 'readonly': True,
              'error': type(error).__name__ + ': ' + str(error)}, separators=(',', ':')), flush=True)
        raise SystemExit(2)
