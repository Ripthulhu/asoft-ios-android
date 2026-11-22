import ast,datetime,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
OLD=BASE/'capture-ios26-firstboot-resume1.py'
TARGET=BASE/'capture-ios26-firstboot-resume1-pin1.py'
RECEIPT=BASE/'resume1-preflight-capture-pin1-install.json'
PREFIX=BASE/'ios26-firstboot-guard-preflight-resume1'
ADAPTER_PREFIX=BASE/'ios26-firstboot-resume1-adapter-preflight'
WORK=Path('/data/local/tmp/pixel-firstboot-guard-e9cc754-resume1')
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE:raise ValueError('root canonical transfer base required')
for path in [TARGET,RECEIPT,WORK,*[Path(str(PREFIX)+x) for x in ('.command.json','.owner.json','.stdout.json','.exit.json')],*[Path(str(ADAPTER_PREFIX)+x) for x in ('.owner.json','.exit.json')]]:
 if os.path.lexists(path):raise ValueError('fresh unused preflight paths required; preserve '+str(path))
if OLD.resolve(strict=True)!=OLD:raise ValueError('noncanonical original capture')
with os.fdopen(os.open(OLD,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
 s=os.fstat(f.fileno())
 if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_uid!=0 or s.st_size!=32928:raise ValueError('original capture shape differs')
 original=f.read(32929)
if len(original)!=32928 or hashlib.sha256(original).hexdigest()!='11229907f2b6a681d8571f6689b85ac553cb4e0db585507d11599ec9780a04ca':raise ValueError('original capture bytes differ')
if original.count(b'd83951e8edc29c2eac4c1b6b8e5f2c3176f6c75a7e26590008afdeade88af4b3')!=1:raise ValueError('old pin must occur once')
body=original.replace(b'd83951e8edc29c2eac4c1b6b8e5f2c3176f6c75a7e26590008afdeade88af4b3',b'd83951e8edc29c2eac4c1b6b8e5f2c3176f6c75a7e2659b008afdeade88af4b3')
if len(body)!=32928 or hashlib.sha256(body).hexdigest()!='c16ef443b619578abb853ba15df22f063413dad18a89acb4e731f53c10a99c8f':raise ValueError('corrected capture bytes differ')
ast.parse(body)
fd=os.open(RECEIPT,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
try:
 with os.fdopen(os.open(TARGET,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644),'wb') as f:
  f.write(body);f.flush();os.fsync(f.fileno())
 with os.fdopen(os.open(TARGET,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f: check=f.read(32929)
 if check!=body:raise ValueError('new capture readback differs')
 receipt={'schema':1,'kind':'resume1_capture_pin1_install','installed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':str(TARGET),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),'original_source':str(OLD),'original_sha256':hashlib.sha256(original).hexdigest(),'changed_source_byte_offset':16314,'old_receipt_pin':'d83951e8edc29c2eac4c1b6b8e5f2c3176f6c75a7e26590008afdeade88af4b3','new_receipt_pin':'d83951e8edc29c2eac4c1b6b8e5f2c3176f6c75a7e2659b008afdeade88af4b3','execution_started':False}
 with os.fdopen(fd,'w',closefd=False) as f:json.dump(receipt,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 d=os.open(BASE,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(d)
 finally:os.close(d)
 print('RESUME1 CAPTURE PIN1 INSTALLED; NO EXECUTION',flush=True)
 print('bytes',len(body),'sha256',hashlib.sha256(body).hexdigest(),flush=True)
finally:os.close(fd)
