import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'saved-inspection-resume1-transfer'
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
manifest=base64.b64decode('ewogICJzY2hlbWEiOiAxLAogICJraW5kIjogInNhdmVkX2luc3BlY3Rpb25fcmVzdW1lMV9zb3VyY2VfdHJhbnNmZXIiLAogICJidW5kbGVfYnl0ZXMiOiAzMjA0MCwKICAiYnVuZGxlX3NoYTI1NiI6ICJjOGQ0MTRmZDQwZjFhNjBlZjEyYTNhOTY2OGQ5NjNmNDBmZjQwZDBkYjRlNjQ2N2I1MWM5NDViMDg1ODRkN2VmIiwKICAiZW5jb2RlZF9ieXRlcyI6IDEyMDYwLAogICJlbmNvZGVkX3NoYTI1NiI6ICI4NzExZDlkYTVkYzlhYmJhNjBlMmNlNGZhZjA4YmU3ZWQ0ZGFjMGMyZTQ0YTBiYjIxN2Y0ZjNlNzYyZjI2NTZlIiwKICAiY2h1bmtzIjogWwogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wMCIsCiAgICAgICJieXRlcyI6IDM1MDAsCiAgICAgICJzaGEyNTYiOiAiM2MxMDAzNzcyZjY0M2YxNTVjZGI5MDg3Y2ZiOTZjZmY5NzljYWZmYjQ1ZWU2YzlhMjExYjkxYWMwZTcyNWZmYyIKICAgIH0sCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAxIiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICJkODU5NGQ4NmJlYjZiZjQ2NzBiNTVlMTIxODQxODUzN2JkZWUzMzg3NTFlYWQwN2Q3YjYzODI2YjRjMDEyNzIzIgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDIiLAogICAgICAiYnl0ZXMiOiAzNTAwLAogICAgICAic2hhMjU2IjogIjA3NTI0MGYwYjI4MmE3ODc2NjY1MzI4MGQ4Y2E0NmRhOGY5ZTY2Yjk5NTNmMzM4NGI2NTM0N2E0OGIxNjc0NWIiCiAgICB9LAogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wMyIsCiAgICAgICJieXRlcyI6IDE1NjAsCiAgICAgICJzaGEyNTYiOiAiYTIyZTY4YzU0ZDFkZmJjMWJkMmNjNTVmNjNhODFlYzI2ZjY5MzNhZDI2OTY0YzQ2MTdlYjk3MDExNDI0MDVhYSIKICAgIH0KICBdLAogICJmaWxlcyI6IFsKICAgIHsKICAgICAgInBhdGgiOiAicnVuLWlvczI2LXNhdmVkLWluc3BlY3Rpb24tcmVzdW1lMS5weSIsCiAgICAgICJieXRlcyI6IDI1MTY4LAogICAgICAic2hhMjU2IjogIjg3NTI2ZWU0MjQxNzEwOGY0NmE4Y2EwM2IzZmVjZTFjZDE1NGYyYzQzOWE5YzY0OTJmMjBjOTdmZDY5ODFiYjkiCiAgICB9LAogICAgewogICAgICAicGF0aCI6ICJsYXVuY2gtaW9zMjYtc2F2ZWQtaW5zcGVjdGlvbi1yZXN1bWUxLXByZWZsaWdodC5weSIsCiAgICAgICJieXRlcyI6IDU5MjYsCiAgICAgICJzaGEyNTYiOiAiZTRiNzhmYmI1MDRiYTA0NDQyNmMwYTNmZWVhMWFlNmRmZWM4Yjc0MGY0OGYzZDI2N2JlNDNhN2I1OGUyNmZkYSIKICAgIH0KICBdCn0K',validate=True)
if hashlib.sha256(manifest).hexdigest()!='cc5cb704e57d274676130c4fcb634cd4ace5232bb9be83a059548cbb60022ce4': raise ValueError('manifest differs')
for name in ('run-ios26-saved-inspection-resume1.py', 'launch-ios26-saved-inspection-resume1-preflight.py', 'saved-inspection-resume1-install.json'):
 if os.path.lexists(BASE/name): raise ValueError('target already exists; preserve it')
TRANSFER.mkdir(mode=0o700)
save(TRANSFER/'manifest.json',manifest)
print('SAVED INSPECTION TRANSFER CREATED',flush=True)
