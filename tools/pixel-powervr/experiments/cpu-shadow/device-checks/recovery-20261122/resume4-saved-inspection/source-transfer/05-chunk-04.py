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
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='041043e5d6adcbfb96b580b9de29b869965cf52a636c98cfcc447742ec2a3127': raise ValueError('chunk differs')
save(TRANSFER/'chunk-04',body)
if read(TRANSFER/'chunk-04',3500)!=body: raise ValueError('chunk readback differs')
print('SOURCE CHUNK 04 VERIFIED',flush=True)
