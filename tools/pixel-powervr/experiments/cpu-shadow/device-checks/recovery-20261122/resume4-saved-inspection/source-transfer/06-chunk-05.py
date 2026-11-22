import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'saved-inspection-resume4-transfer'
TARGET=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
INSTALL=BASE/'saved-inspection-resume4-install.json'
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
if hashlib.sha256(mb).hexdigest()!='3e13577d266ddc922a1ca378852ed18b305033faf4263cf40989fe860a7fe969': raise ValueError('manifest differs')
body=b'a9KhcqlaiuNadbxQb8a4+u1wwRmnFnC2qSWTxXEXxjPjhLQTvHEM7z0lvwDBuOCV5GxzWPytruHj0GpOWgK4vsMj084Kc4Wk/VNLZ0hGRXmNIyWfmZA5x6JsMrtlH6RvuHkSZDnuh8Hq0Imm6bYpFSxv7w5J8YNlyq9HrEMaNiwuedWyqPQOVZnqeEtpFpMLl4LP1HJCL/bNmmZOAqN5s0z1vWUzaciyVioDGf+iHjebty4HQJhQ0Vxz2XAEnbTTXms91oKzaX9ApBfGAZgCV2yMVjL6r67KQ3Ta48B0MA2vEWIvtmkmHIHrp3L0rdVfyzE29VNXj9Zy6srp1eHXAoD7z6rcedmUSF9NYQPsJDjhn+cGr1fn8+sdrxrLY0vt5BsOzEvpJZ3I1cZwJ2TRzmXhwJ2gptCKZcy1HODGfZ0U/Kb6FWL/pZkMxOc1FAfV/fJwbkb05Zl2iHu6UwdGAb9u1SIi5sHSaUlPp8q2hfK+SPkA5FWwMZBjEB7SO02AEh3S8KNwRBv1A3IDshS7mzeMCZmIbhaZa3eB0s1Rv9drDiHSXph5U/GTyu8nnOya23fzIgYD80zcRJ7xIB6BYqgv9gqs0elYr8AjwyuHfAenVmeDzsX28Nh+WEqlX/Bpp1Ezj/ELLoHQfS6GdQN5qLC+FjMvLEbimF08GRnMe9wd7KqWcK6RiNUDWtwLqVvbFJjMNpOD0nLH4qHSC9Reki1SeJzXTi9IupSmp4Ewp11/tnvaUe49alLC1XOuiAGKoteWBrem3Q/Wc/a+cf/Ft88I6ClA5djMemwpp1EFvSW5r/Poom/Z9pbpfdUU4W/KpCTc1RQDUI8vYlP5rVJO3pgsB2ZyPxtyRKqXZ1jWr5Xb9j7PodYZb9gdnvORPCt5ds5p0vCpx39qG6rqZWop/96C544+dyd9j51zhehuU+A969u3nSuuQ46nRzqfipfNlPjd0EuRm7lHb39y+YrH0v/Z6qTfbameQT3GpJ2+tM/Bwsg20te0v1ndpNkvU42T31sOFYootJO1KBlEaU97rOP11tZbOrX4tnRpKZ8I94jroQn76KTh8PYtLfjNiJIgSWP+/MUrQwrax3k+y+q/vyelZc3rRzeAXxU5oTyTjPDQ2Q/db3iDECRuWF8gCEQ4OdaW2rpNCBJC4jz14sAmWehkduSzKIsDx6WRHUZhECdemOeOG+demueURFHuJR5LCMvyLIgffbqePkIBGPo6pO3guHyzH505n/7X/weR0rD2MdkAAA=='
if len(body)!=1268 or hashlib.sha256(body).hexdigest()!='039510f7d3e9db5003cbe3c3f7299ddb373467c55ff3637999ff654b5206d56c': raise ValueError('chunk differs')
save(TRANSFER/'chunk-05',body)
if read(TRANSFER/'chunk-05',1268)!=body: raise ValueError('chunk readback differs')
print('SOURCE CHUNK 05 VERIFIED',flush=True)
