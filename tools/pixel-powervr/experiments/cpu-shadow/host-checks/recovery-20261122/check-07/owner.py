#!/usr/bin/env python3
"""Own one offline xtask check; preparing this file does not launch a check.

Run only with --execute. The repository, dependencies, test selection, and xtask
are unchanged. Polling observes failures/resources; it is not a realtime limit.
"""
import argparse
import ctypes
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import select
import shutil
import signal
import stat
import subprocess
import sys
import time

WORK = Path('/workspace/scratch/abcabc3f01ae/host-clock-fix/clock-worktree')
RUNTIME = Path('/workspace/scratch/abcabc3f01ae/host-clock-fix/metal2vulkan-full')
ROOT = Path('/workspace/scratch/abcabc3f01ae/host-clock-fix/runs')
TOOL_ENV = Path('/workspace/scratch/abcabc3f01ae/host-tooling/environment.json')
FORMAT_PATCH = Path('/workspace/scratch/abcabc3f01ae/host-clock-fix/combined-clock.patch')
FORMAT_RECEIPT = Path('/workspace/scratch/abcabc3f01ae/host-clock-fix/candidate.json')
LLVM_AS = Path('/workspace/scratch/abcabc3f01ae/host-tooling/android-ndk-r29/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-as')
LLVM_BUILD = Path('/workspace/scratch/abcabc3f01ae/asoft-ios-android/tools/pixel-powervr/experiments/cpu-shadow/host-checks/xtask-bda933b-clippy-clock-stop/llvm-as-runtime-build.json')
PINS = {
    str(FORMAT_PATCH): '8f43fac1cd27b5e3e83ac69157141479f3e1bc17111306d5d2ad16c282013c7d',
    str(FORMAT_RECEIPT): '20dde5ad598a10d97329957235d0542ffd83c02e7e801fa8effb79faf0b39b8d',
    str(LLVM_AS): '3c9a80d96a7c71624c0ce7cc2c36ef71032a8fb2e772dd0fde26ddda568b80cc',
    str(LLVM_BUILD): '038e5561de1b726ec90796644c6b7879cd849929f06fa8e54c6b575c7680c0ec',
    str(TOOL_ENV): '41299067f9c6ac1bd997a8925d727b8347a5d9a5976575d01dd32c2c0326848f',
}
COMMAND = ['cargo', '+1.98.1', 'run', '--offline', '--locked', '--package', 'xtask', '--', 'check']
BASE_COMMIT = '64c224c273b11b7e70f430c742b8be2787062e67'
COMMIT = '917149fcaecce24bf69b3cb2d6394e44158c7c93'
FORMATTING = json.loads(FORMAT_RECEIPT.read_text())
RUNTIME_COMMIT = 'fddefd8803535bb84ebcd55593adf5cc15231bac'
MIB = 1024 ** 2
GIB = 1024 ** 3
START_MEMORY = 4 * GIB
MEMORY_FLOOR = 768 * MIB
DISK_FLOOR = 1536 * MIB
HEADROOM = 128 * MIB
ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
FAILURES = [
    ('compiler_or_cargo', re.compile(r'^\s*error(?:\[[A-Z][0-9]+\])?:')),
    ('rustfmt', re.compile(r'^Diff in .+:\d+(?::|$)')),
    ('header', re.compile(r'^header: .*(?:differs from cbindgen|not compared)')),
    ('xtask', re.compile(r'^xtask check:|^check: FAILED$')),
    ('nextest', re.compile(r'^\s*(?:FAIL|TIMEOUT|EXECFAIL|ABORT|SIGABRT|SIGSEGV|SIGILL|SIGBUS|SIGFPE|SIGKILL)\s+\[')),
    ('libtest', re.compile(r'^test .+ \.\.\. FAILED$|^test result: FAILED\.')),
    ('cmake', re.compile(r'^CMake Error(?: at|:)')),
]


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(MIB), b''):
            h.update(block)
    return h.hexdigest()


