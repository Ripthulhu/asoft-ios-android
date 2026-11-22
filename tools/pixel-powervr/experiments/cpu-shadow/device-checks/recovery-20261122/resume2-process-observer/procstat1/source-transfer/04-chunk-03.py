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
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='3904346b8a28f8e99e46da908f2ac818c5f3b045b933e20692c7962aec528fd2': raise ValueError('chunk differs')
save(TRANSFER/'chunk-03',body)
if read(TRANSFER/'chunk-03',3500)!=body: raise ValueError('chunk readback differs')
print('OBSERVER CHUNK 03 VERIFIED',flush=True)
