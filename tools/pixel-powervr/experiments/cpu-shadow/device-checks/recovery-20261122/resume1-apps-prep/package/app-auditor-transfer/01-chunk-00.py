import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'resume1-apps-auditor-transfer'
DEST=Path('/data/local/tmp/pixel-app-checks-counter1-resume1')
INSTALL=BASE/'resume1-apps-auditor-install.json'
def read(path,limit):
 if path.resolve(strict=True)!=path: raise ValueError('noncanonical transfer/source path')
 with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
  info=os.fstat(f.fileno())
  if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_uid!=0 or info.st_size>limit: raise ValueError('invalid bounded root-owned file')
  body=f.read(limit+1)
 if len(body)>limit: raise ValueError('input exceeded bound')
 return body
def save(path,body,mode=0o600):
 with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode),'wb') as f:
  os.fchmod(f.fileno(),mode);f.write(body);f.flush();os.fsync(f.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try: os.fsync(fd)
 finally: os.close(fd)
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
if TRANSFER.resolve(strict=True)!=TRANSFER: raise ValueError('transfer path differs')
mb=read(TRANSFER/'manifest.json',2896)
if hashlib.sha256(mb).hexdigest()!='6f8fa424f05e409e0e349885b0390684744ddd45fbf0b08f9347a8cff8f00eba': raise ValueError('manifest differs')
body=b'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'
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='c88edb712d0a0d56b38c1937652dd65e4b5640c8ee20fed8092a64aae7e228b4': raise ValueError('chunk differs')
save(TRANSFER/'chunk-00',body)
if read(TRANSFER/'chunk-00',3500)!=body: raise ValueError('chunk readback differs')
print('APPS AUDITOR CHUNK 00 VERIFIED',flush=True)
