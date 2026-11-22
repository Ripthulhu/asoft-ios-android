"""Read only the fixed diagnostic receipt and eight header scalar projections."""
import hashlib
import json
import os
from pathlib import Path
import stat
import types

SOURCE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-hfs-header-diagnostic-resume2.py')
SOURCE_PIN = None  # Finalize only to the reviewed installed diagnostic source.
RESULT_PIN = None  # Finalize only from the actual independently reviewed diagnostic result.


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path, limit):
    require(path.resolve(strict=True) == path, 'noncanonical input')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as f:
        before = os.fstat(f.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= limit, 'nonordinary or oversized input')
        body = f.read(limit + 1)
        after = os.fstat(f.fileno())
    require(len(body) == before.st_size <= limit and
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'input changed during read')
    return body


def main():
    require(os.geteuid() == 0 and type(SOURCE_PIN) is dict and type(RESULT_PIN) is dict,
            'root and finalized diagnostic source/result required')
    page = globals().get('__page__')
    require(page is None or type(page) is int and 0 <= page < 4, 'invalid bounded header page')
    source = read(SOURCE, SOURCE_PIN['bytes'])
    require({'bytes': len(source), 'sha256': hashlib.sha256(source).hexdigest()} == SOURCE_PIN, 'diagnostic source differs')
    d = types.ModuleType('verified_header_diagnostic')
    d.__file__ = str(SOURCE)
    exec(compile(source, str(SOURCE), 'exec'), d.__dict__)
    m = d.load_bound_owner()
    body = read(d.OUT / 'result.json', d.LIMITS['result_bytes'])
    require({'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()} == RESULT_PIN, 'actual diagnostic result differs')
    result = json.loads(body)
    require(result.get('schema') == 1 and result.get('kind') == 'readonly_hfs_header_diagnostic' and
            result.get('diagnostic_only') is True and result.get('inspection_success_claimed') is False and
            result.get('guest_vm_started') is False and all(result.get(k) is False for k in ('mounted', 'replayed', 'repaired', 'fsck_run')) and
            result.get('source') == {'path': str(SOURCE), **SOURCE_PIN}, 'diagnostic result/source differs')
    m.absent(result['owner'], 'header diagnostic owner')
    rows = result.get('headers')
    commands = result.get('tool_commands')
    require(type(rows) is list and len(rows) <= 8 and type(commands) is list and len(commands) <= 8, 'result inventory exceeds fixed bounds')
    if result.get('status') == 'READONLY_HFS_HEADERS_OBSERVED':
        require(len(rows) == len(commands) == 8 and result.get('error') is None and result.get('preservation_error') is None and
                all(result.get(k) is True for k in ('disk_identities_unchanged', 'bound_metadata_unchanged', 'bound_tooling_unchanged')) and
                result.get('full_disk_hashes_recomputed') is False and
                result.get('capability') == {'path': str(d.CAPABILITY_RESULT), **d.CAPABILITY_PIN, 'passed': True,
                                            'source_sha256': d.CAPABILITY_SOURCE_SHA256}, 'completed diagnostic receipt is inconsistent')
        _, inspected, _ = d.check_metadata(m)
        images = [Path(row['identity']['path']) for row in inspected['backing_chain']]
        require(len(images) == 2, 'fixed image pair differs')
        index = 0
        for image_index, image in enumerate(images):
            for start, sectors, volume in d.PARTITIONS:
                for copy, relative in (('primary', 1024), ('alternate', sectors * 512 - 1024)):
                    offset = start * 512 + relative
                    target = d.OUT / ('h' + str(index) + '.bin')
                    expected = d.decode_header(read(target, 512), 'saved' if image_index == 0 else 'baseline', volume, copy, offset, sectors)
                    require(rows[index] == expected, 'retained header and scalar projection differ')
                    cmd = commands[index]
                    require(cmd.get('command') == [result['tool']['path'], 'dd', '-f', 'qcow2', '-O', 'raw', 'bs=512',
                            'count=' + str(offset // 512 + 1), 'skip=' + str(offset // 512), 'if=' + str(image), 'of=' + str(target)] and
                            cmd.get('exit_code') == 0 and cmd.get('reaped') is True and cmd.get('forced') is False and
                            not cmd.get('cleanup_error'), 'actual fixed header command differs')
                    index += 1
    else:
        require(page is None, 'header pages require a complete diagnostic')
    require(read(d.OUT / 'result.json', d.LIMITS['result_bytes']) == body and read(SOURCE, SOURCE_PIN['bytes']) == source,
            'result/source changed during projection')
    digest = hashlib.sha256(body)
    print(json.dumps({'schema': 1, 'status': 'HFS_HEADER_METADATA_PROJECTION', 'readonly': True, 'page': page,
        'diagnostic_status': result.get('status'), 'observed_utc': m.utc(),
        'result': {'path': str(d.OUT / 'result.json'), 'bytes': len(body), 'sha256': digest.hexdigest(), 'digest_bytes': list(digest.digest())},
        'headers': len(rows), 'all_own_tool_children_reaped': all(row.get('reaped') is True for row in commands),
        'forced_tool_children': [row.get('pid') for row in commands if row.get('forced')],
        'disk_identities_unchanged': result.get('disk_identities_unchanged'), 'bound_metadata_unchanged': result.get('bound_metadata_unchanged'),
        'bound_tooling_unchanged': result.get('bound_tooling_unchanged'), 'full_disk_hashes_recomputed': result.get('full_disk_hashes_recomputed'),
        'inspection_success_claimed': False, 'raw_header_bytes_exported': False,
        'error': result.get('error'), 'preservation_error': result.get('preservation_error')}, separators=(',', ':')), flush=True)
    if page is not None:
        for row in rows[page * 2:(page + 1) * 2]:
            print(json.dumps(row, separators=(',', ':')), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status': 'HFS_HEADER_PROJECTION_REFUSED', 'readonly': True,
            'error': type(error).__name__ + ': ' + str(error)}, separators=(',', ':')), flush=True)
        raise SystemExit(2)
