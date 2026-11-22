"""Read-only corroborating pins for nine completed resume5 receipt files."""
import argparse,datetime,hashlib,json,os,stat
from pathlib import Path

BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
WORK=Path('/data/local/tmp/pixel-saved-audit-e9cc754-resume5')
MON=BASE/'ios26-saved-inspection-resume5-observer-procstat1'
PATHS=(
 BASE/'ios26-saved-inspection-resume5-owner/exit.json',
 WORK/'result.json',WORK/'a1/vm-result.json',
 WORK/'a1/files/inspection/result.json',WORK/'a1/expected-policy.json',
 MON/'ready.json',MON/'exit.json',MON/'summary.json',MON/'events.jsonl')
IDENTITIES=None  # UNRELEASED: actual independently reviewed completed identities required.
LIMIT=1<<20

def require(ok,message):
 if not ok: raise ValueError(message)

def key(s):
 return (s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,s.st_nlink,
         s.st_size,s.st_mtime_ns,s.st_ctime_ns)

def absent():
 require(type(IDENTITIES) is tuple and len(IDENTITIES)==4 and
         all(type(row) is tuple and len(row)==3 and type(row[1]) is int and row[1]>0 and
             type(row[2]) is int and row[2]>0 for row in IDENTITIES) and
         tuple(row[0] for row in IDENTITIES)==('wrapper','inspector','qemu','observer'),
         'unreleased receipt reader requires actual completed identities')
 for label,pid,ticks in IDENTITIES:
  try:
   with os.fdopen(os.open('/proc/'+str(pid)+'/stat',os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
    raw=f.read(4097)
  except (FileNotFoundError,ProcessLookupError):
   continue
  require(len(raw)<=4096,'oversized task stat')
  left,right=raw.find(b'('),raw.rfind(b')')
  require(0<left<right and int(raw[:left].strip())==pid,'invalid task identity')
  fields=raw[right+1:].split()
  require(len(fields)>=20,'short task stat')
  require(int(fields[19])!=ticks,'recorded '+label+' identity still present')

def read(path):
 require(path.resolve(strict=True)==path,'noncanonical receipt')
 with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
  a=os.fstat(f.fileno())
  require(stat.S_ISREG(a.st_mode) and a.st_uid==0 and a.st_nlink==1 and
          0<=a.st_size<=LIMIT,'nonordinary or oversized receipt')
  body=f.read(LIMIT+1)
  z=os.fstat(f.fileno())
 require(len(body)==a.st_size<=LIMIT and key(a)==key(z),'receipt changed during read')
 require(path.resolve(strict=True)==path and key(os.lstat(path))==key(a),
         'receipt path changed')
 digest=hashlib.sha256(body)
 return key(a),{'path':str(path),'bytes':len(body),'sha256':digest.hexdigest(),
                'digest_bytes':list(digest.digest())}

def main(page):
 require(os.geteuid()==0,'root receipt reader required')
 absent()
 rows=[read(path) for path in PATHS]
 for path,(original,row) in zip(PATHS,rows):
  require(path.resolve(strict=True)==path and key(os.lstat(path))==original,
          'receipt changed during snapshot')
 absent()
 print(json.dumps({'schema':1,'status':'RESUME5_RECEIPT_PINS_OBSERVED',
  'readonly':True,'observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
  'page':page,'pages':2,'files':9,'recorded_identities_absent':True,
  'receipt_metadata_stable':True,'corroboration_only':True},separators=(',',':')),flush=True)
 for i in range(page*5,min(page*5+5,len(rows))):
  row=rows[i][1]
  print(json.dumps({'index':i,'path':row['path'],'bytes':row['bytes']},separators=(',',':')))
  print(row['sha256'])
  print(json.dumps(row['digest_bytes'],separators=(',',':')),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--page',type=int,choices=(0,1),required=True)
 args=parser.parse_args()
 try: main(args.page)
 except Exception as error:
  print(json.dumps({'status':'RESUME5_RECEIPT_PINS_REFUSED','readonly':True,
   'error':type(error).__name__+': '+str(error)},separators=(',',':')),flush=True)
  raise SystemExit(2)
