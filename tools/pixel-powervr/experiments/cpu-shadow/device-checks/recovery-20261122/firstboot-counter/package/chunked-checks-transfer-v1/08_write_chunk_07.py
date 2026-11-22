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
if TRANSFER.resolve(strict=True)!=TRANSFER: raise ValueError('noncanonical transfer directory')
manifest=read(TRANSFER/'manifest.json',1640)
if hashlib.sha256(manifest).hexdigest()!=MANIFEST_SHA: raise ValueError('transfer manifest differs')
body='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'.encode('ascii')
if len(body)!=2164 or hashlib.sha256(body).hexdigest()!='5efed4c21ec28cfecaea40a95d2bbbfed9f16314aefcdc78770102a584378462': raise ValueError('chunk payload differs')
target=TRANSFER/'chunk-07.b64'
save(target,body)
if read(target,2164)!=body: raise ValueError('chunk readback differs')
print('CHUNK VERIFIED 8/8 bytes=2164 sha256=5efed4c21ec28cfecaea40a95d2bbbfed9f16314aefcdc78770102a584378462',flush=True)
