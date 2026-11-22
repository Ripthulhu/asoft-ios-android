#!/usr/bin/env python3
"""Foreground adapter-bound read-only guard preflight; no boot execution or repeated smoke."""
import datetime, hashlib, itertools, json, os, re, signal, stat, subprocess
from pathlib import Path

BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
PREFIX = 'ios26-firstboot-guard-preflight-resume1'
GUARD = Path('/data/local/tmp/pixel-boot-checks-counter1/firstboot/guard_ios26_firstboot.py')
GUARD_SHA = 'ea40638312d6ac41607806ecb03c148fbd0677df6ab01480e13fd40536869674'
AUDIT = Path('/data/local/tmp/pixel-audit-e9cc754')
AUDIT_SHA = '542dcf281cbcfb0016d74eda8dbb7a84db799e390e857321f519de4e0f1a7146'
WORK = Path('/data/local/tmp/pixel-firstboot-guard-e9cc754-resume1')
ADAPTER = BASE / 'run-ios26-firstboot-memfd-adapter-resume1.py'
ADAPTER_SHA = 'ede70023bc1e05b08730b48fab1016c3e665c0e83469509e5b8b74c6f2364ec7'
SMOKE = BASE / 'python-memfd-smoke-memfd1.json'
SMOKE_SHA = '57d7239160422a858ed9882191c5012fd20a20d5b790f482be15013266f313bd'
FAILED_WORK = Path('/data/local/tmp/pixel-firstboot-guard-e9cc754')
FAILED_OWNER = BASE / 'ios26-firstboot-owner-ebbc9c0'
FAILED_RESULT_SHA = '2a4b1ad20f478db58eb5ca7219789146b973f364cf4e7f079eb6acd4f5e7519d'
FAILED_EXIT_SHA = 'c651a9fae9976e04eada79bc229604a9724ea4053723d6b05ee6c0df02ce28b1'
COMMAND = ['/data/data/com.termux/files/usr/bin/python', '-I', '-B', str(ADAPTER)]
GUARD_ARGV = [str(GUARD), '--audit-work', str(AUDIT), '--auditor-dir', '/data/local/tmp/pixel-boot-checks-ebbc9c0/auditor',
              '--runner-dir', '/data/local/tmp/pixel-prep-runner-f4d64db', '--work', str(WORK)]

STAGED = {'/data/local/tmp/pixel-boot-checks-counter1/firstboot/guard_ios26_firstboot.py': {'bytes': 25686, 'sha256': 'ea40638312d6ac41607806ecb03c148fbd0677df6ab01480e13fd40536869674'}, '/data/local/tmp/pixel-saved-checks-counter1/inspect_ios26_firstboot.py': {'bytes': 26030, 'sha256': '2b127ecda390b199287358cdad7e6e7774f5b787148aea524e7b0247a2640cf3'}, '/data/local/tmp/pixel-saved-checks-counter1/inspect_ios26_firstboot_guest.py': {'bytes': 16829, 'sha256': 'ada26de8ababb11bb4af20e558708545eb64fd516481359fd5d0ccf6a7cbae2b'}}
CHECKS_INSTALL = BASE / 'counter1-guard-inspector-install.json'
FAILED2_PINS = {'owner_exit': {'path': '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-firstboot-owner-memfd1/exit.json', 'bytes': 805, 'sha256': '701461a97e794ae669cadda23cbb8a475adb974556d0c4e5cf6c552876a629f5'}, 'guard_result': {'path': '/data/local/tmp/pixel-firstboot-guard-e9cc754-memfd1/result.json', 'bytes': 24006, 'sha256': 'f618a29bc550d6155e78ed3757e3ce715b6c75b1fcf1745c6d6b55944b6a345a'}, 'guard_observations': {'path': '/data/local/tmp/pixel-firstboot-guard-e9cc754-memfd1/guard-observations.json', 'bytes': 8098, 'sha256': '75bcf49437cba79303d019dbd3cdedba63cf269b93cdc5ba9384d47773923a9a'}, 'adapter_owner': {'path': '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-firstboot-memfd1-adapter-execute.owner.json', 'bytes': 1869, 'sha256': 'eed7eaa19246e6bf0ce52839de8040394521111fe1bf60acc67c90a967b1f73c'}, 'adapter_exit': {'path': '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-firstboot-memfd1-adapter-execute.exit.json', 'bytes': 2048, 'sha256': 'fa0a41b1a50e4b9d675b458f7e1cf10af857f8dc41ff74d9e9a46b00008c494b'}, 'attempt_launch': {'path': '/data/local/tmp/pixel-prep-e9cc754/attempts/07-0002/launch.json', 'bytes': 3048, 'sha256': '1137b883bf9472361d9dd80eaed7514de5d4b5a2029230d37531c740719814e7'}, 'attempt_vm_result': {'path': '/data/local/tmp/pixel-prep-e9cc754/attempts/07-0002/vm-result.json', 'bytes': 10131, 'sha256': '6858d9d196127206b79c604321358cc48f61e2405fc4405791510ed70d211428'}}


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def read(path, limit=2 << 20):
    if path.resolve(strict=True) != path: raise ValueError('noncanonical metadata: ' + str(path))
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
            raise ValueError('nonordinary or oversized metadata')
        body = stream.read(limit + 1)
    if len(body) > limit: raise ValueError('metadata grew beyond bound')
    return body


