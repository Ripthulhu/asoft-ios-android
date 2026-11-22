# Appended to the exact reviewed owner loader and preservation helpers.
import math
import re
import types

PARTITION_SHA256 = '6874b9b6b68c7fb50c3f9cf05c1b6a86a53f8fed75863c00a6ad9254b1640593'
JOURNAL_FIELDS = ('status', 'state', 'endian', 'start', 'end', 'bytes', 'block_header_bytes',
                  'header_bytes', 'checksum', 'checksum_bytes', 'header_sha256', 'flags',
                  'journal_bytes', 'journal_sha256', 'baseline_journal_sha256', 'journal_all_zero',
                  'exact_authored_jib', 'baseline_headers_identical', 'baseline_jib_identical',
                  'inactive_payload_examined')


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
        if value is None or type(value) in (bool, int) or type(value) is float and math.isfinite(value):
            chosen[name] = value
        elif type(value) is str and re.fullmatch('[A-Za-z0-9_]{1,100}', value):
            chosen[name] = value
        else:
            raise ValueError('non-scalar selected metadata: ' + name)
    return chosen


def codes(values):
    if values is None:
        return None
    if type(values) is not list or len(values) > 16:
        raise ValueError('classified code list exceeds bound')
    result = []
    for value in values:
        row = value if type(value) is dict else {'code': value}
        chosen = fields(row, ('code', 'type'))
        if not chosen or any(type(v) is not str for v in chosen.values()):
            raise ValueError('classified error code is unavailable')
        result.append(chosen)
    return result


def bound_module(m, path, expected):
    body = m['read_bytes'](path)
    m['require'](m['sha'](body) == expected, 'canonical proof validator changed')
    module = types.ModuleType('bound_resume5_' + path.stem)
    module.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module


def completed_context(m):
    require, raw, read, absent = (m[k] for k in ('require', 'read_bytes', 'read_json', 'absent'))
    owner, work = m['OWNER'], m['WORK']
    preservation = input_preservation(m)
    captured = {}

    def capture(path):
        body = raw(path, 4 << 20)
        captured[path] = body
        return body

    def document(path):
        return json.loads(capture(path))

    start, end = document(owner / 'owner.json'), document(owner / 'exit.json')
    command = m['COMMAND'] + ['--execute']
    require(start.get('schema') == end.get('schema') == 1 and
            start.get('command') == end.get('command') == document(owner / 'command.json') == command and
            all(start.get(k) == end.get(k) for k in ('started_utc', 'wrapper', 'runner')) and
            end.get('exit_code') == end.get('owner_exit_code') == 0 and end.get('accepted') is True and
            end.get('runner_started') is True and end.get('runner_reaped') is True and
            end.get('forced_runner') is False and end.get('wrapper_error') is None and
            end.get('cleanup_errors') == [] and end.get('finished_utc'),
            'accepted clean outer lifecycle is unavailable')
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
    require(vm.get('status') == 'VM_OBSERVATION_COMPLETE' and vm.get('error') is None and
            vm.get('witnesses') == result.get('native_witnesses') and
            vm.get('cleanup') == result.get('cleanup') and vm.get('natural_exit') is True,
            'recorded VM differs from accepted host result')
    launch = work / 'a1/launch.json'
    require(result.get('launch') == {'path': str(launch), 'sha256': m['sha'](capture(launch))}, 'VM launch binding differs')
    guest = document(work / 'a1/files/inspection/result.json')
    require(guest == result.get('guest_result'), 'returned guest result differs')
    diagnostics = {}
    for name in ('fsck-system.txt', 'fsck-data.txt'):
        body = capture(work / 'a1/files/inspection' / name)
        diagnostics[name] = {'present': True, 'bytes': len(body), 'sha256': m['sha'](body)}
    require(m['accept_result'](current) == m['sha'](result_body) == end.get('inspection_result_sha256'),
            'accepted host result binding differs')
    host_path = m['INSPECTOR'] / 'inspect_ios26_firstboot.py'
    host = bound_module(m, host_path, m['SOURCE_HASHES'][host_path])
    auditor_path = Path(expected['partition_guest_source'])
    require(expected.get('partition_guest_sha256') == PARTITION_SHA256 and
            policy.get('partition_guest_sha256') == PARTITION_SHA256, 'partition validator binding differs')
    auditor = bound_module(m, auditor_path, PARTITION_SHA256)
    validated = host.guest_pass({'prep': types.SimpleNamespace(digest=m['digest']), 'auditor': auditor},
                                work / 'a1/files/inspection', policy)
    require(validated == guest, 'canonical validator returned different guest metadata')
    require(input_preservation(m) == preservation, 'bound metadata changed during projection')
    for path, body in captured.items():
        require(raw(path, 4 << 20) == body, 'completed metadata changed during projection')
    for key in ('wrapper', 'runner'):
        absent(start[key], 'completed inspection ' + key)
    absent(child, 'completed inspection QEMU', 'start_ticks')
    return {'owner': end, 'result': result, 'guest': guest, 'policy': policy, 'diagnostics': diagnostics,
            'canonical_pass': True, 'canonical_error': None, 'accepted': True,
            'result_sha256': m['sha'](result_body), 'preservation': preservation}


