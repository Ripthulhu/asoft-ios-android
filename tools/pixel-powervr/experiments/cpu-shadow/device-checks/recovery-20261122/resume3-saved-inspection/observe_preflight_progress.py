"""Read-only fixed-path liveness/progress and selected early-refusal diagnosis."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import stat
import time

BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
SOURCE = BASE / 'run-ios26-saved-inspection-resume3.py'
SOURCE_PIN = {'bytes': 48469, 'sha256': '91ac3ba2ba8c3e40b2a99dfffdc4a53ae49b8e441245755f33ef761846d61e14'}
OWNER = BASE / 'ios26-saved-inspection-resume3-owner'
WORK = Path('/data/local/tmp/pixel-saved-audit-e9cc754-resume3')
LAUNCH = BASE / 'ios26-saved-inspection-resume3-preflight-launch.json'
LOG = BASE / 'ios26-saved-inspection-resume3-preflight-wrapper.log'
WRAPPER = {'pid': 6603, 'starttime': 9193748}
PYTHON = '/data/data/com.termux/files/usr/bin/python'
COMMAND = [PYTHON, '-I', '-B', '/data/local/tmp/pixel-saved-checks-resume3/inspect_ios26_firstboot.py',
    '--guard-work', '/data/local/tmp/pixel-firstboot-guard-e9cc754-resume1', '--work', str(WORK)]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path, limit):
    require(path.resolve(strict=True) == path, 'noncanonical fixed input')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as f:
        a = os.fstat(f.fileno())
        require(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and a.st_uid == 0 and a.st_size <= limit, 'nonordinary or oversized fixed input')
        body = f.read(limit + 1)
        z = os.fstat(f.fileno())
    require(len(body) == a.st_size <= limit and (a.st_dev, a.st_ino, a.st_size, a.st_mtime_ns, a.st_ctime_ns) ==
            (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns), 'fixed input changed while read')
    return body


def optional_json(path, limit=65536):
    if not os.path.lexists(path):
        return None
    body = read(path, limit)
    try:
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeError):
        return {'json_available': False}


def proc_body(pid, name, limit):
    with os.fdopen(os.open(Path('/proc') / str(pid) / name, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as f:
        body = f.read(limit + 1)
    require(len(body) <= limit, 'task proc metadata exceeded bound')
    return body


def proc_stat(expected):
    try:
        body = proc_body(expected['pid'], 'stat', 4096)
    except (FileNotFoundError, ProcessLookupError):
        return None
    left, right = body.find(b'('), body.rfind(b')')
    require(0 < left < right and int(body[:left].strip()) == expected['pid'], 'invalid task stat')
    fields = body[right + 1:].split()
    require(len(fields) >= 22, 'short task stat')
    if int(fields[19]) != expected['starttime']:
        return None
    return {'pid': expected['pid'], 'starttime': int(fields[19]), 'state': fields[0].decode('ascii'),
        'parent_pid': int(fields[1]), 'process_group': int(fields[2]), 'session': int(fields[3]),
        'cpu_ticks': int(fields[11]) + int(fields[12]), 'rss_pages': int(fields[21]), 'virtual_bytes': int(fields[20])}


def snapshot(expected):
    first = proc_stat(expected)
    if first is None:
        return {'expected': expected, 'present': False}
    io = None
    try:
        lines = proc_body(expected['pid'], 'io', 4096).decode('ascii').splitlines()
        allowed = {'rchar', 'wchar', 'syscr', 'syscw', 'read_bytes', 'write_bytes', 'cancelled_write_bytes'}
        io = {name: int(value) for name, value in (line.split(':', 1) for line in lines) if name in allowed}
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        pass
    wait_channel = None
    try:
        wait_channel = proc_body(expected['pid'], 'wchan', 256).decode('ascii').strip()
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        pass
    last = proc_stat(expected)
    if last is None:
        return {'expected': expected, 'present': False, 'ended_during_sample': True}
    return {'expected': expected, 'present': True, 'process': last, 'io': io, 'wait_channel': wait_channel}


def main():
    require(os.geteuid() == 0, 'root fixed metadata reader required')
    source = read(SOURCE, SOURCE_PIN['bytes'])
    require({'bytes': len(source), 'sha256': hashlib.sha256(source).hexdigest()} == SOURCE_PIN, 'reviewed owner source differs')
    launch = json.loads(read(LAUNCH, 65536))
    require(launch.get('status') == 'PREFLIGHT_OWNER_LAUNCHED' and launch.get('source_sha256') == SOURCE_PIN['sha256'] and
            launch.get('command') == [PYTHON, '-I', '-B', str(SOURCE), '--preflight'] and
            {k: launch.get('wrapper', {}).get(k) for k in WRAPPER} == WRAPPER,
            'actual scoped preflight launch differs')
    started = optional_json(OWNER / 'preflight-owner.json')
    identities = {'wrapper': WRAPPER}
    if started is not None and started.get('json_available') is not False:
        require(started.get('schema') == 1 and started.get('wrapper') == WRAPPER and started.get('command') == COMMAND,
                'recorded preflight runner scope differs')
        runner = started.get('runner')
        require(type(runner) is dict and set(runner) == {'pid', 'starttime'} and
                all(type(runner[k]) is int and runner[k] > 0 for k in runner), 'invalid recorded runner identity')
        identities['runner'] = runner
    first = {name: snapshot(value) for name, value in identities.items()}
    time.sleep(1)
    second = {name: snapshot(value) for name, value in identities.items()}
    for name, value in second.items():
        before = first[name]
        if before.get('present') is True and value.get('present') is True:
            value['cpu_ticks_delta'] = value['process']['cpu_ticks'] - before['process']['cpu_ticks']
            if before.get('io') is not None and value.get('io') is not None:
                value['io_delta'] = {key: value['io'][key] - before['io'][key] for key in value['io'].keys() & before['io'].keys()}
    files = {}
    paths = [LOG, *(OWNER / name for name in ('prerequisites.json', 'preflight-command.json', 'preflight-owner.json', 'preflight.json', 'preflight-exit.json'))]
    for path in paths:
        if not os.path.lexists(path):
            files[str(path)] = {'present': False}
            continue
        require(path.resolve(strict=True) == path, 'noncanonical fixed status path')
        st = path.stat()
        require(stat.S_ISREG(st.st_mode) and st.st_uid == 0 and st.st_nlink == 1, 'nonordinary fixed status file')
        files[str(path)] = {'present': True, 'bytes': st.st_size}
    refusal = optional_json(LOG, 16384)
    selected_refusal = None
    if refusal is not None and refusal.get('status') == 'OWNER_REFUSED':
        require(type(refusal.get('error')) is str and len(refusal['error']) <= 1200, 'refusal exceeds selected metadata bound')
        selected_refusal = {'status': 'OWNER_REFUSED', 'error': refusal['error']}
    ended = optional_json(OWNER / 'preflight-exit.json')
    selected_exit = None if ended is None else {key: ended.get(key) for key in
        ('exit_code', 'owner_exit_code', 'accepted', 'runner_reaped', 'forced_runner', 'cleanup_errors', 'wrapper_error')}
    require(read(SOURCE, SOURCE_PIN['bytes']) == source, 'owner source changed during observation')
    print(json.dumps({'schema': 1, 'status': 'SAVED_INSPECTION_PREFLIGHT_SCOPED_DIAGNOSTIC', 'readonly': True,
        'observed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'started_utc': launch.get('started_utc'),
        'sample_interval_seconds': 1, 'clock_ticks_per_second': os.sysconf('SC_CLK_TCK'),
        'owner_directory_present': OWNER.exists(), 'inspection_work_present': WORK.exists(),
        'processes': second, 'fixed_file_sizes': files, 'selected_owner_refusal': selected_refusal, 'selected_preflight_exit': selected_exit,
        'source_unchanged': True, 'native_or_guest_command_started': False, 'raw_logs_or_broad_process_inventory_exported': False}, separators=(',', ':')), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status': 'PREFLIGHT_SCOPED_DIAGNOSTIC_REFUSED', 'readonly': True,
            'error': type(error).__name__ + ': ' + str(error)}, separators=(',', ':')), flush=True)
        raise SystemExit(2)
