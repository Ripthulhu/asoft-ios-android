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
manifest=base64.b64decode('ewogICJzY2hlbWEiOiAxLAogICJraW5kIjogInNhdmVkX2luc3BlY3Rpb25fcmVzdW1lNV9zb3VyY2VfdHJhbnNmZXIiLAogICJ0YXJnZXRfZGlyZWN0b3J5IjogIi9kYXRhL2xvY2FsL3RtcC9waXhlbC1ncHUtdHJhbnNmZXItc3h0djMzc2giLAogICJmcmVzaF90YXJnZXRfZGlyZWN0b3J5IjogZmFsc2UsCiAgImJ1bmRsZV9ieXRlcyI6IDY4MTY4LAogICJidW5kbGVfc2hhMjU2IjogIjJlMTE3MDNlN2MzNWIxZGVkNzE1ZTc2NzQ2Y2IyZTcxZWM1NzEyMmJkMGQ1Y2EyNzk4NTA2N2VmOGQ2OTRlNjEiLAogICJlbmNvZGVkX2J5dGVzIjogMjIyMzYsCiAgImVuY29kZWRfc2hhMjU2IjogImI2MTQ4OGJiNGUwZTIwYjVhOTU1NTlhNzBmMjU0ZTk2ZmM4NTA5YzdlM2MxNmMxZjljMTViZGQ1NDQ1N2FlZGEiLAogICJjaHVua3MiOiBbCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAwIiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICIzZDIxNWM2NDRjYmQwZjhkMzg2Yjk0MThiNmVkYzA1MzZmMmM2NzU3MGU5Mjc3YjNlYjY0NDBmZjQxNGY2ZDFkIgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDEiLAogICAgICAiYnl0ZXMiOiAzNTAwLAogICAgICAic2hhMjU2IjogIjRiOGZiOTc3NjQ4NjVlOTUzYjY3MzE0ZTIzZjg1MTcwYTdkNWY4ODk3ODFmZjRjMDdkYTIzYjNhOTM5MWZiMWUiCiAgICB9LAogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wMiIsCiAgICAgICJieXRlcyI6IDM1MDAsCiAgICAgICJzaGEyNTYiOiAiNTRmYmRhYzVjYzVjNjNjYjc5ZjI0MmI0Y2FmZTUzZWFjYWFhZmRmNTk0ZDdlMGZhNWQyMjMyN2Y2OTUwNmU1MiIKICAgIH0sCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAzIiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICI2NTFhYjJiNjEzNjZlNGEzZGMwY2RjMTdkNTE2MWQyNDQzZWU1YTIzNjljOWUxODc1ZmFhMjk1YWQ2MjkyMTZiIgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDQiLAogICAgICAiYnl0ZXMiOiAzNTAwLAogICAgICAic2hhMjU2IjogIjkyMDkxN2E3ODlhOTlhMDhmZTE0OTk5ODMzYzYzMjgxMjhlZDQ1YTYxYjBiY2FkODc0MTIyZDM5ZDY1YjVmYWYiCiAgICB9LAogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wNSIsCiAgICAgICJieXRlcyI6IDM1MDAsCiAgICAgICJzaGEyNTYiOiAiMDI5Yzk4NjI3Y2QzODBlYjYyYzc0YjQ4ODVhMTlkOWYzN2I2NGU2OGZmZDk0OTJjNzhhNThkM2M1YTg0ZWVjOCIKICAgIH0sCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTA2IiwKICAgICAgImJ5dGVzIjogMTIzNiwKICAgICAgInNoYTI1NiI6ICJiMzJjYzlkOWI2MGM3ODIxOWU1N2E2NzVjNDRlNzIwYjdmMzZmMTc2MDcxNGRkYTg3ZDUxMGJhZDA5YWQyNjcwIgogICAgfQogIF0sCiAgImZpbGVzIjogWwogICAgewogICAgICAicGF0aCI6ICJydW4taW9zMjYtc2F2ZWQtaW5zcGVjdGlvbi1yZXN1bWU1LnB5IiwKICAgICAgImJ5dGVzIjogNjA1NjQsCiAgICAgICJzaGEyNTYiOiAiZGJiNTcwZGM5YjMzNTRhNWQ3YzRlYjIxODg4M2FiMjJmMjVhZmUyNDc1N2M0MjllNDZjYzdjMDRkZTFiYWE2MyIKICAgIH0sCiAgICB7CiAgICAgICJwYXRoIjogImxhdW5jaC1pb3MyNi1zYXZlZC1pbnNwZWN0aW9uLXJlc3VtZTUtcHJlZmxpZ2h0LnB5IiwKICAgICAgImJ5dGVzIjogNjIzMywKICAgICAgInNoYTI1NiI6ICI4OTA4MjU2YWIzNGY0OWRiYTFlMWZhMTdiNTZmZDg1NjNkYWQ3M2FmNTk0YjAwMjhiNjJiMjdiNzQ0NDZlMDM0IgogICAgfQogIF0KfQo=',validate=True)
if hashlib.sha256(manifest).hexdigest()!='d33bd545f82981ea899a1282756a327a26926a29d2f2eb744d25629d43a4bd0c': raise ValueError('manifest differs')
if TARGET!=BASE: raise ValueError('unexpected existing source target')
for name in ('run-ios26-saved-inspection-resume5.py', 'launch-ios26-saved-inspection-resume5-preflight.py'):
 if os.path.lexists(TARGET/name): raise ValueError('source exists; preserve it')
if os.path.lexists(INSTALL): raise ValueError('install receipt exists; preserve it')
TRANSFER.mkdir(mode=0o700)
save(TRANSFER/'manifest.json',manifest)
print('REVIEWED SOURCE TRANSFER CREATED; NO EXECUTION',flush=True)
