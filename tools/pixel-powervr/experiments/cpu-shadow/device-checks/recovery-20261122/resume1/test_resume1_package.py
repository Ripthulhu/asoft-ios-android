#!/usr/bin/env python3
"""Offline regression checks for the reconstructed retry; never run a phone owner."""
import ast
import base64
import copy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
P=HERE/'package'
sha=lambda body:hashlib.sha256(body).hexdigest()

def module(name):
    spec=importlib.util.spec_from_file_location('test_'+name,P/(name+'.py'))
    result=importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result

def functions(path):
    return {n.name:n for n in ast.parse(path.read_text()).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}

def aststr(n):return ast.dump(n,include_attributes=False)

class SourceTests(unittest.TestCase):
    def test_adapter_function_bodies_unchanged(self):
        old=functions(ROOT/'firstboot-counter/package/run_guard_memfd_adapter.py')
        new=functions(P/'run_guard_memfd_adapter.py')
        self.assertEqual(set(old),set(new))
        for key in old:
            if key!='main':self.assertEqual(aststr(old[key]),aststr(new[key]),key)
        # The only main delta is the phase receipt prefix.
        source=(ROOT/'firstboot-counter/package/run_guard_memfd_adapter.py').read_text().replace('run-ios26-firstboot-memfd-adapter-counter1.py','run-ios26-firstboot-memfd-adapter-resume1.py').replace('pixel-firstboot-guard-e9cc754-counter1','pixel-firstboot-guard-e9cc754-resume1').replace('ios26-firstboot-counter1-adapter-','ios26-firstboot-resume1-adapter-')
        self.assertEqual(source,(P/'run_guard_memfd_adapter.py').read_text())
    def test_prior_failure12_bodies_unchanged(self):
        for prior,new in [(ROOT/'firstboot-counter/package/capture_counter1_preflight.py',P/'capture_resume1_preflight.py'),(ROOT/'recovered-owner-sources/run-ios26-firstboot-owner-counter1-pin1.py',P/'run_firstboot_owner_UNRELEASED.py')]:
            orig=functions(prior)['prior_failures']; now=functions(new)['_prior_failures12']; orig.name=now.name
            self.assertEqual(aststr(orig),aststr(now))
    def test_third_failure_functions_identical(self):
        first=functions(P/'capture_resume1_preflight.py')['prior_failures']
        second=functions(P/'run_firstboot_owner_UNRELEASED.py')['prior_failures']
        self.assertEqual(aststr(first),aststr(second))
    def test_original_guard_and_recovered_owner_pins(self):
        self.assertEqual(sha((ROOT/'firstboot-counter/guard-revision/guard_ios26_firstboot.py').read_bytes()),'ea40638312d6ac41607806ecb03c148fbd0677df6ab01480e13fd40536869674')
        self.assertEqual(sha((ROOT/'recovered-owner-sources/run-ios26-firstboot-owner-counter1-pin1.py').read_bytes()),'b7337a992b5c9c651aae1085c358a27c5d2c8b41998398afd5a4f5ba40c6e2e7')
    def test_owner_execution_body_unchanged(self):
        old=functions(ROOT/'recovered-owner-sources/run-ios26-firstboot-owner-counter1-pin1.py')
        new=functions(P/'run_firstboot_owner_UNRELEASED.py')
        for key in ('run','resources','create','identity','absent','read','checks_install'):
            self.assertEqual(aststr(old[key]),aststr(new[key]),key)
    def test_owner_blocked_and_preflight_not_execution(self):
        owner=module('run_firstboot_owner_UNRELEASED');capture=module('capture_resume1_preflight')
        self.assertEqual(owner.PREFLIGHT_BYTES,-1)
        self.assertEqual(owner.PREFLIGHT_SHA,'UNRELEASED_REQUIRES_FRESH_RESUME1_PREFLIGHT')
        self.assertNotIn('--execute',capture.COMMAND)
        self.assertEqual(capture.WORK,owner.WORK)
        self.assertEqual(capture.ADAPTER,owner.ADAPTER)
        self.assertEqual(capture.ADAPTER_SHA,sha((P/'run_guard_memfd_adapter.py').read_bytes()))
        self.assertEqual(owner.ADAPTER_SHA,capture.ADAPTER_SHA)
        self.assertIn("attempt.name == '07-0004'",(P/'run_firstboot_owner_UNRELEASED.py').read_text())
    def test_pins_match_selected_recovery(self):
        expected={r['label']:{k:v for k,v in r.items() if k!='label'} for r in json.loads((ROOT/'workspace-disconnect/failure-pins.json').read_text())['present_files']}
        for name in ('run_firstboot_owner_UNRELEASED','capture_resume1_preflight'):
            self.assertEqual(module(name).FAILED3_PINS,expected)

