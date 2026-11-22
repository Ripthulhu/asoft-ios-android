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
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='c7fe597239d38b00c022e9c9706c39ededaab75fbdcc5e81c1ea161dce1965ac': raise ValueError('chunk differs')
save(TRANSFER/'chunk-01',body)
if read(TRANSFER/'chunk-01',3500)!=body: raise ValueError('chunk readback differs')
print('OBSERVER CHUNK 01 VERIFIED',flush=True)
