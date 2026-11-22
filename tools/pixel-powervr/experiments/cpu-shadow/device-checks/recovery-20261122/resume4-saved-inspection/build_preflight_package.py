"""Build the exclusive resume4 outer pair; reuse the installed resume3 inspector."""
from pathlib import Path
import ast
import base64
import gzip
import hashlib
import json
import shlex

OUT = Path(__file__).resolve().parent
R = OUT.parent
BASE = '/data/local/tmp/pixel-gpu-transfer-sxtv33sh'
sha = lambda body: hashlib.sha256(body).hexdigest()


def write(name, body):
    body = body.encode() if isinstance(body, str) else body
    if name.endswith('.py'):
        ast.parse(body)
    target = OUT / name
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        assert target.read_bytes() == body, 'preserve different existing ' + name
    else:
        target.write_bytes(body)
    return body


def command(name, source):
    body = source.encode()
    ast.parse(body)
    encoded = base64.b64encode(gzip.compress(body, mtime=0)).decode()
    loader = ('import base64,gzip,hashlib; b=gzip.decompress(base64.b64decode(' + repr(encoded) +
        ',validate=True)); assert len(b)==' + str(len(body)) + ' and hashlib.sha256(b).hexdigest()==' + repr(sha(body)) +
        '; exec(compile(b,' + repr(name) + ',"exec"))')
    cmd = '/data/data/com.termux/files/usr/bin/python -I -B -c ' + shlex.quote(loader) + '\n'
    assert len(cmd.encode()) <= 6000, (name, len(cmd.encode()))
    write(name + '.py', body)
    write(name + '.command.txt', cmd)
    return {'name': name, 'source_bytes': len(body), 'source_sha256': sha(body),
            'command_bytes': len(cmd.encode()), 'command_sha256': sha(cmd.encode())}


def file_row(local, target, pin):
    body = local.read_bytes()
    assert {'bytes': len(body), 'sha256': sha(body)} == pin, str(local)
    ast.parse(body)
    return {'path': target, 'body': body.decode(), **pin}


