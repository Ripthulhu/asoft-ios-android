"""Read-only saved-inspection status and, after acceptance, fourteen input pins."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import stat
SOURCE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-saved-inspection-resume5.py')
SOURCE_BYTES = 60564
SOURCE_SHA256 = 'dbb570dc9b3354a5d7c4eb218883ab22f25afe24757c429e46cc7c04de1baa63'
PREFLIGHT_PIN = {'bytes': 9069, 'sha256': '4630b5dc921d3bee52d4805cc829e3624144b763d27b53937443e43c69db44f6'}

def load_owner():
    if type(PREFLIGHT_PIN) is not dict:
        raise ValueError('unreleased observer requires actual fresh preflight')
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

def input_preservation(m):
    """Check metadata and reviewed source bytes without running or adopting a child."""
    owner, raw, require = (m['OWNER'], m['read_bytes'], m['require'])
    preflight_body = raw(owner / 'preflight.json')
    require(len(preflight_body) == PREFLIGHT_PIN['bytes'] and hashlib.sha256(preflight_body).hexdigest() == PREFLIGHT_PIN['sha256'], 'actual new preflight changed')
    current = m['read_json'](owner / 'prerequisites.json')
    m['validate_preflight'](json.loads(preflight_body), current)
    for path, expected in m['SOURCE_HASHES'].items():
        require(hashlib.sha256(raw(path)).hexdigest() == expected, 'reviewed runtime or inspector source changed')
    previous = m['previous_failure_inputs']()
    recent = m['resume2_failure_inputs']()
    latest = m['resume4_failure_inputs']()
    require(all((current['inputs'].get(path) == expected for path, expected in latest.items())), 'resume4/JIB preservation was not bound by fresh preflight')
    require(all((current['inputs'].get(path) == expected for path, expected in recent.items())), 'resume2/diagnostic preservation was not bound by fresh preflight')
    require(all((current['inputs'].get(path) == expected for path, expected in previous.items())), 'prior failure preservation was not bound by fresh preflight')
    for path, expected in current['inputs'].items():
        require(hashlib.sha256(raw(Path(path))).hexdigest() == expected, 'bound input changed: ' + path)
    return {'preflight_stdout_unchanged': True, 'reviewed_sources_unchanged': True, 'bound_inputs_unchanged': True, 'resume1_failure_pins_unchanged': len(previous), 'resume2_diagnostic_pins_unchanged': len(m['RESUME2_PRESERVATION_PINS']), 'resume4_jib_pins_unchanged': len(m['RESUME4_PRESERVATION_PINS']), 'prior_recorded_identities_absent': True, 'error': None}
import math
import re
import types
PARTITION_SHA256 = '6874b9b6b68c7fb50c3f9cf05c1b6a86a53f8fed75863c00a6ad9254b1640593'
JOURNAL_FIELDS = ('status', 'state', 'endian', 'start', 'end', 'bytes', 'block_header_bytes', 'header_bytes', 'checksum', 'checksum_bytes', 'header_sha256', 'flags', 'journal_bytes', 'journal_sha256', 'baseline_journal_sha256', 'journal_all_zero', 'exact_authored_jib', 'baseline_headers_identical', 'baseline_jib_identical', 'inactive_payload_examined')

def fields(row, names):
    if row is None:
        return None
    if type(row) is not dict:
        raise ValueError('selected metadata is not an object')
    chosen = {}
    for name in names:
        if name not in row:
            continue
        value = row[name]
        if value is None or type(value) in (bool, int) or (type(value) is float and math.isfinite(value)):
            chosen[name] = value
        elif type(value) is str and re.fullmatch('[A-Za-z0-9_]{1,100}', value):
            chosen[name] = value
        else:
            raise ValueError('non-scalar selected metadata: ' + name)
    return chosen

def bound_module(m, path, expected):
    body = m['read_bytes'](path)
    m['require'](m['sha'](body) == expected, 'canonical proof validator changed')
    module = types.ModuleType('bound_resume5_' + path.stem)
    module.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module

def completed_context(m):
    require, raw, read, absent = (m[k] for k in ('require', 'read_bytes', 'read_json', 'absent'))
    owner, work = (m['OWNER'], m['WORK'])
    preservation = input_preservation(m)
    captured = {}

    def capture(path):
        body = raw(path, 4 << 20)
        captured[path] = body
        return body

    def document(path):
        return json.loads(capture(path))
    start, end = (document(owner / 'owner.json'), document(owner / 'exit.json'))
    command = m['COMMAND'] + ['--execute']
    require(start.get('schema') == end.get('schema') == 1 and start.get('command') == end.get('command') == document(owner / 'command.json') == command and all((start.get(k) == end.get(k) for k in ('started_utc', 'wrapper', 'runner'))) and (end.get('exit_code') == end.get('owner_exit_code') == 0) and (end.get('accepted') is True) and (end.get('runner_started') is True) and (end.get('runner_reaped') is True) and (end.get('forced_runner') is False) and (end.get('wrapper_error') is None) and (end.get('cleanup_errors') == []) and end.get('finished_utc'), 'accepted clean outer lifecycle is unavailable')
    for key in ('wrapper', 'runner'):
        absent(start[key], 'completed inspection ' + key)
    current = document(owner / 'prerequisites.json')
    expected = document(owner / 'preflight.json')['inspection_session']
    result_body = capture(work / 'result.json')
    require(result_body == capture(work / 'a1/inspection-result.json'), 'host result copies differ')
    result = json.loads(result_body)
    policy = document(work / 'a1/expected-policy.json')
    require(policy.get('inspection_session_sha256') == m['digest'](expected), 'policy belongs to another session')
    vm = document(work / 'a1/vm-result.json')
    child = document(work / 'a1/vm.child.json')
    absent(child, 'completed inspection QEMU', 'start_ticks')
    require(vm.get('status') == 'VM_OBSERVATION_COMPLETE' and vm.get('error') is None and (vm.get('witnesses') == result.get('native_witnesses')) and (vm.get('cleanup') == result.get('cleanup')) and (vm.get('natural_exit') is True), 'recorded VM differs from accepted host result')
    launch = work / 'a1/launch.json'
    require(result.get('launch') == {'path': str(launch), 'sha256': m['sha'](capture(launch))}, 'VM launch binding differs')
    guest = document(work / 'a1/files/inspection/result.json')
    require(guest == result.get('guest_result'), 'returned guest result differs')
    diagnostics = {}
    for name in ('fsck-system.txt', 'fsck-data.txt'):
        body = capture(work / 'a1/files/inspection' / name)
        diagnostics[name] = {'present': True, 'bytes': len(body), 'sha256': m['sha'](body)}
    require(m['accept_result'](current) == m['sha'](result_body) == end.get('inspection_result_sha256'), 'accepted host result binding differs')
    host_path = m['INSPECTOR'] / 'inspect_ios26_firstboot.py'
    host = bound_module(m, host_path, m['SOURCE_HASHES'][host_path])
    auditor_path = Path(expected['partition_guest_source'])
    require(expected.get('partition_guest_sha256') == PARTITION_SHA256 and policy.get('partition_guest_sha256') == PARTITION_SHA256, 'partition validator binding differs')
    auditor = bound_module(m, auditor_path, PARTITION_SHA256)
    validated = host.guest_pass({'prep': types.SimpleNamespace(digest=m['digest']), 'auditor': auditor}, work / 'a1/files/inspection', policy)
    require(validated == guest, 'canonical validator returned different guest metadata')
    require(input_preservation(m) == preservation, 'bound metadata changed during projection')
    for path, body in captured.items():
        require(raw(path, 4 << 20) == body, 'completed metadata changed during projection')
    for key in ('wrapper', 'runner'):
        absent(start[key], 'completed inspection ' + key)
    absent(child, 'completed inspection QEMU', 'start_ticks')
    return {'owner': end, 'result': result, 'guest': guest, 'policy': policy, 'diagnostics': diagnostics, 'canonical_pass': True, 'canonical_error': None, 'accepted': True, 'result_sha256': m['sha'](result_body), 'preservation': preservation}

def volume(row):
    if row is None:
        return None
    chosen = fields(row, ('primary_sha256', 'alternate_sha256'))
    attributes = row.get('attributes')
    if type(attributes) is not list or len(attributes) != 2 or any((type(x) is not int or not 0 <= x <= 4294967295 for x in attributes)):
        raise ValueError('volume attributes unavailable')
    chosen['attributes'] = attributes
    chosen['geometry'] = fields(row.get('geometry'), ('block_bytes', 'blocks', 'jib_block'))
    return chosen

def journal_projection(row):
    if row is None:
        return None
    selected = fields(row, ('status', 'code'))
    selected['volume'] = volume(row.get('volume'))
    selected['baseline_volume'] = volume(row.get('baseline_volume'))
    for key, names in (('metadata', ('endian', 'magic', 'endian_marker', 'start', 'end', 'bytes', 'block_header_bytes', 'header_bytes', 'checksum', 'computed_checksum', 'checksum_bytes', 'header_sha256')), ('journal_info', ('flags', 'jib_offset', 'offset', 'bytes', 'jib_sha256')), ('journal', JOURNAL_FIELDS)):
        selected[key] = fields(row.get(key), names)
    proof = row.get('header_classification')
    selected['header_classification'] = fields(proof, ('schema', 'state', 'volume_name', 'volume_offset', 'volume_bytes', 'header_bytes', 'baseline_headers_identical', 'baseline_jib_identical', 'baseline_journal_metadata_identical'))
    if proof is not None:
        for key, names in (('baseline_journal_info', ('flags', 'jib_offset', 'offset', 'bytes', 'jib_sha256')), ('baseline_journal', JOURNAL_FIELDS), ('jib_transition', ('baseline_flags', 'current_flags', 'cleared_mask', 'compared_bytes', 'other_bytes_identical'))):
            selected['header_classification'][key] = fields(proof.get(key), names)
    return selected

def render(context, view):
    guest, policy, result = (context['guest'], context['policy'], context['result'])
    summary = {'schema': 1, 'status': 'RESUME5_INSPECTION_METADATA_PROJECTION', 'readonly': True, 'view': view, 'observed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'owner_accepted': context['accepted'], 'canonical_guest_pass': context['canonical_pass'], 'canonical_validation_error_type': context['canonical_error'], 'completed_recorded_processes_absent': True, 'metadata_stable': True, 'inspection_result_sha256': context['result_sha256'], 'raw_logs_or_payloads_exported': False, 'full_disk_hashes_recomputed_by_query': False}
    print(json.dumps(summary, separators=(',', ':')), flush=True)
    if view in ('root', 'data'):
        name = 'iOSRoot' if view == 'root' else 'Data'
        print(json.dumps({name: journal_projection(guest.get('journals', {}).get(name))}, separators=(',', ':')), flush=True)
        return

def main():
    parser = argparse.ArgumentParser(description='Read-only compact final proof metadata; no raw diagnostics or filesystem actions.')
    parser.add_argument('--view', choices=('root', 'data'), required=True)
    args = parser.parse_args()
    render(completed_context(load_owner()), args.view)
if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'schema': 1, 'status': 'RESUME5_PROOF_PROJECTION_REFUSED', 'readonly': True, 'error_type': type(exc).__name__, 'error': str(exc)[:240]}, separators=(',', ':')), flush=True)
        raise SystemExit(2)
