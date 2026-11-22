"""Read-only bounded result binding/projection; no native tool or guest starts.

Pin acquisition can bind the prepared source alone. Detailed selected records
require the independently observed actual result pin before a command exists.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import types
BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
SOURCE = BASE / 'run-ios26-data-journal-diagnostic-resume5.py'
OUT = BASE / 'ios26-data-journal-diagnostic-resume5'
SOURCE_PIN = {'bytes': 51923, 'sha256': '85194af9e14f68e16d1990e79603060644a892c772adafc51dc52777055c77c9'}
MODE = 'pin'
RESULT_PIN = None
PAGE = 0

def require(value, message):
    if not value:
        raise ValueError(message)

def sha(body):
    return hashlib.sha256(body).hexdigest()

def pin_ok(value):
    return type(value) is dict and set(value) == {'bytes', 'sha256'} and (type(value['bytes']) is int) and (0 < value['bytes'] <= 128 << 10) and (type(value['sha256']) is str) and re.fullmatch('[0-9a-f]{64}', value['sha256'])

def read(path, limit):
    require(path.resolve(strict=True) == path, 'noncanonical evidence file')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        a = os.fstat(stream.fileno())
        require(stat.S_ISREG(a.st_mode) and a.st_uid == 0 and (a.st_nlink == 1) and (0 <= a.st_size <= limit), 'nonordinary or oversized evidence file')
        body = stream.read(limit + 1)
        b = os.fstat(stream.fileno())
    require(len(body) == a.st_size <= limit and (a.st_dev, a.st_ino, a.st_size, a.st_mtime_ns, a.st_ctime_ns) == (b.st_dev, b.st_ino, b.st_size, b.st_mtime_ns, b.st_ctime_ns), 'evidence changed during read')
    return body

def finalized():
    require(pin_ok(SOURCE_PIN), 'UNRELEASED: exact reviewed host source is not bound')
    require(MODE in ('pin', 'summary', 'records') and type(PAGE) is int and (0 <= PAGE <= 3), 'invalid bounded projection mode')
    if MODE != 'pin':
        require(pin_ok(RESULT_PIN), 'UNRELEASED: actual observed result is not bound')

def validate_completed(result, d):
    require(type(result) is dict and result.get('schema') == 1 and (result.get('kind') == 'readonly_data_journal_diagnostic') and (result.get('status') == 'READONLY_DATA_JOURNAL_DIAGNOSTIC_OBSERVED') and (result.get('source') == {'path': str(SOURCE), **SOURCE_PIN}) and (result.get('parser_source') == {'path': str(d.PARSER_SOURCE), **d.PARSER_SOURCE_PIN}) and (result.get('limits') == d.LIMITS) and (result.get('actual_failed_inspection_pins') == 9), 'completed diagnostic source or scope differs')
    require(all((result.get(k) is True for k in ('diagnostic_only', 'disk_identities_unchanged', 'bound_metadata_unchanged', 'bound_tooling_unchanged', 'recorded_inspection_processes_absent'))) and all((result.get(k) is False for k in ('inspection_success_claimed', 'filesystem_consistency_claimed', 'replay_safety_claimed', 'guest_vm_started', 'fsck_run', 'mounted', 'replayed', 'repaired', 'raw_bytes_exported', 'private_file_inventories_exported', 'whole_image_hashes_recomputed'))) and (result.get('error') is None) and (result.get('preservation_error') is None), 'completed diagnostic preservation or nonacceptance boundary differs')
    owner = result.get('owner')
    require(type(owner) is dict and set(owner) == {'pid', 'starttime'} and (type(owner['pid']) is int) and (owner['pid'] > 1) and (type(owner['starttime']) is int) and (owner['starttime'] > 0), 'completed diagnostic owner identity missing')
    require(type(result.get('started_utc')) is str and type(result.get('finished_utc')) is str, 'completed diagnostic timestamps missing')
    d.validate_parser_analysis(result['analysis'])

def check_children(rows, m):
    require(type(rows) is list and len(rows) == 4 and ([row.get('label') for row in rows] == ['primary', 'alternate', 'jib', 'journal']), 'fixed four owned-child rows required')
    pids = []
    for row in rows:
        pid = row.get('pid')
        require(type(pid) is int and pid > 1 and (pid not in pids) and (row.get('exit_code') == 0) and (row.get('reaped') is True) and (row.get('forced') is False) and (row.get('cleanup_error') is None), 'owned native child was not cleanly reaped')
        require(m.identity(pid) is None, 'recorded owned-child PID is currently occupied')
        pids.append(pid)

def inspect_result():
    finalized()
    require(os.geteuid() == 0 and BASE.resolve(strict=True) == BASE, 'root and canonical result base required')
    source = read(SOURCE, SOURCE_PIN['bytes'])
    require({'bytes': len(source), 'sha256': sha(source)} == SOURCE_PIN, 'reviewed host source changed')
    d = types.ModuleType('bound_readonly_data_journal_result_helpers')
    d.__file__ = str(SOURCE)
    exec(compile(source, str(SOURCE), 'exec'), d.__dict__)
    require(d.OUT == OUT and d.DIAGNOSTIC_SOURCE == SOURCE, 'bound diagnostic scope differs')
    m = d.load_bound_owner()
    if MODE == 'pin' and (not os.path.lexists(OUT / 'result.json')):
        present = os.path.lexists(OUT)
        if present:
            require(OUT.resolve(strict=True) == OUT, 'noncanonical output directory')
            info = OUT.lstat()
            require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0, 'nonordinary output directory')
        require(read(SOURCE, SOURCE_PIN['bytes']) == source, 'diagnostic source changed')
        return (d, m, None, {'output_directory_present': present, 'session_present': present and os.path.lexists(OUT / 'session.json')})
    locks = []
    try:
        for path in (m.PREP / 'owner.lock', m.WORK / 'owner.lock'):
            m.canonical(path)
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            locks.append(fd)
            require(stat.S_ISREG(os.fstat(fd).st_mode), 'nonordinary existing result-check lock')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        body = read(OUT / 'result.json', d.LIMITS['result_bytes'])
        actual_pin = {'bytes': len(body), 'sha256': sha(body)}
        if RESULT_PIN is not None:
            require(pin_ok(RESULT_PIN) and actual_pin == RESULT_PIN, 'actual result binding changed')
        result = json.loads(body)
        validate_completed(result, d)
        m.absent(result['owner'], 'completed Data journal diagnostic')
        check_children(result.get('tool_commands'), m)
        _, inspected, metadata = d.check_metadata(m)
        d.require_absent(m)
        m.refuse_live_children()
        layout, retained_headers = d.load_data_layout(m, metadata)
        prep, tooling, tool, images, before = d.prepare_images(m, inspected, metadata)
        plan = d.read_plan(images, layout, tool, OUT)
        guest, parser = d.load_checkers(m, metadata)
        metadata[str(SOURCE)] = sha(source)
        session_body = read(OUT / 'session.json', d.LIMITS['result_bytes'])
        session = json.loads(session_body)
        require(session == {'schema': 1, 'diagnostic_only': True, 'metadata_sha256': metadata, 'disk_identities': before, 'data_layout': layout, 'limits': d.LIMITS, 'tool': result['tool'], 'parser_source': result['parser_source'], 'read_plan': plan, 'prior_full_hash_records': [row['record'] for row in inspected['backing_chain']], 'whole_image_hashes_recomputed': False}, 'retained diagnostic session differs')
        require(result.get('data_layout') == layout and result.get('previous_full_hash_records') == session['prior_full_hash_records'] and (result.get('tool') == {'path': str(tool), **d.TOOL_PIN}) and (result.get('capability') == {'path': str(d.CAPABILITY_RESULT), **d.CAPABILITY_PIN, 'passed': True}), 'retained diagnostic chain or native tool differs')
        if MODE == 'pin':
            require(type(result.get('retained_reads')) is list and len(result['retained_reads']) == 4, 'fixed retained-read count differs')
            for expected, row, retained in zip(plan, result['tool_commands'], result['retained_reads']):
                require(row.get('label') == expected['label'] and row.get('command') == expected['command'] and (type(retained) is dict) and (set(retained) == {'label', 'path', 'bytes', 'sha256', 'virtual_offset'}) and (retained['label'] == expected['label']) and (retained['path'] == expected['output']) and (retained['bytes'] == expected['bytes']) and (retained['virtual_offset'] == expected['virtual_offset']) and (type(retained['sha256']) is str) and re.fullmatch('[0-9a-f]{64}', retained['sha256']), 'recorded fixed extraction inventory differs')
                exited = read(OUT / (expected['label'] + '.exit.json'), d.LIMITS['tool_output_bytes'])
                require(json.loads(exited) == row, 'owned-child exit receipt differs')
                metadata[str(OUT / (expected['label'] + '.exit.json'))] = sha(exited)
            d.verify_preservation(prep, tooling, images, before, metadata)
            d.require_absent(m)
            check_children(result['tool_commands'], m)
            m.absent(result['owner'], 'completed Data journal diagnostic after pin observation')
            require(read(OUT / 'result.json', d.LIMITS['result_bytes']) == body and read(OUT / 'session.json', d.LIMITS['result_bytes']) == session_body and (read(SOURCE, SOURCE_PIN['bytes']) == source), 'bound result, session or source changed')
            return (d, m, result, actual_pin)
    finally:
        for fd in reversed(locks):
            os.close(fd)

def main():
    d, m, result, result_pin = inspect_result()
    if result is None:
        print(json.dumps({'schema': 1, 'status': 'DATA_JOURNAL_RESULT_NOT_PRESENT', 'readonly': True, 'observed_utc': m.utc(), **result_pin, 'owner_state_known': False, 'completion_claimed': False, 'source': {'path': str(SOURCE), **SOURCE_PIN}, 'native_tool_or_guest_started': False}, separators=(',', ':')), flush=True)
        return
    common = {'schema': 1, 'readonly': True, 'observed_utc': m.utc(), 'source': {'path': str(SOURCE), **SOURCE_PIN}, 'result': {'path': str(OUT / 'result.json'), **result_pin, 'digest_bytes': list(bytes.fromhex(result_pin['sha256']))}, 'owner_absent': True, 'owned_child_pids_absent': True, 'all_own_tool_children_reaped': True, 'forced_tool_children': [], 'tool_commands': 4, 'retained_read_count': 4, 'recorded_inspection_processes_absent': True, 'disk_identities_unchanged': True, 'bound_metadata_unchanged': True, 'bound_tooling_unchanged': True, 'owned_child_exit_receipts_verified': True, 'retained_payloads_reverified': MODE != 'pin', 'pure_parser_recomputed': MODE != 'pin', 'whole_image_hashes_recomputed': False, 'raw_bytes_exported': False, 'private_file_inventories_exported': False, 'inspection_success_claimed': False, 'filesystem_consistency_claimed': False, 'replay_safety_claimed': False, 'native_tool_or_guest_started': False}
    if MODE == 'pin':
        output = {**common, 'status': 'DATA_JOURNAL_RESULT_BINDING_READY', 'diagnostic_status': result['status'], 'parser_status': result['analysis']['status'], 'parser_code': result['analysis']['code'], 'actual_result_bound_before_query': False}
    result_row = output.pop('result')
    print(json.dumps(output, separators=(',', ':')), flush=True)
    print(json.dumps({'result_path': result_row['path'], 'result_bytes': result_row['bytes']}, separators=(',', ':')), flush=True)
    print('result_sha256=' + result_row['sha256'], flush=True)
    print('result_digest_bytes=' + json.dumps(result_row['digest_bytes'], separators=(',', ':')), flush=True)
if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'schema': 1, 'status': 'DATA_JOURNAL_PROJECTION_REFUSED', 'readonly': True, 'error_type': type(error).__name__, 'native_tool_or_guest_started': False}, separators=(',', ':')), flush=True)
        raise SystemExit(2)
