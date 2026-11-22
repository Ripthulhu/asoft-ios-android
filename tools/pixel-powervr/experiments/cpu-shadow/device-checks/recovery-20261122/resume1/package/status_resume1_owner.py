#!/usr/bin/env python3
"""Read only the resume1 owner, guard and attempt metadata; never signal or retry."""
import datetime,hashlib,json,os,re,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
OWNER=BASE/'ios26-firstboot-owner-resume1'
WORK=Path('/data/local/tmp/pixel-firstboot-guard-e9cc754-resume1')
PREP=Path('/data/local/tmp/pixel-prep-e9cc754')
ATTEMPT=PREP/'attempts/07-0004'

def read(path):
 if not path.exists():return None,None
 if path.resolve(strict=True)!=path:raise ValueError('noncanonical metadata')
 with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
  s=os.fstat(f.fileno())
  if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_size>2**20:raise ValueError('nonordinary/oversized metadata')
  b=f.read((2**20)+1)
 if len(b)>2**20:raise ValueError('metadata exceeded bound')
 return json.loads(b),{'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}

def present(value):
 if not value:return None
 p=Path('/proc')/str(value['pid'])/'stat'
 try:b=p.read_bytes()
 except FileNotFoundError:return False
 if len(b)>4096:raise ValueError('oversized process stat')
 f=b[b.rfind(b')')+2:].split()
 return int(f[19])==value.get('starttime',value.get('start_ticks'))

def main():
 print('RESUME1 READ-ONLY STATUS',datetime.datetime.now(datetime.timezone.utc).isoformat())
 startup,_=read(OWNER/'owner.json');exited,exit_pin=read(OWNER/'exit.json')
 print('owner_dir_present',OWNER.exists(),'owner_receipt_present',startup is not None,'exit_receipt_present',exited is not None)
 if startup:
  print('wrapper_identity',startup.get('wrapper'),'still_present',present(startup.get('wrapper')))
  print('guard_identity',startup.get('guard'),'still_present',present(startup.get('guard')))
 if exited:
  print('owner_result',json.dumps({k:exited.get(k) for k in ('exit_code','owner_exit_code','accepted','guard_started','guard_reaped','forced_guard','cleanup_errors','wrapper_error','finished_utc')}))
  print('owner_exit_pin',json.dumps(exit_pin))
 result,result_pin=read(WORK/'result.json')
 if result:
  print('guard_result',json.dumps({k:result.get(k) for k in ('status','checkpoint_accepted_by_guard','bound_inputs_unchanged','original_firstboot_checkpoint_present','error','identity_error','attempt_error')}))
  print('guard_result_pin',json.dumps(result_pin))
 print('attempt_present',ATTEMPT.exists())
 vm,_=read(ATTEMPT/'vm-result.json');child,_=read(ATTEMPT/'vm.child.json')
 if child:print('qemu_identity',child,'still_present',present(child))
 if vm:
  print('vm_result',json.dumps({k:vm.get(k) for k in ('status','stage','milestone','settled','guest_sync_answered','error')}))
  print('native_witnesses',json.dumps({k:vm.get('witnesses',{}).get(k) for k in ('native_initialization','native_execution','native_svc_final','gpu_execution')}))
  print('cleanup',json.dumps(vm.get('cleanup',{})))
 checkpoint,checkpoint_pin=read(PREP/'checkpoints/ios26-firstboot.json')
 print('firstboot_checkpoint',json.dumps(checkpoint_pin))
 if checkpoint:print('checkpoint_attempt',checkpoint.get('attempt'),'status',checkpoint.get('status'))
 for name,path in [('guard_session',WORK/'guard-session.json'),('guard_observations',WORK/'guard-observations.json')]:
  _,pin=read(path)
  if pin:print(name+'_pin',json.dumps(pin))
 memory=Path('/proc/meminfo').read_text()
 for key in ('MemAvailable','SwapFree'):
  match=re.search('^'+key+r':\s+(\d+) kB$',memory,re.M)
  print(key+'_bytes',int(match[1])*1024 if match else None)
 print('readonly_status_complete',flush=True)
if __name__=='__main__':main()
