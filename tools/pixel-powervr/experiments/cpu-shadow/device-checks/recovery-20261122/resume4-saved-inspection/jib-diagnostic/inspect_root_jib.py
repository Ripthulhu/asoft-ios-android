#!/usr/bin/env python3
"""Compare only the two pinned iOSRoot JIBs after the actual resume4 refusal.

Sixteen fixed 512-byte qemu-img reads retain two 4096-byte blocks in fresh own
output. Only scalar fields, hashes and capped difference offsets are exported.
No journal pointer follow, VM, fsck, mount, replay, repair or acceptance change.
Before/after identity checks do not claim a new full-disk hash recomputation.
"""
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import signal
import stat
import struct
import subprocess
import types

BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
OWNER_SOURCE = BASE / 'run-ios26-saved-inspection-resume4.py'
OWNER_SOURCE_PIN = {'bytes': 48469, 'sha256': 'c5cc01768be23c0a7e3ad1364cb89a3dd8562288ac3c51f5eaef35ce7c039f10'}
DIAGNOSTIC_SOURCE = BASE / 'run-ios26-root-jib-diagnostic-resume4.py'
OUT = BASE / 'ios26-root-jib-diagnostic-resume4'
OWNER = BASE / 'ios26-saved-inspection-resume4-owner'
WORK = Path('/data/local/tmp/pixel-saved-audit-e9cc754-resume4')
MONITOR = BASE / 'ios26-saved-inspection-resume4-observer-procstat1'
MONITOR_SOURCE = BASE / 'run-ios26-saved-inspection-resume4-observer-procstat1.py'
MONITOR_SOURCE_PIN = {'bytes': 37877, 'sha256': '949da38590f86d827e6b9fb2f261e785e89b4e3cfe1efdbfbea60354cd281ed9'}
PREFLIGHT_PIN = {'bytes': 9069, 'sha256': 'd68aa23ba833c8939ace08005c573f11764c104bbbae29a5f0285677c7239bf6'}
HEADER_SOURCE = BASE / 'run-ios26-hfs-header-diagnostic-resume2.py'
HEADER_SOURCE_PIN = {'bytes': 22740, 'sha256': 'e79c0fbc472ae2a875164565802feffc4fad0a630571970f6e68d7251801bdcd'}
HEADER_OUT = BASE / 'ios26-hfs-header-diagnostic-resume2'
HEADER_RESULT_PIN = {'bytes': 14542, 'sha256': 'd768516e7cc9846e35aefa5f7583797b4cc0c129402a16994965501c69882ba6'}
TOOL_PIN = {'bytes': 2356032, 'sha256': '1bd2fd6b968c492d0263436c260af2a8c2ee807cf4afd4fd2abb3300446e2440'}
TOOL_MANIFEST_SHA = 'a5461ecf2e41d4966f783dfca620d3d700f9aa1bc76dd5fa745ec54666e764b2'
CAPABILITY_RESULT = BASE / 'ios26-hfs-header-capability-resume4/result.json'
CAPABILITY_PIN = {'bytes': 2659, 'sha256': '897cb1faaab342ff576fcc8a3e8d958282f0d44fd0162c445457853cf1d8c11c'}
CAPABILITY_SOURCE_SHA256 = '4264533ff68a0a116aeecbe140de041b1f02b5036f9bf83783d2f4958f1ece8f'
EXPECTED_WRAPPER = {'pid': 20063, 'starttime': 9342623}
EXPECTED_INSPECTOR = {'pid': 20064, 'starttime': 9342659}
EXPECTED_QEMU = {'pid': 21484, 'start_ticks': 9363754}
EXPECTED_OBSERVER = {'pid': 18179, 'start_ticks': 9323114}
EXPECTED_ERROR = 'ValueError: guest inspection incomplete; retained metadata classifies the boundary'
ROOT_START_SECTORS = 2048
ROOT_SECTORS = 67108864
SECTOR_BYTES = 512
BLOCK_BYTES = 4096
ROOT_BYTES = ROOT_SECTORS * SECTOR_BYTES
DISK_BYTES = 51541704704
EXPECTED_JIB_BLOCK = 257
EXPECTED_JIB_OFFSET = 2101248
LIMITS = {'tool_seconds': 15, 'cleanup_seconds': 5, 'tool_cpu_seconds': 10,
          'min_available_mib': 2816, 'min_free_mib': 1536, 'tool_output_bytes': 64 << 10,
          'jibs': 2, 'jib_bytes': 4096, 'sector_bytes': 512, 'tool_calls': 16,
          'difference_ranges': 128, 'result_bytes': 64 << 10}