class ThirdFailureTests(unittest.TestCase):
    def setUp(self):
        self.m=module('capture_resume1_preflight'); m=self.m
        self.files={};self.existing=set();self.live={}
        self.old_owner=m.BASE/'ios26-firstboot-owner-counter1'
        self.ids={'wrapper':{'pid':28120,'starttime':7858275},'guard':{'pid':28121,'starttime':7858299}}
        old_adapter=m.BASE/'run-ios26-firstboot-memfd-adapter-counter1.py'
        old_source=m.BASE/'run-ios26-firstboot-owner-counter1-pin1.py'
        cmd=['/data/data/com.termux/files/usr/bin/python','-I','-B',str(old_adapter),'--execute']
        argv=[str(m.GUARD),'--audit-work',str(m.AUDIT),'--auditor-dir','/data/local/tmp/pixel-boot-checks-ebbc9c0/auditor','--runner-dir','/data/local/tmp/pixel-prep-runner-f4d64db','--work','/data/local/tmp/pixel-firstboot-guard-e9cc754-counter1','--execute']
        startup={'command':cmd,'started_utc':'fixture',**self.ids}
        exited={**startup,'exit_code':2,'owner_exit_code':2,'accepted':False,'guard_started':True,'guard_reaped':True,'forced_guard':False,'cleanup_errors':[]}
        astart={'phase':'execute','process':self.ids['guard'],'command':cmd,'guard_argv':argv,'adapter_source_sha256':'1402321c22ae98b0ba7094f9e121cb169f2bf4aea38d0272b957f08a26259725','guard_source_sha256':m.GUARD_SHA,'accepted_libc_smoke':{'receipt_sha256':m.SMOKE_SHA}}
        aexit={**astart,'exit_code':2,'error':None,'adapter_completed':False,'attributes_restored':True,'sources_unchanged':True}
        vm={'status':'INCOMPLETE','stage':'ios26-firstboot','cleanup':{'echild':True,'forced_descendants':[]},'qmp':[]}
        self.attempt=Path('/data/local/tmp/pixel-prep-e9cc754/attempts/07-0003')
        stage={'stage':'ios26-firstboot'}
        self.labels={'owner_exit':exited,'adapter_owner':astart,'adapter_exit':aexit,'vm_result':vm,'stage_inputs':stage,'guard_session':{'fixture':True}}
        tobytes=lambda v:(json.dumps(v,sort_keys=True)+'\n').encode()
        actual={'attempt':str(self.attempt),'files':{'stage-inputs.json':{'bytes':len(tobytes(stage)),'sha256':sha(tobytes(stage))},'vm-result.json':{'bytes':len(tobytes(vm)),'sha256':sha(tobytes(vm))}},'vm-result.json':vm}
        result={'schema':1,'status':'INCOMPLETE','bound_inputs_unchanged':True,'checkpoint_accepted_by_guard':False,'original_firstboot_checkpoint_present':False,'actual_attempt':actual,'post_stop_blockstats':[],'supervision':[{'status':'INCOMPLETE'}]}
        self.labels['guard_result']=result;self.labels['guard_observations']={'schema':1,'post_stop_blockstats':[],'supervision':result['supervision']}
        for label,pin in m.FAILED3_PINS.items():
            body=tobytes(self.labels[label]);self.files[Path(pin['path'])]=body
        self.pins={k:{**v,'bytes':len(self.files[Path(v['path'])]),'sha256':sha(self.files[Path(v['path'])])} for k,v in m.FAILED3_PINS.items()}
        self.files[self.old_owner/'owner.json']=tobytes(startup);self.files[self.old_owner/'command.json']=tobytes(cmd)
        self.files[old_adapter]=(ROOT/'firstboot-counter/package/run_guard_memfd_adapter.py').read_bytes()
        self.files[old_source]=(ROOT/'recovered-owner-sources/run-ios26-firstboot-owner-counter1-pin1.py').read_bytes()
        self.m._prior_failures12=lambda:{'07-0001':{'fixture':'one'},'07-0002':{'fixture':'two'}}
        self.m.read=lambda path,*args:self.files[Path(path)]
        self.m.identity=lambda pid:self.live.get(pid)
        self.m.FAILED3_PINS=self.pins
    def run_check(self):
        with patch.object(self.m.os.path,'lexists',lambda p:Path(p) in self.existing):
            return self.m.prior_failures()
    def test_accepts_sparse_pre_vm_failure(self):
        out=self.run_check();self.assertEqual(set(out),{'07-0001','07-0002','07-0003'});self.assertFalse(out['07-0003']['qemu_launched'])
    def test_rejects_every_tampered_pinned_file(self):
        for pin in self.pins.values():
            with self.subTest(path=pin['path']):
                p=Path(pin['path']);old=self.files[p];self.files[p]=old+b' '
                with self.assertRaises(ValueError):self.run_check()
                self.files[p]=old
    def test_rejects_live_historical_owner_and_guard(self):
        for key,value in self.ids.items():
            with self.subTest(role=key):
                self.live[value['pid']]=value
                with self.assertRaises(ValueError):self.run_check()
                self.live.clear()
    def test_accepts_pid_reuse_with_different_start(self):
        for value in self.ids.values():self.live[value['pid']]={**value,'starttime':value['starttime']+1}
        self.run_check()
    def test_rejects_new_launch_or_success_in_failed_attempt(self):
        for name in ('launch.json','vm.child.json','stage-result.json'):
            self.existing.add(self.attempt/name)
            with self.assertRaises(ValueError):self.run_check()
            self.existing.clear()
    def test_does_not_prohibit_new_success_when_rechecking_old_failures(self):
        self.existing.add(self.attempt.parent/'07-0004')
        self.existing.add(self.attempt.parent.parent/'checkpoints/ios26-firstboot.json')
        self.run_check()

