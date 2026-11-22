import datetime, hashlib, json, os, pathlib, re, subprocess, sys, time
P = pathlib.Path
pid, expected_start = map(int, sys.argv[1:3])
receipt = P('/data/local/tmp/pixel-gpu-transfer-sxtv33sh/android-cached-compaction-resume1-01.jsonl')
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def memory():
    d = dict((a,b.strip()) for a,b in (l.split(':',1) for l in P('/proc/meminfo').read_text().splitlines()))
    return {k:int(d[k].split()[0])*1024 for k in ('MemAvailable','SwapTotal','SwapFree')}
def proc():
    p=P('/proc')/str(pid); raw=(p/'stat').read_text()
    d=dict((a,b.strip()) for a,b in (l.split(':',1) for l in (p/'status').read_text().splitlines()))
    return {'start':int(raw.rsplit(')',1)[1].split()[19]), 'uid':d['Uid'],
            'oom':int((p/'oom_score_adj').read_text()),
            **{k:int(d[k].split()[0])*1024 for k in ('RssAnon','VmRSS','VmSwap')}}
def ams():
    s=subprocess.run(['/system/bin/dumpsys','activity','processes'],capture_output=True,text=True,timeout=15,check=True).stdout
    matches=[b for b in re.split(r'(?=\s*\*APP\*)',s) if re.search(r'\bpid='+str(pid)+r'\b',b)]
    if len(matches)!=1: raise ValueError('process not uniquely recorded')
    b=matches[0]; stamp=re.search(r'lastCompactTime=(\d+)',b)
    return {'frozen':'isFrozen=true' in b,'pending_freeze':'isPendingFreeze=true' in b,
            'cached_empty':'cached=true empty=true' in b,
            'last_compact':int(stamp[1]) if stamp else None}
def write(fd, d):
    os.write(fd,(json.dumps(d,sort_keys=True)+'\n').encode());os.fsync(fd)
before=memory(); p=proc(); a=ams()
if before['MemAvailable'] >= 4026531840:
    print('COMPACTION_NOT_NEEDED',json.dumps(before));raise SystemExit(0)
if before['SwapFree']*5 < before['SwapTotal']:
    print('COMPACTION_NOT_REQUESTED_LOW_FREE_SWAP',json.dumps(before));raise SystemExit(0)
if p['start']!=expected_start or p['oom']<900 or not a['frozen'] or a['pending_freeze'] or not a['cached_empty']:
    raise ValueError('target no longer frozen cached-empty with cached priority')
base=receipt.parent
if os.geteuid()!=0 or base.resolve(strict=True)!=base:raise ValueError('canonical root receipt base required')
if proc()!=p or ams()!=a:raise ValueError('target changed before request')
if proc()!=p:raise ValueError('target changed during final AMS observation')
before=memory()
if before['MemAvailable'] >= 4026531840:
    print('COMPACTION_NOT_NEEDED',json.dumps(before));raise SystemExit(0)
if before['SwapFree']*5 < before['SwapTotal']:
    print('COMPACTION_NOT_REQUESTED_LOW_FREE_SWAP',json.dumps(before));raise SystemExit(0)
fd=os.open(receipt,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
try:
    write(fd,{'at':now(),'phase':'before','process':p,'ams':a,'memory':before})
    r=subprocess.run(['/system/bin/am','compact','full',str(pid)],capture_output=True,text=True,timeout=15)
    write(fd,{'at':now(),'phase':'requested','exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
    time.sleep(3)
    after=memory(); q=proc(); z=ams()
    same=q['start']==p['start'] and q['uid']==p['uid'] and q['oom']==p['oom'] and z['frozen'] and z['cached_empty']
    write(fd,{'at':now(),'phase':'after','process':q,'ams':z,'memory':after,'same_frozen_identity':same})
    print('BOUNDED ANDROID COMPACTION',now())
    advanced=type(z['last_compact']) is int and type(a['last_compact']) is int and z['last_compact']>a['last_compact']
    print('command_exit',r.returncode,'same_frozen_identity',same,'compact_record_advanced',advanced)
    print('before_memory',json.dumps(before));print('after_memory',json.dumps(after))
    print('anon_before_after',p['RssAnon'],q['RssAnon'],'swap_before_after',p['VmSwap'],q['VmSwap'])
    print('No process termination or manual thaw requested.')
finally:os.close(fd)