RECEIPT_PINS = {'/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume4-observer-procstat1/events.jsonl': {'bytes': 48601,
                                                                                                                'sha256': '81d8df8425d3be6df9bed237fead205ee27f15aec40078742eabc029bd63409a'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume4-observer-procstat1/exit.json': {'bytes': 478,
                                                                                                             'sha256': '149820613afba9b5b1ba4279198efe7e7ffc5e8cc202b89b46997c292421b903'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume4-observer-procstat1/ready.json': {'bytes': 3839,
                                                                                                              'sha256': '98bd34d1c290027db202ce1ea94c57029fe2c520d5c88c601eecd32ca1c9c215'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume4-observer-procstat1/summary.json': {'bytes': 12457,
                                                                                                                'sha256': '998a6c55622a953eaaf3151d69a97b8cbfdb505b4b1f0422b208d0f7d371c5cd'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume4-owner/exit.json': {'bytes': 905,
                                                                                                'sha256': '42d8672e28ee85245517dada0d016299bf4a22d833cd5cfae968585755cb1d49'},
 '/data/local/tmp/pixel-saved-audit-e9cc754-resume4/a1/expected-policy.json': {'bytes': 271,
                                                                               'sha256': '2592a62d9f9169d015a8822221dae848bc3b346b8f81e4c69ec1ebe531796a3d'},
 '/data/local/tmp/pixel-saved-audit-e9cc754-resume4/a1/files/inspection/result.json': {'bytes': 1948,
                                                                                       'sha256': '72f505c0407a145575408d09a0817d808358a7a7149fe7a13c0290b756f2ce8e'},
 '/data/local/tmp/pixel-saved-audit-e9cc754-resume4/a1/vm-result.json': {'bytes': 1264,
                                                                         'sha256': 'b34b5f2195732900b4710116e70db9c0daa2a7b1c0533c8c397d18f12b611cb2'},
 '/data/local/tmp/pixel-saved-audit-e9cc754-resume4/result.json': {'bytes': 3681,
                                                                   'sha256': '39516c6f49bab5114dd612780f8e6113e869bcac44dea90127f20901710ff51c'}}


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


