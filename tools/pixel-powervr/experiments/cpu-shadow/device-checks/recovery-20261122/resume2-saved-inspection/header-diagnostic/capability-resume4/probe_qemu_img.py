#!/usr/bin/env python3
"""Bounded diagnostic-only HFS headers through the exact frozen native qemu-img.

No guest VM, mount, replay, repair, fsck or inspection-acceptance change.
Only fresh synthetic/evidence files are written. No existing disk image is opened.
"""
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import stat
import struct
import subprocess
import time
import types

BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
OWNER_SOURCE = BASE / 'run-ios26-saved-inspection-resume2.py'
OWNER_SOURCE_PIN = {'bytes': 35799, 'sha256': '445f16736ff3f0c4aca2f9d825f4b71b9264bc24b177fe3a8281ca9c6e0f1e0b'}
DIAGNOSTIC_SOURCE = BASE / 'run-ios26-hfs-header-diagnostic-resume2.py'
OUT = BASE / 'ios26-hfs-header-capability-resume4'
TOOL_PIN = {'bytes': 2356032, 'sha256': '1bd2fd6b968c492d0263436c260af2a8c2ee807cf4afd4fd2abb3300446e2440'}
TOOL_MANIFEST_SHA = 'a5461ecf2e41d4966f783dfca620d3d700f9aa1bc76dd5fa745ec54666e764b2'
PREFLIGHT_PIN = {'bytes': 9070, 'sha256': '84b31f4f08744f6adeb20ab5af308b1d10c839803c051d4bba577201a4ad3760'}
PARTITIONS = ((2048, 67108864, 'iOSRoot'), (67110912, 33554432, 'Data'))
LIMITS = {'tool_seconds': 15, 'cleanup_seconds': 5, 'tool_cpu_seconds': 10,
          'min_available_mib': 2816, 'min_free_mib': 1536, 'tool_output_bytes': 64 << 10,
          'headers': 8, 'header_bytes': 512, 'result_bytes': 64 << 10}


def require(ok, message):
    if not ok:
        raise ValueError(message)

def sha(body):
    return hashlib.sha256(body).hexdigest()

def small_read(path, limit=4 << 20):
    require(path.resolve(strict=True) == path, 'noncanonical input')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        a = os.fstat(stream.fileno())
        require(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and a.st_size <= limit, 'nonordinary or oversized input')
        body = stream.read(limit + 1)
        b = os.fstat(stream.fileno())
    require(len(body) == a.st_size <= limit and
            (a.st_dev, a.st_ino, a.st_size, a.st_mtime_ns, a.st_ctime_ns) ==
            (b.st_dev, b.st_ino, b.st_size, b.st_mtime_ns, b.st_ctime_ns), 'input changed during read')
    return body

