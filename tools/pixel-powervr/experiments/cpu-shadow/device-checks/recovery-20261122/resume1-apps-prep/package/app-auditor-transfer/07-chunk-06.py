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
body=b'zGBumYPxlzLAGY/o7ns1+KXGFR8lVN1zU0X4S09B2HgdwUXZUMRrb96QYhElTZNUCLcpcHXS06eoOOWsr1K6MfZYxofUoZROa2IDf23kvpSYpUJM9Irvqy8cIQ9ltjcf6+a88UfF0uyJ6/aD3s/rCH2u8vrx0FRDOcZSOqKGFrhrgjwsweQ4udonYzJDUSek/IuF62PEaGvQFRWAX/bB1VNuHT7jtr7GzJp7X474lvc/xGWjYu3qk3ffaXX9TLJF9KEtwp2bTpJwub2v8V8Cbvp7XCpnDCpqfl3HRsAAjwF/vdgD2PtyxlGgba99CY5PjbT1+jKTvzT3ZR43ja5MY5EawlFhPqV5FEeR+Qz75tVbQ3s8Ej1azAphViYZdSftYQLszLakMofEVzt616umZpO6dCb+QXPySWnMLdIVeerVcUb78olpAuiYktT+4qZyP6QXwHk5lE5KdGpj/KKbd1++RldRsx+YdWC720gFSwJnH0N3pXblX7Ik3ElV/0RPCXhJvuQCjuR/SWJRiTU9M7i6qWNyjxk/QQ5xfKTItuaADueKD6w/IbXnrFEvhjbbWSkzgNQ+ZLO3/W7Nbf0ZXQytZl6a+oSWy/9OanNMNFzVwsGXdyqD5lbFyqN9sDS6/ir/lA0GmgC3r5D6/CKKqfqriuF2kFr+oBaB069WtV1/ksquuhew9oyWJCq/bsx876ECYXLUg17+J532P0l06Bmimgd/9POrImzGTTooXCVJkU+RGKyyY1u36SikYvzdJICVF15DjEJUawZS6o7CR+kZgfav9PMWL13Mbg+ry2TcGECpI3u4MdzLFHsTCrumETGCiogG8r5Q3mCXSVWDIhzIF6nZ0pBQXameMpLuV1TovJejnsnZbErTuqtDpqRFNuSlFVeB+KU4JfFbvM03xYcX2vi+zl13IkxuOX2nFeBaTfW97r1km9ip94KNp/R4QfX4LJc/A5/FqDFKVuOKPRXFQ2PSXcp2H/JLe1riNM6HnLcN0V0OBXORFeWWnjmoh6mcW47xsdm/V+xU87V85rc9fMMOMBY/SpyBktAO8qHyPWFxSj3v0rhZ/dU7NSqJvxH25HgpqgSnhlWA4Tp0T+lG7dcXWdkpaIWRGoYf0akILtcXNx/e3vJ7P1XK2ApIHzo1nvhTb+wEfwiugcGBixRXDviyMtg+Fvnu4ZEeh+EXW/6jDMRjpfy2DL6YjMLWOl22/5mP6vQG5+Oz2kd1GIudp3WiNB0nvU4/jrudRRL3orNhct6fp8l577yfjEbD8bh73km7UCNJ5sPOWa9z3hvEg1E06MfjePjqZdYiNy6AhSu3SruhfhkLzpR4Whv7JBx9Nem+/I//Byae9if89AAA'
if len(body)!=1368 or hashlib.sha256(body).hexdigest()!='dfc8e266987f04ad3db3b4686963900793f38499418e3e2e3292d303c9ca9d13': raise ValueError('chunk differs')
save(TRANSFER/'chunk-06',body)
if read(TRANSFER/'chunk-06',1368)!=body: raise ValueError('chunk readback differs')
print('APPS AUDITOR CHUNK 06 VERIFIED',flush=True)
