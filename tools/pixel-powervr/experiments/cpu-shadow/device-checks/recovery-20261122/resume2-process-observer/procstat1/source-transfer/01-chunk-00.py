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
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='64fed589f485c90ee30abc2a65b3f49c99f8dfb4f2ace8cca6acb9635e80ae50': raise ValueError('chunk differs')
save(TRANSFER/'chunk-00',body)
if read(TRANSFER/'chunk-00',3500)!=body: raise ValueError('chunk readback differs')
print('OBSERVER CHUNK 00 VERIFIED',flush=True)
