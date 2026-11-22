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
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='ea41a1f49b562a5a8ec04367c35bdaddd2665ac3db465a191da9cb78bbcbc360': raise ValueError('chunk differs')
save(TRANSFER/'chunk-00',body)
if read(TRANSFER/'chunk-00',3500)!=body: raise ValueError('chunk readback differs')
print('OBSERVER CHUNK 00 VERIFIED',flush=True)
