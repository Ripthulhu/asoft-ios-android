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
mb=read(TRANSFER/'manifest.json',1678)
if hashlib.sha256(mb).hexdigest()!='8df1c00f09a83fe990001071e46e1bb0c6ab01ba2a9b489377cb8e0fb73fb4d7': raise ValueError('manifest differs')
m=json.loads(mb)
body=b'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'
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='a9569b9be9f7c802df190a1ff891b01c244f323e40fcff890b07056bd1aac297': raise ValueError('chunk differs')
save(TRANSFER/'chunk-03',body)
if read(TRANSFER/'chunk-03',3500)!=body: raise ValueError('chunk readback differs')
print('OBSERVER CHUNK 03 VERIFIED',flush=True)
