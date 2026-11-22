import json,hashlib,pathlib,datetime
pins=json.loads("[{\"label\":\"owner_exit\",\"path\":\"/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-firstboot-owner-counter1/exit.json\",\"bytes\":811,\"sha256\":\"9926bd3afd65f392ca5d8fcaa4ec67f99428f7dc00dc89d863bed82ebf25faba\"},{\"label\":\"guard_result\",\"path\":\"/data/local/tmp/pixel-firstboot-guard-e9cc754-counter1/result.json\",\"bytes\":2693,\"sha256\":\"b93625243595ce587120da7bddeff89d208515b49877d161605ee6957249cf7b\"},{\"label\":\"guard_observations\",\"path\":\"/data/local/tmp/pixel-firstboot-guard-e9cc754-counter1/guard-observations.json\",\"bytes\":458,\"sha256\":\"2f0674be9937441f84ebd0dc3077344bc4789db463ecc42dc3d709fddc259442\"},{\"label\":\"adapter_owner\",\"path\":\"/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-firstboot-counter1-adapter-execute.owner.json\",\"bytes\":1876,\"sha256\":\"11a5691b70366201d374e341f16668a0d0b41a4cac37c2a3bfaa2d4c64fefd37\"},{\"label\":\"adapter_exit\",\"path\":\"/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-firstboot-counter1-adapter-execute.exit.json\",\"bytes\":2055,\"sha256\":\"d83951e8edc29c2eac4c1b6b8e5f2c3176f6c75a7e26590008afdeade88af4b3\"},{\"label\":\"guard_session\",\"path\":\"/data/local/tmp/pixel-firstboot-guard-e9cc754-counter1/guard-session.json\",\"bytes\":20936,\"sha256\":\"dbb13619f92e0349036a71088511db4eeb978aaae6a22428976761ef54b2873e\"},{\"label\":\"stage_inputs\",\"path\":\"/data/local/tmp/pixel-prep-e9cc754/attempts/07-0003/stage-inputs.json\",\"bytes\":16143,\"sha256\":\"1cc3ce6992bf97a756f59c0d2f9b6c3e87e6f5f18376b9ba385d1345f55f8312\"},{\"label\":\"vm_result\",\"path\":\"/data/local/tmp/pixel-prep-e9cc754/attempts/07-0003/vm-result.json\",\"bytes\":1052,\"sha256\":\"dc618e42ed91d42f3b93bc9be337f4732dee7caec7b58fa2fd2be81d1acc4084\"}]")
print('CURRENT FAILURE PINS',datetime.datetime.now(datetime.timezone.utc).isoformat())
for x in pins:
 b=pathlib.Path(x['path']).read_bytes();h=hashlib.sha256(b).hexdigest();ok=len(b)==x['bytes'] and h==x['sha256']
 print(x['label'],len(b),'MATCH' if ok else 'MISMATCH')
 if not ok:
  print('actual_hex',h);print('actual_decimal',list(bytes.fromhex(h)))
  if x['label']=='adapter_exit':
   d=json.loads(b);a=json.loads(pathlib.Path(x['path'].replace('.exit.json','.owner.json')).read_text())
   print('startup_differences',json.dumps({k:[v,d.get(k)] for k,v in a.items() if d.get(k)!=v}))
   print('exit_extras',json.dumps({k:v for k,v in d.items() if k not in a}))
   print('started_utc',a.get('started_utc'))
