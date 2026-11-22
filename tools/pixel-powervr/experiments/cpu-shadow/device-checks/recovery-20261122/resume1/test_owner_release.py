#!/usr/bin/env python3
"""Offline verification of observed-preflight finalization and owner staging."""
import ast,base64,gzip,hashlib,importlib.util,json,shlex,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent;P=HERE/'package';sha=lambda b:hashlib.sha256(b).hexdigest()
def load(name):
 s=importlib.util.spec_from_file_location('review_'+name,P/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class OwnerTests(unittest.TestCase):
 def test_final_owner_contains_only_observed_pin_delta(self):
  source=(P/'run_firstboot_owner_UNRELEASED_pin1.py').read_text()
  source=source.replace("PREFLIGHT_SHA = 'UNRELEASED_REQUIRES_FRESH_RESUME1_PREFLIGHT'","PREFLIGHT_SHA = '42a0fefd327fd8be51eebb9be6fac4def61a18f5cf8bb274af23d6c093cbe222'")
  source=source.replace('PREFLIGHT_BYTES = -1  # Blocked until a fresh observed resume1 capture is supplied.','PREFLIGHT_BYTES = 21988  # Physically observed fresh resume1 read-only preflight.')
  self.assertEqual(source,(P/'run_firstboot_owner.py').read_text())
 def test_launcher_owner_and_adapter_pins_match(self):
  m=load('launch_firstboot_owner');o=load('run_firstboot_owner')
  self.assertEqual(m.SOURCE_SHA256,sha((P/'run_firstboot_owner.py').read_bytes()))
  self.assertEqual(m.SOURCE_BYTES,len((P/'run_firstboot_owner.py').read_bytes()))
  self.assertEqual(m.ADAPTER_SHA,sha((P/'run_guard_memfd_adapter.py').read_bytes()))
  self.assertEqual(m.OWNER,o.OWNER);self.assertEqual(m.WORK,o.WORK)
  self.assertEqual(m.COMMAND,[m.PYTHON,'-I','-B',str(m.SOURCE),'--execute'])
  self.assertEqual(o.PREFLIGHT_BYTES,21988)
  self.assertEqual(bytes([66,160,254,253,50,127,216,190,81,238,187,155,230,250,196,222,246,26,24,245,207,139,178,116,175,35,214,192,147,203,226,34]).hex(),o.PREFLIGHT_SHA)
 def test_all_owner_commands_decode_exact_sources_with_bound(self):
  for row in json.loads((P/'owner-transport-steps.json').read_text()):
   path=P/'owner-transfer';cmd=(path/(row['name']+'.command.txt')).read_bytes()
   self.assertLessEqual(len(cmd),6000);self.assertEqual(sha(cmd),row['command_sha256'])
   argv=shlex.split(cmd.decode());self.assertEqual(argv[:4],['/data/data/com.termux/files/usr/bin/python','-I','-B','-c'])
   n=next(n for n in ast.walk(ast.parse(argv[4])) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='b64decode')
   body=gzip.decompress(base64.b64decode(ast.literal_eval(n.args[0]),validate=True))
   self.assertEqual(body,(path/(row['name']+'.py')).read_bytes());self.assertEqual(sha(body),row['source_sha256'])
 def test_bundle_exactly_reconstructs_final_owner_and_launcher(self):
  parts=[]
  for p in sorted((P/'owner-transfer').glob('*-chunk-*.py')):
   n=next(n for n in ast.parse(p.read_text()).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='body' for t in n.targets));parts.append(ast.literal_eval(n.value))
  enc=b''.join(parts);m=json.loads((P/'owner-transfer-manifest.json').read_text());self.assertEqual(sha(enc),m['encoded_sha256'])
  b=gzip.decompress(base64.b64decode(enc,validate=True));self.assertEqual(sha(b),m['bundle_sha256']);self.assertEqual(len(b),m['bundle_bytes'])
  rows=json.loads(b)['files'];self.assertEqual([r['path'] for r in rows],['run-ios26-firstboot-owner-resume1.py','launch-ios26-firstboot-owner-resume1.py'])
  for row,name in zip(rows,['run_firstboot_owner.py','launch_firstboot_owner.py']):self.assertEqual(row['body'].encode(),(P/name).read_bytes())
 def test_launch_command_verifies_final_launcher(self):
  cmd=(P/'launch-owner.command.txt').read_text();argv=shlex.split(cmd)
  self.assertEqual(argv[:4],['/data/data/com.termux/files/usr/bin/python','-I','-B','-c'])
  source=(P/'launch_firstboot_owner.py').read_bytes()
  self.assertIn(sha(source),argv[4]);self.assertIn(str(len(source)),argv[4]);self.assertIn("'__name__':'__main__'",argv[4])
if __name__=='__main__':unittest.main(verbosity=2)
