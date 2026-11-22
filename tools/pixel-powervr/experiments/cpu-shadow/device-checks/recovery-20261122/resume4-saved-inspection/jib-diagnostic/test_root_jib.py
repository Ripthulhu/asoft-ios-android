"""Focused synthetic validation; no native tool, phone, VM or disk image runs."""
from pathlib import Path
import ast
import contextlib
import copy
import importlib.util
import io
import json
import struct
import tempfile
import types
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
RECOVERY = HERE.parent.parent


def load():
    spec = importlib.util.spec_from_file_location('tested_root_jib_diagnostic', HERE / 'inspect_root_jib.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def layouts(m):
    return [{'image': name, 'volume_offset': 2048 * 512, 'volume_bytes': m.ROOT_BYTES,
             'block_bytes': 4096, 'jib_block': 257, 'virtual_offset': 2101248, 'bytes': 4096}
            for name in ('saved', 'baseline')]


def jib(m, flags=1):
    body = bytearray(4096)
    body[4:36] = b'PRIVATE-SYNTHETIC-IDENTIFIER-ONLY!'[:32]
    struct.pack_into('>I', body, 0, flags)
    struct.pack_into('>QQ', body, 36, 258 * 4096, 8 << 20)
    for index in range(1, 8):
        body[index * 512] = index
    return bytes(body)


def header(primary=True, jib_block=257):
    body = bytearray(512)
    struct.pack_into('>HHIII', body, 0, 0x4858, 5, 0x80002100 if primary else 0x80002800, 0x4846534a, jib_block)
    struct.pack_into('>III', body, 40, 4096, 8388608, 1000)
    struct.pack_into('>I', body, 68, 2)
    body[104:112] = b'TESTONLY'
    return bytes(body)


class BindingTests(unittest.TestCase):
    def test_all_nine_pins_match_the_actual_288_decimal_bytes(self):
        m = load()
        actual = json.loads((HERE.parent / 'physical-observations/receipt-pins-selected.json').read_bytes())
        self.assertIs(actual['independently_reviewed'], True)
        self.assertIs(actual['independent_pixel_review_pending'], False)
        expected = {}
        for row in actual['rows']:
            self.assertEqual(len(row['digest_bytes']), 32)
            derived = bytes(row['digest_bytes']).hex()
            self.assertEqual(derived, row['sha256'])
            expected[row['path']] = {'bytes': row['bytes'], 'sha256': derived}
        self.assertEqual(len(expected), 9)
        self.assertEqual(expected, m.RECEIPT_PINS)

    def test_eight_reviewed_helpers_are_ast_identical(self):
        previous = RECOVERY / 'resume2-saved-inspection/header-diagnostic/inspect_hfs_headers.py'
        extract = lambda path: {node.name: ast.dump(node, include_attributes=False)
                                for node in ast.parse(path.read_bytes()).body if isinstance(node, ast.FunctionDef)}
        old, new = extract(previous), extract(HERE / 'inspect_root_jib.py')
        for name in ('require', 'sha', 'small_read', 'save', 'save_json', 'module', 'decode_header', 'run_tool'):
            self.assertEqual(new[name], old[name], name)

    def test_bound_read_rejects_changed_file_and_conflicting_binding(self):
        m = load()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder).resolve() / 'metadata.json'
            body = b'{"fixed":true}\n'
            path.write_bytes(body)
            pin = {'bytes': len(body), 'sha256': m.sha(body)}
            metadata = {}
            self.assertEqual(m.bound_read(path, pin, metadata), body)
            self.assertEqual(metadata, {str(path): m.sha(body)})
            with self.assertRaisesRegex(ValueError, 'bindings disagree'):
                m.bound_read(path, pin, {str(path): '0' * 64})
            path.write_bytes(body.replace(b'true', b'null'))
            with self.assertRaisesRegex(ValueError, 'fixed input changed'):
                m.bound_read(path, pin, {})


