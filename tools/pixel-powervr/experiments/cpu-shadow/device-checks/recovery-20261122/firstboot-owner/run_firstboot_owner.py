#!/usr/bin/env python3
"""One-shot receipt owner for the unchanged, reviewed firstboot execution guard."""
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
OWNER = BASE / 'ios26-firstboot-owner-ebbc9c0'
PREFLIGHT = BASE / 'ios26-firstboot-guard-preflight-ebbc9c0'
PREP = Path('/data/local/tmp/pixel-prep-e9cc754')
RUNNER = Path('/data/local/tmp/pixel-prep-runner-f4d64db')
AUDIT = Path('/data/local/tmp/pixel-audit-e9cc754')
AUDITOR = Path('/data/local/tmp/pixel-boot-checks-ebbc9c0/auditor')
GUARD = Path('/data/local/tmp/pixel-boot-checks-ebbc9c0/firstboot/guard_ios26_firstboot.py')
WORK = Path('/data/local/tmp/pixel-firstboot-guard-e9cc754')
PYTHON = '/data/data/com.termux/files/usr/bin/python'
PREFLIGHT_COMMAND = [PYTHON, '-B', str(GUARD), '--audit-work', str(AUDIT),
                     '--auditor-dir', str(AUDITOR), '--runner-dir', str(RUNNER), '--work', str(WORK)]
COMMAND = PREFLIGHT_COMMAND + ['--execute']
GUARD_SHA = '8f98fafd603385b5d3aa20331acc7e536020b6ae136f8690bd190efbeb09845c'
PREFLIGHT_SHA = 'eda974e4e726b0164f8c5bbcda232c972db53622e22b1736f1091717b2e4713b'
AUDIT_SHA = '542dcf281cbcfb0016d74eda8dbb7a84db799e390e857321f519de4e0f1a7146'
SESSION_DIGEST = '9ce5f5b8e4953ac54fddd854c5b4a606c2b9866814af6b1d520c2b590e987a6b'
OWNER_SECONDS, TERM_SECONDS, KILL_SECONDS = 5400, 180, 30


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


def prerequisites():
    require(os.geteuid() == 0, 'root phone owner required')
    for directory in (BASE, PREP, RUNNER, AUDIT, AUDITOR, GUARD.parent, WORK.parent): canonical(directory)
    require(not os.path.lexists(WORK), 'guard work already exists; preserve it')
    body = read(Path(str(PREFLIGHT) + '.stdout.json'))
    require(len(body) == 21952 and sha(body) == PREFLIGHT_SHA, 'accepted preflight bytes differ')
    public = json.loads(body); session = public.get('guard_session', {})
    exited, startup, requested = (record(Path(str(PREFLIGHT) + suffix)) for suffix in ('.exit.json', '.owner.json', '.command.json'))
    require(exited.get('exit_code') == exited.get('owner_exit_code') == 0 and exited.get('accepted_readonly_preflight') is True and
            exited.get('preflight_reaped') is True and exited.get('forced_child') is False and exited.get('wrapper_error') is None and
            exited.get('cleanup_errors') == [] and exited.get('stdout_sha256') == PREFLIGHT_SHA and exited.get('stdout_bytes') == 21952 and
            exited.get('boot_execution_requested') is False and exited.get('inputs_unchanged') is True and exited.get('guard_work_absent') is True and
            exited.get('finished_utc') and requested.get('command') == startup.get('command') == exited.get('command') == PREFLIGHT_COMMAND and
            requested.get('started_utc') == startup.get('started_utc') == exited.get('started_utc') and
            startup.get('preflight') == exited.get('preflight'), 'preflight ownership/exit receipt differs')
    absent(startup['wrapper']); absent(startup['preflight'])
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
    return {'guard': guard, 'prep': prep, 'session': session, 'attempts_before': attempts, 'resources': resources()}


def accepted_result(state):
    result_body = read(WORK / 'result.json'); result = json.loads(result_body)
    session = record(WORK / 'guard-session.json'); prep = state['prep']
    require(session == state['session'] and result.get('guard_session_sha256') == prep.digest(session), 'guard session differs from accepted preflight')
    require(result.get('schema') == 1 and result.get('finished_utc') and result.get('status') == 'GUARDED_FIRSTBOOT_COMPLETE' and result.get('checkpoint_accepted_by_guard') is True and
            result.get('bound_inputs_unchanged') is True and result.get('original_firstboot_checkpoint_present') is True and
            all(not result.get(k) for k in ('error', 'identity_error', 'attempt_error')) and
            all(result.get(k) is False for k in ('boot_complete', 'gpu_path_complete', 'app_gate_changed')), 'firstboot guard did not accept its checkpoint')
    attempt = canonical(Path(result['actual_attempt']['attempt']))
    require(attempt.parent == PREP / 'attempts' and re.fullmatch(r'07-\d{4}', attempt.name), 'invalid firstboot attempt path')
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
            counters[0].get('counter_check') == state['guard'].failed_io_counters(counters[0]['post_stop_blockstats']),
            'mandatory guarded supervision or counter evidence differs')
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
            'guard_session_file_sha256': sha(read(WORK / 'guard-session.json')), 'guard_observations_sha256': sha(observations_body)}


def run():
    state = prerequisites()
    OWNER.mkdir(mode=0o700)
    create('command.json', COMMAND)
    create('inputs.json', {'schema': 1, 'guard_source_sha256': GUARD_SHA, 'accepted_preflight_sha256': PREFLIGHT_SHA,
           'accepted_guard_session': state['session'], 'attempts_before': state['attempts_before'], 'resources': state['resources'],
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
