import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'resume2-process-observer-procstat1-transfer'
INSTALL=BASE/'resume2-process-observer-procstat1-install.json'
OWNER_SOURCE=BASE/'run-ios26-saved-inspection-resume2.py'
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
 for path in [INSTALL,BASE/'ios26-saved-inspection-resume2-observer-procstat1',BASE/'ios26-saved-inspection-resume2-observer-procstat1-launch.json',BASE/'ios26-saved-inspection-resume2-observer-procstat1-wrapper.log']+[BASE/row['path'] for row in files]:
  if os.path.lexists(path): raise ValueError('fresh observer path required; preserve '+str(path))
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
mb=read(TRANSFER/'manifest.json',1678)
if hashlib.sha256(mb).hexdigest()!='a560443a8d372545001df2c12a66f6c67e779bfe9965f7b500a13ff151c085a4': raise ValueError('manifest differs')
m=json.loads(mb)
body=b'1/mKD8+RPsdz/sb8ao/8OA+Z0l1fDo3Fl4H4e+Ktj6VYPmZe9fAiOrk4P/65Fw+pMlaS0vdf6dcqS3DJI/WgwC9046Md9ajO/sDIPEKqtwy9g5uyAqOX9N0Ctx7rCzBLBYDo+EF4iYs3XIJpHW34Xfjp49gQpfbZ+QoL02uC+TBOkvR2wM+zohzoFuLPBXrTIvzGHf2ciZ8ErTdVAKYKwFQDmNoAphaAtVTmIMhxBiNGnKRl+W17PhZ85nttxacjnxJvM8yKL5Iqusu9fMfHfu0inlwIhjz3cEDIhwW8ZRAw/4N/z352MnLdxG/80fdSKOa/H1MjMS9RUFTKVxpRTuWvnEkPL5RKRpBVlilTpsl2WKgMAi1clPe/gwo9LRHbzke1qLnpiHK7ykuEtZuglmmXhOEgQTSD0jsMGqZZmCmjhBUhstcnLBqdfOhR0AbBwb5luvGbrLCSJGVr+qaymwopx7ASIR206UaWE0/sBB8o70SFvB4Ee7vWNOUhHJNSBJIvTuqeCUjvsnzs3ONLjmq9paQWeif1gnY6i5KUIlWvjgSIsFWf0oKt4/OsaiUoFLioyNreJHN5aldqY5jwxK58/71Z5EBt5KS/GSmK0TigXkaTOLWKFsAxGiokS1rk8NcyWeXpJRpQoUwabCHM6TyUhMvCpGeVXkIc9dCdAi3EF6KNNiIoAd3JGhjGpSnjWCacy9drEs+9rNcqaoQ+OFaFYOCtE7QZt34K3Rl5Te/WSC2r0Wt0E2dzpiSz+MWOdCbtyvz06NGErNAzG20qM3e3PbJWsMmRwq70JslQlyMVcd4eQFpiRneuFODP6R9Yni1/yf7QXwHEKLNhHQg1BZ2DK8+IB/YjubfflNnbHk1yLsU/JY7wltpia4+4rdqgZWkiNA64IcptFaxZpHftPNuO+1bvvOUaNXvDEwf83fqIKmkSCeuGpHNLJeJbvpUpTqso66mjvmzPU4fSD1j4U77U6bUJrHKjygYfvqeRVVpG3YBePjbevzn+++kHlHZc82nMcOlnWlVmy4vLN6iLbRaWFLS2Wnj1yCsbzZO67ZgibmM6kw2u6h5cjrK2a6jSd/daQMyiHCDJVEcUxN7moliH2fZRi0eLNFFsSn5LNJW1O0BxiRM7aE2Nblz8hO/Pz14fX1xEyn3IVHv8JnxatIcCzj7HiRCgm3sd7bRh80st3u+syKUsYzTzDNWFvwajcak7/iV4L3VsleGNMjBPGx3rhyajRC7fLNieumFXcImaknUfYdIUyZLOQzvH6q13aw6b8vv2xFCDQB6ejCY33nVv+szvsfI3Zb0NWtErFOinvpDaae8r9mwwPS7G6XE0vDk5P359eXb++9rSZGpUBbvvRBTlni589eJ2UVcWhK3/f1/Rvq+Q+paw259+a+G9lVDkqchy/d3AyOKkmjmt5U4ckLL7Z1+eCNVQ3KFEZ/a9/dqLkX/FZYt0CkTkbcA4CZByGcZF1I8WAvk/dyNzsPt8V13IiATgb72Tme3uJAc78e7O4e7+aHqwF+/tzg7mh/PR4XT+8jA5mMXP09FBchjvJC/2Ry9GB/P0+eHsxWwax89f7s33nj1MBs/QcMA7oo3tXJwBWR7PjnYe/sv/Bj9I2wo2sQAA'
if len(body)!=1632 or hashlib.sha256(body).hexdigest()!='ae1f35f61207199ad4e3f01d00508890b183c791a05a5ef27a8af3fb10ea14f5': raise ValueError('chunk differs')
save(TRANSFER/'chunk-04',body)
if read(TRANSFER/'chunk-04',1632)!=body: raise ValueError('chunk readback differs')
print('OBSERVER CHUNK 04 VERIFIED',flush=True)
