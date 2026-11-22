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
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='cdde90a058001dcec3234ab58a420abe63805db5ba0080cc402fad7a15ff30ac': raise ValueError('chunk differs')
save(TRANSFER/'chunk-02',body)
if read(TRANSFER/'chunk-02',3500)!=body: raise ValueError('chunk readback differs')
print('OBSERVER CHUNK 02 VERIFIED',flush=True)
