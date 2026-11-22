import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'saved-inspection-resume2-execution-transfer'
def read(path,limit):
 if path.resolve(strict=True)!=path: raise ValueError('noncanonical transfer path')
 with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
  s=os.fstat(f.fileno())
  if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_uid!=0 or s.st_size>limit: raise ValueError('invalid transfer file')
  b=f.read(limit+1)
 if len(b)>limit: raise ValueError('transfer input exceeded bound')
 return b
def save(path,body,mode=0o600):
 with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode),'wb') as f:
  f.write(body);f.flush();os.fsync(f.fileno())
 d=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try: os.fsync(d)
 finally: os.close(d)
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
manifest=base64.b64decode('ewogICJzY2hlbWEiOiAxLAogICJraW5kIjogInNhdmVkX2luc3BlY3Rpb25fcmVzdW1lMl9leGVjdXRpb25fc291cmNlX3RyYW5zZmVyIiwKICAiYnVuZGxlX2J5dGVzIjogMjE3NTUsCiAgImJ1bmRsZV9zaGEyNTYiOiAiYzk1YTBmNTdiMWE4YWY3NDlmOWY5ZmUzYTgwZjQ1MzM3ODA2NmI2M2RmM2M0MmUyOTMyZWI4YzQ4NWNiOTVhNyIsCiAgImVuY29kZWRfYnl0ZXMiOiA4Mjg0LAogICJlbmNvZGVkX3NoYTI1NiI6ICI3MjA3YjI0NmM3NDljNDExNDA3ZTcwZmVjNjc1MTY0YzViODQ4YzFjNTAwMjRiMjUyNTZhMDc3ZGUwZTM5YjhhIiwKICAiY2h1bmtzIjogWwogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wMCIsCiAgICAgICJieXRlcyI6IDM1MDAsCiAgICAgICJzaGEyNTYiOiAiOWQzN2YyODM1ZTkyM2I0ZmZlZmU2MmFkZjYzMmJlODUyNWRlYjFiYjc5YjRiNDk2NzQ1ZjdjYjdjYmRmY2UwNyIKICAgIH0sCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAxIiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICIxMTdmMjM4N2RmM2EwMWEyNTU0ZDRhYTNhZjlmOTEwNmFiM2ZjYjU2OGVmZGMwMzVhYjhiNTEzYzY0ZTVlNGZhIgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDIiLAogICAgICAiYnl0ZXMiOiAxMjg0LAogICAgICAic2hhMjU2IjogImExMjg0YzJlZTU2NzEyNDg5OTdjMmQxNDc0NWY5NGFhM2IwNmVmZTI5ZWQxMWMwNTZhMTBhYmQzNTAwMWQ3NGYiCiAgICB9CiAgXSwKICAiZmlsZXMiOiBbCiAgICB7CiAgICAgICJwYXRoIjogImxhdW5jaC1pb3MyNi1zYXZlZC1pbnNwZWN0aW9uLXJlc3VtZTItZXhlY3V0ZS5weSIsCiAgICAgICJieXRlcyI6IDIxMTU0LAogICAgICAic2hhMjU2IjogIjZhYjYyYTRiNTdiZDk5NjE1ZmQ4ZTRhYmJkN2FjZTM3YTY4Mjg1NGUyM2JlZTFhYmY1ZjJhNzY3ZjI0ZWQ5ODIiCiAgICB9CiAgXQp9Cg==',validate=True)
if hashlib.sha256(manifest).hexdigest()!='f888c4f2e2f1f237ff66217da8b79369316c2f899c98d3142ada58dd83c740c0': raise ValueError('manifest differs')
for name in ('launch-ios26-saved-inspection-resume2-execute.py', 'saved-inspection-resume2-execution-install.json'):
 if os.path.lexists(BASE/name): raise ValueError('target already exists; preserve it')
TRANSFER.mkdir(mode=0o700)
save(TRANSFER/'manifest.json',manifest)
print('SAVED INSPECTION TRANSFER CREATED',flush=True)