class TransportTests(unittest.TestCase):
    def test_all_commands_decode_exact_reviewable_source_and_are_bounded(self):
        manifest=json.loads((P/'transport-steps.json').read_text())
        for row in manifest:
            cmd=(P/'preflight-transfer'/(row['name']+'.command.txt')).read_bytes()
            self.assertLessEqual(len(cmd),6000);self.assertEqual(sha(cmd),row['command_sha256'])
            argv=shlex.split(cmd.decode());self.assertEqual(argv[:4],['/data/data/com.termux/files/usr/bin/python','-I','-B','-c'])
            loader=ast.parse(argv[4]); encoded=next(n for n in ast.walk(loader) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='b64decode').args[0].value
            raw=gzip.decompress(base64.b64decode(encoded,validate=True))
            self.assertEqual(raw,(P/'preflight-transfer'/(row['name']+'.py')).read_bytes())
            self.assertEqual(sha(raw),row['source_sha256'])
    def test_bundle_reconstructs_adapter_and_readonly_capture_only(self):
        folder=P/'preflight-transfer';parts=[]
        for path in sorted(folder.glob('*-chunk-*.py')):
            tree=ast.parse(path.read_text());assign=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='body' for t in n.targets))
            parts.append(ast.literal_eval(assign.value))
        encoded=b''.join(parts);manifest=json.loads((P/'preflight-transfer-manifest.json').read_text())
        self.assertEqual(sha(encoded),manifest['encoded_sha256'])
        body=gzip.decompress(base64.b64decode(encoded,validate=True));self.assertEqual(sha(body),manifest['bundle_sha256']);self.assertEqual(len(body),manifest['bundle_bytes'])
        bundle=json.loads(body);files=bundle['files']
        self.assertEqual([r['path'] for r in files],['run-ios26-firstboot-memfd-adapter-resume1.py','capture-ios26-firstboot-resume1.py'])
        for row,name in zip(files,['run_guard_memfd_adapter.py','capture_resume1_preflight.py']):self.assertEqual(row['body'].encode(),(P/name).read_bytes())

if __name__=='__main__':unittest.main(verbosity=2)
