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
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='ece524b64d71e844842a5e901a112bd6349f90ced40d828187c354c4b01037a2': raise ValueError('chunk differs')
save(TRANSFER/'chunk-01',body)
if read(TRANSFER/'chunk-01',3500)!=body: raise ValueError('chunk readback differs')
print('DATA JOURNAL DIAGNOSTIC CHUNK 01 VERIFIED',flush=True)
