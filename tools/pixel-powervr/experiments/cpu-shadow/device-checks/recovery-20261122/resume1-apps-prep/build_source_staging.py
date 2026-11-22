#!/usr/bin/env python3
"""Reproduce the install-only app-auditor transport locally; never runs it."""
import ast
import base64
import gzip
import hashlib
import json
from pathlib import Path
import shlex

HERE = Path(__file__).resolve().parent
CPU = HERE.parents[2]
PACKAGE = HERE / 'package'
TRANSFER = PACKAGE / 'app-auditor-transfer'
FILES = {
    'audit_ios26_apps.py': (34103, '6096521f41a8f2caf1c166495d09df28923135dde02295872b98c97a96378291'),
    'audit_ios26_apps_guest.py': (24987, 'aee8d203cc10fdc2a75d93bed9293d66588190e103cddb50720924c46a43c8c5'),
}
DEPENDENCIES = {
    '/data/local/tmp/pixel-prep-runner-f4d64db/prepare_ios26.py': 'c77bc990e56dcb47d651f9c054c41313a6671498a5b2494e96bb522ae868fb1a',
    '/data/local/tmp/pixel-prep-runner-f4d64db/prepare_ios26_stages.py': '89e242b0c98dd994a04cabaeadc52f8d566ff3fd33fae37e1979ab81fd32b952',
    '/data/local/tmp/pixel-prep-runner-f4d64db/cold_boot_ios26.py': '6a57ed164864eef20aeffd34b14b675a8ac597c20583c9f179414a36b4ccbdeb',
    '/data/local/tmp/pixel-prep-runner-f4d64db/cold_boot_dt.py': '6931310e1318a6397ee2d7eead966bd0fcdeaae9c10038ca2f2aa01de1a45f7e',
    '/data/local/tmp/pixel-boot-checks-counter1/firstboot/guard_ios26_firstboot.py': 'ea40638312d6ac41607806ecb03c148fbd0677df6ab01480e13fd40536869674',
    '/data/local/tmp/pixel-saved-checks-counter1/inspect_ios26_firstboot.py': '2b127ecda390b199287358cdad7e6e7774f5b787148aea524e7b0247a2640cf3',
    '/data/local/tmp/pixel-saved-checks-counter1/inspect_ios26_firstboot_guest.py': 'ada26de8ababb11bb4af20e558708545eb64fd516481359fd5d0ccf6a7cbae2b',
    '/data/local/tmp/pixel-boot-checks-ebbc9c0/auditor/audit_ios26_partition_guest.py': '6874b9b6b68c7fb50c3f9cf05c1b6a86a53f8fed75863c00a6ad9254b1640593',
}


def sha(body):
    return hashlib.sha256(body).hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2) + '\n').encode()


COMMON = '''import base64,hashlib,json,os,stat
from pathlib import Path
BASE=Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TRANSFER=BASE/'resume1-apps-auditor-transfer'
DEST=Path('/data/local/tmp/pixel-app-checks-counter1-resume1')
INSTALL=BASE/'resume1-apps-auditor-install.json'
def read(path,limit):
 if path.resolve(strict=True)!=path: raise ValueError('noncanonical transfer/source path')
 with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
  info=os.fstat(f.fileno())
  if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_uid!=0 or info.st_size>limit: raise ValueError('invalid bounded root-owned file')
  body=f.read(limit+1)
 if len(body)>limit: raise ValueError('input exceeded bound')
 return body
def save(path,body,mode=0o600):
 with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode),'wb') as f:
  os.fchmod(f.fileno(),mode);f.write(body);f.flush();os.fsync(f.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try: os.fsync(fd)
 finally: os.close(fd)
if os.geteuid()!=0 or BASE.resolve(strict=True)!=BASE: raise ValueError('root canonical transfer base required')
'''


