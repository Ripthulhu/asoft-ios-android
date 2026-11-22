import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'saved-inspector-resume3-transfer'
TARGET=Path('/data/local/tmp/pixel-saved-checks-resume3')
INSTALL=BASE/'saved-inspector-resume3-install.json'
def read(path,limit):
 if path.resolve(strict=True)!=path: raise ValueError('noncanonical transfer path')
 with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
  a=os.fstat(f.fileno())
  if not stat.S_ISREG(a.st_mode) or a.st_nlink!=1 or a.st_uid!=0 or a.st_size>limit: raise ValueError('invalid transfer input')
  b=f.read(limit+1)
  z=os.fstat(f.fileno())
 if len(b)!=a.st_size or len(b)>limit or (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)!=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns): raise ValueError('transfer input changed')
 return b
def save(path,body,mode=0o600):
 with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode),'wb') as f:
  f.write(body);f.flush();os.fsync(f.fileno())
 d=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try: os.fsync(d)
 finally: os.close(d)
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
if TRANSFER.resolve(strict=True)!=TRANSFER: raise ValueError('transfer directory differs')
mb=read(TRANSFER/'manifest.json',1622)
if hashlib.sha256(mb).hexdigest()!='95faa2f0adc715771bf6b35c7cf7601913206974e0a21db6476e472d48f35933': raise ValueError('manifest differs')
body=b'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'
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='84d91cfb5cae42c326502bb6beab5b77a470e5c593ced4381408e1e98c3d3f75': raise ValueError('chunk differs')
save(TRANSFER/'chunk-02',body)
if read(TRANSFER/'chunk-02',3500)!=body: raise ValueError('chunk readback differs')
print('SOURCE CHUNK 02 VERIFIED',flush=True)