def volume(row):
    if row is None:
        return None
    chosen = fields(row, ('primary_sha256', 'alternate_sha256'))
    attributes = row.get('attributes')
    if type(attributes) is not list or len(attributes) != 2 or any(type(x) is not int or not 0 <= x <= 0xFFFFFFFF for x in attributes):
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
    for key, names in (
        ('metadata', ('endian', 'magic', 'endian_marker', 'start', 'end', 'bytes', 'block_header_bytes', 'header_bytes',
                      'checksum', 'computed_checksum', 'checksum_bytes', 'header_sha256')),
        ('journal_info', ('flags', 'jib_offset', 'offset', 'bytes', 'jib_sha256')),
        ('journal', JOURNAL_FIELDS)):
        selected[key] = fields(row.get(key), names)
    proof = row.get('header_classification')
    selected['header_classification'] = fields(proof, ('schema', 'state', 'volume_name', 'volume_offset', 'volume_bytes',
        'header_bytes', 'baseline_headers_identical', 'baseline_jib_identical', 'baseline_journal_metadata_identical'))
    if proof is not None:
        for key, names in (
            ('baseline_journal_info', ('flags', 'jib_offset', 'offset', 'bytes', 'jib_sha256')),
            ('baseline_journal', JOURNAL_FIELDS),
            ('jib_transition', ('baseline_flags', 'current_flags', 'cleared_mask', 'compared_bytes', 'other_bytes_identical'))):
            selected['header_classification'][key] = fields(proof.get(key), names)
    return selected


def render(context, view):
    guest, policy, result = context['guest'], context['policy'], context['result']
    summary = {'schema': 1, 'status': 'RESUME5_INSPECTION_METADATA_PROJECTION', 'readonly': True,
        'view': view, 'observed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'owner_accepted': context['accepted'], 'canonical_guest_pass': context['canonical_pass'],
        'canonical_validation_error_type': context['canonical_error'],
        'completed_recorded_processes_absent': True, 'metadata_stable': True,
        'inspection_result_sha256': context['result_sha256'],
        'raw_logs_or_payloads_exported': False, 'full_disk_hashes_recomputed_by_query': False}
    print(json.dumps(summary, separators=(',', ':')), flush=True)
    if view in ('root', 'data'):
        name = 'iOSRoot' if view == 'root' else 'Data'
        print(json.dumps({name: journal_projection(guest.get('journals', {}).get(name))}, separators=(',', ':')), flush=True)
        return
    nonce_matches = None
    if 'inspection_nonce' in guest and 'inspection_nonce' in policy:
        nonce_matches = (all(type(row['inspection_nonce']) is str and re.fullmatch('[0-9a-f]{32}', row['inspection_nonce']) for row in (guest, policy)) and
                         guest['inspection_nonce'] == policy['inspection_nonce'])
    gpt_matches = None
    if 'gpt' in guest and 'baseline_gpt' in guest:
        gpt_matches = (all(type(guest[k]) is dict and type(guest[k].get('disk_bytes')) is int and guest[k]['disk_bytes'] > 0 for k in ('gpt', 'baseline_gpt')) and
                       guest['gpt'] == guest['baseline_gpt'])
    fsck = {}
    for name in ('iOSRoot', 'Data'):
        row = guest.get('fsck', {}).get(name)
        fsck[name] = None if row is None else dict(fields(row, ('status', 'exit_code', 'diagnostic_sha256')), reasons=codes(row.get('reasons')))
    print(json.dumps({'guest': fields(guest, ('schema', 'kind', 'status', 'readonly_attachments', 'raw_metadata_unchanged', 'mounted', 'replayed', 'repaired')),
        'errors': codes(guest.get('errors')), 'cleanup_errors': codes(guest.get('cleanup_errors')),
        'policy_nonce_matches': nonce_matches, 'baseline_gpt_matches': gpt_matches,
        'gpt': fields(guest.get('gpt'), ('status', 'disk_bytes')), 'fsck': fsck,
        'diagnostics': context['diagnostics'],
        'recorded_host_preservation': fields(result, ('full_backing_chain_unchanged', 'preparation_and_guard_unchanged', 'identity_error',
                                                     'boot_complete', 'gpu_path_complete', 'app_gate_changed')),
        'current_input_preservation': context['preservation']}, separators=(',', ':')), flush=True)


def main():
    parser = argparse.ArgumentParser(description='Read-only compact final proof metadata; no raw diagnostics or filesystem actions.')
    parser.add_argument('--view', choices=('root', 'data', 'fsck'), required=True)
    args = parser.parse_args()
    render(completed_context(load_owner()), args.view)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'schema': 1, 'status': 'RESUME5_PROOF_PROJECTION_REFUSED', 'readonly': True,
                          'error_type': type(exc).__name__, 'error': str(exc)[:240]}, separators=(',', ':')), flush=True)
        raise SystemExit(2)
