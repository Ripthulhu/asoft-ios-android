import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'saved-inspection-resume3-transfer'
TARGET=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
INSTALL=BASE/'saved-inspection-resume3-install.json'
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
if hashlib.sha256(mb).hexdigest()!='60fa31ca711f5c10b3e01910fb5b3e6a255b681cb3031a377b889943288461b8': raise ValueError('manifest differs')
body=b'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'
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='beaa5274c01638a078fa062580c43c538e231ebdba3ae9d25fbdd2951fb9b9cf': raise ValueError('chunk differs')
save(TRANSFER/'chunk-02',body)
if read(TRANSFER/'chunk-02',3500)!=body: raise ValueError('chunk readback differs')
print('SOURCE CHUNK 02 VERIFIED',flush=True)
