def resume4_failure_inputs():
    """Preserve the exact failed inspection, completed observer and JIB diagnosis.

    Reuse the pinned diagnostic's metadata and pure retained-payload validators.
    This function never calls its main/extraction routines or starts a tool/VM.
    """
    require(not WORK.is_relative_to(RESUME4_WORK) and not RESUME4_WORK.is_relative_to(WORK) and
            not OWNER.is_relative_to(RESUME4_OWNER) and not RESUME4_OWNER.is_relative_to(OWNER),
            'new inspection overlaps preserved resume4 work')
    expected = {str(RESUME4_OWNER / 'exit.json'), str(RESUME4_WORK / 'result.json'),
                str(RESUME4_WORK / 'a1/vm-result.json'), str(RESUME4_WORK / 'a1/expected-policy.json'),
                str(RESUME4_WORK / 'a1/files/inspection/result.json'),
                *(str(RESUME4_MONITOR / name) for name in ('ready.json', 'exit.json', 'summary.json', 'events.jsonl')),
                str(JIB_SOURCE), str(JIB_WORK / 'result.json')}
    require(set(RESUME4_PRESERVATION_PINS) == expected, 'exact resume4/JIB preservation paths required')
    inputs, cached = {}, {}
    for name, pin in RESUME4_PRESERVATION_PINS.items():
        require(type(pin) is dict and set(pin) == {'bytes', 'sha256'} and
                type(pin['bytes']) is int and 0 < pin['bytes'] <= 4 << 20 and
                type(pin['sha256']) is str and re.fullmatch('[0-9a-f]{64}', pin['sha256']),
                'malformed resume4/JIB preservation pin')
        body = read_bytes(Path(name), pin['bytes'])
        require({'bytes': len(body), 'sha256': sha(body)} == pin, 'preserved resume4/JIB evidence changed: ' + name)
        inputs[name], cached[name] = sha(body), body

    d = types.ModuleType('preserved_root_jib_metadata_validator')
    d.__file__ = str(JIB_SOURCE)
    exec(compile(cached[str(JIB_SOURCE)], str(JIB_SOURCE), 'exec'), d.__dict__)
    old = d.load_bound_owner()
    require(old.OWNER == RESUME4_OWNER and old.WORK == RESUME4_WORK and
            old.INSPECTOR == Path('/data/local/tmp/pixel-saved-checks-resume3') and
            d.OUT == JIB_WORK and d.DIAGNOSTIC_SOURCE == JIB_SOURCE and d.MONITOR == RESUME4_MONITOR and
            d.RECEIPT_PINS == {name: pin for name, pin in RESUME4_PRESERVATION_PINS.items()
                               if name not in (str(JIB_SOURCE), str(JIB_WORK / 'result.json'))},
            'preserved JIB validator scope differs')
    lock = os.open(canonical(RESUME4_WORK / 'owner.lock'), os.O_RDONLY | os.O_NOFOLLOW)
    try:
        require(stat.S_ISREG(os.fstat(lock).st_mode), 'preserved resume4 lock is not ordinary')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _, inspected, bound = d.check_metadata(old)
        layouts = d.load_header_layouts(old, bound)
        for name, expected_sha in bound.items():
            require(name not in inputs or inputs[name] == expected_sha, 'preserved metadata validators disagree')
            inputs[name] = expected_sha
        result = json.loads(cached[str(JIB_WORK / 'result.json')])
        require(result.get('schema') == 1 and result.get('kind') == 'readonly_root_jib_diagnostic' and
                result.get('status') == 'READONLY_ROOT_JIB_COMPARISON_OBSERVED' and
                result.get('source') == {'path': str(JIB_SOURCE), **RESUME4_PRESERVATION_PINS[str(JIB_SOURCE)]} and
                result.get('root_layouts') == layouts and result.get('limits') == d.LIMITS and
                result.get('actual_failed_inspection_pins') == 9 and
                result.get('previous_full_hash_records') == [row['record'] for row in inspected['backing_chain']],
                'completed JIB diagnostic scope differs')
        require(all(result.get(key) is True for key in
                    ('diagnostic_only', 'disk_identities_unchanged', 'bound_metadata_unchanged',
                     'bound_tooling_unchanged', 'recorded_inspection_processes_absent')) and
                all(result.get(key) is False for key in
                    ('inspection_success_claimed', 'difference_classified_as_safe', 'guest_vm_started', 'fsck_run',
                     'mounted', 'replayed', 'repaired', 'journal_pointer_followed', 'raw_bytes_exported',
                     'full_disk_hashes_recomputed')) and
                result.get('error') is None and result.get('preservation_error') is None,
                'completed JIB diagnostic preservation or scope differs')
        absent(result['owner'], 'completed root JIB diagnostic')
        images = [canonical(Path(row['identity']['path'])) for row in inspected['backing_chain']]
        require(len(images) == 2 and images[0] != images[1] and all(path.is_relative_to(PREP) for path in images),
                'preserved JIB image pair differs')
        session = read_json(PREP / 'session.json')
        tool = canonical(Path(session['tooling']) / 'tools/qemu-img')
        require(result.get('tool') == {'path': str(tool), **d.TOOL_PIN} and
                result.get('capability') == {'path': str(d.CAPABILITY_RESULT), **d.CAPABILITY_PIN, 'passed': True},
                'completed JIB tooling or capability differs')
        plan = d.read_plan(images, layouts, tool)
        rows = result.get('tool_commands')
        require(type(rows) is list and len(rows) == len(plan) == 16, 'fixed JIB extraction inventory differs')
        sectors = []
        for expected_row, row in zip(plan, rows):
            require(row.get('label') == expected_row['label'] and row.get('command') == expected_row['command'] and
                    row.get('exit_code') == 0 and row.get('reaped') is True and row.get('forced') is False and
                    not row.get('cleanup_error'), 'preserved JIB extraction was not clean')
            path = Path(expected_row['output'])
            body = read_bytes(path, 512)
            require(len(body) == 512, 'retained JIB sector has changed size')
            sectors.append(body)
            inputs[str(path)] = sha(body)
            for suffix in ('command.json', 'exit.json', 'stdout'):
                retained = JIB_WORK / (row['label'] + '.' + suffix)
                retained_body = read_bytes(retained, d.LIMITS['tool_output_bytes'])
                inputs[str(retained)] = sha(retained_body)
                if suffix == 'exit.json':
                    require(json.loads(retained_body) == row, 'retained JIB child exit differs')
                elif suffix == 'stdout':
                    require(len(retained_body) == row.get('output_bytes') and sha(retained_body) == row.get('output_sha256'),
                            'retained JIB child output differs')
                else:
                    require(json.loads(retained_body) == {'label': row['label'], 'command': row['command'],
                            'pid': None, 'exit_code': None, 'reaped': False, 'forced': False},
                            'retained JIB child command differs')
        blocks = []
        for name, selected_sectors in (('saved', sectors[:8]), ('baseline', sectors[8:])):
            path = JIB_WORK / (name + '-jib.bin')
            body = read_bytes(path, 4096)
            require(body == d.assemble_jib(selected_sectors), 'retained complete JIB differs from its sectors')
            blocks.append(body)
            inputs[str(path)] = sha(body)
        projected = [d.decode_jib(body, layout) for body, layout in zip(blocks, layouts)]
        comparison = d.compare_jibs(blocks[0], blocks[1], d.LIMITS['difference_ranges'])
        require(result.get('jibs') == projected and result.get('comparison') == comparison and
                [row['flags'] for row in projected] == [1, 5] and comparison['equal'] is False and
                comparison['differing_bytes'] == comparison['range_count'] == 1 and
                comparison['ranges'] == [{'start': 3, 'end': 4}] and comparison['omitted_ranges'] == 0 and
                comparison['ranges_truncated'] is False,
                'retained JIB comparison differs from the actual observed transition')
        # The diagnostic observed a flag difference. The new immutable guest
        # must independently prove the authored baseline and initialized-empty
        # journal and pass both read-only fscks; this metadata check grants none
        # of those conclusions.
        path = JIB_WORK / 'session.json'
        inputs[str(path)] = sha(read_bytes(path))
        absent(result['owner'], 'completed root JIB diagnostic after preservation')
        return inputs
    finally:
        os.close(lock)

