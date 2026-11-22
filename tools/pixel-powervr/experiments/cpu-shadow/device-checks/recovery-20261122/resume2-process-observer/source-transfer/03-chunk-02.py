import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'resume2-process-observer-transfer'
INSTALL=BASE/'resume2-process-observer-install.json'
OWNER_SOURCE=BASE/'run-ios26-saved-inspection-resume2.py'
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
 for path in [INSTALL,BASE/'ios26-saved-inspection-resume2-observer',BASE/'ios26-saved-inspection-resume2-observer-launch.json',BASE/'ios26-saved-inspection-resume2-observer-wrapper.log']+[BASE/row['path'] for row in files]:
  if os.path.lexists(path): raise ValueError('fresh observer path required; preserve '+str(path))
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
mb=read(TRANSFER/'manifest.json',1647)
if hashlib.sha256(mb).hexdigest()!='dc136f8dd85dc2e8cdfdb00f8134d5d92ed132299a280e3999838acd398fe7cf': raise ValueError('manifest differs')
m=json.loads(mb)
body=b'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'
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='653cdc753a0fb7e00e165e6b2e9ba7c37d8d620d632f92dd0959e56bd3d4cfe5': raise ValueError('chunk differs')
save(TRANSFER/'chunk-02',body)
if read(TRANSFER/'chunk-02',3500)!=body: raise ValueError('chunk readback differs')
print('OBSERVER CHUNK 02 VERIFIED',flush=True)
