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
if len(body)!=2424 or hashlib.sha256(body).hexdigest()!='563f958fe04e6b76f4cc259534313783f08a7250db8a952b79cb69e98a88f088': raise ValueError('chunk differs')
save(TRANSFER/'chunk-06',body)
if read(TRANSFER/'chunk-06',2424)!=body: raise ValueError('chunk readback differs')
print('DATA JOURNAL DIAGNOSTIC CHUNK 06 VERIFIED',flush=True)
