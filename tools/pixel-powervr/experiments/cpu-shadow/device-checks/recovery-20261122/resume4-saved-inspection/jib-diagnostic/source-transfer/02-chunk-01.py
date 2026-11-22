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
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='37543653973f30eafa73a81ffcb67b96bab1e256adbc87b6960ad3f400514812': raise ValueError('chunk differs')
save(TRANSFER/'chunk-01',body)
if read(TRANSFER/'chunk-01',3500)!=body: raise ValueError('chunk readback differs')
print('ROOT JIB DIAGNOSTIC CHUNK 01 VERIFIED',flush=True)
