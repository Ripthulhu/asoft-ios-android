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
SOURCE=BASE/'run-ios26-root-jib-diagnostic-resume4.py'
OUT=BASE/'ios26-root-jib-diagnostic-resume4'
if os.path.lexists(OUT): raise ValueError('preserve existing diagnostic output')
mb=read(TRANSFER/'manifest.json',1227)
if len(mb)!=1227 or hashlib.sha256(mb).hexdigest()!='fd168adace896ed166cfbba7e770f0ff9623b8f6659cad9de3c97f5584bcd5c6': raise ValueError('installed transfer manifest differs')
installation=json.loads(read(BASE/'root-jib-diagnostic-resume4-install.json',65536))
if installation.get('schema')!=1 or installation.get('kind')!='root_jib_diagnostic_resume4_sources_install' or installation.get('execution_started') is not False or installation.get('files')!=[{'path': 'run-ios26-root-jib-diagnostic-resume4.py', 'bytes': 41544, 'sha256': 'cf31bf3489bed645dbd59f8e024f6759150f9262f1480e6d9d4ff53f855b9480'}] or installation.get('manifest_sha256')!='fd168adace896ed166cfbba7e770f0ff9623b8f6659cad9de3c97f5584bcd5c6': raise ValueError('source installation receipt differs')
body=read(SOURCE,41544)
if len(body)!=41544 or hashlib.sha256(body).hexdigest()!='cf31bf3489bed645dbd59f8e024f6759150f9262f1480e6d9d4ff53f855b9480': raise ValueError('diagnostic source bytes differ')
exec(compile(body,str(SOURCE),'exec'),{'__name__':'__main__','__file__':str(SOURCE)})
