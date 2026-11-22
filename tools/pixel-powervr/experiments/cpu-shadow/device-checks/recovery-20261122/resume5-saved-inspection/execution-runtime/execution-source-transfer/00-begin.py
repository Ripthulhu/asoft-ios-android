import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'saved-inspection-resume5-execution-procstat1-transfer'
TARGET=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
INSTALL=BASE/'saved-inspection-resume5-execution-procstat1-install.json'
def read(path,limit):
 if path.resolve(strict=True)!=path: raise ValueError('noncanonical transfer path')
 with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
  a=os.fstat(f.fileno())
  if not stat.S_ISREG(a.st_mode) or a.st_nlink!=1 or a.st_uid!=0 or a.st_size>limit: raise ValueError('invalid transfer input')
  b=f.read(limit+1)
  z=os.fstat(f.fileno())
 if len(b)!=a.st_size or len(b)>limit or (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)!=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns): raise ValueError('transfer input changed')
 return b
def save(path,body,mode=0o600):
 with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode),'wb') as f:
  f.write(body);f.flush();os.fsync(f.fileno())
 d=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try: os.fsync(d)
 finally: os.close(d)
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
manifest=base64.b64decode('ewogICJzY2hlbWEiOiAxLAogICJraW5kIjogInNhdmVkX2luc3BlY3Rpb25fcmVzdW1lNV9leGVjdXRpb25fcHJvY3N0YXQxX3NvdXJjZV90cmFuc2ZlciIsCiAgInRhcmdldF9kaXJlY3RvcnkiOiAiL2RhdGEvbG9jYWwvdG1wL3BpeGVsLWdwdS10cmFuc2Zlci1zeHR2MzNzaCIsCiAgImZyZXNoX3RhcmdldF9kaXJlY3RvcnkiOiBmYWxzZSwKICAiYnVuZGxlX2J5dGVzIjogMjMzMTAsCiAgImJ1bmRsZV9zaGEyNTYiOiAiMmU3YTkwOWYyZDgxZDg1MjQwOWU4OWNjM2ZiZGRkZjllODc1Yjc0YjJmMzBjNWU4NDhhYTljYzYzNDhhMGYwOCIsCiAgImVuY29kZWRfYnl0ZXMiOiA4NzM2LAogICJlbmNvZGVkX3NoYTI1NiI6ICI2YWQ5YThiMzBmMDhmZmRmZjQ0YzViZjVkZGU1ZjIxYzNiMjdlNDI4MjRlOGYyYzYwOGU1NjAwZjgyNzM3NTk5IiwKICAiY2h1bmtzIjogWwogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wMCIsCiAgICAgICJieXRlcyI6IDM1MDAsCiAgICAgICJzaGEyNTYiOiAiZGQxZjQ2MGQxNGQwOWNkMWFmY2Y1MzFjNmRlYjM3MTk0MDFkNzVmMTQ4M2JiOGI5Y2Q2OTZkMjA2ZjRhYjY4NCIKICAgIH0sCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAxIiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICJjMDdlOTNmNzYzMzUxNDYxMjIwYTIyNTg4Y2MzOTg3YjRhNjE4MWQ4NDVjZTk4NDE0NTZjNDk5OTEzYzkwNjc5IgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDIiLAogICAgICAiYnl0ZXMiOiAxNzM2LAogICAgICAic2hhMjU2IjogIjRkMTdkOGE1NDcyMWEyZDY4YzlhNzRkNzU3NTc1MGYwN2I3OTgzNWQ1NjE4ZjQ3MzBjODI2NDdkM2NlYWZjM2MiCiAgICB9CiAgXSwKICAiZmlsZXMiOiBbCiAgICB7CiAgICAgICJwYXRoIjogImxhdW5jaC1pb3MyNi1zYXZlZC1pbnNwZWN0aW9uLXJlc3VtZTUtZXhlY3V0ZS1wcm9jc3RhdDEucHkiLAogICAgICAiYnl0ZXMiOiAyMjY1MCwKICAgICAgInNoYTI1NiI6ICJhZGU3MWZiYzI1Mjk0ZjhhNWIxNGY5M2E4ZGYwYzBmMTRlYmRkNGJkZDY5OWU3Y2EyY2NiYTAwNGVkZWI1YWFiIgogICAgfQogIF0KfQo=',validate=True)
if hashlib.sha256(manifest).hexdigest()!='5501c4724d4c6231b557e1eff72127e054231615987b4aa29615ae0974777fdf': raise ValueError('manifest differs')
if TARGET!=BASE: raise ValueError('unexpected existing source target')
for name in ('launch-ios26-saved-inspection-resume5-execute-procstat1.py',):
 if os.path.lexists(TARGET/name): raise ValueError('source exists; preserve it')
if os.path.lexists(INSTALL): raise ValueError('install receipt exists; preserve it')
TRANSFER.mkdir(mode=0o700)
save(TRANSFER/'manifest.json',manifest)
print('REVIEWED SOURCE TRANSFER CREATED; NO EXECUTION',flush=True)
