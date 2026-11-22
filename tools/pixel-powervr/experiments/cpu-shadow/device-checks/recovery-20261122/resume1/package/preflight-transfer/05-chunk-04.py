import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'resume1-preflight-transfer'
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
manifest=read(TRANSFER/'manifest.json',1390)
if hashlib.sha256(manifest).hexdigest()!='f4b1270949e8e138ce2416adbb10bdfc558c25380e2359fdaa82105e6ee6844d': raise ValueError('manifest differs')
body=b'uMV5F2IPK0uxVZtl+6hXu81X/yxiHONdLof7ibHXkYBrtZK6xI7W+orgQPodGvcRdP8wtOwJFoIWy7CXzvG+BMAigq70dEE/bhg5tkffV6Rzer/my0G/ecqTYTDKsEtcjDEw0crk23PbNbszoeVYAgiWG2aBGk4tdEHtipOJrdO91MkFFK4A/zX+F/QO9VrK+h5NMYoWI+VG8+Cnp6/fvP3x5cu3Fsq0Y+bjUHIO/an95CQ50xSKaFyKAVmBdloiYAf9HeMIsbZgoZyrTZvhXnRZHm6K57wKyymuZTIj1qbxpr9/nUFhHY1D7a0AIE+JMU6Tm11enHrupfJK6NWyvdU89/Ty3p4LmldzMmMDxgti2PAnmGwGzHK4q+3RjikJnsZKYZP3M7z+dhRNqJZMalChwhMZTmR401X/dsy/h5iwgd3UxAObzMc+FS7/sXD4j1tpya2+ugTGV7v7vrXOPRWzHRV3r3QPd2eQuof/75kK5+4Swe/j/R12bWBsl5lf9rBsrKIeWiNTu2WFUsi5t+Laox73ynrJ87r4GPju0R6Nnk1ZbMSFKhfysiEcoX47FJsQfu+7e+hS3DikCmnXD+E3vBDoefUj3uijt2NeL4QF/Unws1msfSFQGwEYALSJCohcKvwSN/5gg5qnk5W6UFcHXTIfq3ZjT39x406fyzb6cMnJzDQRlRt+aq53Ek3Iq3kue+Jxx/+Ft29Bz58umoujLvlNW4hm7+ntdEbmWUGsT/yKNKPgCFEObxKjfY5bAQ45yPR6CVOvN1i1NVlZ5OI0YHCRNwepS4MYaRnTad8qtINMmVzB2twuZYmKPWplr/O56+oy3V1j6ezS/V4q33GH/0uUM/NW+mwQnqMB75UnD03TNMWMjTSVScPcHfzmFoT4/Bzk9JAndEDzR+MjRg5HwPwSNx4foRZ3dHokgj3HOxIMJ6tbqMnZFZR2HNdNEjsq3SwkYewUcRA5ZRjGSRYHJA8CL898auNN8EFgR4XjBElC8ySKbWL7OTm6uxwfoWkNbYkeGrtJHjiLHTID8ejUufsf/w/sXl3kv6cAAA=='
if len(body)!=1068 or hashlib.sha256(body).hexdigest()!='77981ec100fe41afa3f004fee0617d36d84e78a8a1666df61ad293feb03066de': raise ValueError('chunk differs')
save(TRANSFER/'chunk-04',body)
if read(TRANSFER/'chunk-04',1068)!=body: raise ValueError('chunk readback differs')
print('RESUME1 CHUNK 04 VERIFIED',flush=True)
