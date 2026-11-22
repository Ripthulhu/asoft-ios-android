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
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='7dc95a7fed07f109bf2e2306c8c30dbcdfed3cc0e632a8f3a497ff04543dc0a3': raise ValueError('chunk differs')
save(TRANSFER/'chunk-02',body)
if read(TRANSFER/'chunk-02',3500)!=body: raise ValueError('chunk readback differs')
print('OBSERVER CHUNK 02 VERIFIED',flush=True)
