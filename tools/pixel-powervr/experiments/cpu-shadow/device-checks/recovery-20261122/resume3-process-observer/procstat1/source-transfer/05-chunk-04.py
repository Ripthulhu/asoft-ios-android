import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'resume3-process-observer-procstat1-transfer'
INSTALL=BASE/'resume3-process-observer-procstat1-install.json'
OWNER_SOURCE=BASE/'run-ios26-saved-inspection-resume3.py'
def read(path,limit):
 if path.resolve(strict=True)!=path: raise ValueError('noncanonical input')
 with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
  a=os.fstat(f.fileno())
  if not stat.S_ISREG(a.st_mode) or a.st_uid!=0 or a.st_nlink!=1 or a.st_size>limit: raise ValueError('invalid bounded root-owned file')
  body=f.read(limit+1);b=os.fstat(f.fileno())
 if len(body)!=a.st_size or (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)!=(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns,b.st_ctime_ns): raise ValueError('input changed during read')
 return body
def save(path,body,mode=0o600):
 with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode),'wb') as f:
  os.fchmod(f.fileno(),mode);f.write(body);f.flush();os.fsync(f.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try: os.fsync(fd)
 finally: os.close(fd)
def fresh(files):
 for path in [INSTALL,BASE/'ios26-saved-inspection-resume3-observer-procstat1',BASE/'ios26-saved-inspection-resume3-observer-procstat1-launch.json',BASE/'ios26-saved-inspection-resume3-observer-procstat1-wrapper.log']+[BASE/row['path'] for row in files]:
  if os.path.lexists(path): raise ValueError('fresh observer path required; preserve '+str(path))
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
mb=read(TRANSFER/'manifest.json',1678)
if hashlib.sha256(mb).hexdigest()!='affe3f299edc825a462e69d21f88771fc8c24971eea62b610f6bee6b6e10fc02': raise ValueError('manifest differs')
m=json.loads(mb)
body=b'+hzP+Rvzqz3y4zxkSnd9OTQWXwbi74m3PpZi+Zh51cOL6OTi/PjnXjykylhJSt9/pV+rLMEl76gHBX6hGx/tqkd19gdG5hFSvWXoHdyUFRi9pO8WuPVYX4BZKgBExw/CS1y84RJM62jD78JPH8eGKLXPzldYmF4TzIdxkqS3A36eFeVAtxB/LtCbFuE37ujnTPwkaL2pAjBVAKYawNQGMLUArKUyB0GOMxgx4iQty2/b87HgM99rKz4d+ZR4m2FWfJFU0V3u5Ts+9msX8eRCMOS5hwNCPizgLYOA+R/89+xnJyPXTfzGH30vhWL++zE1EvMSBUWlfKUR5VT+ypn08EKpZARZZZkyZZpsh4XKINDCRXn/O6jQ0xKx7XxUi5qbjii3q7xEWLsJapl2SRgOEkQzKL3DoGGahZkySlgRInt9wqLRyYceBW0QHB1Yphu/yQorSVK2pm8qu6mQcgwrEdJBm25kOfHETvCB8k5UyOtBsL9nTVMewjEpRSD54qTumYD0LsvHzj2+5KjWW0pqoXdSL2insyhJKVL16kiACFv1KS3YOj7PqlaCQoGLiqztTTKXp3alNoYJT+zK99+bRQ7URk76m5GiGI0D6mU0iVOraAEco6FCsqRFDn8tk1WeXqIBFcqkwRbCnM5DSbgsTHpW6SXEUQ/dKdBCfCHaaCOCEtCdrIFhXJoyjmXCuXy9JvHcy3qtokbog2NVCAbeOkGbceun0J2R1/RujdSyGr1GN3E2Z0oyi1/sSGfSrsxPjx5NyAo9s9GmMnN32yNrBZuMFHalN0mGuoxUxHl7AGmJGd25UoA/p39gebb8JftDfwUQo8yGdSDUFHQOrjwjHtiP5N5+U2ZvezTJuRT/lDjCW2qLrT3itmqDlqWJ0Djghii3VbBmkd6182w77lu985Zr1OwNTxzwd+sjqqRJJKwbks4tlYhv+VamOK2irKeO+rI9Tx1KP2DhT/lSp9cmsMqNKht8+J5GVmkZdQN6+dh4/+b476cfUNpxzacxw6WfaVWZLS8u36AutllYUtDaauHVI69sNE/qtmOKuI3pTDa4qntwOcrarqFK391rATGLcoAkUx1REHubi2IdZttHLR4t0kSxKfkt0VTW7gDFJU7soDU1unHxE74/P3t9fHERKfchU+3xm/Bp0R4KOPscJ0KAbu51tNOGzS+1eL+zIpeyjNHMM1QX/hqMxqXu+JfgvdSxVYY3ysA8bXSsH5qMErl8s2B76oZdwSVqStZ9hElTJEs6D+0cq7ferTlsyu/bE0MNAnl4MprceM+96TO/x8rflPU2aEWvUKCf+kJqp72v2LPB9LgYp8fR8Obk/Pj15dn572tLk6lRFey+E1GUe7rw1YvbRV1ZELb+/31F+75C6lvCbn/6rYX3VkKRpyLL9XcDOxYn1cxpLXfigJS9P/vyRKiG4g4lOrPv7ddejPwrLlukUyAibwPGSYCUyzAuon60EMj/uRuZo73DPXUhIxKAv/VOZn/nYL67P989mu9OY/jn4Gj/4EUMf6XP95OXyeH+7jRJX0z3D47SvWT+cjd9cXg0mz6fHe7s7r6M9/eePUwGz9BwwDuije1cnAFZHs9Guw//5X8DG678ZTWxAAA='
if len(body)!=1624 or hashlib.sha256(body).hexdigest()!='25dca8b90df9250e6365e95a55833b77fe86e5d7cf29648e056469913883a173': raise ValueError('chunk differs')
save(TRANSFER/'chunk-04',body)
if read(TRANSFER/'chunk-04',1624)!=body: raise ValueError('chunk readback differs')
print('OBSERVER CHUNK 04 VERIFIED',flush=True)
