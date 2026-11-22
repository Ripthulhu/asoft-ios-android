import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'resume5-process-observer-procstat1-transfer'
INSTALL=BASE/'resume5-process-observer-procstat1-install.json'
OWNER_SOURCE=BASE/'run-ios26-saved-inspection-resume5.py'
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
 for path in [INSTALL,BASE/'ios26-saved-inspection-resume5-observer-procstat1',BASE/'ios26-saved-inspection-resume5-observer-procstat1-launch.json',BASE/'ios26-saved-inspection-resume5-observer-procstat1-wrapper.log']+[BASE/row['path'] for row in files]:
  if os.path.lexists(path): raise ValueError('fresh observer path required; preserve '+str(path))
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
mb=base64.b64decode('ewogICJzY2hlbWEiOiAxLAogICJraW5kIjogInJlc3VtZTVfcHJvY2Vzc19vYnNlcnZlcl9wcm9jc3RhdDFfc291cmNlX3RyYW5zZmVyIiwKICAiYnVuZGxlX2J5dGVzIjogNDUzNjUsCiAgImJ1bmRsZV9zaGEyNTYiOiAiMTA5MmIyYmI2ODAzNTI1YmEyYTg1YjllNDdlZGYxNjI0ZjkzMDljMWFhNjkyZjY5Y2IyNGM4OWM0ZGY0YTU1OCIsCiAgImVuY29kZWRfYnl0ZXMiOiAxNTYyNCwKICAiZW5jb2RlZF9zaGEyNTYiOiAiMTYyOTgwMmZhYjliY2QxYTFiNzJhYjdlNzU3Y2UyNGMyN2E0MjYzYjQxNmQ2MGFlOTIzYWEyMTI4MzkwZjJmZCIsCiAgImZpbGVzIjogWwogICAgewogICAgICAicGF0aCI6ICJydW4taW9zMjYtc2F2ZWQtaW5zcGVjdGlvbi1yZXN1bWU1LW9ic2VydmVyLXByb2NzdGF0MS5weSIsCiAgICAgICJieXRlcyI6IDM3ODc3LAogICAgICAic2hhMjU2IjogIjQ3OGI4YjkxNzk0NDNhZTNiNjBlOTIxYmQ2NTkzM2NkNjRhMGNkMWMyMDliZjllODMyN2M1NDFmZTcyZjY1ZGUiCiAgICB9LAogICAgewogICAgICAicGF0aCI6ICJsYXVuY2gtaW9zMjYtc2F2ZWQtaW5zcGVjdGlvbi1yZXN1bWU1LW9ic2VydmVyLXByb2NzdGF0MS5weSIsCiAgICAgICJieXRlcyI6IDYyNTIsCiAgICAgICJzaGEyNTYiOiAiOGZjMjEyOTNmNTJiM2VhMjMyNTEzN2VjNGY4MmU0MjdhOGJhMjU0YmM2MGIwOWViYzhmMjE1ZGRhYTgxM2RlNiIKICAgIH0KICBdLAogICJpbnNwZWN0aW9uX293bmVyX3NvdXJjZSI6IHsKICAgICJwYXRoIjogIi9kYXRhL2xvY2FsL3RtcC9waXhlbC1ncHUtdHJhbnNmZXItc3h0djMzc2gvcnVuLWlvczI2LXNhdmVkLWluc3BlY3Rpb24tcmVzdW1lNS5weSIsCiAgICAiYnl0ZXMiOiA2MDU2NCwKICAgICJzaGEyNTYiOiAiZGJiNTcwZGM5YjMzNTRhNWQ3YzRlYjIxODg4M2FiMjJmMjVhZmUyNDc1N2M0MjllNDZjYzdjMDRkZTFiYWE2MyIKICB9LAogICJjaHVua3MiOiBbCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAwIiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICJiNjc3YjJjZDRlYzJjMTdkM2JhOGVkZmE1NTYzMWZjODRhZTBlN2NjMjc0YTBjYWE2OWU5NWY3NDk2NTk4ZWNlIgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDEiLAogICAgICAiYnl0ZXMiOiAzNTAwLAogICAgICAic2hhMjU2IjogIjcxZmUxMDY0OWI2ODEyYzA0OTE5NzVjNWY0OWMyNWZiYzQzZjFjZmE2ZjIyZDA1ZjgxMjgwYjhhZWM1NDU5ZjAiCiAgICB9LAogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wMiIsCiAgICAgICJieXRlcyI6IDM1MDAsCiAgICAgICJzaGEyNTYiOiAiYmE1NjAxMjhkNDJhZGQyY2ZiMDBjYWE5YTA3YmI2OTBlNTA5OWM5YjNlMjZhN2U1NmU1Mjc2YmE2YjUzODNkNyIKICAgIH0sCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAzIiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICI2MzQ5ZDZiNDMzMjA0YTRhZjNkY2UyMWJlYmI3NmRiMTQ2MTZkYjhjOGM1ZGVjNWU2MDQ3OGFjNDIwMTQ2MGIxIgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDQiLAogICAgICAiYnl0ZXMiOiAxNjI0LAogICAgICAic2hhMjU2IjogImY5ZGUzMDg5YzVkOTNlODVjYTM0ZTVhMWM1Y2VjMDE4NzZiMmMzN2E3NWE1MzczMjc4MWNlMTIyNjFiMjg0ZjkiCiAgICB9CiAgXQp9Cg==',validate=True)
if hashlib.sha256(mb).hexdigest()!='a899909aca777e0f3e77e46059ce454cda0e731499adc7e94262522f842a2ede': raise ValueError('manifest differs')
m=json.loads(mb)
fresh(m['files'])
p=m['inspection_owner_source'];owner_body=read(OWNER_SOURCE,p['bytes'])
if len(owner_body)!=p['bytes'] or hashlib.sha256(owner_body).hexdigest()!=p['sha256']: raise ValueError('inspection owner source differs')
TRANSFER.mkdir(mode=0o700)
save(TRANSFER/'manifest.json',mb)
print('OBSERVER SOURCE TRANSFER CREATED; NO EXECUTION',flush=True)
