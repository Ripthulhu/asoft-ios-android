"""Focused host bounds/ownership tests; no real native tools, phone or VM."""
from pathlib import Path
import ast
import contextlib
import copy
import importlib.util
import io
import json
import os
import struct
import tempfile
import types
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
R5 = HERE.parent.parent
REC = R5.parent
CPU = REC.parent.parent


def load(path=None):
    path = path or (HERE / 'inspect_data_journal.py' if (HERE / 'inspect_data_journal.py').exists()
                    else HERE / 'inspect_data_journal_UNRELEASED.py')
    spec = importlib.util.spec_from_file_location('tested_' + path.stem, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def headers():
    result = []
    for attributes in (0x80002000, 0x80002100):
        body = bytearray(512)
        struct.pack_into('>HHIII', body, 0, 0x4858, 5, attributes, 0x4846534a, 129)
        struct.pack_into('>III', body, 40, 4096, 4194304, 1000)
        body[104:112] = b'TESTONLY'
        result.append(bytes(body))
    return result


def layout(m):
    h = headers()
    return {'volume': 'Data', 'volume_offset': m.DATA_BASE, 'volume_bytes': m.DATA_BYTES,
            'block_bytes': 4096, 'jib_block': 129, 'jib_relative_offset': 528384,
            'jib_bytes': 4096, 'journal_relative_offset': 532480, 'journal_bytes': 8388608,
            'primary_header_sha256': m.sha(h[0]), 'alternate_header_sha256': m.sha(h[1])}


def jib():
    body = bytearray(4096)
    struct.pack_into('>I', body, 0, 1)
    body[4:36] = b'PRIVATE-DEVICE-SIGNATURE-TEST-ONLY!'[:32]
    struct.pack_into('>QQ', body, 36, 532480, 8388608)
    return bytes(body)


def journal():
    body = bytearray(8388608)
    struct.pack_into('<IIQQQIII', body, 0, 0x4a4e4c78, 0x12345678, 512, 614400,
                     8388608, 49152, 195764962, 512)
    return bytes(body)


class BindingTests(unittest.TestCase):
    def test_nine_actual_pins_match_all288_reviewed_decimal_bytes(self):
        m = load()
        evidence = json.loads((R5 / 'physical-observations/receipt-pins-selected.json').read_bytes())
        self.assertIs(evidence['independently_reviewed'], True)
        self.assertIs(evidence['independent_pixel_review_pending'], False)
        expected = {}
        for row in evidence['rows']:
            self.assertEqual(len(row['digest_bytes']), 32)
            self.assertEqual(bytes(row['digest_bytes']).hex(), row['sha256'])
            expected[row['path']] = {'bytes': row['bytes'], 'sha256': row['sha256']}
        self.assertEqual(len(expected), 9)
        self.assertEqual(m.RECEIPT_PINS, expected)

    def test_actual_failure_metadata_and_processes_match_reviewed_projection(self):
        m = load()
        evidence = json.loads((R5 / 'physical-observations/guest-boundary-selected.json').read_bytes())
        self.assertIs(evidence['independent_review_pending'], False)
        self.assertEqual(m.expected_data_metadata(), evidence['guest']['journals']['Data']['metadata'])
        self.assertEqual(m.EXPECTED_WRAPPER, evidence['identities']['wrapper'])
        self.assertEqual(m.EXPECTED_INSPECTOR, evidence['identities']['inspector'])
        self.assertEqual(m.EXPECTED_QEMU, evidence['identities']['qemu'])
        self.assertEqual(m.EXPECTED_ERROR, evidence['host_error'])

    def test_nine_pure_or_io_helpers_unchanged_from_reviewed_jib_source(self):
        old = REC / 'resume4-saved-inspection/jib-diagnostic/inspect_root_jib.py'
        extract = lambda p: {n.name: ast.dump(n, include_attributes=False)
                             for n in ast.parse(p.read_bytes()).body if isinstance(n, ast.FunctionDef)}
        a, b = extract(old), extract(HERE / 'inspect_data_journal_UNRELEASED.py')
        for name in ('require', 'sha', 'small_read', 'save', 'save_json', 'module', 'decode_header', 'bound_read', 'verify_capability'):
            self.assertEqual(a[name], b[name], name)

    def test_unbound_parser_refuses_before_file_or_process_actions(self):
        m = load()
        with mock.patch.object(m, 'PARSER_SOURCE_PIN', None), mock.patch.object(m, 'bound_read') as read, \
             mock.patch.object(m.subprocess, 'Popen') as spawn, mock.patch.object(m.Path, 'mkdir') as mkdir:
            with self.assertRaisesRegex(ValueError, 'UNRELEASED'):
                m.main()
            read.assert_not_called(); spawn.assert_not_called(); mkdir.assert_not_called()

    def test_changed_receipt_or_source_and_conflicting_bindings_refuse(self):
        m = load()
        with tempfile.TemporaryDirectory() as root:
            p = Path(root).resolve() / 'record.json'; p.write_bytes(b'{"pinned":true}\n')
            pin = {'bytes': p.stat().st_size, 'sha256': m.sha(p.read_bytes())}
            self.assertEqual(m.bound_read(p, pin, {}), p.read_bytes())
            with self.assertRaisesRegex(ValueError, 'bindings disagree'):
                m.bound_read(p, pin, {str(p): '0' * 64})
            p.write_bytes(b'{"pinned":null}\n')
            with self.assertRaisesRegex(ValueError, 'fixed input changed'):
                m.bound_read(p, pin, {})

    def test_absence_gate_keeps_all_four_exact_identity_keys(self):
        m = load(); calls = []
        m.require_absent(types.SimpleNamespace(absent=lambda *a: calls.append(a)))
        self.assertEqual([(r[0], r[2]) for r in calls], [(m.EXPECTED_WRAPPER, 'starttime'),
            (m.EXPECTED_INSPECTOR, 'starttime'), (m.EXPECTED_QEMU, 'start_ticks'), (m.EXPECTED_OBSERVER, 'start_ticks')])

    def test_missing_or_changed_nonempty_boundary_refuses(self):
        m = load()
        actual = json.loads((R5 / 'physical-observations/guest-boundary-selected.json').read_bytes())['guest']['journals']
        m.validate_failed_journals(actual)
        for key, value in (('start', 614400), ('checksum', 0), ('header_sha256', '0' * 64), ('block_header_bytes', 4096)):
            changed = copy.deepcopy(actual); changed['Data']['metadata'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): m.validate_failed_journals(changed)
        changed = copy.deepcopy(actual); del changed['Data']['metadata']['header_sha256']
        with self.assertRaises(ValueError): m.validate_failed_journals(changed)
        changed = copy.deepcopy(actual); changed['iOSRoot']['status'] = 'INCOMPLETE'
        with self.assertRaises(ValueError): m.validate_failed_journals(changed)


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.m = m = load(); self.images = [Path('/fixed/prep/saved.qcow2'), Path('/fixed/prep/baseline.qcow2')]
        self.chain = [{'identity': {'path': str(p)}, 'record': {'path': p.name, 'sha256': str(i)*64}}
                      for i,p in enumerate(self.images)]
        self.session = json.dumps({'backing_chain': self.chain}).encode()
        self.metadata = {str(m.WORK / 'inspection-session.json'): m.sha(self.session)}
        self.result = {'status': 'READONLY_HFS_HEADERS_OBSERVED',
            'source': {'path': str(m.HEADER_SOURCE), **m.HEADER_SOURCE_PIN},
            'previous_full_hash_records': [r['record'] for r in self.chain],
            'headers': [{} for _ in range(8)], 'tool_commands': [{} for _ in range(8)],
            'tool': {'path': '/fixed/tool/qemu-img'}}
        self.bodies = {}
        for index, body in enumerate(headers(), 2): self.set_header(index, body)

    def set_header(self, index, body):
        m = self.m; copy_name = 'primary' if index == 2 else 'alternate'
        offset = m.DATA_BASE + (1024 if index == 2 else m.DATA_BYTES - 1024)
        path = m.HEADER_OUT / ('h' + str(index) + '.bin'); self.bodies[path] = body
        self.result['headers'][index] = m.decode_header(body, 'saved', 'Data', copy_name, offset, m.DATA_SECTORS)
        self.result['tool_commands'][index] = {'command': [self.result['tool']['path'], 'dd', '-f', 'qcow2', '-O', 'raw',
            'bs=512', 'count=' + str(offset//512 + 1), 'skip=' + str(offset//512),
            'if=' + str(self.images[0]), 'of=' + str(path)], 'reaped': True, 'forced': False, 'exit_code': 0}

    def derive(self):
        m = self.m
        def bound(p, pin, metadata):
            if p == m.HEADER_SOURCE: return b'# synthetic pinned source\n'
            if p == m.HEADER_OUT / 'result.json': return json.dumps(self.result).encode()
            return self.bodies[p]
        with mock.patch.object(m, 'bound_read', side_effect=bound), mock.patch.object(m, 'small_read', return_value=self.session):
            return m.load_data_layout(types.SimpleNamespace(), self.metadata)

    def test_exact_saved_data_headers_derive_fixed_layout(self):
        self.assertEqual(self.derive(), (layout(self.m), headers()))

    def test_header_scalars_and_retained_bytes_cannot_diverge(self):
        self.result['headers'][2]['journal_info_block'] = 130
        with self.assertRaises(ValueError): self.derive()

    def test_header_from_other_chain_or_read_range_refuses(self):
        original = copy.deepcopy(self.result)
        self.result['previous_full_hash_records'] = []
        with self.assertRaises(ValueError): self.derive()
        self.result = original; self.result['tool_commands'][2]['command'][-2] = 'if=/unrelated.qcow2'
        with self.assertRaises(ValueError): self.derive()

    def test_either_header_changed_geometry_legacy_or_runtime_flag_refuses(self):
        for index in (2,3):
            saved = self.bodies[self.m.HEADER_OUT / ('h' + str(index) + '.bin')]
            for field, value in ((12,130),(4,0x80002800),(4,0x80006000),(40,512)):
                bad = bytearray(saved); struct.pack_into('>I',bad,field,value); self.set_header(index,bytes(bad))
                with self.subTest(index=index,field=field,value=value), self.assertRaises(ValueError): self.derive()
                self.set_header(index,saved)

    def test_current_session_change_between_binding_and_scope_refuses(self):
        self.session += b' '
        with self.assertRaises(ValueError): self.derive()


class ExtractionTests(unittest.TestCase):
    def test_four_ranges_use_proven_input_limit_before_skip_semantics(self):
        m = load(); images = [Path('/saved'),Path('/baseline')]
        rows = m.read_plan(images,layout(m),Path('/tool'),Path('/fresh'))
        self.assertEqual([r['label'] for r in rows],['primary','alternate','jib','journal'])
        self.assertEqual([r['bytes'] for r in rows],[512,512,4096,8388608])
        self.assertEqual(sum(r['bytes'] for r in rows),8393728)
        for row in rows:
            self.assertEqual(row['command'],['/tool','dd','-f','qcow2','-O','raw','bs=512',
                'count='+str((row['virtual_offset']+row['bytes'])//512), 'skip='+str(row['virtual_offset']//512),
                'if=/saved','of='+row['output']])
            self.assertGreaterEqual(row['virtual_offset'],m.DATA_BASE)
            self.assertLessEqual(row['virtual_offset']+row['bytes'],m.DATA_BASE+m.DATA_BYTES)

    def test_no_extra_or_type_coerced_layout_ranges(self):
        m=load()
        for key,value in (('jib_block',True),('journal_relative_offset',536576),('journal_bytes',16777216),('volume_offset',0),('extra',1)):
            changed=layout(m); changed[key]=value
            with self.subTest(key=key), self.assertRaises(ValueError):
                m.read_plan([Path('/a'),Path('/b')],changed,Path('/tool'))
        with self.assertRaises(ValueError): m.read_plan([Path('/same'),Path('/same')],layout(m),Path('/tool'))

    def test_jib_pointer_flags_and_metadata_overlap_refuse_before_journal(self):
        m=load(); guest=load(CPU/'inspect_ios26_firstboot_guest.py')
        valid=m.validate_jib(jib(),headers(),guest)
        self.assertNotIn('PRIVATE',json.dumps(valid)); self.assertNotIn('TESTONLY',json.dumps(valid))
        for flags,offset,size in ((5,532480,8388608),(1,536576,8388608),(1,532480,4096)):
            changed=bytearray(jib()); struct.pack_into('>I',changed,0,flags); struct.pack_into('>QQ',changed,36,offset,size)
            with self.subTest(flags=flags,offset=offset,size=size), self.assertRaises(ValueError):
                m.validate_jib(bytes(changed),headers(),guest)
        bad=bytearray(headers()[0]); struct.pack_into('>QII',bad,112,4096,0,1); struct.pack_into('>II',bad,128,130,1)
        with self.assertRaises(guest.InspectionError): m.validate_jib(jib(),[bytes(bad),headers()[1]],guest)

    def test_fresh_journal_keeps_unchanged_nonempty_validator(self):
        m=load(); guest=load(CPU/'inspect_ios26_firstboot_guest.py'); body=journal()
        with mock.patch.object(m,'EXPECTED_DATA_HEADER_SHA256',m.sha(body[:512])):
            m.validate_journal_header(body,guest)
            with self.assertRaises(ValueError): m.validate_journal_header(body[:-1],guest)
            changed=bytearray(body); changed[20]^=1
            with self.assertRaises(ValueError): m.validate_journal_header(bytes(changed),guest)
        with self.assertRaises(ValueError): m.validate_journal_header(body,guest)

    def test_changed_jib_stops_before_fourth_tool_and_partial_outputs_remain(self):
        m=load(); guest=load(CPU/'inspect_ios26_firstboot_guest.py'); calls=[]
        with tempfile.TemporaryDirectory() as root, mock.patch.object(m,'OUT',Path(root).resolve()):
            rows=m.read_plan([Path('/saved'),Path('/baseline')],layout(m),Path('/tool'),m.OUT)
            bodies=dict(zip(['primary','alternate','jib'],headers()+[bytes(4096)]))
            def execute(label,command,env,tool_rows):
                calls.append(label); Path(command[-1][3:]).write_bytes(bodies[label])
                tool_rows.append({'reaped':True,'forced':False,'exit_code':0})
            with mock.patch.object(m,'run_tool',side_effect=execute):
                with self.assertRaisesRegex(ValueError,'JIB changed'):
                    m.extract_data(types.SimpleNamespace(resources=lambda:None),rows,layout(m),headers(),guest,{},[])
            self.assertEqual(calls,['primary','alternate','jib'])
            self.assertTrue((m.OUT/'jib.bin').exists()); self.assertFalse((m.OUT/'journal.bin').exists())

    def test_existing_fixed_output_is_never_overwritten(self):
        m=load()
        with tempfile.TemporaryDirectory() as root, mock.patch.object(m,'OUT',Path(root).resolve()):
            rows=m.read_plan([Path('/saved'),Path('/baseline')],layout(m),Path('/tool'),m.OUT)
            (m.OUT/'primary.bin').write_bytes(b'preserve')
            with mock.patch.object(m,'run_tool') as run:
                with self.assertRaises(ValueError): m.extract_data(types.SimpleNamespace(),rows,layout(m),headers(),None,{},[])
                run.assert_not_called()
            self.assertEqual((m.OUT/'primary.bin').read_bytes(),b'preserve')


class OwnershipTests(unittest.TestCase):
    def test_stable_identity_matches_old_schema_and_rejects_symlink_and_hardlink(self):
        m=load()
        with tempfile.TemporaryDirectory() as root:
            path=Path(root).resolve()/'image.qcow2'; path.write_bytes(bytes(65536)+b'tail')
            row=m.stable_image_identity(path); s=path.stat()
            self.assertEqual(row,{'path':str(path),'device':s.st_dev,'inode':s.st_ino,'bytes':65540,
                'mtime_ns':s.st_mtime_ns,'ctime_ns':s.st_ctime_ns,'first_64k_sha256':m.sha(bytes(65536))})
            link=path.with_name('symlink'); link.symlink_to(path)
            with self.assertRaises(ValueError): m.stable_image_identity(link)
            os.link(path,path.with_name('hardlink'))
            with self.assertRaises(ValueError): m.stable_image_identity(path)

    def test_metadata_refusal_releases_both_locks_without_output_or_child(self):
        m=load()
        with tempfile.TemporaryDirectory() as root:
            base=Path(root).resolve(); prep=base/'prep'; work=base/'work'; prep.mkdir();work.mkdir()
            for d in (prep,work): (d/'owner.lock').write_bytes(b'')
            owner=types.SimpleNamespace(PREP=prep,WORK=work,canonical=lambda p:p)
            with mock.patch.object(m,'load_bound_owner',return_value=owner), mock.patch.object(m,'OUT',base/'fresh'), \
                 mock.patch.object(m,'check_metadata',side_effect=ValueError('synthetic refused')), \
                 mock.patch.object(m.subprocess,'Popen') as spawn, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(m.main(),2); spawn.assert_not_called(); self.assertFalse(m.OUT.exists())
            for d in (prep,work):
                with (d/'owner.lock').open('rb') as f: m.fcntl.flock(f,m.fcntl.LOCK_EX|m.fcntl.LOCK_NB)

    def test_owned_tool_timeout_kills_and_reaps_only_that_child_then_refuses(self):
        m=load()
        child=mock.Mock(); child.pid=912345; child.poll.side_effect=[None,0]; child.wait.return_value=-9
        with tempfile.TemporaryDirectory() as root, mock.patch.object(m,'OUT',Path(root).resolve()), \
             mock.patch.object(m.subprocess,'Popen',return_value=child) as spawn, \
             mock.patch.object(m.time,'monotonic',side_effect=[0,61]):
            rows=[]
            with self.assertRaisesRegex(ValueError,'did not finish cleanly'): m.run_tool('journal',['/fake/tool'],{},rows)
            child.kill.assert_called_once_with(); child.wait.assert_called_once_with(timeout=5)
            self.assertEqual(len(rows),1); self.assertTrue(rows[0]['forced']);self.assertTrue(rows[0]['reaped'])
            self.assertEqual(json.loads((m.OUT/'journal.exit.json').read_bytes()),rows[0])
            self.assertTrue(spawn.call_args.kwargs['start_new_session'])

    def test_owned_tool_log_overflow_forces_only_its_child_and_retains_failure(self):
        m=load(); child=mock.Mock();child.pid=912345;child.poll.side_effect=[None,0];child.wait.return_value=-9
        def spawn(*args,**kwargs):
            kwargs['stdout'].write(bytes(65537));kwargs['stdout'].flush();return child
        with tempfile.TemporaryDirectory() as root, mock.patch.object(m,'OUT',Path(root).resolve()), \
             mock.patch.object(m.subprocess,'Popen',side_effect=spawn):
            rows=[]
            with self.assertRaisesRegex(ValueError,'oversized'): m.run_tool('journal',['/fake/tool'],{},rows)
            child.kill.assert_called_once_with();self.assertTrue(rows[0]['forced']);self.assertTrue(rows[0]['reaped'])
            self.assertTrue((m.OUT/'journal.exit.json').exists())


class ProjectionBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.m=load();self.parser=load(HERE.parent/'parse_data_journal.py')
        self.incomplete=self.parser.new_result()
        self.incomplete.update(code='unsupported_zero_transaction_sequence',failure={
            'code':'unsupported_zero_transaction_sequence','record_index':0,'entry_index':None,'journal_offset':512})

    def test_incomplete_parser_outcome_is_preserved_without_acceptance(self):
        self.assertEqual(self.m.validate_parser_analysis(self.incomplete),self.incomplete)
        self.assertIs(self.incomplete['inspection_accepted'],False)

    def test_compact_terminal_summary_keeps_coverage_and_omits_record_rows(self):
        row=self.m.compact_analysis(self.incomplete)
        self.assertNotIn('records',row)
        self.assertEqual(row['counts'],self.incomplete['counts'])
        self.assertEqual(row['limitations'],self.incomplete['limitations'])
        self.assertEqual(row['record_count'],0)
        self.assertIs(row['full_selected_records_retained_in_result'],True)
        self.assertIsNone(self.m.compact_analysis(None))

    def test_missing_or_wrong_nonacceptance_flags_refuse(self):
        for key in ('readonly','replay_performed','filesystem_accepted','inspection_accepted','raw_payload_exported',
                    'target_block_numbers_exported','entry0_pointer_followed'):
            for mode in ('missing','opposite'):
                v=copy.deepcopy(self.incomplete)
                if mode=='missing': del v[key]
                else: v[key]=not v[key]
                with self.subTest(key=key,mode=mode),self.assertRaises(ValueError):self.m.validate_parser_analysis(v)

    def test_extra_raw_field_or_broader_scope_or_unbounded_positions_refuse(self):
        changes=[lambda v:v.update(raw_payload='private'),lambda v:v['scope'].update(active_end=700000),
                 lambda v:v['failure'].update(entry_index=4097),lambda v:v['counts'].update(live_entries=True),
                 lambda v:v['limitations'].update(known_guest_kernel_source_identity=True)]
        for change in changes:
            v=copy.deepcopy(self.incomplete);change(v)
            with self.assertRaises(ValueError):self.m.validate_parser_analysis(v)

    def test_completion_without_coverage_is_not_upgraded(self):
        v=copy.deepcopy(self.incomplete);v.update(status='STRUCTURE_DIAGNOSIS_COMPLETE',failure=None,
                                                code='supported_nonempty_structure_observed')
        with self.assertRaisesRegex(ValueError,'coverage'):self.m.validate_parser_analysis(v)


class MainOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.m=load();self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name).resolve()
        self.prep=self.base/'prep';self.work=self.base/'work';self.prep.mkdir();self.work.mkdir()
        for d in (self.prep,self.work):(d/'owner.lock').write_bytes(b'')
        self.out=self.base/'fresh'
        self.owner=types.SimpleNamespace(PREP=self.prep,WORK=self.work,canonical=lambda p:p,
            refuse_live_children=lambda:None,resources=lambda:None,identity=lambda p:{'pid':p,'starttime':1},
            utc=lambda:'2026-11-22T00:00:00+00:00')
        parser=load(HERE.parent/'parse_data_journal.py')
        self.analysis=parser.new_result();self.analysis.update(code='unsupported_zero_transaction_sequence',failure={
            'code':'unsupported_zero_transaction_sequence','record_index':0,'entry_index':None,'journal_offset':512})
        self.parser=types.SimpleNamespace(analyze_journal=mock.Mock(return_value=self.analysis))

    def tearDown(self):self.temp.cleanup()

    @contextlib.contextmanager
    def setup_main(self,preservation_error=None,save_failure=False):
        m=self.m;real_read=m.small_read;real_save=m.save_json
        def read(path,*args):
            if path==m.DIAGNOSTIC_SOURCE:return b'# exact synthetic own source\n'
            return real_read(path,*args)
        def extract(owner,plan,lay,heads,guest,env,rows):
            rows.extend({'pid':90000+i,'reaped':True,'forced':False,'exit_code':0} for i in range(4))
            return {'jib':jib(),'journal':journal()},[]
        def save(name,value):
            if save_failure and name=='result.json':raise OSError('synthetic result write failure')
            return real_save(name,value)
        with contextlib.ExitStack() as stack:
            patches={'OUT':self.out,'PARSER_SOURCE_PIN':{'bytes':1,'sha256':'0'*64}}
            for key,value in patches.items():stack.enter_context(mock.patch.object(m,key,value))
            funcs={'load_bound_owner':{'return_value':self.owner},
                'check_metadata':{'return_value':({}, {'backing_chain':[{'record':{'path':'saved'}},{'record':{'path':'baseline'}}]}, {})},
                'require_absent':{},'load_data_layout':{'return_value':(layout(m),headers())},
                'prepare_images':{'return_value':(None,Path('/tooling'),Path('/tool'),[Path('/saved'),Path('/baseline')],[])},
                'load_checkers':{'return_value':(None,self.parser)},'small_read':{'side_effect':read},
                'extract_data':{'side_effect':extract},'validate_jib':{'return_value':{'flags':1}},
                'verify_preservation':{'side_effect':preservation_error},'save_json':{'side_effect':save}}
            for name,kwargs in funcs.items():stack.enter_context(mock.patch.object(m,name,**kwargs))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            yield

    def assert_locks_released(self):
        for d in (self.prep,self.work):
            with (d/'owner.lock').open('rb') as f:self.m.fcntl.flock(f,self.m.fcntl.LOCK_EX|self.m.fcntl.LOCK_NB)

    def test_completed_extraction_keeps_parser_incomplete_and_no_safety_acceptance(self):
        with self.setup_main():self.assertEqual(self.m.main(),0)
        r=json.loads((self.out/'result.json').read_bytes())
        self.assertEqual(r['status'],'READONLY_DATA_JOURNAL_DIAGNOSTIC_OBSERVED')
        self.assertEqual(r['analysis']['status'],'INCOMPLETE')
        for key in ('inspection_success_claimed','replay_safety_claimed','filesystem_consistency_claimed','whole_image_hashes_recomputed'):
            self.assertIs(r[key],False)
        self.assertEqual(self.parser.analyze_journal.call_args.kwargs,{'volume_bytes':17179869184,
            'expected_header_sha256':self.m.EXPECTED_DATA_HEADER_SHA256})
        self.assert_locks_released()

    def test_after_read_preservation_failure_forces_incomplete(self):
        with self.setup_main(ValueError('synthetic preservation changed')):self.assertEqual(self.m.main(),2)
        r=json.loads((self.out/'result.json').read_bytes());self.assertEqual(r['status'],'INCOMPLETE')
        self.assertIn('synthetic preservation changed',r['preservation_error']);self.assert_locks_released()

    def test_result_write_failure_still_releases_both_locks(self):
        with self.setup_main(save_failure=True),self.assertRaisesRegex(OSError,'result write failure'):self.m.main()
        self.assert_locks_released();self.assertTrue((self.out/'session.json').exists())

    def test_resource_refusal_creates_no_output_or_parser_run(self):
        self.owner.resources=mock.Mock(side_effect=ValueError('synthetic resource refusal'))
        with self.setup_main():self.assertEqual(self.m.main(),2)
        self.assertFalse(self.out.exists());self.parser.analyze_journal.assert_not_called();self.assert_locks_released()


if __name__ == '__main__':
    unittest.main()
