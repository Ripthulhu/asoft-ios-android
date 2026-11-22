import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'resume2-process-observer-procstat1-transfer'
INSTALL=BASE/'resume2-process-observer-procstat1-install.json'
OWNER_SOURCE=BASE/'run-ios26-saved-inspection-resume2.py'
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
 for path in [INSTALL,BASE/'ios26-saved-inspection-resume2-observer-procstat1',BASE/'ios26-saved-inspection-resume2-observer-procstat1-launch.json',BASE/'ios26-saved-inspection-resume2-observer-procstat1-wrapper.log']+[BASE/row['path'] for row in files]:
  if os.path.lexists(path): raise ValueError('fresh observer path required; preserve '+str(path))
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
mb=base64.b64decode('ewogICJzY2hlbWEiOiAxLAogICJraW5kIjogInJlc3VtZTJfcHJvY2Vzc19vYnNlcnZlcl9wcm9jc3RhdDFfc291cmNlX3RyYW5zZmVyIiwKICAiYnVuZGxlX2J5dGVzIjogNDUzNjYsCiAgImJ1bmRsZV9zaGEyNTYiOiAiNTI1NDQ0YWVjODZmYWE4YjhlM2VmZjQ2MDliYTcyODA4ZGQ2Y2FiNmYxMjczYWJmNDVmNTllMTBiYWJmZjZlNSIsCiAgImVuY29kZWRfYnl0ZXMiOiAxNTYzMiwKICAiZW5jb2RlZF9zaGEyNTYiOiAiOGNiZTNjNDU1YWFhMTg2YWIyMWFjMTRkNGRlNWZkZWMzZDE0ZmJmYjEwMzg3ZDZiODE5MThlMzhiMDQzNTI1YiIsCiAgImZpbGVzIjogWwogICAgewogICAgICAicGF0aCI6ICJydW4taW9zMjYtc2F2ZWQtaW5zcGVjdGlvbi1yZXN1bWUyLW9ic2VydmVyLXByb2NzdGF0MS5weSIsCiAgICAgICJieXRlcyI6IDM3ODc4LAogICAgICAic2hhMjU2IjogImE0OWVjOWIxMWJhMGZlZmRhMDNlMmE2ODhlODY0MjJkZjUzODUxYzllYzE0NmYyMTU5MTk2MWRhMjAxMDRiZDIiCiAgICB9LAogICAgewogICAgICAicGF0aCI6ICJsYXVuY2gtaW9zMjYtc2F2ZWQtaW5zcGVjdGlvbi1yZXN1bWUyLW9ic2VydmVyLXByb2NzdGF0MS5weSIsCiAgICAgICJieXRlcyI6IDYyNTIsCiAgICAgICJzaGEyNTYiOiAiYzIxZDYxYTIxODI0MGI2M2EzMmM2ZjhmMDhiZjk4ZDZjYTVlMDZkOGExZDc0MDcwNmZlNThjN2NiYWE1OTNmMyIKICAgIH0KICBdLAogICJpbnNwZWN0aW9uX293bmVyX3NvdXJjZSI6IHsKICAgICJwYXRoIjogIi9kYXRhL2xvY2FsL3RtcC9waXhlbC1ncHUtdHJhbnNmZXItc3h0djMzc2gvcnVuLWlvczI2LXNhdmVkLWluc3BlY3Rpb24tcmVzdW1lMi5weSIsCiAgICAiYnl0ZXMiOiAzNTc5OSwKICAgICJzaGEyNTYiOiAiNDQ1ZjE2NzM2ZmYzZjBjNGFjYTJmOWQ4MjVmNGI3MWI5MjY0YmMyNGIxNzdmZTNhODI4MWNhOWM2ZTBmMWUwYiIKICB9LAogICJjaHVua3MiOiBbCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAwIiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICI2NGZlZDU4OWY0ODVjOTBlZTMwYWJjMmE2NWIzZjQ5Yzk5ZjhkZmI0ZjJhY2U4Y2NhNmFjYjk2MzVlODBhZTUwIgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDEiLAogICAgICAiYnl0ZXMiOiAzNTAwLAogICAgICAic2hhMjU2IjogIjRhMGRmOTMzODljZGViOTRkZjllZmZlZDYzOWJlMTA3MjAwM2Q0NzU1MTNjNzFlOTE4NDRhNDE3NGRlYmY3YWYiCiAgICB9LAogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wMiIsCiAgICAgICJieXRlcyI6IDM1MDAsCiAgICAgICJzaGEyNTYiOiAiN2RjOTVhN2ZlZDA3ZjEwOWJmMmUyMzA2YzhjMzBkYmNkZmVkM2NjMGU2MzJhOGYzYTQ5N2ZmMDQ1NDNkYzBhMyIKICAgIH0sCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAzIiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICIzOTA0MzQ2YjhhMjhmOGU5OWU0NmRhOTA4ZjJhYzgxOGM1ZjNiMDQ1YjkzM2UyMDY5MmM3OTYyYWVjNTI4ZmQyIgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDQiLAogICAgICAiYnl0ZXMiOiAxNjMyLAogICAgICAic2hhMjU2IjogImFlMWYzNWY2MTIwNzE5OWFkNGUzZjAxZDAwNTA4ODkwYjE4M2M3OTFhMDVhNWVmMjdhOGFmM2ZiMTBlYTE0ZjUiCiAgICB9CiAgXQp9Cg==',validate=True)
if hashlib.sha256(mb).hexdigest()!='a560443a8d372545001df2c12a66f6c67e779bfe9965f7b500a13ff151c085a4': raise ValueError('manifest differs')
m=json.loads(mb)
fresh(m['files'])
p=m['inspection_owner_source'];owner_body=read(OWNER_SOURCE,p['bytes'])
if len(owner_body)!=p['bytes'] or hashlib.sha256(owner_body).hexdigest()!=p['sha256']: raise ValueError('inspection owner source differs')
TRANSFER.mkdir(mode=0o700)
save(TRANSFER/'manifest.json',mb)
print('OBSERVER SOURCE TRANSFER CREATED; NO EXECUTION',flush=True)
