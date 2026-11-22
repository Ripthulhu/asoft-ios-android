#!/usr/bin/env python3
"""Bounded read-only Data journal diagnosis after the actual resume5 refusal.

Read only the two pinned Data volume headers, one 4096-byte JIB and the whole
8 MiB in-volume journal through the exact native qemu-img. No guest VM, fsck,
mount, replay, repair, parent image write, acceptance change or raw export.
Backings retain their prior full-hash records plus fresh before/after stable
identities; this diagnostic does not recompute whole-image hashes.
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
import time
import types

BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
OWNER_SOURCE = BASE / 'run-ios26-saved-inspection-resume5.py'
OWNER_SOURCE_PIN = {'bytes': 60564, 'sha256': 'dbb570dc9b3354a5d7c4eb218883ab22f25afe24757c429e46cc7c04de1baa63'}
DIAGNOSTIC_SOURCE = BASE / 'run-ios26-data-journal-diagnostic-resume5.py'
PARSER_SOURCE = BASE / 'parse-ios26-data-journal-resume5.py'
PARSER_SOURCE_PIN = None  # Bound only after the independent pure-parser review.
OUT = BASE / 'ios26-data-journal-diagnostic-resume5'
OWNER = BASE / 'ios26-saved-inspection-resume5-owner'
WORK = Path('/data/local/tmp/pixel-saved-audit-e9cc754-resume5')
MONITOR = BASE / 'ios26-saved-inspection-resume5-observer-procstat1'
MONITOR_SOURCE = BASE / 'run-ios26-saved-inspection-resume5-observer-procstat1.py'
MONITOR_SOURCE_PIN = {'bytes': 37877, 'sha256': '478b8b9179443ae3b60e921bd65933cd64a0cd1c209bf9e8327c541fe72f65de'}
PREFLIGHT_PIN = {'bytes': 9069, 'sha256': '4630b5dc921d3bee52d4805cc829e3624144b763d27b53937443e43c69db44f6'}
HEADER_SOURCE = BASE / 'run-ios26-hfs-header-diagnostic-resume2.py'
HEADER_SOURCE_PIN = {'bytes': 22740, 'sha256': 'e79c0fbc472ae2a875164565802feffc4fad0a630571970f6e68d7251801bdcd'}
HEADER_OUT = BASE / 'ios26-hfs-header-diagnostic-resume2'
HEADER_RESULT_PIN = {'bytes': 14542, 'sha256': 'd768516e7cc9846e35aefa5f7583797b4cc0c129402a16994965501c69882ba6'}
TOOL_PIN = {'bytes': 2356032, 'sha256': '1bd2fd6b968c492d0263436c260af2a8c2ee807cf4afd4fd2abb3300446e2440'}
TOOL_MANIFEST_SHA = 'a5461ecf2e41d4966f783dfca620d3d700f9aa1bc76dd5fa745ec54666e764b2'
CAPABILITY_RESULT = BASE / 'ios26-hfs-header-capability-resume4/result.json'
CAPABILITY_PIN = {'bytes': 2659, 'sha256': '897cb1faaab342ff576fcc8a3e8d958282f0d44fd0162c445457853cf1d8c11c'}
CAPABILITY_SOURCE_SHA256 = '4264533ff68a0a116aeecbe140de041b1f02b5036f9bf83783d2f4958f1ece8f'
EXPECTED_WRAPPER = {'pid': 3218, 'starttime': 10596300}
EXPECTED_INSPECTOR = {'pid': 3219, 'starttime': 10596334}
EXPECTED_QEMU = {'pid': 4784, 'start_ticks': 10606734}
EXPECTED_OBSERVER = {'pid': 31097, 'start_ticks': 10563710}
EXPECTED_ERROR = 'ValueError: guest inspection incomplete; retained metadata classifies the boundary'
DATA_START_SECTORS = 67110912
DATA_SECTORS = 33554432
SECTOR_BYTES = 512
BLOCK_BYTES = 4096
DATA_BASE = DATA_START_SECTORS * SECTOR_BYTES
DATA_BYTES = DATA_SECTORS * SECTOR_BYTES
DISK_BYTES = 51541704704
EXPECTED_JIB_BLOCK = 129
EXPECTED_JIB_RELATIVE = EXPECTED_JIB_BLOCK * BLOCK_BYTES
EXPECTED_JOURNAL_RELATIVE = EXPECTED_JIB_RELATIVE + BLOCK_BYTES
JOURNAL_BYTES = 8 << 20
EXPECTED_DATA_HEADER_SHA256 = 'f9bd83c96acbaba80a2d24b09731ef6f39ae78cc922cbca9d65c774716c2a66f'
LIMITS = {'tool_seconds': 60, 'cleanup_seconds': 5, 'tool_cpu_seconds': 30,
          'min_available_mib': 2816, 'min_free_mib': 1536, 'tool_output_bytes': 64 << 10,
          'tool_file_bytes': 8 << 20, 'tool_calls': 4, 'headers': 2, 'header_bytes': 512,
          'jib_bytes': 4096, 'journal_bytes': 8388608, 'result_bytes': 128 << 10}
RECEIPT_PINS = {'/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume5-observer-procstat1/events.jsonl': {'bytes': 18872,
                                                                                                                'sha256': '5190b81b28170fc749b4caa2b40938213b597280746067dab2eaf318fc5aea0d'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume5-observer-procstat1/exit.json': {'bytes': 479,
                                                                                                             'sha256': '1b4bcab1312eaa029d1466dcd4051aaa61a457ad70cd143949fecaf2aba636bf'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume5-observer-procstat1/ready.json': {'bytes': 3841,
                                                                                                              'sha256': '7e22ccf73c349f9c396a54cba434ec98a93fef0a44028a0856f3ebfd39be5f51'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume5-observer-procstat1/summary.json': {'bytes': 12385,
                                                                                                                'sha256': '46cb269e513b4242957b7b2f31fd354c13d7748d38f6cc3f44f302833e9355fe'},
 '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume5-owner/exit.json': {'bytes': 905,
                                                                                                'sha256': '9fd323cb4ce95cd7d60fd4e975b9bfe93d4bddddb2bfacc8ffbf50d87eae9e5c'},
 '/data/local/tmp/pixel-saved-audit-e9cc754-resume5/a1/expected-policy.json': {'bytes': 271,
                                                                               'sha256': '1df83dee3f68a036283f1a3a8ed8b173bc443ee06dbaf1df0eb30e41308ef135'},
 '/data/local/tmp/pixel-saved-audit-e9cc754-resume5/a1/files/inspection/result.json': {'bytes': 5335,
                                                                                       'sha256': 'd2b1d1b1648192c31efac3dc690d5aee4e1cd70f92c3afba0932599175d06741'},
 '/data/local/tmp/pixel-saved-audit-e9cc754-resume5/a1/vm-result.json': {'bytes': 1266,
                                                                         'sha256': '0f4a71f0b51fbbb89834419a22737bc7c9230335ccc84bf8ac30bdc60879cb49'},
 '/data/local/tmp/pixel-saved-audit-e9cc754-resume5/result.json': {'bytes': 7269,
                                                                   'sha256': '08ab06ea5b0e1d46a168935df1dbaabeda0daa7ab569b1e001f61e17d7cfc828'}}


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
        resource.setrlimit(resource.RLIMIT_FSIZE, (LIMITS['tool_file_bytes'], LIMITS['tool_file_bytes']))
        resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    row = {'label': label, 'command': command, 'pid': None, 'exit_code': None, 'reaped': False, 'forced': False}
    save_json(label + '.command.json', row)
    child = None
    try:
        with os.fdopen(os.open(OUT / (label + '.stdout'), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
            child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
                                     env=env, close_fds=True, start_new_session=True, preexec_fn=child_limits)
            row['pid'] = child.pid
            deadline = time.monotonic() + LIMITS['tool_seconds']
            while child.poll() is None:
                if time.monotonic() >= deadline or os.fstat(stream.fileno()).st_size > LIMITS['tool_output_bytes']:
                    row['forced'] = True
                    child.kill()  # This exact unreaped child only; never an inspection process.
                    break
                time.sleep(0.05)
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


def check_metadata(m):
    """Validate current resume5 evidence separately from the preserved resume2 set."""
    expected = {str(OWNER / 'exit.json'), str(WORK / 'result.json'), str(WORK / 'a1/vm-result.json'),
                str(WORK / 'a1/files/inspection/result.json'), str(WORK / 'a1/expected-policy.json'),
                *(str(MONITOR / name) for name in ('ready.json', 'exit.json', 'summary.json', 'events.jsonl'))}
    require(set(RECEIPT_PINS) == expected, 'exact nine observed resume5 receipt paths required')
    metadata, cached = {}, {}
    for name, pin in RECEIPT_PINS.items():
        cached[name] = bound_read(Path(name), pin, metadata)
    bound_read(OWNER_SOURCE, OWNER_SOURCE_PIN, metadata)
    bound_read(MONITOR_SOURCE, MONITOR_SOURCE_PIN, metadata)
    public_body = bound_read(OWNER / 'preflight.json', PREFLIGHT_PIN, metadata)
    public = json.loads(public_body)
    current = m.read_json(OWNER / 'prerequisites.json')
    m.validate_preflight(public, current)
    for historical in (m.previous_failure_inputs(), m.resume2_failure_inputs(), m.resume4_failure_inputs()):
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
            'actual resume5 failed owner differs')
    for name in ('wrapper', 'runner'):
        m.absent(startup[name], 'completed resume5 ' + name)
    qemu = m.read_json(WORK / 'a1/vm.child.json')
    require(qemu == EXPECTED_QEMU, 'actual resume5 QEMU identity differs')
    m.absent(qemu, 'completed resume5 QEMU', 'start_ticks')
    result_body = cached[str(WORK / 'result.json')]
    require(result_body == small_read(WORK / 'a1/inspection-result.json'), 'returned host results disagree')
    result = json.loads(result_body)
    guest = json.loads(cached[str(WORK / 'a1/files/inspection/result.json')])
    policy = json.loads(cached[str(WORK / 'a1/expected-policy.json')])
    require(result.get('schema') == 1 and result.get('status') == 'INCOMPLETE' and result.get('error') == EXPECTED_ERROR and
            result.get('full_backing_chain_unchanged') is True and result.get('preparation_and_guard_unchanged') is True and
            result.get('identity_error') is None and result.get('guest_result') == guest and
            all(result.get(k) is False for k in ('boot_complete', 'gpu_path_complete', 'app_gate_changed')),
            'actual resume5 host failure boundary differs')
    require(guest.get('schema') == 1 and guest.get('kind') == 'ios26_saved_firstboot_inspection' and
            guest.get('status') == 'INCOMPLETE' and guest.get('readonly_attachments') is True and
            all(guest.get(k) is False for k in ('mounted', 'replayed', 'repaired', 'boot_complete', 'gpu_path_complete')) and
            guest.get('errors') == [{'code': 'nonempty_journal'}] and guest.get('cleanup_errors') == [] and
            guest.get('fsck') == {}, 'actual Data journal refusal differs')
    validate_failed_journals(guest.get('journals'))
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
    m.absent(EXPECTED_OBSERVER, 'completed resume5 independent observer', 'start_ticks')
    inspected = m.read_json(WORK / 'inspection-session.json')
    require(m.digest(inspected) == result.get('inspection_session_sha256') and
            inspected == public.get('inspection_session'), 'actual inspection and accepted preflight sessions differ')
    for path in (OWNER / 'owner.json', OWNER / 'command.json', OWNER / 'prerequisites.json',
                 WORK / 'inspection-session.json', WORK / 'a1/vm.child.json', WORK / 'a1/inspection-result.json'):
        metadata[str(path)] = sha(small_read(path))
    return current, inspected, metadata


def verify_preservation(prep, tooling, images, before, metadata):
    require([stable_image_identity(path) for path in images] == before, 'disk identity changed during diagnostic')
    require([row['path'] for row in prep.cold.qcow_chain(images[0])] == [str(path) for path in images] and
            [row['path'] for row in prep.cold.qcow_chain(images[1])] == [str(images[1])],
            'backing graph changed during diagnostic')
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
    guard = module(guard_body, m.GUARD_SOURCE, 'verified_frozen_guard_for_data_journal')
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
    before = [stable_image_identity(path) for path in images]
    require(before == [row['identity'] for row in chain], 'image identity differs from the inspected full chain')
    metadata[str(tooling / 'tooling-manifest.json')] = TOOL_MANIFEST_SHA
    return prep, tooling, tool, images, before


def require_finalized():
    require(type(PARSER_SOURCE_PIN) is dict and set(PARSER_SOURCE_PIN) == {'bytes', 'sha256'} and
            type(PARSER_SOURCE_PIN['bytes']) is int and 0 < PARSER_SOURCE_PIN['bytes'] <= 128 << 10 and
            type(PARSER_SOURCE_PIN['sha256']) is str and
            re.fullmatch('[0-9a-f]{64}', PARSER_SOURCE_PIN['sha256']),
            'UNRELEASED: reviewed pure parser source is not bound')
    require(type(EXPECTED_DATA_HEADER_SHA256) is str and
            re.fullmatch('[0-9a-f]{64}', EXPECTED_DATA_HEADER_SHA256),
            'UNRELEASED: actual failed Data header is not bound')


def load_bound_owner():
    require_finalized()
    require(os.geteuid() == 0 and BASE.resolve(strict=True) == BASE, 'root and canonical base required')
    body = bound_read(OWNER_SOURCE, OWNER_SOURCE_PIN, {})
    m = module(body, OWNER_SOURCE, 'verified_resume5_saved_inspection_owner')
    require(m.OWNER == OWNER and m.WORK == WORK and m.BASE == BASE and
            m.INSPECTOR == Path('/data/local/tmp/pixel-saved-checks-resume5') and
            m.HEADER_SOURCE == HEADER_SOURCE and m.HEADER_WORK == HEADER_OUT,
            'current owner or preserved header scope differs')
    return m


def expected_data_metadata():
    return {'endian': 'little', 'magic': 0x4A4E4C78, 'endian_marker': 0x12345678,
            'start': 512, 'end': 614400, 'bytes': JOURNAL_BYTES, 'block_header_bytes': 49152,
            'header_bytes': 512, 'checksum': 195764962, 'computed_checksum': 195764962,
            'checksum_bytes': 44, 'header_sha256': EXPECTED_DATA_HEADER_SHA256}


def validate_failed_journals(journals):
    require(type(journals) is dict and set(journals) == {'iOSRoot', 'Data'},
            'actual failed journal inventory differs')
    root = journals['iOSRoot']
    require(type(root) is dict and root.get('status') == 'PASSED' and
            root.get('header_classification', {}).get('state') == 'ROOT_AUTHORED_NEEDINIT_TO_INITIALIZED_EMPTY' and
            root.get('journal', {}).get('status') == 'PASSED' and
            root['journal'].get('state') == 'INITIALIZED_EMPTY' and
            root['journal'].get('start') == root['journal'].get('end') == 512,
            'actual retained root metadata classification differs')
    require(journals['Data'] == {'status': 'INCOMPLETE', 'code': 'nonempty_journal',
                                 'metadata': expected_data_metadata()},
            'actual retained Data nonempty-journal boundary differs')


def stable_image_identity(path):
    """The old identity schema, with a stable no-follow descriptor read."""
    require(path.resolve(strict=True) == path, 'noncanonical backing-chain member')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        a = os.fstat(stream.fileno())
        require(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and a.st_size >= 65536,
                'nonordinary backing-chain member')
        header = stream.read(65536)
        b = os.fstat(stream.fileno())
    require(len(header) == 65536 and
            (a.st_dev, a.st_ino, a.st_size, a.st_mtime_ns, a.st_ctime_ns) ==
            (b.st_dev, b.st_ino, b.st_size, b.st_mtime_ns, b.st_ctime_ns),
            'backing-chain identity changed during observation')
    return {'path': str(path), 'device': a.st_dev, 'inode': a.st_ino, 'bytes': a.st_size,
            'mtime_ns': a.st_mtime_ns, 'ctime_ns': a.st_ctime_ns, 'first_64k_sha256': sha(header)}


def load_data_layout(m, metadata):
    """Bind current Data geometry to the retained exact eight-header diagnostic."""
    bound_read(HEADER_SOURCE, HEADER_SOURCE_PIN, metadata)
    headers = json.loads(bound_read(HEADER_OUT / 'result.json', HEADER_RESULT_PIN, metadata))
    require(headers.get('status') == 'READONLY_HFS_HEADERS_OBSERVED' and
            headers.get('source') == {'path': str(HEADER_SOURCE), **HEADER_SOURCE_PIN} and
            len(headers.get('headers', [])) == len(headers.get('tool_commands', [])) == 8,
            'preserved header result differs')
    session_path = WORK / 'inspection-session.json'
    session_body = small_read(session_path)
    require(metadata.get(str(session_path)) == sha(session_body), 'current inspection session changed before Data derivation')
    chain = json.loads(session_body).get('backing_chain')
    require(type(chain) is list and len(chain) == 2 and
            headers.get('previous_full_hash_records') == [row['record'] for row in chain],
            'retained headers and current inspected image records differ')
    image = str(Path(chain[0]['identity']['path']))
    rows, bodies = [], []
    for index, copy in ((2, 'primary'), (3, 'alternate')):
        row = headers['headers'][index]
        path = HEADER_OUT / ('h' + str(index) + '.bin')
        body = bound_read(path, {'bytes': SECTOR_BYTES, 'sha256': row['sha256']}, metadata)
        relative = 1024 if copy == 'primary' else DATA_BYTES - 1024
        decoded = decode_header(body, 'saved', 'Data', copy, DATA_BASE + relative, DATA_SECTORS)
        require(row == decoded and decoded['geometry_matches_frozen_expectation'] is True and
                decoded['journaled_bit13'] is True and decoded['runtime_inconsistent_bit14'] is False and
                decoded['boot_inconsistent_bit11'] is False and
                decoded['journal_info_block'] == EXPECTED_JIB_BLOCK and
                decoded['attributes'] == (0x80002000 if copy == 'primary' else 0x80002100),
                'retained Data header differs from the exact observed boundary')
        offset = decoded['virtual_offset']
        command = headers['tool_commands'][index]
        require(command.get('command') == [headers['tool']['path'], 'dd', '-f', 'qcow2', '-O', 'raw', 'bs=512',
                    'count=' + str(offset // 512 + 1), 'skip=' + str(offset // 512),
                    'if=' + image, 'of=' + str(path)] and
                command.get('reaped') is True and command.get('forced') is False and command.get('exit_code') == 0 and
                not command.get('cleanup_error'), 'retained Data header was read from a different image or range')
        rows.append(decoded)
        bodies.append(body)
    require(all(rows[0][key] == rows[1][key] for key in
                ('block_bytes', 'total_blocks', 'journal_info_block', 'volume_id_sha256')),
            'retained Data header geometry disagrees')
    layout = {'volume': 'Data', 'volume_offset': DATA_BASE, 'volume_bytes': DATA_BYTES,
              'block_bytes': BLOCK_BYTES, 'jib_block': EXPECTED_JIB_BLOCK,
              'jib_relative_offset': EXPECTED_JIB_RELATIVE, 'jib_bytes': BLOCK_BYTES,
              'journal_relative_offset': EXPECTED_JOURNAL_RELATIVE, 'journal_bytes': JOURNAL_BYTES,
              'primary_header_sha256': sha(bodies[0]), 'alternate_header_sha256': sha(bodies[1])}
    return layout, bodies


def read_plan(images, layout, tool, out=OUT):
    require(type(images) is list and len(images) == 2 and images[0] != images[1],
            'exact distinct saved and baseline images required')
    expected = {'volume': 'Data', 'volume_offset': DATA_BASE, 'volume_bytes': DATA_BYTES,
                'block_bytes': BLOCK_BYTES, 'jib_block': EXPECTED_JIB_BLOCK,
                'jib_relative_offset': EXPECTED_JIB_RELATIVE, 'jib_bytes': BLOCK_BYTES,
                'journal_relative_offset': EXPECTED_JOURNAL_RELATIVE, 'journal_bytes': JOURNAL_BYTES}
    require(type(layout) is dict and set(layout) == set(expected) | {'primary_header_sha256', 'alternate_header_sha256'} and
            all(type(layout[key]) is type(value) and layout[key] == value for key, value in expected.items()) and
            all(type(layout[key]) is str and re.fullmatch('[0-9a-f]{64}', layout[key]) for key in
                ('primary_header_sha256', 'alternate_header_sha256')), 'fixed Data layout differs')
    plan = []
    for label, relative, size in (('primary', 1024, 512), ('alternate', DATA_BYTES - 1024, 512),
                                  ('jib', EXPECTED_JIB_RELATIVE, BLOCK_BYTES),
                                  ('journal', EXPECTED_JOURNAL_RELATIVE, JOURNAL_BYTES)):
        offset = DATA_BASE + relative
        require(offset % 512 == size % 512 == 0 and DATA_BASE <= offset < offset + size <= DATA_BASE + DATA_BYTES,
                'fixed extraction outside Data volume')
        target = out / (label + '.bin')
        skip, count = offset // 512, size // 512
        plan.append({'label': label, 'image': 'saved', 'virtual_offset': offset, 'bytes': size, 'output': str(target),
                     'command': [str(tool), 'dd', '-f', 'qcow2', '-O', 'raw', 'bs=512',
                                 'count=' + str(skip + count), 'skip=' + str(skip),
                                 'if=' + str(images[0]), 'of=' + str(target)]})
    require(len(plan) == LIMITS['tool_calls'] and sum(row['bytes'] for row in plan) == JOURNAL_BYTES + BLOCK_BYTES + 1024,
            'fixed extraction inventory differs')
    return plan


def load_checkers(m, metadata):
    guest_path = m.INSPECTOR / 'inspect_ios26_firstboot_guest.py'
    guest_body = bound_read(guest_path, m.INSPECTOR_SOURCE_PINS[guest_path.name], metadata)
    guest = module(guest_body, guest_path, 'verified_saved_inspection_geometry_helpers')
    require((guest.BLOCK, guest.SECTOR, guest.JOURNAL_BYTES) == (BLOCK_BYTES, SECTOR_BYTES, JOURNAL_BYTES),
            'pinned guest geometry differs')
    parser_body = bound_read(PARSER_SOURCE, PARSER_SOURCE_PIN, metadata)
    parser = module(parser_body, PARSER_SOURCE, 'verified_readonly_data_journal_parser')
    return guest, parser


def validate_jib(body, header_bodies, guest):
    require(len(body) == BLOCK_BYTES, 'exact 4096-byte JIB required')
    flags = struct.unpack_from('>I', body)[0]
    offset, size = struct.unpack_from('>QQ', body, 36)
    require((flags, offset, size) == (1, EXPECTED_JOURNAL_RELATIVE, JOURNAL_BYTES),
            'current Data JIB changed flags or discovery range')
    guest.no_metadata_overlap(header_bodies, EXPECTED_JIB_RELATIVE, offset, size, DATA_BYTES)
    return {'bytes': len(body), 'sha256': sha(body), 'flags': flags,
            'jib_relative_offset': EXPECTED_JIB_RELATIVE, 'journal_relative_offset': offset, 'journal_bytes': size}


def validate_journal_header(body, guest):
    require(len(body) == JOURNAL_BYTES, 'exact whole 8 MiB journal required')
    require(sha(body[:SECTOR_BYTES]) == EXPECTED_DATA_HEADER_SHA256,
            'fresh journal header differs from the actual failed inspection')
    try:
        guest.initialized_header(body[:SECTOR_BYTES], {'bytes': JOURNAL_BYTES})
    except guest.InspectionError as error:
        require(error.code == 'nonempty_journal' and error.metadata == expected_data_metadata(),
                'fresh journal header no longer matches the exact retained refusal')
    else:
        raise ValueError('fresh journal unexpectedly bypassed the retained nonempty refusal')


def extract_data(m, plan, layout, retained_headers, guest, env, tool_rows):
    require([row.get('label') for row in plan] == ['primary', 'alternate', 'jib', 'journal'],
            'fixed Data extraction order differs')
    payloads, records = {}, []
    for index, row in enumerate(plan):
        target = Path(row['output'])
        require(target == OUT / (row['label'] + '.bin') and not os.path.lexists(target),
                'fresh fixed extraction output required')
        m.resources()
        run_tool(row['label'], row['command'], env, tool_rows)
        body = small_read(target, row['bytes'])
        require(len(body) == row['bytes'], 'short fixed Data extraction')
        if index < 2:
            key = 'primary_header_sha256' if index == 0 else 'alternate_header_sha256'
            require(body == retained_headers[index] and sha(body) == layout[key],
                    'fresh Data header differs from the bound retained header')
        elif row['label'] == 'jib':
            validate_jib(body, retained_headers, guest)
        else:
            validate_journal_header(body, guest)
        payloads[row['label']] = body
        records.append({'label': row['label'], 'path': str(target), 'bytes': len(body), 'sha256': sha(body),
                        'virtual_offset': row['virtual_offset']})
    require(len(tool_rows) == LIMITS['tool_calls'] and
            all(row.get('reaped') is True and row.get('forced') is False and row.get('exit_code') == 0 and
                not row.get('cleanup_error') for row in tool_rows), 'fixed extraction or clean owned-child completion missing')
    return payloads, records


def validate_parser_analysis(value):
    """Allow only bounded diagnostic scalars, including explicit parser refusal."""
    false_flags = {'replay_performed', 'filesystem_accepted', 'inspection_accepted', 'raw_payload_exported',
                   'target_block_numbers_exported', 'entry0_pointer_followed'}
    fields = {'schema', 'kind', 'status', 'code', 'readonly', 'format', 'scope', 'checks', 'counts',
              'records', 'failure', 'limitations'} | false_flags
    require(type(value) is dict and set(value) == fields and type(value['schema']) is int and value['schema'] == 1 and
            value['kind'] == 'data_journal_structure_diagnosis' and value['readonly'] is True and
            value['format'] == 'apple_hfs_modern_nonwrapped_le_d1bac2f' and
            value['status'] in ('STRUCTURE_DIAGNOSIS_COMPLETE', 'INCOMPLETE') and
            all(value[key] is False for key in false_flags), 'parser result schema or nonacceptance boundary differs')
    scope = {'journal_bytes': 8388608, 'volume_bytes': DATA_BYTES, 'sector_bytes': 512,
             'block_list_bytes': 49152, 'active_start': 512, 'active_end': 614400, 'active_bytes': 613888,
             'entry_capacity': 3071, 'max_lists': 16, 'max_entries': 4096, 'nonwrapped_only': True}
    require(type(value['scope']) is dict and set(value['scope']) == set(scope) and
            all(type(value['scope'][key]) is type(expected) and value['scope'][key] == expected
                for key, expected in scope.items()), 'parser scope differs')
    limits = {'known_guest_kernel_source_identity': False, 'header_sequence_is_outside_header_checksum': True,
              'header_sequence_bound_to_first_or_last_transaction': False,
              'target_numbers_have_no_independent_checksum': True, 'killed_payload_checksums_evaluated': False,
              'inactive_journal_region_interpreted': False, 'transaction_replay_order_or_coalescing_evaluated': False,
              'filesystem_semantics_evaluated': False}
    require(type(value['limitations']) is dict and set(value['limitations']) == set(limits) and
            all(value['limitations'][key] is expected for key, expected in limits.items()),
            'parser limitations differ')
    checks = {'header_hash_matches', 'journal_header_checksum_valid', 'header_profile_matches',
              'complete_active_interval', 'all_list_header_checksums_valid', 'all_live_payload_checksums_valid',
              'all_live_target_ranges_valid', 'sequence_and_first_header_consistent', 'bytes_used_matches_payloads'}
    counts = {'list_headers_seen', 'list_headers_verified', 'completed_lists', 'entries_seen', 'live_entries',
              'killed_entries', 'live_target_ranges_verified', 'payload_checksums_verified', 'payload_checksums_unavailable',
              'payload_bytes_consumed', 'live_payload_bytes', 'killed_payload_bytes', 'transaction_starts',
              'continuation_lists', 'sequence_increments', 'active_bytes_consumed'}
    require(type(value['checks']) is dict and set(value['checks']) == checks and
            all(item is None or type(item) is bool for item in value['checks'].values()), 'parser check fields differ')
    require(type(value['counts']) is dict and set(value['counts']) == counts and
            all(type(item) is int and 0 <= item <= JOURNAL_BYTES for item in value['counts'].values()),
            'parser count fields differ')
    records = value['records']
    numeric = {'index', 'journal_offset', 'max_blocks', 'num_blocks', 'bytes_used', 'flags', 'live_entries',
               'killed_entries', 'payload_checksums_verified', 'payload_checksums_unavailable', 'payload_bytes_consumed'}
    boolean = {'list_header_checksum_valid', 'sequence_and_first_header_consistent', 'bytes_used_matches_payloads'}
    require(type(records) is list and len(records) <= 16, 'parser record count exceeds bound')
    for index, row in enumerate(records):
        require(type(row) is dict and set(row) == numeric | boolean | {'status'} and
                all(type(row[key]) is int and -(1 << 31) <= row[key] < (1 << 31) for key in numeric) and
                row['index'] == index and 512 <= row['journal_offset'] < 614400 and row['journal_offset'] % 512 == 0 and
                all(row[key] is None or type(row[key]) is bool for key in boolean) and
                row['status'] in ('INCOMPLETE', 'STRUCTURE_OBSERVED'), 'parser selected record schema differs')
    require(type(value['code']) is str and re.fullmatch('[a-z0-9_]{1,80}', value['code']),
            'parser code is not a fixed-format diagnostic')
    if value['status'] == 'STRUCTURE_DIAGNOSIS_COMPLETE':
        require(value['failure'] is None and value['code'] == 'supported_nonempty_structure_observed' and
                all(item is True for item in value['checks'].values()) and
                0 < len(records) == value['counts']['completed_lists'] == value['counts']['list_headers_seen'] and
                value['counts']['active_bytes_consumed'] == 613888 and
                all(row['status'] == 'STRUCTURE_OBSERVED' for row in records),
                'parser completion claim lacks complete supported coverage')
    else:
        failure = value['failure']
        require(type(failure) is dict and set(failure) == {'code', 'record_index', 'entry_index', 'journal_offset'} and
                failure['code'] == value['code'] and
                (failure['record_index'] is None or type(failure['record_index']) is int and 0 <= failure['record_index'] <= 16) and
                (failure['entry_index'] is None or type(failure['entry_index']) is int and 0 <= failure['entry_index'] <= 4096) and
                (failure['journal_offset'] is None or type(failure['journal_offset']) is int and 0 <= failure['journal_offset'] <= JOURNAL_BYTES),
                'parser refusal lacks bounded diagnostic positions')
    require(len(json.dumps(value, sort_keys=True).encode()) <= 32 << 10, 'parser selected output exceeds bound')
    return value


def require_absent(m):
    for identity, label, key in ((EXPECTED_WRAPPER, 'resume5 owner', 'starttime'),
                                 (EXPECTED_INSPECTOR, 'resume5 inspector', 'starttime'),
                                 (EXPECTED_QEMU, 'resume5 QEMU', 'start_ticks'),
                                 (EXPECTED_OBSERVER, 'resume5 observer', 'start_ticks')):
        m.absent(identity, label, key)


def compact_analysis(value):
    if value is None:
        return None
    validate_parser_analysis(value)
    return {**{key: value[key] for key in ('status', 'code', 'format', 'checks', 'counts', 'failure', 'limitations',
                                          'replay_performed', 'filesystem_accepted', 'inspection_accepted')},
            'record_count': len(value['records']), 'full_selected_records_retained_in_result': True}


def main():
    m = load_bound_owner()
    require(not os.path.lexists(OUT), 'preserve existing Data journal diagnostic output')
    locks, created = [], False
    result = {'schema': 1, 'kind': 'readonly_data_journal_diagnostic', 'status': 'INCOMPLETE',
              'diagnostic_only': True, 'inspection_success_claimed': False,
              'filesystem_consistency_claimed': False, 'replay_safety_claimed': False,
              'guest_vm_started': False, 'fsck_run': False, 'mounted': False, 'replayed': False, 'repaired': False,
              'raw_bytes_exported': False, 'private_file_inventories_exported': False,
              'whole_image_hashes_recomputed': False,
              'preservation_scope': 'stable identities of both recorded backing-chain files and unchanged prior full-hash records; freshly hashed bound metadata and sources',
              'tool_commands': [], 'retained_reads': [], 'analysis': None, 'error': None}
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
        require_absent(m)
        layout, retained_headers = load_data_layout(m, metadata)
        prep, tooling, tool, images, before = prepare_images(m, inspected, metadata)
        plan = read_plan(images, layout, tool, OUT)
        guest, parser = load_checkers(m, metadata)
        own_source = small_read(DIAGNOSTIC_SOURCE, 128 << 10)
        metadata[str(DIAGNOSTIC_SOURCE)] = sha(own_source)
        m.resources()
        OUT.mkdir(mode=0o700)
        created = True
        result.update(started_utc=m.utc(), owner=m.identity(os.getpid()),
                      source={'path': str(DIAGNOSTIC_SOURCE), 'bytes': len(own_source), 'sha256': sha(own_source)},
                      parser_source={'path': str(PARSER_SOURCE), **PARSER_SOURCE_PIN},
                      tool={'path': str(tool), **TOOL_PIN}, limits=LIMITS, data_layout=layout,
                      actual_failed_inspection_pins=9,
                      previous_full_hash_records=[row['record'] for row in inspected['backing_chain']],
                      capability={'path': str(CAPABILITY_RESULT), **CAPABILITY_PIN, 'passed': True})
        require(result['owner'] is not None, 'diagnostic owner identity unavailable')
        save_json('session.json', {'schema': 1, 'diagnostic_only': True, 'metadata_sha256': metadata,
                                  'disk_identities': before, 'data_layout': layout, 'limits': LIMITS,
                                  'tool': result['tool'], 'parser_source': result['parser_source'], 'read_plan': plan,
                                  'prior_full_hash_records': result['previous_full_hash_records'],
                                  'whole_image_hashes_recomputed': False})
        env = {'PATH': '/system/bin', 'LD_LIBRARY_PATH': str(tooling / 'lib'), 'TMPDIR': str(OUT), 'LANG': 'C', 'LC_ALL': 'C'}
        payloads, result['retained_reads'] = extract_data(m, plan, layout, retained_headers, guest, env, result['tool_commands'])
        result['jib'] = validate_jib(payloads['jib'], retained_headers, guest)
        result['analysis'] = validate_parser_analysis(parser.analyze_journal(
            payloads['journal'], volume_bytes=DATA_BYTES, expected_header_sha256=EXPECTED_DATA_HEADER_SHA256))
        # This status says the bounded diagnosis completed, including any
        # explicit INCOMPLETE parser outcome. It never accepts the filesystem.
        result['status'] = 'READONLY_DATA_JOURNAL_DIAGNOSTIC_OBSERVED'
    except BaseException as error:
        result['error'] = type(error).__name__ + ': ' + str(error)
    finally:
        try:
            if created:
                try:
                    verify_preservation(prep, tooling, images, before, metadata)
                    require_absent(m)
                    result['disk_identities_unchanged'] = True
                    result['bound_metadata_unchanged'] = True
                    result['bound_tooling_unchanged'] = True
                    result['recorded_inspection_processes_absent'] = True
                except BaseException as error:
                    result['status'] = 'INCOMPLETE'
                    result['preservation_error'] = type(error).__name__ + ': ' + str(error)
                result['finished_utc'] = m.utc()
                save_json('result.json', result)
        finally:
            for fd in reversed(locks):
                os.close(fd)
    if created:
        body = small_read(OUT / 'result.json', LIMITS['result_bytes'])
        analysis = result.get('analysis')
        print(json.dumps({'schema': 1, 'status': result['status'], 'diagnostic_only': True, 'observed_utc': m.utc(),
                          'result': {'path': str(OUT / 'result.json'), 'bytes': len(body), 'sha256': sha(body),
                                     'digest_bytes': list(hashlib.sha256(body).digest())},
                          'data_layout': result.get('data_layout'), 'retained_reads': result['retained_reads'],
                          'analysis': compact_analysis(analysis), 'tool_commands': len(result['tool_commands']),
                          'all_own_tool_children_reaped': all(row['reaped'] for row in result['tool_commands']),
                          'forced_tool_children': [row['pid'] for row in result['tool_commands'] if row['forced']],
                          'disk_identities_unchanged': result.get('disk_identities_unchanged'),
                          'bound_metadata_unchanged': result.get('bound_metadata_unchanged'),
                          'bound_tooling_unchanged': result.get('bound_tooling_unchanged'),
                          'recorded_inspection_processes_absent': result.get('recorded_inspection_processes_absent'),
                          'whole_image_hashes_recomputed': False, 'inspection_success_claimed': False,
                          'filesystem_consistency_claimed': False, 'replay_safety_claimed': False,
                          'raw_bytes_exported': False, 'private_file_inventories_exported': False,
                          'error': result.get('error'), 'preservation_error': result.get('preservation_error')},
                         separators=(',', ':')), flush=True)
    else:
        print(json.dumps({'schema': 1, 'status': 'DATA_JOURNAL_DIAGNOSTIC_REFUSED', 'diagnostic_only': True,
                          'error': result['error'], 'existing_outputs_preserved': True}, separators=(',', ':')), flush=True)
    return 0 if result['status'] == 'READONLY_DATA_JOURNAL_DIAGNOSTIC_OBSERVED' else 2


if __name__ == '__main__':
    raise SystemExit(main())


