import pathlib,json,hashlib,datetime
b=pathlib.Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
a=(b/'ios26-firstboot-counter1-adapter-execute.owner.json').read_bytes()
assert hashlib.sha256(a).hexdigest()=='11a5691b70366201d374e341f16668a0d0b41a4cac37c2a3bfaa2d4c64fefd37'
d=json.loads(a)
expected={**d,'finished_utc':'2026-11-22T13:21:30.830188+00:00','exit_code':2,'error':None,'attributes_restored':True,'sources_unchanged':True,'adapter_completed':False}
e=(json.dumps(expected,indent=2)+'\n').encode();raw=(b/'ios26-firstboot-counter1-adapter-execute.exit.json').read_bytes()
print('EXIT RECONSTRUCTION',datetime.datetime.now(datetime.timezone.utc).isoformat())
print('exact_writer_bytes_match='+str(e==raw))
print('bytes='+str(len(raw)));print('sha256='+hashlib.sha256(raw).hexdigest())
print('all_capture_paths_absent='+str(all(not pathlib.Path(str(b/'ios26-firstboot-guard-preflight-resume1')+s).exists() for s in ('.command.json','.stdout','.stderr','.exit.json'))))
print('adapter_preflight_receipts_absent='+str(all(not pathlib.Path(str(b/'ios26-firstboot-resume1-adapter-preflight')+s).exists() for s in ('.owner.json','.exit.json'))))
print('new_guard_work_absent='+str(not pathlib.Path('/data/local/tmp/pixel-firstboot-guard-e9cc754-resume1').exists()))
