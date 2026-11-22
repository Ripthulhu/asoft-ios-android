import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'hfs-header-diagnostic-resume2-transfer'
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
manifest=base64.b64decode('ewogICJzY2hlbWEiOiAxLAogICJraW5kIjogImhmc19oZWFkZXJfZGlhZ25vc3RpY19yZXN1bWUyX3NvdXJjZV90cmFuc2ZlciIsCiAgImJ1bmRsZV9ieXRlcyI6IDIzMzE3LAogICJidW5kbGVfc2hhMjU2IjogImE5Y2U3MGJjZTllNDkxZGQxMmUyZDMxZjU4ZWQxYTdiMTVhY2FhZDU0MTQzOGUyOTA0ZGM3ZjA3NWM0MmZkOGIiLAogICJlbmNvZGVkX2J5dGVzIjogOTUzNiwKICAiZW5jb2RlZF9zaGEyNTYiOiAiZDk5ZTQxNDdhZDYyNGYwOWE1ZTJhMjNmNmU3YWIyYzU3Yjk5OWY4NWMwMTA1NjRjNTc5YTgxYWMwMjExMDEwZSIsCiAgImNodW5rcyI6IFsKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDAiLAogICAgICAiYnl0ZXMiOiAzNTAwLAogICAgICAic2hhMjU2IjogIjQzMzI3YThiNDA5YTU3NDFkMTJjYTBjYzU5NTllOWFhYmVmMWYzZDIxMzc4OTk3NTRlNzYzYjRlOGQyZjA5YzUiCiAgICB9LAogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wMSIsCiAgICAgICJieXRlcyI6IDM1MDAsCiAgICAgICJzaGEyNTYiOiAiMDcyMWFjMWJlMjFiOWExMWUxMWEyZjMxNmJlMjllOGQ5OWE4NWFjMzQ5NGFkODk2ODk0MTQ3YmRiN2Q0MDc0NyIKICAgIH0sCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAyIiwKICAgICAgImJ5dGVzIjogMjUzNiwKICAgICAgInNoYTI1NiI6ICJlMTZlZWQ5NGU0MzNjOWMyODBjZGRhYjhhMmU5NTU3OWE4YjdjZDdmY2U1ZmM3YzhlNmNmZmNkMzMzNDdlNmNkIgogICAgfQogIF0sCiAgImZpbGVzIjogWwogICAgewogICAgICAicGF0aCI6ICJydW4taW9zMjYtaGZzLWhlYWRlci1kaWFnbm9zdGljLXJlc3VtZTIucHkiLAogICAgICAiYnl0ZXMiOiAyMjc0MCwKICAgICAgInNoYTI1NiI6ICJlNzljMGZiYzQ3MmFlMmE4NzUxNjQ1NjU4MDJmZWZmYzRmYWQwYTYzMDU3MTk3MGY2ZTY4ZDcyNTE4MDFiZGNkIgogICAgfQogIF0KfQo=',validate=True)
if hashlib.sha256(manifest).hexdigest()!='02089c6f06b3d9b8f665ecd6500f53c1e8d8d44f01f7c21d389e248fd334739f': raise ValueError('manifest differs')
for name in ('run-ios26-hfs-header-diagnostic-resume2.py', 'hfs-header-diagnostic-resume2-install.json'):
 if os.path.lexists(BASE/name): raise ValueError('target already exists; preserve it')
TRANSFER.mkdir(mode=0o700)
save(TRANSFER/'manifest.json',manifest)
print('HFS HEADER DIAGNOSTIC TRANSFER CREATED',flush=True)
