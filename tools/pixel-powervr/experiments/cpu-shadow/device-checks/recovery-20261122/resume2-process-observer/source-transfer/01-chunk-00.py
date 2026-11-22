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
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='56e282225b8c007fa4384fa83ebef7acc77e5ebf9afe1f62d6341cccdabf7993': raise ValueError('chunk differs')
save(TRANSFER/'chunk-00',body)
if read(TRANSFER/'chunk-00',3500)!=body: raise ValueError('chunk readback differs')
print('OBSERVER CHUNK 00 VERIFIED',flush=True)
