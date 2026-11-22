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
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='ad28e8d235d8c5356aad933a39b96bbd5a02ac6b65f1292238da457168a36623': raise ValueError('chunk differs')
save(TRANSFER/'chunk-03',body)
if read(TRANSFER/'chunk-03',3500)!=body: raise ValueError('chunk readback differs')
print('SOURCE CHUNK 03 VERIFIED',flush=True)
