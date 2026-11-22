import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'resume2-process-observer-transfer'
INSTALL=BASE/'resume2-process-observer-install.json'
OWNER_SOURCE=BASE/'run-ios26-saved-inspection-resume2.py'
def read(path,limit):
 if path.resolve(strict=True)!=path: raise ValueError('noncanonical input')
 with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
  a=os.fstat(f.fileno())
  if not stat.S_ISREG(a.st_mode) or a.st_uid!=0 or a.st_nlink!=1 or a.st_size>limit: raise ValueError('invalid bounded root-owned file')
  body=f.read(limit+1);b=os.fstat(f.fileno())
 if len(body)!=a.st_size or (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)!=(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns,b.st_ctime_ns): raise ValueError('input changed during read')
 return body
def save(path,body,mode=0o600):
 with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode),'wb') as f:
  os.fchmod(f.fileno(),mode);f.write(body);f.flush();os.fsync(f.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try: os.fsync(fd)
 finally: os.close(fd)
def fresh(files):
 for path in [INSTALL,BASE/'ios26-saved-inspection-resume2-observer',BASE/'ios26-saved-inspection-resume2-observer-launch.json',BASE/'ios26-saved-inspection-resume2-observer-wrapper.log']+[BASE/row['path'] for row in files]:
  if os.path.lexists(path): raise ValueError('fresh observer path required; preserve '+str(path))
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
p=BASE/'launch-ios26-saved-inspection-resume2-observer.py'
b=read(p,6192)
if len(b)!=6192 or hashlib.sha256(b).hexdigest()!='06f29e080ccb28b2b390a66ed66802121b34c128c0a057a66d105e670438c01c': raise ValueError('launcher source differs')
import sys
sys.argv=[str(p),'--preflight-sha256','84b31f4f08744f6adeb20ab5af308b1d10c839803c051d4bba577201a4ad3760','--preflight-bytes','9070']
exec(compile(b,str(p),'exec'),{'__name__':'__main__','__file__':str(p)})