def decode_header(body, image, volume, copy, offset, sectors):
    require(len(body) == 512, 'exact 512-byte header read required')
    signature, version, attributes, mounted, jib = struct.unpack_from('>HHIII', body)
    block, blocks, free = struct.unpack_from('>III', body, 40)
    count = struct.unpack_from('>I', body, 68)[0]
    return {'image': image, 'volume': volume, 'copy': copy, 'virtual_offset': offset, 'bytes': len(body),
            'sha256': sha(body), 'signature_hex': '0x%04x' % signature, 'version': version,
            'attributes': attributes, 'attributes_hex': '0x%08x' % attributes,
            'journaled_bit13': bool(attributes & 0x2000), 'boot_inconsistent_bit11': bool(attributes & 0x0800),
            'runtime_inconsistent_bit14': bool(attributes & 0x4000), 'clean_unmount_bit8': bool(attributes & 0x0100),
            'last_mounted_version': mounted, 'last_mounted_version_hex': '0x%08x' % mounted,
            'journal_info_block': jib, 'block_bytes': block, 'total_blocks': blocks, 'free_blocks': free,
            'write_count': count, 'volume_id_sha256': sha(body[104:112]),
            'geometry_matches_frozen_expectation': (signature, version, block, blocks) == (0x4858, 5, 4096, sectors * 512 // 4096)}


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


def bound_read(path, pin, metadata):
    """Cache and bind the exact bytes that the caller will parse or compile."""
    require(type(pin) is dict and set(pin) == {'bytes', 'sha256'} and
            type(pin['bytes']) is int and 0 < pin['bytes'] <= 4 << 20 and
            type(pin['sha256']) is str and re.fullmatch('[0-9a-f]{64}', pin['sha256']),
            'invalid fixed input pin')
    body = small_read(path, pin['bytes'])
    require({'bytes': len(body), 'sha256': sha(body)} == pin, 'fixed input changed: ' + str(path))
    require(str(path) not in metadata or metadata[str(path)] == pin['sha256'], 'input bindings disagree')
    metadata[str(path)] = pin['sha256']
    return body


def load_bound_owner():
    require(os.geteuid() == 0 and BASE.resolve(strict=True) == BASE, 'root and canonical base required')
    body = bound_read(OWNER_SOURCE, OWNER_SOURCE_PIN, {})
    m = module(body, OWNER_SOURCE, 'verified_resume4_saved_inspection_owner')
    require(m.OWNER == OWNER and m.WORK == WORK and m.BASE == BASE and
            m.INSPECTOR == Path('/data/local/tmp/pixel-saved-checks-resume3') and
            m.HEADER_SOURCE == HEADER_SOURCE and m.HEADER_WORK == HEADER_OUT,
            'current owner or preserved header scope differs')
    return m


def check_metadata(m):
    """Validate current resume4 evidence separately from the preserved resume2 set."""
    expected = {str(OWNER / 'exit.json'), str(WORK / 'result.json'), str(WORK / 'a1/vm-result.json'),
                str(WORK / 'a1/files/inspection/result.json'), str(WORK / 'a1/expected-policy.json'),
                *(str(MONITOR / name) for name in ('ready.json', 'exit.json', 'summary.json', 'events.jsonl'))}
    require(set(RECEIPT_PINS) == expected, 'exact nine observed resume4 receipt paths required')
    metadata, cached = {}, {}
    for name, pin in RECEIPT_PINS.items():
        cached[name] = bound_read(Path(name), pin, metadata)
    bound_read(OWNER_SOURCE, OWNER_SOURCE_PIN, metadata)
    bound_read(MONITOR_SOURCE, MONITOR_SOURCE_PIN, metadata)
    public_body = bound_read(OWNER / 'preflight.json', PREFLIGHT_PIN, metadata)
    public = json.loads(public_body)
    current = m.read_json(OWNER / 'prerequisites.json')
    m.validate_preflight(public, current)
    for historical in (m.previous_failure_inputs(), m.resume2_failure_inputs()):
        require(all(current['inputs'].get(name) == pin for name, pin in historical.items()),
                'historical preservation set was not bound by the current preflight')
    for name, pin in current['inputs'].items():
        require(sha(small_read(Path(name))) == pin, 'bound preparation/source input changed')
        require(name not in metadata or metadata[name] == pin, 'current preservation bindings disagree')
        metadata[name] = pin
    for path, pin in m.SOURCE_HASHES.items():
        require(sha(small_read(path)) == pin, 'reviewed runtime or inspector source changed')
        metadata[str(path)] = pin
    startup = m.read_json(OWNER / 'owner.json')
    exited = json.loads(cached[str(OWNER / 'exit.json')])
    require(startup.get('schema') == exited.get('schema') == 1 and
            startup.get('wrapper') == EXPECTED_WRAPPER and startup.get('runner') == EXPECTED_INSPECTOR and
            startup.get('command') == exited.get('command') == m.read_json(OWNER / 'command.json') == m.COMMAND + ['--execute'] and
            all(startup.get(k) == exited.get(k) for k in ('wrapper', 'runner', 'started_utc')) and
            exited.get('exit_code') == exited.get('owner_exit_code') == 2 and exited.get('accepted') is False and
            exited.get('runner_started') is True and exited.get('runner_reaped') is True and
            exited.get('forced_runner') is False and exited.get('cleanup_errors') == [] and
            exited.get('wrapper_error') == 'ValueError: inspector exited 2' and exited.get('finished_utc'),
            'actual resume4 failed owner differs')
    for name in ('wrapper', 'runner'):
        m.absent(startup[name], 'completed resume4 ' + name)
    qemu = m.read_json(WORK / 'a1/vm.child.json')
    require(qemu == EXPECTED_QEMU, 'actual resume4 QEMU identity differs')
    m.absent(qemu, 'completed resume4 QEMU', 'start_ticks')
    result_body = cached[str(WORK / 'result.json')]
    require(result_body == small_read(WORK / 'a1/inspection-result.json'), 'returned host results disagree')
    result = json.loads(result_body)
    guest = json.loads(cached[str(WORK / 'a1/files/inspection/result.json')])
    policy = json.loads(cached[str(WORK / 'a1/expected-policy.json')])
    require(result.get('schema') == 1 and result.get('status') == 'INCOMPLETE' and result.get('error') == EXPECTED_ERROR and
            result.get('full_backing_chain_unchanged') is True and result.get('preparation_and_guard_unchanged') is True and
            result.get('identity_error') is None and result.get('guest_result') == guest and
            all(result.get(k) is False for k in ('boot_complete', 'gpu_path_complete', 'app_gate_changed')),
            'actual resume4 host failure boundary differs')
    require(guest.get('schema') == 1 and guest.get('kind') == 'ios26_saved_firstboot_inspection' and
            guest.get('status') == 'INCOMPLETE' and guest.get('readonly_attachments') is True and
            all(guest.get(k) is False for k in ('mounted', 'replayed', 'repaired', 'boot_complete', 'gpu_path_complete')) and
            guest.get('errors') == [{'code': 'root_baseline_jib_changed'}] and guest.get('cleanup_errors') == [] and
            guest.get('journals') == {'iOSRoot': {'status': 'INCOMPLETE', 'code': 'root_baseline_jib_changed'}} and
            guest.get('fsck') == {}, 'actual JIB refusal differs')
    require(type(guest.get('inspection_nonce')) is str and re.fullmatch('[0-9a-f]{32}', guest['inspection_nonce']) and
            guest['inspection_nonce'] == policy.get('inspection_nonce') and guest.get('policy_sha256') == m.digest(policy) and
            type(guest.get('gpt')) is dict and guest['gpt'].get('status') == 'PASSED' and
            guest['gpt'].get('disk_bytes') == DISK_BYTES and guest['gpt'] == guest.get('baseline_gpt'),
            'actual guest policy or GPT binding differs')
    for name in ('fsck-system.txt', 'fsck-data.txt'):
        require(not os.path.lexists(WORK / 'a1/files/inspection' / name), 'unexpected retained fsck diagnostic')
    vm = json.loads(cached[str(WORK / 'a1/vm-result.json')])
    cleanup, witnesses = vm.get('cleanup', {}), vm.get('witnesses', {})
    require(vm.get('status') == 'VM_OBSERVATION_COMPLETE' and vm.get('natural_exit') is True and vm.get('error') is None and
            cleanup.get('exit_code') == 0 and cleanup.get('echild') is True and cleanup.get('forced_qemu') is False and
            cleanup.get('forced_descendants') == [] and cleanup.get('errors') == [] and
            all(witnesses.get(k) is True for k in ('native_initialization', 'native_execution', 'native_svc_final')) and
            witnesses.get('fatal_markers') == [], 'actual native VM or cleanup boundary differs')
    ready = json.loads(cached[str(MONITOR / 'ready.json')])
    observer_exit = json.loads(cached[str(MONITOR / 'exit.json')])
    summary = json.loads(cached[str(MONITOR / 'summary.json')])
    require(ready.get('schema') == 1 and ready.get('kind') == 'saved_inspection_process_observer_ready' and
            ready.get('status') == 'READY' and ready.get('observer') == EXPECTED_OBSERVER and
            ready.get('source') == {'path': str(MONITOR_SOURCE), **MONITOR_SOURCE_PIN} and
            ready.get('scope', {}).get('inspection_owner_directory') == str(OWNER) and
            ready.get('scope', {}).get('inspection_work') == str(WORK) and
            ready.get('scope', {}).get('inspection_command') == m.COMMAND + ['--execute'] and
            all(ready.get('preflight', {}).get(k) == v for k, v in {'path': str(OWNER / 'preflight.json'), **PREFLIGHT_PIN}.items()),
            'preserved current observer scope differs')
    require(observer_exit.get('schema') == summary.get('schema') == 1 and
            observer_exit.get('status') == summary.get('status') == 'OBSERVATION_FINISHED' and
            observer_exit.get('exit_code') == 0 and observer_exit.get('observer') == summary.get('observer') == EXPECTED_OBSERVER and
            observer_exit.get('errors') == summary.get('errors') == [] and summary.get('remaining_observed_identities') == [] and
            observer_exit.get('diagnostic_only') is True and summary.get('diagnostic_only') is True and
            observer_exit.get('summary') == {'path': str(MONITOR / 'summary.json'), **RECEIPT_PINS[str(MONITOR / 'summary.json')]} and
            summary.get('ready') == {'path': str(MONITOR / 'ready.json'), **RECEIPT_PINS[str(MONITOR / 'ready.json')]} and
            all(summary.get('events', {}).get(k) == v for k, v in
                {'path': str(MONITOR / 'events.jsonl'), **RECEIPT_PINS[str(MONITOR / 'events.jsonl')]}.items()),
            'preserved current observer completion differs')
    # Sampling/read gaps are preserved by the exact pins, not converted into a
    # claim of complete observation or used to alter the inspection verdict.
    m.absent(EXPECTED_OBSERVER, 'completed resume4 independent observer', 'start_ticks')
    inspected = m.read_json(WORK / 'inspection-session.json')
    require(m.digest(inspected) == result.get('inspection_session_sha256') and
            inspected == public.get('inspection_session'), 'actual inspection and accepted preflight sessions differ')
    for path in (OWNER / 'owner.json', OWNER / 'command.json', OWNER / 'prerequisites.json',
                 WORK / 'inspection-session.json', WORK / 'a1/vm.child.json', WORK / 'a1/inspection-result.json'):
        metadata[str(path)] = sha(small_read(path))
    return current, inspected, metadata


def root_offset(block_bytes, jib_block):
    require(type(block_bytes) is int and type(jib_block) is int and block_bytes == BLOCK_BYTES,
            'root block geometry differs')
    require(0 < jib_block < ROOT_BYTES // block_bytes - 1, 'root JIB block outside volume')
    base = ROOT_START_SECTORS * SECTOR_BYTES
    offset = base + jib_block * block_bytes
    require(offset % SECTOR_BYTES == 0 and base + block_bytes <= offset and
            offset + BLOCK_BYTES <= base + ROOT_BYTES - block_bytes and offset + BLOCK_BYTES <= DISK_BYTES,
            'root JIB range outside fixed volume')
    require(jib_block == EXPECTED_JIB_BLOCK and offset == EXPECTED_JIB_OFFSET,
            'derived JIB location differs from actual pinned headers')
    return offset


def load_header_layouts(m, metadata):
    """Derive scope from all four bound root headers, without opening an image."""
    bound_read(HEADER_SOURCE, HEADER_SOURCE_PIN, metadata)
    headers = json.loads(bound_read(HEADER_OUT / 'result.json', HEADER_RESULT_PIN, metadata))
    require(headers.get('status') == 'READONLY_HFS_HEADERS_OBSERVED' and
            headers.get('source') == {'path': str(HEADER_SOURCE), **HEADER_SOURCE_PIN} and
            len(headers.get('headers', [])) == len(headers.get('tool_commands', [])) == 8,
            'preserved header result differs')
    session_path = WORK / 'inspection-session.json'
    session_body = small_read(session_path)
    require(metadata.get(str(session_path)) == sha(session_body), 'current inspection session changed before root derivation')
    chain = json.loads(session_body).get('backing_chain')
    require(type(chain) is list and len(chain) == 2 and
            headers.get('previous_full_hash_records') == [row['record'] for row in chain],
            'retained headers and current inspected image records differ')
    images = [str(Path(row['identity']['path'])) for row in chain]
    root_rows, root_bodies = {}, {}
    for index, image, copy in ((0, 'saved', 'primary'), (1, 'saved', 'alternate'),
                               (4, 'baseline', 'primary'), (5, 'baseline', 'alternate')):
        row = headers['headers'][index]
        path = HEADER_OUT / ('h' + str(index) + '.bin')
        body = bound_read(path, {'bytes': 512, 'sha256': row['sha256']}, metadata)
        relative = 1024 if copy == 'primary' else ROOT_BYTES - 1024
        decoded = decode_header(body, image, 'iOSRoot', copy, ROOT_START_SECTORS * SECTOR_BYTES + relative, ROOT_SECTORS)
        require(row == decoded and decoded['geometry_matches_frozen_expectation'] is True and
                decoded['journaled_bit13'] is True and decoded['runtime_inconsistent_bit14'] is False and
                (copy != 'primary' or (decoded['clean_unmount_bit8'] is True and decoded['boot_inconsistent_bit11'] is False)) and
                (copy != 'alternate' or decoded['boot_inconsistent_bit11'] is True),
                'retained root header differs from the exact observed boundary')
        command = headers['tool_commands'][index]
        offset = decoded['virtual_offset']
        require(command.get('command') == [headers['tool']['path'], 'dd', '-f', 'qcow2', '-O', 'raw', 'bs=512',
                    'count=' + str(offset // 512 + 1), 'skip=' + str(offset // 512),
                    'if=' + images[0 if image == 'saved' else 1], 'of=' + str(path)] and
                command.get('reaped') is True and command.get('forced') is False and command.get('exit_code') == 0 and
                not command.get('cleanup_error'), 'retained root header was read from a different image or range')
        root_rows[(image, copy)], root_bodies[(image, copy)] = decoded, body
    require(all(root_bodies[('saved', copy)] == root_bodies[('baseline', copy)] for copy in ('primary', 'alternate')),
            'corresponding retained root headers differ')
    layouts = []
    for image in ('saved', 'baseline'):
        primary, alternate = (root_rows[(image, copy)] for copy in ('primary', 'alternate'))
        require(all(primary[k] == alternate[k] for k in ('block_bytes', 'total_blocks', 'journal_info_block', 'volume_id_sha256')),
                'retained root header geometry disagrees')
        offset = root_offset(primary['block_bytes'], primary['journal_info_block'])
        layouts.append({'image': image, 'volume_offset': ROOT_START_SECTORS * SECTOR_BYTES,
                        'volume_bytes': ROOT_BYTES, 'block_bytes': primary['block_bytes'],
                        'jib_block': primary['journal_info_block'], 'virtual_offset': offset, 'bytes': BLOCK_BYTES})
    return layouts


def read_plan(images, layouts, tool, out=OUT):
    require(len(images) == len(layouts) == 2 and [row.get('image') for row in layouts] == ['saved', 'baseline'],
            'exact saved and baseline JIB scope required')
    require(images[0] != images[1], 'distinct saved and baseline images required')
    plan = []
    for image_index, (image, layout) in enumerate(zip(images, layouts)):
        require(layout == {'image': 'saved' if image_index == 0 else 'baseline',
                          'volume_offset': ROOT_START_SECTORS * SECTOR_BYTES, 'volume_bytes': ROOT_BYTES,
                          'block_bytes': BLOCK_BYTES, 'jib_block': EXPECTED_JIB_BLOCK,
                          'virtual_offset': root_offset(layout.get('block_bytes'), layout.get('jib_block')), 'bytes': BLOCK_BYTES},
                'fixed derived JIB layout differs')
        for sector in range(BLOCK_BYTES // SECTOR_BYTES):
            offset = layout['virtual_offset'] + sector * SECTOR_BYTES
            require(layout['virtual_offset'] <= offset and offset + SECTOR_BYTES <= layout['virtual_offset'] + BLOCK_BYTES,
                    'sector outside bound JIB')
            label = ('s' if image_index == 0 else 'b') + str(sector)
            target = out / (label + '.bin')
            skip = offset // SECTOR_BYTES
            plan.append({'label': label, 'image': layout['image'], 'sector_index': sector,
                         'virtual_offset': offset, 'output': str(target),
                         'command': [str(tool), 'dd', '-f', 'qcow2', '-O', 'raw', 'bs=512',
                                     'count=' + str(skip + 1), 'skip=' + str(skip), 'if=' + str(image), 'of=' + str(target)]})
    require(len(plan) == LIMITS['tool_calls'], 'fixed read plan is incomplete')
    return plan


def assemble_jib(sectors):
    require(type(sectors) is list and len(sectors) == BLOCK_BYTES // SECTOR_BYTES and
            all(type(body) is bytes and len(body) == SECTOR_BYTES for body in sectors),
            'exact eight ordered 512-byte sectors required')
    return b''.join(sectors)


def decode_jib(body, layout):
    require(type(body) is bytes and len(body) == BLOCK_BYTES, 'exact 4096-byte JIB required')
    require(layout.get('image') in ('saved', 'baseline') and layout.get('bytes') == BLOCK_BYTES and
            layout.get('virtual_offset') == root_offset(layout.get('block_bytes'), layout.get('jib_block')) and
            layout.get('volume_offset') == ROOT_START_SECTORS * SECTOR_BYTES and layout.get('volume_bytes') == ROOT_BYTES,
            'decoded JIB layout differs')
    flags = struct.unpack_from('>I', body, 0)[0]
    offset, size = struct.unpack_from('>QQ', body, 36)
    require(flags in (1, 5), 'JIB flags differ from the prior observed guest boundary')
    require(size == 8 << 20 and offset % BLOCK_BYTES == 0 and BLOCK_BYTES <= offset < offset + size <= ROOT_BYTES - BLOCK_BYTES,
            'JIB journal range differs from the prior observed guest boundary')
    return {'image': layout['image'], 'virtual_offset': layout['virtual_offset'], 'jib_block': layout['jib_block'],
            'bytes': len(body), 'sha256': sha(body), 'flags': flags, 'flags_hex': '0x%08x' % flags,
            'journal_offset': offset, 'journal_bytes': size}


def compare_jibs(saved, baseline, range_limit=128):
    require(type(saved) is type(baseline) is bytes and len(saved) == len(baseline) == BLOCK_BYTES,
            'two exact 4096-byte JIBs required')
    require(type(range_limit) is int and 1 <= range_limit <= LIMITS['difference_ranges'], 'invalid difference range bound')
    ranges, count, differing, start = [], 0, 0, None
    for offset in range(BLOCK_BYTES + 1):
        changed = offset < BLOCK_BYTES and saved[offset] != baseline[offset]
        if changed:
            differing += 1
            if start is None:
                start = offset
        elif start is not None:
            count += 1
            if len(ranges) < range_limit:
                ranges.append({'start': start, 'end': offset})
            start = None
    return {'equal': differing == 0, 'differing_bytes': differing, 'range_count': count,
            'ranges': ranges, 'range_limit': range_limit, 'omitted_ranges': count - len(ranges),
            'ranges_truncated': count > len(ranges), 'offset_convention': 'JIB-relative half-open intervals',
            'raw_byte_values_exported': False, 'difference_classified_as_safe': False}


def verify_preservation(prep, tooling, images, before, metadata):
    require([prep.cold.readonly_identity(path) for path in images] == before, 'disk identity changed during diagnostic')
    for name, pin in metadata.items():
        require(sha(small_read(Path(name))) == pin, 'bound metadata/source changed during diagnostic')
    prep.verify_tools(tooling, TOOL_MANIFEST_SHA)


def verify_capability(tool, metadata):
    body = bound_read(CAPABILITY_RESULT, CAPABILITY_PIN, metadata)
    capability = json.loads(body)
    expected = [[str(tool), 'dd', '--help'], [str(tool), 'dd', '-f', 'raw', '-O', 'raw', 'bs=512', 'count=3', 'skip=2',
                'if=' + str(CAPABILITY_RESULT.parent / 'sample.input'), 'of=' + str(CAPABILITY_RESULT.parent / 'sample.output')]]
    require(capability.get('schema') == 1 and capability.get('kind') == 'native_qemu_img_read_capability_probe' and
            capability.get('status') == 'QEMU_IMG_READ_CAPABILITY_PASSED' and capability.get('source_sha256') == CAPABILITY_SOURCE_SHA256 and
            capability.get('tool') == {'path': str(tool), **TOOL_PIN} and capability.get('tooling_manifest_sha256') == TOOL_MANIFEST_SHA and
            capability.get('bound_tooling_and_session_unchanged') is True and capability.get('expected_bytes_match') is True and
            capability.get('input_unchanged') is True and capability.get('synthetic_input_bytes') == 2048 and
            capability.get('expected_output_sha256') == capability.get('actual_output_sha256') == sha(bytes([51]) * 512) and
            capability.get('skip_blocks') == 2 and capability.get('count_blocks') == 3 and
            capability.get('count_semantics') == 'input_limit_before_skip' and
            capability.get('block_bytes') == capability.get('output_bytes') == 512 and
            capability.get('existing_disk_images_opened') is False and capability.get('guest_vm_started') is False and
            capability.get('error') is None and not capability.get('preservation_error') and
            [row.get('command') for row in capability.get('tool_commands', [])] == expected and
            all(row.get('reaped') is True and row.get('forced') is False and row.get('exit_code') == 0 and
                not row.get('cleanup_error') for row in capability['tool_commands']),
            'actual 512-byte capability proof differs')


def prepare_images(m, inspected, metadata):
    session = m.read_json(m.PREP / 'session.json')
    guard_body = small_read(m.GUARD_SOURCE)
    require(sha(guard_body) == m.SOURCE_HASHES[m.GUARD_SOURCE], 'exact guard bytes differ before compile')
    metadata[str(m.GUARD_SOURCE)] = sha(guard_body)
    guard = module(guard_body, m.GUARD_SOURCE, 'verified_frozen_guard_for_jib')
    prep = guard.load_frozen(m.RUNNER, session['runner_sources'])
    tooling = m.canonical(Path(session['tooling']))
    require(session['tooling_manifest_sha256'] == TOOL_MANIFEST_SHA, 'bound tooling manifest differs')
    manifest = prep.verify_tools(tooling, TOOL_MANIFEST_SHA)
    require(manifest['files']['tools/qemu-img']['bytes'] == TOOL_PIN['bytes'] and
            manifest['files']['tools/qemu-img']['sha256'] == TOOL_PIN['sha256'], 'qualified qemu-img pin differs')
    tool = tooling / 'tools/qemu-img'
    verify_capability(tool, metadata)
    chain = inspected['backing_chain']
    require(type(chain) is list and len(chain) == 2, 'exact saved and baseline backing chain required')
    images = [m.canonical(Path(row['identity']['path'])) for row in chain]
    require(all(path.is_relative_to(m.PREP) for path in images) and images[0] != images[1], 'unexpected saved or baseline path')
    require([row['path'] for row in prep.cold.qcow_chain(images[0])] == [str(path) for path in images] and
            [row['path'] for row in prep.cold.qcow_chain(images[1])] == [str(images[1])], 'backing graph differs')
    before = [prep.cold.readonly_identity(path) for path in images]
    require(before == [row['identity'] for row in chain], 'image identity differs from the inspected full chain')
    metadata[str(tooling / 'tooling-manifest.json')] = TOOL_MANIFEST_SHA
    return prep, tooling, tool, images, before


def extract_jibs(m, plan, layouts, env, tool_rows):
    require([(row.get('image'), row.get('sector_index')) for row in plan] ==
            [(image, sector) for image in ('saved', 'baseline') for sector in range(8)],
            'fixed extraction order differs')
    payloads, decoded = [], []
    for image_index, layout in enumerate(layouts):
        sectors = []
        for row in plan[image_index * 8:(image_index + 1) * 8]:
            target = Path(row['output'])
            require(target == OUT / (row['label'] + '.bin') and not os.path.lexists(target),
                    'fresh fixed sector output required')
            m.resources()
            run_tool(row['label'], row['command'], env, tool_rows)
            body = small_read(target, SECTOR_BYTES)
            require(len(body) == SECTOR_BYTES, 'short JIB sector extraction')
            sectors.append(body)
        payload = assemble_jib(sectors)
        save(layout['image'] + '-jib.bin', payload)
        decoded.append(decode_jib(payload, layout))
        payloads.append(payload)
    require(len(payloads) == 2 and len(tool_rows) == LIMITS['tool_calls'] and
            all(row.get('reaped') is True and row.get('forced') is False and row.get('exit_code') == 0 and
                not row.get('cleanup_error') for row in tool_rows), 'fixed extraction or clean owned-child completion missing')
    return payloads, decoded


def main():
    m = load_bound_owner()
    require(not os.path.lexists(OUT), 'preserve existing JIB diagnostic output')
    locks, created = [], False
    result = {'schema': 1, 'kind': 'readonly_root_jib_diagnostic', 'status': 'INCOMPLETE',
              'diagnostic_only': True, 'inspection_success_claimed': False, 'difference_classified_as_safe': False,
              'guest_vm_started': False, 'fsck_run': False, 'mounted': False, 'replayed': False, 'repaired': False,
              'journal_pointer_followed': False, 'raw_bytes_exported': False, 'full_disk_hashes_recomputed': False,
              'tool_commands': [], 'jibs': [], 'comparison': None, 'error': None}
    metadata, before, prep, images, tooling = None, None, None, None, None
    try:
        for path in (m.PREP / 'owner.lock', m.WORK / 'owner.lock'):
            m.canonical(path)
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            locks.append(fd)
            require(stat.S_ISREG(os.fstat(fd).st_mode), 'nonordinary existing ownership lock')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _, inspected, metadata = check_metadata(m)
        m.refuse_live_children()
        layouts = load_header_layouts(m, metadata)
        prep, tooling, tool, images, before = prepare_images(m, inspected, metadata)
        plan = read_plan(images, layouts, tool, OUT)
        own_source = small_read(DIAGNOSTIC_SOURCE, 64 << 10)
        metadata[str(DIAGNOSTIC_SOURCE)] = sha(own_source)
        m.resources()
        OUT.mkdir(mode=0o700)
        created = True
        result.update(started_utc=m.utc(), owner=m.identity(os.getpid()),
                      source={'path': str(DIAGNOSTIC_SOURCE), 'bytes': len(own_source), 'sha256': sha(own_source)},
                      tool={'path': str(tool), **TOOL_PIN}, limits=LIMITS, root_layouts=layouts,
                      actual_failed_inspection_pins=9,
                      previous_full_hash_records=[row['record'] for row in inspected['backing_chain']],
                      capability={'path': str(CAPABILITY_RESULT), **CAPABILITY_PIN, 'passed': True})
        require(result['owner'] is not None, 'diagnostic owner identity unavailable')
        save_json('session.json', {'schema': 1, 'diagnostic_only': True, 'metadata_sha256': metadata,
                                  'disk_identities': before, 'root_layouts': layouts,
                                  'limits': LIMITS, 'tool': result['tool'], 'read_plan': plan})
        env = {'PATH': '/system/bin', 'LD_LIBRARY_PATH': str(tooling / 'lib'), 'TMPDIR': str(OUT), 'LANG': 'C', 'LC_ALL': 'C'}
        payloads, result['jibs'] = extract_jibs(m, plan, layouts, env, result['tool_commands'])
        result['comparison'] = compare_jibs(payloads[0], payloads[1], LIMITS['difference_ranges'])
        result['status'] = 'READONLY_ROOT_JIB_COMPARISON_OBSERVED'
    except BaseException as error:
        result['error'] = type(error).__name__ + ': ' + str(error)
    finally:
        if created:
            try:
                verify_preservation(prep, tooling, images, before, metadata)
                for identity, label, key in ((EXPECTED_WRAPPER, 'resume4 owner', 'starttime'),
                                             (EXPECTED_INSPECTOR, 'resume4 inspector', 'starttime'),
                                             (EXPECTED_QEMU, 'resume4 QEMU', 'start_ticks'),
                                             (EXPECTED_OBSERVER, 'resume4 observer', 'start_ticks')):
                    m.absent(identity, label, key)
                result['disk_identities_unchanged'] = True
                result['bound_metadata_unchanged'] = True
                result['bound_tooling_unchanged'] = True
                result['recorded_inspection_processes_absent'] = True
            except BaseException as error:
                result['status'] = 'INCOMPLETE'
                result['preservation_error'] = type(error).__name__ + ': ' + str(error)
            result['finished_utc'] = m.utc()
            save_json('result.json', result)
        for fd in reversed(locks):
            os.close(fd)
    if created:
        body = small_read(OUT / 'result.json', LIMITS['result_bytes'])
        print(json.dumps({'schema': 1, 'status': result['status'], 'diagnostic_only': True, 'observed_utc': m.utc(),
                          'result': {'path': str(OUT / 'result.json'), 'bytes': len(body), 'sha256': sha(body),
                                     'digest_bytes': list(hashlib.sha256(body).digest())},
                          'jibs': result['jibs'], 'comparison': result['comparison'],
                          'tool_commands': len(result['tool_commands']),
                          'all_own_tool_children_reaped': all(row['reaped'] for row in result['tool_commands']),
                          'forced_tool_children': [row['pid'] for row in result['tool_commands'] if row['forced']],
                          'disk_identities_unchanged': result.get('disk_identities_unchanged'),
                          'bound_metadata_unchanged': result.get('bound_metadata_unchanged'),
                          'bound_tooling_unchanged': result.get('bound_tooling_unchanged'),
                          'full_disk_hashes_recomputed': False, 'inspection_success_claimed': False,
                          'difference_classified_as_safe': False, 'raw_bytes_exported': False,
                          'error': result.get('error'), 'preservation_error': result.get('preservation_error')},
                         separators=(',', ':')), flush=True)
    else:
        print(json.dumps({'schema': 1, 'status': 'ROOT_JIB_DIAGNOSTIC_REFUSED', 'diagnostic_only': True,
                          'error': result['error'], 'existing_files_unchanged': True}, separators=(',', ':')), flush=True)
    return 0 if result['status'] == 'READONLY_ROOT_JIB_COMPARISON_OBSERVED' else 2


if __name__ == '__main__':
    raise SystemExit(main())


