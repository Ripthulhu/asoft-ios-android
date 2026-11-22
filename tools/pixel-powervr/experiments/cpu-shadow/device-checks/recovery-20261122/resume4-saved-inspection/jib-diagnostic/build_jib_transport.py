"""Build exclusive source-only staging and a separate launch from an exact frozen pin.

This local builder never imports the diagnostic or accesses a device.  Existing
generated files may be reused only when their complete bytes are identical.
"""
from pathlib import Path
import argparse
import ast
import base64
import gzip
import hashlib
import json
import re
import shlex


ROOT = Path(__file__).resolve().parent
BASE = '/data/local/tmp/pixel-gpu-transfer-sxtv33sh'
PHONE_NAME = 'run-ios26-root-jib-diagnostic-resume4.py'
OUTPUT_NAME = 'ios26-root-jib-diagnostic-resume4'
TRANSFER_NAME = 'root-jib-diagnostic-resume4-transfer'
INSTALL_NAME = 'root-jib-diagnostic-resume4-install.json'
PYTHON = '/data/data/com.termux/files/usr/bin/python'
BUNDLE_KIND = 'root_jib_diagnostic_resume4_sources'
INSTALL_KIND = 'root_jib_diagnostic_resume4_sources_install'


def sha(body):
    return hashlib.sha256(body).hexdigest()


def write(name, body):
    body = body.encode() if isinstance(body, str) else body
    if name.endswith('.py'):
        ast.parse(body)
    path = ROOT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        assert path.read_bytes() == body, 'preserve differing existing ' + str(path)
    else:
        with path.open('xb') as stream:
            stream.write(body)
    return body


def wrapped_command(label, code):
    ast.parse(code)
    body = code.encode()
    encoded = base64.b64encode(gzip.compress(body, mtime=0)).decode()
    loader = ('import base64,gzip,hashlib; b=gzip.decompress(base64.b64decode(' + repr(encoded) +
              ',validate=True)); assert len(b)==' + str(len(body)) +
              ' and hashlib.sha256(b).hexdigest()==' + repr(sha(body)) +
              '; exec(compile(b,' + repr(label) + ',"exec"))')
    command = PYTHON + ' -I -B -c ' + shlex.quote(loader) + '\n'
    assert len(command.encode()) <= 6000, (label, len(command.encode()))
    return command


COMMON = '''import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'root-jib-diagnostic-resume4-transfer'
def read(path,limit):
 if path.resolve(strict=True)!=path: raise ValueError('noncanonical transfer path')
 with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
  a=os.fstat(f.fileno())
  if not stat.S_ISREG(a.st_mode) or a.st_nlink!=1 or a.st_uid!=0 or a.st_size>limit: raise ValueError('invalid transfer file')
  b=f.read(limit+1);z=os.fstat(f.fileno())
 if len(b)!=a.st_size or len(b)>limit or (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)!=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns): raise ValueError('transfer input changed or exceeded bound')
 return b
def save(path,body,mode=0o600):
 with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode),'wb') as f:
  f.write(body);f.flush();os.fsync(f.fileno())
 d=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try: os.fsync(d)
 finally: os.close(d)
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
'''


