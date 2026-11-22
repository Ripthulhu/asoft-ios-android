"""Bind execution staging/readers only to actual independently reviewed fresh preflight."""
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

assert len(sys.argv) == 2, 'actual independently reviewed preflight observation required'
observed_path = Path(sys.argv[1]).resolve(strict=True)
observed_body = observed_path.read_bytes()
v = json.loads(observed_body)
assert v.get('independently_reviewed') is True or v.get('independent_review_pending') is False
assert (observed_path.parent / v['independent_review']).resolve(strict=True).is_file()
assert v['schema'] == 1 and v['status'] == 'SAVED_INSPECTION_PREFLIGHT_BINDING_READY' and v['readonly'] is True
assert v['preflight_status'] == 'PREFLIGHT_READY' and v['accepted'] is True
assert v['exit_code'] == v['owner_exit_code'] == 0 and v['runner_reaped'] is True and v['forced_runner'] is False
assert v['wrapper_absent'] is True and v['runner_absent'] is True and v['work_absent'] is True
assert v['inputs_unchanged'] is True and v['execution_started'] is False
preflight = v['preflight']
assert preflight['path'] == BASE + '/ios26-saved-inspection-resume4-owner/preflight.json'
assert type(preflight['bytes']) is int and 0 < preflight['bytes'] <= 2 << 20
assert re.fullmatch('[a-f0-9]{64}', preflight['sha256'])
assert len(preflight['digest_bytes']) == 32 and all(type(x) is int and 0 <= x <= 255 for x in preflight['digest_bytes'])
assert bytes(preflight['digest_bytes']).hex() == preflight['sha256']
preflight_pin = {key: preflight[key] for key in ('bytes', 'sha256')}
monitor_pin = {'bytes':37877,'sha256':'949da38590f86d827e6b9fb2f261e785e89b4e3cfe1efdbfbea60354cd281ed9'}
monitor = (R / 'resume4-process-observer/procstat1/observe_processes.py').read_bytes()
assert {'bytes':len(monitor),'sha256':sha(monitor)} == monitor_pin
assert (R / 'resume4-process-observer/procstat1/independent-install-review.json').is_file()
draft = (OUT / 'launch_saved_inspection_execution_UNRELEASED.py').read_bytes()
assert len(draft)==22157 and sha(draft)=='8652bc99d23886bf04e6bc994ef43001069a06f3a03a58e9d4a522fead092336'
source = draft.decode()
for name,value in {'PREFLIGHT_SHA256':preflight_pin['sha256'],'PREFLIGHT_BYTES':preflight_pin['bytes'],'MONITOR_PIN':monitor_pin}.items():
    assert source.count(name+' = None') == 1
    source=source.replace(name+' = None',name+' = '+repr(value))
a,b=ast.parse(draft),ast.parse(source)
for tree in (a,b):
    tree.body=[n for n in tree.body if not(isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('PREFLIGHT_SHA256','PREFLIGHT_BYTES','MONITOR_PIN') for t in n.targets))]
assert ast.dump(a)==ast.dump(b)
body=write('launch_saved_inspection_execution.py',source)
launcher_pin={'bytes':len(body),'sha256':sha(body)}
files=[{'path':'launch-ios26-saved-inspection-resume4-execute-procstat1.py','body':source,**launcher_pin}]
transfer_record=transfer('execution-source-transfer','execution-transfer-manifest.json','execution-transport-steps.json',
    'saved-inspection-resume4-execution-procstat1','saved_inspection_resume4_execution_procstat1',BASE,False,files)
# The runtime command still requires a separately observed/reviewed actual ready receipt.
old_builder=(R/'resume2-saved-inspection/procstat1/build_execution_command.py').read_bytes()
assert len(old_builder)==5574 and sha(old_builder)=='c88a4e4dc5878358bbef6ce77452fe24ec06696cd1ee9aa38b1169993bb173b2'
new_builder=old_builder.decode().replace('resume2','resume4')
for name,value in {'SOURCE_PIN':launcher_pin,'MONITOR_PIN':monitor_pin,'PREFLIGHT_PIN':preflight_pin}.items():
    node=next(n for n in ast.parse(new_builder).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets))
    new_builder=new_builder.replace(ast.get_source_segment(new_builder,node),name+' = '+repr(value),1)
