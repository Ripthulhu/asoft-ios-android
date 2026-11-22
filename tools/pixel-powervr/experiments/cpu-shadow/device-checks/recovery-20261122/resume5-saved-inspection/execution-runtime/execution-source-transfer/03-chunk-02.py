import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'saved-inspection-resume5-execution-procstat1-transfer'
TARGET=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
INSTALL=BASE/'saved-inspection-resume5-execution-procstat1-install.json'
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
if TRANSFER.resolve(strict=True)!=TRANSFER: raise ValueError('transfer directory differs')
mb=read(TRANSFER/'manifest.json',1079)
if hashlib.sha256(mb).hexdigest()!='5501c4724d4c6231b557e1eff72127e054231615987b4aa29615ae0974777fdf': raise ValueError('manifest differs')
body=b'dufVzzRJuAYvKrZMmlBA5Ctm9tRsWWYbRViGsBdXv7QcTBq3nB9UrpEJuinxRi0CZaW4OdZyTH2QbmP2mpdmU18Op5OhA+waULHqD9GKzlgnsXR++KG4bcnWIRf4EwohE93KG79mgVgWho2TskbRDC8MnLyipGtc3xXtuLnGMdsk1dF+Z91v2LndWpmXhalmjZef51cn/MQRIzEncaaZFyTFwsUxVqzzDo6HZk/TATfAi2XK55bnXdwl11qF2/1dldstjn6KeDzzBGD5BJqBkb2Zh6O0X7tiDw6MGi1ppl0HAaDaV8HsHLUIqI17fNWH10o7WHXeV57Jt1zKci0V9qT+toLFneaO6Uwq0MtKsXYP+dXnmFQUzwyO8eYDqUXY2w5+v9bfffD+enZ6K7/M/nh/Yb8UoeV0k3G3a6JnxRfBWlOnB9qEcdJ0xz2qYovUTQT9auCUv4GinBqUURzg5svwzi/fX/328WJ2O0MkRRVO3Pc1rrtUHMAtrDPrIX1Jbh02aByayiEpbG3xvQJdzf2m6ev3vwKpvASKOpqXuMAI8Ev94GMhPc5mny8/XVxwUoY0xeW4N7dn4Ky51YS08lyqFFdcwlA3ZlXbnryV6Fcersyiiq3xYESpVXu/gPLwNABbNERFjZVOgR1xo/mTPH3WpB2oZ8kCWtJ/XRAqXhTCh0L2qztdrUnQvLzYwmVEkccA463CL38kUYpX4nU+sikqEWE8dKK1C15iLck2P+Fz35Gpd8zrwMh+Oj7Ohi2nxHQnnK1YYAfkyri3pUcjgj7Ftb0i4OOFcjw7WAEgFAX2d29OP4PdAQv0cfaeJXCsVE6RMDdcn0Z5dD3i++7EUTNw2Hmicm87dNRhmntfkFJ6LaMs7qhg0DJI+GoR0MfvwNWdsT/ZSy4yfD7dQ6OyOq0A4Hlk7M+yFYC22ZHXzsCJc4u3t2CTQUzOhdrZ0zpJyDYETELoSY3HY2mNbgXc984lZQfp2PsucQ9Y2gBUOe04p47ApKi3Js/qQCKYHTzYr+MqVNtP8m/oEmXKzLEDnzxDIZ9l8rA/5ssxAuzIt7nEeCOgiujmNUdYGDN1RUdTY1VolsKoo3ZxhfQswxPu3NTqGvxhDmO4XW8klpbo22LJ6jg/6TfLUOICyFMa5bTh3t3Fbn2n5WqbPTQq2tlLkZ7jYMdLkXgBXIZChZbGaKvyXU1n59cg0VfXf1pIyjQ0ZqDGsMDKu6aBMipXglaDKZBiv8zch3hexK947RSV+uMJKwILfOwVqngeUL5OtXOa3oMvHucfWUsjpFmQRkzWTzwvTALPa+qgHRKGHhEwDbfdFvajzSShKMzKyEzXwa/CICuzBoIWUxEnkXprwB5U/N72v4SCWZc2z+DtQ4W2E00Jx8j+Q5wZo3+zynconF09z1C0b1J8y5ESsKyQMCVZeLkBpKNs5Bg/dFFNVujmNxkwh2LNsG+Ygx2moDRpy5Ev3O0dUxCm43r24dMN9Lm6NpzyXU6DMCjTV5mT3ZhkNsGT2RVPvtwpk5miPfTvc0mETVBzQNp7Hsol3pAW0svM9A07UDf7GuUNJraoxg5aB0wUDqb9/njUbR1gQuNgevC6d3jKl+7qL8UEjFw8AQsJ6VFv6Qf9UX8yXB6Tkd8bLicDchwuu0F32RtSPwyH8DueTOhRQPpB4JNud0hD6o8I8Q9eFq0DDMwAV214X/j0ahoy5Me5MNY4mPZe/u1/AdF7l20OWwAA'
if len(body)!=1736 or hashlib.sha256(body).hexdigest()!='4d17d8a54721a2d68c9a74d7575750f07b79835d5618f4730c82647d3ceafc3c': raise ValueError('chunk differs')
save(TRANSFER/'chunk-02',body)
if read(TRANSFER/'chunk-02',1736)!=body: raise ValueError('chunk readback differs')
print('SOURCE CHUNK 02 VERIFIED',flush=True)
