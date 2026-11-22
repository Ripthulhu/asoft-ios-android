import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'data-journal-diagnostic-resume5-transfer'
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
manifest=base64.b64decode('ewogICJzY2hlbWEiOiAxLAogICJraW5kIjogImRhdGFfam91cm5hbF9kaWFnbm9zdGljX3Jlc3VtZTVfc291cmNlX3RyYW5zZmVyIiwKICAiYnVuZGxlX2J5dGVzIjogNjgzOTYsCiAgImJ1bmRsZV9zaGEyNTYiOiAiODM1YWNmM2Y3ZmFlNjZkMmUxM2FlMTcxNGI3YWU2YTE2OWIxZmI2YzQwMzVjNWE0MjA0ZDk0NmU3NmM2MzQwNCIsCiAgImVuY29kZWRfYnl0ZXMiOiAyMzQyNCwKICAiZW5jb2RlZF9zaGEyNTYiOiAiNGYwNTdiYjhiMzE2YjQ3YzFiYzI5N2Q2Zjg3NzY3NTk4NWRkMTUxMGI3NDg2YTZkNmZiOTYwZTMzZTc0OTEzZiIsCiAgImNodW5rcyI6IFsKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDAiLAogICAgICAiYnl0ZXMiOiAzNTAwLAogICAgICAic2hhMjU2IjogImJhZDQyOGRhMzVhZDY3YjM3ZDg3ZWU4NWZiYWU1MzI2MzdjOGVkODliMGJkZTBiOTY5NWQyOTRkNTNjOTNjOWMiCiAgICB9LAogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wMSIsCiAgICAgICJieXRlcyI6IDM1MDAsCiAgICAgICJzaGEyNTYiOiAiZWNlNTI0YjY0ZDcxZTg0NDg0MmE1ZTkwMWExMTJiZDYzNDlmOTBjZWQ0MGQ4MjgxODdjMzU0YzRiMDEwMzdhMiIKICAgIH0sCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTAyIiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICI3MjQyODM4ODFhMjMzN2Q3OThkZTYzYmNlYjYyNTVjNDM3MTljYzBjMzllNTY0MTJhZDdkMGJjZGM2NTAyMWU0IgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDMiLAogICAgICAiYnl0ZXMiOiAzNTAwLAogICAgICAic2hhMjU2IjogIjhkZDAwZjNlMGQ0NjYwMjI1ZTg5Y2Q4YzcxMjQ3NjU3MWQ3M2U5YWJmMTI4NmIwYjk5Y2YwMGMxMjViMTk4MDQiCiAgICB9LAogICAgewogICAgICAibmFtZSI6ICJjaHVuay0wNCIsCiAgICAgICJieXRlcyI6IDM1MDAsCiAgICAgICJzaGEyNTYiOiAiNjljODkxMzUyMGY5NzM1Nzc0YThhZTdmYjI4YjllZTQ4ZjQ3MWI3ODY4MTk1YjgxOTQ0Y2Y0OWFhNmVmZmNjZSIKICAgIH0sCiAgICB7CiAgICAgICJuYW1lIjogImNodW5rLTA1IiwKICAgICAgImJ5dGVzIjogMzUwMCwKICAgICAgInNoYTI1NiI6ICIyNmJjOWVkODgyOWIwYjgwZTQ2YzU5OTk1NmFjMTM3MDY2YzgxZjQ3ZTgyODA0MDg3Y2RkZTc4NjIzMWRmYTJjIgogICAgfSwKICAgIHsKICAgICAgIm5hbWUiOiAiY2h1bmstMDYiLAogICAgICAiYnl0ZXMiOiAyNDI0LAogICAgICAic2hhMjU2IjogIjU2M2Y5NThmZTA0ZTZiNzZmNGNjMjU5NTM0MzEzNzgzZjA4YTcyNTBkYjhhOTUyYjc5Y2I2OWU5OGE4OGYwODgiCiAgICB9CiAgXSwKICAiZmlsZXMiOiBbCiAgICB7CiAgICAgICJwYXRoIjogInJ1bi1pb3MyNi1kYXRhLWpvdXJuYWwtZGlhZ25vc3RpYy1yZXN1bWU1LnB5IiwKICAgICAgImJ5dGVzIjogNTE5MjMsCiAgICAgICJzaGEyNTYiOiAiODUxOTRhZjllMTRmNjhlMTZkMTk5MGU3OTYwMzA2MDY0NGE4OTJjNzcyYWRhZmM1MWRjNTI3NzcwNTVjNzdjOSIKICAgIH0sCiAgICB7CiAgICAgICJwYXRoIjogInBhcnNlLWlvczI2LWRhdGEtam91cm5hbC1yZXN1bWU1LnB5IiwKICAgICAgImJ5dGVzIjogMTQ2MTcsCiAgICAgICJzaGEyNTYiOiAiNDAzNjA1NWI0OTBmNWZkOTNhNzRlNmQxMmRlMTJmNTExZGU0NWU4ZTBmNjJkZmE4MTQxOTE1MWZjMmRjYzg1MiIKICAgIH0KICBdCn0K',validate=True)
if len(manifest)!=1692 or hashlib.sha256(manifest).hexdigest()!='fb21a4782fa6f5bf04edac463df6cf6a2a6767102d969135085d53128d45d65d': raise ValueError('manifest differs')
for name in ('run-ios26-data-journal-diagnostic-resume5.py', 'parse-ios26-data-journal-resume5.py', 'data-journal-diagnostic-resume5-install.json', 'ios26-data-journal-diagnostic-resume5'):
 if os.path.lexists(BASE/name): raise ValueError('target already exists; preserve it')
TRANSFER.mkdir(mode=0o700)
save(TRANSFER/'manifest.json',manifest)
print('DATA JOURNAL DIAGNOSTIC TRANSFER CREATED',flush=True)
