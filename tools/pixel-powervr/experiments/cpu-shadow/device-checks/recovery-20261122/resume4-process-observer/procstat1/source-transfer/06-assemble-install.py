import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'resume4-process-observer-procstat1-transfer'
INSTALL=BASE/'resume4-process-observer-procstat1-install.json'
OWNER_SOURCE=BASE/'run-ios26-saved-inspection-resume4.py'
def read(path,limit):
 if path.resolve(strict=True)!=path: raise ValueError('noncanonical input')
 with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
  a=os.fstat(f.fileno())
  if not stat.S_ISREG(a.st_mode) or a.st_uid!=0 or a.st_nlink!=1 or a.st_size>limit: raise ValueError('invalid bounded root-owned file')
  body=f.read(limit+1);b=os.fstat(f.fileno())
 if len(body)!=a.st_size or (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)!=(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns,b.st_ctime_ns): raise ValueError('input changed during read')
 return body
def save(path,body,mode=0o600):
 with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode),'wb') as f:
  os.fchmod(f.fileno(),mode);f.write(body);f.flush();os.fsync(f.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try: os.fsync(fd)
 finally: os.close(fd)
def fresh(files):
 for path in [INSTALL,BASE/'ios26-saved-inspection-resume4-observer-procstat1',BASE/'ios26-saved-inspection-resume4-observer-procstat1-launch.json',BASE/'ios26-saved-inspection-resume4-observer-procstat1-wrapper.log']+[BASE/row['path'] for row in files]:
  if os.path.lexists(path): raise ValueError('fresh observer path required; preserve '+str(path))
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
import datetime,gzip,io
mb=read(TRANSFER/'manifest.json',1678)
if hashlib.sha256(mb).hexdigest()!='8df1c00f09a83fe990001071e46e1bb0c6ab01ba2a9b489377cb8e0fb73fb4d7': raise ValueError('manifest differs')
m=json.loads(mb)
if {p.name for p in TRANSFER.iterdir()}!={'manifest.json',*(r['name'] for r in m['chunks'])}: raise ValueError('transfer already assembled or unexpected content')
parts=[]
for r in m['chunks']:
 b=read(TRANSFER/r['name'],r['bytes'])
 if len(b)!=r['bytes'] or hashlib.sha256(b).hexdigest()!=r['sha256']: raise ValueError('stored chunk differs')
 parts.append(b)
encoded=b''.join(parts)
if len(encoded)!=m['encoded_bytes'] or hashlib.sha256(encoded).hexdigest()!=m['encoded_sha256']: raise ValueError('encoded bundle differs')
with gzip.GzipFile(fileobj=io.BytesIO(base64.b64decode(encoded,validate=True)),mode='rb') as f: bundle=f.read(m['bundle_bytes']+1)
if len(bundle)!=m['bundle_bytes'] or hashlib.sha256(bundle).hexdigest()!=m['bundle_sha256']: raise ValueError('bundle differs')
b=json.loads(bundle)
if b.get('schema')!=1 or b.get('kind')!='resume4_process_observer_procstat1_sources' or [{k:r[k] for k in ('path','bytes','sha256')} for r in b['files']]!=m['files']: raise ValueError('source inventory differs')
if [r['path'] for r in b['files']]!=['run-ios26-saved-inspection-resume4-observer-procstat1.py','launch-ios26-saved-inspection-resume4-observer-procstat1.py']: raise ValueError('source destinations differ')
for r in b['files']:
 body=r['body'].encode()
 if '/' in r['path'] or len(body)!=r['bytes'] or hashlib.sha256(body).hexdigest()!=r['sha256']: raise ValueError('source differs')
fresh(m['files'])
p=m['inspection_owner_source'];owner_body=read(OWNER_SOURCE,p['bytes'])
if len(owner_body)!=p['bytes'] or hashlib.sha256(owner_body).hexdigest()!=p['sha256']: raise ValueError('inspection owner source differs')
save(TRANSFER/'install-reserved.json',b'{"installation_reserved":true,"execution_started":false}\n')
for r in b['files']:
 body=r['body'].encode();save(BASE/r['path'],body,0o644)
 if read(BASE/r['path'],r['bytes'])!=body: raise ValueError('installed source readback differs')
p=m['inspection_owner_source'];owner_body=read(OWNER_SOURCE,p['bytes'])
if len(owner_body)!=p['bytes'] or hashlib.sha256(owner_body).hexdigest()!=p['sha256']: raise ValueError('inspection owner source differs')
receipt={'schema':1,'kind':'resume4_process_observer_procstat1_sources_install','installed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':m['files'],'inspection_owner_source':m['inspection_owner_source'],'manifest_sha256':hashlib.sha256(mb).hexdigest(),'execution_started':False,'inspection_started':False}
save(INSTALL,(json.dumps(receipt,indent=2)+'\n').encode())
print('OBSERVER SOURCES INSTALLED; NO EXECUTION',flush=True)
for r in m['files']: print(r['path'],r['bytes'],r['sha256'],flush=True)
