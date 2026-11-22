import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'saved-inspection-resume5-transfer'
TARGET=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
INSTALL=BASE/'saved-inspection-resume5-install.json'
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
mb=read(TRANSFER/'manifest.json',1796)
if hashlib.sha256(mb).hexdigest()!='d33bd545f82981ea899a1282756a327a26926a29d2f2eb744d25629d43a4bd0c': raise ValueError('manifest differs')
body=b'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'
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='651ab2b61366e4a3dc0cdc17d5161d2443ee5a2369c9e1875faa295ad629216b': raise ValueError('chunk differs')
save(TRANSFER/'chunk-03',body)
if read(TRANSFER/'chunk-03',3500)!=body: raise ValueError('chunk readback differs')
print('SOURCE CHUNK 03 VERIFIED',flush=True)