def sha_prefix(path, size):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        remaining = size
        while remaining:
            block = stream.read(min(MIB, remaining))
            if not block:
                raise RuntimeError('raw log truncated during bounded hashing')
            h.update(block)
            remaining -= len(block)
    return h.hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def write_new(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def git(work, *args):
    return subprocess.check_output(
        ['git', '--no-optional-locks', '-C', str(work), *args],
        env={'PATH': '/usr/bin:/bin', 'HOME': '/home/agent', 'LC_ALL': 'C.UTF-8'},
        stderr=subprocess.PIPE, timeout=120)


def snapshot(work, out, label):
    """Hash actual source bytes and retain exact tracked/staged changes, not just HEAD."""
    patches = {}
    for kind, args in [('worktree', []), ('staged', ['--cached'])]:
        data = git(work, 'diff', '--binary', '--no-ext-diff', '--no-textconv', *args)
        name = f'{label}-{kind}.patch'
        write_new(out / name, data)
        patches[kind] = {'file': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    paths = set(git(work, 'ls-files', '-z', '--cached', '--others', '--exclude-standard').split(b'\0'))
    files = {}
    for raw in sorted(paths - {b''}):
        name = os.fsdecode(raw)
        p = work / name
        try:
            s = p.lstat()
        except FileNotFoundError:
            files[name] = {'type': 'missing'}
            continue
        row = {'mode': stat.S_IMODE(s.st_mode)}
        if stat.S_ISREG(s.st_mode):
            row.update(type='file', bytes=s.st_size, sha256=sha(p))
        elif stat.S_ISLNK(s.st_mode):
            row.update(type='symlink', target=os.readlink(p))
        elif stat.S_ISDIR(s.st_mode):
            # Gitlinks are recorded, not traversed. The check does not build vendor/QEMU.
            row.update(type='gitlink', index=git(work, 'ls-files', '--stage', '--', name).decode())
        else:
            raise RuntimeError(f'unsupported source type: {p}')
        files[name] = row
    identity = {
        'root': str(work), 'commit': git(work, 'rev-parse', 'HEAD').decode().strip(),
        'tree': git(work, 'rev-parse', 'HEAD^{tree}').decode().strip(),
        'status_hex': git(work, 'status', '--porcelain=v1', '-z', '--untracked-files=all').hex(),
        'files': files, 'diff_sha256': {k: v['sha256'] for k, v in patches.items()},
    }
    write_new(out / f'{label}-source.json', encoded(identity))
    return {'source': f'{label}-source.json', 'sha256': sha(out / f'{label}-source.json'),
            'identity_sha256': hashlib.sha256(encoded(identity)).hexdigest(),
            'commit': identity['commit'], 'status_hex': identity['status_hex'],
            'tracked_and_untracked_paths': len(files), 'patches': patches}


def resource(paths):
    text = Path('/proc/meminfo').read_text()
    rows = re.findall(r'^MemAvailable:\s+([0-9]+) kB$', text, re.M)
    if len(rows) != 1:
        raise RuntimeError('missing/malformed MemAvailable')
    disks = {str(p): shutil.disk_usage(p).free for p in paths}
    return {'utc': utc(), 'monotonic': time.monotonic(), 'available_bytes': int(rows[0]) * 1024,
            'disk_free_bytes': disks}


def proc(pid):
    try:
        p = Path('/proc') / str(pid)
        raw = (p / 'stat').read_text()
        name, rest = raw.rsplit(')', 1)
        fields = rest.split()
        return {'pid': pid, 'state': fields[0], 'ppid': int(fields[1]), 'pgrp': int(fields[2]),
                'session': int(fields[3]), 'start_ticks': int(fields[19]), 'uid': p.stat().st_uid,
                'name': name.split('(', 1)[1], 'user_cpu_ticks': int(fields[11]),
                'system_cpu_ticks': int(fields[12])}
    except (FileNotFoundError, ProcessLookupError):
        return None


def process_table():
    result = {}
    for p in Path('/proc').iterdir():
        if p.name.isdigit():
            row = proc(int(p.name))
            if row:
                result[row['pid']] = row
    return result


def owned_processes(known):
    """Only recorded identities, their descendants, and this subreaper's adopted children."""
    table = process_table()
    owned = {pid for pid, start in known.items() if pid in table and table[pid]['start_ticks'] == start}
    owned.update(pid for pid, row in table.items() if row['ppid'] == os.getpid())
    while True:
        new = {pid for pid, row in table.items() if row['ppid'] in owned}
        if new <= owned:
            break
        owned.update(new)
    for pid in owned:
        known[pid] = table[pid]['start_ticks']
    return [table[pid] for pid in sorted(owned)]


def pin_processes(rows, handles):
    """Retain identities so cleanup can still signal them if later /proc discovery fails."""
    for row in rows:
        key = (row['pid'], row['start_ticks'])
        if key in handles:
            continue
        try:
            fd = os.pidfd_open(row['pid'])
        except ProcessLookupError:
            continue
        try:
            actual = proc(row['pid'])
            if actual and actual['start_ticks'] == row['start_ticks']:
                handles[key] = fd
                fd = None
        finally:
            if fd is not None:
                os.close(fd)


def live_handles(handles):
    poller = select.poll()
    for fd in handles.values():
        poller.register(fd, select.POLLIN)
    ended = {fd for fd, event in poller.poll(0) if event & select.POLLIN}
    return [key for key, fd in handles.items() if fd not in ended]


def close_exited_handles(handles):
    # A full nextest run can create thousands of processes; exited pidfds need no retention.
    live = set(live_handles(handles))
    for key, fd in list(handles.items()):
        if key not in live:
            os.close(fd)
            del handles[key]


def stop_pinned(child, handles):
    """Scanner-failure fallback: bounded cleanup of held identities, never a full-tree PASS."""
    report = {'complete': False, 'requires_owned_process_recheck': True, 'signals': [], 'reaped': []}
    for sig, seconds in [(signal.SIGTERM, 30), (signal.SIGKILL, 10)]:
        for (pid, start), fd in handles.items():
            try:
                signal.pidfd_send_signal(fd, sig)
                report['signals'].append({'pid': pid, 'start_ticks': start, 'signal': sig})
            except ProcessLookupError:
                pass
        # Until Popen reaps its own leader, its PID/group cannot be recycled.
        if child.returncode is None:
            try:
                os.killpg(child.pid, sig)
            except ProcessLookupError:
                pass
        deadline = time.monotonic() + seconds
        while True:
            child.poll()
            for pid, start in handles:
                if pid != child.pid:
                    try:
                        reaped, status = os.waitpid(pid, os.WNOHANG)
                        if reaped:
                            report['reaped'].append({'pid': pid, 'wait_status': status})
                    except ChildProcessError:
                        pass
            alive = live_handles(handles)
            if not alive and child.poll() is not None:
                report['held_identities_exited'] = True
                return report
            if time.monotonic() >= deadline:
                report['held_identities_still_alive'] = alive
                break
            time.sleep(0.1)
    return report


def send_owned(rows, sig, events):
    # pidfds avoid a signal reaching a recycled PID. Repeated scans catch forks/adoption.
    for row in rows:
        if row['state'] == 'Z':
            continue
        try:
            fd = os.pidfd_open(row['pid'])
            try:
                actual = proc(row['pid'])
                if actual and actual['start_ticks'] == row['start_ticks']:
                    signal.pidfd_send_signal(fd, sig)
                    events.append({'pid': row['pid'], 'start_ticks': row['start_ticks'], 'signal': sig})
            finally:
                os.close(fd)
        except ProcessLookupError:
            pass


def cleanup(child, known, handles):
    events, reaped, errors = [], [], []
    # No new metadata subprocess is created until this owned tree is gone.
    for sig, seconds in [(signal.SIGTERM, 30), (signal.SIGKILL, 10)]:
        deadline = time.monotonic() + seconds
        sent = set()
        while True:
            child.poll()  # Reap the leader through Popen, preserving its exact return code.
            rows = owned_processes(known)
            pin_processes(rows, handles)
            for row in rows:
                if row['pid'] == child.pid:
                    continue
                try:
                    pid, status = os.waitpid(row['pid'], os.WNOHANG)
                    if pid:
                        reaped.append({'pid': pid, 'wait_status': status, 'exit_code': os.waitstatus_to_exitcode(status)})
                except ChildProcessError:
                    pass
            rows = owned_processes(known)
            if not rows and child.poll() is not None:
                if live_handles(handles):
                    raise RuntimeError('held descendant remains alive outside discovered tree; pinned fallback required')
                return {'signals': events, 'reaped': reaped, 'errors': errors, 'remaining': [], 'complete': True}
            try:
                fresh = [row for row in rows if (row['pid'], row['start_ticks']) not in sent]
                send_owned(fresh, sig, events)
                sent.update((row['pid'], row['start_ticks']) for row in fresh)
            except Exception as exc:
                errors.append(repr(exc))
            if time.monotonic() >= deadline:
                break
            time.sleep(0.1)
    child.poll()
    return {'signals': events, 'reaped': reaped, 'errors': errors,
            'remaining': owned_processes(known), 'complete': False}


def assembler_identity():
    info = LLVM_AS.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_size != 4105480
            or stat.S_IMODE(info.st_mode) != 0o755 or not os.access(LLVM_AS, os.X_OK)):
        raise RuntimeError('pinned llvm-as must remain the exact regular executable file')
    digest = sha(LLVM_AS)
    if digest != PINS[str(LLVM_AS)]:
        raise RuntimeError('pinned llvm-as bytes changed')
    return {'path': str(LLVM_AS), 'bytes': info.st_size, 'mode': stat.S_IMODE(info.st_mode),
            'sha256': digest, 'earlier_build_metadata': str(LLVM_BUILD),
            'earlier_build_metadata_sha256': PINS[str(LLVM_BUILD)]}


def read_inputs():
    """Bind the recovered source trees and current tool environment, never reuse a prior pass."""
    assembler_identity()
    for path, expected in PINS.items():
        if sha(path) != expected:
            raise RuntimeError(f'pinned input changed: {path}')
    if git(WORK, 'rev-parse', BASE_COMMIT + '^{tree}').decode().strip() != 'c603324e4e499668f5ae4133cfe14b39f4491275':
        raise RuntimeError('recovered base differs from the saved bda933b source tree')
    if git(WORK, 'rev-parse', COMMIT + '^{tree}').decode().strip() != FORMATTING['source_tree']:
        raise RuntimeError('wrong candidate tree')
    if git(RUNTIME, 'rev-parse', 'HEAD^{tree}').decode().strip() != '1b8c0eff2356c3a05cc372b6ea25e74cbdeff8d0':
        raise RuntimeError('wrong restored runtime tree')
    actual_patch = git(WORK, 'diff', '--binary', '--full-index', BASE_COMMIT, COMMIT,
                       '--')
    if actual_patch != FORMAT_PATCH.read_bytes():
        raise RuntimeError('source revision differs from reviewed clock patch')
    if sha(WORK / 'crates/reims-vgpu-vulkan/src/cpu_shadow_probe.rs') != FORMATTING['source_sha256']:
        raise RuntimeError('working probe differs from candidate')
    if sha(WORK / 'Cargo.lock') != 'a2dbc994dead0c1003f2917193b858a4f05713d952746cc6ae1a5936180c0e17':
        raise RuntimeError('Cargo resolution differs from the saved checkpoint')
    env = json.loads(TOOL_ENV.read_text())
    env.update(CARGO_BUILD_JOBS='1', CARGO_INCREMENTAL='0', CARGO_NET_OFFLINE='true',
               CARGO_PROFILE_DEV_DEBUG='0', CARGO_TARGET_DIR='/home/agent/.cache/reims-clock-recovery-target',
               NEXTEST_TEST_THREADS='1', NEXTEST_RETRIES='0', RUST_TEST_THREADS='1')
    for name in ['HOME', 'LANG', 'LC_ALL', 'TMPDIR']:
        if name in os.environ:
            env[name] = os.environ[name]
    env.setdefault('LANG', 'C.UTF-8')
    env.setdefault('LC_ALL', 'C.UTF-8')
    for name in ['cargo', 'rustc', 'rustfmt', 'clippy-driver', 'cbindgen', 'cargo-nextest', 'cmake']:
        if not shutil.which(name, path=env['PATH']):
            raise RuntimeError(f'required command absent: {name}')
    for name in ['VK_ICD_FILENAMES', 'VK_LAYER_PATH', 'CMAKE_PREFIX_PATH']:
        if not Path(env[name]).exists():
            raise RuntimeError(f'required path absent: {name}')
    Path(env['CARGO_TARGET_DIR']).mkdir(parents=True, exist_ok=True)
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--out', type=Path, default=ROOT / 'host-xtask-check-clock-07')
    args = parser.parse_args()
    if not args.execute:
        parser.error('prepared only; --execute is required to launch the check')
    out = args.out.absolute()
    if out.exists() or out.is_symlink() or out.parent.resolve() != ROOT.resolve():
        raise RuntimeError('output must be a fresh direct child of the evidence root')
    out.mkdir(mode=0o700)
    result = {'schema': 1, 'status': 'INCOMPLETE', 'started_utc': utc(), 'command': COMMAND,
              'cwd': str(WORK), 'cargo_exit_code': None, 'stop_reason': None,
              'source_unchanged': False, 'check_fully_passed': False,
              'physical_gpu_or_guest_boot_qualified': False}
    child = None
    known, handles, samples, first_failure = {}, {}, [], None
    interrupted = []
    lock_fd = None
    old_handlers = {}
    before = None
    def on_signal(signum, frame):
        interrupted.append(signum)
    try:
        lock_fd = os.open('/home/agent/.cache/reims-clock-recovery-check.lock',
                          os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for sig in [signal.SIGINT, signal.SIGTERM, signal.SIGHUP]:
            old_handlers[sig] = signal.signal(sig, on_signal)
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
            raise OSError(ctypes.get_errno(), 'could not become child subreaper')
        if not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
            raise RuntimeError('Linux pidfd support is required')
        env = read_inputs()
        target = Path(env['CARGO_TARGET_DIR'])
        # This is a coordination check, not a claim that every host process honors our lock.
        conflicts = []
        for pid, row in process_table().items():
            if pid == os.getpid():
                continue
            try:
                cmd = (Path('/proc') / str(pid) / 'cmdline').read_bytes().split(b'\0')
                penv = (Path('/proc') / str(pid) / 'environ').read_bytes().split(b'\0')
                if (b'CARGO_TARGET_DIR=' + os.fsencode(target)) in penv and any(
                        Path(os.fsdecode(x)).name in ['cargo', 'rustc', 'clippy-driver', 'xtask', 'cargo-nextest'] for x in cmd):
                    conflicts.append({'pid': pid, 'start_ticks': row['start_ticks']})
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                continue
        if conflicts:
            raise RuntimeError(f'candidate cache already has a build/test owner: {conflicts}')
        before = {name: snapshot(work, out, f'before-{name}')
                  for name, work in [('reims', WORK), ('metal2vulkan', RUNTIME)]}
        if before['reims']['commit'] != COMMIT or before['metal2vulkan']['commit'] != RUNTIME_COMMIT:
            raise RuntimeError('source revision changed')
        if before['reims']['status_hex'] != b' M Cargo.toml\0'.hex() or before['metal2vulkan']['status_hex']:
            raise RuntimeError('source changes differ from the local Cargo.toml path override and restored clean runtime')
        paths = [target, out, Path('/tmp')]
        launch = {'schema': 1, 'command': COMMAND, 'cwd': str(WORK), 'environment': env,
                  'source_before': before, 'input_receipts': PINS, 'owner_source_sha256': sha(__file__),
                  'approved_clock_revision': FORMATTING,
                  'pinned_llvm_assembler': assembler_identity(),
                  'target_resolved': str(target.resolve()), 'start_available_min': START_MEMORY,
                  'run_memory_floor': MEMORY_FLOOR, 'run_disk_floor': DISK_FLOOR,
                  'stop_headroom': HEADROOM, 'resource_sample_seconds': 1,
                  'log_poll_seconds': 0.25, 'termination_seconds': [30, 10],
                  'home_retained_for_cargo_unlike_direct_fixture': True,
                  'not_a_hard_realtime_resource_limit': True}
        write_new(out / 'owner.py', Path(__file__).read_bytes())
        write_new(out / 'approved-clock.patch', FORMAT_PATCH.read_bytes())
        write_new(out / 'clock-receipt.json', FORMAT_RECEIPT.read_bytes())
        write_new(out / 'llvm-as-runtime-build.json', LLVM_BUILD.read_bytes())
        write_new(out / 'launch.json', encoded(launch))
        raw_fd = os.open(out / 'check.log', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        sample_fd = os.open(out / 'resources.jsonl', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(raw_fd, 'wb', buffering=0) as raw, os.fdopen(sample_fd, 'wb', buffering=0) as sample_log:
            sample = resource(paths)
            samples.append(sample)
            sample_log.write(json.dumps(sample).encode() + b'\n')
            if sample['available_bytes'] < START_MEMORY or min(sample['disk_free_bytes'].values()) <= DISK_FLOOR + HEADROOM:
                raise RuntimeError('fresh launch resource floor not met')
            if interrupted:
                raise RuntimeError('interrupted before launch')
            # Popen and all subsequent owner writes are inside the cleanup-protected try.
            child = subprocess.Popen(COMMAND, cwd=WORK, env=env, stdin=subprocess.DEVNULL,
                                     stdout=raw, stderr=subprocess.STDOUT, start_new_session=True)
            handles[(child.pid, None)] = os.pidfd_open(child.pid)
            row = proc(child.pid)
            if row:
                known[child.pid] = row['start_ticks']
                handles[(child.pid, row['start_ticks'])] = handles.pop((child.pid, None))
            write_new(out / 'owner.json', encoded({'pid': child.pid, 'process': row, 'owner_pid': os.getpid(),
                                                  'utc': utc(), 'start_new_session': True, 'subreaper': True}))
            next_resource = time.monotonic() + 1
            pending, phase, offset = '', 'cargo run xtask build', 0
            with (out / 'check.log').open('rb') as reader:
                while True:
                    data = reader.read(MIB)
                    offset += len(data)
                    pending += data.decode('utf-8', errors='replace')
                    lines = pending.split('\n')
                    pending = lines.pop()
                    if len(pending) > MIB:
                        raise RuntimeError('unbounded raw-log line; retained complete raw bytes')
                    for raw_line in lines:
                        line = ANSI.sub('', raw_line).rstrip('\r')
                        if line.startswith('$ cargo '):
                            phase = line[2:]
                        for kind, pattern in FAILURES:
                            if pattern.search(line) and first_failure is None:
                                first_failure = {'utc': utc(), 'kind': kind, 'phase': phase,
                                                 'line': line, 'raw_read_offset': offset}
                    owned = owned_processes(known)
                    pin_processes(owned, handles)
                    close_exited_handles(handles)
                    if first_failure:
                        result['stop_reason'] = 'first_concrete_log_failure'
                        break
                    if interrupted:
                        result['stop_reason'] = 'owner_signal'
                        break
                    if time.monotonic() >= next_resource:
                        sample = resource(paths)
                        sample['owned_processes'] = owned
                        sample['clock_ticks_per_second'] = os.sysconf('SC_CLK_TCK')
                        samples.append(sample)
                        sample_log.write(json.dumps(sample).encode() + b'\n')
                        if sample['available_bytes'] <= MEMORY_FLOOR + HEADROOM or min(sample['disk_free_bytes'].values()) <= DISK_FLOOR + HEADROOM:
                            result['stop_reason'] = 'resource_headroom_reached'
                            break
                        next_resource = time.monotonic() + 1
                    if child.poll() is not None and not data:
                        break
                    time.sleep(0.25)
            raw.flush()
            os.fsync(raw.fileno())
    except BaseException as exc:
        result['error'] = repr(exc)
        result['stop_reason'] = result['stop_reason'] or 'owner_exception_or_preflight_refusal'
    finally:
        for sig in old_handlers:
            signal.signal(sig, signal.SIG_IGN)
        try:
            if child is not None:
                result['cleanup'] = cleanup(child, known, handles)
                result['cargo_exit_code'] = child.returncode
                if result['cleanup']['signals'] and result['stop_reason'] is None:
                    result['stop_reason'] = 'owned_descendants_needed_cleanup'
            else:
                result['cleanup'] = {'complete': True, 'remaining': [], 'signals': [], 'reaped': [], 'errors': []}
        except BaseException as exc:
            result['cleanup'] = {'complete': False, 'error': repr(exc), 'requires_owned_process_recheck': True}
            # Held pidfds still identify the same descendants if /proc discovery failed.
            # Unseen descendants remain unverified, so fallback can never grant PASS.
            try:
                if child is not None:
                    result['cleanup']['pinned_fallback'] = stop_pinned(child, handles)
            except BaseException as fallback:
                result['cleanup']['leader_fallback_error'] = repr(fallback)
            if child is not None:
                result['cargo_exit_code'] = child.returncode
        result['first_failure'] = first_failure
        result['signals_received'] = interrupted
        result['source_before'] = before
        try:
            if before is not None and result['cleanup'].get('complete'):
                after = {name: snapshot(work, out, f'after-{name}')
                         for name, work in [('reims', WORK), ('metal2vulkan', RUNTIME)]}
                result['source_after'] = after
                result['source_unchanged'] = all(before[k]['identity_sha256'] == after[k]['identity_sha256'] for k in before)
                result['assembler_after'] = assembler_identity()
                result['prior_receipts_unchanged'] = all(sha(p) == expected for p, expected in PINS.items())
            if (out / 'check.log').exists():
                size = (out / 'check.log').stat().st_size
                result['raw_log'] = {'bytes_observed': size, 'prefix_sha256': sha_prefix(out / 'check.log', size),
                                     'full_stable_log': bool(result['cleanup'].get('complete'))}
                # The observed prefix bounds both hashing and parsing even if cleanup failed.
                # A surviving writer never receives full-log acceptance.
                final_ok = False
                with (out / 'check.log').open('rb') as stream:
                    remaining = size
                    while remaining and result['cleanup'].get('complete'):
                        raw_line = stream.readline(min(MIB + 1, remaining))
                        if not raw_line:
                            raise RuntimeError('raw log truncated during final scan')
                        if len(raw_line) > MIB:
                            raise RuntimeError('oversized final raw-log line; full raw bytes retained')
                        remaining -= len(raw_line)
                        line = ANSI.sub('', raw_line.decode(errors='replace')).strip('\r\n')
                        final_ok |= line == 'check: ok'
                        for kind, pattern in FAILURES:
                            if pattern.search(line) and result['first_failure'] is None:
                                result['first_failure'] = {'kind': kind, 'line': line, 'observed_in_final_scan': True}
                if (out / 'check.log').stat().st_size != size:
                    result['raw_log']['full_stable_log'] = False
                    raise RuntimeError('raw log changed after cleanup')
                result['check_ok_marker'] = final_ok
            if 'paths' in locals():
                final_resource = resource(paths)
                samples.append(final_resource)
                write_new(out / 'after-resources.json', encoded(final_resource))
                if final_resource['available_bytes'] < MEMORY_FLOOR or min(final_resource['disk_free_bytes'].values()) < DISK_FLOOR:
                    result['stop_reason'] = result['stop_reason'] or 'final_resource_floor_violated'
            result['check_fully_passed'] = bool(child is not None and result['cargo_exit_code'] == 0
                and result.get('check_ok_marker') and result['stop_reason'] is None
                and result['first_failure'] is None and result['source_unchanged']
                and result.get('prior_receipts_unchanged') and result['cleanup']['complete']
                and not result['cleanup'].get('errors'))
            result['status'] = 'HOST_XTASK_CHECK_PASSED' if result['check_fully_passed'] else 'INCOMPLETE'
        except BaseException as exc:
            result['postcheck_error'] = repr(exc)
            result['check_fully_passed'] = False
            result['status'] = 'INCOMPLETE'
        try:
            result['finished_utc'] = utc()
            result['resource_samples'] = len(samples)
            result['minimum_observed_available_bytes'] = min((x['available_bytes'] for x in samples), default=None)
            result['known_owned_processes'] = known
            write_new(out / 'result.json', encoded(result))
        finally:
            for fd in handles.values():
                os.close(fd)
            if lock_fd is not None:
                os.close(lock_fd)
            for sig, old in old_handlers.items():
                signal.signal(sig, old)
    print(json.dumps({'status': result['status'], 'result': str(out / 'result.json'),
                      'cargo_exit_code': result['cargo_exit_code'], 'stop_reason': result['stop_reason']}), flush=True)
    return 0 if result['check_fully_passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
