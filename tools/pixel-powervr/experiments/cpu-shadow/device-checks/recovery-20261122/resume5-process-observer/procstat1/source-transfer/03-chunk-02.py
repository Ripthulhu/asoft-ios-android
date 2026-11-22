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
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='ba560128d42add2cfb00caa9a07bb690e5099c9b3e26a7e56e5276ba6b5383d7': raise ValueError('chunk differs')
save(TRANSFER/'chunk-02',body)
if read(TRANSFER/'chunk-02',3500)!=body: raise ValueError('chunk readback differs')
print('OBSERVER CHUNK 02 VERIFIED',flush=True)
