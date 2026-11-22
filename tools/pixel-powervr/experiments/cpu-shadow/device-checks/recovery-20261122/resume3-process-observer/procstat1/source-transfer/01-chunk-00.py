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
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='3a5f39769ecd1a161f3d58df7f121f5b226a674bb5048f44c27e88c3cb0213b4': raise ValueError('chunk differs')
save(TRANSFER/'chunk-00',body)
if read(TRANSFER/'chunk-00',3500)!=body: raise ValueError('chunk readback differs')
print('OBSERVER CHUNK 00 VERIFIED',flush=True)
