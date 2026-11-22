"""Finalize only from an independently reviewed actual native capability pass."""
from pathlib import Path
import ast
import base64
import gzip
import hashlib
import json
import re
import shlex
import sys

OUT = Path(__file__).resolve().parent
BASE = '/data/local/tmp/pixel-gpu-transfer-sxtv33sh'
sha = lambda body: hashlib.sha256(body).hexdigest()


def write(name, body):
    body = body.encode() if isinstance(body, str) else body
    if name.endswith('.py'):
        ast.parse(body)
    path = OUT / name
    if path.exists():
        assert path.read_bytes() == body, 'preserve differing existing ' + str(path)
    else:
        path.write_bytes(body)
    return body


if len(sys.argv) != 2:
    raise SystemExit('Usage: finalize_header_diagnostic.py ACTUAL_REVIEWED_CAPABILITY_JSON')
observation_path = Path(sys.argv[1]).resolve(strict=True)
observation = observation_path.read_bytes()
observed = json.loads(observation)
assert observed.get('independently_reviewed') is True or observed.get('independent_review_pending') is False
assert (observation_path.parent / observed['independent_review']).resolve(strict=True).is_file()
assert observed['status'] == 'QEMU_IMG_READ_CAPABILITY_PASSED'
assert observed['diagnostic_only'] is True and observed['existing_disk_images_opened'] is False
assert observed['guest_vm_started'] is False and observed['owned_tool_children_reaped'] is True
assert observed['forced_tool_children'] == [] and observed['bound_tooling_and_session_unchanged'] is True
assert observed['expected_bytes_match'] is True and observed['input_unchanged'] is True
assert observed['synthetic_input_bytes'] == 2048 and observed['skip_blocks'] == 2 and observed['count_blocks'] == 3
assert observed['count_semantics'] == 'input_limit_before_skip' and observed['output_bytes'] == 512
assert observed['error'] is None and observed['preservation_error'] is None
assert observed['tool'] == {'path': '/data/local/tmp/pixel-tools-1528a782/tools/qemu-img', 'bytes': 2356032,
    'sha256': '1bd2fd6b968c492d0263436c260af2a8c2ee807cf4afd4fd2abb3300446e2440'}
row = observed['result']
assert row['path'] == BASE + '/ios26-hfs-header-capability-resume4/result.json'
assert type(row['bytes']) is int and 0 < row['bytes'] <= 65536
assert re.fullmatch('[a-f0-9]{64}', row['sha256'])
assert len(row['digest_bytes']) == 32 and all(type(v) is int and 0 <= v <= 255 for v in row['digest_bytes'])
assert bytes(row['digest_bytes']).hex() == row['sha256']
pin = {key: row[key] for key in ('bytes', 'sha256')}
draft = (OUT / 'inspect_hfs_headers_capability4_UNRELEASED.py').read_bytes()
assert len(draft) == 22684 and sha(draft) == 'dcdc2556dfd330eecffdd6e5a7d1d2918138f28a0c28dd3a5f9a7cec4a81b7f3'
old = 'CAPABILITY_PIN = None  # Finalize only from the actual independently reviewed passed native capability receipt.'
assert draft.decode().count(old) == 1
source = draft.decode().replace(old, 'CAPABILITY_PIN = ' + repr(pin) + '  # Actual independently reviewed native capability pass.')
a, b = ast.parse(draft), ast.parse(source)
for tree in (a, b):
    tree.body = [node for node in tree.body if not (isinstance(node, ast.Assign) and
        any(isinstance(target, ast.Name) and target.id == 'CAPABILITY_PIN' for target in node.targets))]
assert ast.dump(a) == ast.dump(b)
body = write('inspect_hfs_headers.py', source)
files = [{'path': 'run-ios26-hfs-header-diagnostic-resume2.py', 'body': source, 'bytes': len(body), 'sha256': sha(body)}]
bundle = (json.dumps({'schema': 1, 'kind': 'hfs_header_diagnostic_resume2_sources', 'files': files},
                     sort_keys=True, separators=(',', ':')) + '\n').encode()
