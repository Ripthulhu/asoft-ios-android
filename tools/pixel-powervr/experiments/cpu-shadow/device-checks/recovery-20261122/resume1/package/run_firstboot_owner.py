#!/usr/bin/env python3
"""One-shot retry owner for the counter1 guard through the reviewed local memfd adapter."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import types

BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
OWNER = BASE / 'ios26-firstboot-owner-resume1'
PREFLIGHT = BASE / 'ios26-firstboot-guard-preflight-resume1'
PREP = Path('/data/local/tmp/pixel-prep-e9cc754')
RUNNER = Path('/data/local/tmp/pixel-prep-runner-f4d64db')
AUDIT = Path('/data/local/tmp/pixel-audit-e9cc754')
AUDITOR = Path('/data/local/tmp/pixel-boot-checks-ebbc9c0/auditor')
GUARD = Path('/data/local/tmp/pixel-boot-checks-counter1/firstboot/guard_ios26_firstboot.py')
WORK = Path('/data/local/tmp/pixel-firstboot-guard-e9cc754-resume1')
PYTHON = '/data/data/com.termux/files/usr/bin/python'
ADAPTER = BASE / 'run-ios26-firstboot-memfd-adapter-resume1.py'
ADAPTER_SHA = 'ede70023bc1e05b08730b48fab1016c3e665c0e83469509e5b8b74c6f2364ec7'
SMOKE = BASE / 'python-memfd-smoke-memfd1.json'
SMOKE_SHA = '57d7239160422a858ed9882191c5012fd20a20d5b790f482be15013266f313bd'
FAILED_WORK = Path('/data/local/tmp/pixel-firstboot-guard-e9cc754')
FAILED_OWNER = BASE / 'ios26-firstboot-owner-ebbc9c0'
FAILED_RESULT_SHA = '2a4b1ad20f478db58eb5ca7219789146b973f364cf4e7f079eb6acd4f5e7519d'
FAILED_EXIT_SHA = 'c651a9fae9976e04eada79bc229604a9724ea4053723d6b05ee6c0df02ce28b1'
PREFLIGHT_COMMAND = [PYTHON, '-I', '-B', str(ADAPTER)]
COMMAND = PREFLIGHT_COMMAND + ['--execute']
GUARD_ARGV = [str(GUARD), '--audit-work', str(AUDIT), '--auditor-dir', str(AUDITOR),
              '--runner-dir', str(RUNNER), '--work', str(WORK)]
GUARD_SHA = 'ea40638312d6ac41607806ecb03c148fbd0677df6ab01480e13fd40536869674'
PREFLIGHT_SHA = '42a0fefd327fd8be51eebb9be6fac4def61a18f5cf8bb274af23d6c093cbe222'
PREFLIGHT_BYTES = 21988  # Physically observed fresh resume1 read-only preflight.
AUDIT_SHA = '542dcf281cbcfb0016d74eda8dbb7a84db799e390e857321f519de4e0f1a7146'
SESSION_DIGEST = '9ce5f5b8e4953ac54fddd854c5b4a606c2b9866814af6b1d520c2b590e987a6b'
OWNER_SECONDS, TERM_SECONDS, KILL_SECONDS = 5400, 180, 30

STAGED = {'/data/local/tmp/pixel-boot-checks-counter1/firstboot/guard_ios26_firstboot.py': {'bytes': 25686, 'sha256': 'ea40638312d6ac41607806ecb03c148fbd0677df6ab01480e13fd40536869674'}, '/data/local/tmp/pixel-saved-checks-counter1/inspect_ios26_firstboot.py': {'bytes': 26030, 'sha256': '2b127ecda390b199287358cdad7e6e7774f5b787148aea524e7b0247a2640cf3'}, '/data/local/tmp/pixel-saved-checks-counter1/inspect_ios26_firstboot_guest.py': {'bytes': 16829, 'sha256': 'ada26de8ababb11bb4af20e558708545eb64fd516481359fd5d0ccf6a7cbae2b'}}
CHECKS_INSTALL = BASE / 'counter1-guard-inspector-install.json'
FAILED2_PINS = {'owner_exit': {'path': '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-firstboot-owner-memfd1/exit.json', 'bytes': 805, 'sha256': '701461a97e794ae669cadda23cbb8a475adb974556d0c4e5cf6c552876a629f5'}, 'guard_result': {'path': '/data/local/tmp/pixel-firstboot-guard-e9cc754-memfd1/result.json', 'bytes': 24006, 'sha256': 'f618a29bc550d6155e78ed3757e3ce715b6c75b1fcf1745c6d6b55944b6a345a'}, 'guard_observations': {'path': '/data/local/tmp/pixel-firstboot-guard-e9cc754-memfd1/guard-observations.json', 'bytes': 8098, 'sha256': '75bcf49437cba79303d019dbd3cdedba63cf269b93cdc5ba9384d47773923a9a'}, 'adapter_owner': {'path': '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-firstboot-memfd1-adapter-execute.owner.json', 'bytes': 1869, 'sha256': 'eed7eaa19246e6bf0ce52839de8040394521111fe1bf60acc67c90a967b1f73c'}, 'adapter_exit': {'path': '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-firstboot-memfd1-adapter-execute.exit.json', 'bytes': 2048, 'sha256': 'fa0a41b1a50e4b9d675b458f7e1cf10af857f8dc41ff74d9e9a46b00008c494b'}, 'attempt_launch': {'path': '/data/local/tmp/pixel-prep-e9cc754/attempts/07-0002/launch.json', 'bytes': 3048, 'sha256': '1137b883bf9472361d9dd80eaed7514de5d4b5a2029230d37531c740719814e7'}, 'attempt_vm_result': {'path': '/data/local/tmp/pixel-prep-e9cc754/attempts/07-0002/vm-result.json', 'bytes': 10131, 'sha256': '6858d9d196127206b79c604321358cc48f61e2405fc4405791510ed70d211428'}}


def require(condition, message):
    if not condition: raise ValueError(message)


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def canonical(path):
    require(path.is_absolute() and path.resolve(strict=True) == path, 'noncanonical path: ' + str(path))
    return path


def read(path, limit=4 << 20):
    canonical(path)
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= limit, 'nonordinary/oversized metadata')
        body = stream.read(limit + 1)
    require(len(body) <= limit, 'metadata grew beyond bound')
    return body


def record(path):
    return json.loads(read(path))


def create(name, value):
    canonical(OWNER)
    with os.fdopen(os.open(OWNER / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as stream:
        json.dump(value, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    fd = os.open(OWNER, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def identity(pid):
    require(type(pid) is int and pid > 0, 'invalid PID')
    try:
        with Path('/proc/{}/stat'.format(pid)).open('rb') as stream: body = stream.read(4097)
    except FileNotFoundError:
        return None
    require(len(body) <= 4096, 'oversized process stat')
    return {'pid': pid, 'starttime': int(body[body.rfind(b')') + 2:].split()[19])}


def absent(value, key='starttime'):
    require(type(value) is dict and set(value) == {'pid', key} and type(value[key]) is int, 'invalid recorded process identity')
    require(identity(value['pid']) != {'pid': value['pid'], 'starttime': value[key]}, 'recorded process still present: ' + str(value['pid']))


def resources():
    with Path('/proc/meminfo').open('rb') as stream: body = stream.read(65537)
    require(len(body) <= 65536, 'oversized meminfo')
    match = re.search(rb'^MemAvailable:\s+(\d+) kB$', body, re.M)
    require(match is not None, 'MemAvailable unavailable')
    memory = int(match[1]) * 1024
    disk = os.statvfs(PREP); free = disk.f_bavail * disk.f_frsize
    require(memory >= 3840 << 20, 'firstboot needs 3840 MiB MemAvailable; observed ' + str(memory))
    require(free >= 4500000000, 'firstboot needs 4500000000 free bytes; observed ' + str(free))
    return {'at_utc': utc(), 'mem_available_bytes': memory, 'free_bytes': free,
            'memory_floor_bytes': 3840 << 20, 'space_floor_bytes': 4500000000}


def _prior_failures12():
    exited_body = read(FAILED_OWNER / 'exit.json'); result_body = read(FAILED_WORK / 'result.json')
    if hashlib.sha256(exited_body).hexdigest() != FAILED_EXIT_SHA or hashlib.sha256(result_body).hexdigest() != FAILED_RESULT_SHA:
        raise ValueError('preserved failed firstboot evidence differs')
    exited = json.loads(exited_body); result = json.loads(result_body); startup = json.loads(read(FAILED_OWNER / 'owner.json'))
    if (exited.get('exit_code') != 2 or exited.get('owner_exit_code') != 2 or exited.get('accepted') is not False or
            exited.get('guard_reaped') is not True or exited.get('forced_guard') is not False or exited.get('cleanup_errors') != [] or
            any(exited.get(k) != startup.get(k) for k in ('command', 'wrapper', 'guard', 'started_utc')) or
            result.get('status') != 'INCOMPLETE' or result.get('bound_inputs_unchanged') is not True or
            result.get('original_firstboot_checkpoint_present') is not False or
            result.get('actual_attempt', {}).get('attempt') != '/data/local/tmp/pixel-prep-e9cc754/attempts/07-0001' or
            set(result.get('actual_attempt', {}).get('files', {})) != {'stage-inputs.json'}):
        raise ValueError('prior failure is not the clean pre-VM memfd failure')
    stage = read(Path('/data/local/tmp/pixel-prep-e9cc754/attempts/07-0001/stage-inputs.json'))
    expected = result['actual_attempt']['files']['stage-inputs.json']
    if len(stage) != expected['bytes'] or hashlib.sha256(stage).hexdigest() != expected['sha256']:
        raise ValueError('preserved failed-attempt stage inputs changed')
    for key in ('wrapper', 'guard'):
        value = startup[key]
        if identity(value['pid']) == value: raise ValueError('prior firstboot owner or guard still present')
    for name in ('launch.json', 'vm-result.json', 'vm.child.json'):
        if os.path.lexists(Path('/data/local/tmp/pixel-prep-e9cc754/attempts/07-0001') / name):
            raise ValueError('prior failed attempt has unexpected VM metadata')
    first = {'guard_result_sha256': FAILED_RESULT_SHA, 'owner_exit_sha256': FAILED_EXIT_SHA, 'attempt': '07-0001'}
    second = {}; hashes = {}
    for label, pinned in FAILED2_PINS.items():
        raw = read(Path(pinned['path']))
        if len(raw) != pinned['bytes'] or hashlib.sha256(raw).hexdigest() != pinned['sha256']:
            raise ValueError('preserved counter-rejected receipt changed: ' + label)
        second[label] = json.loads(raw); hashes[label] = pinned['sha256']
    old_adapter = BASE / 'run-ios26-firstboot-memfd-adapter-memfd1.py'
    old_guard = Path('/data/local/tmp/pixel-boot-checks-ebbc9c0/firstboot/guard_ios26_firstboot.py')
    old_work = Path('/data/local/tmp/pixel-firstboot-guard-e9cc754-memfd1')
    old_owner = BASE / 'ios26-firstboot-owner-memfd1'
    old_sources = {old_adapter: 'e981d6d561b821641a6993b2aa96b84fa63776ccd1a7bc8cb314d1261ae899a8',
                   old_guard: '8f98fafd603385b5d3aa20331acc7e536020b6ae136f8690bd190efbeb09845c',
                   BASE / 'run-ios26-firstboot-owner-memfd1.py': '771742c200d2d64c54cdd18db7bcd1cba4fc242999f16376531e0d9803f9a3d5'}
    if any(hashlib.sha256(read(path)).hexdigest() != pin for path, pin in old_sources.items()):
        raise ValueError('preserved memfd1 execution source changed')
    old_command = ['/data/data/com.termux/files/usr/bin/python', '-I', '-B', str(old_adapter), '--execute']
    old_guard_argv = [str(old_guard), '--audit-work', str(AUDIT), '--auditor-dir', '/data/local/tmp/pixel-boot-checks-ebbc9c0/auditor',
                      '--runner-dir', '/data/local/tmp/pixel-prep-runner-f4d64db', '--work', str(old_work), '--execute']
    exited, result = second['owner_exit'], second['guard_result']
    startup = json.loads(read(old_owner / 'owner.json'))
    if (exited.get('exit_code') != 2 or exited.get('owner_exit_code') != 2 or exited.get('accepted') is not False or
            exited.get('guard_started') is not True or exited.get('guard_reaped') is not True or exited.get('forced_guard') is not False or
            exited.get('cleanup_errors') != [] or exited.get('wrapper_error') != 'ValueError: guard exited 2' or
            startup.get('command') != old_command or json.loads(read(old_owner / 'command.json')) != old_command or
            any(exited.get(k) != startup.get(k) for k in ('command', 'wrapper', 'guard', 'started_utc'))):
        raise ValueError('counter-rejected outer owner was not cleanly reaped with exit2')
    astart, aexit = second['adapter_owner'], second['adapter_exit']
    if (any(aexit.get(k) != v for k, v in astart.items()) or astart.get('phase') != 'execute' or
            astart.get('process') != startup.get('guard') or astart.get('command') != old_command or astart.get('guard_argv') != old_guard_argv or
            astart.get('adapter_source_sha256') != old_sources[old_adapter] or astart.get('guard_source_sha256') != old_sources[old_guard] or
            astart.get('accepted_libc_smoke', {}).get('receipt_sha256') != SMOKE_SHA or
            aexit.get('exit_code') != 2 or aexit.get('error') is not None or aexit.get('adapter_completed') is not False or
            aexit.get('attributes_restored') is not True or aexit.get('sources_unchanged') is not True):
        raise ValueError('counter-rejected adapter provenance or restoration differs')
    actual = result.get('actual_attempt', {}); attempt = Path('/data/local/tmp/pixel-prep-e9cc754/attempts/07-0002')
    if (result.get('schema') != 1 or result.get('status') != 'INCOMPLETE' or result.get('bound_inputs_unchanged') is not True or
            result.get('checkpoint_accepted_by_guard') is not False or result.get('original_firstboot_checkpoint_present') is not False or
            actual.get('attempt') != str(attempt) or set(actual.get('files', {})) != {'stage-inputs.json', 'launch.json', 'vm-result.json'} or
            os.path.lexists(attempt / 'stage-result.json')):
        raise ValueError('counter-rejected attempt boundary changed')
    for name, expected in actual['files'].items():
        raw = read(attempt / name)
        if len(raw) != expected['bytes'] or hashlib.sha256(raw).hexdigest() != expected['sha256']:
            raise ValueError('preserved counter-rejected attempt metadata changed')
    if actual.get('launch.json') != second['attempt_launch'] or actual.get('vm-result.json') != second['attempt_vm_result']:
        raise ValueError('preserved counter-rejected embedded metadata differs')
    if second['guard_observations'] != {'schema': 1, 'post_stop_blockstats': result.get('post_stop_blockstats'), 'supervision': result.get('supervision')}:
        raise ValueError('counter-rejected observations changed')
    events = result.get('post_stop_blockstats', [])
    if (len(events) != 1 or events[0].get('status') != 'INCOMPLETE' or events[0].get('stop_acknowledged') is not True or
            events[0].get('failed_io_counters_zero') is not False or
            events[0].get('error') != 'ValueError: post-stop stats must identify exactly the root backend' or 'post_stop_blocks' in events[0]):
        raise ValueError('counter-rejected event was changed or retroactively completed')
    vm = second['attempt_vm_result']; cleanup = vm.get('cleanup', {}); witness = vm.get('witnesses', {})
    if (vm.get('status') != 'INCOMPLETE' or vm.get('stage') != 'ios26-firstboot' or
            any(vm.get(k) is not True for k in ('milestone', 'settled', 'guest_sync_answered')) or
            any(witness.get(k) is not True for k in ('native_initialization', 'native_execution', 'native_svc_final')) or
            cleanup.get('exit_code') != 0 or cleanup.get('echild') is not True or cleanup.get('quit_acknowledged') is not True or
            cleanup.get('stop_flushed') is not False or cleanup.get('forced_qemu') is not False or cleanup.get('forced_descendants') != [] or
            type(cleanup.get('errors')) is not list or not cleanup['errors']):
        raise ValueError('counter-rejected VM must retain its stop-hook failure and owned QEMU reap')
    expected_ids = {'wrapper': {'pid': 897, 'starttime': 7531924}, 'guard': {'pid': 899, 'starttime': 7531951}}
    for key, value in expected_ids.items():
        if startup.get(key) != value or identity(value['pid']) == value: raise ValueError('preserved memfd1 owner identity differs or is live')
    child = json.loads(read(attempt / 'vm.child.json'))
    if child != {'pid': 2037, 'start_ticks': 7545319} or identity(2037) == {'pid': 2037, 'starttime': 7545319}:
        raise ValueError('preserved counter-rejected QEMU identity differs or is live')
    return {'07-0001': first, '07-0002': {'attempt': '07-0002', 'pinned_receipt_sha256': hashes,
            'stage_inputs_sha256': actual['files']['stage-inputs.json']['sha256'], 'status': 'INCOMPLETE', 'checkpoint_accepted': False}}



# All eight pins come from the selected, independently decoded recovery record.
# They bind raw phone files; projected cleanup defaults are not asserted as raw fields.
FAILED3_PINS = {'owner_exit': {'path': '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-firstboot-owner-counter1/exit.json', 'bytes': 811, 'sha256': '9926bd3afd65f392ca5d8fcaa4ec67f99428f7dc00dc89d863bed82ebf25faba'}, 'guard_result': {'path': '/data/local/tmp/pixel-firstboot-guard-e9cc754-counter1/result.json', 'bytes': 2693, 'sha256': 'b93625243595ce587120da7bddeff89d208515b49877d161605ee6957249cf7b'}, 'guard_observations': {'path': '/data/local/tmp/pixel-firstboot-guard-e9cc754-counter1/guard-observations.json', 'bytes': 458, 'sha256': '2f0674be9937441f84ebd0dc3077344bc4789db463ecc42dc3d709fddc259442'}, 'adapter_owner': {'path': '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-firstboot-counter1-adapter-execute.owner.json', 'bytes': 1876, 'sha256': '11a5691b70366201d374e341f16668a0d0b41a4cac37c2a3bfaa2d4c64fefd37'}, 'adapter_exit': {'path': '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-firstboot-counter1-adapter-execute.exit.json', 'bytes': 2055, 'sha256': 'd83951e8edc29c2eac4c1b6b8e5f2c3176f6c75a7e2659b008afdeade88af4b3'}, 'guard_session': {'path': '/data/local/tmp/pixel-firstboot-guard-e9cc754-counter1/guard-session.json', 'bytes': 20936, 'sha256': 'dbb13619f92e0349036a71088511db4eeb978aaae6a22428976761ef54b2873e'}, 'stage_inputs': {'path': '/data/local/tmp/pixel-prep-e9cc754/attempts/07-0003/stage-inputs.json', 'bytes': 16143, 'sha256': '1cc3ce6992bf97a756f59c0d2f9b6c3e87e6f5f18376b9ba385d1345f55f8312'}, 'vm_result': {'path': '/data/local/tmp/pixel-prep-e9cc754/attempts/07-0003/vm-result.json', 'bytes': 1052, 'sha256': 'dc618e42ed91d42f3b93bc9be337f4732dee7caec7b58fa2fd2be81d1acc4084'}}


def prior_failures():
    preserved = _prior_failures12()
    third = {}; hashes = {}
    for label, pin in FAILED3_PINS.items():
        body = read(Path(pin['path']))
        if len(body) != pin['bytes'] or hashlib.sha256(body).hexdigest() != pin['sha256']:
            raise ValueError('preserved memory-refused receipt changed: ' + label)
        third[label] = json.loads(body); hashes[label] = pin['sha256']
    old_owner = BASE / 'ios26-firstboot-owner-counter1'
    old_adapter = BASE / 'run-ios26-firstboot-memfd-adapter-counter1.py'
    old_source = BASE / 'run-ios26-firstboot-owner-counter1-pin1.py'
    old_work = Path('/data/local/tmp/pixel-firstboot-guard-e9cc754-counter1')
    old_command = ['/data/data/com.termux/files/usr/bin/python', '-I', '-B', str(old_adapter), '--execute']
    old_argv = [str(GUARD), '--audit-work', str(AUDIT), '--auditor-dir', '/data/local/tmp/pixel-boot-checks-ebbc9c0/auditor',
                '--runner-dir', '/data/local/tmp/pixel-prep-runner-f4d64db', '--work', str(old_work), '--execute']
    if (hashlib.sha256(read(old_adapter)).hexdigest() != '1402321c22ae98b0ba7094f9e121cb169f2bf4aea38d0272b957f08a26259725' or
            hashlib.sha256(read(old_source)).hexdigest() != 'b7337a992b5c9c651aae1085c358a27c5d2c8b41998398afd5a4f5ba40c6e2e7'):
        raise ValueError('preserved counter1 execution source changed')
    startup = json.loads(read(old_owner / 'owner.json')); exited = third['owner_exit']
    if (exited.get('exit_code') != 2 or exited.get('owner_exit_code') != 2 or exited.get('accepted') is not False or
            exited.get('guard_started') is not True or exited.get('guard_reaped') is not True or exited.get('forced_guard') is not False or
            exited.get('cleanup_errors') != [] or startup.get('command') != old_command or
            json.loads(read(old_owner / 'command.json')) != old_command or
            any(exited.get(k) != startup.get(k) for k in ('command', 'wrapper', 'guard', 'started_utc'))):
        raise ValueError('memory-refused outer owner changed or was not cleanly reaped')
    expected_ids = {'wrapper': {'pid': 28120, 'starttime': 7858275}, 'guard': {'pid': 28121, 'starttime': 7858299}}
    for key, value in expected_ids.items():
        if startup.get(key) != value or identity(value['pid']) == value:
            raise ValueError('memory-refused owner identity differs or remains live')
    astart, aexit = third['adapter_owner'], third['adapter_exit']
    if (any(aexit.get(k) != v for k,v in astart.items()) or astart.get('phase') != 'execute' or
            astart.get('process') != expected_ids['guard'] or astart.get('command') != old_command or astart.get('guard_argv') != old_argv or
            astart.get('adapter_source_sha256') != '1402321c22ae98b0ba7094f9e121cb169f2bf4aea38d0272b957f08a26259725' or
            astart.get('guard_source_sha256') != GUARD_SHA or astart.get('accepted_libc_smoke',{}).get('receipt_sha256') != SMOKE_SHA or
            aexit.get('exit_code') != 2 or aexit.get('error') is not None or aexit.get('adapter_completed') is not False or
            aexit.get('attributes_restored') is not True or aexit.get('sources_unchanged') is not True):
        raise ValueError('memory-refused adapter provenance or restoration differs')
    result = third['guard_result']; actual = result.get('actual_attempt', {})
    attempt = Path('/data/local/tmp/pixel-prep-e9cc754/attempts/07-0003')
    if (result.get('schema') != 1 or result.get('status') != 'INCOMPLETE' or result.get('bound_inputs_unchanged') is not True or
            result.get('checkpoint_accepted_by_guard') is not False or result.get('original_firstboot_checkpoint_present') is not False or
            actual.get('attempt') != str(attempt) or set(actual.get('files', {})) != {'stage-inputs.json','vm-result.json'} or
            actual.get('vm-result.json') != third['vm_result']):
        raise ValueError('memory-refused attempt boundary changed')
    for name, pin in actual['files'].items():
        raw = read(attempt/name)
        if len(raw)!=pin['bytes'] or hashlib.sha256(raw).hexdigest()!=pin['sha256']:
            raise ValueError('memory-refused attempt metadata changed')
    for name in ('launch.json','vm.child.json','stage-result.json'):
        if os.path.lexists(attempt/name): raise ValueError('memory-refused attempt unexpectedly contains VM launch/success evidence')
    if third['guard_observations'] != {'schema':1,'post_stop_blockstats':result.get('post_stop_blockstats'),'supervision':result.get('supervision')}:
        raise ValueError('memory-refused guard observations differ')
    # No QEMU cleanup success or QEMU process identity is inferred from absent fields.
    vm = third['vm_result']
    if vm.get('status') != 'INCOMPLETE' or vm.get('stage') != 'ios26-firstboot':
        raise ValueError('memory-refused VM receipt changed')
    preserved['07-0003'] = {'attempt':'07-0003','pinned_receipt_sha256':hashes,
                          'status':'INCOMPLETE','checkpoint_accepted':False,'qemu_launched':False}
    return preserved


def checks_install():
    body = read(CHECKS_INSTALL); installed = json.loads(body)
    if (installed.get('schema') != 1 or installed.get('kind') != 'counter1_guard_and_saved_inspector_source_install' or
            installed.get('status') != 'VERIFIED' or installed.get('execution_started') is not False or installed.get('files') != STAGED):
        raise ValueError('counter1 checks source installation receipt differs')
    for path, expected in STAGED.items():
        raw = read(Path(path))
        if len(raw) != expected['bytes'] or hashlib.sha256(raw).hexdigest() != expected['sha256']:
            raise ValueError('counter1 staged source differs')
    return hashlib.sha256(body).hexdigest()



def adapter_evidence(phase, child_id):
    prefix = BASE / ('ios26-firstboot-resume1-adapter-' + phase)
    expected_command = PREFLIGHT_COMMAND if phase == 'preflight' else COMMAND
    expected_guard_argv = GUARD_ARGV + (['--execute'] if phase == 'execute' else [])
    owner_body, exit_body = (read(Path(str(prefix) + suffix)) for suffix in ('.owner.json', '.exit.json'))
    startup, exited = json.loads(owner_body), json.loads(exit_body)
    names = ['memfd_create', 'MFD_CLOEXEC', 'MFD_ALLOW_SEALING']
    if (any(exited.get(k) != v for k, v in startup.items()) or startup.get('schema') != 1 or
            startup.get('phase') != phase or startup.get('process') != child_id or startup.get('command') != expected_command or
            startup.get('guard_argv') != expected_guard_argv or startup.get('adapter_source_sha256') != ADAPTER_SHA or
            startup.get('guard_source_sha256') != GUARD_SHA or startup.get('missing_attributes') != names or
            startup.get('installed_attributes') != names or startup.get('constants') != {'MFD_CLOEXEC': 1, 'MFD_ALLOW_SEALING': 2} or
            startup.get('accepted_libc_smoke', {}).get('receipt_sha256') != SMOKE_SHA or
            startup.get('boot_execution_requested') is not (phase == 'execute') or exited.get('exit_code') != 0 or exited.get('error') is not None or
            exited.get('adapter_completed') is not True or exited.get('attributes_restored') is not True or exited.get('sources_unchanged') is not True):
        raise ValueError('adapter provenance or cleanup differs')
    return {'owner_sha256': hashlib.sha256(owner_body).hexdigest(), 'exit_sha256': hashlib.sha256(exit_body).hexdigest(),
            'adapter_source_sha256': ADAPTER_SHA, 'smoke_receipt_sha256': SMOKE_SHA,
            'installed_attributes': names, 'attributes_restored': True, 'adapter_completed': True}


def prerequisites():
    require(os.geteuid() == 0, 'root phone owner required')
    for directory in (BASE, PREP, RUNNER, AUDIT, AUDITOR, GUARD.parent, WORK.parent): canonical(directory)
    require(not os.path.lexists(WORK), 'guard work already exists; preserve it')
    require(sha(read(ADAPTER)) == ADAPTER_SHA and sha(read(SMOKE)) == SMOKE_SHA, 'adapter source or accepted smoke changed')
    preserved_failures = prior_failures(); checks_install_sha = checks_install()
    body = read(Path(str(PREFLIGHT) + '.stdout.json'))
    require(len(body) == PREFLIGHT_BYTES and sha(body) == PREFLIGHT_SHA, 'accepted preflight bytes differ')
    public = json.loads(body); session = public.get('guard_session', {})
    exited, startup, requested = (record(Path(str(PREFLIGHT) + suffix)) for suffix in ('.exit.json', '.owner.json', '.command.json'))
    require(exited.get('exit_code') == exited.get('owner_exit_code') == 0 and exited.get('accepted_readonly_preflight') is True and
            exited.get('preflight_reaped') is True and exited.get('forced_child') is False and exited.get('wrapper_error') is None and
            exited.get('cleanup_errors') == [] and exited.get('stdout_sha256') == PREFLIGHT_SHA and exited.get('stdout_bytes') == PREFLIGHT_BYTES and
            exited.get('boot_execution_requested') is False and exited.get('inputs_unchanged') is True and exited.get('guard_work_absent') is True and
            exited.get('finished_utc') and requested.get('command') == startup.get('command') == exited.get('command') == PREFLIGHT_COMMAND and
            requested.get('started_utc') == startup.get('started_utc') == exited.get('started_utc') and
            startup.get('preflight') == exited.get('preflight'), 'preflight ownership/exit receipt differs')
    absent(startup['wrapper']); absent(startup['preflight'])
    adapter = adapter_evidence('preflight', startup['preflight'])
    require(exited.get('adapter') == adapter and exited.get('adapter_source_sha256') == requested.get('adapter_source_sha256') == ADAPTER_SHA and
            exited.get('smoke_receipt_sha256') == requested.get('smoke_receipt_sha256') == SMOKE_SHA and
            exited.get('preserved_failures') == requested.get('preserved_failures') == preserved_failures and
            exited.get('checks_install_sha256') == requested.get('checks_install_sha256') == checks_install_sha, 'adapter-bound preflight capture differs')
    prior_root = BASE / 'ios26-partition-audit-ebbc9c0-owner'
    prior, prior_exit = record(prior_root / 'owner.json'), record(prior_root / 'exit.json')
    audit_command = [PYTHON, '-B', str(AUDITOR / 'audit_ios26_partition.py'), '--prep-work', str(PREP),
                     '--runner-dir', str(RUNNER), '--work', str(AUDIT), '--execute']
    require(prior.get('command') == prior_exit.get('command') == record(prior_root / 'command.json') == audit_command and
            prior.get('started_utc') == prior_exit.get('started_utc') and prior_exit.get('finished_utc') and
            prior_exit.get('exit_code') == prior_exit.get('owner_exit_code') == 0 and prior_exit.get('accepted') is True and
            prior_exit.get('runner_started') is True and prior_exit.get('runner_reaped') is True and prior_exit.get('forced_runner') is False and
            prior_exit.get('wrapper_error') is None and prior_exit.get('cleanup_errors') == [] and
            prior_exit.get('audit_result_sha256') == AUDIT_SHA and
            all(prior.get(k) == prior_exit.get(k) for k in ('wrapper', 'runner')), 'partition audit owner did not finish cleanly')
    absent(prior['wrapper']); absent(prior['runner']); absent(record(AUDIT / 'a1/vm.child.json'), 'start_ticks')
    require(public.get('schema') == 1 and public.get('status') == 'PREFLIGHT_READY' and
            session.get('kind') == 'ios26_firstboot_execution_guard' and session.get('guard_source') == str(GUARD) and
            session.get('guard_source_sha256') == GUARD_SHA and session.get('prep_work') == str(PREP) and session.get('runner_dir') == str(RUNNER) and
            all(public.get(k) is False for k in ('boot_complete', 'gpu_path_complete', 'app_gate_changed')), 'accepted preflight contract differs')
    guard_body = read(GUARD); require(sha(guard_body) == GUARD_SHA, 'staged guard source changed')
    guard = types.ModuleType('reviewed_firstboot_guard'); guard.__file__ = str(GUARD)
    exec(compile(guard_body, str(GUARD), 'exec'), guard.__dict__)  # Definitions only: __name__ is not __main__.
    prep = guard.load_frozen(RUNNER, session['frozen_sources'])
    require(sha(read(PREP / 'session.json')) == session['prep_session_sha256'] and
            prep.digest(record(PREP / 'session.json')) == SESSION_DIGEST, 'preparation session changed')
    audit = session['partition_audit']
    require(audit.get('work') == str(AUDIT) and audit.get('source_directory') == str(AUDITOR) and
            audit.get('audit_result_sha256') == AUDIT_SHA and sha(read(AUDIT / 'result.json')) == AUDIT_SHA, 'partition audit changed')
    for name, expected in audit['source_hashes'].items(): require(sha(read(AUDITOR / name)) == expected, 'auditor source changed')
    for path, expected in {**audit['files'], **audit['checkpoints']}.items(): require(sha(read(Path(path))) == expected, 'bound evidence changed: ' + path)
    expected_names = {Path(p).name for p in audit['checkpoints']}
    require(len(expected_names) == 7 and {p.name for p in (PREP / 'checkpoints').iterdir()} == expected_names,
            'exact seven-checkpoint partition boundary required')
    for value in session['frozen_input_identities'].values():
        require(prep.cold.readonly_identity(value['path']) == value, 'bound original input identity changed')
    fd = os.open(canonical(PREP / 'owner.lock'), os.O_RDONLY | os.O_NOFOLLOW)
    try:
        require(stat.S_ISREG(os.fstat(fd).st_mode), 'preparation lock is not ordinary')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB); prep.refuse_live_children(PREP)
    finally: os.close(fd)
    attempts = sorted(p.name for p in (PREP / 'attempts').iterdir() if re.fullmatch(r'07-\d{4}', p.name))
    require(attempts == ['07-0001', '07-0002', '07-0003'], 'expected exactly three preserved failed firstboot attempts')
    return {'guard': guard, 'prep': prep, 'session': session, 'attempts_before': attempts, 'resources': resources(),
            'adapter_preflight': adapter, 'preserved_failures': preserved_failures, 'checks_install_sha256': checks_install_sha}


def accepted_result(state):
    adapter = adapter_evidence('execute', state['guard_process'])
    require(sha(read(ADAPTER)) == ADAPTER_SHA and sha(read(SMOKE)) == SMOKE_SHA and
            prior_failures() == state['preserved_failures'] and checks_install() == state['checks_install_sha256'],
            'adapter/smoke, preserved failures or staged sources changed during retry')
    result_body = read(WORK / 'result.json'); result = json.loads(result_body)
    session = record(WORK / 'guard-session.json'); prep = state['prep']
    require(session == state['session'] and result.get('guard_session_sha256') == prep.digest(session), 'guard session differs from accepted preflight')
    require(result.get('schema') == 1 and result.get('finished_utc') and result.get('status') == 'GUARDED_FIRSTBOOT_COMPLETE' and result.get('checkpoint_accepted_by_guard') is True and
            result.get('bound_inputs_unchanged') is True and result.get('original_firstboot_checkpoint_present') is True and
            all(not result.get(k) for k in ('error', 'identity_error', 'attempt_error')) and
            all(result.get(k) is False for k in ('boot_complete', 'gpu_path_complete', 'app_gate_changed')), 'firstboot guard did not accept its checkpoint')
    attempt = canonical(Path(result['actual_attempt']['attempt']))
    require(attempt.parent == PREP / 'attempts' and attempt.name == '07-0004', 'invalid firstboot attempt path')
    new_attempts = {p.name for p in (PREP / 'attempts').iterdir() if re.fullmatch(r'07-\d{4}', p.name)} - set(state['attempts_before'])
    require(new_attempts == {attempt.name}, 'firstboot did not create exactly one new owned attempt')
    checkpoint_path = PREP / 'checkpoints/ios26-firstboot.json'; checkpoint_body = read(checkpoint_path); checkpoint = json.loads(checkpoint_body)
    old = state['session']['partition_audit']['checkpoints']
    require(result.get('checkpoint') == {'path': str(checkpoint_path), 'sha256': sha(checkpoint_body)} and
            checkpoint.get('attempt') == str(attempt) and checkpoint.get('stage') == 'ios26-firstboot' and checkpoint.get('status') == 'STAGE_COMPLETE' and
            checkpoint.get('session_sha256') == SESSION_DIGEST and checkpoint.get('previous_sha256') == old[str(PREP / 'checkpoints/ios26-partition.json')],
            'guard/checkpoint/attempt binding differs')
    require({p.name for p in checkpoint_path.parent.iterdir()} == {Path(p).name for p in old} | {checkpoint_path.name}, 'unexpected checkpoint boundary')
    for path, expected in old.items(): require(sha(read(Path(path))) == expected, 'predecessor checkpoint changed')
    require(set(result['actual_attempt']['files']) == {'stage-inputs.json', 'launch.json', 'vm-result.json', 'stage-result.json'},
            'missing or unexpected firstboot attempt metadata')
    for name, expected in result['actual_attempt']['files'].items():
        body = read(attempt / name); require(len(body) == expected['bytes'] and sha(body) == expected['sha256'], 'attempt metadata changed')
    stage_inputs = record(attempt / 'stage-inputs.json')
    require(record(attempt / 'stage-result.json') == checkpoint and stage_inputs.get('stage') == 'ios26-firstboot' and
            stage_inputs.get('session_sha256') == SESSION_DIGEST, 'firstboot stage metadata differs from accepted checkpoint')
    vm = record(attempt / 'vm-result.json'); launch = record(attempt / 'launch.json')
    require(result['actual_attempt'].get('vm-result.json') == vm and result['actual_attempt'].get('launch.json') == launch and
            launch.get('deadline_seconds') == 3600 and vm.get('schema') == 1 and vm.get('stage') == 'ios26-firstboot' and
            vm.get('finished_utc') and vm.get('status') == 'VM_OBSERVATION_COMPLETE' and prep.vm_success(vm, False) and
            vm.get('guest_sync_answered') is True and vm.get('cleanup', {}).get('quit_acknowledged') is True,
            'firstboot lacks original native/sync/clean controlled-stop evidence')
    supervision, counters = result.get('supervision', []), result.get('post_stop_blockstats', [])
    require(len(supervision) == len(counters) == 1 and supervision[0].get('status') == 'GUARDED_SUPERVISION_PASSED' and
            supervision[0].get('stage') == 'ios26-firstboot' and supervision[0].get('original_supervision_status') == 'VM_OBSERVATION_COMPLETE' and
            supervision[0].get('attempt') == str(attempt) and supervision[0].get('guest_sync_answered') is True and
            counters[0].get('status') == 'COUNTERS_CHECKED' and counters[0].get('stop_acknowledged') is True and
            counters[0].get('failed_io_counters_zero') is True and counters[0].get('stop_internal_flush_return_observed') is False and
            counters[0].get('counter_check') == state['guard'].failed_io_counters(counters[0]['post_stop_blockstats'], counters[0]['post_stop_blocks']),
            'mandatory guarded supervision or counter evidence differs')
    trace = [row for row in vm.get('qmp', []) if row.get('request', {}).get('execute') in ('stop', 'query-blockstats', 'query-block', 'quit')]
    require([row.get('request', {}).get('execute') for row in trace] == ['stop', 'query-blockstats', 'query-block', 'quit'] and
            all('return' in row.get('response', {}) and 'error' not in row['response'] for row in trace) and
            trace[1]['response']['return'] == counters[0]['post_stop_blockstats'] and trace[2]['response']['return'] == counters[0]['post_stop_blocks'],
            'actual QMP trace does not bind both ordered post-stop snapshots')
    absent(record(attempt / 'vm.child.json'), 'start_ticks')
    observations_body = read(WORK / 'guard-observations.json'); observations = json.loads(observations_body)
    require(observations.get('schema') == 1 and observations.get('post_stop_blockstats') == counters and
            observations.get('supervision') == supervision, 'guard observations differ from accepted result')
    require(sha(read(GUARD)) == GUARD_SHA, 'guard source changed during execution')
    fd = os.open(canonical(PREP / 'owner.lock'), os.O_RDONLY | os.O_NOFOLLOW)
    try:
        require(stat.S_ISREG(os.fstat(fd).st_mode), 'preparation lock is not ordinary')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB); prep.refuse_live_children(PREP)
    finally: os.close(fd)
    return {'result_sha256': sha(result_body), 'checkpoint_sha256': sha(checkpoint_body), 'attempt': str(attempt),
            'guard_session_file_sha256': sha(read(WORK / 'guard-session.json')), 'guard_observations_sha256': sha(observations_body),
            'adapter': adapter, 'preserved_failures': state['preserved_failures'], 'checks_install_sha256': state['checks_install_sha256']}


def run():
    state = prerequisites()
    OWNER.mkdir(mode=0o700)
    create('command.json', COMMAND)
    create('inputs.json', {'schema': 1, 'guard_source_sha256': GUARD_SHA, 'accepted_preflight_sha256': PREFLIGHT_SHA,
           'accepted_guard_session': state['session'], 'attempts_before': state['attempts_before'], 'resources': state['resources'],
           'adapter_source_sha256': ADAPTER_SHA, 'accepted_smoke_receipt_sha256': SMOKE_SHA,
           'adapter_preflight': state['adapter_preflight'], 'preserved_failures': state['preserved_failures'],
           'checks_install_sha256': state['checks_install_sha256'], 'staged_sources': STAGED,
           'vm_deadline_seconds': 3600, 'outer_deadline_seconds': OWNER_SECONDS, 'term_grace_seconds': TERM_SECONDS,
           'kill_reap_seconds': KILL_SECONDS, 'outer_source_sha256': sha(read(Path(__file__).resolve(strict=True)))})
    started, child, child_identity = utc(), None, None
    code = error = acceptance = None; forced = False; cleanup_errors = []

    def interrupted(number, _frame): raise InterruptedError('outer owner signal ' + str(number))

    handlers = {s: signal.signal(s, interrupted) for s in (signal.SIGINT, signal.SIGTERM)}
    try:
        launch_resources = resources()  # Fresh check immediately before guard spawn; guard rechecks before its VM.
        with os.fdopen(os.open(OWNER / 'run.log', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as output:
            child = subprocess.Popen(COMMAND, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT)
            child_identity = identity(child.pid); require(child_identity is not None, 'guard identity unavailable')
            state['guard_process'] = child_identity
            create('owner.json', {'schema': 1, 'started_utc': started, 'wrapper': identity(os.getpid()), 'guard': child_identity,
                   'command': COMMAND, 'resources': launch_resources, 'guard_process_group': os.getpgid(child.pid), 'guard_session': os.getsid(child.pid)})
            code = child.wait(timeout=OWNER_SECONDS); output.flush(); os.fsync(output.fileno())
        require(code == 0, 'guard exited ' + str(code))
        acceptance = accepted_result(state)
    except BaseException as exc:
        error = type(exc).__name__ + ': ' + str(exc)
        for number in handlers: signal.signal(number, signal.SIG_IGN)
        try:
            if child is not None and child.poll() is None:
                child.send_signal(signal.SIGTERM)
                try: child.wait(timeout=TERM_SECONDS)
                except subprocess.TimeoutExpired: forced = True; child.kill(); child.wait(timeout=KILL_SECONDS)
        except BaseException as exc: cleanup_errors.append(type(exc).__name__ + ': ' + str(exc))
        if child is not None: code = child.returncode
    finally:
        accepted = acceptance is not None and code == 0 and not error and not forced and not cleanup_errors
        try:
            for number in handlers: signal.signal(number, signal.SIG_IGN)
            create('exit.json', {'schema': 1, 'started_utc': started, 'finished_utc': utc(), 'command': COMMAND,
                   'wrapper': identity(os.getpid()), 'guard': child_identity, 'exit_code': code, 'owner_exit_code': 0 if accepted else 2,
                   'accepted': accepted, 'guard_started': child is not None, 'guard_reaped': child is not None and code is not None,
                   'wrapper_error': error, 'forced_guard': forced, 'cleanup_errors': cleanup_errors, 'acceptance': acceptance,
                   'requires_owned_process_recheck': True, 'boot_complete': False, 'gpu_path_complete': False, 'app_gate_changed': False})
        finally:
            for number, handler in handlers.items(): signal.signal(number, handler)
    return 0 if accepted else 2


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--execute', action='store_true', required=True)
    parser.parse_args()
    try: raise SystemExit(run())
    except Exception as exc:
        print(json.dumps({'schema': 1, 'status': 'FIRSTBOOT_OWNER_REFUSED', 'error': type(exc).__name__ + ': ' + str(exc)}), flush=True)
        raise SystemExit(2)