class HeaderScopeTests(unittest.TestCase):
    def setUp(self):
        self.m = load()
        m = self.m
        self.images = [Path('/fixed/prep/saved.qcow2'), Path('/fixed/prep/baseline.qcow2')]
        self.chain = [{'identity': {'path': str(path)}, 'record': {'path': path.name, 'sha256': str(index) * 64}}
                      for index, path in enumerate(self.images)]
        self.session = json.dumps({'backing_chain': self.chain}).encode()
        self.metadata = {str(m.WORK / 'inspection-session.json'): m.sha(self.session)}
        self.result = {'status': 'READONLY_HFS_HEADERS_OBSERVED',
                       'source': {'path': str(m.HEADER_SOURCE), **m.HEADER_SOURCE_PIN},
                       'previous_full_hash_records': [row['record'] for row in self.chain],
                       'headers': [{} for _ in range(8)], 'tool_commands': [{} for _ in range(8)],
                       'tool': {'path': '/fixed/tools/qemu-img'}}
        self.bodies = {}
        for index, image, primary in ((0, 'saved', True), (1, 'saved', False), (4, 'baseline', True), (5, 'baseline', False)):
            self.set_header(index, image, primary, header(primary))

    def set_header(self, index, image, primary, body):
        m = self.m
        relative = 1024 if primary else m.ROOT_BYTES - 1024
        offset = 2048 * 512 + relative
        path = m.HEADER_OUT / ('h' + str(index) + '.bin')
        self.bodies[path] = body
        self.result['headers'][index] = m.decode_header(body, image, 'iOSRoot', 'primary' if primary else 'alternate', offset, m.ROOT_SECTORS)
        self.result['tool_commands'][index] = {'command': [self.result['tool']['path'], 'dd', '-f', 'qcow2', '-O', 'raw', 'bs=512',
            'count=' + str(offset // 512 + 1), 'skip=' + str(offset // 512),
            'if=' + str(self.images[0 if image == 'saved' else 1]), 'of=' + str(path)],
            'reaped': True, 'forced': False, 'exit_code': 0}

    def derive(self):
        m = self.m
        def read_bound(path, pin, metadata):
            if path == m.HEADER_SOURCE:
                return b'# synthetic historical source\n'
            if path == m.HEADER_OUT / 'result.json':
                return json.dumps(self.result).encode()
            return self.bodies[path]
        with mock.patch.object(m, 'bound_read', side_effect=read_bound), mock.patch.object(m, 'small_read', return_value=self.session):
            return m.load_header_layouts(types.SimpleNamespace(), self.metadata)

    def test_both_offsets_are_derived_from_all_four_bound_headers(self):
        self.assertEqual(self.derive(), layouts(self.m))

    def test_each_changed_root_header_is_rejected(self):
        for index, image, primary in ((0, 'saved', True), (1, 'saved', False), (4, 'baseline', True), (5, 'baseline', False)):
            with self.subTest(index=index):
                self.set_header(index, image, primary, header(primary, 258))
                with self.assertRaises(ValueError):
                    self.derive()
                self.set_header(index, image, primary, header(primary))

    def test_scalar_row_cannot_override_the_retained_header(self):
        self.result['headers'][0]['journal_info_block'] = 258
        with self.assertRaisesRegex(ValueError, 'retained root header differs'):
            self.derive()

    def test_short_retained_header_refuses(self):
        self.bodies[self.m.HEADER_OUT / 'h5.bin'] = header(False)[:-1]
        with self.assertRaisesRegex(ValueError, 'exact 512-byte'):
            self.derive()

    def test_header_evidence_must_belong_to_current_image_records(self):
        self.result['previous_full_hash_records'] = [{'path': 'wrong.qcow2'}]
        with self.assertRaisesRegex(ValueError, 'image records differ'):
            self.derive()

    def test_header_command_must_name_current_image_and_exact_range(self):
        self.result['tool_commands'][4]['command'][-2] = 'if=/fixed/unrelated.qcow2'
        with self.assertRaisesRegex(ValueError, 'different image or range'):
            self.derive()

    def test_current_inspection_session_cannot_change_between_checks(self):
        self.session = self.session.replace(b'saved.qcow2', b'other.qcow2')
        with self.assertRaisesRegex(ValueError, 'session changed'):
            self.derive()


class RangeAndDecodeTests(unittest.TestCase):
    def test_root_arithmetic_and_types_refuse_other_ranges(self):
        m = load()
        self.assertEqual(m.root_offset(4096, 257), 2101248)
        for block, index in ((True, 257), (512, 257), (4096, True), (4096, 0), (4096, -1),
                             (4096, m.ROOT_BYTES // 4096 - 1), (4096, 258)):
            with self.subTest(block=block, index=index), self.assertRaises(ValueError):
                m.root_offset(block, index)

    def test_plan_contains_only_sixteen_proven_512_byte_reads(self):
        m = load()
        images = [Path('/fixed/saved.qcow2'), Path('/fixed/baseline.qcow2')]
        plan = m.read_plan(images, layouts(m), Path('/fixed/qemu-img'), Path('/fresh/output'))
        self.assertEqual([row['label'] for row in plan], ['s' + str(i) for i in range(8)] + ['b' + str(i) for i in range(8)])
        self.assertEqual(len({row['output'] for row in plan}), 16)
        for index, row in enumerate(plan):
            skip = 4104 + index % 8
            self.assertEqual(row['virtual_offset'], skip * 512)
            self.assertEqual(row['command'], ['/fixed/qemu-img', 'dd', '-f', 'qcow2', '-O', 'raw', 'bs=512',
                'count=' + str(skip + 1), 'skip=' + str(skip), 'if=' + str(images[index // 8]), 'of=' + row['output']])

    def test_plan_rejects_changed_layout_and_duplicate_images(self):
        m = load()
        changed = layouts(m)
        changed[0]['virtual_offset'] += 512
        with self.assertRaises(ValueError):
            m.read_plan([Path('/saved'), Path('/baseline')], changed, Path('/tool'))
        with self.assertRaisesRegex(ValueError, 'distinct'):
            m.read_plan([Path('/same'), Path('/same')], layouts(m), Path('/tool'))

    def test_decode_exports_only_exact_scalar_allowlist(self):
        m = load()
        for flags in (1, 5):
            body = jib(m, flags)
            decoded = m.decode_jib(body, layouts(m)[0])
            self.assertEqual(decoded, {'image': 'saved', 'virtual_offset': 2101248, 'jib_block': 257,
                'bytes': 4096, 'sha256': m.sha(body), 'flags': flags, 'flags_hex': '0x%08x' % flags,
                'journal_offset': 258 * 4096, 'journal_bytes': 8 << 20})
            self.assertNotIn('PRIVATE', json.dumps(decoded))
            self.assertNotIn('TESTONLY', json.dumps(decoded))

    def test_decoder_refuses_partial_or_expanded_payload_and_invalid_fields(self):
        m = load()
        for body in (jib(m)[:-1], jib(m) + b'x'):
            with self.assertRaisesRegex(ValueError, 'exact 4096-byte'):
                m.decode_jib(body, layouts(m)[0])
        for flag, offset, size in ((0, 258 * 4096, 8 << 20), (1, 17, 8 << 20),
                                   (1, m.ROOT_BYTES - 4096, 8 << 20), (1, 258 * 4096, 4096)):
            body = bytearray(jib(m)); struct.pack_into('>I', body, 0, flag); struct.pack_into('>QQ', body, 36, offset, size)
            with self.subTest(flag=flag, offset=offset, size=size), self.assertRaises(ValueError):
                m.decode_jib(bytes(body), layouts(m)[0])

    def test_reconstruction_requires_eight_exact_sectors_in_selected_order(self):
        m = load()
        sectors = [bytes([index]) * 512 for index in range(8)]
        self.assertEqual(m.assemble_jib(sectors), b''.join(sectors))
        for invalid in (sectors[:-1], sectors + [bytes(512)], sectors[:-1] + [bytes(511)], sectors[:-1] + [bytes(513)]):
            with self.assertRaisesRegex(ValueError, 'eight ordered'):
                m.assemble_jib(invalid)


class DifferenceTests(unittest.TestCase):
    def setUp(self):
        self.m = load()

    def compare(self, offsets):
        saved = bytearray(4096)
        for index in offsets:
            saved[index] = 1
        return self.m.compare_jibs(bytes(saved), bytes(4096))

    def test_identical_blocks_have_no_difference_or_safety_claim(self):
        row = self.compare([])
        self.assertIs(row['equal'], True)
        self.assertEqual((row['differing_bytes'], row['range_count'], row['ranges'], row['omitted_ranges']), (0, 0, [], 0))
        self.assertIs(row['difference_classified_as_safe'], False)

    def test_boundary_and_adjacent_changes_form_exact_half_open_ranges(self):
        row = self.compare([0, 1, 2, 511, 4095])
        self.assertEqual(row['ranges'], [{'start': 0, 'end': 3}, {'start': 511, 'end': 512}, {'start': 4095, 'end': 4096}])
        self.assertEqual((row['differing_bytes'], row['range_count']), (5, 3))
        self.assertIs(row['ranges_truncated'], False)
        self.assertTrue(all(set(item) == {'start', 'end'} for item in row['ranges']))

    def test_all_bytes_changed_remains_one_bounded_range(self):
        row = self.compare(range(4096))
        self.assertEqual(row['ranges'], [{'start': 0, 'end': 4096}])
        self.assertEqual(row['differing_bytes'], 4096)

    def test_alternating_changes_count_every_byte_and_report_omitted_ranges(self):
        row = self.compare(range(0, 4096, 2))
        self.assertEqual(row['differing_bytes'], 2048)
        self.assertEqual(row['range_count'], 2048)
        self.assertEqual(len(row['ranges']), 128)
        self.assertEqual(row['omitted_ranges'], 1920)
        self.assertIs(row['ranges_truncated'], True)
        self.assertEqual(row['ranges'][-1], {'start': 254, 'end': 255})

    def test_invalid_size_or_range_limit_refuses(self):
        for left, right, limit in ((bytes(4095), bytes(4096), 128), (bytes(4096), bytes(4097), 128),
                                   (bytes(4096), bytes(4096), 0), (bytes(4096), bytes(4096), 129),
                                   (bytes(4096), bytes(4096), True)):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.m.compare_jibs(left, right, limit)


class ExtractionTests(unittest.TestCase):
    def run_extraction(self, *, short=None, dirty=None, reverse=False):
        m = load()
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder).resolve()
            images = [Path('/fixed/saved'), Path('/fixed/baseline')]
            layout = layouts(m)
            plan = m.read_plan(images, layout, Path('/fixed/qemu-img'), out)
            if reverse:
                plan[0], plan[1] = plan[1], plan[0]
            payloads = [jib(m, 1), jib(m, 5)]
            calls, rows = [], []
            resources = mock.Mock()
            def fake_run(label, command, env, collected):
                index = len(calls)
                calls.append((label, command))
                self.assertEqual(command, plan[index]['command'])
                image_index, sector = index // 8, index % 8
                body = payloads[image_index][sector * 512:(sector + 1) * 512]
                if short is not None and index == 0:
                    body = body[:short] if short < 512 else body + bytes(short - 512)
                Path(plan[index]['output']).write_bytes(body)
                row = {'pid': 1000 + index, 'command': command, 'exit_code': 0, 'reaped': True, 'forced': False}
                if dirty is not None and index == 15:
                    row.update(dirty)
                collected.append(row)
            with mock.patch.object(m, 'OUT', out), mock.patch.object(m, 'run_tool', side_effect=fake_run):
                if short is not None or dirty is not None or reverse:
                    with self.assertRaises(ValueError):
                        m.extract_jibs(types.SimpleNamespace(resources=resources), plan, layout, {}, rows)
                    self.assertEqual(len(calls), 0 if reverse else 1 if short is not None else 16)
                else:
                    actual, decoded = m.extract_jibs(types.SimpleNamespace(resources=resources), plan, layout, {}, rows)
                    self.assertEqual(actual, payloads)
                    self.assertEqual([row['flags'] for row in decoded], [1, 5])
                    self.assertEqual(resources.call_count, 16)
                    self.assertEqual((out / 'saved-jib.bin').read_bytes(), payloads[0])
                    self.assertEqual((out / 'baseline-jib.bin').read_bytes(), payloads[1])

    def test_extraction_preserves_all_sixteen_sector_positions(self):
        self.run_extraction()

    def test_extraction_refuses_short_and_oversized_sectors(self):
        for size in (0, 511, 513):
            with self.subTest(size=size):
                self.run_extraction(short=size)

    def test_extraction_rejects_reordered_plan_before_any_child(self):
        self.run_extraction(reverse=True)

    def test_extraction_requires_every_owned_child_clean_and_reaped(self):
        for dirty in ({'reaped': False}, {'forced': True}, {'exit_code': 2}, {'cleanup_error': 'synthetic'}):
            with self.subTest(dirty=dirty):
                self.run_extraction(dirty=dirty)


class PreservationTests(unittest.TestCase):
    def test_metadata_refusal_precedes_output_and_child_and_releases_locks(self):
        m = load()
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder).resolve(); prep = base / 'prep'; work = base / 'work'
            prep.mkdir(); work.mkdir()
            locks = [prep / 'owner.lock', work / 'owner.lock']
            for path in locks:
                path.write_bytes(b'')
            out = base / 'new-diagnostic'
            owner = types.SimpleNamespace(PREP=prep, WORK=work, canonical=lambda path: path.resolve(strict=True))
            with mock.patch.object(m, 'OUT', out), mock.patch.object(m, 'load_bound_owner', return_value=owner), \
                    mock.patch.object(m, 'check_metadata', side_effect=ValueError('unbound current evidence')), \
                    mock.patch.object(m, 'run_tool') as native, contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(m.main(), 2)
                native.assert_not_called()
            self.assertFalse(out.exists())
            self.assertEqual(json.loads(output.getvalue())['status'], 'ROOT_JIB_DIAGNOSTIC_REFUSED')
            for path in locks:
                with path.open('rb') as stream:
                    m.fcntl.flock(stream.fileno(), m.fcntl.LOCK_EX | m.fcntl.LOCK_NB)

    def test_preservation_detects_metadata_identity_and_tool_changes(self):
        m = load()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder).resolve() / 'receipt.json'; path.write_bytes(b'original')
            metadata = {str(path): m.sha(b'original')}
            images = [Path('/saved'), Path('/baseline')]
            before = [{'path': str(path), 'marker': 1} for path in images]
            verify = mock.Mock()
            cold = types.SimpleNamespace(readonly_identity=lambda path: before[images.index(path)])
            prep = types.SimpleNamespace(cold=cold, verify_tools=verify)
            m.verify_preservation(prep, Path('/tools'), images, before, metadata)
            verify.assert_called_once_with(Path('/tools'), m.TOOL_MANIFEST_SHA)
            path.write_bytes(b'changed!')
            with self.assertRaisesRegex(ValueError, 'metadata/source changed'):
                m.verify_preservation(prep, Path('/tools'), images, before, metadata)
            path.write_bytes(b'original')
            cold.readonly_identity = lambda path: {'path': str(path), 'marker': 2}
            with self.assertRaisesRegex(ValueError, 'disk identity changed'):
                m.verify_preservation(prep, Path('/tools'), images, before, metadata)
            cold.readonly_identity = lambda path: before[images.index(path)]
            verify.side_effect = ValueError('tool changed')
            with self.assertRaisesRegex(ValueError, 'tool changed'):
                m.verify_preservation(prep, Path('/tools'), images, before, metadata)

    def test_final_preservation_failure_cannot_leave_a_completed_result(self):
        m = load()
        with tempfile.TemporaryDirectory() as folder, contextlib.ExitStack() as stack:
            base = Path(folder).resolve(); prep_dir = base / 'prep'; work = base / 'work'
            prep_dir.mkdir(); work.mkdir()
            for path in (prep_dir / 'owner.lock', work / 'owner.lock'):
                path.write_bytes(b'')
            source = base / 'source.py'; source.write_text('# synthetic source\n')
            out = base / 'new-diagnostic'
            owner = types.SimpleNamespace(PREP=prep_dir, WORK=work, canonical=lambda path: path.resolve(strict=True),
                resources=mock.Mock(), refuse_live_children=mock.Mock(), utc=lambda: 'synthetic-utc',
                identity=lambda pid: {'pid': pid, 'starttime': 1}, absent=mock.Mock())
            inspected = {'backing_chain': [{'record': {'path': 'saved'}}, {'record': {'path': 'baseline'}}]}
            layout = layouts(m); payloads = [jib(m, 1), jib(m, 5)]
            replacements = {'OUT': out, 'DIAGNOSTIC_SOURCE': source,
                'load_bound_owner': mock.Mock(return_value=owner),
                'check_metadata': mock.Mock(return_value=({}, inspected, {})),
                'load_header_layouts': mock.Mock(return_value=layout),
                'prepare_images': mock.Mock(return_value=(object(), base / 'tools', base / 'qemu-img',
                                                         [base / 'saved', base / 'baseline'], [])),
                'extract_jibs': mock.Mock(return_value=(payloads, [m.decode_jib(body, row) for body, row in zip(payloads, layout)])),
                'verify_preservation': mock.Mock(side_effect=ValueError('synthetic bound metadata changed'))}
            for key, value in replacements.items():
                stack.enter_context(mock.patch.object(m, key, value))
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = m.main()
            result = json.loads((out / 'result.json').read_bytes())
            self.assertEqual(code, 2)
            self.assertEqual(result['status'], 'INCOMPLETE')
            self.assertIn('synthetic bound metadata changed', result['preservation_error'])
            self.assertNotIn('disk_identities_unchanged', result)
            self.assertIs(result['inspection_success_claimed'], False)
            self.assertIs(result['difference_classified_as_safe'], False)


if __name__ == '__main__':
    unittest.main(verbosity=2)
