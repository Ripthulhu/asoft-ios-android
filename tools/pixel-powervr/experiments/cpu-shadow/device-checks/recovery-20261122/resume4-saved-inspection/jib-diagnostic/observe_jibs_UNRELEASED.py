"""Future read-only projection, blocked until source and actual result are bound.

Raw JIB blocks and sectors are read only to verify the retained comparison. They
are never exported. This program starts no tool, guest, fsck or other process.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import types


SOURCE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-root-jib-diagnostic-resume4.py')
SOURCE_PIN = None  # Bind only the independently reviewed diagnostic source.
RESULT_PIN = None  # Bind only an actual independently reviewed completed result.


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path, limit):
    require(path.resolve(strict=True) == path, 'noncanonical retained input')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_uid == 0 and before.st_nlink == 1 and
                0 <= before.st_size <= limit, 'nonordinary or oversized retained input')
        body = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    require(len(body) == before.st_size <= limit and
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
            'retained input changed during read')
    return body


def collect():
    require(type(SOURCE_PIN) is dict and type(RESULT_PIN) is dict,
            'unreleased: reviewed source and actual completed-result bindings required')
    require(os.geteuid() == 0, 'root metadata reader required')
    source = read(SOURCE, SOURCE_PIN['bytes'])
    require({'bytes': len(source), 'sha256': hashlib.sha256(source).hexdigest()} == SOURCE_PIN,
            'diagnostic source differs')
    diagnostic = types.ModuleType('verified_root_jib_diagnostic')
    diagnostic.__file__ = str(SOURCE)
    exec(compile(source, str(SOURCE), 'exec'), diagnostic.__dict__)
    d = diagnostic
    m = d.load_bound_owner()
    result_path = d.OUT / 'result.json'
    body = read(result_path, d.LIMITS['result_bytes'])
    require({'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()} == RESULT_PIN,
            'actual completed diagnostic result differs')
    result = json.loads(body)
    require(result.get('schema') == 1 and result.get('kind') == 'readonly_root_jib_diagnostic' and
            result.get('status') == 'READONLY_ROOT_JIB_COMPARISON_OBSERVED' and
            result.get('source') == {'path': str(SOURCE), **SOURCE_PIN}, 'completed diagnostic/source differs')
    require(all(result.get(key) is True for key in
                ('diagnostic_only', 'disk_identities_unchanged', 'bound_metadata_unchanged', 'bound_tooling_unchanged',
                 'recorded_inspection_processes_absent')),
            'recorded preservation differs')
    require(all(result.get(key) is False for key in
                ('inspection_success_claimed', 'guest_vm_started', 'mounted', 'replayed', 'repaired',
                 'fsck_run', 'full_disk_hashes_recomputed', 'journal_pointer_followed',
                 'raw_bytes_exported', 'difference_classified_as_safe')), 'diagnostic boundary differs')
    require(result.get('error') is None and result.get('preservation_error') is None,
            'diagnostic retained an error')
    m.absent(result['owner'], 'root JIB diagnostic owner')
    _, inspected, metadata = d.check_metadata(m)
    layouts = d.load_header_layouts(m, metadata)
    require(type(layouts) is list and len(layouts) == 2 and result.get('root_layouts') == layouts,
            'fixed root layouts differ')
    images = [m.canonical(Path(row['identity']['path'])) for row in inspected['backing_chain']]
    require(len(images) == 2 and images[0] != images[1], 'fixed saved/baseline image pair differs')
    session = m.read_json(m.PREP / 'session.json')
    tool = m.canonical(Path(session['tooling']) / 'tools/qemu-img')
    require(result.get('tool') == {'path': str(tool), **d.TOOL_PIN}, 'recorded tool differs')
    plan = d.read_plan(images, layouts, tool)
    commands = result.get('tool_commands')
    require(type(plan) is list and len(plan) == 16 and type(commands) is list and len(commands) == 16,
            'fixed sixteen-sector command inventory differs')
    retained = []
    for expected, actual in zip(plan, commands):
        require(actual.get('label') == expected['label'] and actual.get('command') == expected['command'] and
                actual.get('exit_code') == 0 and actual.get('reaped') is True and actual.get('forced') is False and
                not actual.get('cleanup_error'), 'actual owned extraction command differs')
        sector = read(Path(expected['output']), 512)
        require(len(sector) == 512, 'retained extraction sector is not exactly 512 bytes')
        retained.append(sector)
    raw = [read(d.OUT / (name + '-jib.bin'), 4096) for name in ('saved', 'baseline')]
    require(all(len(block) == 4096 for block in raw) and
            raw == [b''.join(retained[:8]), b''.join(retained[8:])],
            'retained complete JIB differs from its eight extracted sectors')
    rows = [d.decode_jib(block, layout) for block, layout in zip(raw, layouts)]
    comparison = d.compare_jibs(raw[0], raw[1])
    require(result.get('jibs') == rows and result.get('comparison') == comparison,
            'retained JIB bytes and scalar comparison differ')
    require(type(comparison.get('ranges')) is list and len(comparison['ranges']) <= 128,
            'difference ranges exceed output bound')
    public_rows = [{key: row[key] for key in
                    ('image', 'bytes', 'sha256', 'virtual_offset', 'jib_block', 'flags', 'flags_hex',
                     'journal_offset', 'journal_bytes')} for row in rows]
    public_comparison = {key: comparison[key] for key in
                         ('equal', 'differing_bytes', 'range_count', 'range_limit', 'omitted_ranges', 'ranges_truncated',
                          'offset_convention', 'raw_byte_values_exported', 'difference_classified_as_safe')}
    public_comparison['ranges'] = [{key: row[key] for key in ('start', 'end')}
                                   for row in comparison['ranges']]
    require(read(result_path, d.LIMITS['result_bytes']) == body and read(SOURCE, SOURCE_PIN['bytes']) == source,
            'bound result or source changed during projection')
    m.absent(result['owner'], 'root JIB diagnostic owner after projection')
    digest = hashlib.sha256(body)
    return {'schema': 1, 'status': 'ROOT_JIB_METADATA_PROJECTION', 'readonly': True,
            'observed_utc': m.utc(), 'diagnostic_status': result['status'],
            'result': {'path': str(result_path), 'bytes': len(body), 'sha256': digest.hexdigest(),
                       'digest_bytes': list(digest.digest())},
            'source': {'path': str(SOURCE), **SOURCE_PIN},
            'jibs': public_rows, 'comparison': public_comparison, 'all_own_tool_children_reaped': True,
            'forced_tool_children': [], 'recorded_disk_identities_unchanged': True,
            'recorded_bound_metadata_unchanged': True, 'recorded_bound_tooling_unchanged': True,
            'full_disk_hashes_recomputed': False, 'inspection_success_claimed': False,
            'raw_jib_bytes_exported': False, 'device_signatures_exported': False,
            'uuid_values_exported': False, 'journal_state_evaluated': False,
            'journal_pointer_followed': False, 'difference_classified_as_safe': False,
            'recorded_inspection_processes_absent': True,
            'native_tool_or_guest_started': False}


def main():
    page = globals().get('__page__')
    require(page is None or type(page) is int and 0 <= page < 4, 'invalid bounded difference page')
    result = collect()
    ranges = result['comparison']['ranges']
    summary = {key: value for key, value in result.items() if key not in ('jibs', 'comparison')}
    summary['comparison'] = {key: value for key, value in result['comparison'].items() if key != 'ranges'}
    summary.update(page=page, projected_ranges=0 if page is None else len(ranges[page * 32:(page + 1) * 32]))
    print(json.dumps(summary, separators=(',', ':')), flush=True)
    if page is None:
        for row in result['jibs']:
            print(json.dumps(row, separators=(',', ':')), flush=True)
    else:
        for row in ranges[page * 32:(page + 1) * 32]:
            print(json.dumps(row, separators=(',', ':')), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status': 'ROOT_JIB_PROJECTION_REFUSED', 'readonly': True,
                          'error_type': type(error).__name__}, separators=(',', ':')), flush=True)
        raise SystemExit(2)
