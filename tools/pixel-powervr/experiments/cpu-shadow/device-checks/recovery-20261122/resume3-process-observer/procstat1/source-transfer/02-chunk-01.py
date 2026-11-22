import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'resume3-process-observer-procstat1-transfer'
INSTALL=BASE/'resume3-process-observer-procstat1-install.json'
OWNER_SOURCE=BASE/'run-ios26-saved-inspection-resume3.py'
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
 for path in [INSTALL,BASE/'ios26-saved-inspection-resume3-observer-procstat1',BASE/'ios26-saved-inspection-resume3-observer-procstat1-launch.json',BASE/'ios26-saved-inspection-resume3-observer-procstat1-wrapper.log']+[BASE/row['path'] for row in files]:
  if os.path.lexists(path): raise ValueError('fresh observer path required; preserve '+str(path))
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
mb=read(TRANSFER/'manifest.json',1678)
if hashlib.sha256(mb).hexdigest()!='affe3f299edc825a462e69d21f88771fc8c24971eea62b610f6bee6b6e10fc02': raise ValueError('manifest differs')
m=json.loads(mb)
body=b'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'
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='5f7d1ce1d96a8a90102c19f622e0b890cc6d7823bbda30bfbd3865ccb9e184aa': raise ValueError('chunk differs')
save(TRANSFER/'chunk-01',body)
if read(TRANSFER/'chunk-01',3500)!=body: raise ValueError('chunk readback differs')
print('OBSERVER CHUNK 01 VERIFIED',flush=True)
