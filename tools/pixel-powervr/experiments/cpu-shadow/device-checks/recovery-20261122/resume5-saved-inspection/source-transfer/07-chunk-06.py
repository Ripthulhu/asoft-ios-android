import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'saved-inspection-resume5-transfer'
TARGET=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
INSTALL=BASE/'saved-inspection-resume5-install.json'
def read(path,limit):
 if path.resolve(strict=True)!=path: raise ValueError('noncanonical transfer path')
 with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
  a=os.fstat(f.fileno())
  if not stat.S_ISREG(a.st_mode) or a.st_nlink!=1 or a.st_uid!=0 or a.st_size>limit: raise ValueError('invalid transfer input')
  b=f.read(limit+1)
  z=os.fstat(f.fileno())
 if len(b)!=a.st_size or len(b)>limit or (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)!=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns): raise ValueError('transfer input changed')
 return b
def save(path,body,mode=0o600):
 with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode),'wb') as f:
  f.write(body);f.flush();os.fsync(f.fileno())
 d=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try: os.fsync(d)
 finally: os.close(d)
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
if TRANSFER.resolve(strict=True)!=TRANSFER: raise ValueError('transfer directory differs')
mb=read(TRANSFER/'manifest.json',1796)
if hashlib.sha256(mb).hexdigest()!='d33bd545f82981ea899a1282756a327a26926a29d2f2eb744d25629d43a4bd0c': raise ValueError('manifest differs')
body=b'GmAoBIqxAwLB2JHpAXnk55FBWNop/ThhsBKXn4DOnvBKcrYlLP5KN4wQnrZSzElL+WejORLWwsojMWRs4J1RUXq/pMA4EaL6UJSNJlfskwypNwmILMf9MDB6udK7bUoFOm3dISm1MWrijJGZtEYvGVSrchPyltKaKBcu5cWx48VBGpo1zVQORvNmmep7y9TUcDOtVN7//NOxlEqnLZ8KnAR1CW4qGw6gk3b+YK3HWt8wzTaI9MKmAlPgBMJoJS9N1lX5zab2ODAdTLNuZCYQ2zQR8dP1Y3v61urv7Rmbet81P5jPeeD06lvrAoDbz6rcedmUyBBXYTrt5IXhn6eGiKTO59fHqzUG25a2zjcceL5S5zoXfht7pxDhOz7WHleqZgcQy5ievqrzghhuTikvj3XPq93XKPMX8BpK8NDDGXFuxqXVI+0QW7pTB0YBv27VIiLmwdJpiaVTZRJENUlkygDyKrg/iH8IDxnUJ98VYCtczkDE7w3sgFyBCMpupw0/RyaiW5OmmgtVJWLXjm5zCJH2wsy1BO0qLaKITWyCFkz/Fd5nNHETecajBFKKob44mLJGp32DKfe8ldoXcjl2Oht0LLaHp0SApVS6X1Q7jZpVkfsFBULbIjPrBvJQYX0t1YAwtIljdvJ8YDDvYXewi1ow5C8L1QM6PHirW9uUM802o51KRsdQpLIy1MGlLVK4X7CTFSRdSmNpIKyQlw+O6tsrKkpNSkTIThUxQAn+0tHgpqfifsVf1pZR07AHaCJzgMqxifPUUbG2CnrX5K7OnIwheesrI613TRH+qixxIspPMQB+D1ZG88lvlYqNxxxDMJO7SV/8Vr08wyFxqaLdtwVctc54w+7wnA/kWSnpMadJ/ace/6lNz6qXsaPComc82fqxP7K+8Ix65O1qhu7pd+8Wg/5K1njdPWN2eTh9LX439FJk47aYO56fnvEUBL+3OrFHe9UzqMdoP2tjjUsxkrTYmtqb1U2a/TK1X/m9FYeiiEI7x42SQZTSucWpUG9tvaVjh29Ll5byifBAQgtN2EYnjTjBb+n4aEaUBEn6QKavzwwpaBvneZCzZHtPSsuaKkVxCvxqVoKaW9WBTduh+y0dL34Q1H4XgQgH+5qgW06YNHNT+BvJg7AMM5oTj3kl8ZI8ikuaRnFACU0CUkZZmLuun+axn/tJnoRhGDM3CJ/cX46foAAMfe3SdnBcvtlPjrz7//X/ACGYmeBICgEA'
if len(body)!=1236 or hashlib.sha256(body).hexdigest()!='b32cc9d9b60c78219e57a675c44e720b7f36f1760714dda87d510bad09ad2670': raise ValueError('chunk differs')
save(TRANSFER/'chunk-06',body)
if read(TRANSFER/'chunk-06',1236)!=body: raise ValueError('chunk readback differs')
print('SOURCE CHUNK 06 VERIFIED',flush=True)
