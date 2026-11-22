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
if TRANSFER.resolve(strict=True)!=TRANSFER: raise ValueError('transfer directory differs')
mb=read(TRANSFER/'manifest.json',975)
if hashlib.sha256(mb).hexdigest()!='d01a641097a8133a9e4cdedcd726e9d2def2a15c514c2afe87d4e350545cedc4': raise ValueError('manifest differs')
body=b'/dKyMGncsn6QuUYq6LrEa7UIlJXihlHL0vVBuovpW0eaTXU6jE+aDjBrQMWsP0RrsqCd+NTZ4YfiVh6dh5jgTyiEVHQrb4bqBWJRGFZrXnpBGA+Wn7yipKtd8+TtuLjau0uSVEX7nXEOfu9yK2VeGqbqNV527lue8ONHjDhN/OwrK0jyifNXYWCddzAd6j11B1wDL6Ypnhued3HnWGnlbvd3VW43P/rJ4/HM4YDlE2gaRvqiGIbSfKmHOThs1CgkmXJtAIBqXzSyd9QioNbue1UfXiutIF8xjpGVxcTZbcOlLNdSYU3qT7Ubu1NfMXWTcvSiUqzcV331OSYZxVODo92QF1qE3or//Vq9I//+enF6K74s/nh/YV6eb1ndZNzt6uhp8YVvrbnVA21Cd9J8z32bYonkiXX1CtmcvamgnBoUURzgZtNwzi/fX/328WJxu0AkRRWO3wvVrkVUHMAtrDPtIXxJZh22aBya0iEpbG3xvQJdzT2Y+evXvwKpuCyIOpqVuMAIsMvf4GMhP84Wny8/XVwwVgYkxenYN7dn4KzZ1Yw08lyyFFcc1pc3K2XbgbwV71cerrxF5bbGgxGlVuUeuvTwFABTNHhFjZZOYTviQrMnefqsSDtwz5AFtKT/uiBUvFCCDYXbr+50tSJBy/JkC5cRRR4DjLcKv/gRTCne0Nb5SEmUIkL30InSzvcSbUl2+QmjfU+m3tKvjeL2U/GxbdiySpvuhG0rGtgBuzLmbanRCOdPcb2rCPhYoRzPDlYAcEWB/e2b089gd8ACfVy8pwkcI5VTJMw116dRHl2N+L47sSQFFj1PVO5tho4qTPPgizRKbwkUxR0ZDBoGCV9BAfr4Hbi6C/onfRlChs/nB3hUVqcVACyPjP1ptgLQNjviehI4cXbxlg9s0pjJdqFy9rROErKtCyYhcITGY7G0wrcC7nvrktCDdPT1i7gGNG0Aqpx0rFOLY5Lc27jP8kAimB082K/iKlTbT+Jv6BJl0szRA58sQyGeZeKwP+bLMQLsiLd+xHgjoIrp+nU4mBg1dUVHXWNVaJbCqKN2sbn0hMEJc25qdQ3+UIcx2G22AkuL92UvuYvzk36zDMUvgDylUU4a9t1dbNd3Cte77KFR0U5fnvMc+3tensMK4CIUKrQ0RluV7/Q5O78Gib66/tNAUuahRoEcwwArr5oCSrlcCVoNJkGK9dJzH/x5Eb/i9URU6o8ntAjM8dE3euJ5QPF2z85peg++eJx/pC2NgGR+GlFZP3GcIPEdp6mCdtwgcFwO07DbbW4/2lQSisKsiMxUHfwqDKIyqyFoURVxEsnb5QdQsfu9/xIKal3aLIN3CBXaTjQlDCP9hTgzyv9mle9QOLtqnqFo36b4NhwpYFkhYVKy8HIDSEfZyNH90EU1WaGb32TALII1w75mDvaYghLRhiNfuNt7SOCm43rx4dMN9Lm61pzyfU4DNyjzV5mT/ZhENsER2RVHvAQoE5miA/zvM0mERZA0IO8dB+USb9Jy6aVm+oYeqFt8jfIGFVtUY0etIyoKR/N+vz8dt44woXE0P3rdGyLFO2DVVy4CRiaegGXqTaa+G/RnvfFsEnjd2XQS9ro94g+HZDz1RwGZeEMSTMioNxyE4YjMhsOh5016Q3fWc/ve0cuqdYSBGeCqDe8Ln16SIUJ+pIVujaN57+Xf/hdkluttnVkAAA=='
if len(body)!=1704 or hashlib.sha256(body).hexdigest()!='68a48127842cedd3f2a27ea600f299a6ba0c835312544dc7ed9c26e391b8ce24': raise ValueError('chunk differs')
save(TRANSFER/'chunk-02',body)
if read(TRANSFER/'chunk-02',1704)!=body: raise ValueError('chunk readback differs')
print('SAVED INSPECTION CHUNK 02 VERIFIED',flush=True)
