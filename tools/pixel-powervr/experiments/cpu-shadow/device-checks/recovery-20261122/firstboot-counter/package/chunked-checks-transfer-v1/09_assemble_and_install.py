import datetime,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'counter1-checks-installer-transfer-v1'
MANIFEST_SHA='64549f3cbf4c09ba2cb6cd269e72e9d4f64935b5f9216d8935b6cbfdf0d28394'
def read(path,limit):
 if path.resolve(strict=True)!=path: raise ValueError('noncanonical transfer artifact')
 with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as source:
  info=os.fstat(source.fileno())
  if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_uid!=0 or info.st_size>limit: raise ValueError('nonordinary transfer artifact')
  body=source.read(limit+1)
 if len(body)>limit: raise ValueError('transfer artifact exceeded bound')
 return body
def save(path,body):
 with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as output:
  output.write(body);output.flush();os.fsync(output.fileno())
 directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try: os.fsync(directory)
 finally: os.close(directory)
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
import base64,gzip,io
if TRANSFER.resolve(strict=True)!=TRANSFER: raise ValueError('noncanonical transfer directory')
manifest_body=read(TRANSFER/'manifest.json',1640)
if hashlib.sha256(manifest_body).hexdigest()!=MANIFEST_SHA: raise ValueError('transfer manifest differs')
manifest=json.loads(manifest_body)
if {p.name for p in TRANSFER.iterdir()}!={'manifest.json',*(row['name'] for row in manifest['chunks'])}: raise ValueError('unknown or previously assembled transfer artifacts; preserve all')
chunks=[]
for row in manifest['chunks']:
 body=read(TRANSFER/row['name'],row['bytes'])
 if len(body)!=row['bytes'] or hashlib.sha256(body).hexdigest()!=row['sha256']: raise ValueError('stored chunk differs')
 chunks.append(body)
encoded=b''.join(chunks)
if len(encoded)!=manifest['encoded_bytes'] or hashlib.sha256(encoded).hexdigest()!=manifest['encoded_sha256']: raise ValueError('complete encoded payload differs')
with gzip.GzipFile(fileobj=io.BytesIO(base64.b64decode(encoded,validate=True)),mode='rb') as source: installer=source.read(31390)
if len(installer)!=31389 or hashlib.sha256(installer).hexdigest()!='3f2811db3507908a02c79e86ccfb28d248163a0c03267657d12ed110424a41a3': raise ValueError('reviewed installer bytes differ')
source_path=TRANSFER/'reviewed-installer.py'
save(source_path,installer)
if read(source_path,31389)!=installer: raise ValueError('assembled installer readback differs')
started=datetime.datetime.now(datetime.timezone.utc).isoformat()
reservation={'schema':1,'kind':'exact_reviewed_installer_execution_reservation','started_utc':started,'pid':os.getpid(),'manifest_sha256':MANIFEST_SHA,'installer_bytes':len(installer),'installer_sha256':'3f2811db3507908a02c79e86ccfb28d248163a0c03267657d12ed110424a41a3','source':str(source_path),'execution_requested':True}
save(TRANSFER/'execute.json',(json.dumps(reservation,indent=2)+'\n').encode())
error=None
try:
 namespace={'__name__':'__main__','__file__':'install_counter1_checks.py'}
 exec(compile(installer,'install_counter1_checks.py','exec'),namespace)
except BaseException as exc: error=type(exc).__name__+': '+str(exc)
finally:
 ended={**reservation,'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'installer_returned':error is None,'error':error}
 save(TRANSFER/'execution-exit.json',(json.dumps(ended,indent=2)+'\n').encode())
print('EXACT INSTALLER RETURNED' if error is None else 'INSTALLER INCOMPLETE '+error,flush=True)
raise SystemExit(0 if error is None else 2)
