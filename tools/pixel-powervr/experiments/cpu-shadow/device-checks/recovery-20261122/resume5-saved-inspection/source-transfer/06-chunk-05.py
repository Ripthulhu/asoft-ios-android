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
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='029c98627cd380eb62c74b4885a19d9f37b64e68ffd9492c78a58d3c5a84eec8': raise ValueError('chunk differs')
save(TRANSFER/'chunk-05',body)
if read(TRANSFER/'chunk-05',3500)!=body: raise ValueError('chunk readback differs')
print('SOURCE CHUNK 05 VERIFIED',flush=True)
