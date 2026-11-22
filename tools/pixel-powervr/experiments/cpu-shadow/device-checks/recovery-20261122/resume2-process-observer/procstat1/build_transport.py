#!/usr/bin/env python3
"""Build bounded install-only observer packets locally; no phone operations."""
import ast
import base64
import gzip
import hashlib
import json
from pathlib import Path
import shlex

HERE = Path(__file__).resolve().parent
TRANSFER = HERE / 'source-transfer'
PHONE = '/data/local/tmp/pixel-gpu-transfer-sxtv33sh'
FILES = [('observe_processes.py', 'run-ios26-saved-inspection-resume2-observer-procstat1.py'),
         ('launch_observer.py', 'launch-ios26-saved-inspection-resume2-observer-procstat1.py')]
OWNER_PIN = {'bytes': 35799, 'sha256': '445f16736ff3f0c4aca2f9d825f4b71b9264bc24b177fe3a8281ca9c6e0f1e0b'}
PREFLIGHT_SHA = '84b31f4f08744f6adeb20ab5af308b1d10c839803c051d4bba577201a4ad3760'


def sha(body):
    return hashlib.sha256(body).hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2) + '\n').encode()


def command(directory, name, source):
    ast.parse(source)
    body = source.encode()
    encoded = base64.b64encode(gzip.compress(body, mtime=0)).decode()
    loader = ('import base64,gzip,hashlib;b=gzip.decompress(base64.b64decode(' + repr(encoded) +
        ',validate=True));assert len(b)==' + str(len(body)) + ' and hashlib.sha256(b).hexdigest()==' + repr(sha(body)) +
        ';exec(compile(b,' + repr(name) + ',"exec"))')
    line = '/data/data/com.termux/files/usr/bin/python -I -B -c ' + shlex.quote(loader) + '\n'
    if len(line.encode()) > 6000:
        raise ValueError('phone command exceeds 6000 bytes: ' + name)
    (directory / (name + '.py')).write_bytes(body)
    (directory / (name + '.command.txt')).write_text(line)
    return {'name': name, 'source_bytes': len(body), 'source_sha256': sha(body),
            'command_bytes': len(line.encode()), 'command_sha256': sha(line.encode())}


COMMON = '''import base64,hashlib,json,os,stat
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
'''


