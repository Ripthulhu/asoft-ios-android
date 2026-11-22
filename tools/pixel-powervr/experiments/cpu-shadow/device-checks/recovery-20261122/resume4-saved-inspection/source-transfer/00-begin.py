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
manifest=base64.b64decode('ewogICJzY2hlbWEiOiAxLAogICJraW5kIjogInNhdmVkX2luc3BlY3Rpb25fcmVzdW1lNF9zb3VyY2VfdHJhbnNmZXIiLAogICJ0YXJnZXRfZGlyZWN0b3J5IjogIi9kYXRhL2xvY2FsL3RtcC9waXhlbC1ncHUtdHJhbnNmZXItc3h0djMzc2giLAogICJmcmVzaF90YXJnZXRfZGlyZWN0b3J5IjogZmFsc2UsCiAgImJ1bmRsZV9ieXRlcyI6IDU1NjAxLAogICJidW5kbGVfc2hhMjU2IjogIjI0M2RhYTE5NTI3Y2FjMmMwZTk1ZTkyZWU3MjllOTZmZjhjMzRhNzY1OWYwZmY5OGM3MTVjNTI4NTE2ZWE0NjYiLAogICJlbmNvZGVkX2J5dGVzIjogMTg3NjgsCiAgImVuY29kZWRfc2hhMjU2IjogIjYzOTg5NDcyZWExM2IwZjE0NTgzNGNiZWI5ZWViNWIwZDg1YWNiYjQ1NjY1ODIzNmJjZmUwOTZhYmMxYmU1MDMiLAogICJjaHVua3MiOiBbCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAwIiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICI4MTJmZWI5YzY2M2M3MTMxNGU2YWY2YjMwYjVkMmQ2OGExZDllZmQwZDIyOTRiNTM1OTEzNTY2NzcxNjMyZDlmIgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDEiLAogICAgICAiYnl0ZXMiOiAzNTAwLAogICAgICAic2hhMjU2IjogIjBkNWZhODFiYzE5YTdjMDc2MWI1OGQ2ZGM0OGVjMGE2NzFlODhiMTdhYzI0OTQ2MThiNzNlZDYzNjc2ZGM4ZTgiCiAgICB9LAogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wMiIsCiAgICAgICJieXRlcyI6IDM1MDAsCiAgICAgICJzaGEyNTYiOiAiOTE0MzczYmYwM2IxZjc5YzljZGU2NzQwMzQ5MDcyMDAyM2MwNTA2NDZkYTY4YzAwMjQ1MzNjNzQzNjZmYWQ0NSIKICAgIH0sCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAzIiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICIzY2RjMjM2ODA3MTYwN2U5ODk5ZDc0NzhkZTk1ZWVkODNkNTcxYmVhODhlMmY0ZjcyM2U4YWU5ODIxNWQ4NzA0IgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDQiLAogICAgICAiYnl0ZXMiOiAzNTAwLAogICAgICAic2hhMjU2IjogIjA0MTA0M2U1ZDZhZGNiZmI5NmI1ODBiOWRlMjliODY5OTY1Y2Y1MmE2MzZjOThjZmNjNDQ3NzQyZWMyYTMxMjciCiAgICB9LAogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wNSIsCiAgICAgICJieXRlcyI6IDEyNjgsCiAgICAgICJzaGEyNTYiOiAiMDM5NTEwZjdkM2U5ZGI1MDAzY2JlM2MzZjcyOTlkZGIzNzM0NjdjNTVmZjM2Mzc5OTlmZjY1NGI1MjA2ZDU2YyIKICAgIH0KICBdLAogICJmaWxlcyI6IFsKICAgIHsKICAgICAgInBhdGgiOiAicnVuLWlvczI2LXNhdmVkLWluc3BlY3Rpb24tcmVzdW1lNC5weSIsCiAgICAgICJieXRlcyI6IDQ4NDY5LAogICAgICAic2hhMjU2IjogImM1Y2MwMTc2OGJlMjNjMGE3ZTNhZDEzNjRjYjg5YTNkZDg1NjIyODhhYzNjNTFmNWVhZWYzNWNlN2MwMzlmMTAiCiAgICB9LAogICAgewogICAgICAicGF0aCI6ICJsYXVuY2gtaW9zMjYtc2F2ZWQtaW5zcGVjdGlvbi1yZXN1bWU0LXByZWZsaWdodC5weSIsCiAgICAgICJieXRlcyI6IDU5MjYsCiAgICAgICJzaGEyNTYiOiAiNTlhYThmYjM4NTBhZDYxZDA3NGU3ZDg1MTJjNzA2NzY1ODkzNmZmMTI4ZjNiZmZjYTc3ZjM5M2U5YWVkZmQ1OCIKICAgIH0KICBdCn0K',validate=True)
if hashlib.sha256(manifest).hexdigest()!='3e13577d266ddc922a1ca378852ed18b305033faf4263cf40989fe860a7fe969': raise ValueError('manifest differs')
if TARGET!=BASE: raise ValueError('unexpected existing source target')
for name in ('run-ios26-saved-inspection-resume4.py', 'launch-ios26-saved-inspection-resume4-preflight.py'):
 if os.path.lexists(TARGET/name): raise ValueError('source exists; preserve it')
if os.path.lexists(INSTALL): raise ValueError('install receipt exists; preserve it')
TRANSFER.mkdir(mode=0o700)
save(TRANSFER/'manifest.json',manifest)
print('REVIEWED SOURCE TRANSFER CREATED; NO EXECUTION',flush=True)
