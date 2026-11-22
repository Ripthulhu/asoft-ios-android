import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'data-journal-diagnostic-resume5-transfer'
def read(path,limit):
 if path.resolve(strict=True)!=path: raise ValueError('noncanonical transfer path')
 with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
  a=os.fstat(f.fileno())
  if not stat.S_ISREG(a.st_mode) or a.st_nlink!=1 or a.st_uid!=0 or a.st_size>limit: raise ValueError('invalid transfer file')
  b=f.read(limit+1);z=os.fstat(f.fileno())
 if len(b)!=a.st_size or len(b)>limit or (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)!=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns): raise ValueError('transfer input changed or exceeded bound')
 return b
def save(path,body,mode=0o600):
 with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode),'wb') as f:
  f.write(body);f.flush();os.fsync(f.fileno())
 d=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try: os.fsync(d)
 finally: os.close(d)
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
if TRANSFER.resolve(strict=True)!=TRANSFER: raise ValueError('transfer directory differs')
mb=read(TRANSFER/'manifest.json',1692)
if len(mb)!=1692 or hashlib.sha256(mb).hexdigest()!='fb21a4782fa6f5bf04edac463df6cf6a2a6767102d969135085d53128d45d65d': raise ValueError('manifest differs')
body=b'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'
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='26bc9ed8829b0b80e46c599956ac137066c81f47e82804087cdde786231dfa2c': raise ValueError('chunk differs')
save(TRANSFER/'chunk-05',body)
if read(TRANSFER/'chunk-05',3500)!=body: raise ValueError('chunk readback differs')
print('DATA JOURNAL DIAGNOSTIC CHUNK 05 VERIFIED',flush=True)
