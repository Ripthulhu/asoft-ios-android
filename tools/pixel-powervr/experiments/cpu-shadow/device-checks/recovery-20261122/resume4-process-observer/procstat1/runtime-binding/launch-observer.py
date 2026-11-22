import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'resume4-process-observer-procstat1-transfer'
INSTALL=BASE/'resume4-process-observer-procstat1-install.json'
OWNER_SOURCE=BASE/'run-ios26-saved-inspection-resume4.py'
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
 for path in [INSTALL,BASE/'ios26-saved-inspection-resume4-observer-procstat1',BASE/'ios26-saved-inspection-resume4-observer-procstat1-launch.json',BASE/'ios26-saved-inspection-resume4-observer-procstat1-wrapper.log']+[BASE/row['path'] for row in files]:
  if os.path.lexists(path): raise ValueError('fresh observer path required; preserve '+str(path))
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
p=BASE/'launch-ios26-saved-inspection-resume4-observer-procstat1.py'
b=read(p,6252)
if len(b)!=6252 or hashlib.sha256(b).hexdigest()!='f082680cd7f9bb6cf1ae3c8e8debd0d9b347f6d1338597c52c23ea63bf3afadf': raise ValueError('launcher source differs')
import sys
sys.argv=[str(p),'--preflight-sha256','d68aa23ba833c8939ace08005c573f11764c104bbbae29a5f0285677c7239bf6','--preflight-bytes','9069']
exec(compile(b,str(p),'exec'),{'__name__':'__main__','__file__':str(p)})
