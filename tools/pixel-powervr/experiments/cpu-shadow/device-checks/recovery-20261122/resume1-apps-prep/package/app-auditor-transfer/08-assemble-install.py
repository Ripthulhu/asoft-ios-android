import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'resume1-apps-auditor-transfer'
DEST=Path('/data/local/tmp/pixel-app-checks-counter1-resume1')
INSTALL=BASE/'resume1-apps-auditor-install.json'
def read(path,limit):
 if path.resolve(strict=True)!=path: raise ValueError('noncanonical transfer/source path')
 with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
  info=os.fstat(f.fileno())
  if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_uid!=0 or info.st_size>limit: raise ValueError('invalid bounded root-owned file')
  body=f.read(limit+1)
 if len(body)>limit: raise ValueError('input exceeded bound')
 return body
def save(path,body,mode=0o600):
 with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode),'wb') as f:
  os.fchmod(f.fileno(),mode);f.write(body);f.flush();os.fsync(f.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try: os.fsync(fd)
 finally: os.close(fd)
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
import datetime,gzip,io
if TRANSFER.resolve(strict=True)!=TRANSFER: raise ValueError('transfer path differs')
mb=read(TRANSFER/'manifest.json',2896)
if hashlib.sha256(mb).hexdigest()!='6f8fa424f05e409e0e349885b0390684744ddd45fbf0b08f9347a8cff8f00eba': raise ValueError('manifest differs')
m=json.loads(mb)
if {p.name for p in TRANSFER.iterdir()}!={'manifest.json',*(row['name'] for row in m['chunks'])}: raise ValueError('transfer already assembled or unexpected content')
parts=[]
for row in m['chunks']:
 body=read(TRANSFER/row['name'],row['bytes'])
 if len(body)!=row['bytes'] or hashlib.sha256(body).hexdigest()!=row['sha256']: raise ValueError('stored chunk differs')
 parts.append(body)
encoded=b''.join(parts)
if len(encoded)!=m['encoded_bytes'] or hashlib.sha256(encoded).hexdigest()!=m['encoded_sha256']: raise ValueError('complete transfer differs')
with gzip.GzipFile(fileobj=io.BytesIO(base64.b64decode(encoded,validate=True)),mode='rb') as f: bundle=f.read(m['bundle_bytes']+1)
if len(bundle)!=m['bundle_bytes'] or hashlib.sha256(bundle).hexdigest()!=m['bundle_sha256']: raise ValueError('source bundle differs')
b=json.loads(bundle)
if b.get('schema')!=1 or b.get('kind')!='resume1_apps_auditor_sources' or [{k:row[k] for k in ('path','bytes','sha256')} for row in b['files']]!=m['files']: raise ValueError('source inventory differs')
if m['source_directory']!=str(DEST) or set(row['path'] for row in b['files'])!={'audit_ios26_apps.py','audit_ios26_apps_guest.py'}: raise ValueError('invalid source destination/inventory')
for row in b['files']:
 body=row['body'].encode()
 if '/' in row['path'] or len(body)!=row['bytes'] or hashlib.sha256(body).hexdigest()!=row['sha256']: raise ValueError('source bytes differ')
for path in (DEST,INSTALL):
 if os.path.lexists(path): raise ValueError('source/install target exists; preserve it')
for path,pin in m['dependencies'].items():
 if hashlib.sha256(read(Path(path),4<<20)).hexdigest()!=pin: raise ValueError('prerequisite source changed: '+path)
save(TRANSFER/'install-reserved.json',b'{"installation_reserved":true,"execution_started":false}\n')
DEST.mkdir(mode=0o755);os.chmod(DEST,0o755)
for row in b['files']:
 body=row['body'].encode();target=DEST/row['path'];save(target,body,0o644)
 if read(target,row['bytes'])!=body: raise ValueError('installed source readback differs')
if {p.name for p in DEST.iterdir()}!={row['path'] for row in m['files']}: raise ValueError('installed source directory contains unexpected files')
for path,pin in m['dependencies'].items():
 if hashlib.sha256(read(Path(path),4<<20)).hexdigest()!=pin: raise ValueError('prerequisite changed during source install: '+path)
receipt={'schema':1,'kind':'resume1_apps_auditor_sources_install','source_directory':str(DEST),
 'installed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':m['files'],
 'dependencies':m['dependencies'],'manifest_sha256':hashlib.sha256(mb).hexdigest(),
 'execution_started':False,'preparation_started':False,'helper_started':False}
save(INSTALL,(json.dumps(receipt,indent=2)+'\n').encode())
print('APPS AUDITOR SOURCES INSTALLED; NO EXECUTION',flush=True)
for row in m['files']: print(row['path'],row['bytes'],row['sha256'],flush=True)
