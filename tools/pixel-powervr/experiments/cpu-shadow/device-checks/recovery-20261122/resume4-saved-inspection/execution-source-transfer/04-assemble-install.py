import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'saved-inspection-resume4-execution-procstat1-transfer'
TARGET=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
INSTALL=BASE/'saved-inspection-resume4-execution-procstat1-install.json'
def read(path,limit):
 if path.resolve(strict=True)!=path: raise ValueError('noncanonical transfer path')
 with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
  a=os.fstat(f.fileno())
  if not stat.S_ISREG(a.st_mode) or a.st_nlink!=1 or a.st_uid!=0 or a.st_size>limit: raise ValueError('invalid transfer input')
  b=f.read(limit+1)
  z=os.fstat(f.fileno())
 if len(b)!=a.st_size or len(b)>limit or (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)!=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns): raise ValueError('transfer input changed')
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
mb=read(TRANSFER/'manifest.json',1079)
if hashlib.sha256(mb).hexdigest()!='1e33809a2e49ff421b4afcf40ff15c17d071abc46bf920e9953edebac980e6b2': raise ValueError('manifest differs')
m=json.loads(mb)
if {p.name for p in TRANSFER.iterdir()}!={'manifest.json',*(r['name'] for r in m['chunks'])}: raise ValueError('transfer already assembled or unknown files')
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
if b.get('schema')!=1 or b.get('kind')!='saved_inspection_resume4_execution_procstat1_sources' or [{k:r[k] for k in ('path','bytes','sha256')} for r in b['files']]!=m['files']: raise ValueError('bundle manifest differs')
for row in b['files']:
 body=row['body'].encode()
 if '/' in row['path'] or row['path'] in ('','.','..') or len(body)!=row['bytes'] or hashlib.sha256(body).hexdigest()!=row['sha256']: raise ValueError('source bytes differ')
 if os.path.lexists(TARGET/row['path']): raise ValueError('source exists; preserve it')
if os.path.lexists(INSTALL): raise ValueError('install receipt exists; preserve it')
if TARGET!=BASE: raise ValueError('unexpected existing source target')
save(TRANSFER/'install-reserved.json',b'{"installation_reserved":true,"execution_started":false}\n')
if TARGET.resolve(strict=True)!=TARGET: raise ValueError('source target differs')
for row in b['files']:
 body=row['body'].encode();target=TARGET/row['path'];save(target,body,0o644)
 if read(target,row['bytes'])!=body: raise ValueError('installed readback differs')
receipt={'schema':1,'kind':'saved_inspection_resume4_execution_procstat1_sources_install','installed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':m['files'],'target_directory':str(TARGET),'execution_started':False,'manifest_sha256':hashlib.sha256(mb).hexdigest()}
save(INSTALL,(json.dumps(receipt,indent=2)+'\n').encode())
print('REVIEWED SOURCES INSTALLED; NO EXECUTION',str(TARGET),flush=True)
for row in m['files']: print(row['path'],row['bytes'],row['sha256'],flush=True)
