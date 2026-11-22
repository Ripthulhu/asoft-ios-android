import datetime
import hashlib
import json
import os
import pathlib
import signal
import stat
import subprocess

BASE = pathlib.Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
OWNER = BASE / 'ios26-disks-retry-f4d64db'

def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def read_json(name):
    path = BASE / name
    if path.resolve(strict=True) != path or not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError('noncanonical or nonregular input: ' + name)
    return json.loads(path.read_text())

def create(name, body):
    fd = os.open(OWNER / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as out:
        json.dump(body, out, indent=2)
        out.write('\n')
        out.flush()
        os.fsync(out.fileno())

def identity(pid):
    raw = (pathlib.Path('/proc') / str(pid) / 'stat').read_text()
    return {'pid': pid, 'starttime': int(raw[raw.rfind(')') + 2:].split()[19])}

old = read_json('ios26-disk-exit-f4d64db.json')
command = read_json('ios26-disk-retry-command-f4d64db.json')
preflight = read_json('ios26-disk-retry-preflight-f4d64db.json')
check = read_json('ios26-disk-retry-preflight-exit-f4d64db.json')
expected = [part for part in old['command'] if part not in ('-u', '--execute')]
expected += ['--helper-seconds', '21600']
assert old['exit_code'] == 2 and old['finished_utc']
assert command == expected and check['command'] == command and check['exit_code'] == 0
assert hashlib.sha256((BASE / 'ios26-disk-retry-preflight-f4d64db.json').read_bytes()).hexdigest() == check['stdout_sha256']
assert preflight['status'] == 'PREFLIGHT_READY'
assert preflight['completed'] == ['shared-fetch', 'shared-unpack', 'shared-build', 'ios26-fetch', 'ios26-decrypt']
assert preflight['remaining'] == ['ios26-rootfs', 'ios26-partition']
assert preflight['guest_boot_stages'] == [] and preflight['network_stages'] == []
assert '--allow-guest-boots' not in command and command[command.index('--through') + 1] == 'ios26-partition'
assert os.geteuid() == 0 and BASE.resolve(strict=True) == BASE
OWNER.mkdir(mode=0o700)
command.insert(1, '-u')
command.append('--execute')
create('command.json', command)
start = utc()
child = None
forced = False
error = None
returncode = None
cleanup_errors = []

def interrupted(number, frame):
    raise InterruptedError('outer owner signal ' + str(number))

old_handlers = {s: signal.signal(s, interrupted) for s in (signal.SIGINT, signal.SIGTERM)}
try:
    fd = os.open(OWNER / 'run.log', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as log:
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        create('owner.json', {'schema': 1, 'started_utc': start, 'wrapper': identity(os.getpid()), 'runner': identity(child.pid), 'command': command})
        returncode = child.wait()
except BaseException as exc:
    error = type(exc).__name__ + ': ' + str(exc)
    for s in old_handlers:
        signal.signal(s, signal.SIG_IGN)
    try:
        if child is not None and child.poll() is None:
            child.send_signal(signal.SIGTERM)
            try:
                child.wait(timeout=60)
            except subprocess.TimeoutExpired:
                forced = True
                child.kill()
                child.wait(timeout=30)
    except BaseException as cleanup_error:
        cleanup_errors.append(type(cleanup_error).__name__ + ': ' + str(cleanup_error))
    if child is not None:
        returncode = child.returncode
finally:
    try:
        for s in old_handlers:
            signal.signal(s, signal.SIG_IGN)
        create('exit.json', {'schema': 1, 'started_utc': start, 'finished_utc': utc(), 'exit_code': returncode, 'command': command, 'wrapper_error': error, 'forced_runner': forced, 'cleanup_errors': cleanup_errors, 'runner_started': child is not None, 'runner_reaped': child is not None and returncode is not None, 'requires_owned_process_recheck': True})
    finally:
        for s, handler in old_handlers.items():
            signal.signal(s, handler)
raise SystemExit(2 if error is not None or forced or cleanup_errors or returncode != 0 else 0)
