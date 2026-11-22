#!/usr/bin/env python3
"""Offline checks of the observed one-byte receipt-pin repair and exclusive installer."""
import ast,base64,contextlib,gzip,hashlib,io,json,os,shlex,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent;P=HERE/'package';sha=lambda x:hashlib.sha256(x).hexdigest()
class PinTests(unittest.TestCase):
 def test_each_source_changes_one_documented_byte(self):
  e=json.loads((HERE/'adapter-exit-pin-erratum.json').read_text())
  self.assertEqual(bytes(e['observed_sha256_decimal']).hex(),e['observed_sha256'])
  for name,record in e['revisions'].items():
   old=(P/record['predecessor']).read_bytes();new=(P/name).read_bytes()
   self.assertEqual(sha(old),record['before_sha256']);self.assertEqual(sha(new),record['sha256'])
   self.assertEqual(len(old),len(new));self.assertEqual([i for i in range(len(old)) if old[i]!=new[i]],[record['changed_source_byte_offset']])
   self.assertEqual(old[record['changed_source_byte_offset']],ord('0'));self.assertEqual(new[record['changed_source_byte_offset']],ord('b'))
 def test_command_decodes_to_installer_and_is_bounded(self):
  cmd=(P/'install-capture-pin1.command.txt').read_bytes();self.assertLessEqual(len(cmd),6000)
  argv=shlex.split(cmd.decode());self.assertEqual(argv[:4],['/data/data/com.termux/files/usr/bin/python','-I','-B','-c'])
  tree=ast.parse(argv[4]);node=next(n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='b64decode')
  self.assertEqual(gzip.decompress(base64.b64decode(ast.literal_eval(node.args[0]),validate=True)),(P/'install_capture_pin1.py').read_bytes())
 def simulate(self,variant):
  with tempfile.TemporaryDirectory(prefix='capture-pin1-offline-') as d:
   base=Path(d).resolve();old=base/'capture-ios26-firstboot-resume1.py';old.write_bytes((P/'capture_resume1_preflight.py').read_bytes())
   code=(P/'install_capture_pin1.py').read_text().replace("BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')",f'BASE=Path({str(base)!r})').replace("WORK=Path('/data/local/tmp/pixel-firstboot-guard-e9cc754-resume1')",f'WORK=Path({str(base/"guard-work")!r})')
   target=base/'capture-ios26-firstboot-resume1-pin1.py';receipt=base/'resume1-preflight-capture-pin1-install.json'
   if variant=='changed-original':old.write_bytes(old.read_bytes()+b'x')
   if variant=='existing-phase':(base/'ios26-firstboot-resume1-adapter-preflight.owner.json').write_text('{}\n')
   before=old.read_bytes()
   with contextlib.redirect_stdout(io.StringIO()):
    if variant!='success':
     with self.assertRaises(ValueError):exec(compile(code,'path-substituted-offline-installer','exec'),{})
     self.assertFalse(target.exists());self.assertFalse(receipt.exists())
    else:
     exec(compile(code,'path-substituted-offline-installer','exec'),{})
     self.assertEqual(target.read_bytes(),(P/'capture_resume1_preflight_pin1.py').read_bytes())
     self.assertFalse(json.loads(receipt.read_text())['execution_started'])
     with self.assertRaises(ValueError):exec(compile(code,'path-substituted-offline-installer','exec'),{})
   self.assertEqual(old.read_bytes(),before)
 @unittest.skipUnless(os.geteuid()==0,'installer is root-only')
 def test_install_preserves_original_and_refuses_replay(self):self.simulate('success')
 @unittest.skipUnless(os.geteuid()==0,'installer is root-only')
 def test_changed_source_refused_before_new_files(self):self.simulate('changed-original')
 @unittest.skipUnless(os.geteuid()==0,'installer is root-only')
 def test_existing_adapter_receipt_refused_before_new_files(self):self.simulate('existing-phase')
if __name__=='__main__':unittest.main(verbosity=2)
