import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'resume2-process-observer-transfer'
INSTALL=BASE/'resume2-process-observer-install.json'
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
 for path in [INSTALL,BASE/'ios26-saved-inspection-resume2-observer',BASE/'ios26-saved-inspection-resume2-observer-launch.json',BASE/'ios26-saved-inspection-resume2-observer-wrapper.log']+[BASE/row['path'] for row in files]:
  if os.path.lexists(path): raise ValueError('fresh observer path required; preserve '+str(path))
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
mb=base64.b64decode('ewogICJzY2hlbWEiOiAxLAogICJraW5kIjogInJlc3VtZTJfcHJvY2Vzc19vYnNlcnZlcl9zb3VyY2VfdHJhbnNmZXIiLAogICJidW5kbGVfYnl0ZXMiOiA0MTI3MCwKICAiYnVuZGxlX3NoYTI1NiI6ICIxYmMxY2RmODJiOTdlZjNjOWNmNTA3Yzc1OTJmMjFmNjc3ZGE5YjhlMzgyOTc0YWIxMjJlMWM2YmM1NTM5ZjhmIiwKICAiZW5jb2RlZF9ieXRlcyI6IDE0NDgwLAogICJlbmNvZGVkX3NoYTI1NiI6ICI1OGM5ZjIwNTUzZGU2ZDYxZGMyOTBlMzg4NzM4ZmVjNzNlMmUyYjAwOTFlMDkzMjIyYzFjNWM5NzI1NjA2MWZlIiwKICAiZmlsZXMiOiBbCiAgICB7CiAgICAgICJwYXRoIjogInJ1bi1pb3MyNi1zYXZlZC1pbnNwZWN0aW9uLXJlc3VtZTItb2JzZXJ2ZXIucHkiLAogICAgICAiYnl0ZXMiOiAzMzkzMCwKICAgICAgInNoYTI1NiI6ICIyNjEyNTI5MWVlYmNlZDk2NDY4NTExY2MwNjBhOTU2MjMzMTVhYmExNGUyZmQ4YjYzY2Q2MDU2ZmVkMjdiMTkyIgogICAgfSwKICAgIHsKICAgICAgInBhdGgiOiAibGF1bmNoLWlvczI2LXNhdmVkLWluc3BlY3Rpb24tcmVzdW1lMi1vYnNlcnZlci5weSIsCiAgICAgICJieXRlcyI6IDYxOTIsCiAgICAgICJzaGEyNTYiOiAiMDZmMjllMDgwY2NiMjhiMmIzOTBhNjZlZDY2ODAyMTIxYjM0YzEyOGMwYTA1N2E2NmQxMDVlNjcwNDM4YzAxYyIKICAgIH0KICBdLAogICJpbnNwZWN0aW9uX293bmVyX3NvdXJjZSI6IHsKICAgICJwYXRoIjogIi9kYXRhL2xvY2FsL3RtcC9waXhlbC1ncHUtdHJhbnNmZXItc3h0djMzc2gvcnVuLWlvczI2LXNhdmVkLWluc3BlY3Rpb24tcmVzdW1lMi5weSIsCiAgICAiYnl0ZXMiOiAzNTc5OSwKICAgICJzaGEyNTYiOiAiNDQ1ZjE2NzM2ZmYzZjBjNGFjYTJmOWQ4MjVmNGI3MWI5MjY0YmMyNGIxNzdmZTNhODI4MWNhOWM2ZTBmMWUwYiIKICB9LAogICJjaHVua3MiOiBbCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAwIiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICI1NmUyODIyMjViOGMwMDdmYTQzODRmYTgzZWJlZjdhY2M3N2U1ZWJmOWFmZTFmNjJkNjM0MWNjY2RhYmY3OTkzIgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDEiLAogICAgICAiYnl0ZXMiOiAzNTAwLAogICAgICAic2hhMjU2IjogIjc3Y2E0NzczY2YyN2VlNzNhMjY5MWRmMGYzM2U5MjFiNDc5OTUyOGMxZjQwZmRhNTEwOWU4MmY1ODg4MGRmZTUiCiAgICB9LAogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wMiIsCiAgICAgICJieXRlcyI6IDM1MDAsCiAgICAgICJzaGEyNTYiOiAiNjUzY2RjNzUzYTBmYjdlMDBlMTY1ZTZiMmU5YmE3YzM3ZDhkNjIwZDYzMmY5MmRkMDk1OWU1NmJkM2Q0Y2ZlNSIKICAgIH0sCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAzIiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICI4NmI0NmM2ZTcyZTdhZjU5MGY0YjI1YTYxMWExMDgzMGRiZmFmODgzYmUzZTBlZGMwZDBiMDIyNmVhZGM3MGJhIgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDQiLAogICAgICAiYnl0ZXMiOiA0ODAsCiAgICAgICJzaGEyNTYiOiAiNTYxZmEyNjBkNmMyNDQyNWMwNzRhYjhmY2ZjZGQzYmFkNTA1MTE4MDZjN2IxMTg1MDhiNjRlMTNlYmI4ZGRiNSIKICAgIH0KICBdCn0K',validate=True)
if hashlib.sha256(mb).hexdigest()!='dc136f8dd85dc2e8cdfdb00f8134d5d92ed132299a280e3999838acd398fe7cf': raise ValueError('manifest differs')
m=json.loads(mb)
fresh(m['files'])
p=m['inspection_owner_source'];owner_body=read(OWNER_SOURCE,p['bytes'])
if len(owner_body)!=p['bytes'] or hashlib.sha256(owner_body).hexdigest()!=p['sha256']: raise ValueError('inspection owner source differs')
TRANSFER.mkdir(mode=0o700)
save(TRANSFER/'manifest.json',mb)
print('OBSERVER SOURCE TRANSFER CREATED; NO EXECUTION',flush=True)
