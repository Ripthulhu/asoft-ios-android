import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'saved-inspector-resume3-transfer'
TARGET=Path('/data/local/tmp/pixel-saved-checks-resume3')
INSTALL=BASE/'saved-inspector-resume3-install.json'
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
manifest=base64.b64decode('ewogICJzY2hlbWEiOiAxLAogICJraW5kIjogInNhdmVkX2luc3BlY3Rvcl9yZXN1bWUzX3NvdXJjZV90cmFuc2ZlciIsCiAgInRhcmdldF9kaXJlY3RvcnkiOiAiL2RhdGEvbG9jYWwvdG1wL3BpeGVsLXNhdmVkLWNoZWNrcy1yZXN1bWUzIiwKICAiZnJlc2hfdGFyZ2V0X2RpcmVjdG9yeSI6IHRydWUsCiAgImJ1bmRsZV9ieXRlcyI6IDU0NzQ3LAogICJidW5kbGVfc2hhMjU2IjogIjU4MWM0MTdlNWY2NjI1Y2UyNzA3NGI0YmJjNTc5YTgzMTU1MDQ1OGRmZjY3NDczZjg0NmMwNmMxNjJkNGEyMzMiLAogICJlbmNvZGVkX2J5dGVzIjogMTk0MzYsCiAgImVuY29kZWRfc2hhMjU2IjogImU0YmU0M2ViYWEzZjE2ZDYyOTY1NmNkZWM5ZGUzNmQ4ZjcwODE5M2E4ODNmN2QwZDE1YTBjOGU4MzU4ZDMxNTciLAogICJjaHVua3MiOiBbCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAwIiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICIyMDRmMjQ2YWZmOGQ3MjY0YzRkZGQ4MjM0NWFhMGM4ZjliZDg1ZDA0OGRjNmM1MTA5MjUwN2Y5NzM5N2MxOTc5IgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDEiLAogICAgICAiYnl0ZXMiOiAzNTAwLAogICAgICAic2hhMjU2IjogImE0YTRhZTc2ZDczN2IyZjA5Njg4NGQxNGZlMDk0NGQyMTZkMGQ3ZDBkYzAxNWU1NmIxMGM3MDU4YzAxNjJiNTEiCiAgICB9LAogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wMiIsCiAgICAgICJieXRlcyI6IDM1MDAsCiAgICAgICJzaGEyNTYiOiAiODRkOTFjZmI1Y2FlNDJjMzI2NTAyYmI2YmVhYjViNzdhNDcwZTVjNTkzY2VkNDM4MTQwOGUxZTk4YzNkM2Y3NSIKICAgIH0sCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAzIiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICJhZDI4ZThkMjM1ZDhjNTM1NmFhZDkzM2EzOWI5NmJiZDVhMDJhYzZiNjVmMTI5MjIzOGRhNDU3MTY4YTM2NjIzIgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDQiLAogICAgICAiYnl0ZXMiOiAzNTAwLAogICAgICAic2hhMjU2IjogIjRmZjI1OGY3YTc5NTBkZjYyNWY4YzM4ZjE0OTBmMTExNjNiY2RmMzhkODYxNmU0NTEzNjMwZDZhNGMzODEwMTYiCiAgICB9LAogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wNSIsCiAgICAgICJieXRlcyI6IDE5MzYsCiAgICAgICJzaGEyNTYiOiAiODg1NTk1N2VhNDM3NzVkZDczNzMwNGY5ZGE5ZDJiMWQ5ZGFlZjAwZTIzMjA4ZjVjZmFjMjhkODcxZjljYWQ5OSIKICAgIH0KICBdLAogICJmaWxlcyI6IFsKICAgIHsKICAgICAgInBhdGgiOiAiaW5zcGVjdF9pb3MyNl9maXJzdGJvb3QucHkiLAogICAgICAiYnl0ZXMiOiAzMjU3NiwKICAgICAgInNoYTI1NiI6ICIyNDUzOTNiZjU5YjllNzMxZmE5ZjUxMWI5MzY4ZTU2NzZmODZhOGFkMGQ2YjhlMDM4NTllNzMyMzliZjg1NTljIgogICAgfSwKICAgIHsKICAgICAgInBhdGgiOiAiaW5zcGVjdF9pb3MyNl9maXJzdGJvb3RfZ3Vlc3QucHkiLAogICAgICAiYnl0ZXMiOiAxODk3OSwKICAgICAgInNoYTI1NiI6ICJmNTJlNGQ0ZWM3OGMwOGJmNzNlYzM3ZWZhYzhhYTZlY2I5OWE1YWIyYmFmMTc0NDgxZmRhOGIyODZmYjQ5ZDk3IgogICAgfQogIF0KfQo=',validate=True)
if hashlib.sha256(manifest).hexdigest()!='95faa2f0adc715771bf6b35c7cf7601913206974e0a21db6476e472d48f35933': raise ValueError('manifest differs')
if os.path.lexists(TARGET): raise ValueError('preserve existing inspector source directory')
if TARGET.parent.resolve(strict=True)!=TARGET.parent: raise ValueError('noncanonical inspector parent')
for name in ('inspect_ios26_firstboot.py', 'inspect_ios26_firstboot_guest.py'):
 if os.path.lexists(TARGET/name): raise ValueError('source exists; preserve it')
if os.path.lexists(INSTALL): raise ValueError('install receipt exists; preserve it')
TRANSFER.mkdir(mode=0o700)
save(TRANSFER/'manifest.json',manifest)
print('REVIEWED SOURCE TRANSFER CREATED; NO EXECUTION',flush=True)
