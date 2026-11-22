import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'saved-inspection-resume2-execution-transfer'
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
mb=read(TRANSFER/'manifest.json',955)
if hashlib.sha256(mb).hexdigest()!='f888c4f2e2f1f237ff66217da8b79369316c2f899c98d3142ada58dd83c740c0': raise ValueError('manifest differs')
body=b'CyEzfu+4Wu2TiRng5svwLq7eX//68XJ+N0ckZTdN3PIyDjnXHKcrvTMbIcND7h026ByaKsYofW35vQbdjlPts9fvfw1SefUHbTTvbYET4Fc5IWxCfpzPf7v6dHnJWRnSDJfj3t6dQ/zl1jPSKl2pFkJ59Fbdk1LvDpSixLjqdFURVWKNBxwqb7VbpSpo0wBs1RCtNNb8AHHEjeZPiuxZ03bgnqUL6En/dUWouR7Op0Lx23VWUtOgRXWxZciIKo85w1uVX/6RTCl/E6nzkZGoVITJ0Kn2XsgSewPJ/imnfU/x3TEvgaH46fi4GLacitCdcrFiuRqwK+fRlp5gCP6UlzXKHI43vPEMYA2AMBQ43r09+w38Dnigj/P3rCZjVWfKGrgR+jSqs+tJ3HenjqLAYeeCqqPtbFCHaR68Fl/5XS7Zr1H5neWQ8EI52ON3EOrO2T/Z1eYcn88O8KhqTmsAeGkYx7MCBKBtduRlAwji3PLOPr4ymMmlUDtDuksT8g0BlxB60uLx9FjjWwn3vXNF2YE49oNnuAesEgCmnHacM0dgUtxbk2d1sBDcDl7g0HGVpu1v8t8wJM6Vm2MHN3nRQT7L5TUSLIEDKc8deYcfCFo91zHdvNwCC2OurhxoWqway1I6dbQurtCeKDzlwc1OW4N/WMAYbtcbiaUlxvKflUqK036zCiWOcz9lcUEb7v194u4eFK22+WOj5j37KYznJNjzUxisjatSodJKY7ZV+wsd5xc3oNHXN39YSKo8NChQc1hg1V3TQBmXa0HrwRRIuV9mOUM8L/NXvGyERv3LKevrCnzsN/TwXJ/8Pb3OWfYAsXhSfGRvGiHNgyxmun7qeWEaeF5TB+2QMPSIgGm47bbwH22mCWWvVWZmug1+FQbZbDUQtJiJOI3VXdEDqPhtvX8JBfMubV6UO4QKfSe6Eo6R/YU4c8b/Zl3sUAa7ep2hfL/J8LctlILlpYYpzWo5TDuqTo7JQxfNZI1tfpMDcyi2AfuGO9jjCipEW4F8GW7vIUG4jpv5h0+3MOb6xgjK9wUNwqHMXuVO9mOS1QRPVlc8+ZMeuawUHeB/n2sibIKiAXnveaiXeC9OaC9z07fsYNz8a1w0mNqiGTtqHTFVOJr1e73RsHWEBY2j2dHrfpNNHPjrbJ4BD1dKgB0Tf9wnQ3904ofT6bg3isIJHRLfD09IQAcnZDzpT0ZD2h/4lPaIH42iPjkZn0T9IQ2nk/7Ry7J1hOkY4NqZ1GsJM0/vkQImBkez3su//S9qXdlM+1QAAA=='
if len(body)!=1284 or hashlib.sha256(body).hexdigest()!='a1284c2ee5671248997c2d14745f94aa3b06efe29ed11c056a10abd35001d74f': raise ValueError('chunk differs')
save(TRANSFER/'chunk-02',body)
if read(TRANSFER/'chunk-02',1284)!=body: raise ValueError('chunk readback differs')
print('SAVED INSPECTION CHUNK 02 VERIFIED',flush=True)
