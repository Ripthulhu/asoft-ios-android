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
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='bad428da35ad67b37d87ee85fbae532637c8ed89b0bde0b9695d294d53c93c9c': raise ValueError('chunk differs')
save(TRANSFER/'chunk-00',body)
if read(TRANSFER/'chunk-00',3500)!=body: raise ValueError('chunk readback differs')
print('DATA JOURNAL DIAGNOSTIC CHUNK 00 VERIFIED',flush=True)
