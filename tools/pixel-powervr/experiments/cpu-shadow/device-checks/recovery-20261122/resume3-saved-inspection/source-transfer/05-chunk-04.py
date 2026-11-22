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
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='56d70b743006f1f7107135f88b4a03173b2e8b0ffdd757c0014a3923f5bfa7ec': raise ValueError('chunk differs')
save(TRANSFER/'chunk-04',body)
if read(TRANSFER/'chunk-04',3500)!=body: raise ValueError('chunk readback differs')
print('SOURCE CHUNK 04 VERIFIED',flush=True)
