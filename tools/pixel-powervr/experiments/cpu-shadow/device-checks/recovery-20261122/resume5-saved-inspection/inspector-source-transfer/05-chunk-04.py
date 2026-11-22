import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'saved-inspector-resume5-transfer'
TARGET=Path('/data/local/tmp/pixel-saved-checks-resume5')
INSTALL=BASE/'saved-inspector-resume5-install.json'
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
if hashlib.sha256(mb).hexdigest()!='c4cb64bb0d5b7ae281b2bd54b755db3231b8870abc4de54b45841e09fc591efd': raise ValueError('manifest differs')
body=b'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'
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='690e14c394db95badcec0bfb3ba0f9bd6da2bb132838b44b03fd2de22584dbe1': raise ValueError('chunk differs')
save(TRANSFER/'chunk-04',body)
if read(TRANSFER/'chunk-04',3500)!=body: raise ValueError('chunk readback differs')
print('SOURCE CHUNK 04 VERIFIED',flush=True)
