"""Read-only classified guest-result projection after the actual clean-VM failure."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
SOURCE = BASE / 'run-ios26-saved-inspection-resume5.py'
SOURCE_BYTES = 60564
SOURCE_SHA = 'dbb570dc9b3354a5d7c4eb218883ab22f25afe24757c429e46cc7c04de1baa63'
PREFLIGHT_PIN = {'bytes': 9069, 'sha256': '4630b5dc921d3bee52d4805cc829e3624144b763d27b53937443e43c69db44f6'}
EXPECTED_WRAPPER = None
EXPECTED_ERROR = None
RESULT_PIN = None

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
        if not chosen or any((type(x) is not str or re.fullmatch('[A-Za-z0-9_]{1,100}', x) is None for x in chosen.values())):
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
    if type(EXPECTED_WRAPPER) is not dict or set(EXPECTED_WRAPPER) != {'pid', 'starttime'} or any((type(v) is not int or v <= 0 for v in EXPECTED_WRAPPER.values())) or (type(EXPECTED_ERROR) is not str) or (not 1 <= len(EXPECTED_ERROR) <= 256) or (type(RESULT_PIN) is not dict) or (set(RESULT_PIN) != {'bytes', 'sha256'}) or (type(RESULT_PIN['bytes']) is not int) or (not 0 < RESULT_PIN['bytes'] <= 4 << 20) or (type(RESULT_PIN['sha256']) is not str) or (re.fullmatch('[0-9a-f]{64}', RESULT_PIN['sha256']) is None):
        raise ValueError('unreleased failure projection requires actual reviewed identity, error and result pin')
    m = load_owner()
    require, raw, read, absent = (m[k] for k in ('require', 'read_bytes', 'read_json', 'absent'))
    owner, work = (m['OWNER'], m['WORK'])
    current = read(owner / 'prerequisites.json')
    public = raw(owner / 'preflight.json')
    require(len(public) == PREFLIGHT_PIN['bytes'] and m['sha'](public) == PREFLIGHT_PIN['sha256'], 'actual preflight changed')
    m['validate_preflight'](json.loads(public), current)
    previous = m['previous_failure_inputs']()
    recent = m['resume2_failure_inputs']()
    latest = m['resume4_failure_inputs']()
    require(all((current['inputs'].get(path) == pin for path, pin in {**recent, **latest}.items())), 'later historical failures/JIB diagnosis were not bound by fresh preflight')
    require(all((current['inputs'].get(path) == pin for path, pin in previous.items())), 'prior failure was not bound')
    for path, pin in current['inputs'].items():
        require(m['sha'](raw(Path(path))) == pin, 'bound input changed')
    for path, pin in m['SOURCE_HASHES'].items():
        require(m['sha'](raw(path)) == pin, 'reviewed inspector/runtime source changed')
    start, end = (read(owner / 'owner.json'), read(owner / 'exit.json'))
    command = m['COMMAND'] + ['--execute']
    require(start.get('schema') == end.get('schema') == 1 and start.get('wrapper') == EXPECTED_WRAPPER and (start.get('command') == end.get('command') == read(owner / 'command.json') == command) and all((start.get(k) == end.get(k) for k in ('started_utc', 'wrapper', 'runner'))) and (end.get('exit_code') == end.get('owner_exit_code') == 2) and (end.get('accepted') is False) and (end.get('runner_started') is True) and (end.get('runner_reaped') is True) and (end.get('forced_runner') is False) and (end.get('wrapper_error') == 'ValueError: inspector exited 2') and (end.get('cleanup_errors') == []) and end.get('finished_utc'), 'actual failed owner is not complete and cleanly reaped')
    for key in ('wrapper', 'runner'):
        absent(start[key], 'inspection ' + key)
    result_body = raw(work / 'result.json')
    require({'bytes': len(result_body), 'sha256': m['sha'](result_body)} == RESULT_PIN, 'actual failed host result changed')
    require(result_body == raw(work / 'a1/inspection-result.json'), 'two returned host results differ')
    result = json.loads(result_body)
    require(result.get('schema') == 1 and result.get('status') == 'INCOMPLETE' and (result.get('error') == EXPECTED_ERROR) and (result.get('full_backing_chain_unchanged') is True) and (result.get('preparation_and_guard_unchanged') is True) and (result.get('identity_error') is None) and all((result.get(k) is False for k in ('boot_complete', 'gpu_path_complete', 'app_gate_changed'))), 'actual failed inspection boundary differs')
    vm_path = work / 'a1/vm-result.json'
    vm = read(vm_path)
    cleanup, witnesses = (vm.get('cleanup', {}), vm.get('witnesses', {}))
    require(vm.get('status') == 'VM_OBSERVATION_COMPLETE' and vm.get('natural_exit') is True and (vm.get('error') is None) and (cleanup.get('exit_code') == 0) and (cleanup.get('echild') is True) and (cleanup.get('forced_qemu') is False) and (cleanup.get('forced_descendants') == []) and (cleanup.get('errors') == []) and all((witnesses.get(k) is True for k in ('native_initialization', 'native_execution', 'native_svc_final'))) and (witnesses.get('fatal_markers') == []), 'VM/native/cleanup boundary differs')
    child = read(work / 'a1/vm.child.json')
    absent(child, 'inspection QEMU', 'start_ticks')
    guest_path = work / 'a1/files/inspection/result.json'
    guest_body = raw(guest_path)
    guest = json.loads(guest_body)
    require(result.get('guest_result') == guest, 'retained guest result differs from the host result')
    policy = read(work / 'a1/expected-policy.json')
    nonce_matches = None
    if 'inspection_nonce' in guest and 'inspection_nonce' in policy:
        nonce_matches = all((type(row['inspection_nonce']) is str and re.fullmatch('[0-9a-f]{32}', row['inspection_nonce']) is not None for row in (guest, policy))) and guest['inspection_nonce'] == policy['inspection_nonce']
    policy_matches = None
    if 'policy_sha256' in guest:
        policy_matches = type(guest['policy_sha256']) is str and re.fullmatch('[0-9a-f]{64}', guest['policy_sha256']) is not None and (guest['policy_sha256'] == m['digest'](policy))
    baseline_matches = None
    if 'gpt' in guest and 'baseline_gpt' in guest:
        baseline_matches = all((type(guest[key]) is dict and type(guest[key].get('disk_bytes')) is int and (guest[key]['disk_bytes'] > 0) and (type(guest[key].get('status')) is str) for key in ('gpt', 'baseline_gpt'))) and guest['gpt'] == guest['baseline_gpt']
    journals, fsck = ({}, {})
    for name in ('iOSRoot', 'Data'):
        row = guest.get('journals', {}).get(name)
        if row is not None:
            item = fields(row, ('status', 'code'))
            for key, names in (('metadata', ('endian', 'magic', 'endian_marker', 'start', 'end', 'bytes', 'block_header_bytes', 'header_bytes', 'checksum', 'computed_checksum', 'checksum_bytes', 'header_sha256')), ('journal_info', ('flags', 'jib_offset', 'offset', 'bytes', 'jib_sha256')), ('journal', ('status', 'state', 'endian', 'start', 'end', 'bytes', 'block_header_bytes', 'header_bytes', 'checksum', 'checksum_bytes', 'flags', 'journal_bytes', 'baseline_headers_identical', 'baseline_jib_identical', 'journal_all_zero'))):
                if key in row:
                    item[key] = fields(row[key], names)
            if 'header_classification' in row:
                proof = row['header_classification']
                item['header_classification'] = fields(proof, ('schema', 'state', 'volume_name', 'volume_offset', 'volume_bytes', 'header_bytes', 'baseline_headers_identical', 'baseline_jib_identical', 'baseline_journal_metadata_identical'))
                if 'jib_transition' in proof:
                    item['header_classification']['jib_transition'] = fields(proof['jib_transition'], ('baseline_flags', 'current_flags', 'cleared_mask', 'compared_bytes', 'other_bytes_identical'))
            if 'volume' in row:
                volume = row['volume']
                attrs = volume.get('attributes')
                require(type(attrs) is list and len(attrs) == 2 and all((type(v) is int and 0 <= v <= 4294967295 for v in attrs)), 'unexpected volume attribute metadata')
                item['volume'] = {'attributes': attrs, 'geometry': fields(volume['geometry'], ('block_bytes', 'blocks', 'jib_block')) if 'geometry' in volume else None}
            journals[name] = item
        row = guest.get('fsck', {}).get(name)
        if row is not None:
            fsck[name] = dict(fields(row, ('status', 'exit_code', 'diagnostic_sha256')), reasons=codes(row['reasons']) if 'reasons' in row else None)
    diagnostics = {}
    for name in ('fsck-system.txt', 'fsck-data.txt'):
        path = work / 'a1/files/inspection' / name
        if os.path.lexists(path):
            m['canonical'](path)
            info = path.stat()
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and (info.st_size <= 4 << 20), 'nonordinary diagnostic file')
            diagnostics[name] = {'present': True, 'bytes': info.st_size}
        else:
            diagnostics[name] = {'present': False}
    require(raw(work / 'result.json') == result_body and raw(guest_path) == guest_body, 'completed guest/host metadata changed during projection')
    for path, pin in current['inputs'].items():
        require(m['sha'](raw(Path(path))) == pin, 'bound input changed during projection')
    for key in ('wrapper', 'runner'):
        absent(start[key], 'completed inspection ' + key)
    absent(child, 'completed inspection QEMU', 'start_ticks')
    print(json.dumps({'schema': 1, 'status': 'SAVED_INSPECTION_GUEST_BOUNDARY_PROJECTION', 'readonly': True, 'observed_utc': m['utc'](), 'owner_accepted': False, 'owner_runner_qemu_absent': True, 'identities': {'wrapper': start['wrapper'], 'inspector': start['runner'], 'qemu': child}, 'bound_inputs_unchanged': True, 'resume1_failure_pins_unchanged': len(previous), 'native_vm_complete_clean_unforced': True, 'host_error': result['error'], 'native': fields(witnesses, ('native_initialization', 'native_execution', 'native_svc_final')), 'cleanup': {**fields(cleanup, ('exit_code', 'echild', 'forced_qemu')), 'forced_descendants': [], 'errors': []}, 'resume2_diagnostic_pins_unchanged': len(m['RESUME2_PRESERVATION_PINS']), 'resume4_jib_pins_unchanged': len(m['RESUME4_PRESERVATION_PINS']), 'guest': dict(fields(guest, ('schema', 'kind', 'status', 'readonly_attachments', 'raw_metadata_unchanged', 'mounted', 'replayed', 'repaired', 'boot_complete', 'gpu_path_complete', 'elapsed_seconds')), policy_nonce_matches=nonce_matches, policy_digest_matches=policy_matches, errors=codes(guest['errors']) if 'errors' in guest else None, cleanup_errors=codes(guest['cleanup_errors']) if 'cleanup_errors' in guest else None, gpt=fields(guest['gpt'], ('status', 'disk_bytes')) if 'gpt' in guest else None, baseline_gpt_matches=baseline_matches, journals=journals, fsck=fsck), 'known_diagnostics': diagnostics, 'failed_host_result_pin': RESULT_PIN, 'raw_logs_exported': False, 'private_file_inventories_exported': False, 'inspection_success_claimed': False}, separators=(',', ':')), flush=True)
if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'schema': 1, 'status': 'GUEST_BOUNDARY_PROJECTION_REFUSED', 'readonly': True, 'error': type(error).__name__ + ': ' + str(error)}, separators=(',', ':')), flush=True)
        raise SystemExit(2)