def save(name, value):
    with os.fdopen(os.open(BASE / (PREFIX + name), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as stream:
        json.dump(value, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    directory = os.open(BASE, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(directory)
    finally: os.close(directory)


def identity(pid):
    try:
        with Path('/proc/{}/stat'.format(pid)).open('rb') as stream: raw = stream.read(4097)
    except FileNotFoundError:
        return None
    if len(raw) > 4096: raise ValueError('process metadata exceeded bound')
    return {'pid': pid, 'starttime': int(raw[raw.rfind(b')') + 2:].split()[19])}


def text(path, limit=4096):
    try:
        with Path(path).open('rb') as stream: body = stream.read(limit + 1)
        return body.decode('ascii').strip() if len(body) <= limit else '<oversized>'
    except (OSError, UnicodeError):
        return None


def observation():
    memory = re.search(r'^MemAvailable:\s+(\d+) kB$', text('/proc/meminfo', 65536) or '', re.M)
    available = int(memory[1]) * 1024 if memory else None
    disk = os.statvfs(BASE); free = disk.f_bavail * disk.f_frsize
    zones = list(itertools.islice(Path('/sys/class/thermal').glob('thermal_zone*'), 65))
    thermal = [{'zone': z.name, 'type': text(z / 'type', 128), 'temp_raw': text(z / 'temp', 128)} for z in zones[:64]]
    return {'at_utc': utc(), 'mem_available_bytes': available, 'free_bytes': free,
            'memory_floor_bytes': 3840 << 20, 'memory_floor_met': available is not None and available >= 3840 << 20,
            'space_floor_bytes': 4500000000, 'space_floor_met': free >= 4500000000,
            'battery': {n: text('/sys/class/power_supply/battery/' + n, 256) for n in ('status', 'capacity', 'temp', 'voltage_now', 'current_now')},
            'power_online': {n: text('/sys/class/power_supply/' + n + '/online', 128) for n in ('usb', 'ac', 'wireless')},
            'thermal': thermal, 'thermal_list_truncated': len(zones) > 64}


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



def adapter_evidence(child_id):
    prefix = BASE / 'ios26-firstboot-resume1-adapter-preflight'
    owner_body, exit_body = (read(Path(str(prefix) + suffix)) for suffix in ('.owner.json', '.exit.json'))
    startup, exited = json.loads(owner_body), json.loads(exit_body)
    names = ['memfd_create', 'MFD_CLOEXEC', 'MFD_ALLOW_SEALING']
    if (any(exited.get(k) != v for k, v in startup.items()) or startup.get('schema') != 1 or
            startup.get('phase') != 'preflight' or startup.get('process') != child_id or startup.get('command') != COMMAND or
            startup.get('guard_argv') != GUARD_ARGV or startup.get('adapter_source_sha256') != ADAPTER_SHA or
            startup.get('guard_source_sha256') != GUARD_SHA or startup.get('missing_attributes') != names or
            startup.get('installed_attributes') != names or startup.get('constants') != {'MFD_CLOEXEC': 1, 'MFD_ALLOW_SEALING': 2} or
            startup.get('accepted_libc_smoke', {}).get('receipt_sha256') != SMOKE_SHA or
            startup.get('boot_execution_requested') is not False or exited.get('exit_code') != 0 or exited.get('error') is not None or
            exited.get('adapter_completed') is not True or exited.get('attributes_restored') is not True or exited.get('sources_unchanged') is not True):
        raise ValueError('adapter preflight provenance or cleanup differs')
    return {'owner_sha256': hashlib.sha256(owner_body).hexdigest(), 'exit_sha256': hashlib.sha256(exit_body).hexdigest(),
            'adapter_source_sha256': ADAPTER_SHA, 'smoke_receipt_sha256': SMOKE_SHA,
            'installed_attributes': names, 'attributes_restored': True, 'adapter_completed': True}


def main():
    if os.geteuid() != 0 or BASE.resolve(strict=True) != BASE: raise ValueError('canonical root transfer directory required')
    if os.path.lexists(WORK) or '--execute' in COMMAND: raise ValueError('fresh work and preflight-only argv required')
    for suffix in ('.command.json', '.owner.json', '.stdout.json', '.exit.json'):
        if os.path.lexists(BASE / (PREFIX + suffix)): raise FileExistsError('capture already exists; preserve it')
    if hashlib.sha256(read(ADAPTER)).hexdigest() != ADAPTER_SHA: raise ValueError('staged adapter source differs')
    if hashlib.sha256(read(SMOKE)).hexdigest() != SMOKE_SHA: raise ValueError('accepted smoke receipt differs')
    prior = prior_failures(); checks_install_sha = checks_install()
    if hashlib.sha256(read(GUARD)).hexdigest() != GUARD_SHA: raise ValueError('staged guard source differs')
    if hashlib.sha256(read(AUDIT / 'result.json')).hexdigest() != AUDIT_SHA: raise ValueError('accepted audit result differs')
    attempts = Path('/data/local/tmp/pixel-prep-e9cc754/attempts')
    existing = sorted(p.name for p in attempts.iterdir() if re.fullmatch(r'07-\d{4}', p.name))
    if existing != ['07-0001','07-0002','07-0003']: raise ValueError('expected exactly three preserved failed firstboot attempts')
    if os.path.lexists(attempts.parent/'checkpoints/ios26-firstboot.json'): raise ValueError('firstboot already exists; inspect instead')
    start, before = utc(), observation()
    save('.command.json', {'schema': 1, 'started_utc': start, 'command': COMMAND, 'before': before,
                          'guard_source_sha256': GUARD_SHA, 'accepted_audit_result_sha256': AUDIT_SHA, 'preflight_only': True,
                          'adapter_source_sha256': ADAPTER_SHA, 'smoke_receipt_sha256': SMOKE_SHA, 'preserved_failures': prior, 'checks_install_sha256': checks_install_sha})
    child = child_id = None; code = error = None; forced = False; cleanup_errors = []; parsed = {}; adapter = None

    def interrupted(number, _frame): raise InterruptedError('capture signal ' + str(number))

    handlers = {s: signal.signal(s, interrupted) for s in (signal.SIGINT, signal.SIGTERM)}
    try:
        with os.fdopen(os.open(BASE / (PREFIX + '.stdout.json'), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as output:
            child = subprocess.Popen(COMMAND, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT)
            child_id = identity(child.pid)
            startup = {'schema': 1, 'started_utc': start, 'wrapper': identity(os.getpid()), 'preflight': child_id, 'command': COMMAND}
            save('.owner.json', startup); print(json.dumps(startup), flush=True)
            code = child.wait(timeout=600); output.flush(); os.fsync(output.fileno())
        parsed = json.loads(read(BASE / (PREFIX + '.stdout.json')))
        adapter = adapter_evidence(child_id)
        if prior_failures() != prior or checks_install() != checks_install_sha: raise ValueError('prior failures or source installation changed')
    except BaseException as exc:
        error = type(exc).__name__ + ': ' + str(exc)
        for number in handlers: signal.signal(number, signal.SIG_IGN)
        try:
            if child is not None and child.poll() is None:
                child.terminate()
                try: child.wait(timeout=10)
                except subprocess.TimeoutExpired: forced = True; child.kill(); child.wait(timeout=10)
        except BaseException as exc: cleanup_errors.append(type(exc).__name__ + ': ' + str(exc))
        if child is not None: code = child.returncode
    finally:
        for number in handlers: signal.signal(number, signal.SIG_IGN)
        try:
            session = parsed.get('guard_session', {}); audit = session.get('partition_audit', {})
            stdout = read(BASE / (PREFIX + '.stdout.json')) if (BASE / (PREFIX + '.stdout.json')).exists() else b''
            unchanged = (hashlib.sha256(read(GUARD)).hexdigest() == GUARD_SHA and
                         hashlib.sha256(read(AUDIT / 'result.json')).hexdigest() == AUDIT_SHA and
                         hashlib.sha256(read(ADAPTER)).hexdigest() == ADAPTER_SHA and hashlib.sha256(read(SMOKE)).hexdigest() == SMOKE_SHA and
                         hashlib.sha256(read(FAILED_OWNER / 'exit.json')).hexdigest() == FAILED_EXIT_SHA and
                         hashlib.sha256(read(FAILED_WORK / 'result.json')).hexdigest() == FAILED_RESULT_SHA and
                         prior_failures() == prior and checks_install() == checks_install_sha and not os.path.lexists(WORK))
            accepted = bool(adapter is not None and code == 0 and not error and not forced and not cleanup_errors and unchanged and
                parsed.get('schema') == 1 and parsed.get('status') == 'PREFLIGHT_READY' and
                session.get('kind') == 'ios26_firstboot_execution_guard' and session.get('guard_source_sha256') == GUARD_SHA and
                audit.get('audit_result_sha256') == AUDIT_SHA and len(audit.get('checkpoints', {})) == 7 and
                all(parsed.get(k) is False for k in ('boot_complete', 'gpu_path_complete', 'app_gate_changed')))
            receipt = {'schema': 1, 'started_utc': start, 'finished_utc': utc(), 'command': COMMAND,
                'preflight': child_id, 'exit_code': code, 'owner_exit_code': 0 if accepted else 2,
                'accepted_readonly_preflight': accepted, 'preflight_reaped': child is not None and code is not None,
                'forced_child': forced, 'wrapper_error': error, 'cleanup_errors': cleanup_errors,
                'stdout_bytes': len(stdout), 'stdout_sha256': hashlib.sha256(stdout).hexdigest(),
                'selected': {'status': parsed.get('status'), 'error': parsed.get('error'), 'guard_source_sha256': session.get('guard_source_sha256'),
                  'prep_session_sha256': session.get('prep_session_sha256'), 'audit_result_sha256': audit.get('audit_result_sha256'),
                  'checkpoint_count': len(audit.get('checkpoints', {})), 'mandatory_next_gate': session.get('mandatory_next_gate')},
                'guard_work_absent': not os.path.lexists(WORK), 'inputs_unchanged': unchanged,
                'before': before, 'after': observation(), 'boot_execution_requested': False,
                'adapter': adapter, 'adapter_source_sha256': ADAPTER_SHA, 'smoke_receipt_sha256': SMOKE_SHA, 'preserved_failures': prior, 'checks_install_sha256': checks_install_sha}
            save('.exit.json', receipt)
            print('FIRSTBOOT READ-ONLY PREFLIGHT', parsed.get('status'), 'accepted=', accepted, 'boot_requested=false')
            print('exit=', code, 'reaped=', receipt['preflight_reaped'], 'forced=', forced, 'cleanup_errors=', cleanup_errors)
            print('stdout_bytes=', len(stdout))
            print('stdout_sha_a=', receipt['stdout_sha256'][:32]); print('stdout_sha_b=', receipt['stdout_sha256'][32:])
            print('stdout_sha_decimal=', list(bytes.fromhex(receipt['stdout_sha256'])))
            print('guard_sha256=', session.get('guard_source_sha256'))
            print('adapter_sha256=', ADAPTER_SHA, 'completed/restored=', adapter is not None)
            print('smoke_receipt_sha256=', SMOKE_SHA, 'preserved_failed_attempts=07-0001,07-0002,07-0003')
            print('checks_install_sha_a=', checks_install_sha[:32]); print('checks_install_sha_b=', checks_install_sha[32:])
            print('audit_result_sha256=', audit.get('audit_result_sha256'))
            print('checkpoints=', len(audit.get('checkpoints', {})), 'guard_work_absent=', receipt['guard_work_absent'], 'inputs_unchanged=', unchanged)
            for label in ('before', 'after'):
                row = receipt[label]
                print(label, row['at_utc'], 'MemAvailable=', row['mem_available_bytes'], 'free=', row['free_bytes'], '3840MiB_met=', row['memory_floor_met'], '4.5GB_met=', row['space_floor_met'])
            after = receipt['after']; print('battery=', json.dumps(after['battery']), 'power_online=', json.dumps(after['power_online']))
            observed = sorted((z for z in after['thermal'] if re.fullmatch(r'-?\d+', z['temp_raw'] or '')), key=lambda z: int(z['temp_raw']), reverse=True)
            print('observed_hottest_raw=', json.dumps(observed[:5]), 'thermal_truncated=', after['thermal_list_truncated'])
            print('error=', error or parsed.get('error'), flush=True)
        finally:
            for number, handler in handlers.items(): signal.signal(number, handler)
    return 0 if accepted else 2


if __name__ == '__main__':
    raise SystemExit(main())
