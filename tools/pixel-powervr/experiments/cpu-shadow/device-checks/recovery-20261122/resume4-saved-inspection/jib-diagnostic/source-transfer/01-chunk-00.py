import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'root-jib-diagnostic-resume4-transfer'
def read(path,limit):
 if path.resolve(strict=True)!=path: raise ValueError('noncanonical transfer path')
 with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
  a=os.fstat(f.fileno())
  if not stat.S_ISREG(a.st_mode) or a.st_nlink!=1 or a.st_uid!=0 or a.st_size>limit: raise ValueError('invalid transfer file')
  b=f.read(limit+1);z=os.fstat(f.fileno())
 if len(b)!=a.st_size or len(b)>limit or (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)!=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns): raise ValueError('transfer input changed or exceeded bound')
 return b
def save(path,body,mode=0o600):
 with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode),'wb') as f:
  f.write(body);f.flush();os.fsync(f.fileno())
 d=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try: os.fsync(d)
 finally: os.close(d)
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
if TRANSFER.resolve(strict=True)!=TRANSFER: raise ValueError('transfer directory differs')
mb=read(TRANSFER/'manifest.json',1227)
if len(mb)!=1227 or hashlib.sha256(mb).hexdigest()!='fd168adace896ed166cfbba7e770f0ff9623b8f6659cad9de3c97f5584bcd5c6': raise ValueError('manifest differs')
body=b'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'
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='0087c9b1fb658269c8ac4ae2a33d5dc62d4fb0414a199db0220c2b43f58eef7b': raise ValueError('chunk differs')
save(TRANSFER/'chunk-00',body)
if read(TRANSFER/'chunk-00',3500)!=body: raise ValueError('chunk readback differs')
print('ROOT JIB DIAGNOSTIC CHUNK 00 VERIFIED',flush=True)