def transfer(directory, manifest_name, steps_name, prefix, kind, target, fresh_directory, files):
    bundle = (json.dumps({'schema': 1, 'kind': kind + '_sources', 'files': files}, sort_keys=True, separators=(',', ':')) + '\n').encode()
    encoded = base64.b64encode(gzip.compress(bundle, mtime=0))
    chunks = [encoded[i:i + 3500] for i in range(0, len(encoded), 3500)]
    manifest = {'schema': 1, 'kind': kind + '_source_transfer', 'target_directory': target,
        'fresh_target_directory': fresh_directory, 'bundle_bytes': len(bundle), 'bundle_sha256': sha(bundle),
        'encoded_bytes': len(encoded), 'encoded_sha256': sha(encoded),
        'chunks': [{'name': f'chunk-{i:02d}', 'bytes': len(value), 'sha256': sha(value)} for i, value in enumerate(chunks)],
        'files': [{k: row[k] for k in ('path', 'bytes', 'sha256')} for row in files]}
    mb = write(manifest_name, json.dumps(manifest, indent=2) + '\n')
    common = f'''import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path({BASE!r})
TRANSFER=BASE/{(prefix+'-transfer')!r}
TARGET=Path({target!r})
INSTALL=BASE/{(prefix+'-install.json')!r}
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
'''
    fresh = "if os.path.lexists(TARGET): raise ValueError('preserve existing inspector source directory')\nif TARGET.parent.resolve(strict=True)!=TARGET.parent: raise ValueError('noncanonical inspector parent')\n" if fresh_directory else "if TARGET!=BASE: raise ValueError('unexpected existing source target')\n"
    steps = []
    begin = common + f"manifest=base64.b64decode({base64.b64encode(mb).decode()!r},validate=True)\nif hashlib.sha256(manifest).hexdigest()!={sha(mb)!r}: raise ValueError('manifest differs')\n" + fresh + f"for name in {tuple(row['path'] for row in files)!r}:\n if os.path.lexists(TARGET/name): raise ValueError('source exists; preserve it')\nif os.path.lexists(INSTALL): raise ValueError('install receipt exists; preserve it')\nTRANSFER.mkdir(mode=0o700)\nsave(TRANSFER/'manifest.json',manifest)\nprint('REVIEWED SOURCE TRANSFER CREATED; NO EXECUTION',flush=True)\n"
    steps.append(command(directory + '/00-begin', begin))
    for i, chunk in enumerate(chunks):
        code = common + f"if TRANSFER.resolve(strict=True)!=TRANSFER: raise ValueError('transfer directory differs')\nmb=read(TRANSFER/'manifest.json',{len(mb)})\nif hashlib.sha256(mb).hexdigest()!={sha(mb)!r}: raise ValueError('manifest differs')\nbody={chunk!r}\nif len(body)!={len(chunk)} or hashlib.sha256(body).hexdigest()!={sha(chunk)!r}: raise ValueError('chunk differs')\nsave(TRANSFER/'chunk-{i:02d}',body)\nif read(TRANSFER/'chunk-{i:02d}',{len(chunk)})!=body: raise ValueError('chunk readback differs')\nprint('SOURCE CHUNK {i:02d} VERIFIED',flush=True)\n"
        steps.append(command(directory + f'/{i+1:02d}-chunk-{i:02d}', code))
    assembly = common + f'''import datetime,gzip,io
if TRANSFER.resolve(strict=True)!=TRANSFER: raise ValueError('transfer directory differs')
mb=read(TRANSFER/'manifest.json',{len(mb)})
if hashlib.sha256(mb).hexdigest()!={sha(mb)!r}: raise ValueError('manifest differs')
m=json.loads(mb)
if {{p.name for p in TRANSFER.iterdir()}}!={{'manifest.json',*(r['name'] for r in m['chunks'])}}: raise ValueError('transfer already assembled or unknown files')
parts=[]
for row in m['chunks']:
 b=read(TRANSFER/row['name'],row['bytes'])
 if len(b)!=row['bytes'] or hashlib.sha256(b).hexdigest()!=row['sha256']: raise ValueError('stored chunk differs')
 parts.append(b)
encoded=b''.join(parts)
if len(encoded)!=m['encoded_bytes'] or hashlib.sha256(encoded).hexdigest()!=m['encoded_sha256']: raise ValueError('complete transfer differs')
with gzip.GzipFile(fileobj=io.BytesIO(base64.b64decode(encoded,validate=True)),mode='rb') as f: bb=f.read(m['bundle_bytes']+1)
if len(bb)!=m['bundle_bytes'] or hashlib.sha256(bb).hexdigest()!=m['bundle_sha256']: raise ValueError('source bundle differs')
b=json.loads(bb)
if b.get('schema')!=1 or b.get('kind')!={(kind+'_sources')!r} or [{{k:r[k] for k in ('path','bytes','sha256')}} for r in b['files']]!=m['files']: raise ValueError('bundle manifest differs')
for row in b['files']:
 body=row['body'].encode()
 if '/' in row['path'] or row['path'] in ('','.','..') or len(body)!=row['bytes'] or hashlib.sha256(body).hexdigest()!=row['sha256']: raise ValueError('source bytes differ')
 if os.path.lexists(TARGET/row['path']): raise ValueError('source exists; preserve it')
if os.path.lexists(INSTALL): raise ValueError('install receipt exists; preserve it')
''' + fresh + "save(TRANSFER/'install-reserved.json',b'{\"installation_reserved\":true,\"execution_started\":false}\\n')\n" + ("TARGET.mkdir(mode=0o755)\n" if fresh_directory else '') + f'''if TARGET.resolve(strict=True)!=TARGET: raise ValueError('source target differs')
for row in b['files']:
 body=row['body'].encode();target=TARGET/row['path'];save(target,body,0o644)
 if read(target,row['bytes'])!=body: raise ValueError('installed readback differs')
receipt={{'schema':1,'kind':{(kind+'_sources_install')!r},'installed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':m['files'],'target_directory':str(TARGET),'execution_started':False,'manifest_sha256':hashlib.sha256(mb).hexdigest()}}
save(INSTALL,(json.dumps(receipt,indent=2)+'\\n').encode())
print('REVIEWED SOURCES INSTALLED; NO EXECUTION',str(TARGET),flush=True)
for row in m['files']: print(row['path'],row['bytes'],row['sha256'],flush=True)
'''
    steps.append(command(directory + f'/{len(chunks)+1:02d}-assemble-install', assembly))
    write(steps_name, json.dumps(steps, indent=2) + '\n')
    return {'manifest': manifest_name, 'manifest_bytes': len(mb), 'manifest_sha256': sha(mb),
            'steps': steps, 'max_command_bytes': max(row['command_bytes'] for row in steps)}