def build(source_bytes, source_sha256):
    assert type(source_bytes) is int and 0 < source_bytes <= 128 << 10
    assert re.fullmatch('[a-f0-9]{64}', source_sha256)
    source = (ROOT / 'inspect_root_jib.py').read_bytes()
    assert {'bytes': len(source), 'sha256': sha(source)} == {
        'bytes': source_bytes, 'sha256': source_sha256}, 'frozen source pin differs'
    ast.parse(source)
    files = [{'path': PHONE_NAME, 'body': source.decode(), 'bytes': len(source), 'sha256': sha(source)}]
    bundle = (json.dumps({'schema': 1, 'kind': BUNDLE_KIND, 'files': files},
                         sort_keys=True, separators=(',', ':')) + '\n').encode()
    encoded = base64.b64encode(gzip.compress(bundle, mtime=0))
    chunks = [encoded[index:index + 3500] for index in range(0, len(encoded), 3500)]
    manifest = {'schema': 1, 'kind': 'root_jib_diagnostic_resume4_source_transfer',
                'bundle_bytes': len(bundle), 'bundle_sha256': sha(bundle),
                'encoded_bytes': len(encoded), 'encoded_sha256': sha(encoded),
                'chunks': [{'name': f'chunk-{index:02d}', 'bytes': len(body), 'sha256': sha(body)}
                           for index, body in enumerate(chunks)],
                'files': [{key: row[key] for key in ('path', 'bytes', 'sha256')} for row in files]}
    mb = write('transfer-manifest.json', json.dumps(manifest, indent=2) + '\n')
    steps = []

    def step(label, code):
        command = wrapped_command(label, code)
        write('source-transfer/' + label + '.py', code)
        write('source-transfer/' + label + '.command.txt', command)
        steps.append({'name': label, 'command_bytes': len(command.encode()),
                      'command_sha256': sha(command.encode()), 'source_bytes': len(code.encode()),
                      'source_sha256': sha(code.encode())})

    targets = (PHONE_NAME, INSTALL_NAME, OUTPUT_NAME)
    step('00-begin', COMMON + f'''manifest=base64.b64decode({base64.b64encode(mb).decode()!r},validate=True)
if len(manifest)!={len(mb)} or hashlib.sha256(manifest).hexdigest()!={sha(mb)!r}: raise ValueError('manifest differs')
for name in {targets!r}:
 if os.path.lexists(BASE/name): raise ValueError('target already exists; preserve it')
TRANSFER.mkdir(mode=0o700)
save(TRANSFER/'manifest.json',manifest)
print('ROOT JIB DIAGNOSTIC TRANSFER CREATED',flush=True)
''')
    for index, chunk in enumerate(chunks):
        step(f'{index + 1:02d}-chunk-{index:02d}', COMMON + f'''if TRANSFER.resolve(strict=True)!=TRANSFER: raise ValueError('transfer directory differs')
mb=read(TRANSFER/'manifest.json',{len(mb)})
if len(mb)!={len(mb)} or hashlib.sha256(mb).hexdigest()!={sha(mb)!r}: raise ValueError('manifest differs')
body={chunk!r}
if len(body)!={len(chunk)} or hashlib.sha256(body).hexdigest()!={sha(chunk)!r}: raise ValueError('chunk differs')
save(TRANSFER/'chunk-{index:02d}',body)
if read(TRANSFER/'chunk-{index:02d}',{len(chunk)})!=body: raise ValueError('chunk readback differs')
print('ROOT JIB DIAGNOSTIC CHUNK {index:02d} VERIFIED',flush=True)
''')
    step(f'{len(chunks) + 1:02d}-assemble-install', COMMON + f'''import datetime,gzip,io
if TRANSFER.resolve(strict=True)!=TRANSFER: raise ValueError('transfer directory differs')
mb=read(TRANSFER/'manifest.json',{len(mb)})
if len(mb)!={len(mb)} or hashlib.sha256(mb).hexdigest()!={sha(mb)!r}: raise ValueError('manifest differs')
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
if b.get('schema')!=1 or b.get('kind')!={BUNDLE_KIND!r} or [{{k:x[k] for k in ('path','bytes','sha256')}} for x in b['files']]!=m['files']: raise ValueError('bundle manifest differs')
if [row['path'] for row in b['files']]!=[{PHONE_NAME!r}]: raise ValueError('unexpected source inventory')
for row in b['files']:
 body=row['body'].encode()
 if len(body)!=row['bytes'] or hashlib.sha256(body).hexdigest()!=row['sha256']: raise ValueError('source bytes differ')
for name in {targets!r}:
 if os.path.lexists(BASE/name): raise ValueError('target already exists; preserve it')
save(TRANSFER/'install-reserved.json',b'{{"installation_reserved":true,"execution_started":false}}\\n')
for row in b['files']:
 body=row['body'].encode();target=BASE/row['path'];save(target,body,0o644)
 if read(target,row['bytes'])!=body: raise ValueError('installed readback differs')
receipt={{'schema':1,'kind':{INSTALL_KIND!r},'installed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':m['files'],'execution_started':False,'manifest_sha256':hashlib.sha256(mb).hexdigest()}}
save(BASE/{INSTALL_NAME!r},(json.dumps(receipt,indent=2)+'\\n').encode())
print('ROOT JIB DIAGNOSTIC SOURCE INSTALLED; NO EXECUTION',flush=True)
for row in m['files']: print(row['path'],row['bytes'],row['sha256'],flush=True)
''')
    write('transport-steps.json', json.dumps(steps, indent=2) + '\n')

    launch = COMMON + f'''SOURCE=BASE/{PHONE_NAME!r}
OUT=BASE/{OUTPUT_NAME!r}
if os.path.lexists(OUT): raise ValueError('preserve existing diagnostic output')
mb=read(TRANSFER/'manifest.json',{len(mb)})
if len(mb)!={len(mb)} or hashlib.sha256(mb).hexdigest()!={sha(mb)!r}: raise ValueError('installed transfer manifest differs')
installation=json.loads(read(BASE/{INSTALL_NAME!r},65536))
if installation.get('schema')!=1 or installation.get('kind')!={INSTALL_KIND!r} or installation.get('execution_started') is not False or installation.get('files')!={manifest['files']!r} or installation.get('manifest_sha256')!={sha(mb)!r}: raise ValueError('source installation receipt differs')
body=read(SOURCE,{len(source)})
if len(body)!={len(source)} or hashlib.sha256(body).hexdigest()!={sha(source)!r}: raise ValueError('diagnostic source bytes differ')
exec(compile(body,str(SOURCE),'exec'),{{'__name__':'__main__','__file__':str(SOURCE)}})
'''
    launch_body = write('launch_jib_diagnostic.py', launch)
    launch_command = write('run-jib-diagnostic.command.txt', wrapped_command('root-jib-diagnostic-launch', launch))
    reader_draft = Path(__file__).with_name('observe_jib_result_pin_UNRELEASED.py').read_bytes()
    reader_source = reader_draft.decode()
    assert reader_source.count('SOURCE_PIN = None') == 1
    reader_source = reader_source.replace('SOURCE_PIN = None', 'SOURCE_PIN = ' +
                                          repr({'bytes': len(source), 'sha256': sha(source)}))
    before, after = ast.parse(reader_draft), ast.parse(reader_source)
    for tree in (before, after):
        tree.body = [node for node in tree.body if not (isinstance(node, ast.Assign) and
                     any(isinstance(target, ast.Name) and target.id == 'SOURCE_PIN' for target in node.targets))]
    assert ast.dump(before) == ast.dump(after), 'binding-reader delta exceeded source pin'
    reader_body = write('observe_jib_result_pin.py', reader_source)
    reader_command = write('observe-jib-result-pin.command.txt',
                           wrapped_command('readonly-root-jib-result-binding', reader_source))
    record = {'schema': 1, 'state': 'SOURCE_STAGING_AND_SEPARATE_LAUNCH_PENDING_INDEPENDENT_REVIEW',
              'source': {'path': BASE + '/' + PHONE_NAME, 'bytes': len(source), 'sha256': sha(source)},
              'source_only_installation': True, 'diagnostic_executed_locally': False,
              'fresh_phone_output': BASE + '/' + OUTPUT_NAME,
              'manifest': {'bytes': len(mb), 'sha256': sha(mb)},
              'steps': len(steps), 'max_transfer_command_bytes': max(row['command_bytes'] for row in steps),
              'launcher': {'bytes': len(launch_body), 'sha256': sha(launch_body)},
              'launch_command': {'bytes': len(launch_command), 'sha256': sha(launch_command)},
              'future_result_binding_reader': {'bytes': len(reader_body), 'sha256': sha(reader_body)},
              'future_result_binding_command': {'bytes': len(reader_command), 'sha256': sha(reader_command)},
              'builder': {'bytes': len(Path(__file__).read_bytes()), 'sha256': sha(Path(__file__).read_bytes())},
              'actual_result_binding': None, 'scalar_projection_released': False}
    write('transport-build.json', json.dumps(record, indent=2) + '\n')
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-bytes', required=True, type=int)
    parser.add_argument('--source-sha256', required=True)
    arguments = parser.parse_args()
    print(json.dumps(build(arguments.source_bytes, arguments.source_sha256), indent=2))