def save(name, body):
    require('/' not in name and name not in ('', '.', '..'), 'invalid own evidence name')
    require(len(body) <= LIMITS['result_bytes'], 'own evidence bound exceeded')
    with os.fdopen(os.open(OUT / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(OUT, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

def save_json(name, value):
    save(name, (json.dumps(value, sort_keys=True, indent=2) + '\n').encode())

def module(body, path, name):
    value = types.ModuleType(name)
    value.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), value.__dict__)
    return value

def run_tool(label, command, env, tool_rows):
    require(label.isalnum() and len(label) <= 24, 'invalid own tool label')
    parent = os.getpid()
    def child_limits():
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0 or os.getppid() != parent:
            os._exit(125)
        resource.setrlimit(resource.RLIMIT_CPU, (LIMITS['tool_cpu_seconds'], LIMITS['tool_cpu_seconds']))
        resource.setrlimit(resource.RLIMIT_FSIZE, (LIMITS['tool_output_bytes'], LIMITS['tool_output_bytes']))
        resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    row = {'label': label, 'command': command, 'pid': None, 'exit_code': None, 'reaped': False, 'forced': False}
    save_json(label + '.command.json', row)
    child = None
    try:
        with os.fdopen(os.open(OUT / (label + '.stdout'), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
            child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
                                     env=env, close_fds=True, start_new_session=True, preexec_fn=child_limits)
            row['pid'] = child.pid
            try:
                row['exit_code'] = child.wait(timeout=LIMITS['tool_seconds'])
            except subprocess.TimeoutExpired:
                row['forced'] = True
                child.kill()  # This exact unreaped child only; never a target inspection process.
                row['exit_code'] = child.wait(timeout=LIMITS['cleanup_seconds'])
            row['reaped'] = True
            stream.flush()
            os.fsync(stream.fileno())
        output = small_read(OUT / (label + '.stdout'), LIMITS['tool_output_bytes'])
        row.update(output_bytes=len(output), output_sha256=sha(output))
        require(row['exit_code'] == 0 and not row['forced'], 'owned qemu-img command did not finish cleanly: ' + label)
        return output
    finally:
        cleanup_error = None
        try:
            if child is not None and child.poll() is None:
                row['forced'] = True
                child.kill()
                row['exit_code'] = child.wait(timeout=LIMITS['cleanup_seconds'])
                row['reaped'] = True
        except BaseException as error:
            cleanup_error = type(error).__name__ + ': ' + str(error)
            row['reaped'] = False
            row['cleanup_error'] = cleanup_error
        finally:
            tool_rows.append(row)
            save_json(label + '.exit.json', row)
        if cleanup_error is not None:
            raise RuntimeError('owned child cleanup incomplete: ' + cleanup_error)

def main():
    require(os.geteuid() == 0 and BASE.resolve(strict=True) == BASE, 'root canonical base required')
    require(not os.path.lexists(OUT), 'preserve existing capability evidence')
    source = small_read(OWNER_SOURCE, OWNER_SOURCE_PIN['bytes'])
    require({'bytes':len(source),'sha256':sha(source)} == OWNER_SOURCE_PIN, 'reviewed owner source differs')
    m = module(source, OWNER_SOURCE, 'verified_inspection_owner')
    current = m.read_json(m.OWNER / 'prerequisites.json')
    for path, pin in m.SOURCE_HASHES.items():
        require(sha(small_read(path)) == pin, 'frozen source differs')
    session_body = small_read(m.PREP / 'session.json')
    require(sha(session_body) == current['inputs'][str(m.PREP / 'session.json')], 'actual bound session changed')
    session = json.loads(session_body)
    require(m.digest(session) == m.SESSION_DIGEST and session['tooling_manifest_sha256'] == TOOL_MANIFEST_SHA,
            'actual tooling session differs')
    guard = module(small_read(m.GUARD_SOURCE), m.GUARD_SOURCE, 'verified_guard')
    prep = guard.load_frozen(m.RUNNER, session['runner_sources'])
    tooling = m.canonical(Path(session['tooling']))
    manifest = prep.verify_tools(tooling, TOOL_MANIFEST_SHA)
    require({k:manifest['files']['tools/qemu-img'][k] for k in ('bytes','sha256')} == TOOL_PIN, 'frozen qemu-img differs')
    tool = tooling / 'tools/qemu-img'
    m.resources()
    OUT.mkdir(mode=0o700)
    result = {'schema':1,'kind':'native_qemu_img_read_capability_probe','status':'INCOMPLETE',
              'source_sha256':globals().get('__loader_source_sha256__'), 'started_utc':m.utc(),
              'owner':m.identity(os.getpid()),'tool':{'path':str(tool),**TOOL_PIN},
              'tooling_manifest_sha256':TOOL_MANIFEST_SHA,'tool_commands':[], 'error':None,
              'existing_disk_images_opened':False,'guest_vm_started':False,'diagnostic_only':True,'limits':LIMITS}
    try:
        save_json('session.json', result)
        env={'PATH':'/system/bin','LD_LIBRARY_PATH':str(tooling/'lib'),'TMPDIR':str(OUT),'LANG':'C','LC_ALL':'C'}
        help_body=run_tool('help',[str(tool),'dd','--help'],env,result['tool_commands'])
        help_text=help_body.decode('utf-8')
        sample=b''.join(bytes([17*(index+1)])*512 for index in range(4))
        save('sample.input',sample)
        command=[str(tool),'dd','-f','raw','-O','raw','bs=512','count=3','skip=2',
                 'if='+str(OUT/'sample.input'),'of='+str(OUT/'sample.output')]
        run_tool('sample',command,env,result['tool_commands'])
        output=small_read(OUT/'sample.output',512)
        require(output==sample[1024:1536] and small_read(OUT/'sample.input',2048)==sample,
                'dd skip/count/output bound or synthetic input preservation failed')
        result.update(status='QEMU_IMG_READ_CAPABILITY_PASSED',dd_help_line=next((line.strip()[:400] for line in help_text.splitlines() if line.strip()),''),help_sha256=sha(help_body),
                      synthetic_input_bytes=2048,skip_blocks=2,count_blocks=3,count_semantics='input_limit_before_skip',block_bytes=512,output_bytes=len(output),
                      expected_output_sha256=sha(sample[1024:1536]),actual_output_sha256=sha(output),
                      expected_bytes_match=True,input_unchanged=True)
    except BaseException as error:
        result['error']=type(error).__name__+': '+str(error)
    finally:
        try:
            prep.verify_tools(tooling,TOOL_MANIFEST_SHA)
            require(sha(small_read(m.PREP/'session.json'))==sha(session_body),'bound session changed')
            result['bound_tooling_and_session_unchanged']=True
        except BaseException as error:
            result['status']='INCOMPLETE'
            result['preservation_error']=type(error).__name__+': '+str(error)
        result['finished_utc']=m.utc()
        save_json('result.json',result)
    body=small_read(OUT/'result.json',LIMITS['result_bytes'])
    print(json.dumps({'schema':1,'status':result['status'],'observed_utc':m.utc(),'diagnostic_only':True,
          'result':{'path':str(OUT/'result.json'),'bytes':len(body),'sha256':sha(body),'digest_bytes':list(hashlib.sha256(body).digest())},
          'tool':result['tool'],'dd_help_line':result.get('dd_help_line'),'synthetic_input_bytes':result.get('synthetic_input_bytes'),
          'skip_blocks':result.get('skip_blocks'),'count_blocks':result.get('count_blocks'),'count_semantics':result.get('count_semantics'),'output_bytes':result.get('output_bytes'),
          'expected_bytes_match':result.get('expected_bytes_match'),'input_unchanged':result.get('input_unchanged'),
          'owned_tool_children_reaped':all(row['reaped'] for row in result['tool_commands']),
          'forced_tool_children':[row['pid'] for row in result['tool_commands'] if row['forced']],
          'bound_tooling_and_session_unchanged':result.get('bound_tooling_and_session_unchanged'),
          'existing_disk_images_opened':False,'guest_vm_started':False,'error':result.get('error'),
          'preservation_error':result.get('preservation_error')},separators=(',',':')),flush=True)
    return 0 if result['status']=='QEMU_IMG_READ_CAPABILITY_PASSED' else 2


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'schema':1,'status':'CAPABILITY_PROBE_REFUSED','error':type(error).__name__+': '+str(error),
              'existing_disk_images_opened':False,'diagnostic_only':True},separators=(',',':')),flush=True)
        raise SystemExit(2)
