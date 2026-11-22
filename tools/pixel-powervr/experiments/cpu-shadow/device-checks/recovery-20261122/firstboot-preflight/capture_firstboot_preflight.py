#!/usr/bin/env python3
"""Foreground read-only firstboot-guard preflight; no boot execution."""
import datetime, hashlib, itertools, json, os, re, signal, stat, subprocess
from pathlib import Path

BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
PREFIX = 'ios26-firstboot-guard-preflight-ebbc9c0'
GUARD = Path('/data/local/tmp/pixel-boot-checks-ebbc9c0/firstboot/guard_ios26_firstboot.py')
GUARD_SHA = '8f98fafd603385b5d3aa20331acc7e536020b6ae136f8690bd190efbeb09845c'
AUDIT = Path('/data/local/tmp/pixel-audit-e9cc754')
AUDIT_SHA = '542dcf281cbcfb0016d74eda8dbb7a84db799e390e857321f519de4e0f1a7146'
WORK = Path('/data/local/tmp/pixel-firstboot-guard-e9cc754')
COMMAND = ['/data/data/com.termux/files/usr/bin/python', '-B', str(GUARD),
           '--audit-work', str(AUDIT), '--auditor-dir', '/data/local/tmp/pixel-boot-checks-ebbc9c0/auditor',
           '--runner-dir', '/data/local/tmp/pixel-prep-runner-f4d64db', '--work', str(WORK)]
PRIOR = [(8032, 7235994), (8034, 7236028), (8247, 7238076)]


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


def main():
    if os.geteuid() != 0 or BASE.resolve(strict=True) != BASE: raise ValueError('canonical root transfer directory required')
    if os.path.lexists(WORK) or '--execute' in COMMAND: raise ValueError('fresh work and preflight-only argv required')
    for suffix in ('.command.json', '.owner.json', '.stdout.json', '.exit.json'):
        if os.path.lexists(BASE / (PREFIX + suffix)): raise FileExistsError('capture already exists; preserve it')
    if hashlib.sha256(read(GUARD)).hexdigest() != GUARD_SHA: raise ValueError('staged guard source differs')
    if hashlib.sha256(read(AUDIT / 'result.json')).hexdigest() != AUDIT_SHA: raise ValueError('accepted audit result differs')
    if any(identity(pid) == {'pid': pid, 'starttime': ticks} for pid, ticks in PRIOR):
        raise ValueError('recorded audit owner or helper is still present')
    start, before = utc(), observation()
    save('.command.json', {'schema': 1, 'started_utc': start, 'command': COMMAND, 'before': before,
                          'guard_source_sha256': GUARD_SHA, 'accepted_audit_result_sha256': AUDIT_SHA, 'preflight_only': True})
    child = child_id = None; code = error = None; forced = False; cleanup_errors = []; parsed = {}

    def interrupted(number, _frame): raise InterruptedError('capture signal ' + str(number))

    handlers = {s: signal.signal(s, interrupted) for s in (signal.SIGINT, signal.SIGTERM)}
    try:
        with os.fdopen(os.open(BASE / (PREFIX + '.stdout.json'), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as output:
            child = subprocess.Popen(COMMAND, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT)
            child_id = identity(child.pid)
            startup = {'schema': 1, 'started_utc': start, 'wrapper': identity(os.getpid()), 'preflight': child_id, 'command': COMMAND}
            save('.owner.json', startup); print(json.dumps(startup), flush=True)
            code = child.wait(); output.flush(); os.fsync(output.fileno())
        parsed = json.loads(read(BASE / (PREFIX + '.stdout.json')))
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
                         hashlib.sha256(read(AUDIT / 'result.json')).hexdigest() == AUDIT_SHA and not os.path.lexists(WORK))
            accepted = bool(code == 0 and not error and not forced and not cleanup_errors and unchanged and
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
                'before': before, 'after': observation(), 'boot_execution_requested': False}
            save('.exit.json', receipt)
            print('FIRSTBOOT READ-ONLY PREFLIGHT', parsed.get('status'), 'accepted=', accepted, 'boot_requested=false')
            print('exit=', code, 'reaped=', receipt['preflight_reaped'], 'forced=', forced, 'cleanup_errors=', cleanup_errors)
            print('stdout_sha256=', receipt['stdout_sha256'], 'bytes=', len(stdout))
            print('guard_sha256=', session.get('guard_source_sha256'))
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
