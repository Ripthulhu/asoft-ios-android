import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'resume1-owner-transfer'
def read(path,limit):
 if path.resolve(strict=True)!=path: raise ValueError('noncanonical transfer path')
 with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
  s=os.fstat(f.fileno())
  if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_uid!=0 or s.st_size>limit: raise ValueError('invalid transfer file')
  b=f.read(limit+1)
 if len(b)>limit: raise ValueError('transfer input exceeded bound')
 return b
def save(path,body,mode=0o600):
 with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode),'wb') as f:
  f.write(body);f.flush();os.fsync(f.fileno())
 d=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try: os.fsync(d)
 finally: os.close(d)
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
import datetime,gzip,io
if TRANSFER.resolve(strict=True)!=TRANSFER: raise ValueError('transfer directory differs')
mb=read(TRANSFER/'manifest.json',1383)
if hashlib.sha256(mb).hexdigest()!='638833f7810d4fcd50c90bf90cb9d9e27368f39baaaab3223a785d89cc9a8414': raise ValueError('manifest differs')
m=json.loads(mb)
if {x.name for x in TRANSFER.iterdir()}!={'manifest.json',*(x['name'] for x in m['chunks'])}: raise ValueError('transfer already assembled or unknown files')
parts=[]
for row in m['chunks']:
 b=read(TRANSFER/row['name'],row['bytes'])
 if len(b)!=row['bytes'] or hashlib.sha256(b).hexdigest()!=row['sha256']: raise ValueError('stored chunk differs')
 parts.append(b)
encoded=b''.join(parts)
if len(encoded)!=m['encoded_bytes'] or hashlib.sha256(encoded).hexdigest()!=m['encoded_sha256']: raise ValueError('complete transfer differs')
with gzip.GzipFile(fileobj=io.BytesIO(base64.b64decode(encoded,validate=True)),mode='rb') as f: bb=f.read(m['bundle_bytes']+1)
if len(bb)!=m['bundle_bytes'] or hashlib.sha256(bb).hexdigest()!=m['bundle_sha256']: raise ValueError('source bundle differs')
b=json.loads(bb)
if b.get('schema')!=1 or b.get('kind')!='resume1_owner_sources' or [{k:x[k] for k in ('path','bytes','sha256')} for x in b['files']]!=m['files']: raise ValueError('bundle manifest differs')
for row in b['files']:
 body=row['body'].encode()
 if '/' in row['path'] or len(body)!=row['bytes'] or hashlib.sha256(body).hexdigest()!=row['sha256']: raise ValueError('source bytes differ')
 if os.path.lexists(BASE/row['path']): raise ValueError('source already exists; preserve it')
if os.path.lexists(BASE/'resume1-owner-install.json'): raise ValueError('install receipt exists; preserve it')
save(TRANSFER/'install-reserved.json',b'{"installation_reserved":true,"execution_started":false}\n')
for row in b['files']:
 body=row['body'].encode();target=BASE/row['path'];save(target,body,0o644)
 if read(target,row['bytes'])!=body: raise ValueError('installed readback differs')
receipt={'schema':1,'kind':'resume1_owner_sources_install','installed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':m['files'],'execution_started':False,'manifest_sha256':hashlib.sha256(mb).hexdigest()}
save(BASE/'resume1-owner-install.json',(json.dumps(receipt,indent=2)+'\n').encode())
print('RESUME1 OWNER SOURCES INSTALLED; NO EXECUTION',flush=True)
for row in m['files']:print(row['path'],row['bytes'],row['sha256'],flush=True)
