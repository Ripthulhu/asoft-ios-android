import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'saved-inspection-resume4-execution-procstat1-transfer'
TARGET=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
INSTALL=BASE/'saved-inspection-resume4-execution-procstat1-install.json'
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
manifest=base64.b64decode('ewogICJzY2hlbWEiOiAxLAogICJraW5kIjogInNhdmVkX2luc3BlY3Rpb25fcmVzdW1lNF9leGVjdXRpb25fcHJvY3N0YXQxX3NvdXJjZV90cmFuc2ZlciIsCiAgInRhcmdldF9kaXJlY3RvcnkiOiAiL2RhdGEvbG9jYWwvdG1wL3BpeGVsLWdwdS10cmFuc2Zlci1zeHR2MzNzaCIsCiAgImZyZXNoX3RhcmdldF9kaXJlY3RvcnkiOiBmYWxzZSwKICAiYnVuZGxlX2J5dGVzIjogMjI5NjQsCiAgImJ1bmRsZV9zaGEyNTYiOiAiNjU5M2JmY2ZmODM2ZTFlNjYzYjY3YzcwMTE4NjYyMTdkMjBhZTk2ZTk2OGM1ODAxMzM0ODI5ZjYyYzEyMGY5OCIsCiAgImVuY29kZWRfYnl0ZXMiOiA4Njg0LAogICJlbmNvZGVkX3NoYTI1NiI6ICIxZWVmZDVjMjYxMDNhM2MwYzFiMjg1MTc5Yjk1OTMxMjAxNTIyMzZhMzMxMTdhODFlN2U3Y2RhNDVlYjI1Nzg3IiwKICAiY2h1bmtzIjogWwogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wMCIsCiAgICAgICJieXRlcyI6IDM1MDAsCiAgICAgICJzaGEyNTYiOiAiYjk0ZmFhM2FlNGI2NDQyNmM5Y2M1MTc1ZTNhYjgxOWJiODhjMjEyMWRiMThjOTk2MjliNzk0YTkwMzc0ZTIxNiIKICAgIH0sCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAxIiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICJmOWI5N2I1ZjRhODc2MmRiMjk5MDNhMzRiNTlhMzRhNTc3M2IwNjhjZWNjZTA4ZmVhNzU2Njc4NWJmMjIyOTY5IgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDIiLAogICAgICAiYnl0ZXMiOiAxNjg0LAogICAgICAic2hhMjU2IjogIjZiZTc2OWNjM2I4MTgyMmIwNGU1MjljZmUzZjA5MzdlMmM5NWVlYzYxMzNjOGUwNDJlNDlkNDUyZjM0ZTk0ZWMiCiAgICB9CiAgXSwKICAiZmlsZXMiOiBbCiAgICB7CiAgICAgICJwYXRoIjogImxhdW5jaC1pb3MyNi1zYXZlZC1pbnNwZWN0aW9uLXJlc3VtZTQtZXhlY3V0ZS1wcm9jc3RhdDEucHkiLAogICAgICAiYnl0ZXMiOiAyMjMwOSwKICAgICAgInNoYTI1NiI6ICJmZGExNTg1MDYxNzQ1OTRhMDEzNjZkMmM2ZmIyZDFhNGQ3NjI4ZmNhNzgzZWY4OWQ3ZTBhOGQ1YzQ5MDMwNmY1IgogICAgfQogIF0KfQo=',validate=True)
if hashlib.sha256(manifest).hexdigest()!='1e33809a2e49ff421b4afcf40ff15c17d071abc46bf920e9953edebac980e6b2': raise ValueError('manifest differs')
if TARGET!=BASE: raise ValueError('unexpected existing source target')
for name in ('launch-ios26-saved-inspection-resume4-execute-procstat1.py',):
 if os.path.lexists(TARGET/name): raise ValueError('source exists; preserve it')
if os.path.lexists(INSTALL): raise ValueError('install receipt exists; preserve it')
TRANSFER.mkdir(mode=0o700)
save(TRANSFER/'manifest.json',manifest)
print('REVIEWED SOURCE TRANSFER CREATED; NO EXECUTION',flush=True)
