"""Read-only bounded result binding/projection; no source or device execution.

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
SOURCE_PIN = None
RESULT_PIN = None
MODE = 'pin'
PAGE = 0


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def pin_ok(value):
    return type(value) is dict and set(value) == {'bytes', 'sha256'} and type(value['bytes']) is int and \
        0 < value['bytes'] <= 128 << 10 and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256'])


def read(path, limit):
    require(path.resolve(strict=True) == path, 'noncanonical evidence file')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        a = os.fstat(stream.fileno())
        require(stat.S_ISREG(a.st_mode) and a.st_uid == 0 and a.st_nlink == 1 and a.st_size <= limit,
                'nonordinary or oversized evidence file')
        body = stream.read(limit + 1)
        b = os.fstat(stream.fileno())
    require(len(body) == a.st_size <= limit and
            (a.st_dev, a.st_ino, a.st_size, a.st_mtime_ns, a.st_ctime_ns) ==
            (b.st_dev, b.st_ino, b.st_size, b.st_mtime_ns, b.st_ctime_ns), 'evidence changed during read')
    return body


def finalized():
    require(pin_ok(SOURCE_PIN), 'UNRELEASED: exact reviewed host source is not bound')
    require(MODE in ('pin', 'summary', 'records') and type(PAGE) is int and 0 <= PAGE <= 3,
            'invalid bounded projection mode')
    if MODE != 'pin':
        require(pin_ok(RESULT_PIN), 'UNRELEASED: actual observed result is not bound')


def validate_completed(result, d):
    require(type(result) is dict and result.get('schema') == 1 and
            result.get('kind') == 'readonly_data_journal_diagnostic' and
            result.get('status') == 'READONLY_DATA_JOURNAL_DIAGNOSTIC_OBSERVED' and
            result.get('source') == {'path': str(SOURCE), **SOURCE_PIN} and
            result.get('parser_source') == {'path': str(d.PARSER_SOURCE), **d.PARSER_SOURCE_PIN} and
            result.get('limits') == d.LIMITS and result.get('actual_failed_inspection_pins') == 9,
            'completed diagnostic source or scope differs')
    require(all(result.get(k) is True for k in ('diagnostic_only', 'disk_identities_unchanged',
                'bound_metadata_unchanged', 'bound_tooling_unchanged', 'recorded_inspection_processes_absent')) and
            all(result.get(k) is False for k in ('inspection_success_claimed', 'filesystem_consistency_claimed',
                'replay_safety_claimed', 'guest_vm_started', 'fsck_run', 'mounted', 'replayed', 'repaired',
                'raw_bytes_exported', 'private_file_inventories_exported', 'whole_image_hashes_recomputed')) and
            result.get('error') is None and result.get('preservation_error') is None,
            'completed diagnostic preservation or nonacceptance boundary differs')
    owner = result.get('owner')
    require(type(owner) is dict and set(owner) == {'pid', 'starttime'} and
            type(owner['pid']) is int and owner['pid'] > 1 and type(owner['starttime']) is int and owner['starttime'] > 0,
            'completed diagnostic owner identity missing')
    require(type(result.get('started_utc')) is str and type(result.get('finished_utc')) is str,
            'completed diagnostic timestamps missing')
    d.validate_parser_analysis(result['analysis'])


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
        require(session == {'schema': 1, 'diagnostic_only': True, 'metadata_sha256': metadata,
            'disk_identities': before, 'data_layout': layout, 'limits': d.LIMITS, 'tool': result['tool'],
            'parser_source': result['parser_source'], 'read_plan': plan,
            'prior_full_hash_records': [row['record'] for row in inspected['backing_chain']],
            'whole_image_hashes_recomputed': False}, 'retained diagnostic session differs')
        require(result.get('data_layout') == layout and
                result.get('previous_full_hash_records') == session['prior_full_hash_records'] and
                result.get('tool') == {'path': str(tool), **d.TOOL_PIN} and
                result.get('capability') == {'path': str(d.CAPABILITY_RESULT), **d.CAPABILITY_PIN, 'passed': True},
                'retained diagnostic chain or native tool differs')
        rows = result.get('tool_commands')
        require(type(rows) is list and len(rows) == len(plan) == 4, 'fixed four-command result missing')
        payloads, reads, retained_pins = {}, [], {}
        for expected, row in zip(plan, rows):
            label = expected['label']
            require(row.get('label') == label and row.get('command') == expected['command'] and
                    row.get('exit_code') == 0 and row.get('reaped') is True and row.get('forced') is False and
                    row.get('cleanup_error') is None, 'owned diagnostic tool did not finish cleanly')
            path = Path(expected['output'])
            raw = read(path, expected['bytes'])
            require(len(raw) == expected['bytes'], 'retained fixed read changed size')
            payloads[label] = raw
            reads.append({'label': label, 'path': str(path), 'bytes': len(raw), 'sha256': sha(raw),
                          'virtual_offset': expected['virtual_offset']})
            retained_pins[str(path)] = {'bytes': len(raw), 'sha256': sha(raw)}
            for suffix in ('command.json', 'exit.json', 'stdout'):
                p = OUT / (label + '.' + suffix)
                b = read(p, d.LIMITS['tool_output_bytes'])
                retained_pins[str(p)] = {'bytes': len(b), 'sha256': sha(b)}
                if suffix == 'exit.json':
                    require(json.loads(b) == row, 'retained owned-child exit differs')
                elif suffix == 'command.json':
                    require(json.loads(b) == {'label': label, 'command': row['command'], 'pid': None,
                        'exit_code': None, 'reaped': False, 'forced': False}, 'retained owned-child command differs')
                else:
                    require(row.get('output_bytes') == len(b) and row.get('output_sha256') == sha(b),
                            'retained owned-child output differs')
        require(result.get('retained_reads') == reads and
                payloads['primary'] == retained_headers[0] and payloads['alternate'] == retained_headers[1],
                'retained Data read inventory or headers differ')
        require(result.get('jib') == d.validate_jib(payloads['jib'], retained_headers, guest), 'retained Data JIB differs')
        d.validate_journal_header(payloads['journal'], guest)
        analysis = d.validate_parser_analysis(parser.analyze_journal(payloads['journal'], volume_bytes=d.DATA_BYTES,
                                                       expected_header_sha256=d.EXPECTED_DATA_HEADER_SHA256))
        require(result['analysis'] == analysis, 'retained pure parser diagnosis differs')
        d.verify_preservation(prep, tooling, images, before, metadata)
        d.require_absent(m)
        m.absent(result['owner'], 'completed Data journal diagnostic after result validation')
        require(read(OUT / 'result.json', d.LIMITS['result_bytes']) == body and
                read(OUT / 'session.json', d.LIMITS['result_bytes']) == session_body,
                'retained result or session changed during projection')
        return d, m, result, actual_pin
    finally:
        for fd in reversed(locks):
            os.close(fd)


def main():
    d, m, result, result_pin = inspect_result()
    common = {'schema': 1, 'readonly': True, 'observed_utc': m.utc(),
              'source': {'path': str(SOURCE), **SOURCE_PIN},
              'result': {'path': str(OUT / 'result.json'), **result_pin,
                         'digest_bytes': list(bytes.fromhex(result_pin['sha256']))},
              'owner_absent': True, 'recorded_inspection_processes_absent': True,
              'disk_identities_unchanged': True, 'bound_metadata_unchanged': True,
              'bound_tooling_unchanged': True, 'retained_reads_and_owned_child_receipts_verified': True,
              'whole_image_hashes_recomputed': False, 'raw_bytes_exported': False,
              'private_file_inventories_exported': False, 'inspection_success_claimed': False,
              'filesystem_consistency_claimed': False, 'replay_safety_claimed': False}
    if MODE == 'pin':
        output = {**common, 'status': 'DATA_JOURNAL_RESULT_BINDING_READY',
                  'diagnostic_status': result['status'], 'parser_status': result['analysis']['status'],
                  'parser_code': result['analysis']['code'], 'actual_result_bound_before_query': False}
    elif MODE == 'summary':
        output = {**common, 'status': 'DATA_JOURNAL_DIAGNOSIS_SUMMARY', 'actual_result_bound_before_query': True,
                  'analysis': d.compact_analysis(result['analysis'])}
    else:
        records = result['analysis']['records']
        output = {**common, 'status': 'DATA_JOURNAL_SELECTED_LIST_RECORDS', 'actual_result_bound_before_query': True,
                  'page': PAGE, 'page_size': 4, 'total_records': len(records),
                  'records': records[PAGE * 4:(PAGE + 1) * 4], 'parser_status': result['analysis']['status'],
                  'parser_code': result['analysis']['code']}
    print(json.dumps(output, separators=(',', ':')), flush=True)


if __name__ == '__main__':
    main()
