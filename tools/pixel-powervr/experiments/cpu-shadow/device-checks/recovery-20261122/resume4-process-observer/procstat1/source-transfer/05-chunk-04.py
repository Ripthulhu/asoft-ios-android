import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'resume4-process-observer-procstat1-transfer'
INSTALL=BASE/'resume4-process-observer-procstat1-install.json'
OWNER_SOURCE=BASE/'run-ios26-saved-inspection-resume4.py'
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
 for path in [INSTALL,BASE/'ios26-saved-inspection-resume4-observer-procstat1',BASE/'ios26-saved-inspection-resume4-observer-procstat1-launch.json',BASE/'ios26-saved-inspection-resume4-observer-procstat1-wrapper.log']+[BASE/row['path'] for row in files]:
  if os.path.lexists(path): raise ValueError('fresh observer path required; preserve '+str(path))
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
mb=read(TRANSFER/'manifest.json',1678)
if hashlib.sha256(mb).hexdigest()!='8df1c00f09a83fe990001071e46e1bb0c6ab01ba2a9b489377cb8e0fb73fb4d7': raise ValueError('manifest differs')
m=json.loads(mb)
body=b'z/Gcv7a/2qM+zkOmdNeXQ1P5ZSD+nnjrYymOj5lXPbxITi7Oj3/upUOqjJUJ+v4r/VrlGS55Rz8o8Avd+GhXP6rzPzAyj5AaLEPv4aaswOglfbfArcf6AsxSASA6fhBe5uMNl2BbRxt+F37yMDZkqX12vsLCzJpgPoyTTNwO+HlelAPTQv65QG9agt+4o59T+ZOg9SYawEQDmBgAExfAxAGwlso8BHnOYMSIl7Ssvm3Px4LPfK+t+HTkU+Jthl3xRVFFd7mX7/jYr13EowvBkOceDgj5sIC3DCLmf/Dv2c9eRq6f+I0/+kEKxfz3Y2ok5yULiir5SiOqqfyVM+nhhVbJCLLOMmXKtNkOC5VBZISL9v53UGGgJWLb+6gWNbcdUX5XdYmwdhP0Mt2SMBwkiGaQuMOgYZqFnTJKWJEie33CotUphB4NbRAdPHVMN36TF06SpGpN31T2UyHVGE4ipIc208hx4smd4AMVnKiU14Nof8+ZpjqEI1KKQPKlWd2zAZldVo+9e3zFUZ23lNRC75Re0E5n0ZJSpurViQQRt+pTOrBNfJ5TrQSFAhcVWdubZC5P7UpvDBOe3JXvv7eLHOiNHPc3I0U5GgfUq2gSr1bRAjhGQ4VkSYsc/lpmq7m4RAMqVkmDLYR5nYeKcFmY9JzSS4ijHrpToIX8QrTVRgYloDvZAMO4NG0cq4Rz9XpN4nmQ9TpFjdAHx6oQDLx1gjbj1k+xP6Og6d0aqWU1Bo1u4mzelFQWv9yRzqRdlZ+ePJiQFQdmY0xl5u6uR9YJNjnS2FXeJBXqcqQjztsDKEvM6s6VAsI5/QPHsxUu2R+HK4BYZTacA6GnYHJw1RkJwH4g9/abMnvboynOpfmnwhHeUjts7QG3VRu0Kk2ExgE3RLmtgzULcdfOs+24bw3OW63RsDc8ccDfnY+okiaRsW5IOrdSIr7lW5nytMqynibqy/U8dSj9gIU/5UudQZvAKTeqbfDhOxpZp2XUDejlI+v96+O/n75Hacc1n0YMl36KqrJbXly+Rl1ss7CkqLXV0qtHXtlkltVtxxRxG9uZbHFV/+BylLVbQ5W+u9cCYhflAEmmO6IgDjaXxTrstg9aPEakyWJT6luiQtXuAMUlzdygNT26dfETvzs/e3V8cZFo9yFT7fHr+HHRHho4+xzHUoBu7nV004btL7UEv7OilrJM0cyzVBf+GozBpen4l+id0rF1hjfKwLloTKwfmowKuXyz4Hrqhl3BJXpKzn2ETVMkSzoP7Qyrt96tOWza79uTQw0idXhymtxoz7/ps7/Hyt+UDTZoRa9QoJ/+Qmqnva/Zs8X0uBhnwNHw+uT8+NXl2fnva0uT6VE17L4XUTQPdOGrF7+LvrIgbP3/+4r2fYXSt6Td/vhbi+CthCZPTZbr7wZ2HE5qmNNa7sQBKXt/9uWJVA3lHUpy5t7br70Y+VdctiinQELeBoyTACmXY1xE/WAhkP9zNzIHe8/29IWMTAD+1juZ2c7h3sHhzjR7PnsxmRxMZ7up2J8eisNMTLKd7MVk/+nz2UG2u4/e8ufTZ3vTvX2RHuxPZvvpLM1mT76MB0/QcMA7oo3tXJwBWR5Pjna//Jf/DTRGXpg1sQAA'
if len(body)!=1620 or hashlib.sha256(body).hexdigest()!='fb5574ee6d7e54584e7b12c4d4eaea3039afb3d03154c46b1ab71d45d48c3b19': raise ValueError('chunk differs')
save(TRANSFER/'chunk-04',body)
if read(TRANSFER/'chunk-04',1620)!=body: raise ValueError('chunk readback differs')
print('OBSERVER CHUNK 04 VERIFIED',flush=True)
