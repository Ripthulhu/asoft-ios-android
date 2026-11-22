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
mb=read(TRANSFER/'manifest.json',1647)
if hashlib.sha256(mb).hexdigest()!='dc136f8dd85dc2e8cdfdb00f8134d5d92ed132299a280e3999838acd398fe7cf': raise ValueError('manifest differs')
m=json.loads(mb)
body=b'NboRsgnfn52+Pjo/j5Tjj6n26E34tJwLBZy9hVMhQB/vL7QLcc2vXXi/VSGXso7RuNMKi/iihsal7vin4L3UrFXNNMrAZVrrjDs0FCVyOSZge9v6bSkeakpWJMGkKZIlrYd2gZd83m05bMpj2xFD9QJ5eDKa3GTkxujMb1rydzm9DRo5JPZXJlutfMWeDabHdzZ63Atvjs+OXl+cnv2+9QYrNaqC3XXyepaeLhw0cbuoYANh6/9HGpqRBqlvCWv96fEGbzxBkaciy+1e/YHFSTVz2sqdOJVk9EeHPYRqKKIf0akdcd8a0vhnhEmkKyAiHwNmOICUyzCjoXrwao3/uljKwfBwpEIpogz366Ipg4PF6DAdvBzM57PRy9lotnc4iA8O0uTg4OVgNBwNZ3v78+Ho5XwQD56/gDfJcPA8PXgx2N+DZ8P5sy/T3jM0FzCm84BNi+OSlfFsPPzyL/8Xmfm2ljahAAA='
if len(body)!=480 or hashlib.sha256(body).hexdigest()!='561fa260d6c24425c074ab8fcfcdd3bad50511806c7b118508b64e13ebb8ddb5': raise ValueError('chunk differs')
save(TRANSFER/'chunk-04',body)
if read(TRANSFER/'chunk-04',480)!=body: raise ValueError('chunk readback differs')
print('OBSERVER CHUNK 04 VERIFIED',flush=True)
