import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'data-journal-diagnostic-resume5-transfer'
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
SOURCE=BASE/'run-ios26-data-journal-diagnostic-resume5.py'
OUT=BASE/'ios26-data-journal-diagnostic-resume5'
if os.path.lexists(OUT): raise ValueError('preserve existing diagnostic output')
mb=read(TRANSFER/'manifest.json',1692)
if len(mb)!=1692 or hashlib.sha256(mb).hexdigest()!='fb21a4782fa6f5bf04edac463df6cf6a2a6767102d969135085d53128d45d65d': raise ValueError('installed transfer manifest differs')
installation=json.loads(read(BASE/'data-journal-diagnostic-resume5-install.json',65536))
if installation.get('schema')!=1 or installation.get('kind')!='data_journal_diagnostic_resume5_sources_install' or installation.get('execution_started') is not False or installation.get('files')!=[{'path': 'run-ios26-data-journal-diagnostic-resume5.py', 'bytes': 51923, 'sha256': '85194af9e14f68e16d1990e79603060644a892c772adafc51dc52777055c77c9'}, {'path': 'parse-ios26-data-journal-resume5.py', 'bytes': 14617, 'sha256': '4036055b490f5fd93a74e6d12de12f511de45e8e0f62dfa81419151fc2dcc852'}] or installation.get('manifest_sha256')!='fb21a4782fa6f5bf04edac463df6cf6a2a6767102d969135085d53128d45d65d': raise ValueError('source installation receipt differs')
for row in installation['files']:
 b=read(BASE/row['path'],row['bytes'])
 if len(b)!=row['bytes'] or hashlib.sha256(b).hexdigest()!=row['sha256']: raise ValueError('installed source pair differs')
body=read(SOURCE,51923)
if len(body)!=51923 or hashlib.sha256(body).hexdigest()!='85194af9e14f68e16d1990e79603060644a892c772adafc51dc52777055c77c9': raise ValueError('diagnostic source bytes differ')
exec(compile(body,str(SOURCE),'exec'),{'__name__':'__main__','__file__':str(SOURCE)})
