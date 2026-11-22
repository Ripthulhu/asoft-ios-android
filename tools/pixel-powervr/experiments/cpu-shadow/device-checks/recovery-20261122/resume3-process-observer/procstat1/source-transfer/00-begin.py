import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'resume3-process-observer-procstat1-transfer'
INSTALL=BASE/'resume3-process-observer-procstat1-install.json'
OWNER_SOURCE=BASE/'run-ios26-saved-inspection-resume3.py'
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
 for path in [INSTALL,BASE/'ios26-saved-inspection-resume3-observer-procstat1',BASE/'ios26-saved-inspection-resume3-observer-procstat1-launch.json',BASE/'ios26-saved-inspection-resume3-observer-procstat1-wrapper.log']+[BASE/row['path'] for row in files]:
  if os.path.lexists(path): raise ValueError('fresh observer path required; preserve '+str(path))
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
mb=base64.b64decode('ewogICJzY2hlbWEiOiAxLAogICJraW5kIjogInJlc3VtZTNfcHJvY2Vzc19vYnNlcnZlcl9wcm9jc3RhdDFfc291cmNlX3RyYW5zZmVyIiwKICAiYnVuZGxlX2J5dGVzIjogNDUzNjUsCiAgImJ1bmRsZV9zaGEyNTYiOiAiYmM0NTRlODAzZGFiZTY1NzQ5YjAxNDRjYWQxZjU3OWFiOThiYmEwYjk1MDY4MGFhNmM0ZmMwY2FlYThhYzZmNiIsCiAgImVuY29kZWRfYnl0ZXMiOiAxNTYyNCwKICAiZW5jb2RlZF9zaGEyNTYiOiAiNWRmMTIwY2VkODEyNzA5NTA5NTdhZjYzZmM1ODQxMmMwOGU5YTg3NmE0N2QyZDYyZDEwMjI0NmI1Nzk5NmY1ZCIsCiAgImZpbGVzIjogWwogICAgewogICAgICAicGF0aCI6ICJydW4taW9zMjYtc2F2ZWQtaW5zcGVjdGlvbi1yZXN1bWUzLW9ic2VydmVyLXByb2NzdGF0MS5weSIsCiAgICAgICJieXRlcyI6IDM3ODc3LAogICAgICAic2hhMjU2IjogIjQwNjQzMzNjYWJhZDkxMjBjMDM3MTZkYTllOTViMzU4ZjA1ZmMzMDM2NTg4NWIwNTUwMTg1N2Y0MzJhOTJhZjEiCiAgICB9LAogICAgewogICAgICAicGF0aCI6ICJsYXVuY2gtaW9zMjYtc2F2ZWQtaW5zcGVjdGlvbi1yZXN1bWUzLW9ic2VydmVyLXByb2NzdGF0MS5weSIsCiAgICAgICJieXRlcyI6IDYyNTIsCiAgICAgICJzaGEyNTYiOiAiMzA0ZjEzZjE2ZjFiYTZmMTQ2MzQ4YWE2ZmU3M2Q5ZDUzMWJkZThiMzQ2ZTJkZjkxZTg1NmNiN2M1MDExOWEzMiIKICAgIH0KICBdLAogICJpbnNwZWN0aW9uX293bmVyX3NvdXJjZSI6IHsKICAgICJwYXRoIjogIi9kYXRhL2xvY2FsL3RtcC9waXhlbC1ncHUtdHJhbnNmZXItc3h0djMzc2gvcnVuLWlvczI2LXNhdmVkLWluc3BlY3Rpb24tcmVzdW1lMy5weSIsCiAgICAiYnl0ZXMiOiA0ODQ2OSwKICAgICJzaGEyNTYiOiAiOTFhYzNiYTJiYThjM2U0MGIyYTk5ZGZmZmRjNGE1M2FlNDliOGU0NDEyNDU3NTVmMzNlZjc2MTg0NmQ2MWUxNCIKICB9LAogICJjaHVua3MiOiBbCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAwIiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICIzYTVmMzk3NjllY2QxYTE2MWYzZDU4ZGY3ZjEyMWY1YjIyNmE2NzRiYjUwNDhmNDRjMjdlODhjM2NiMDIxM2I0IgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDEiLAogICAgICAiYnl0ZXMiOiAzNTAwLAogICAgICAic2hhMjU2IjogIjVmN2QxY2UxZDk2YThhOTAxMDJjMTlmNjIyZTBiODkwY2M2ZDc4MjNiYmRhMzBiZmJkMzg2NWNjYjllMTg0YWEiCiAgICB9LAogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wMiIsCiAgICAgICJieXRlcyI6IDM1MDAsCiAgICAgICJzaGEyNTYiOiAiY2RkZTkwYTA1ODAwMWRjZWMzMjM0YWI1OGE0MjBhYmU2MzgwNWRiNWJhMDA4MGNjNDAyZmFkN2ExNWZmMzBhYyIKICAgIH0sCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAzIiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICI5M2NhMDIwNzQwNWZiMjk4ODAwNzMxZTk1NGMyMDc3OWE3ODA2M2M3ZTdlYzI3MzE4MzQ5ZGU4ZDlhYzkwNWRiIgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDQiLAogICAgICAiYnl0ZXMiOiAxNjI0LAogICAgICAic2hhMjU2IjogIjI1ZGNhOGI5MGRmOTI1MGU2MzY1ZTk1YTU1ODMzYjc3ZmU4NmU1ZDdjZjI5NjQ4ZTA1NjQ2OTkxMzg4M2ExNzMiCiAgICB9CiAgXQp9Cg==',validate=True)
if hashlib.sha256(mb).hexdigest()!='affe3f299edc825a462e69d21f88771fc8c24971eea62b610f6bee6b6e10fc02': raise ValueError('manifest differs')
m=json.loads(mb)
fresh(m['files'])
p=m['inspection_owner_source'];owner_body=read(OWNER_SOURCE,p['bytes'])
if len(owner_body)!=p['bytes'] or hashlib.sha256(owner_body).hexdigest()!=p['sha256']: raise ValueError('inspection owner source differs')
TRANSFER.mkdir(mode=0o700)
save(TRANSFER/'manifest.json',mb)
print('OBSERVER SOURCE TRANSFER CREATED; NO EXECUTION',flush=True)