write('build_execution_command.py',new_builder)
observer_draft=(OUT/'observe_inspection_UNRELEASED.py').read_bytes()
assert len(observer_draft)==10851 and sha(observer_draft)=='6a1798ee1fe556383b7177aec019a1854592f1396a8a7b3ca08b13b5cc809fff'
observer=observer_draft.decode().replace('PREFLIGHT_PIN = None','PREFLIGHT_PIN = '+repr(preflight_pin))
a,b=ast.parse(observer_draft),ast.parse(observer)
for tree in (a,b):
    tree.body=[n for n in tree.body if not(isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PREFLIGHT_PIN' for t in n.targets))]
assert ast.dump(a)==ast.dump(b)
observer_body=write('observe_inspection.py',observer)
paged=observer.replace('def pins(m):','def pins(m, page=None):')
paged=paged.replace("          'inspection_result_sha256': accepted_sha}, separators=(',', ':')), flush=True)\n    for index, row in enumerate(rows):", "          'inspection_result_sha256': accepted_sha, 'page': page, 'pages': 3}, separators=(',', ':')), flush=True)\n    selected = rows if page is None else rows[page * 5:(page + 1) * 5]\n    for index, row in enumerate(selected, start=0 if page is None else page * 5):")
paged=paged.replace("    parser.add_argument('--pins', action='store_true')\n    args = parser.parse_args()", "    parser.add_argument('--pins', action='store_true')\n    parser.add_argument('--page', type=int, choices=range(3))\n    args = parser.parse_args()\n    if args.page is not None and not args.pins:\n        parser.error('--page requires --pins')")
paged=paged.replace('    pins(owner) if args.pins else status(owner)','    pins(owner, args.page) if args.pins else status(owner)')
paged_body=write('observe_inspection_paged.py',paged)
reader_commands=[]
for name,payload,args in [('observe-inspection.command.txt',observer_body,[]), *[('observe-success-pins-'+str(page)+'.command.txt',paged_body,['--pins','--page',str(page)]) for page in range(3)]]:
    encoded=base64.b64encode(gzip.compress(payload,mtime=0)).decode()
    loader='import base64,gzip,hashlib; b=gzip.decompress(base64.b64decode('+repr(encoded)+',validate=True)); assert len(b)=='+str(len(payload))+' and hashlib.sha256(b).hexdigest()=='+repr(sha(payload))+'; exec(compile(b,"resume4-inspection-observer","exec"),{"__name__":"__main__"})'
    cmd=shlex.join(['/data/data/com.termux/files/usr/bin/python','-I','-B','-c',loader,*args])+'\n'
    assert len(cmd.encode())<=6000
    write(name,cmd)
    reader_commands.append({'path':name,'bytes':len(cmd.encode()),'sha256':sha(cmd.encode())})
record={'schema':1,'state':'FINALIZED_EXECUTION_SOURCE_AND_READERS_PENDING_INDEPENDENT_RELEASE',
 'actual_preflight_observation':{'path':str(observed_path),'bytes':len(observed_body),'sha256':sha(observed_body)},
 'actual_preflight':{'path':preflight['path'],**preflight_pin},'monitor_source':monitor_pin,'actual_monitor_ready':None,
 'execution_launcher':launcher_pin,'execution_transfer':transfer_record,
 'ready_command_builder':{'bytes':len(new_builder.encode()),'sha256':sha(new_builder.encode())},
 'status_observer':{'bytes':len(observer_body),'sha256':sha(observer_body)},
 'paged_success_observer':{'bytes':len(paged_body),'sha256':sha(paged_body)},'reader_commands':reader_commands,
 'phone_execution_performed':False,'inspection_success_claimed':False}
write('execution-binding-finalization.json',json.dumps(record,indent=2)+'\n')
print(json.dumps({k:record[k] for k in ('state','actual_preflight','monitor_source','execution_launcher','ready_command_builder','status_observer','paged_success_observer','reader_commands')},indent=2))
