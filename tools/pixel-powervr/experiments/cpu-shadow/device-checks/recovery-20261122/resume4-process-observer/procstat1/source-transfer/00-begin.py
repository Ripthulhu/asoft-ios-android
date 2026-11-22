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
mb=base64.b64decode('ewogICJzY2hlbWEiOiAxLAogICJraW5kIjogInJlc3VtZTRfcHJvY2Vzc19vYnNlcnZlcl9wcm9jc3RhdDFfc291cmNlX3RyYW5zZmVyIiwKICAiYnVuZGxlX2J5dGVzIjogNDUzNjUsCiAgImJ1bmRsZV9zaGEyNTYiOiAiMzRlZGY5NjcyMTQxMTRlOGYxZjgyN2Y0MTliZDE3MGVkMzc5OTRlNGE1NTk3ZTg0OTk4MDExZDFmYmY5N2M0OSIsCiAgImVuY29kZWRfYnl0ZXMiOiAxNTYyMCwKICAiZW5jb2RlZF9zaGEyNTYiOiAiYTA5ZWIzZGZiMjFmNmQ2MzY2ZjZjMGEyYTRkZDE5MzQ2MDZiMTM2NjQ3YzExMDE5MDE0N2M3NmM3NTE5ZjhmYiIsCiAgImZpbGVzIjogWwogICAgewogICAgICAicGF0aCI6ICJydW4taW9zMjYtc2F2ZWQtaW5zcGVjdGlvbi1yZXN1bWU0LW9ic2VydmVyLXByb2NzdGF0MS5weSIsCiAgICAgICJieXRlcyI6IDM3ODc3LAogICAgICAic2hhMjU2IjogIjk0OWRhMzg1OTBmODZkODI3ZTZiOWZiMmYyNjFlNzg1ZTg5YjRlM2NmZTFlZmRiZmJlYTYwMzU0Y2QyODFlZDkiCiAgICB9LAogICAgewogICAgICAicGF0aCI6ICJsYXVuY2gtaW9zMjYtc2F2ZWQtaW5zcGVjdGlvbi1yZXN1bWU0LW9ic2VydmVyLXByb2NzdGF0MS5weSIsCiAgICAgICJieXRlcyI6IDYyNTIsCiAgICAgICJzaGEyNTYiOiAiZjA4MjY4MGNkN2Y5YmI2Y2YxYWUzYzhlOGRlYmQwZDliMzQ3ZjZkMTMzODU5N2M1MmMyM2VhNjNiZjNhZmFkZiIKICAgIH0KICBdLAogICJpbnNwZWN0aW9uX293bmVyX3NvdXJjZSI6IHsKICAgICJwYXRoIjogIi9kYXRhL2xvY2FsL3RtcC9waXhlbC1ncHUtdHJhbnNmZXItc3h0djMzc2gvcnVuLWlvczI2LXNhdmVkLWluc3BlY3Rpb24tcmVzdW1lNC5weSIsCiAgICAiYnl0ZXMiOiA0ODQ2OSwKICAgICJzaGEyNTYiOiAiYzVjYzAxNzY4YmUyM2MwYTdlM2FkMTM2NGNiODlhM2RkODU2MjI4OGFjM2M1MWY1ZWFlZjM1Y2U3YzAzOWYxMCIKICB9LAogICJjaHVua3MiOiBbCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAwIiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICJlYTQxYTFmNDliNTYyYTVhOGVjMDQzNjdjMzViZGFkZGQyNjY1YWMzZGI0NjVhMTkxZGE5Y2I3OGJiY2JjMzYwIgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDEiLAogICAgICAiYnl0ZXMiOiAzNTAwLAogICAgICAic2hhMjU2IjogImM3ZmU1OTcyMzlkMzhiMDBjMDIyZTljOTcwNmMzOWVkZWRhYWI3NWZiZGNjNWU4MWMxZWExNjFkY2UxOTY1YWMiCiAgICB9LAogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wMiIsCiAgICAgICJieXRlcyI6IDM1MDAsCiAgICAgICJzaGEyNTYiOiAiNmFlOTE2YWE0MWExNjEwZDY3NDU0MWU5Nzc2OTllM2Q5ZmI5YWNhNzYwMzgxY2RhN2JjNjJiOWFmNjg4NTU4MSIKICAgIH0sCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAzIiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICJhOTU2OWI5YmU5ZjdjODAyZGYxOTBhMWZmODkxYjAxYzI0NGYzMjNlNDBmY2ZmODkwYjA3MDU2YmQxYWFjMjk3IgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDQiLAogICAgICAiYnl0ZXMiOiAxNjIwLAogICAgICAic2hhMjU2IjogImZiNTU3NGVlNmQ3ZTU0NTg0ZTdiMTJjNGQ0ZWFlYTMwMzlhZmIzZDAzMTU0YzQ2YjFhYjcxZDQ1ZDQ4YzNiMTkiCiAgICB9CiAgXQp9Cg==',validate=True)
if hashlib.sha256(mb).hexdigest()!='8df1c00f09a83fe990001071e46e1bb0c6ab01ba2a9b489377cb8e0fb73fb4d7': raise ValueError('manifest differs')
m=json.loads(mb)
fresh(m['files'])
p=m['inspection_owner_source'];owner_body=read(OWNER_SOURCE,p['bytes'])
if len(owner_body)!=p['bytes'] or hashlib.sha256(owner_body).hexdigest()!=p['sha256']: raise ValueError('inspection owner source differs')
TRANSFER.mkdir(mode=0o700)
save(TRANSFER/'manifest.json',mb)
print('OBSERVER SOURCE TRANSFER CREATED; NO EXECUTION',flush=True)
