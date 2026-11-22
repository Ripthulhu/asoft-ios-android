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
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='93ca0207405fb298800731e954c20779a78063c7e7ec27318349de8d9ac905db': raise ValueError('chunk differs')
save(TRANSFER/'chunk-03',body)
if read(TRANSFER/'chunk-03',3500)!=body: raise ValueError('chunk readback differs')
print('OBSERVER CHUNK 03 VERIFIED',flush=True)
