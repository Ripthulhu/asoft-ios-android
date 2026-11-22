"""Future read-only acquisition of a clean completed diagnostic result binding.

This reader emits only a receipt pin and fixed status fields. It does not release
the detailed projection and does not start any tool or guest.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import types


BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
SOURCE = BASE / 'run-ios26-root-jib-diagnostic-resume4.py'
SOURCE_PIN = None  # Bind only the independently reviewed diagnostic source.
RESULT = BASE / 'ios26-root-jib-diagnostic-resume4/result.json'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path, limit):
    require(path.resolve(strict=True) == path, 'noncanonical input')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_uid == 0 and
                0 <= before.st_size <= limit, 'input identity differs')
        body = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    require(len(body) == before.st_size <= limit and
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
            'input changed during read')
    return body


def main():
    require(type(SOURCE_PIN) is dict, 'unreleased diagnostic source binding')
    require(os.geteuid() == 0, 'root metadata reader required')
    source = read(SOURCE, SOURCE_PIN['bytes'])
    require({'bytes': len(source), 'sha256': hashlib.sha256(source).hexdigest()} == SOURCE_PIN,
            'diagnostic source differs')
    diagnostic = types.ModuleType('verified_root_jib_binding_source')
    diagnostic.__file__ = str(SOURCE)
    exec(compile(source, str(SOURCE), 'exec'), diagnostic.__dict__)
    require(diagnostic.OUT / 'result.json' == RESULT, 'fixed result path differs')
    m = diagnostic.load_bound_owner()
    body = read(RESULT, diagnostic.LIMITS['result_bytes'])
    result = json.loads(body)
    require(result.get('schema') == 1 and result.get('kind') == 'readonly_root_jib_diagnostic' and
            result.get('status') == 'READONLY_ROOT_JIB_COMPARISON_OBSERVED', 'completed diagnostic required')
    require(result.get('source') == {'path': str(SOURCE), **SOURCE_PIN} and
            type(result.get('jibs')) is list and len(result['jibs']) == 2 and
            type(result.get('tool_commands')) is list and len(result['tool_commands']) == 16,
            'fixed source and extraction inventory required')
    require(all(row.get('reaped') is True and row.get('forced') is False and row.get('exit_code') == 0 and
                not row.get('cleanup_error') for row in result['tool_commands']), 'owned tool cleanup differs')
    require(all(result.get(key) is True for key in
                ('diagnostic_only', 'disk_identities_unchanged', 'bound_metadata_unchanged', 'bound_tooling_unchanged',
                 'recorded_inspection_processes_absent')),
            'preservation differs')
    require(all(result.get(key) is False for key in
                ('inspection_success_claimed', 'guest_vm_started', 'mounted', 'replayed', 'repaired',
                 'fsck_run', 'full_disk_hashes_recomputed', 'journal_pointer_followed',
                 'raw_bytes_exported', 'difference_classified_as_safe')), 'diagnostic boundary differs')
    require(result.get('error') is None and result.get('preservation_error') is None, 'diagnostic retained an error')
    m.absent(result['owner'], 'root JIB diagnostic owner')
    require(read(RESULT, diagnostic.LIMITS['result_bytes']) == body and read(SOURCE, SOURCE_PIN['bytes']) == source,
            'bound result or source changed')
    digest = hashlib.sha256(body)
    print(json.dumps({'schema': 1, 'status': 'ROOT_JIB_RESULT_BINDING_READY', 'readonly': True,
        'observed_utc': m.utc(), 'diagnostic_status': result['status'],
        'result': {'path': str(RESULT), 'bytes': len(body), 'sha256': digest.hexdigest(),
                   'digest_bytes': list(digest.digest())},
        'source': {'path': str(SOURCE), **SOURCE_PIN}, 'jibs': 2, 'tool_commands': 16,
        'all_own_tool_children_reaped': True, 'forced_tool_children': [],
        'disk_identities_unchanged': True, 'bound_metadata_unchanged': True, 'bound_tooling_unchanged': True,
        'recorded_inspection_processes_absent': True, 'journal_pointer_followed': False,
        'difference_classified_as_safe': False, 'raw_bytes_exported': False,
        'inspection_success_claimed': False, 'full_disk_hashes_recomputed': False,
        'raw_jib_bytes_exported': False, 'error': None, 'preservation_error': None}, separators=(',', ':')), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status': 'ROOT_JIB_RESULT_BINDING_NOT_READY_OR_REFUSED', 'readonly': True,
                          'error_type': type(error).__name__}, separators=(',', ':')), flush=True)
        raise SystemExit(2)
