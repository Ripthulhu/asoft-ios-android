import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'saved-inspection-resume4-transfer'
TARGET=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
INSTALL=BASE/'saved-inspection-resume4-install.json'
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
mb=read(TRANSFER/'manifest.json',1653)
if hashlib.sha256(mb).hexdigest()!='3e13577d266ddc922a1ca378852ed18b305033faf4263cf40989fe860a7fe969': raise ValueError('manifest differs')
body=b'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'
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='3cdc2368071607e9899d7478de95eed83d571bea88e2f4f723e8ae98215d8704': raise ValueError('chunk differs')
save(TRANSFER/'chunk-03',body)
if read(TRANSFER/'chunk-03',3500)!=body: raise ValueError('chunk readback differs')
print('SOURCE CHUNK 03 VERIFIED',flush=True)