owner_pin = {'bytes':48469,'sha256':'c5cc01768be23c0a7e3ad1364cb89a3dd8562288ac3c51f5eaef35ce7c039f10'}
launcher_pin = {'bytes':5926,'sha256':'59aa8fb3850ad61d074e7d8512c7067658936ff128f3bffca77f393e9aedfd58'}
outer_files = [file_row(OUT / 'run_saved_inspection_owner.py','run-ios26-saved-inspection-resume4.py',owner_pin),
               file_row(OUT / 'launch_saved_inspection_preflight.py','launch-ios26-saved-inspection-resume4-preflight.py',launcher_pin)]
outer = transfer('source-transfer','transfer-manifest.json','transport-steps.json','saved-inspection-resume4',
    'saved_inspection_resume4',BASE,False,outer_files)
source_path = BASE + '/launch-ios26-saved-inspection-resume4-preflight.py'
load = f'''from pathlib import Path
import hashlib,os,stat
p=Path({source_path!r})
if os.geteuid()!=0 or p.resolve(strict=True)!=p: raise ValueError('root canonical launcher required')
with os.fdopen(os.open(p,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
 a=os.fstat(f.fileno())
 if not stat.S_ISREG(a.st_mode) or a.st_uid!=0 or a.st_nlink!=1 or a.st_size!={launcher_pin['bytes']}: raise ValueError('launcher identity differs')
 b=f.read({launcher_pin['bytes']+1});z=os.fstat(f.fileno())
if (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)!=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns): raise ValueError('launcher changed during read')
if len(b)!={launcher_pin['bytes']} or hashlib.sha256(b).hexdigest()!={launcher_pin['sha256']!r}: raise ValueError('launcher bytes differ')
exec(compile(b,str(p),'exec'),{{'__name__':'__main__','__file__':str(p)}})
'''
cmd = '/data/data/com.termux/files/usr/bin/python -I -B -c ' + shlex.quote(load) + '\n'
write('launch-preflight.command.txt',cmd)
record={'schema':1,'state':'SOURCE_STAGING_PENDING_INDEPENDENT_TRANSPORT_REVIEW',
 'inspector_directory_reused':'/data/local/tmp/pixel-saved-checks-resume3',
 'inspector_source_transfer_required':False,
 'outer':outer,'source_only_command_order':[r['name']+'.command.txt' for r in outer['steps']],
 'launch_preflight':{'path':'launch-preflight.command.txt','bytes':len(cmd.encode()),'sha256':sha(cmd.encode())},
 'fresh_preflight_pin':None,'inspection_execution_released':False}
write('staging-order.json',json.dumps(record,indent=2)+'\n')
print(json.dumps({'owner':owner_pin,'launcher':launcher_pin,'outer_steps':len(outer['steps']),
 'max_command_bytes':outer['max_command_bytes'],'launch_preflight':record['launch_preflight'],
 'outer_manifest':{k:outer[k] for k in ('manifest_bytes','manifest_sha256')}},indent=2))
