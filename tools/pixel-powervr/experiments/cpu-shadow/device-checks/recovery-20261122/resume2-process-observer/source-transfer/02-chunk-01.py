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
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='77ca4773cf27ee73a2691df0f33e921b4799528c1f40fda5109e82f58880dfe5': raise ValueError('chunk differs')
save(TRANSFER/'chunk-01',body)
if read(TRANSFER/'chunk-01',3500)!=body: raise ValueError('chunk readback differs')
print('OBSERVER CHUNK 01 VERIFIED',flush=True)
