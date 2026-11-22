#!/usr/bin/env python3
"""Unreleased two-phase owner for the accepted resume1 saved-disk inspection.

Finalize FIRSTBOOT_SUCCESS_PINS from observed successful phone receipts before
installation. No mode can run while that mapping is None. --preflight invokes
only the immutable inspector's default read-only path. --execute additionally
requires the actual observed preflight stdout SHA and length, and clean reaping.
The inspector owns all VM/disk logic; this wrapper never launches QEMU directly.
"""
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

BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
OWNER = BASE / 'ios26-saved-inspection-resume1-owner'
FIRSTBOOT_OWNER = BASE / 'ios26-firstboot-owner-resume1'
FIRSTBOOT_ADAPTER = BASE / 'run-ios26-firstboot-memfd-adapter-resume1.py'
FIRSTBOOT_SOURCE = BASE / 'run-ios26-firstboot-owner-resume1.py'
GUARD_WORK = Path('/data/local/tmp/pixel-firstboot-guard-e9cc754-resume1')
GUARD_SOURCE = Path('/data/local/tmp/pixel-boot-checks-counter1/firstboot/guard_ios26_firstboot.py')
PREP = Path('/data/local/tmp/pixel-prep-e9cc754')
RUNNER = Path('/data/local/tmp/pixel-prep-runner-f4d64db')
INSPECTOR = Path('/data/local/tmp/pixel-saved-checks-counter1')
WORK = Path('/data/local/tmp/pixel-saved-audit-e9cc754-resume1')
PYTHON = '/data/data/com.termux/files/usr/bin/python'
COMMAND = [PYTHON, '-I', '-B', str(INSPECTOR / 'inspect_ios26_firstboot.py'),
           '--guard-work', str(GUARD_WORK), '--work', str(WORK)]
FIRSTBOOT_COMMAND = [PYTHON, '-I', '-B', str(FIRSTBOOT_ADAPTER), '--execute']
STAGES = ['shared-fetch', 'shared-unpack', 'shared-build', 'ios26-fetch',
          'ios26-decrypt', 'ios26-rootfs', 'ios26-partition', 'ios26-firstboot']
