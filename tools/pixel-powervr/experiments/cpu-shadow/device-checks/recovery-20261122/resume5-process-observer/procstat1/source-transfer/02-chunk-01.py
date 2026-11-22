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
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='71fe10649b6812c0491975c5f49c25fbc43f1cfa6f22d05f81280b8aec5459f0': raise ValueError('chunk differs')
save(TRANSFER/'chunk-01',body)
if read(TRANSFER/'chunk-01',3500)!=body: raise ValueError('chunk readback differs')
print('OBSERVER CHUNK 01 VERIFIED',flush=True)
