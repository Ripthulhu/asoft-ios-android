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
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='914373bf03b1f79c9cde67403490720023c050646da68c0024533c74366fad45': raise ValueError('chunk differs')
save(TRANSFER/'chunk-02',body)
if read(TRANSFER/'chunk-02',3500)!=body: raise ValueError('chunk readback differs')
print('SOURCE CHUNK 02 VERIFIED',flush=True)