encoded = base64.b64encode(gzip.compress(bundle, mtime=0))
chunks = [encoded[i:i + 3500] for i in range(0, len(encoded), 3500)]
manifest = {'schema': 1, 'kind': 'hfs_header_diagnostic_resume2_source_transfer',
            'bundle_bytes': len(bundle), 'bundle_sha256': sha(bundle),
            'encoded_bytes': len(encoded), 'encoded_sha256': sha(encoded),
            'chunks': [{'name': f'chunk-{i:02d}', 'bytes': len(x), 'sha256': sha(x)} for i, x in enumerate(chunks)],
            'files': [{k: row[k] for k in ('path', 'bytes', 'sha256')} for row in files]}
mb = write('transfer-manifest.json', json.dumps(manifest, indent=2) + '\n')
D = OUT / 'source-transfer'
D.mkdir(exist_ok=True)

common = '''import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'hfs-header-diagnostic-resume2-transfer'
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
'''


def command(name, code):
    ast.parse(code)
    b = code.encode()
    enc = base64.b64encode(gzip.compress(b, mtime=0)).decode()
    loader = ('import base64,gzip,hashlib; b=gzip.decompress(base64.b64decode(' + repr(enc) +
              ',validate=True)); assert len(b)==' + str(len(b)) + ' and hashlib.sha256(b).hexdigest()==' +
              repr(sha(b)) + '; exec(compile(b,' + repr(name) + ',"exec"))')
    cmd = '/data/data/com.termux/files/usr/bin/python -I -B -c ' + shlex.quote(loader) + '\n'
    assert len(cmd.encode()) <= 6000, (name, len(cmd))
    write('source-transfer/' + name + '.py', b)
    write('source-transfer/' + name + '.command.txt', cmd)
    return {'name': name, 'command_bytes': len(cmd.encode()), 'command_sha256': sha(cmd.encode()),
            'source_bytes': len(b), 'source_sha256': sha(b)}


steps = []
targets = tuple([x['path'] for x in files] + ['hfs-header-diagnostic-resume2-install.json'])
steps.append(command('00-begin', common + f"manifest=base64.b64decode({base64.b64encode(mb).decode()!r},validate=True)\nif hashlib.sha256(manifest).hexdigest()!={sha(mb)!r}: raise ValueError('manifest differs')\nfor name in {targets!r}:\n if os.path.lexists(BASE/name): raise ValueError('target already exists; preserve it')\nTRANSFER.mkdir(mode=0o700)\nsave(TRANSFER/'manifest.json',manifest)\nprint('HFS HEADER DIAGNOSTIC TRANSFER CREATED',flush=True)\n"))
for i, chunk in enumerate(chunks):
    steps.append(command(f'{i+1:02d}-chunk-{i:02d}', common + f"if TRANSFER.resolve(strict=True)!=TRANSFER: raise ValueError('transfer directory differs')\nmb=read(TRANSFER/'manifest.json',{len(mb)})\nif hashlib.sha256(mb).hexdigest()!={sha(mb)!r}: raise ValueError('manifest differs')\nbody={chunk!r}\nif len(body)!={len(chunk)} or hashlib.sha256(body).hexdigest()!={sha(chunk)!r}: raise ValueError('chunk differs')\nsave(TRANSFER/'chunk-{i:02d}',body)\nif read(TRANSFER/'chunk-{i:02d}',{len(chunk)})!=body: raise ValueError('chunk readback differs')\nprint('HFS HEADER DIAGNOSTIC CHUNK {i:02d} VERIFIED',flush=True)\n"))
