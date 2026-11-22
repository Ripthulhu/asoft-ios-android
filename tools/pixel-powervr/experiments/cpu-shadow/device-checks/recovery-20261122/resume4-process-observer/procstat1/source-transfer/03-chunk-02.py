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
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='6ae916aa41a1610d674541e977699e3d9fb9aca760381cda7bc62b9af6885581': raise ValueError('chunk differs')
save(TRANSFER/'chunk-02',body)
if read(TRANSFER/'chunk-02',3500)!=body: raise ValueError('chunk readback differs')
print('OBSERVER CHUNK 02 VERIFIED',flush=True)
