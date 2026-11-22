import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'hfs-header-diagnostic-resume2-transfer'
def read(path,limit):
 if path.resolve(strict=True)!=path: raise ValueError('noncanonical transfer path')
 with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
  s=os.fstat(f.fileno())
  if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_uid!=0 or s.st_size>limit: raise ValueError('invalid transfer file')
  b=f.read(limit+1)
 if len(b)>limit: raise ValueError('transfer input exceeded bound')
 return b
def save(path,body,mode=0o600):
 with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode),'wb') as f:
  f.write(body);f.flush();os.fsync(f.fileno())
 d=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try: os.fsync(d)
 finally: os.close(d)
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
if TRANSFER.resolve(strict=True)!=TRANSFER: raise ValueError('transfer directory differs')
mb=read(TRANSFER/'manifest.json',944)
if hashlib.sha256(mb).hexdigest()!='02089c6f06b3d9b8f665ecd6500f53c1e8d8d44f01f7c21d389e248fd334739f': raise ValueError('manifest differs')
body=b'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'
if len(body)!=2536 or hashlib.sha256(body).hexdigest()!='e16eed94e433c9c280cddab8a2e95579a8b7cd7fce5fc7c8e6cffcd33347e6cd': raise ValueError('chunk differs')
save(TRANSFER/'chunk-02',body)
if read(TRANSFER/'chunk-02',2536)!=body: raise ValueError('chunk readback differs')
print('HFS HEADER DIAGNOSTIC CHUNK 02 VERIFIED',flush=True)
