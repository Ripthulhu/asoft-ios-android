import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'saved-inspector-resume3-transfer'
TARGET=Path('/data/local/tmp/pixel-saved-checks-resume3')
INSTALL=BASE/'saved-inspector-resume3-install.json'
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
if hashlib.sha256(mb).hexdigest()!='95faa2f0adc715771bf6b35c7cf7601913206974e0a21db6476e472d48f35933': raise ValueError('manifest differs')
body=b'BHedts5ofbNchYhJ1dIn9eh6TqcA48MKT3R4S7lp20Gy8lBZ+6PTo6KywU69BWxaGcFmNTZvJSB+jTtx7fuB+3tPOg2GP+Wm9aygE4PL7SwBCeFF7ul4DJmwIFUpsvkd3lJgoj5+8J5tBkvSej0HqznyQAv7Fqly+W/2zZ2uMKADXWQ1wliTkg+/U1QoNuz7lRAXTrswsd276TBq/zX6ngCFdMUECO2Sesj59btf8SFneseZ6al8w7nWF1EncCFqEzIoPAlChDWGaVFHJl2S2dWhGROMdhswJM/kZEcit3jvesePGuK1gi07Rnni6EB3Tr3Lpjq3ae1q9f6QOqMOOuk1lUXLjuO0WOVxuErFuTcZgJWxwU84qkk6OGcgZjSTKEXEgkLp+WIxSW8GXQp9VlqOUb+3pr4UAeoyrojsrRpsdxR7iIletUZVBWldwhg7UWxNv1qj2qJjeRSc+Q5qx7QEH/jkVZzkMRR3fMKZgG3x9BigmNjHk4urM4x+vnxWqpj6ZK1knth0OyB9P6UPg5ie8cXzzq0RQe/4E22d7MU32y/rY+g5G2mf++dwx+c+W/XddxiFoaIhVWfyyxPd4lqf+BL3y5Mvz4pyq7KLhMpmZou9IYt7vkqlV1oMBzHOySuNHDCWcU4plO5i+uZ2mIOQhREASaFSapUZiGUT0BaC+9uYOtOqIQoERKyJp0T5Y6fGZVt6+zp42bSDqaoo6vPvplBxfQolPZW/sVilzNPUxx6+2ax3M/byKOwVmTpzKfxVYdsGo6E51DAauQQVr0Od1U/nOQwJu9qKIX0tU+IBOJ7UPcHrfKoJIFswpLVMqQZQmLB3gNpBsBs0PImp2dgsYre60lnCTU/9HFpI3A2G3T5npzJqCFvJwAjl78BxbYiUxZ3bWbGcy7dG2jPxb6pgj4g8TdKB0fzt6e8fPr17t4FIQTMAkXrhHH4C/TG7ubx6e/7pqkUSNtbs7XW7LZ7wwC/ZV3InoS4YztKB3EFKA80J8Dg8oLk+ZAJBSqIdiXXSGflA3owziOBw3YR051gbPuHPAm3QDCs/tdiTDquqHDGOMyFNvYwfygaF16MAYiTFZg1sYOTGrmdeBpSvGLqnD0vUmvrPnP8GzgUzBq2S1cLrHbGR1dS4zz1kykARV5N5N8VztN4E+LXkR195GsnYrLTexnWnO2SHIqaLRrOpUKJ6uVlHRbeUBS1pTAho9at5pjy4SdQzJLxwuso5v56ZXvxvE/ckdP42+c1aWkX2WssiMCOBczFQv3qtkNQ81lFVSf7dDJAylZMjieodPsF/6duajE5DbdMZGQG7VZnzyc4gtTbN4VZdWwJKLLvjA4uGw7qsUXIi/qxQJIzRIcVgckE/Clds87PS5zJ6j7Ayz4AoYXJgllWmMWqlWlBxYgsdUPbXpCZ0DW0Kotc7PAjJeO4LjvXN+1ulI/Uno/z38iXWZCbkjFUqFUyt3TVkw7a0QfMvkf52gNmHOpi7btjrC3NSRt/JLsW1mup7XSp/GztUKnsjbS2bufR8mgZzNvmuTDk1sG3z9uSVLa42lbwvl97XWqyfe4q/LuUb83zrtFuZ/OCMhLMomcfTLQ68lBcaLFO7j0917vOkjBn4nsRtbtoilciNQnGur1MjIA/EIExVZbhr4SSBGGBUHuiiN7d058h5wb4F+Zpzc/PDG5iXH+l9Gs9/kB1S7YyewzFfXxV8jmP9jDTOmLOMDIzq2hMEP+npzqnp1nKIi9PLT++uOKNe9Ui3ghmI8rcDI5uuzGL3dyaa6x2/fPFyU6I5RnEn3dzscC8+mB7EkxfHk+7xePZiP57sv4hn0eQ4io7iyfjly+gwGu+No1nvxcHBcW82jY7He8dHs/HBy+nLFztPoxZduEBffM8iRoezhuBYxPthASwd9gyHJZyG+T79j/8HvXd6AdvVAAA='
if len(body)!=1936 or hashlib.sha256(body).hexdigest()!='8855957ea43775dd737304f9da9d2b1d9daef00e23208f5cfac28d871f9cad99': raise ValueError('chunk differs')
save(TRANSFER/'chunk-05',body)
if read(TRANSFER/'chunk-05',1936)!=body: raise ValueError('chunk readback differs')
print('SOURCE CHUNK 05 VERIFIED',flush=True)
