#!/usr/bin/env python3
"""Bounded diagnostic-only HFS headers through the exact frozen native qemu-img.

No guest VM, mount, replay, repair, fsck or inspection-acceptance change.
Only fresh own evidence files are written. Existing disk chains open as dd input.
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
OUT = BASE / 'ios26-hfs-header-diagnostic-resume2'
TOOL_PIN = {'bytes': 2356032, 'sha256': '1bd2fd6b968c492d0263436c260af2a8c2ee807cf4afd4fd2abb3300446e2440'}
TOOL_MANIFEST_SHA = 'a5461ecf2e41d4966f783dfca620d3d700f9aa1bc76dd5fa745ec54666e764b2'
FAILED_INSPECTION_PINS = {'/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume2-owner/exit.json': {'bytes': 906,
                                                                                                'sha256': '83a9f8f145d78b64b2cb555576f0de73f22a9658d118ce034e8db813ed4e81bd'},
 '/data/local/tmp/pixel-saved-audit-e9cc754-resume2/a1/expected-policy.json': {'bytes': 271,
                                                                               'sha256': '62b374f2088e8eb92f7aa8b32b899c09cac0e0dd2cbcc55a1e0e5bbfb5f9455a'},
 '/data/local/tmp/pixel-saved-audit-e9cc754-resume2/a1/files/inspection/result.json': {'bytes': 1972,
                                                                                       'sha256': '4548dc39a1c014152ab090d57a1c9ceabde4d94afb67a5d54feec4fae9454de2'},
 '/data/local/tmp/pixel-saved-audit-e9cc754-resume2/a1/vm-result.json': {'bytes': 1266,
                                                                         'sha256': '05d3c3f5ebc3cb658c4283fd5412fdac32a8caf49e291188bdf8eee2a0377ee5'},
 '/data/local/tmp/pixel-saved-audit-e9cc754-resume2/result.json': {'bytes': 3705,
                                                                   'sha256': 'b7c788a7581db8c4061d2e97f6600c20ac9a0cdd3f47816e92c6c7276d54dfb1'}}  # Five actual independently reviewed failure bindings.
CAPABILITY_RESULT = BASE / 'ios26-hfs-header-capability-resume4/result.json'
CAPABILITY_PIN = None  # Finalize only from the actual independently reviewed passed native capability receipt.
CAPABILITY_SOURCE_SHA256 = '4264533ff68a0a116aeecbe140de041b1f02b5036f9bf83783d2f4958f1ece8f'
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


def load_bound_owner():
    require(type(FAILED_INSPECTION_PINS) is dict and type(CAPABILITY_PIN) is dict,
            'UNRELEASED: actual failed-inspection and passed capability pins required')
    require(os.geteuid() == 0 and BASE.resolve(strict=True) == BASE, 'root and canonical base required')
    body = small_read(OWNER_SOURCE, OWNER_SOURCE_PIN['bytes'])
    require({'bytes': len(body), 'sha256': sha(body)} == OWNER_SOURCE_PIN, 'reviewed inspection owner source differs')
    return module(body, OWNER_SOURCE, 'verified_saved_inspection_owner')


def check_metadata(m):
    expected = {str(m.OWNER / 'exit.json'), str(m.WORK / 'result.json'), str(m.WORK / 'a1/vm-result.json'),
                str(m.WORK / 'a1/files/inspection/result.json'), str(m.WORK / 'a1/expected-policy.json')}
    require(set(FAILED_INSPECTION_PINS) == expected, 'exact five observed failure paths required')
    bound = {}
    for name, pin in FAILED_INSPECTION_PINS.items():
        body = small_read(Path(name))
        require({'bytes': len(body), 'sha256': sha(body)} == pin, 'actual failed inspection metadata changed')
        bound[name] = sha(body)
    public_body = small_read(m.OWNER / 'preflight.json')
    require({'bytes': len(public_body), 'sha256': sha(public_body)} == PREFLIGHT_PIN, 'actual preflight changed')
    current = m.read_json(m.OWNER / 'prerequisites.json')
    public = json.loads(public_body)
    m.validate_preflight(public, current)
    previous = m.previous_failure_inputs()
    require(all(current['inputs'].get(name) == pin for name, pin in previous.items()), 'prior failure preservation differs')
    for name, pin in current['inputs'].items():
        require(sha(small_read(Path(name))) == pin, 'bound preparation/source input changed')
        bound[name] = pin
    for path, pin in m.SOURCE_HASHES.items():
        require(sha(small_read(path)) == pin, 'frozen source differs')
    startup, exited = m.read_json(m.OWNER / 'owner.json'), m.read_json(m.OWNER / 'exit.json')
    require(startup.get('wrapper') == {'pid': 13387, 'starttime': 8827282} and
            startup.get('command') == exited.get('command') == m.read_json(m.OWNER / 'command.json') == m.COMMAND + ['--execute'] and
            all(startup.get(k) == exited.get(k) for k in ('wrapper', 'runner', 'started_utc')) and
            exited.get('exit_code') == exited.get('owner_exit_code') == 2 and exited.get('accepted') is False and
            exited.get('runner_reaped') is True and exited.get('forced_runner') is False and
            exited.get('cleanup_errors') == [] and exited.get('wrapper_error') == 'ValueError: inspector exited 2',
            'exact failed inspection owner differs')
    for key in ('wrapper', 'runner'):
        m.absent(startup[key], 'inspection ' + key)
    m.absent(m.read_json(m.WORK / 'a1/vm.child.json'), 'inspection QEMU', 'start_ticks')
    result = m.read_json(m.WORK / 'result.json')
    guest = m.read_json(m.WORK / 'a1/files/inspection/result.json')
    require(result.get('status') == 'INCOMPLETE' and result.get('full_backing_chain_unchanged') is True and
            result.get('preparation_and_guard_unchanged') is True and result.get('identity_error') is None and
            result.get('guest_result') == guest and guest.get('readonly_attachments') is True and
            all(guest.get(k) is False for k in ('mounted', 'replayed', 'repaired')) and
            guest.get('errors') == [{'code': 'volume_not_journaled_or_inconsistent'}] and
            guest.get('journals', {}).get('iOSRoot', {}).get('code') == 'volume_not_journaled_or_inconsistent',
            'actual classified guest boundary differs')
    inspected = m.read_json(m.WORK / 'inspection-session.json')
    require(m.digest(inspected) == result.get('inspection_session_sha256') and
            inspected == public.get('inspection_session'), 'accepted preflight and actual inspection session differ')
    for path in (m.OWNER / 'owner.json', m.OWNER / 'command.json', m.OWNER / 'prerequisites.json',
                 m.OWNER / 'preflight.json', m.WORK / 'inspection-session.json', m.WORK / 'a1/vm.child.json'):
        bound[str(path)] = sha(small_read(path))
    return current, inspected, bound


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


def main():
    m = load_bound_owner()
    require(not os.path.lexists(OUT), 'preserve existing diagnostic work')
    locks, created, result = [], False, {'schema': 1, 'kind': 'readonly_hfs_header_diagnostic', 'status': 'INCOMPLETE',
        'diagnostic_only': True, 'inspection_success_claimed': False, 'guest_vm_started': False,
        'mounted': False, 'replayed': False, 'repaired': False, 'fsck_run': False,
        'tool_commands': [], 'headers': [], 'error': None}
    metadata, before, prep, images = None, None, None, None
    try:
        for path in (m.PREP / 'owner.lock', m.WORK / 'owner.lock'):
            m.canonical(path)
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            locks.append(fd)
            require(stat.S_ISREG(os.fstat(fd).st_mode), 'nonordinary existing ownership lock')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        current, inspected, metadata = check_metadata(m)
        m.refuse_live_children()
        session = m.read_json(m.PREP / 'session.json')
        guard = module(small_read(m.GUARD_SOURCE), m.GUARD_SOURCE, 'verified_frozen_guard')
        prep = guard.load_frozen(m.RUNNER, session['runner_sources'])
        tooling = m.canonical(Path(session['tooling']))
        require(session['tooling_manifest_sha256'] == TOOL_MANIFEST_SHA, 'bound tooling manifest differs')
        manifest = prep.verify_tools(tooling, TOOL_MANIFEST_SHA)
        require(manifest['files']['tools/qemu-img']['bytes'] == TOOL_PIN['bytes'] and
                manifest['files']['tools/qemu-img']['sha256'] == TOOL_PIN['sha256'], 'frozen qemu-img pin differs')
        tool = tooling / 'tools/qemu-img'
        capability_body = small_read(CAPABILITY_RESULT, LIMITS['result_bytes'])
        require({'bytes': len(capability_body), 'sha256': sha(capability_body)} == CAPABILITY_PIN,
                'actual passed capability receipt changed')
        capability = json.loads(capability_body)
        expected_probe_commands = [[str(tool), 'dd', '--help'], [str(tool), 'dd', '-f', 'raw', '-O', 'raw', 'bs=512', 'count=3', 'skip=2',
            'if=' + str(CAPABILITY_RESULT.parent / 'sample.input'), 'of=' + str(CAPABILITY_RESULT.parent / 'sample.output')]]
        require(capability.get('schema') == 1 and capability.get('kind') == 'native_qemu_img_read_capability_probe' and
                capability.get('status') == 'QEMU_IMG_READ_CAPABILITY_PASSED' and
                capability.get('source_sha256') == CAPABILITY_SOURCE_SHA256 and
                capability.get('tool') == {'path': str(tool), **TOOL_PIN} and capability.get('tooling_manifest_sha256') == TOOL_MANIFEST_SHA and
                capability.get('bound_tooling_and_session_unchanged') is True and capability.get('expected_bytes_match') is True and
                capability.get('input_unchanged') is True and capability.get('synthetic_input_bytes') == 2048 and
                capability.get('expected_output_sha256') == capability.get('actual_output_sha256') == sha(bytes([51]) * 512) and
                capability.get('skip_blocks') == 2 and capability.get('count_blocks') == 3 and
                capability.get('count_semantics') == 'input_limit_before_skip' and
                capability.get('block_bytes') == capability.get('output_bytes') == 512 and
                capability.get('existing_disk_images_opened') is False and capability.get('guest_vm_started') is False and
                capability.get('error') is None and not capability.get('preservation_error') and
                [row.get('command') for row in capability.get('tool_commands', [])] == expected_probe_commands and
                all(row.get('reaped') is True and row.get('forced') is False and row.get('exit_code') == 0 and
                    not row.get('cleanup_error') for row in capability['tool_commands']), 'actual frozen capability probe did not pass cleanly')
        metadata[str(CAPABILITY_RESULT)] = sha(capability_body)
        chain = inspected['backing_chain']
        require(type(chain) is list and len(chain) == 2, 'exact saved/baseline chain required')
        images = [m.canonical(Path(row['identity']['path'])) for row in chain]
        require(all(path.is_relative_to(m.PREP) for path in images) and images[0] != images[1], 'unexpected image paths')
        require([row['path'] for row in prep.cold.qcow_chain(images[0])] == [str(x) for x in images] and
                [row['path'] for row in prep.cold.qcow_chain(images[1])] == [str(images[1])], 'bound backing graph differs')
        before = [prep.cold.readonly_identity(path) for path in images]
        require(before == [row['identity'] for row in chain], 'disk identity changed from the full inspected chain')
        own_source = small_read(DIAGNOSTIC_SOURCE, 64 << 10)
        metadata[str(DIAGNOSTIC_SOURCE)] = sha(own_source)
        metadata[str(tooling / 'tooling-manifest.json')] = TOOL_MANIFEST_SHA
        m.resources()  # Preserve the installed owner's existing available-memory/storage floors.
        OUT.mkdir(mode=0o700)
        created = True
        result.update(started_utc=m.utc(), owner={'pid': os.getpid(), 'starttime': m.identity(os.getpid())['starttime']},
                      source={'path': str(DIAGNOSTIC_SOURCE), 'bytes': len(own_source), 'sha256': sha(own_source)},
                      tool={'path': str(tool), **TOOL_PIN}, limits=LIMITS,
                      previous_full_hash_records=[row['record'] for row in chain], full_disk_hashes_recomputed=False)
        save_json('session.json', {'schema': 1, 'diagnostic_only': True, 'metadata_sha256': metadata,
                                  'disk_identities': before, 'limits': LIMITS, 'tool': result['tool']})
        env = {'PATH': '/system/bin', 'LD_LIBRARY_PATH': str(tooling / 'lib'), 'TMPDIR': str(OUT), 'LANG': 'C', 'LC_ALL': 'C'}
        result['capability'] = {'path': str(CAPABILITY_RESULT), **CAPABILITY_PIN, 'passed': True, 'source_sha256': CAPABILITY_SOURCE_SHA256}
        for image_index, image in enumerate(images):
            for start, sectors, volume in PARTITIONS:
                for copy, relative in (('primary', 1024), ('alternate', sectors * 512 - 1024)):
                    offset = start * 512 + relative
                    require(offset % 512 == 0 and 0 <= offset < 51541704704 - 512, 'header offset bounds')
                    label = 'h' + str(len(result['headers']))
                    target = OUT / (label + '.bin')
                    require(not os.path.lexists(target), 'fresh header output required')
                    command = [str(tool), 'dd', '-f', 'qcow2', '-O', 'raw', 'bs=512', 'count=' + str(offset // 512 + 1),
                               'skip=' + str(offset // 512), 'if=' + str(image), 'of=' + str(target)]
                    m.resources()
                    run_tool(label, command, env, result['tool_commands'])
                    result['headers'].append(decode_header(small_read(target, 512), 'saved' if image_index == 0 else 'baseline',
                                                            volume, copy, offset, sectors))
        require(len(result['headers']) == LIMITS['headers'], 'incomplete fixed header inventory')
        result['status'] = 'READONLY_HFS_HEADERS_OBSERVED'
    except BaseException as error:
        result['error'] = type(error).__name__ + ': ' + str(error)
    finally:
        if created:
            try:
                require([prep.cold.readonly_identity(path) for path in images] == before, 'disk identity changed during diagnostic')
                for name, pin in metadata.items():
                    require(sha(small_read(Path(name))) == pin, 'bound metadata/source changed during diagnostic')
                prep.verify_tools(tooling, TOOL_MANIFEST_SHA)
                result['disk_identities_unchanged'] = True
                result['bound_metadata_unchanged'] = True
                result['bound_tooling_unchanged'] = True
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
                          'capability_passed': result.get('capability', {}).get('passed') is True,
                          'headers': len(result['headers']), 'all_own_tool_children_reaped': all(x['reaped'] for x in result['tool_commands']),
                          'forced_tool_children': [x['pid'] for x in result['tool_commands'] if x['forced']],
                          'disk_identities_unchanged': result.get('disk_identities_unchanged'),
                          'bound_metadata_unchanged': result.get('bound_metadata_unchanged'),
                          'full_disk_hashes_recomputed': False, 'inspection_success_claimed': False,
                          'error': result.get('error'), 'preservation_error': result.get('preservation_error')}, separators=(',', ':')), flush=True)
        for row in result['headers']:
            print(json.dumps(row, separators=(',', ':')), flush=True)
    else:
        print(json.dumps({'schema': 1, 'status': 'HEADER_DIAGNOSTIC_REFUSED', 'diagnostic_only': True,
                          'error': result['error'], 'existing_files_unchanged': True}, separators=(',', ':')), flush=True)
    return 0 if result['status'] == 'READONLY_HFS_HEADERS_OBSERVED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
