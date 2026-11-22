import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'saved-inspection-resume3-transfer'
TARGET=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
INSTALL=BASE/'saved-inspection-resume3-install.json'
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
mb=read(TRANSFER/'manifest.json',1653)
if hashlib.sha256(mb).hexdigest()!='60fa31ca711f5c10b3e01910fb5b3e6a255b681cb3031a377b889943288461b8': raise ValueError('manifest differs')
body=b'TTpULlVLcVyrjhfqzRhXvx0uOOPUAs42tWSyOO7CeGackHaCN47hvafkFyAYF7ySnG0Oi7/VNXwcWs1JSwDXd3hk2llhrpC0f2rpDMmoKK9xpOQzEzLnWJRNZrfsg/QNN0+CLMf9MFgdOtE03TalguXt3SEpfrBM+fWIdUjDhsUlr1oWld6hKlMdbynNYnLhUvCZWk7oxb5Z08xJYDRvlqm+t2wmDVnWSmUg41/U42bz1uUACBMqmmsuG46gk3baa63HWnA27Q+I9MI4AFPgio3RSkb/1VV5iE57HJgOpuE1QuzFNs2EI3D9VI6+tfprOcamfurq0VpOXTm9OvxaAHD/WZU7L5sS6aspbICdBCf889zg9ep8fr3jVWN5bKmdfMOBeSm9pBO52hjuhCzauSwcuBPUFFqxjLmWA9y4r5OC31S/Quy/NJOB+LyG4qC6Xx7OzYi+PNMOcU936sAo4NetWkTEPFg6LenpVNm2UN4XKR+AvAo2BnIMwkN6pwlQokMafhSOaKN+QG5AlmJ384YxIRPRzSJz7S5Qujnq93rNIUTaCzNvKn5S+f2Ek11z+25exGBgnombyDMexCNQDPXFXoE1Oh3rFXhkeOWQ7+DU6mzQudgeHtsPS6n0Cz7tNGrmMX7BJRC6z8WwbiAPFdbXYuaFxUgcs4snI4N5j7uDXdUSzjUSsXpAi3shdWubApPZZnJQWu5YPFR6gdpLskUKj/Pa6QVJl9L0NBDmtOvPdk87yr1HTUq4es4VMUBR9NrS4Na0+8F6zt437r/49hkBPQWoHJtZjy3lNKqgtyT3dR5d9C3b3jK9r5oi/E2ZlIS7mmIA6vFFbCq/VcrJG5PlwEzuZ0OOSPXyDMv6tXLb3uc51DrjDbvDcz6SZyXPzjlNGj71+E9tQ1W9TC3l31vw3NHn7qTvsXOuEN1tCrxnffu2c8V1yPH0SOdT8bKZEr8beilyM/fo7U8uX/FY+j9bnfS7LdUzqMeYtNOX9jlYGNlG+pr2N6ubNPtlqnHye8uhQhGFdrIWJYMo7WmPdbze2npLpxbfli4t5RPhHnE9NGEfnTQc3r6lBb8ZURIkacyfv3hlSEH7OM9nWf3396S0rHn96AbwqyInlGeSER46+6H7DW8QgsQN6wsEgQgnx9pSW7cJccDsPEqzNEqDPHXSNAmYyxIvj2I/IzmzA5sGdujhT5u6bu76fpDRMI0cN4qy+NGn6+kjFIChr0PaDo7LN/vRmfPpf/1/vYKK3DHZAAA='
if len(body)!=1264 or hashlib.sha256(body).hexdigest()!='bd89f4f165969f9d15e0be90bedf799cf01e97587a048baf6f1882ebcab274af': raise ValueError('chunk differs')
save(TRANSFER/'chunk-05',body)
if read(TRANSFER/'chunk-05',1264)!=body: raise ValueError('chunk readback differs')
print('SOURCE CHUNK 05 VERIFIED',flush=True)