def main():
    TRANSFER.mkdir(exist_ok=True)
    files = []
    for local, phone in FILES:
        body = (HERE / local).read_bytes()
        ast.parse(body)
        files.append({'path': phone, 'bytes': len(body), 'sha256': sha(body), 'body': body.decode()})
    source_pin = {k: files[0][k] for k in ('bytes', 'sha256')}
    for local in ('launch_observer.py', 'observe_ready.py'):
        tree = ast.parse((HERE / local).read_text())
        pins = [ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign) and
                any(isinstance(t, ast.Name) and t.id == 'SOURCE_PIN' for t in node.targets)]
        if pins != [source_pin]:
            raise ValueError('observer binding differs: ' + local)
    bundle = (json.dumps({'schema': 1, 'kind': 'resume2_process_observer_procstat1_sources', 'files': files},
                         sort_keys=True, separators=(',', ':')) + '\n').encode()
    encoded = base64.b64encode(gzip.compress(bundle, mtime=0))
    chunks = [encoded[n:n + 3500] for n in range(0, len(encoded), 3500)]
    manifest = {'schema': 1, 'kind': 'resume2_process_observer_procstat1_source_transfer',
        'bundle_bytes': len(bundle), 'bundle_sha256': sha(bundle), 'encoded_bytes': len(encoded), 'encoded_sha256': sha(encoded),
        'files': [{k: r[k] for k in ('path', 'bytes', 'sha256')} for r in files],
        'inspection_owner_source': {'path': str(PHONE + '/run-ios26-saved-inspection-resume2.py'), **OWNER_PIN},
        'chunks': [{'name': f'chunk-{n:02d}', 'bytes': len(b), 'sha256': sha(b)} for n, b in enumerate(chunks)]}
    mb = json_bytes(manifest)
    (HERE / 'transfer-manifest.json').write_bytes(mb)
    verify_owner = "p=m['inspection_owner_source'];owner_body=read(OWNER_SOURCE,p['bytes'])\nif len(owner_body)!=p['bytes'] or hashlib.sha256(owner_body).hexdigest()!=p['sha256']: raise ValueError('inspection owner source differs')\n"
    load_manifest = f"mb=read(TRANSFER/'manifest.json',{len(mb)})\nif hashlib.sha256(mb).hexdigest()!={sha(mb)!r}: raise ValueError('manifest differs')\nm=json.loads(mb)\n"
    begin = COMMON + f"mb=base64.b64decode({base64.b64encode(mb).decode()!r},validate=True)\nif hashlib.sha256(mb).hexdigest()!={sha(mb)!r}: raise ValueError('manifest differs')\nm=json.loads(mb)\nfresh(m['files'])\n" + verify_owner + "TRANSFER.mkdir(mode=0o700)\nsave(TRANSFER/'manifest.json',mb)\nprint('OBSERVER SOURCE TRANSFER CREATED; NO EXECUTION',flush=True)\n"
    steps = [command(TRANSFER, '00-begin', begin)]
    for n, body in enumerate(chunks):
        code = COMMON + load_manifest + f"body={body!r}\nif len(body)!={len(body)} or hashlib.sha256(body).hexdigest()!={sha(body)!r}: raise ValueError('chunk differs')\nsave(TRANSFER/'chunk-{n:02d}',body)\nif read(TRANSFER/'chunk-{n:02d}',{len(body)})!=body: raise ValueError('chunk readback differs')\nprint('OBSERVER CHUNK {n:02d} VERIFIED',flush=True)\n"
        steps.append(command(TRANSFER, f'{n + 1:02d}-chunk-{n:02d}', code))
    assembly = COMMON + 'import datetime,gzip,io\n' + load_manifest + '''if {p.name for p in TRANSFER.iterdir()}!={'manifest.json',*(r['name'] for r in m['chunks'])}: raise ValueError('transfer already assembled or unexpected content')
parts=[]
for r in m['chunks']:
 b=read(TRANSFER/r['name'],r['bytes'])
 if len(b)!=r['bytes'] or hashlib.sha256(b).hexdigest()!=r['sha256']: raise ValueError('stored chunk differs')
 parts.append(b)
encoded=b''.join(parts)
if len(encoded)!=m['encoded_bytes'] or hashlib.sha256(encoded).hexdigest()!=m['encoded_sha256']: raise ValueError('encoded bundle differs')
with gzip.GzipFile(fileobj=io.BytesIO(base64.b64decode(encoded,validate=True)),mode='rb') as f: bundle=f.read(m['bundle_bytes']+1)
if len(bundle)!=m['bundle_bytes'] or hashlib.sha256(bundle).hexdigest()!=m['bundle_sha256']: raise ValueError('bundle differs')
b=json.loads(bundle)
if b.get('schema')!=1 or b.get('kind')!='resume2_process_observer_procstat1_sources' or [{k:r[k] for k in ('path','bytes','sha256')} for r in b['files']]!=m['files']: raise ValueError('source inventory differs')
if [r['path'] for r in b['files']]!=['run-ios26-saved-inspection-resume2-observer-procstat1.py','launch-ios26-saved-inspection-resume2-observer-procstat1.py']: raise ValueError('source destinations differ')
for r in b['files']:
 body=r['body'].encode()
 if '/' in r['path'] or len(body)!=r['bytes'] or hashlib.sha256(body).hexdigest()!=r['sha256']: raise ValueError('source differs')
fresh(m['files'])
''' + verify_owner + '''save(TRANSFER/'install-reserved.json',b'{"installation_reserved":true,"execution_started":false}\\n')
for r in b['files']:
 body=r['body'].encode();save(BASE/r['path'],body,0o644)
 if read(BASE/r['path'],r['bytes'])!=body: raise ValueError('installed source readback differs')
''' + verify_owner + '''receipt={'schema':1,'kind':'resume2_process_observer_procstat1_sources_install','installed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':m['files'],'inspection_owner_source':m['inspection_owner_source'],'manifest_sha256':hashlib.sha256(mb).hexdigest(),'execution_started':False,'inspection_started':False}
save(INSTALL,(json.dumps(receipt,indent=2)+'\\n').encode())
print('OBSERVER SOURCES INSTALLED; NO EXECUTION',flush=True)
for r in m['files']: print(r['path'],r['bytes'],r['sha256'],flush=True)
'''
    steps.append(command(TRANSFER, f'{len(chunks) + 1:02d}-assemble-install', assembly))
    (HERE / 'transport-steps.json').write_bytes(json_bytes(steps))
    launcher = files[1]
    launch_source = COMMON + f"p=BASE/{launcher['path']!r}\nb=read(p,{launcher['bytes']})\nif len(b)!={launcher['bytes']} or hashlib.sha256(b).hexdigest()!={launcher['sha256']!r}: raise ValueError('launcher source differs')\nimport sys\nsys.argv=[str(p),'--preflight-sha256',{PREFLIGHT_SHA!r},'--preflight-bytes','9070']\nexec(compile(b,str(p),'exec'),{{'__name__':'__main__','__file__':str(p)}})\n"
    # Source builder writes distinct launcher wrapper name; never replaces launch_observer.py.
    launch_step = command(HERE, 'launch-observer', launch_source)
    ready_step = command(HERE, 'observe-ready', (HERE / 'observe_ready.py').read_text())
    result = {'schema': 1, 'status': 'READY_FOR_INDEPENDENT_REVIEW', 'source_install_only': True,
              'files': manifest['files'], 'manifest_sha256': sha(mb), 'steps': len(steps),
              'maximum_install_command_bytes': max(r['command_bytes'] for r in steps),
              'launch_command': launch_step, 'ready_command': ready_step,
              'physical_installation_observed': False, 'physical_execution_observed': False}
    (HERE / 'package-status.json').write_bytes(json_bytes(result))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
