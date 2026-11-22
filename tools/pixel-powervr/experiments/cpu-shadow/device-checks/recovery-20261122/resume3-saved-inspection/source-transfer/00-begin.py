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
manifest=base64.b64decode('ewogICJzY2hlbWEiOiAxLAogICJraW5kIjogInNhdmVkX2luc3BlY3Rpb25fcmVzdW1lM19zb3VyY2VfdHJhbnNmZXIiLAogICJ0YXJnZXRfZGlyZWN0b3J5IjogIi9kYXRhL2xvY2FsL3RtcC9waXhlbC1ncHUtdHJhbnNmZXItc3h0djMzc2giLAogICJmcmVzaF90YXJnZXRfZGlyZWN0b3J5IjogZmFsc2UsCiAgImJ1bmRsZV9ieXRlcyI6IDU1NjAxLAogICJidW5kbGVfc2hhMjU2IjogIjIxYTQ4OTFjMTk4MmE1NmI3ODVmMTMxZWU3NGQxODJkMDBiNzc5MDU4MmExZDQ1M2VhNTY0ZTdiOWIyZmE3NTEiLAogICJlbmNvZGVkX2J5dGVzIjogMTg3NjQsCiAgImVuY29kZWRfc2hhMjU2IjogIjgyY2Y3N2MxNGUzZDM3NTZiMGExZDU0MzMyNzFjNTBmNDE0ZDY2MjlmMGIxZjcwYmU3ODFjYjk5OGRiMzk1MGIiLAogICJjaHVua3MiOiBbCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAwIiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICIyNWJiNGI5YzIyMGZhM2MwMGZmNmUyNTlhZmFhMjI4MWVkZjAxZWU1YmUwNGIwM2EwN2FlZGY1YThkMmQzZmEwIgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDEiLAogICAgICAiYnl0ZXMiOiAzNTAwLAogICAgICAic2hhMjU2IjogImU4YjgzOGI4N2ZiNDY0NzExYjI4ZjJjZGE5ZDI5OGUxNzU4ZDFiMWNhMzBjYWQ0OWNhNGUxM2U2MjQ0NjFiMTAiCiAgICB9LAogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wMiIsCiAgICAgICJieXRlcyI6IDM1MDAsCiAgICAgICJzaGEyNTYiOiAiYmVhYTUyNzRjMDE2MzhhMDc4ZmEwNjI1ODBjNDNjNTM4ZTIzMWViZGJhM2FlOWQyNWZiZGQyOTUxZmI5YjljZiIKICAgIH0sCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAzIiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICJjM2MxMTg0OTNiYWQwNWNkMTgzZTFjZTQ1NTU4MmVlZWQ4NDM4NmVkOGUwMWJkZDdlZjhiYTY2ZjQ1MjY3ZDgzIgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDQiLAogICAgICAiYnl0ZXMiOiAzNTAwLAogICAgICAic2hhMjU2IjogIjU2ZDcwYjc0MzAwNmYxZjcxMDcxMzVmODhiNGEwMzE3M2IyZThiMGZmZGQ3NTdjMDAxNGEzOTIzZjViZmE3ZWMiCiAgICB9LAogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wNSIsCiAgICAgICJieXRlcyI6IDEyNjQsCiAgICAgICJzaGEyNTYiOiAiYmQ4OWY0ZjE2NTk2OWY5ZDE1ZTBiZTkwYmVkZjc5OWNmMDFlOTc1ODdhMDQ4YmFmNmYxODgyZWJjYWIyNzRhZiIKICAgIH0KICBdLAogICJmaWxlcyI6IFsKICAgIHsKICAgICAgInBhdGgiOiAicnVuLWlvczI2LXNhdmVkLWluc3BlY3Rpb24tcmVzdW1lMy5weSIsCiAgICAgICJieXRlcyI6IDQ4NDY5LAogICAgICAic2hhMjU2IjogIjkxYWMzYmEyYmE4YzNlNDBiMmE5OWRmZmZkYzRhNTNhZTQ5YjhlNDQxMjQ1NzU1ZjMzZWY3NjE4NDZkNjFlMTQiCiAgICB9LAogICAgewogICAgICAicGF0aCI6ICJsYXVuY2gtaW9zMjYtc2F2ZWQtaW5zcGVjdGlvbi1yZXN1bWUzLXByZWZsaWdodC5weSIsCiAgICAgICJieXRlcyI6IDU5MjYsCiAgICAgICJzaGEyNTYiOiAiODVlMGY3YmRiN2I1ZmIxYmI5NWUyZTkzZjc4NGRhZmUwNTBjNTA2Mzc4NGQwYzIyZjI0NDVkYzZiNzEyNzdkOCIKICAgIH0KICBdCn0K',validate=True)
if hashlib.sha256(manifest).hexdigest()!='60fa31ca711f5c10b3e01910fb5b3e6a255b681cb3031a377b889943288461b8': raise ValueError('manifest differs')
if TARGET!=BASE: raise ValueError('unexpected existing source target')
for name in ('run-ios26-saved-inspection-resume3.py', 'launch-ios26-saved-inspection-resume3-preflight.py'):
 if os.path.lexists(TARGET/name): raise ValueError('source exists; preserve it')
if os.path.lexists(INSTALL): raise ValueError('install receipt exists; preserve it')
TRANSFER.mkdir(mode=0o700)
save(TRANSFER/'manifest.json',manifest)
print('REVIEWED SOURCE TRANSFER CREATED; NO EXECUTION',flush=True)
