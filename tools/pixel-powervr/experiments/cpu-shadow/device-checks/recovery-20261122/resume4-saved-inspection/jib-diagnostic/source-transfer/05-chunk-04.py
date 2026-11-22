import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'root-jib-diagnostic-resume4-transfer'
def read(path,limit):
 if path.resolve(strict=True)!=path: raise ValueError('noncanonical transfer path')
 with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
  a=os.fstat(f.fileno())
  if not stat.S_ISREG(a.st_mode) or a.st_nlink!=1 or a.st_uid!=0 or a.st_size>limit: raise ValueError('invalid transfer file')
  b=f.read(limit+1);z=os.fstat(f.fileno())
 if len(b)!=a.st_size or len(b)>limit or (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)!=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns): raise ValueError('transfer input changed or exceeded bound')
 return b
def save(path,body,mode=0o600):
 with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode),'wb') as f:
  f.write(body);f.flush();os.fsync(f.fileno())
 d=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try: os.fsync(d)
 finally: os.close(d)
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
if TRANSFER.resolve(strict=True)!=TRANSFER: raise ValueError('transfer directory differs')
mb=read(TRANSFER/'manifest.json',1227)
if len(mb)!=1227 or hashlib.sha256(mb).hexdigest()!='fd168adace896ed166cfbba7e770f0ff9623b8f6659cad9de3c97f5584bcd5c6': raise ValueError('manifest differs')
body=b'fUKn8r0AvQ4rlbPD6NwDFmIEDgfnq1tPyZbM6sBlXD11/lk1VRjXz/txNKicp/tsgjMySC1P/TET7gdTVXhzfvrD+4ur6/PXyv0xoW+tOHZbGetaF+V0KQep4LZB+4HpDdb3UbrtIo0s7Hxq6yOWHNr8VJG4Hyw+XKWVVF6sB/BfLPpOZAU/lUWkfUKxPZ+Qp7gwYg31lVa+r6otuJoSor16ah0Ud2rxTHhDfD29EN97EndWxGYv5Ka3jSBc81yw2CijBX8v5q392m+uLtovrbb7NdovCZQ+ExMRtWgaYaUaboQeoFFGQoA+Nd0qJIK5YR7Kl9tk3kJfF8SimLOycPeZ/wBI84OVcZWo/FxUp1JXo6IxtIp4eZbKL6EqMfOSdFQu+qgVMzop49k6ZajMpuJlYJnIoJckMw7AnVgSgXxLjr8wyZwH73TAPzrWwVAh5enD6fWPqAUdcxXIY9bdO2/feG/Pv7s8vcQ4IrWouARW6F+FhtfvPrw5v5RlvFjVe3v6/geE+ZogvfZO377ln091tb6vpk1iHxnUS/wA+lp1f32V/9zoGgR9lUzPwZKTuLGXyl5hX9aBNKWGMYQyifDLIgaUeYe3CVC9PL08v7p4XxYzkBH1l33OTY5Tflztyz7mVv/mGuYjMeM+ecnnKP+dbJA6NHJeiOPbl6nr97G4cl79MEGfa01gQSNmDbKCEV76fcmF88p12/qnDLQRVAH6X20UUbP9YLX1r4eu1X9SSGqr9NQ7aR5GVZVq2pOmTxQKaqzwNy3i3f45RdmXbUjFYb+8q4ylfElPloSNRSph+oyEFjBf8uHFNs6gGZrtHRpitcuv/3ijAGp8MmFJUSxSwdo+sFgp7sK/KreKkojcnPhNV5DrXf5+d/3b0vRB3dImaeQ7db9YY40ZyZNlef/ah1I3WzBdu5S8FO3Xm6JbkfTK5q/uziEtQJUlRNydSMwdvhwmCtOfVIpc1hdVVVMP5Cy/9AYMF2BTqZEYiuqiVggCe8BgGaCs1NY7oPXKm6E6zlhMV03zJml7GGzV9Ke8yBapfhgSUg0q8dxLmISe+ry28OVpXzHVFOGvG1EUQjYGRI+F9r3n58fAs2B8g/YZhLWz2xOjwF57u2dW1cqTTfitzV4Evs63m6DXWz23Iy/wPr3IaffMFrzEn3fQUXYQvvRsNXzIo/Sg6qLhpPoVjlqez8HDLT6smG+LRbfTR4XhhK6i0uev+aOdQlGFqZ98BaPtKCVYs9Avz77/CTMT27nuFyBJKcX8lUPOw6J0A4PEyOjsv3zBwjdOpTvqsvzFaj5fFXXZow6glOhGEJ6H/nXP68hQJn2H+IrssLOP6a7L7neRSfSq/4pI6tXJyBmPRv1XKFlenbza7rMj+g7IERqVGH85KrEqPhc6Gmw+QX9m/9AnTIZOkAxHs3kQR5PROAqi8TyZxbY7SibT8dwZ28ncnbiJM5rZ8SSaR6MkGQ+T2XgczOHRq6dl/xV62nH8un+9/KQqe5NwaCKPVyfO0//6v82/qU2vpQAA'
if len(body)!=1532 or hashlib.sha256(body).hexdigest()!='bab6d785ef078bba2510dfc8d4660ab70e3da9466e102436c9cd9edd799ed6bd': raise ValueError('chunk differs')
save(TRANSFER/'chunk-04',body)
if read(TRANSFER/'chunk-04',1532)!=body: raise ValueError('chunk readback differs')
print('ROOT JIB DIAGNOSTIC CHUNK 04 VERIFIED',flush=True)
