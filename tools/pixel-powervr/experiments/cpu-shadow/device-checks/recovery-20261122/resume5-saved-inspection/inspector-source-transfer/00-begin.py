import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'saved-inspector-resume5-transfer'
TARGET=Path('/data/local/tmp/pixel-saved-checks-resume5')
INSTALL=BASE/'saved-inspector-resume5-install.json'
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
manifest=base64.b64decode('ewogICJzY2hlbWEiOiAxLAogICJraW5kIjogInNhdmVkX2luc3BlY3Rvcl9yZXN1bWU1X3NvdXJjZV90cmFuc2ZlciIsCiAgInRhcmdldF9kaXJlY3RvcnkiOiAiL2RhdGEvbG9jYWwvdG1wL3BpeGVsLXNhdmVkLWNoZWNrcy1yZXN1bWU1IiwKICAiZnJlc2hfdGFyZ2V0X2RpcmVjdG9yeSI6IHRydWUsCiAgImJ1bmRsZV9ieXRlcyI6IDYxOTY3LAogICJidW5kbGVfc2hhMjU2IjogImJlZTk4MDJhMTkyZTFlMzg1YWM4MGFjNDA1ZGQxZjVjMmJiOTExNzBiNmFmNmQ3MWZmYjM4MDZiMmY0ODRiOWQiLAogICJlbmNvZGVkX2J5dGVzIjogMjA4NTIsCiAgImVuY29kZWRfc2hhMjU2IjogImM3NmQ0YTkxNGU1YmI1MTlmNzc4MzA2N2FlYmI0NWQ4YmFkNmQ3ZWFlMmM5ZDBmNDE3YTRlNTI5MzNlODhkZTgiLAogICJjaHVua3MiOiBbCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAwIiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICJjZGE3ZDFmNDQ2Y2RmMzZkMWE2ODNjYTkxYTI0NmU3YWIwODVmYzM1YWMzNGFhY2I2ZWM2MTUxMTczZDM0ZTUyIgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDEiLAogICAgICAiYnl0ZXMiOiAzNTAwLAogICAgICAic2hhMjU2IjogImRkMTU2MmMxNjY4ZjA0N2Y0M2Q5NjIxNTllYmJlZTI3ZWZlY2ZjODRhNTdkZDlkNmY2NGE1MDBjNTRlODVmYjUiCiAgICB9LAogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wMiIsCiAgICAgICJieXRlcyI6IDM1MDAsCiAgICAgICJzaGEyNTYiOiAiNDNmOTkwZjAxZmY5NzFhNTNhZDYwZGRkMGQyOGMzZTU0ZWUyNWYyNWU4MGI1M2Y3YWY5Njk3ZGZjNmQ5ZmQ0YiIKICAgIH0sCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAzIiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICI3Y2IxNTY4MTNkNTU5ODBjOGIzODBkNDUxNTY3NjQ1OTZjMGY0MTJjNjgyOTg0OGM5NGNmNGU5NmEzNGIwMjUwIgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDQiLAogICAgICAiYnl0ZXMiOiAzNTAwLAogICAgICAic2hhMjU2IjogIjY5MGUxNGMzOTRkYjk1YmFkY2VjMGJmYjNiYTBmOWJkNmRhMmJiMTMyODM4YjQ0YjAzZmQyZGUyMjU4NGRiZTEiCiAgICB9LAogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wNSIsCiAgICAgICJieXRlcyI6IDMzNTIsCiAgICAgICJzaGEyNTYiOiAiOTkzYzEyNTA1YjUxZjBkZjliMmJkM2UwMWQ5YWNkNThhNzViZTY2NTJlMTliNGY5YzIxNzc5YzE0ZWE4NjU0NSIKICAgIH0KICBdLAogICJmaWxlcyI6IFsKICAgIHsKICAgICAgInBhdGgiOiAiaW5zcGVjdF9pb3MyNl9maXJzdGJvb3QucHkiLAogICAgICAiYnl0ZXMiOiAzNzQ0NCwKICAgICAgInNoYTI1NiI6ICIzMGVhYWZmYzQyYWE3M2JmOTU0ODhmM2NhNTA0ZDdjNTYzNDRmYmFkYTBhYWVkNzQ2OTA0ZWQxZjRmNzhmZDNlIgogICAgfSwKICAgIHsKICAgICAgInBhdGgiOiAiaW5zcGVjdF9pb3MyNl9maXJzdGJvb3RfZ3Vlc3QucHkiLAogICAgICAiYnl0ZXMiOiAyMDkyOSwKICAgICAgInNoYTI1NiI6ICI5NmM1NTliYWMxOWEzYzM2YTRlMjZjMmNmNTdiNzVjYmFmZGZkNTg3OWRlNmU0ZmNlYjU4MmIyYzA3YTliNTFhIgogICAgfQogIF0KfQo=',validate=True)
if hashlib.sha256(manifest).hexdigest()!='c4cb64bb0d5b7ae281b2bd54b755db3231b8870abc4de54b45841e09fc591efd': raise ValueError('manifest differs')
if os.path.lexists(TARGET): raise ValueError('preserve existing inspector source directory')
if TARGET.parent.resolve(strict=True)!=TARGET.parent: raise ValueError('noncanonical inspector parent')
for name in ('inspect_ios26_firstboot.py', 'inspect_ios26_firstboot_guest.py'):
 if os.path.lexists(TARGET/name): raise ValueError('source exists; preserve it')
if os.path.lexists(INSTALL): raise ValueError('install receipt exists; preserve it')
TRANSFER.mkdir(mode=0o700)
save(TRANSFER/'manifest.json',manifest)
print('REVIEWED SOURCE TRANSFER CREATED; NO EXECUTION',flush=True)
