import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'resume1-preflight-transfer'
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
manifest=base64.b64decode('ewogICJzY2hlbWEiOiAxLAogICJraW5kIjogInJlc3VtZTFfcHJlZmxpZ2h0X3NvdXJjZV90cmFuc2ZlciIsCiAgImJ1bmRsZV9ieXRlcyI6IDQyOTQzLAogICJidW5kbGVfc2hhMjU2IjogImY2ZTdiNWVkNzI1ODRhM2E0ODU0ZGE4M2NjNWViMmI0YTk0NjZhNjJhMWU3YTVmMWI4OTQ0M2RjZDc0YmZkOGEiLAogICJlbmNvZGVkX2J5dGVzIjogMTUwNjgsCiAgImVuY29kZWRfc2hhMjU2IjogImFmOGE0M2JiZGUwZTBjNzUyOWI2ODU4M2MxMjZhNDc3ZmMwZGRkMTM2MTJiYTU3Y2UxMzVlMGVlNWE4M2NhMWYiLAogICJjaHVua3MiOiBbCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAwIiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICJhOTc5N2YwMjcxYzZmZGIyMjM2M2IyNTVlZDUxNzczZjRmZjU1NDYyN2Y0OGQwNmYzNWFmMzY3YTFjOTFjMWNmIgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDEiLAogICAgICAiYnl0ZXMiOiAzNTAwLAogICAgICAic2hhMjU2IjogImRkYThmMWJkMzVhMjkyOWNmYmUyNjYxYjAzODA3NGEwMTUyMWUxYjM0Y2JhYzQyNzQwMWY5NDVjNjczNmMxMDIiCiAgICB9LAogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wMiIsCiAgICAgICJieXRlcyI6IDM1MDAsCiAgICAgICJzaGEyNTYiOiAiOTljYzhhMWNkOTgyNWI0YTFlOGRiYTk1YTYwY2Y5ZWFlNDI5ZWEzZTQ2ZTcwMzc5NWQwMjUxODY0M2M4NWYwYyIKICAgIH0sCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAzIiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICIyOGE1OWMzYjM1NDFmYjNkY2ZkODI1Mzc3ZmU1YjU2NWFmMDQyZTU1MDEzNDZkYzZkNmFiMDM1YmJmOWZiN2Q4IgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDQiLAogICAgICAiYnl0ZXMiOiAxMDY4LAogICAgICAic2hhMjU2IjogIjc3OTgxZWMxMDBmZTQxYWZhM2YwMDRmZWUwNjE3ZDM2ZDg0ZTc4YThhMTY2NmRmNjFhZDI5M2ZlYjAzMDY2ZGUiCiAgICB9CiAgXSwKICAiZmlsZXMiOiBbCiAgICB7CiAgICAgICJwYXRoIjogInJ1bi1pb3MyNi1maXJzdGJvb3QtbWVtZmQtYWRhcHRlci1yZXN1bWUxLnB5IiwKICAgICAgImJ5dGVzIjogOTEwMSwKICAgICAgInNoYTI1NiI6ICJlZGU3MDAyM2JjMWUwNWIwODczMGI0OGZhYjEwMTZjM2U2NjVjMGU4MzQ2OTUwOWU1YjhiNzRjNmYyMzY0ZWM3IgogICAgfSwKICAgIHsKICAgICAgInBhdGgiOiAiY2FwdHVyZS1pb3MyNi1maXJzdGJvb3QtcmVzdW1lMS5weSIsCiAgICAgICJieXRlcyI6IDMyOTI4LAogICAgICAic2hhMjU2IjogIjExMjI5OTA3ZjJiNmE2ODFkODU3MWY2Njg5Yjg1YWM1NTNjYjRlMGRiNTg1NTA3ZDExNTk5ZWM5NzgwYTA0Y2EiCiAgICB9CiAgXQp9Cg==',validate=True)
if hashlib.sha256(manifest).hexdigest()!='f4b1270949e8e138ce2416adbb10bdfc558c25380e2359fdaa82105e6ee6844d': raise ValueError('manifest differs')
for name in ('run-ios26-firstboot-memfd-adapter-resume1.py','capture-ios26-firstboot-resume1.py','resume1-preflight-install.json'):
 if os.path.lexists(BASE/name): raise ValueError('target already exists; preserve it')
TRANSFER.mkdir(mode=0o700)
save(TRANSFER/'manifest.json',manifest)
print('RESUME1 TRANSFER CREATED',flush=True)
