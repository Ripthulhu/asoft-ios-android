#!/usr/bin/env python3
"""Two-phase receipt owner for the already staged, immutable partition auditor.

No arguments: show usage. --preflight: retain the exact read-only preflight.
--execute: consume that successful receipt and run the exact command + --execute.
This owner never calls preparation, QEMU, or a host-policy tool directly.
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys

BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
OWNER = BASE / 'ios26-partition-audit-ebbc9c0-owner'
PREVIOUS = BASE / 'ios26-disks-retry-f4d64db'
PREP = Path('/data/local/tmp/pixel-prep-e9cc754')
RUNNER = Path('/data/local/tmp/pixel-prep-runner-f4d64db')
AUDITOR = Path('/data/local/tmp/pixel-boot-checks-ebbc9c0/auditor')
WORK = Path('/data/local/tmp/pixel-audit-e9cc754')
PYTHON = '/data/data/com.termux/files/usr/bin/python'
COMMAND = [PYTHON, '-B', str(AUDITOR / 'audit_ios26_partition.py'),
           '--prep-work', str(PREP), '--runner-dir', str(RUNNER), '--work', str(WORK)]
STAGES = ['shared-fetch', 'shared-unpack', 'shared-build', 'ios26-fetch',
          'ios26-decrypt', 'ios26-rootfs', 'ios26-partition']
SESSION_SHA = '9ce5f5b8e4953ac54fddd854c5b4a606c2b9866814af6b1d520c2b590e987a6b'
PREVIOUS_OWNER_SHA = '46db915626179ad8ab55fc7ce3ec0fb002410a6d888c69576b1d1fd9ae68675e'
PREVIOUS_COMMAND_SHA = '7e8abfa6b35867e279b2275a9a81f2fe61b17d9f4995e2edcb5dc232802bbc1a'
SOURCE_HASHES = {
    RUNNER / 'prepare_ios26.py': 'c77bc990e56dcb47d651f9c054c41313a6671498a5b2494e96bb522ae868fb1a',
    RUNNER / 'prepare_ios26_stages.py': '89e242b0c98dd994a04cabaeadc52f8d566ff3fd33fae37e1979ab81fd32b952',
    RUNNER / 'cold_boot_ios26.py': '6a57ed164864eef20aeffd34b14b675a8ac597c20583c9f179414a36b4ccbdeb',
    RUNNER / 'cold_boot_dt.py': '6931310e1318a6397ee2d7eead966bd0fcdeaae9c10038ca2f2aa01de1a45f7e',
    AUDITOR / 'audit_ios26_partition.py': '6988d94e975ebd43dd022eb3303b5c6722a05755a1b0614d780343e577065687',
    AUDITOR / 'audit_ios26_partition_guest.py': '6874b9b6b68c7fb50c3f9cf05c1b6a86a53f8fed75863c00a6ad9254b1640593',
    BASE / 'run-ios26-disks-retry-f4d64db.py': '6ed877eba0114375409dce5146c0e7187fca06af6ab587cddbd2aab836b9d38a',
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


def read_bytes(path):
    canonical(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= 2 << 20,
                'not bounded ordinary metadata: ' + str(path))
        body = stream.read((2 << 20) + 1)
        require(len(body) <= 2 << 20, 'metadata grew beyond bound: ' + str(path))
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


def clean_vm(value, stage):
    cleanup, witness = value.get('cleanup', {}), value.get('witnesses', {})
    require(value.get('schema') == 1 and value.get('stage') == stage and
            value.get('status') == 'VM_OBSERVATION_COMPLETE' and value.get('natural_exit') is True and
            value.get('done_codes') == [0] and value.get('finished_utc') and not value.get('error') and
            witness.get('native_initialization') is True and witness.get('native_execution') is True and
            witness.get('fatal_markers') == [] and cleanup.get('exit_code') == 0 and
            cleanup.get('echild') is True and cleanup.get('forced_qemu') is False and
            cleanup.get('forced_descendants') == [] and cleanup.get('errors') == [],
            'checkpoint helper lacks natural native completion and clean reap: ' + stage)


def prerequisites():
    """Read-only metadata/identity/lock check; auditor owns full artifact validation."""
    require(os.geteuid() == 0, 'root phone owner required')
    for directory in (BASE, PREVIOUS, PREP, RUNNER, AUDITOR, WORK.parent):
        canonical(directory)
    require(not os.path.lexists(WORK), 'audit work already exists; preserve it')
    require(len(str(WORK)) <= 55, 'audit work path exceeds auditor bound')
    inputs = {}

    def checked(path, expected=None):
        body = read_bytes(path)
        value = inputs[str(path)] = sha(body)
        require(expected is None or value == expected, 'input hash differs: ' + str(path))
        return body

    for path, expected in SOURCE_HASHES.items():
        checked(path, expected)
    checked(Path(__file__).resolve(strict=True))
    prior = json.loads(checked(PREVIOUS / 'owner.json', PREVIOUS_OWNER_SHA))
    command = json.loads(checked(PREVIOUS / 'command.json', PREVIOUS_COMMAND_SHA))
    exited = json.loads(checked(PREVIOUS / 'exit.json'))
    require(prior.get('schema') == exited.get('schema') == 1 and
            prior['command'] == command == exited.get('command') and
            prior['started_utc'] == exited.get('started_utc') and exited.get('finished_utc') and
            exited.get('exit_code') == 0 and exited.get('runner_started') is True and
            exited.get('runner_reaped') is True and exited.get('forced_runner') is False and
            exited.get('wrapper_error') is None and exited.get('cleanup_errors') == [],
            'previous outer owner has not completed cleanly')
    absent(prior['wrapper'], 'previous wrapper')
    absent(prior['runner'], 'previous runner')
    session = json.loads(checked(PREP / 'session.json'))
    require(digest(session) == SESSION_SHA, 'preparation session differs')
    folder = canonical(PREP / 'checkpoints')
    require({p.name for p in folder.iterdir()} == {s + '.json' for s in STAGES},
            'exact seven-checkpoint partition boundary required')
    previous_sha = None
    checkpoints = {}
    for stage in STAGES:
        path = folder / (stage + '.json')
        body = checked(path)
        record = json.loads(body)
        require(record.get('schema') == 1 and record.get('status') == 'STAGE_COMPLETE' and
                record.get('stage') == stage and record.get('session_sha256') == SESSION_SHA and
                record.get('previous_sha256') == previous_sha and isinstance(record.get('artifacts'), dict),
                'incomplete or disconnected checkpoint: ' + stage)
        previous_sha = checkpoints[str(path)] = sha(body)
        if stage in ('ios26-rootfs', 'ios26-partition'):
            attempt = canonical(Path(record['attempt']))
            require(attempt.parent == PREP / 'attempts', 'checkpoint attempt escapes preparation')
            clean_vm(json.loads(checked(attempt / 'vm-result.json')), stage)
    result = json.loads(checked(PREP / 'result.json'))
    require(result.get('status') == 'PREPARATION_CHECKPOINT' and result.get('completed') == STAGES and
            result.get('stage') == 'ios26-partition' and result.get('finished_utc') and
            not result.get('error') and all(result.get(k) is False for k in
                ('boot_complete', 'gpu_path_complete', 'app_gate_changed')),
            'preparation result is not the completed partition boundary')
    fd = os.open(canonical(PREP / 'owner.lock'), os.O_RDONLY | os.O_NOFOLLOW)
    try:
        require(stat.S_ISREG(os.fstat(fd).st_mode), 'preparation lock is not ordinary')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        refuse_live_children()
    finally:
        os.close(fd)
    return {'inputs': inputs, 'checkpoints': checkpoints}


def validate_preflight(public, current):
    session = public.get('session', {})
    require(public.get('schema') == 1 and public.get('status') == 'PREFLIGHT_READY' and
            public.get('work') == str(WORK) and public.get('execution_verified') is False and
            all(public.get(k) is False for k in ('boot_complete', 'gpu_path_complete', 'app_gate_changed')) and
            session.get('schema') == 1 and session.get('kind') == 'standalone_ios26_partition_audit' and
            session.get('prep_work') == str(PREP) and session.get('runner_dir') == str(RUNNER) and
            session.get('prep_session_sha256') == current['inputs'][str(PREP / 'session.json')] and
            session.get('checkpoints') == current['checkpoints'] and session.get('readonly') is True and
            session.get('native_required') is True and session.get('tcg_retry') is False and
            session.get('auditor_sources') == {p.name: h for p, h in SOURCE_HASHES.items() if p.parent == AUDITOR} and
            session.get('frozen_runner_sources') == {p.name: h for p, h in SOURCE_HASHES.items() if p.parent == RUNNER},
            'read-only auditor preflight did not accept the exact completed boundary')


def accept_result():
    value = read_json(WORK / 'result.json')
    expected_session = read_json(OWNER / 'preflight.json')['session']
    actual_session = read_json(WORK / 'audit-session.json')
    witness, cleanup = value.get('native_witnesses', {}), value.get('cleanup', {})
    require(value.get('schema') == 1 and value.get('status') == 'PARTITION_AUDIT_PASSED' and
            actual_session == expected_session and value.get('session_sha256') == digest(expected_session) and
            value.get('disk_unchanged') is True and value.get('preparation_records_unchanged') is True and
            value.get('natural_exit') is True and not value.get('error') and not value.get('identity_error') and
            witness.get('native_initialization') is True and witness.get('native_execution') is True and
            witness.get('fatal_markers') == [] and cleanup.get('exit_code') == 0 and
            cleanup.get('echild') is True and cleanup.get('forced_qemu') is False and
            cleanup.get('forced_descendants') == [] and cleanup.get('errors') == [] and
            all(value.get(k) is False for k in ('boot_complete', 'gpu_path_complete', 'app_gate_changed')),
            'auditor did not produce a complete unchanged, native, clean partition audit')
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
            require(child_identity is not None, 'spawned auditor has no process identity')
            create(prefix + 'owner.json', {'schema': 1, 'started_utc': started,
                   'wrapper': wrapper, 'runner': child_identity, 'command': command})
            returncode = child.wait()
            stream.flush()
            os.fsync(stream.fileno())
        require(returncode == 0, 'auditor exited ' + str(returncode))
        if execute:
            result_sha = accept_result()
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
                    child.wait(timeout=60)
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
                   'stdout_sha256': stdout_sha, 'audit_result_sha256': result_sha,
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
    args = parser.parse_args(argv)
    try:
        current = prerequisites()
        if args.preflight:
            OWNER.mkdir(mode=0o700)
            create('prerequisites.json', current)
        else:
            canonical(OWNER)
            require(read_json(OWNER / 'prerequisites.json') == current, 'preflight inputs changed')
            receipt = read_json(OWNER / 'preflight-exit.json')
            startup = read_json(OWNER / 'preflight-owner.json')
            require(receipt.get('schema') == 1 and receipt.get('command') == COMMAND and
                    read_json(OWNER / 'preflight-command.json') == COMMAND and
                    receipt.get('exit_code') == receipt.get('owner_exit_code') == 0 and
                    receipt.get('accepted') is True and receipt.get('runner_reaped') is True and
                    receipt.get('forced_runner') is False and receipt.get('wrapper_error') is None and
                    receipt.get('cleanup_errors') == [] and receipt.get('finished_utc') and
                    startup.get('command') == COMMAND and startup.get('started_utc') == receipt.get('started_utc') and
                    all(startup.get(k) == receipt.get(k) for k in ('wrapper', 'runner')) and
                    sha(read_bytes(OWNER / 'preflight.json')) == receipt.get('stdout_sha256'),
                    'missing, failed or mismatched read-only preflight receipt')
            absent(startup['wrapper'], 'preflight wrapper')
            absent(startup['runner'], 'preflight auditor')
            validate_preflight(read_json(OWNER / 'preflight.json'), current)
        return run_phase(args.execute, current)
    except Exception as exc:
        print(json.dumps({'schema': 1, 'status': 'OWNER_REFUSED', 'error': type(exc).__name__ + ': ' + str(exc)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
