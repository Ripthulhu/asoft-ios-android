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
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='b677b2cd4ec2c17d3ba8edfa55631fc84ae0e7cc274a0caa69e95f7496598ece': raise ValueError('chunk differs')
save(TRANSFER/'chunk-00',body)
if read(TRANSFER/'chunk-00',3500)!=body: raise ValueError('chunk readback differs')
print('OBSERVER CHUNK 00 VERIFIED',flush=True)
