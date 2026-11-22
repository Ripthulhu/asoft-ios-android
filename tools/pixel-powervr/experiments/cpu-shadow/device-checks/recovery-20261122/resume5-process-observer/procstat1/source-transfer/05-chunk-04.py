import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'resume5-process-observer-procstat1-transfer'
INSTALL=BASE/'resume5-process-observer-procstat1-install.json'
OWNER_SOURCE=BASE/'run-ios26-saved-inspection-resume5.py'
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
 for path in [INSTALL,BASE/'ios26-saved-inspection-resume5-observer-procstat1',BASE/'ios26-saved-inspection-resume5-observer-procstat1-launch.json',BASE/'ios26-saved-inspection-resume5-observer-procstat1-wrapper.log']+[BASE/row['path'] for row in files]:
  if os.path.lexists(path): raise ValueError('fresh observer path required; preserve '+str(path))
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
mb=read(TRANSFER/'manifest.json',1678)
if hashlib.sha256(mb).hexdigest()!='a899909aca777e0f3e77e46059ce454cda0e731499adc7e94262522f842a2ede': raise ValueError('manifest differs')
m=json.loads(mb)
body=b'53jO35hf7ZEf5yFTuuvLobH4MhB/T7z1sRTLx8yrHl5EJxfnxz/34iFVxkpS+v4r/VplCS55Rz0o8Avd+GhXPaqzPzAyj5DqLUPv4KaswOglfbfArcf6AsxSASA6fhBe4uINl2BaRxt+F376ODZEqX12vsLC9JpgPoyTJL0d8POsKAe6hfhzgd60CL9xRz9n4idB600VgKkCMNUApjaAqQVgLZU5CHKcwYgRJ2lZftuejwWf+V5b8enIp8TbDLPii6SK7nIv3/GxX7uIJxeCIc89HBDyYQFvGQTM/+Dfs5+djFw38Rt/9L0Uivnvx9RIzEsUFJXylUaUU/krZ9LDC6WSEWSVZcqUabIdFiqDQAsX5f3voEJPS8S281Etam46otyu8hJh7SaoZdolYThIEM2g9A6DhmkWZsooYUWI7PUJi0YnH3oUtEFwdGCZbvwmK6wkSdmavqnspkLKMaxESAdtupHlxBM7wQfKO1EhrwfB/p41TXkIx6QUgeSLk7pnAtK7LB879/iSo1pvKamF3km9oJ3OoiSlSNWrIwEibNWntGDr+DyrWgkKBS4qsrY3yVye2pXaGCY8sSvff28WOVAbOelvRopiNA6ol9EkTq2iBXCMhgrJkhY5/LVMVnl6iQZUKJMGWwhzOg8l4bIw6VmllxBHPXSnQAvxhWijjQhKQHeyBoZxaco4lgnn8vWaxHMv67WKGqEPjlUhGHjrBG3GrZ9Cd0Ze07s1Ustq9BrdxNmcKcksfrEjnUm7Mj89ejQhK/TMRpvKzN1tj6wVbDJS2JXeJBnqMlIR5+0BpCVmdOdKAf6c/oHl2fKX7A/9FUCMMhvWgVBT0Dm48ox4YD+Se/tNmb3t0STnUvxT4ghvqS229ojbqg1aliZC44AbotxWwZpFetfOs+24b/XOW65Rszc8ccDfrY+okiaRsG5IOrdUIr7lW5nitIqynjrqy/Y8dSj9gIU/5UudXpvAKjeqbPDhexpZpWXUDejlY+P9m+O/n35Aacc1n8YMl36mVWW2vLh8g7rYZmFJQWurhVePvLLRPKnbjiniNqYz2eCq7sHlKGu7hip9d68FxCzKAZJMdURB7G0uinWYbR+1eLRIE8Wm5LdEU1m7AxSXOLGD1tToxsVP+P787PXxxUWk3IdMtcdvwqdFeyjg7HOcCAG6udfRThs2v9Ti/c6KXMoyRjPPUF34azAal7rjX4L3UsdWGd4oA/O00bF+aDJK5PLNgu2pG3YFl6gpWfcRJk2RLOk8tHOs3nq35rApv29PDDUI5OHJaHLjPfemz/weK39T1tugFb1CgX7qC6md9r5izwbT42KcHkfDm5Pz49eXZ+e/ry1NpkZVsPtORFHu6cJXL24XdWVB2Pr/9xXt+wqpbwm7/em3Ft5bCUWeiizX3w3sWJxUM6e13IkDUvb+7MsToRqKO5TozL63X3sx8q+4bJFOgYi8DRgnAVIuw7iI+tFCIP/nbmSO9g731IWMSAD+1juZF/PZ3u7ey/354d50P4339vcOd/efp7OD+Yu99GDvefxiCi0PprOjnenOy3Q6ezHf2z1Mkjh+sbufpEfPHiaDZ2g44B3RxnYuzoAsj2ej3Yf/8r8BGQAVizWxAAA='
if len(body)!=1624 or hashlib.sha256(body).hexdigest()!='f9de3089c5d93e85ca34e5a1c5cec01876b2c37a75a53732781ce12261b284f9': raise ValueError('chunk differs')
save(TRANSFER/'chunk-04',body)
if read(TRANSFER/'chunk-04',1624)!=body: raise ValueError('chunk readback differs')
print('OBSERVER CHUNK 04 VERIFIED',flush=True)
