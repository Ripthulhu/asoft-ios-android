import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'saved-inspection-resume2-execution-procstat1-transfer'
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
manifest=base64.b64decode('ewogICJzY2hlbWEiOiAxLAogICJraW5kIjogInNhdmVkX2luc3BlY3Rpb25fcmVzdW1lMl9leGVjdXRpb25fcHJvY3N0YXQxX3NvdXJjZV90cmFuc2ZlciIsCiAgImJ1bmRsZV9ieXRlcyI6IDIyOTQxLAogICJidW5kbGVfc2hhMjU2IjogIjhkODYyYzQ3OGUxYzhlNzgyNzljMzA0ZjZmYjYzZWRlZjM3MTg0N2Q0Njg2NTBhODMxNTk3MTNjNjRlM2Q1MDYiLAogICJlbmNvZGVkX2J5dGVzIjogODcwNCwKICAiZW5jb2RlZF9zaGEyNTYiOiAiYTkyNzEyZGMzMDdhOWQ3ZjVkNTQ3ZjhlMTUzMzk2ZDAzOWI5NjUzZTdlZmZmYzcyYWE4NTVjZDcwN2Y1MGVkMyIsCiAgImNodW5rcyI6IFsKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDAiLAogICAgICAiYnl0ZXMiOiAzNTAwLAogICAgICAic2hhMjU2IjogIjgxYTkzYmQwNWMyZWQ3YzhmZDM5NjI1N2M4MzQxYmZmNDgyM2JkNzE3ZDdlODA4ODcyM2IyYjZlMzc0ZWMxNzYiCiAgICB9LAogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wMSIsCiAgICAgICJieXRlcyI6IDM1MDAsCiAgICAgICJzaGEyNTYiOiAiNzY1MjljYWM4MzkwNjc0YzAxMjcwNmQ4NmRlYmJjY2U3Yzg4OGU2MTgwZTUzODA0MDI1YmM3M2YzZjFhMTFkMSIKICAgIH0sCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAyIiwKICAgICAgImJ5dGVzIjogMTcwNCwKICAgICAgInNoYTI1NiI6ICI2OGE0ODEyNzg0MmNlZGQzZjJhMjdlYTYwMGYyOTlhNmJhMGM4MzUzMTI1NDRkYzdlZDljMjZlMzkxYjhjZTI0IgogICAgfQogIF0sCiAgImZpbGVzIjogWwogICAgewogICAgICAicGF0aCI6ICJsYXVuY2gtaW9zMjYtc2F2ZWQtaW5zcGVjdGlvbi1yZXN1bWUyLWV4ZWN1dGUtcHJvY3N0YXQxLnB5IiwKICAgICAgImJ5dGVzIjogMjIyODYsCiAgICAgICJzaGEyNTYiOiAiOGI3OGNhZDI5MTY5N2RiMDk4N2YxMDFlYzQ0ZTY4YzVkZTdiNGVkN2U1MTQzZmY1ZTk0NDRiYjcxNGE5MWEyYiIKICAgIH0KICBdCn0K',validate=True)
if hashlib.sha256(manifest).hexdigest()!='d01a641097a8133a9e4cdedcd726e9d2def2a15c514c2afe87d4e350545cedc4': raise ValueError('manifest differs')
for name in ('launch-ios26-saved-inspection-resume2-execute-procstat1.py', 'saved-inspection-resume2-execution-procstat1-install.json'):
 if os.path.lexists(BASE/name): raise ValueError('target already exists; preserve it')
TRANSFER.mkdir(mode=0o700)
save(TRANSFER/'manifest.json',manifest)
print('SAVED INSPECTION TRANSFER CREATED',flush=True)
