import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'resume2-process-observer-transfer'
INSTALL=BASE/'resume2-process-observer-install.json'
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
 for path in [INSTALL,BASE/'ios26-saved-inspection-resume2-observer',BASE/'ios26-saved-inspection-resume2-observer-launch.json',BASE/'ios26-saved-inspection-resume2-observer-wrapper.log']+[BASE/row['path'] for row in files]:
  if os.path.lexists(path): raise ValueError('fresh observer path required; preserve '+str(path))
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
mb=read(TRANSFER/'manifest.json',1647)
if hashlib.sha256(mb).hexdigest()!='dc136f8dd85dc2e8cdfdb00f8134d5d92ed132299a280e3999838acd398fe7cf': raise ValueError('manifest differs')
m=json.loads(mb)
body=b'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'
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='86b46c6e72e7af590f4b25a611a10830dbfaf883be3e0edc0d0b0226eadc70ba': raise ValueError('chunk differs')
save(TRANSFER/'chunk-03',body)
if read(TRANSFER/'chunk-03',3500)!=body: raise ValueError('chunk readback differs')
print('OBSERVER CHUNK 03 VERIFIED',flush=True)
