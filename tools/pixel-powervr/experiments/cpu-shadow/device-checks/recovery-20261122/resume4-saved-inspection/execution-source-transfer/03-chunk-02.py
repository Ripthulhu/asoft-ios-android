import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'saved-inspection-resume4-execution-procstat1-transfer'
TARGET=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
INSTALL=BASE/'saved-inspection-resume4-execution-procstat1-install.json'
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
if hashlib.sha256(mb).hexdigest()!='1e33809a2e49ff421b4afcf40ff15c17d071abc46bf920e9953edebac980e6b2': raise ValueError('manifest differs')
body=b'Wi0CZSW/YdSwdH2QbCP6MpJ6XZ0O45OmA8waUD7r9+GKzGgnPnV2+CG/lUfnISb4KwohFd3Sm6F6gVgUhtWal14QxoPlJweUdLVrnrwdF1d7pUmcqGjfGOfgdy63UualYape42XnvuUJP37EiNPEz76ygiSfOH81BtZ5e+O+3lN3wDXwfJriueF553eOlVbudr8pc7v50U8ej6cOByyeQNMw0vfHMJTmSz7MwWGjhgFJlWsDAFT54pGdo+YBtXbfq/zwWmEF+YpxjKwsJs5uGy5lsZYKa1J9qt3YnfqKqZuUoxeVYuW+6sHnmGQUTw2OdkNeaBF6K/7ztXpH/t317PRWfJn99e7CvDzfsNrxsN3W0dPiC99aU6sD2oTupOmO+zb5EskT6+oVsil7U0ExNSiiOMDNpuGcX767+vPDxex2hkjyKhy/F6pdiyg5gJtbZ9pD+JLMOmzQONSlQ5Lb2vx7CbqKezDTw9e/BKm4LIg6mpW4wAiwy9/gYyE/zmafLj9eXDBW+iTB6dg3t2fgrNnljDTyXLIUlx/WlzcrZduevBXvVxyuuEXltsaDEYVW5R669PAUAFM0eEWNlk5hO+JCsydZ8qxIO3DPkAW0pP+6IJS8UIINhduv6nS1IkHz4mRzlxFFHgOM1wq/+BFMyV/c1vpASZQiQvfQidLO9xJtibfZCaN9R6be0q+N4vZT8bFt2LAKm+6EbSsa2AG7UuZtqdEI509+vSsP+FihHM8OlgBwRYH97ZvTT2B3wAJ9mL2jCRwjlZMnzDXXp1YcXY343pxYkgKLnicq9jZDRxWmvvdFGoWXB4rijgwGDYOEr6AAffwWXN0Z/ZO+DCHF59M9PCqq0xIAlkfG/jRbAWjrLXE9CZw4O3/LBzZpzGS7UDl7WiUJ6cYFk+A7QuOxWFrhWw73k3VJ6EE6+lZGXAOaNgBVTlrWqcUxSe6t3Wd5IBHMDh7sV3Hlqu1X8Td0CVNp5uiBT5ahEM9Scdgf8+UYAbbEWz8ivBFQxnT9OhxMjJq6vKOusUo0S27UUbvYXHoC/4Q5N5W6Bn+ow+hv1xuBpcH7NmiyOspOuvUiFL8A8pSEGanZd3eRXd0pWG3Th1pJO315znPk7Xh5DiuAi1Ao19IYbZW+0+fs/Bok+ur6i4GkyEONAjmGAVZcNQWUcrkUtBxMguTrpec++PM8fsXriajUH09oEZjjoy/6xPOA4qWfrdPkHnzxKPtAW2o+Sb0kpLJ+4jh+7DlOXQVtub7vuBymZjeb3H40qSTkhVkRmak6+CAMojKrIWhQFXESytvle1Cx+73/EgpqXZosg7cPFdpONCUMI/2FOFPK/3qZ75A7u2qeIW/fJPg2HClgaS5hUrLwcgNIR9HI0f3QRjVZoptfZcAsgjXDrmYOdpiCAtGGI5+72ztI4Kbjevb+4w30ubrWnPJdTgM3KNODzMluTCKb4IjsiiNeApSKTNEe/neZJMIiSBqQ946Dcok3abn0UjN9Qw/Uzb6FWY2KLaqxo8YRFYWjabfba08aR5jQOJoeHfbGSPFqWPUVjICRiSdgCXy3MxgP2sPOqD+Y9N12pzcc+l1vGCy7fsft+6Nhd4zvhxz3SDCe+CPSdsf+wOtP2r32MBgcvSwaRxiYAa7K8D736SUZIuRHWujWOJp2Xv7tfwEwwqoetFkAAA=='
if len(body)!=1684 or hashlib.sha256(body).hexdigest()!='6be769cc3b81822b04e529cfe3f0937e2c95eec6133c8e042e49d452f34e94ec': raise ValueError('chunk differs')
save(TRANSFER/'chunk-02',body)
if read(TRANSFER/'chunk-02',1684)!=body: raise ValueError('chunk readback differs')
print('SOURCE CHUNK 02 VERIFIED',flush=True)
