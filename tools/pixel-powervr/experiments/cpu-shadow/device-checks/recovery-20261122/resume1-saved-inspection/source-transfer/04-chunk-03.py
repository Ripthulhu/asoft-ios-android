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
if TRANSFER.resolve(strict=True)!=TRANSFER: raise ValueError('transfer directory differs')
mb=read(TRANSFER/'manifest.json',1263)
if hashlib.sha256(mb).hexdigest()!='cc5cb704e57d274676130c4fcb634cd4ace5232bb9be83a059548cbb60022ce4': raise ValueError('manifest differs')
body=b'9mHfpxBl+OzLD7VLfPsXX5nLrh/V7nrVbvfdftnsd7zaZ9eNv+Y1tDtuqvn/6d5YEYvdcW1sXjRujf0OjXPtKS/f5bRsOrFdNFL3xuI3jR4pK//de7PPgTfIwnRqX+VQnPjdP/xKJfrH7pQV0lS/QpQt2CGXfbL13L6W/NZQfeKePZ8OFM/ifKENThde+Ds5VCamceTGhFU5UUqXMUZ1zJtBw/bVoF9xyygHyu4SFaYRvhFP7dtRTNkVkj1SRmnaPinLFWjAR9Dh3fJzgDxIydSz2cDl44mabOPV2LjWlGuGviYKjMvJvkMHDtgVpfxW+cBUAAY+YT+xhmkZNK+7bC8Ju/CM5SyV6GC5D8wQSo2rXZvbdR2auhiUa8ahBZptaImb0FgJo3nhZvP2Mv0aZBNRvBPzjDUS2CYw+Xvdw8ehJU7a7WZdm4fb5CJc0Zd3P+oKyWgo0jiNm8z5u8Zd5tpOEO9xPQxVh0U0Ndj6LVd5O1dImB/ylkM5DxHY4B+xU7aoqA6V17CxniIsJiYuDJ+h5fjjmWe2NO8kMLrX05TPGzGTWixrb8VBRnjHzaugkRwAY0Ke5gpExx4AaeTrdIjKcDbjD8j0PDiAnwlEx8boJU7/qabsiE5zHECnX+RPxhF7vkwjXgisvpShL63+yQxjUV/afjTuFhyBFUoy9NTxa07A3XtVrLz+GUIVA2xdcMIeB4aul/vzzxde1ZHHhtvJFhy/giP8ktbJ1Tpwx23RVrJwS05Qc2j5NIK35+qCCyNfJwy/oZ5C7E6aiYP4rIXUoHpdHuJmnL5caJu4A5zcMJL4qldDiJgbS5clHUBlbAvtfX7lA4hXrsbAjkF6iOo0TkosSMOHvBCt103IAmwp+hTUiol/SqEOiwRaLlCUOep5vXoTouwFzOuGL/J+P15kV2ffzUQMHswzeRN1xl9SEciH+sNVgYqdDq0KPPB45bbaQXkjubZA4ksX7Gw/TKXUE3zabtTCYyzBxRm6q8RQdRCbCttrZ+Z5xIhvs7M3PUN599uD3SgL5xaFmBrQYlVI7damwWT2Gey1llsRD3m9gKqSbIjCw6p2OknSljQdHXg47fary9MOKu+RSPFSz0AKA3YzvKXRre73vXXOvsEqyn9hDTDWY4GUoyPr1JJFo5J6K/KsLonF2rLqnuqwlET4mwwp8XI1qQDYgU5Rltb4Xi67+wcweR5tK0RS0zMi67eybHtX5VBjj9fqjn18QuyVJD5hMmn7rje/SSGg7PwqxUFfpzik8PTA4tNtX63gFw8f8NGK3WVLWz9isbvAYutHLXZ3U13q9TLdOPG8UVAhhULzshZpg0jvaUd0XC2tWtKhxZalLUsZIqwirkMm7JKTRsHbt4zg1yMKgSSC+cHFB8MK2qV5virqvxuS9LIC6SgG+LXShETsJhleobObut8wgzCZu75KIHBGODo0ltrIJlAvnM6SMJzYXkhsz/NcP7LJOKGUOIT6cUIj/HKgnXizZBy7/jSk3phMw8mMun4Sk1cvt8NXaAADrH3eDo7LFvvVwnn5l/8D+xN9PCh9AAA='
if len(body)!=1560 or hashlib.sha256(body).hexdigest()!='a22e68c54d1dfbc1bd2cc55f63a81ec26f6933ad26964c4617eb9701142405aa': raise ValueError('chunk differs')
save(TRANSFER/'chunk-03',body)
if read(TRANSFER/'chunk-03',1560)!=body: raise ValueError('chunk readback differs')
print('SAVED INSPECTION CHUNK 03 VERIFIED',flush=True)
