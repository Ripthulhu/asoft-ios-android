"""One measured cache-reclaim operation while the preparation lock is idle."""
import datetime,fcntl,hashlib,json,os,pathlib,stat
P=pathlib.Path
BASE=P('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
PREP=P('/data/local/tmp/pixel-prep-e9cc754')
RECEIPT=BASE/'kernel-clean-cache-reclaim-resume1-01.jsonl'
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def mem():
 d=dict((a,b.strip()) for a,b in (l.split(':',1) for l in P('/proc/meminfo').read_text().splitlines()))
 return {k:int(d[k].split()[0])*1024 for k in ('MemFree','MemAvailable','Cached','SReclaimable','SUnreclaim','SwapTotal','SwapFree','Dirty','Writeback')}
def oom():
 d=dict(l.split() for l in P('/proc/vmstat').read_text().splitlines());return int(d['oom_kill'])
def absent():
 for p in (BASE/'ios26-firstboot-owner-resume1',BASE/'ios26-firstboot-owner-resume1-launch.json',BASE/'ios26-firstboot-owner-resume1-wrapper.log',P('/data/local/tmp/pixel-firstboot-guard-e9cc754-resume1'),PREP/'attempts/07-0004',PREP/'checkpoints/ios26-firstboot.json'):
  if os.path.lexists(p):raise ValueError('boot state no longer idle: '+str(p))
def log(fd,d):os.write(fd,(json.dumps(d,sort_keys=True)+'\n').encode());os.fsync(fd)
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE or PREP.resolve(strict=True)!=PREP:raise ValueError('canonical root preparation required')
fd=os.open(PREP/'owner.lock',os.O_RDONLY|os.O_NOFOLLOW)
try:
 if not stat.S_ISREG(os.fstat(fd).st_mode):raise ValueError('nonordinary preparation lock')
 fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);absent()
 before=mem()
 if before['MemAvailable'] >= 4026531840:
  print('CACHE_RECLAIM_NOT_NEEDED',now(),json.dumps(before));raise SystemExit(0)
 public=json.loads((BASE/'ios26-firstboot-guard-preflight-resume1.stdout.json').read_text())
 paths=public['guard_session']['frozen_input_identities']
 def identities():
  out={}
  for v in paths.values():
   p=P(v['path']);s=p.stat();out[str(p)]={'dev':s.st_dev,'ino':s.st_ino,'size':s.st_size,'mtime_ns':s.st_mtime_ns}
  return out
 original=identities();before_oom=oom()
 note=os.open(RECEIPT,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 try:
  log(note,{'phase':'before','at_utc':now(),'memory':before,'oom_kill':before_oom,'input_stat_identities':original})
  os.sync();absent()
  control=P('/proc/sys/vm/drop_caches')
  if control.resolve(strict=True)!=control:raise ValueError('unexpected cache control path')
  drop=os.open(control,os.O_WRONLY|os.O_NOFOLLOW)
  try:
   if os.write(drop,b'3\n')!=2:raise OSError('short cache control write')
  finally:os.close(drop)
  after=mem();same=identities()==original;after_oom=oom()
  out={'phase':'after','at_utc':now(),'memory':after,'input_stat_identities_unchanged':same,'oom_kill_before':before_oom,'oom_kill_after':after_oom,'cache_request':3,'process_termination_requested':False,'persistent_policy_change':False}
  log(note,out)
  print('ONE-TIME CLEAN CACHE RECLAIM',out['at_utc'])
  print('before',json.dumps(before));print('after',json.dumps(after))
  print('MemAvailable_change_bytes',after['MemAvailable']-before['MemAvailable'])
  print('input_stat_identities_unchanged',same,'oom_kill_unchanged',after_oom==before_oom)
 except BaseException as e:
  log(note,{'phase':'error','at_utc':now(),'error':type(e).__name__+': '+str(e)});raise
 finally:os.close(note)
finally:os.close(fd)
