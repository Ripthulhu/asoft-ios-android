import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'resume2-process-observer-procstat1-transfer'
INSTALL=BASE/'resume2-process-observer-procstat1-install.json'
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
 for path in [INSTALL,BASE/'ios26-saved-inspection-resume2-observer-procstat1',BASE/'ios26-saved-inspection-resume2-observer-procstat1-launch.json',BASE/'ios26-saved-inspection-resume2-observer-procstat1-wrapper.log']+[BASE/row['path'] for row in files]:
  if os.path.lexists(path): raise ValueError('fresh observer path required; preserve '+str(path))
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
mb=read(TRANSFER/'manifest.json',1678)
if hashlib.sha256(mb).hexdigest()!='a560443a8d372545001df2c12a66f6c67e779bfe9965f7b500a13ff151c085a4': raise ValueError('manifest differs')
m=json.loads(mb)
body=b'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'
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='4a0df93389cdeb94df9effed639be1072003d475513c71e91844a4174debf7af': raise ValueError('chunk differs')
save(TRANSFER/'chunk-01',body)
if read(TRANSFER/'chunk-01',3500)!=body: raise ValueError('chunk readback differs')
print('OBSERVER CHUNK 01 VERIFIED',flush=True)
