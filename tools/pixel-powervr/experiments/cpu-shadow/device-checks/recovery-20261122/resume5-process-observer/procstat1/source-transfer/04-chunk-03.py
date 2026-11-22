import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'resume5-process-observer-procstat1-transfer'
INSTALL=BASE/'resume5-process-observer-procstat1-install.json'
OWNER_SOURCE=BASE/'run-ios26-saved-inspection-resume5.py'
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
 for path in [INSTALL,BASE/'ios26-saved-inspection-resume5-observer-procstat1',BASE/'ios26-saved-inspection-resume5-observer-procstat1-launch.json',BASE/'ios26-saved-inspection-resume5-observer-procstat1-wrapper.log']+[BASE/row['path'] for row in files]:
  if os.path.lexists(path): raise ValueError('fresh observer path required; preserve '+str(path))
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
mb=read(TRANSFER/'manifest.json',1678)
if hashlib.sha256(mb).hexdigest()!='a899909aca777e0f3e77e46059ce454cda0e731499adc7e94262522f842a2ede': raise ValueError('manifest differs')
m=json.loads(mb)
body=b'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'
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='6349d6b433204a4af3dce21bebb76db14616db8c8c5dec5e60478ac4201460b1': raise ValueError('chunk differs')
save(TRANSFER/'chunk-03',body)
if read(TRANSFER/'chunk-03',3500)!=body: raise ValueError('chunk readback differs')
print('OBSERVER CHUNK 03 VERIFIED',flush=True)
