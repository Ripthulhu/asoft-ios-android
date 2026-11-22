import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'resume1-owner-transfer'
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
manifest=base64.b64decode('ewogICJzY2hlbWEiOiAxLAogICJraW5kIjogInJlc3VtZTFfb3duZXJfc291cmNlX3RyYW5zZmVyIiwKICAiYnVuZGxlX2J5dGVzIjogNTA4MDUsCiAgImJ1bmRsZV9zaGEyNTYiOiAiZjQ2OWM2OGFlMDg4NjM3ZThhYzliMmQ2MWM3YzJhZGQ4ZGVlOTc4MTM3NzUzODg5NTA5OWFmYTEwM2MxYTI4ZCIsCiAgImVuY29kZWRfYnl0ZXMiOiAxNzQzMiwKICAiZW5jb2RlZF9zaGEyNTYiOiAiYzg2NzUwMzVhZDU3NDE3OGI3ZTgzNTcxZjk5MjVkZTg0ODRmOTdlOTMzMDY0YzNlN2E1ZDM2MTJjMjYwMzc2YSIsCiAgImNodW5rcyI6IFsKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDAiLAogICAgICAiYnl0ZXMiOiAzNTAwLAogICAgICAic2hhMjU2IjogImNjNzA0NzU0MTE2ZjQwMGQ0NjNmN2I5ZDZiYWI0MjYyOTMxZDkxNTc5OTIxYWQ1ZjI5MDhmNzVkOGJjNzExYTAiCiAgICB9LAogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wMSIsCiAgICAgICJieXRlcyI6IDM1MDAsCiAgICAgICJzaGEyNTYiOiAiZjk2M2EzZTNkM2JmYTY5ODkzMzRlZWRhMDJkZTczMDgyNTQyMzI2NTljZGU3NjU4NzVhNDkxY2ZjZjkyYWM1NyIKICAgIH0sCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAyIiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICI5YjRlYTg3NmYzMDYxMDZkMDE1NzhlYzM0NmMzMjI4MDc1OTc4ZDdjZmQ3ZWMzOTA1ZjIwYTkzZjI4NDFiNjJmIgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDMiLAogICAgICAiYnl0ZXMiOiAzNTAwLAogICAgICAic2hhMjU2IjogIjdmZTg0MDJmNDMxODAwMGQ4MWU3MTVjZTlkM2NmZDU2MDFjMzYzOGMwZDU0ZWZhMTc2NWFiN2VlNjc5NDI4ZGYiCiAgICB9LAogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wNCIsCiAgICAgICJieXRlcyI6IDM0MzIsCiAgICAgICJzaGEyNTYiOiAiZWIzMjlmMGIwZDJlZThiYTU0NTNmNzg1OTZjNDU0NWE2MDk3ODYyMTNkNmZjZDVjNzcxNjQ4YmY4NzA2OWRmZSIKICAgIH0KICBdLAogICJmaWxlcyI6IFsKICAgIHsKICAgICAgInBhdGgiOiAicnVuLWlvczI2LWZpcnN0Ym9vdC1vd25lci1yZXN1bWUxLnB5IiwKICAgICAgImJ5dGVzIjogNDI0OTAsCiAgICAgICJzaGEyNTYiOiAiODYyYWY1NTI2N2Y3ZWNkMTI3M2ZhZjhmMTYxZTQwNjUxNjFmMWJmNDlhNWRmNjYxNGNmYjI1NzFmYzk1ZDQ3MyIKICAgIH0sCiAgICB7CiAgICAgICJwYXRoIjogImxhdW5jaC1pb3MyNi1maXJzdGJvb3Qtb3duZXItcmVzdW1lMS5weSIsCiAgICAgICJieXRlcyI6IDcyOTksCiAgICAgICJzaGEyNTYiOiAiNDc5NTNhYjkyZWZiZTY4YWU5NjZiNzlmNjA5Yjk4OTI3MzBlODZjNDkwMTIxODk3MzNkNzQ4MzBjNjFiMTIyMCIKICAgIH0KICBdCn0K',validate=True)
if hashlib.sha256(manifest).hexdigest()!='638833f7810d4fcd50c90bf90cb9d9e27368f39baaaab3223a785d89cc9a8414': raise ValueError('manifest differs')
for name in ('run-ios26-firstboot-owner-resume1.py','launch-ios26-firstboot-owner-resume1.py','resume1-owner-install.json'):
 if os.path.lexists(BASE/name): raise ValueError('target already exists; preserve it')
TRANSFER.mkdir(mode=0o700)
save(TRANSFER/'manifest.json',manifest)
print('RESUME1 OWNER TRANSFER CREATED',flush=True)
