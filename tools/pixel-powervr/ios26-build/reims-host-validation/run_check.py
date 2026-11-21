import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time

ROOT = Path('/workspace/scratch/4d73d97b75b7/reims-pixel-producer-runtime')
OUT = Path(__file__).resolve().parent
LVP = Path('/workspace/scratch/95f3cf369f81/tooling/lavapipe')

def snapshot():
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=ROOT)
    untracked = {}
    for name in filter(None, git('ls-files', '--others', '--exclude-standard', '-z').decode().split('\0')):
        p = ROOT / name
        if p.is_file():
            untracked[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    return {
        'head': git('rev-parse', 'HEAD').decode().strip(),
        'tracked_diff_sha256': hashlib.sha256(git('diff', '--binary', 'HEAD')).hexdigest(),
        'untracked_sha256': untracked,
        'lock_sha256': hashlib.sha256((ROOT / 'Cargo.lock').read_bytes()).hexdigest(),
    }

p = argparse.ArgumentParser()
p.add_argument('--validation', action='store_true')
p.add_argument('--cold-cache', action='store_true')
p.add_argument('--timeout', type=int, default=1800)
p.add_argument('label')
p.add_argument('command', nargs=argparse.REMAINDER)
a = p.parse_args()
assert re.fullmatch('[a-z0-9_-]+', a.label)
command = a.command[1:] if a.command[:1] == ['--'] else a.command
assert command
env = dict(os.environ)
selected = {
    'CARGO_TARGET_DIR': '/home/agent/.cache/reims-pixel-producer-runtime-target',
    'CARGO_BUILD_JOBS': '1',
    'RUSTFLAGS': '-Dwarnings',
    'CARGO_PROFILE_DEV_DEBUG': '0',
    'CARGO_PROFILE_TEST_DEBUG': '0',
    'CARGO_INCREMENTAL': '0',
    'NEXTEST_TEST_THREADS': '1',
    'RUST_TEST_THREADS': '1',
    'VK_ICD_FILENAMES': str(LVP / 'lvp-local.json'),
    'CMAKE_PREFIX_PATH': '/home/agent/.cache/reims-host-sdl-root/usr',
    'PKG_CONFIG_PATH': '/home/agent/.cache/reims-host-sdl-root/usr/lib/x86_64-linux-gnu/pkgconfig:/home/agent/.cache/reims-host-sdl-root/usr/share/pkgconfig',
}
env.update(selected)
env['PATH'] = ':'.join([
    '/home/agent/.cargo/bin',
    '/workspace/scratch/95f3cf369f81/tooling/nextest',
    '/workspace/scratch/4d73d97b75b7/producer-tools/bin',
    '/home/agent/.cache/reims-gate-tools/cmake/data/bin',
    '/home/agent/.cache/reims-gate-tools/bin',
    env['PATH'],
])
env['LD_LIBRARY_PATH'] = str(LVP / 'usr/lib/x86_64-linux-gnu') + ':/home/agent/.cache/reims-host-sdl-root/usr/lib/x86_64-linux-gnu:' + env.get('LD_LIBRARY_PATH', '')
if a.validation:
    selected.update({
        'VK_LAYER_PATH': str(LVP / 'layers'),
        'VK_INSTANCE_LAYERS': 'VK_LAYER_KHRONOS_validation',
        'VK_LAYER_ENABLES': 'VK_VALIDATION_FEATURE_ENABLE_SYNCHRONIZATION_VALIDATION_EXT',
        'VK_LOADER_DEBUG': 'error,warn,layer',
    })
    env.update(selected)
if a.cold_cache:
    cache = OUT / ('cache-' + a.label)
    cache.mkdir()
    selected['XDG_CACHE_HOME'] = str(cache)
    env['XDG_CACHE_HOME'] = str(cache)
    env.pop('HOME', None)
before = snapshot()
started = time.time()
timed_out = False
with (OUT / (a.label + '.log')).open('w') as log:
    child = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        code = child.wait(timeout=a.timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(child.pid, signal.SIGTERM)
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
        code = 124
after = snapshot()
record = {
    'command': command, 'cwd': str(ROOT), 'exit': code,
    'seconds': time.time() - started, 'timeout_seconds': a.timeout, 'timed_out': timed_out,
    'environment': selected, 'child_HOME_removed': a.cold_cache,
    'source_before': before, 'source_after': after, 'source_stable': before == after,
    'log': a.label + '.log',
    'log_sha256': hashlib.sha256((OUT / (a.label + '.log')).read_bytes()).hexdigest(),
}
(OUT / (a.label + '.json')).write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
print(json.dumps({k: record[k] for k in ['command', 'exit', 'seconds', 'source_stable', 'log']}, indent=2))
print((OUT / (a.label + '.log')).read_text(errors='replace')[-12000:])
raise SystemExit(code if code >= 0 else 128 - code)