def main():
    (PACKAGE / 'app-auditor').mkdir(parents=True, exist_ok=True)
    TRANSFER.mkdir(parents=True, exist_ok=True)
    files = []
    for name, (length, expected) in FILES.items():
        body = (CPU / name).read_bytes()
        if len(body) != length or sha(body) != expected:
            raise ValueError('reviewed app-auditor source differs: ' + name)
        if name == 'audit_ios26_apps.py' and body != (HERE.parent / 'downstream-counter/revision' / name).read_bytes():
            raise ValueError('host source differs from retained reviewed counter1 export')
        (PACKAGE / 'app-auditor' / name).write_bytes(body)
        files.append({'path': name, 'bytes': length, 'sha256': expected, 'body': body.decode()})
    bundle = (json.dumps({'schema': 1, 'kind': 'resume1_apps_auditor_sources', 'files': files},
                         sort_keys=True, separators=(',', ':')) + '\n').encode()
    encoded = base64.b64encode(gzip.compress(bundle, mtime=0))
    chunks = [encoded[n:n + 3500] for n in range(0, len(encoded), 3500)]
    manifest = {'schema': 1, 'kind': 'resume1_apps_auditor_source_transfer',
                'source_directory': '/data/local/tmp/pixel-app-checks-counter1-resume1',
                'bundle_bytes': len(bundle), 'bundle_sha256': sha(bundle),
                'encoded_bytes': len(encoded), 'encoded_sha256': sha(encoded),
                'files': [{k: row[k] for k in ('path', 'bytes', 'sha256')} for row in files],
                'dependencies': DEPENDENCIES,
                'chunks': [{'name': f'chunk-{n:02d}', 'bytes': len(body), 'sha256': sha(body)} for n, body in enumerate(chunks)]}
    mb = json_bytes(manifest)
    (PACKAGE / 'app-auditor-transfer-manifest.json').write_bytes(mb)

    def command(name, code):
        ast.parse(code)
        body = code.encode()
        encoded_source = base64.b64encode(gzip.compress(body, mtime=0)).decode()
        loader = ('import base64,gzip,hashlib; b=gzip.decompress(base64.b64decode(' + repr(encoded_source) +
                  ',validate=True)); assert len(b)==' + str(len(body)) + ' and hashlib.sha256(b).hexdigest()==' +
                  repr(sha(body)) + '; exec(compile(b,' + repr(name) + ',"exec"))')
        line = '/data/data/com.termux/files/usr/bin/python -I -B -c ' + shlex.quote(loader) + '\n'
        if len(line.encode()) > 6000:
            raise ValueError('command exceeds bounded phone transport: ' + name)
        (TRANSFER / (name + '.py')).write_bytes(body)
        (TRANSFER / (name + '.command.txt')).write_text(line)
        return {'name': name, 'source_bytes': len(body), 'source_sha256': sha(body),
                'command_bytes': len(line.encode()), 'command_sha256': sha(line.encode())}

    begin = COMMON + f'''mb=base64.b64decode({base64.b64encode(mb).decode()!r},validate=True)
if hashlib.sha256(mb).hexdigest()!={sha(mb)!r}: raise ValueError('manifest differs')
m=json.loads(mb)
for path in (DEST,INSTALL):
 if os.path.lexists(path): raise ValueError('fresh source/install path required; preserve existing evidence')
if DEST.parent.resolve(strict=True)!=DEST.parent: raise ValueError('noncanonical destination parent')
for path,pin in m['dependencies'].items():
 if hashlib.sha256(read(Path(path),4<<20)).hexdigest()!=pin: raise ValueError('changed prerequisite source: '+path)
TRANSFER.mkdir(mode=0o700)
save(TRANSFER/'manifest.json',mb)
print('APPS AUDITOR SOURCE TRANSFER CREATED; NO EXECUTION',flush=True)
'''
    steps = [command('00-begin', begin)]
    for n, body in enumerate(chunks):
        code = COMMON + f'''if TRANSFER.resolve(strict=True)!=TRANSFER: raise ValueError('transfer path differs')
mb=read(TRANSFER/'manifest.json',{len(mb)})
if hashlib.sha256(mb).hexdigest()!={sha(mb)!r}: raise ValueError('manifest differs')
body={body!r}
if len(body)!={len(body)} or hashlib.sha256(body).hexdigest()!={sha(body)!r}: raise ValueError('chunk differs')
save(TRANSFER/'chunk-{n:02d}',body)
if read(TRANSFER/'chunk-{n:02d}',{len(body)})!=body: raise ValueError('chunk readback differs')
print('APPS AUDITOR CHUNK {n:02d} VERIFIED',flush=True)
'''
        steps.append(command(f'{n + 1:02d}-chunk-{n:02d}', code))
    assembly = COMMON + f'''import datetime,gzip,io
if TRANSFER.resolve(strict=True)!=TRANSFER: raise ValueError('transfer path differs')
mb=read(TRANSFER/'manifest.json',{len(mb)})
if hashlib.sha256(mb).hexdigest()!={sha(mb)!r}: raise ValueError('manifest differs')
m=json.loads(mb)
if {{p.name for p in TRANSFER.iterdir()}}!={{'manifest.json',*(row['name'] for row in m['chunks'])}}: raise ValueError('transfer already assembled or unexpected content')
parts=[]
for row in m['chunks']:
 body=read(TRANSFER/row['name'],row['bytes'])
 if len(body)!=row['bytes'] or hashlib.sha256(body).hexdigest()!=row['sha256']: raise ValueError('stored chunk differs')
 parts.append(body)
encoded=b''.join(parts)
if len(encoded)!=m['encoded_bytes'] or hashlib.sha256(encoded).hexdigest()!=m['encoded_sha256']: raise ValueError('complete transfer differs')
with gzip.GzipFile(fileobj=io.BytesIO(base64.b64decode(encoded,validate=True)),mode='rb') as f: bundle=f.read(m['bundle_bytes']+1)
if len(bundle)!=m['bundle_bytes'] or hashlib.sha256(bundle).hexdigest()!=m['bundle_sha256']: raise ValueError('source bundle differs')
b=json.loads(bundle)
if b.get('schema')!=1 or b.get('kind')!='resume1_apps_auditor_sources' or [{{k:row[k] for k in ('path','bytes','sha256')}} for row in b['files']]!=m['files']: raise ValueError('source inventory differs')
if m['source_directory']!=str(DEST) or set(row['path'] for row in b['files'])!={{'audit_ios26_apps.py','audit_ios26_apps_guest.py'}}: raise ValueError('invalid source destination/inventory')
for row in b['files']:
 body=row['body'].encode()
 if '/' in row['path'] or len(body)!=row['bytes'] or hashlib.sha256(body).hexdigest()!=row['sha256']: raise ValueError('source bytes differ')
for path in (DEST,INSTALL):
 if os.path.lexists(path): raise ValueError('source/install target exists; preserve it')
for path,pin in m['dependencies'].items():
 if hashlib.sha256(read(Path(path),4<<20)).hexdigest()!=pin: raise ValueError('prerequisite source changed: '+path)
save(TRANSFER/'install-reserved.json',b'{{"installation_reserved":true,"execution_started":false}}\\n')
DEST.mkdir(mode=0o755);os.chmod(DEST,0o755)
for row in b['files']:
 body=row['body'].encode();target=DEST/row['path'];save(target,body,0o644)
 if read(target,row['bytes'])!=body: raise ValueError('installed source readback differs')
if {{p.name for p in DEST.iterdir()}}!={{row['path'] for row in m['files']}}: raise ValueError('installed source directory contains unexpected files')
for path,pin in m['dependencies'].items():
 if hashlib.sha256(read(Path(path),4<<20)).hexdigest()!=pin: raise ValueError('prerequisite changed during source install: '+path)
receipt={{'schema':1,'kind':'resume1_apps_auditor_sources_install','source_directory':str(DEST),
 'installed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':m['files'],
 'dependencies':m['dependencies'],'manifest_sha256':hashlib.sha256(mb).hexdigest(),
 'execution_started':False,'preparation_started':False,'helper_started':False}}
save(INSTALL,(json.dumps(receipt,indent=2)+'\\n').encode())
print('APPS AUDITOR SOURCES INSTALLED; NO EXECUTION',flush=True)
for row in m['files']: print(row['path'],row['bytes'],row['sha256'],flush=True)
'''
    steps.append(command(f'{len(chunks) + 1:02d}-assemble-install', assembly))
    (PACKAGE / 'app-auditor-transport-steps.json').write_bytes(json_bytes(steps))
    provenance = {'schema': 1, 'status': 'SOURCE_ONLY_UNRELEASED_OWNER',
                  'source_basis': 'retained downstream-counter reviewed host and unchanged app guest',
                  'source_files': manifest['files'], 'manifest_sha256': sha(mb),
                  'transfer_steps': len(steps), 'maximum_command_bytes': max(row['command_bytes'] for row in steps),
                  'source_install_only': True, 'owner_transport_released': False,
                  'physical_installation_observed': False, 'physical_execution_observed': False}
    (PACKAGE / 'source-staging-provenance.json').write_bytes(json_bytes(provenance))
    print(json.dumps(provenance, indent=2))


if __name__ == '__main__':
    main()