SESSION_DIGEST = '9ce5f5b8e4953ac54fddd854c5b4a606c2b9866814af6b1d520c2b590e987a6b'
FIRSTBOOT_SUCCESS_PINS = {'/data/local/tmp/pixel-firstboot-guard-e9cc754-resume1/guard-observations.json': {'bytes': 13249, 'sha256': 'c6b967916eee233f8d6bfe4efbd13dee002caf2fc1af1b61dc5bb0ff9027703a'}, '/data/local/tmp/pixel-firstboot-guard-e9cc754-resume1/guard-session.json': {'bytes': 20936, 'sha256': 'dbb13619f92e0349036a71088511db4eeb978aaae6a22428976761ef54b2873e'}, '/data/local/tmp/pixel-firstboot-guard-e9cc754-resume1/result.json': {'bytes': 33910, 'sha256': '8d2731493b0ccdad2056677e56774f11718d9d01fb35e895023963d98847f8e3'}, '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-firstboot-owner-resume1/command.json': {'bytes': 176, 'sha256': 'b1fa143253a989f64c347d792324897bbebeb6ae3197c4824a69dff7dbb608f2'}, '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-firstboot-owner-resume1/exit.json': {'bytes': 4104, 'sha256': 'd7efc91338833952c35637bdbb0f53260d35a5a9c3a9bba60979240a7d3abc53'}, '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-firstboot-owner-resume1/owner.json': {'bytes': 667, 'sha256': 'b37b5d9e806689e93be5bcf41a82ac0d86c15e116c37919fe3109ba3c5e26545'}, '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-firstboot-memfd-adapter-resume1.py': {'bytes': 9101, 'sha256': 'ede70023bc1e05b08730b48fab1016c3e665c0e83469509e5b8b74c6f2364ec7'}, '/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-firstboot-owner-resume1.py': {'bytes': 42490, 'sha256': '862af55267f7ecd1273faf8f161e4065161f1bf49a5df6614cfb2571fc95d473'}, '/data/local/tmp/pixel-prep-e9cc754/checkpoints/ios26-firstboot.json': {'bytes': 803, 'sha256': '0c3418d053477d73d210eb8a22dd28e49cff61ff5140f77b6c97d4c96c8c079e'}}  # Physically observed accepted 07-0004.
SOURCE_HASHES = {
    GUARD_SOURCE: 'ea40638312d6ac41607806ecb03c148fbd0677df6ab01480e13fd40536869674',
    INSPECTOR / 'inspect_ios26_firstboot.py': '2b127ecda390b199287358cdad7e6e7774f5b787148aea524e7b0247a2640cf3',
    INSPECTOR / 'inspect_ios26_firstboot_guest.py': 'ada26de8ababb11bb4af20e558708545eb64fd516481359fd5d0ccf6a7cbae2b',
    RUNNER / 'prepare_ios26.py': 'c77bc990e56dcb47d651f9c054c41313a6671498a5b2494e96bb522ae868fb1a',
    RUNNER / 'prepare_ios26_stages.py': '89e242b0c98dd994a04cabaeadc52f8d566ff3fd33fae37e1979ab81fd32b952',
    RUNNER / 'cold_boot_ios26.py': '6a57ed164864eef20aeffd34b14b675a8ac597c20583c9f179414a36b4ccbdeb',
    RUNNER / 'cold_boot_dt.py': '6931310e1318a6397ee2d7eead966bd0fcdeaae9c10038ca2f2aa01de1a45f7e',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def digest(value):
    return sha(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())


def canonical(path):
    require(path.is_absolute() and path.resolve(strict=True) == path, 'noncanonical path: ' + str(path))
    return path


def read_bytes(path, limit=4 << 20):
    canonical(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= limit,
                'not bounded ordinary metadata: ' + str(path))
        body = stream.read(limit + 1)
        require(len(body) <= limit, 'metadata grew beyond bound: ' + str(path))
        return body


def read_json(path):
    return json.loads(read_bytes(path))


def create(name, value):
    canonical(OWNER)
    fd = os.open(OWNER / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(OWNER, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def identity(pid):
    require(type(pid) is int and pid > 0, 'invalid process identity')
    try:
        raw = (Path('/proc') / str(pid) / 'stat').read_text()
    except FileNotFoundError:
        return None
    return {'pid': pid, 'starttime': int(raw[raw.rfind(')') + 2:].split()[19])}


def absent(record, label, start_key='starttime'):
    require(set(record) == {'pid', start_key} and type(record[start_key]) is int,
            'invalid recorded identity: ' + label)
    require(identity(record['pid']) != {'pid': record['pid'], 'starttime': record[start_key]},
            'recorded process is still present: ' + label)


def refuse_live_children():
    for path in (PREP / 'attempts').glob('*/*.child.json'):
        absent(read_json(path), str(path), 'start_ticks')
    marker = (str(PREP) + '/attempts/').encode()
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            command = (entry / 'cmdline').read_bytes()
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        require(not (marker in command and
                     (b'qemu-system-aarch64' in command or b'com.asoft.ios.PrepareInputs' in command)),
                'unreaped preparation process: PID ' + entry.name)


def expected_success_paths():
    return {str(p) for p in (FIRSTBOOT_SOURCE, FIRSTBOOT_ADAPTER,
            *(FIRSTBOOT_OWNER / name for name in ('owner.json', 'command.json', 'exit.json')),
            *(GUARD_WORK / name for name in ('guard-session.json', 'guard-observations.json', 'result.json')),
            PREP / 'checkpoints/ios26-firstboot.json')}


def require_finalized():
    require(type(FIRSTBOOT_SUCCESS_PINS) is dict and set(FIRSTBOOT_SUCCESS_PINS) == expected_success_paths(),
            'unreleased owner: actual accepted firstboot pins must be finalized')
    for path, pin in FIRSTBOOT_SUCCESS_PINS.items():
        require(type(pin) is dict and set(pin) == {'bytes', 'sha256'} and
                type(pin['bytes']) is int and 0 < pin['bytes'] <= 2 << 20 and
                type(pin['sha256']) is str and re.fullmatch('[0-9a-f]{64}', pin['sha256']),
                'malformed firstboot pin: ' + path)


def prerequisites():
    """Metadata/identity/lock checks. The immutable inspector validates disks."""
    require_finalized()
    require(os.geteuid() == 0, 'root phone owner required')
    for folder in (BASE, FIRSTBOOT_OWNER, GUARD_WORK, PREP, RUNNER, INSPECTOR, WORK.parent):
        canonical(folder)
    require(not os.path.lexists(WORK), 'inspection output already exists; preserve it')
    require(len(str(WORK)) <= 55, 'inspection work path exceeds inspector bound')
    inputs = {}

    def checked(path, expected=None, size=None):
        body = read_bytes(path)
        inputs[str(path)] = actual = sha(body)
        require(expected is None or actual == expected, 'changed bound input: ' + str(path))
        require(size is None or len(body) == size, 'changed bound input size: ' + str(path))
        return body

    for path, pin in FIRSTBOOT_SUCCESS_PINS.items():
        checked(Path(path), pin['sha256'], pin['bytes'])
    for path, pin in SOURCE_HASHES.items():
        checked(path, pin)
    checked(Path(__file__).resolve(strict=True))
    first = read_json(FIRSTBOOT_OWNER / 'owner.json')
    exited = read_json(FIRSTBOOT_OWNER / 'exit.json')
    require(first.get('schema') == exited.get('schema') == 1 and
            first.get('command') == read_json(FIRSTBOOT_OWNER / 'command.json') == FIRSTBOOT_COMMAND and
            all(exited.get(k) == first.get(k) for k in ('command', 'wrapper', 'guard', 'started_utc')) and
            exited.get('exit_code') == exited.get('owner_exit_code') == 0 and
            exited.get('accepted') is True and exited.get('guard_started') is True and
            exited.get('guard_reaped') is True and exited.get('forced_guard') is False and
            exited.get('wrapper_error') is None and exited.get('cleanup_errors') == [] and
            exited.get('finished_utc'), 'resume1 firstboot owner has not accepted and cleanly reaped')
    for key in ('wrapper', 'guard'):
        absent(first[key], 'firstboot ' + key)
    guard = read_json(GUARD_WORK / 'result.json')
    require(guard.get('schema') == 1 and guard.get('status') == 'GUARDED_FIRSTBOOT_COMPLETE' and
            guard.get('checkpoint_accepted_by_guard') is True and guard.get('bound_inputs_unchanged') is True and
            guard.get('original_firstboot_checkpoint_present') is True and
            guard.get('actual_attempt', {}).get('attempt') == str(PREP / 'attempts/07-0004') and
            all(not guard.get(k) for k in ('error', 'identity_error', 'attempt_error')),
            'resume1 guard has not accepted the actual 07-0004 checkpoint')
    acceptance = exited.get('acceptance', {})
    require(acceptance.get('result_sha256') == inputs[str(GUARD_WORK / 'result.json')] and
            acceptance.get('checkpoint_sha256') == inputs[str(PREP / 'checkpoints/ios26-firstboot.json')] and
            acceptance.get('guard_session_file_sha256') == inputs[str(GUARD_WORK / 'guard-session.json')] and
            acceptance.get('guard_observations_sha256') == inputs[str(GUARD_WORK / 'guard-observations.json')] and
            acceptance.get('attempt') == str(PREP / 'attempts/07-0004'), 'outer firstboot acceptance differs')
    require(all(guard.get(k) is False for k in ('boot_complete', 'gpu_path_complete', 'app_gate_changed')),
            'unexpected firstboot completion claims')
    session = json.loads(checked(PREP / 'session.json'))
    require(digest(session) == SESSION_DIGEST, 'preparation session differs')
    folder = canonical(PREP / 'checkpoints')
    require({p.name for p in folder.iterdir()} == {s + '.json' for s in STAGES},
            'exact eight-checkpoint firstboot boundary required')
    previous, checkpoints = None, {}
    for stage in STAGES:
        path = folder / (stage + '.json')
        body = checked(path)
        record = json.loads(body)
        require(record.get('schema') == 1 and record.get('status') == 'STAGE_COMPLETE' and
                record.get('stage') == stage and record.get('session_sha256') == SESSION_DIGEST and
                record.get('previous_sha256') == previous, 'disconnected/incomplete checkpoint: ' + stage)
        previous = checkpoints[str(path)] = sha(body)
        if stage == 'ios26-firstboot':
            require(record.get('attempt') == str(PREP / 'attempts/07-0004'), 'wrong accepted firstboot attempt')
    require(guard.get('checkpoint') == {'path': str(PREP / 'checkpoints/ios26-firstboot.json'),
            'sha256': checkpoints[str(PREP / 'checkpoints/ios26-firstboot.json')]}, 'guard checkpoint binding differs')
    guard_files = {str(GUARD_WORK / name): inputs[str(GUARD_WORK / name)]
                   for name in ('guard-session.json', 'guard-observations.json', 'result.json')}
    require(set(guard['actual_attempt'].get('files', {})) ==
            {'stage-inputs.json', 'launch.json', 'vm-result.json', 'stage-result.json'}, 'incomplete firstboot attempt metadata')
    for name, pin in guard['actual_attempt']['files'].items():
        path = PREP / 'attempts/07-0004' / name
        body = checked(path, pin['sha256'], pin['bytes'])
        guard_files[str(path)] = sha(body)
    fd = os.open(canonical(PREP / 'owner.lock'), os.O_RDONLY | os.O_NOFOLLOW)
    try:
        require(stat.S_ISREG(os.fstat(fd).st_mode), 'preparation lock is not ordinary')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        refuse_live_children()
    finally:
        os.close(fd)
    return {'inputs': inputs, 'checkpoints': checkpoints, 'guard_files': guard_files}


def validate_preflight(public, current):
    session = public.get('inspection_session', {})
    require(public.get('schema') == 1 and public.get('status') == 'PREFLIGHT_READY' and
            all(public.get(k) is False for k in ('boot_complete', 'gpu_path_complete', 'app_gate_changed')) and
            session.get('schema') == 1 and session.get('kind') == 'ios26_saved_firstboot_inspection' and
            session.get('prep_work') == str(PREP) and session.get('runner_dir') == str(RUNNER) and
            session.get('prep_session_sha256') == current['inputs'][str(PREP / 'session.json')] and
            session.get('checkpoints') == current['checkpoints'] and session.get('guard_files') == current['guard_files'] and
            session.get('guard_work') == str(GUARD_WORK) and session.get('guard_source') == str(GUARD_SOURCE) and
            session.get('guard_source_sha256') == SOURCE_HASHES[GUARD_SOURCE] and
            session.get('source_directory') == str(INSPECTOR) and
            session.get('inspector_sources') == {p.name: h for p, h in SOURCE_HASHES.items() if p.parent == INSPECTOR} and
            session.get('frozen_sources') == {p.name: h for p, h in SOURCE_HASHES.items() if p.parent == RUNNER} and
            session.get('readonly') is True and session.get('native_required') is True and session.get('tcg_retry') is False and
            all(session.get(k) is False for k in ('mounts_allowed', 'replay_allowed', 'repair_allowed',
                                               'boot_complete', 'gpu_path_complete', 'app_gate_changed')) and
            session.get('helper_ram_mib') == 2048 and
            session.get('bounds') == {'helper_seconds': 7200, 'max_log_mib': 64, 'min_free_mib': 1536, 'min_available_mib': 512} and
            type(session.get('backing_chain')) is list and len(session['backing_chain']) == 2,
            'inspector preflight did not accept the exact saved firstboot boundary')


def resources():
    match = re.search(rb'^MemAvailable:\s+(\d+) kB$', Path('/proc/meminfo').read_bytes(), re.M)
    require(match is not None and int(match[1]) * 1024 >= 2816 << 20, 'inspection needs 2816 MiB MemAvailable')
    free = os.statvfs(PREP)
    require(free.f_bavail * free.f_frsize >= 1536 << 20, 'inspection needs 1536 MiB free storage')


def accept_result(current):
    value = read_json(WORK / 'result.json')
    expected = read_json(OWNER / 'preflight.json')['inspection_session']
    actual = read_json(WORK / 'inspection-session.json')
    witness, cleanup = value.get('native_witnesses', {}), value.get('cleanup', {})
    require(value.get('schema') == 1 and value.get('status') == 'SAVED_FIRSTBOOT_INSPECTION_PASSED' and
            actual == expected and value.get('inspection_session_sha256') == digest(expected) and
            value.get('full_backing_chain_unchanged') is True and value.get('preparation_and_guard_unchanged') is True and
            value.get('natural_exit') is True and not value.get('error') and not value.get('identity_error') and
            witness.get('native_initialization') is True and witness.get('native_execution') is True and
            witness.get('fatal_markers') == [] and cleanup.get('exit_code') == 0 and cleanup.get('echild') is True and
            cleanup.get('forced_qemu') is False and cleanup.get('forced_descendants') == [] and cleanup.get('errors') == [] and
            all(value.get(k) is False for k in ('boot_complete', 'gpu_path_complete', 'app_gate_changed')),
            'inspector did not produce a complete unchanged native inspection')
    outputs = value.get('outputs', {})
    require(set(outputs) == {'inspection/result.json', 'inspection/fsck-system.txt', 'inspection/fsck-data.txt'},
            'inspection output inventory incomplete')
    for name, pin in outputs.items():
        path = WORK / 'a1/files' / name
        require(pin.get('path') == str(path.relative_to(WORK)) and pin.get('bytes') == path.stat().st_size and
                pin.get('sha256') == sha(read_bytes(path)), 'inspection returned file differs: ' + name)
    guest = read_json(WORK / 'a1/files/inspection/result.json')
    require(guest == value.get('guest_result') and guest.get('status') == 'SAVED_FIRSTBOOT_INSPECTION_PASSED' and
            guest.get('errors') == [] and guest.get('cleanup_errors') == [] and guest.get('raw_metadata_unchanged') is True and
            guest.get('readonly_attachments') is True and all(guest.get(k) is False for k in ('mounted', 'replayed', 'repaired')),
            'raw inspection result disagrees with host acceptance')
    for path, pin in current['inputs'].items():
        require(sha(read_bytes(Path(path))) == pin, 'bound firstboot/source/checkpoint changed during inspection')
    refuse_live_children()
    absent(read_json(WORK / 'a1/vm.child.json'), 'inspection VM', 'start_ticks')
    return sha(read_bytes(WORK / 'result.json'))


def run_phase(execute, current):
    prefix, output = ('', 'run.log') if execute else ('preflight-', 'preflight.json')
    command = COMMAND + (['--execute'] if execute else [])
    # Exclusive command receipt reserves this phase before any child can start.
    create(prefix + 'command.json', command)
    started, child, child_identity = utc(), None, None
    forced, error, returncode, accepted, result_sha = False, None, None, False, None
    cleanup_errors = []
    wrapper = identity(os.getpid())

    def interrupted(number, _frame):
        raise InterruptedError('outer owner signal ' + str(number))

    old = {s: signal.signal(s, interrupted) for s in (signal.SIGINT, signal.SIGTERM)}
    try:
        fd = os.open(OWNER / output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
            child_identity = identity(child.pid)
            require(child_identity is not None, 'spawned inspector has no process identity')
            create(prefix + 'owner.json', {'schema': 1, 'started_utc': started,
                   'wrapper': wrapper, 'runner': child_identity, 'command': command})
            returncode = child.wait(timeout=7800 if execute else 1800)
            stream.flush()
            os.fsync(stream.fileno())
        require(returncode == 0, 'inspector exited ' + str(returncode))
        if execute:
            result_sha = accept_result(current)
        else:
            validate_preflight(read_json(OWNER / output), current)
            require(prerequisites() == current, 'prerequisites changed during read-only preflight')
        accepted = True
    except BaseException as exc:
        error = type(exc).__name__ + ': ' + str(exc)
        for number in old:
            signal.signal(number, signal.SIG_IGN)
        try:
            if child is not None and child.poll() is None:
                # Only this unreaped direct child is signalled. Its own native
                # supervisor retains QMP shutdown, subreaping and PDEATHSIG.
                child.send_signal(signal.SIGTERM)
                try:
                    child.wait(timeout=180)
                except subprocess.TimeoutExpired:
                    forced = True
                    child.kill()
                    child.wait(timeout=30)
        except BaseException as exc:
            cleanup_errors.append(type(exc).__name__ + ': ' + str(exc))
        if child is not None:
            returncode = child.returncode
    finally:
        owner_exit_code = 0 if accepted and not error and not forced and not cleanup_errors and returncode == 0 else 2
        try:
            for number in old:
                signal.signal(number, signal.SIG_IGN)
            stdout_sha = None
            if not execute and (OWNER / output).exists():
                try:
                    stdout_sha = sha(read_bytes(OWNER / output))
                except Exception as exc:
                    cleanup_errors.append('preflight output hash: ' + str(exc))
                    owner_exit_code = 2
            create(prefix + 'exit.json', {'schema': 1, 'started_utc': started, 'finished_utc': utc(),
                   'wrapper': wrapper, 'runner': child_identity, 'exit_code': returncode,
                   'owner_exit_code': owner_exit_code, 'command': command, 'wrapper_error': error,
                   'forced_runner': forced, 'cleanup_errors': cleanup_errors, 'runner_started': child is not None,
                   'runner_reaped': child is not None and returncode is not None, 'accepted': accepted,
                   'stdout_sha256': stdout_sha, 'inspection_result_sha256': result_sha,
                   'requires_owned_process_recheck': True})
        finally:
            for number, handler in old.items():
                signal.signal(number, handler)
    return owner_exit_code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--preflight', action='store_true')
    modes.add_argument('--execute', action='store_true')
    parser.add_argument('--preflight-sha256')
    parser.add_argument('--preflight-bytes', type=int)
    args = parser.parse_args(argv)
    try:
        current = prerequisites()
        if args.preflight:
            require(args.preflight_sha256 is None and args.preflight_bytes is None, 'preflight cannot consume execution pins')
            OWNER.mkdir(mode=0o700)
            create('prerequisites.json', current)
        else:
            require(type(args.preflight_sha256) is str and re.fullmatch('[0-9a-f]{64}', args.preflight_sha256) and
                    type(args.preflight_bytes) is int and 0 < args.preflight_bytes <= 2 << 20,
                    'actual observed preflight SHA-256 and bytes required')
            canonical(OWNER)
            require(read_json(OWNER / 'prerequisites.json') == current, 'preflight inputs changed')
            receipt = read_json(OWNER / 'preflight-exit.json')
            startup = read_json(OWNER / 'preflight-owner.json')
            body = read_bytes(OWNER / 'preflight.json')
            require(sha(body) == args.preflight_sha256 and len(body) == args.preflight_bytes, 'observed preflight pin differs')
            require(receipt.get('schema') == 1 and receipt.get('command') == COMMAND and
                    read_json(OWNER / 'preflight-command.json') == COMMAND and
                    receipt.get('exit_code') == receipt.get('owner_exit_code') == 0 and
                    receipt.get('accepted') is True and receipt.get('runner_started') is True and receipt.get('runner_reaped') is True and
                    receipt.get('forced_runner') is False and receipt.get('wrapper_error') is None and
                    receipt.get('cleanup_errors') == [] and receipt.get('finished_utc') and
                    startup.get('command') == COMMAND and startup.get('started_utc') == receipt.get('started_utc') and
                    all(startup.get(k) == receipt.get(k) for k in ('wrapper', 'runner')) and
                    sha(body) == receipt.get('stdout_sha256'), 'missing, failed or mismatched read-only preflight receipt')
            absent(startup['wrapper'], 'preflight wrapper')
            absent(startup['runner'], 'preflight inspector')
            validate_preflight(json.loads(body), current)
            resources()
        return run_phase(args.execute, current)
    except Exception as exc:
        print(json.dumps({'schema': 1, 'status': 'OWNER_REFUSED', 'error': type(exc).__name__ + ': ' + str(exc)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