assembly = common + f'''import datetime,gzip,io
if TRANSFER.resolve(strict=True)!=TRANSFER: raise ValueError('transfer directory differs')
mb=read(TRANSFER/'manifest.json',{len(mb)})
if hashlib.sha256(mb).hexdigest()!={sha(mb)!r}: raise ValueError('manifest differs')
m=json.loads(mb)
if {{x.name for x in TRANSFER.iterdir()}}!={{'manifest.json',*(x['name'] for x in m['chunks'])}}: raise ValueError('transfer already assembled or unknown files')
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
if b.get('schema')!=1 or b.get('kind')!='hfs_header_diagnostic_resume2_sources' or [{{k:x[k] for k in ('path','bytes','sha256')}} for x in b['files']]!=m['files']: raise ValueError('bundle manifest differs')
for row in b['files']:
 body=row['body'].encode()
 if '/' in row['path'] or len(body)!=row['bytes'] or hashlib.sha256(body).hexdigest()!=row['sha256']: raise ValueError('source bytes differ')
 if os.path.lexists(BASE/row['path']): raise ValueError('source already exists; preserve it')
if os.path.lexists(BASE/'hfs-header-diagnostic-resume2-install.json'): raise ValueError('install receipt exists; preserve it')
save(TRANSFER/'install-reserved.json',b'{{"installation_reserved":true,"execution_started":false}}\\n')
for row in b['files']:
 body=row['body'].encode();target=BASE/row['path'];save(target,body,0o644)
 if read(target,row['bytes'])!=body: raise ValueError('installed readback differs')
receipt={{'schema':1,'kind':'hfs_header_diagnostic_resume2_sources_install','installed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':m['files'],'execution_started':False,'manifest_sha256':hashlib.sha256(mb).hexdigest()}}
save(BASE/'hfs-header-diagnostic-resume2-install.json',(json.dumps(receipt,indent=2)+'\\n').encode())
print('HFS HEADER DIAGNOSTIC SOURCES INSTALLED; NO EXECUTION',flush=True)
for row in m['files']:print(row['path'],row['bytes'],row['sha256'],flush=True)
'''
steps.append(command(f'{len(chunks)+1:02d}-assemble-install', assembly))
write('transport-steps.json', json.dumps(steps, indent=2) + '\n')

source_path = BASE + '/run-ios26-hfs-header-diagnostic-resume2.py'
load = f'''from pathlib import Path
import hashlib,os,stat
p=Path({source_path!r})
if os.geteuid()!=0 or p.resolve(strict=True)!=p: raise ValueError('root canonical source required')
with os.fdopen(os.open(p,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
 a=os.fstat(f.fileno())
 if not stat.S_ISREG(a.st_mode) or a.st_uid!=0 or a.st_nlink!=1 or a.st_size!={len(body)}: raise ValueError('source identity differs')
 b=f.read({len(body)+1})
 z=os.fstat(f.fileno())
if (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)!=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns): raise ValueError('source changed during read')
if len(b)!={len(body)} or hashlib.sha256(b).hexdigest()!={sha(body)!r}: raise ValueError('source bytes differ')
exec(compile(b,str(p),'exec'),{{'__name__':'__main__','__file__':str(p)}})
'''
cmd = '/data/data/com.termux/files/usr/bin/python -I -B -c ' + shlex.quote(load) + '\n'
assert len(cmd.encode()) <= 6000
write('run-header-diagnostic.command.txt', cmd)
record = {'schema': 1, 'state': 'FINALIZED_HEADER_DIAGNOSTIC_PENDING_INDEPENDENT_RELEASE_REVIEW',
    'actual_capability_observation': {'path': str(observation_path), 'bytes': len(observation), 'sha256': sha(observation)},
    'actual_capability': {'path': row['path'], **pin}, 'reviewed_draft_sha256': sha(draft),
    'source': {'path': source_path, 'bytes': len(body), 'sha256': sha(body)},
    'transfer_manifest_sha256': sha(mb), 'transfer_steps': len(steps),
    'max_transfer_command_bytes': max(step['command_bytes'] for step in steps),
    'command': {'bytes': len(cmd.encode()), 'sha256': sha(cmd.encode())},
    'disk_images_opened_locally': False, 'inspection_success_claimed': False}
write('capability-binding-finalization.json', json.dumps(record, indent=2) + '\n')
print(json.dumps(record, indent=2))
