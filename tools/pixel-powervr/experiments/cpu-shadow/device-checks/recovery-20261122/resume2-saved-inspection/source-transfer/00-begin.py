import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'saved-inspection-resume2-transfer'
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
manifest=base64.b64decode('ewogICJzY2hlbWEiOiAxLAogICJraW5kIjogInNhdmVkX2luc3BlY3Rpb25fcmVzdW1lMl9zb3VyY2VfdHJhbnNmZXIiLAogICJidW5kbGVfYnl0ZXMiOiA0Mjc5MSwKICAiYnVuZGxlX3NoYTI1NiI6ICIwMDkxOTlmMDVmMGJhNzViNTMwYzRhOTFhYjlmMWZlYWVjZDY2ZmI5YzU0NmNmMzRhOTQ5NjdjMDJhMmFkZGQ5IiwKICAiZW5jb2RlZF9ieXRlcyI6IDE0NzUyLAogICJlbmNvZGVkX3NoYTI1NiI6ICIyYTUwYTAwY2MxNzM5ODQwYTA0YmE3OWFkN2UwNTAxZjNhOGI2MDc5N2ZkN2I1MjcwMGU5YjFhZGM3NGJkNjUzIiwKICAiY2h1bmtzIjogWwogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wMCIsCiAgICAgICJieXRlcyI6IDM1MDAsCiAgICAgICJzaGEyNTYiOiAiNjc4NzViYWUxYzUxYWFlYzFjM2Y0MDRlNWUwMDE5OTg0ZDg1MzllZThkOWEyMDEwOTdjNGIzZGU4ZjI0YWY0ZSIKICAgIH0sCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAxIiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICIxOTNkNGRiYjY1ODY4NWU2YjAxMTEzNTU4ZTU3MzI4YmU2NDk2Yjc3NmJmN2NkMzM1ZmNkOThhYjNlMzgwOTQzIgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDIiLAogICAgICAiYnl0ZXMiOiAzNTAwLAogICAgICAic2hhMjU2IjogIjUzY2FiYTlmZDFiYTVlYzdjOWY0YjgxMjIzYzMwMzIzOTI2MDYxMmM2MjA1ZjVmZTA0OTgwNDhiOTY5MzcxNzMiCiAgICB9LAogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wMyIsCiAgICAgICJieXRlcyI6IDM1MDAsCiAgICAgICJzaGEyNTYiOiAiYTI3MTc4NzQ5ODdkYTY4ZTVkNGNlN2ZhM2NhZjY1YzBhMzgxZmIwZTJhYjZlOTg1ZTk0ZGRiNzM3NmJlNzFlOSIKICAgIH0sCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTA0IiwKICAgICAgImJ5dGVzIjogNzUyLAogICAgICAic2hhMjU2IjogIjk4ZTZmZWJjODQxNWNmZjgyNzQ4Y2NlOWVhMTUxNTNjNGQwMTJiZGUxMzg3MDNiYTM5OWEzYWViNDk1YjYzMDQiCiAgICB9CiAgXSwKICAiZmlsZXMiOiBbCiAgICB7CiAgICAgICJwYXRoIjogInJ1bi1pb3MyNi1zYXZlZC1pbnNwZWN0aW9uLXJlc3VtZTIucHkiLAogICAgICAiYnl0ZXMiOiAzNTc5OSwKICAgICAgInNoYTI1NiI6ICI0NDVmMTY3MzZmZjNmMGM0YWNhMmY5ZDgyNWY0YjcxYjkyNjRiYzI0YjE3N2ZlM2E4MjgxY2E5YzZlMGYxZTBiIgogICAgfSwKICAgIHsKICAgICAgInBhdGgiOiAibGF1bmNoLWlvczI2LXNhdmVkLWluc3BlY3Rpb24tcmVzdW1lMi1wcmVmbGlnaHQucHkiLAogICAgICAiYnl0ZXMiOiA1OTI2LAogICAgICAic2hhMjU2IjogImVhYTA3MmQxMDZiZjM3NjMxZjhkYjc2YzM3NGY4OWI4ZDNiYjExZTA1NTVkYzgwOGQ4Y2MwMWFkZTA2MWIwYWQiCiAgICB9CiAgXQp9Cg==',validate=True)
if hashlib.sha256(manifest).hexdigest()!='d561ce431542c6bff8b8fb997879b0f0b15363f691521adff91cd2c8cc7a99b5': raise ValueError('manifest differs')
for name in ('run-ios26-saved-inspection-resume2.py', 'launch-ios26-saved-inspection-resume2-preflight.py', 'saved-inspection-resume2-install.json'):
 if os.path.lexists(BASE/name): raise ValueError('target already exists; preserve it')
TRANSFER.mkdir(mode=0o700)
save(TRANSFER/'manifest.json',manifest)
print('SAVED INSPECTION TRANSFER CREATED',flush=True)
