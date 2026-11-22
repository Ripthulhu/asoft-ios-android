import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'saved-inspection-resume2-transfer'
def read(path,limit):
 if path.resolve(strict=True)!=path: raise ValueError('noncanonical transfer path')
 with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
  s=os.fstat(f.fileno())
  if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_uid!=0 or s.st_size>limit: raise ValueError('invalid transfer file')
  b=f.read(limit+1)
 if len(b)>limit: raise ValueError('transfer input exceeded bound')
 return b
def save(path,body,mode=0o600):
 with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode),'wb') as f:
  f.write(body);f.flush();os.fsync(f.fileno())
 d=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try: os.fsync(d)
 finally: os.close(d)
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
if TRANSFER.resolve(strict=True)!=TRANSFER: raise ValueError('transfer directory differs')
mb=read(TRANSFER/'manifest.json',1405)
if hashlib.sha256(mb).hexdigest()!='d561ce431542c6bff8b8fb997879b0f0b15363f691521adff91cd2c8cc7a99b5': raise ValueError('manifest differs')
body=b'l2cKEQ90JwlGAr9p1WEiOmGpvGSgU+nbQn2fX/kA7JWLMdBjEB4iO42DEhPS8CNPRJsMA7ICXYrexa1g4m+/tm6RWIkFijRHNa7XEiHyXph5W/FB3u/Hk+za6LseiMGDeTpuosz4JhmBfKjPzgps0OnYrMAjj1eO5Q7KJxSVDRJP87Kz/bCUWg3wKdSouMdYgIsj9FCKYdNAEBXWV87Mc48RJ7OLJxNNeE/7g102Gs41MrFmQINlIfVr6wqT3mZ2UFvueTzk9QJNlmSHFR6XtTMIkj6nGWjA3WnXn5yedlR6j5wUT/WMJTNgT1kaCtzadj8aL+j7Nv0X9gB9PQZwObowHhsyaVRCb0Xum7tjMbdse0vVvhqO8A/pUuLpalIAsAOdIi1NfKtlkjdelgMzuV+MJSI1y9M869cybXtf5lCHxltxx17LFbSSZ+eMJ41Tvf6Iruhl7zO6Rz2ne0zi6ZHJp2PP7PL7iI94ZXd/2tLoq7v7EyxGX+Hd36xp0u6XbsaJ752ECskUupe1SB1EWk97vOPN1jZbOjfYtvR5KZsIy4gb4An7+KSW8PY1PfjtiIIhCWd+/PK1pgXtkzyf5PXf35O0smJpKMbySbS6ydDZD92vGEHwIttvAggcEU6O9aV2ogmUEDOwM8v0k9wJfMfKwywJ/NQJ3DyMkjBzksSyqOl5XpaGZpiFaWpaJKOmbyUmyR49XM8foQIMfR2ydnBcttmPzqyH//H/AJHDgH8npwAA'
if len(body)!=752 or hashlib.sha256(body).hexdigest()!='98e6febc8415cff82748cce9ea15153c4d012bde138703ba399a3aeb495b6304': raise ValueError('chunk differs')
save(TRANSFER/'chunk-04',body)
if read(TRANSFER/'chunk-04',752)!=body: raise ValueError('chunk readback differs')
print('SAVED INSPECTION CHUNK 04 VERIFIED',flush=True)
