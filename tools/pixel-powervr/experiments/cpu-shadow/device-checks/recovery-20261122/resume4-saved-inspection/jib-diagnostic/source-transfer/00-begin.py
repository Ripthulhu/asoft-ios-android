import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'root-jib-diagnostic-resume4-transfer'
def read(path,limit):
 if path.resolve(strict=True)!=path: raise ValueError('noncanonical transfer path')
 with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
  a=os.fstat(f.fileno())
  if not stat.S_ISREG(a.st_mode) or a.st_nlink!=1 or a.st_uid!=0 or a.st_size>limit: raise ValueError('invalid transfer file')
  b=f.read(limit+1);z=os.fstat(f.fileno())
 if len(b)!=a.st_size or len(b)>limit or (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)!=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns): raise ValueError('transfer input changed or exceeded bound')
 return b
def save(path,body,mode=0o600):
 with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode),'wb') as f:
  f.write(body);f.flush();os.fsync(f.fileno())
 d=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try: os.fsync(d)
 finally: os.close(d)
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
manifest=base64.b64decode('ewogICJzY2hlbWEiOiAxLAogICJraW5kIjogInJvb3RfamliX2RpYWdub3N0aWNfcmVzdW1lNF9zb3VyY2VfdHJhbnNmZXIiLAogICJidW5kbGVfYnl0ZXMiOiA0MjQxNSwKICAiYnVuZGxlX3NoYTI1NiI6ICIwZDhhMzA2MTFiMDM2M2FiYzc3MWFhMDQzOGY4ZTIwYmYyZWQ2OWVkYjBjMGZhNzdlZTZmMzQ4YzBlMDYwNzM3IiwKICAiZW5jb2RlZF9ieXRlcyI6IDE1NTMyLAogICJlbmNvZGVkX3NoYTI1NiI6ICJmNzMxNjgwMjE3OWJmMTdkYmQ5ZTRkYmU2ZDIyNDQ1MGZkNTgwOTUyMWMzMWRjODU1MjI4NjUyMDcxNGQwZWE1IiwKICAiY2h1bmtzIjogWwogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wMCIsCiAgICAgICJieXRlcyI6IDM1MDAsCiAgICAgICJzaGEyNTYiOiAiMDA4N2M5YjFmYjY1ODI2OWM4YWM0YWUyYTMzZDVkYzYyZDRmYjA0MTRhMTk5ZGIwMjIwYzJiNDNmNThlZWY3YiIKICAgIH0sCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAxIiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICIzNzU0MzY1Mzk3M2YzMGVhZmE3M2E4MWZmY2I2N2I5NmJhYjFlMjU2YWRiYzg3YjY5NjBhZDNmNDAwNTE0ODEyIgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDIiLAogICAgICAiYnl0ZXMiOiAzNTAwLAogICAgICAic2hhMjU2IjogIjA4NWIwODUwNzQ5MjRiOGRjNDQxOTAzMGFlOTUzMTJjMDA5NjM1OTI5MzJiMDdlYzEzMGQ5ZjcwZmNkOTE1NDEiCiAgICB9LAogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wMyIsCiAgICAgICJieXRlcyI6IDM1MDAsCiAgICAgICJzaGEyNTYiOiAiYmQ3ZTVhOTUxMGM5YzBkYjE3OGVlZDhlMmRmMmZmOTFlMjNlMWM4YWRkYmU2OTFmNTU0MjViZjU2ZWM4ZDFjZSIKICAgIH0sCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTA0IiwKICAgICAgImJ5dGVzIjogMTUzMiwKICAgICAgInNoYTI1NiI6ICJiYWI2ZDc4NWVmMDc4YmJhMjUxMGRmYzhkNDY2MGFiNzBlM2RhOTQ2NmUxMDI0MzZjOWNkOWVkZDc5OWVkNmJkIgogICAgfQogIF0sCiAgImZpbGVzIjogWwogICAgewogICAgICAicGF0aCI6ICJydW4taW9zMjYtcm9vdC1qaWItZGlhZ25vc3RpYy1yZXN1bWU0LnB5IiwKICAgICAgImJ5dGVzIjogNDE1NDQsCiAgICAgICJzaGEyNTYiOiAiY2YzMWJmMzQ4OWJlZDY0NWRiZDU5ZjhlMDI0ZjY3NTkxNTBmOTI2MmYxNDgwZTZkOWQ0ZmY1M2Y4NTViOTQ4MCIKICAgIH0KICBdCn0K',validate=True)
if len(manifest)!=1227 or hashlib.sha256(manifest).hexdigest()!='fd168adace896ed166cfbba7e770f0ff9623b8f6659cad9de3c97f5584bcd5c6': raise ValueError('manifest differs')
for name in ('run-ios26-root-jib-diagnostic-resume4.py', 'root-jib-diagnostic-resume4-install.json', 'ios26-root-jib-diagnostic-resume4'):
 if os.path.lexists(BASE/name): raise ValueError('target already exists; preserve it')
TRANSFER.mkdir(mode=0o700)
save(TRANSFER/'manifest.json',manifest)
print('ROOT JIB DIAGNOSTIC TRANSFER CREATED',flush=True)
