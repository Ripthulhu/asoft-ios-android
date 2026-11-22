import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'saved-inspector-resume5-transfer'
TARGET=Path('/data/local/tmp/pixel-saved-checks-resume5')
INSTALL=BASE/'saved-inspector-resume5-install.json'
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
mb=read(TRANSFER/'manifest.json',1622)
if hashlib.sha256(mb).hexdigest()!='c4cb64bb0d5b7ae281b2bd54b755db3231b8870abc4de54b45841e09fc591efd': raise ValueError('manifest differs')
body=b'y1MSoXdFY9Y3XTuL9qmeC91i3S2ucA3Q16mmgij9V+wKlvdB/Yo2aCLbrgT/97915I+O+BMEGVDEcqa62V1qKBNMAOXwylA9DLKC7/l9O00GEopN0pHuhlD9NDx7ffruzd+D/8u/3p1+f/rmzem/yyu1O/Y40C++QWKxyUglLgL0M6PoB3JiOjrCZhxQizHJoI6lgoZICpBg3Z/bcyL6iFFTOjNsqKbREl/fnL76KTz+D1ix8fvdS6O/+B4NzcFLbA57d3JKs9s8eXPOiYg8I0B49RBEZAygm9M8Q+JJjqNoMtTQNfmfYJSA0rNVEYdzlCQnN8l8mtfssLGCOi5tcEhzKNFBZ/ER75Rxq4bd7Fm3a1SVmOCi2AbsenV2/OJCItfxf7x6I/8+e/3vZy7StYJudmiNau0jzmD7TXTBGJXZIpmEeOHnnbw+XhVPw6qkYozzkMTzqXSGBDSbO+eDASewF3fawSOAwGSeFTGvz4S4KpDnSEth7H5eRrncWMF+W8ES1KCJclQkCYBNF51fs6tdwECSJEl36xQ3GHqFLBNUijSqEOXTLpNiQfxh2J7pvaU+YwiX1BH0qbNsVYquDCuINVwxydkVhmr5OtItDSPuQO2HFI3Hlumz0ovPEqw7qYjPbEIgMAoMGBgyKUnRYyoQkVYExKvjChDz8v7yBUXTAskegV7EZdCOV1mwTJYxvtSDbyLIVtA+CTzrDnYRWXeNPRFfKpsiv+sVyC8VOIgCZ4OELgXYdR2j5K4fs+COdEqkvlyFfEK4nnQwu7cdzFoyRhSX41/Z1a9DWUikBs4hYgUw3UVUDmX9D+cXL87C70/P3r64oA6jHKjfbTzwxYuQphLxsoi9koXU63IdYMGkFsiBLqL8JJ1lvlgRVLWDk2yJvymYzzBoAHk8OJCegh1AoAJhAeunHW+CaALMAahZv99s6edGblQJWlAnmk5xIg0aAWSsrPMSEevklBvZHl4MbSOqEdsZYV+jefI7m1GAv2Szhoikkd21gttsvlrEFNsFSoCgwSpaAb+RsX2a3ybIyyg6m+EqH60ANdHPiyyxfzt5+WURvIvj6QmM2y6zNqLHA7rZp0XC99+md3P8UNjWU/GKrYzFIzeaXYjztT5ksxmcE+uTeMHFBo9oGufqi6sVSxU65HqFEAgn0Zybq/Jfk6v6MhDs8UWofOBiVawdUbZKAKv8HfJXHFnDzHzF18BnfLRXJKESBKX6w7EjTs/P2PWffBihonykZcKSGlOjysshRgjhlSl/9fzvTpBxcZURPZjMk6tVyXQX2v9b0OhhIK0j5aZWU7en6/Z6Hrd/PM3clJ4B8Zya3hnRi3e97I86xg36y2NHH8XTgc9AJU+0Ch5rVOluLE7UyO3VKLA7Z5WjsdftHwVfoUuiPIzwZ3Vc2cc6ZB67z7wqjRwMH69/hF1tvuYQ2H1tvJrhwEJERESvgU26gmICfMJ8IyZOB10M8sTcYzO2H9iGVqNPxkJm8+iaxJsD3HRhb9Ff6UYHn7QBoQsXEVvn+ut9D9j5g1qox6X97vND7CoD+in23QQZm4AfnXAPetJWuCYK76DXY5hozGXWHhGDIq85J9UVNqpQ84CsCq+WByBN74Myc1q1oHrK+/htkMvEmqb0hTlJpQSITjXoX52yQzvxP+E4zrJJGefA+JRPk2SGneDiJpbdlXeZtsmxWTAAwW8q7hwx/Ao+PwdhbDpFXRAX3aJFKp5L4BUeNojs9AwrwJAdXweNBkkgu7uEZvDhWRN/HDXlJ+cwQHtoiYNEeR49NLBKs1pn1DvqDoAE4XsalMUv76fwH6BQDfgYtAMolk4h7OxPrv6ARBm5+pOvv9lfK9iHM9DQs/866DWhOz4bRyLwojTVzrJCPAQV+GBz0GarnihxjbHxaoSg16JekQf8niwbDTjaB03+Zt0f+xZzUl1Lt8W9WiYC8zm/oiFicCZSkksMjF0UIPATFTgIqkkd7IxX7AKMtZ1hD/YVn7ms5qMdLo8IBkKoQoAIlAbp8QagUzQHa2/iygYBMQHVMiBgrNRDQWwZBhUz8SyEzXsKdsIir34/IfxdjeRrkmPCSu2saPqw+NG1yqyMRp/0S3D0KJBhSwxhGT+/+HDx4+nZ8evw3fHx65N3Jxfhfx6fnXI1g8Gt4Vr6eDlhEkiblWeTLoxlxS1Rzuk+ms9FyBl97UlQDSVUEQ/rOKKETAUdFchMbqg+VniN2Zd8w89wsvFTBlJy6jogcNvYg9W01YCovMl3WvjA89lcUOGuAg5Ooi2Zo4298uswqJBh47FvPJ8WNqo6uhww0iTSgUryUn22jjT9iQcydNS4TYqd8twoVgshb4hfni4kfvP9LUAWTajL6IEc0AHUi4Re8UjMS9mT68+a+MaZuiG/BLgrCI/KoCoDpBfbACXiqz+ORG3co2qrWDVCinLy4s3JfwKFOX77/uLvrGIq6m62rSPwSVp69DbRcqRxZCxfWKK4mVyLEDhJWVJ0Y2N9IwV+ouaCCK0ZwdG5sBHKMVaP7m5QrX6/0ivOsYtPz6pNsdG3AWm09BKy2hBHtZoK1Brjg38LItyXZ8HWpFXzv4oFbTGkD13HWKV7/z38A5JF79ABtreFf8hNrb7zraktt4PRnEK1VHZPXZauw6U1x/rzdVOlNsTTimnLIJvSBCfmO5lHRaF8mbT5zTaw/SLd+FHSJzvsl5QWYYJT4p6klS5JJ/MVKQlYF2fGuRYmQM4tCxtDEINbR4uraRTQA/8BszOO387XUTk9zXRjb4267edRezb+dMjht3QLeWMhJH82fX4yrE+D4PBZr3t0dNiXxozLnddRSQ6S+/sHB/0+nAsqeeQnt9yTkNxsmZ8/cpRE9VEJUKrUkPQrxiL74oWXTyVekiqLOLKQFiBbgW25EnFzF1H+YHEUSlCRYrx++XWLaFIypqFWIqM7uRCx+9KDwrrilNOjmx6KYKisbIbo26qxvXkkfdnKCxpdyMDho+2yQEOCNyLYCENYMtVgWa8wyME2KQ3bTqJGXZDDjJyemO6jMg1juZVkuaV0+3oXXMLswFJCvvV33eYIngYZNKpVITlu1g4umqv9dzF23HQG0phSweOaYWi3CP28EUZFCUBrb/2GR67crVhsZLFTfomujcb7nE9Cf+g3RdAQQBAxundgLDJN1b1e8wmK4BYnFE5VnTZq29ftsvUsSUntYnA38oHxuBLYhSW4ezmSOVttQK+aG23buhFO2d02qeXKCrTW3vpFSfonIFk/Q7Eon9e9oQ2fX5ydvLoI/3b64ezdizco7T7aTACRLjI33s85NB75CegW6MKZT/wLC8R7lgLGoEeQcDQ/OjFBRNgra/2uiE5Ros4wRnXVDHBxGnqEd3M3/vBNoX+y/3O/57HzbLzL8+4vqWAvX5wfvzl5dxyevD5+d3Hy6sWbkLf8zcUxYPnFMTk8h29fnP10fOZR7/7ILeG/wMXg/9wD+tdqLtOyIlky0ueeiifGx6w9E76T'
if len(body)!=3500 or hashlib.sha256(body).hexdigest()!='43f990f01ff971a53ad60ddd0d28c3e54ee25f25e80b53f7af9697dfc6d9fd4b': raise ValueError('chunk differs')
save(TRANSFER/'chunk-02',body)
if read(TRANSFER/'chunk-02',3500)!=body: raise ValueError('chunk readback differs')
print('SOURCE CHUNK 02 VERIFIED',flush=True)
