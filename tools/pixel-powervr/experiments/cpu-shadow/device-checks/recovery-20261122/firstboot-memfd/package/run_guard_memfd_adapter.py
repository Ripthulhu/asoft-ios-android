#!/usr/bin/env python3
"""Add only Android Python's three missing memfd attributes for the frozen guard.

Default is the unchanged guard's read-only preflight. --execute is explicit.
The adapter is process-local; no frozen source, Python installation or policy changes.
"""
import argparse
import ctypes
import datetime
import hashlib
import json
import operator
import os
from pathlib import Path
import stat
import sys

BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
SOURCE = BASE / 'run-ios26-firstboot-memfd-adapter-memfd1.py'
GUARD = Path('/data/local/tmp/pixel-boot-checks-ebbc9c0/firstboot/guard_ios26_firstboot.py')
GUARD_SHA = '8f98fafd603385b5d3aa20331acc7e536020b6ae136f8690bd190efbeb09845c'
WORK = Path('/data/local/tmp/pixel-firstboot-guard-e9cc754-memfd1')
PYTHON = '/data/data/com.termux/files/usr/bin/python'
SMOKE = BASE / 'python-memfd-smoke-memfd1.json'
SMOKE_SHA = '57d7239160422a858ed9882191c5012fd20a20d5b790f482be15013266f313bd'
PROBE_SHA = '069232bec27b8775499941bf52da9f4e076d8a8b3ee14171510691cbbf010225'
GUARD_ARGS = ['--audit-work', '/data/local/tmp/pixel-audit-e9cc754',
              '--auditor-dir', '/data/local/tmp/pixel-boot-checks-ebbc9c0/auditor',
              '--runner-dir', '/data/local/tmp/pixel-prep-runner-f4d64db', '--work', str(WORK)]
NAMES = ('memfd_create', 'MFD_CLOEXEC', 'MFD_ALLOW_SEALING')


def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat()


def require(value, message):
    if not value: raise ValueError(message)


def read(path, limit=2 << 20):
    require(path.is_absolute() and path.resolve(strict=True) == path, 'noncanonical input')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= limit, 'nonordinary/oversized input')
        body = stream.read(limit + 1)
    require(len(body) <= limit, 'input exceeded bound')
    return body


def sha(body): return hashlib.sha256(body).hexdigest()


def identity(pid):
    try:
        with Path('/proc/{}/stat'.format(pid)).open('rb') as stream: body = stream.read(4097)
    except FileNotFoundError: return None
    require(len(body) <= 4096, 'oversized process stat')
    return {'pid': pid, 'starttime': int(body[body.rfind(b')') + 2:].split()[19])}


def save(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as stream:
        json.dump(value, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    fd = os.open(BASE, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def accepted_smoke():
    body = read(SMOKE); captured = json.loads(body)
    require(sha(body) == SMOKE_SHA and captured.get('schema') == 1 and
            captured.get('probe_source_sha256') == PROBE_SHA and captured.get('probe_source_bytes') == 5677 and
            captured.get('invocation') == 'exact reviewed module definitions; probe(True)' and
            captured.get('receipt_file_created') is True, 'captured libc smoke bytes or provenance differ')
    evidence = captured.get('probe', {}); detail = evidence.get('smoke', {})
    require(evidence.get('schema') == 1 and evidence.get('smoke_requested') is True and
            evidence.get('libc_memfd_create_symbol') is True and evidence.get('os_memfd_create') is False and
            evidence.get('os_constants') == {'MFD_CLOEXEC': None, 'MFD_ALLOW_SEALING': None} and
            evidence.get('persistent_files_created') is False and evidence.get('vm_started') is False and
            detail.get('status') == 'MEMFD_SMOKE_PASSED' and detail.get('flags') == 3 and detail.get('seals') == 7 and
            detail.get('bytes') == evidence.get('page_bytes') == 4096 and detail.get('inheritable') is False and
            detail.get('grow_refused_errno') == detail.get('shrink_refused_errno') == 1 and
            all(detail.get(k) is True for k in ('cloexec', 'mapped_readwrite', 'fd_read_alias', 'mapping_closed', 'fd_closed')),
            'exact libc memfd smoke evidence differs')
    return {'source_sha256': PROBE_SHA, 'receipt': str(SMOKE), 'receipt_sha256': sha(body),
            'receipt_bytes': len(body), 'observed_utc': evidence['observed_utc'], 'status': detail['status']}


def libc_adapter():
    # CPython 3.14.8 uses FSConverter and unsigned-int flags; bionic exports this
    # exact libc ABI. Linux UAPI defines CLOEXEC=1 and ALLOW_SEALING=2.
    library = ctypes.CDLL(None, use_errno=True)
    function = library.memfd_create
    function.argtypes = [ctypes.c_char_p, ctypes.c_uint]; function.restype = ctypes.c_int
    mask = (1 << (ctypes.sizeof(ctypes.c_uint) * 8)) - 1

    def memfd_create(name, flags=1):
        encoded = os.fsencode(name)
        if b'\0' in encoded: raise ValueError('embedded null byte')
        requested = operator.index(flags) & mask
        fd = function(encoded, requested)
        if fd == -1:
            saved_errno = ctypes.get_errno()
            raise OSError(saved_errno, os.strerror(saved_errno))
        return fd
    return memfd_create


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--execute', action='store_true')
    args = parser.parse_args(); phase = 'execute' if args.execute else 'preflight'
    prefix = BASE / ('ios26-firstboot-memfd1-adapter-' + phase)
    require(os.geteuid() == 0 and BASE.resolve(strict=True) == BASE, 'canonical root transfer directory required')
    require(Path(__file__).resolve(strict=True) == SOURCE, 'unexpected adapter source path')
    require(Path(sys.executable).resolve(strict=True) == Path(PYTHON).resolve(strict=True), 'unexpected Python interpreter')
    require(sys.flags.isolated == 1 and sys.dont_write_bytecode, 'adapter requires actual Python -I -B mode')
    require(not os.path.lexists(WORK), 'fresh guard work required; preserve existing evidence')
    for suffix in ('.owner.json', '.exit.json'):
        require(not os.path.lexists(Path(str(prefix) + suffix)), 'adapter receipt already exists; preserve it')
    source_body, guard_body = read(SOURCE), read(GUARD)
    require(sha(guard_body) == GUARD_SHA, 'frozen guard bytes changed')
    smoke = accepted_smoke()
    missing = [name for name in NAMES if not hasattr(os, name)]
    require(missing == list(NAMES), 'Python capabilities changed from reviewed missing-attribute contract')
    replacement = libc_adapter()
    original_argv = sys.argv[:]; guard_argv = [str(GUARD), *GUARD_ARGS] + (['--execute'] if args.execute else [])
    actual_argv = [PYTHON, '-I', '-B', str(SOURCE)] + (['--execute'] if args.execute else [])
    started = utc(); process = identity(os.getpid()); added = []
    startup = {'schema': 1, 'kind': 'process_local_android_memfd_adapter', 'started_utc': started, 'process': process,
               'phase': phase, 'command': actual_argv, 'guard_argv': guard_argv, 'adapter_source_sha256': sha(source_body),
               'guard_source_sha256': GUARD_SHA, 'missing_attributes': missing, 'installed_attributes': list(NAMES),
               'constants': {'MFD_CLOEXEC': 1, 'MFD_ALLOW_SEALING': 2}, 'libc_symbol': 'memfd_create',
               'libc_abi': 'int(const char *, unsigned int)', 'accepted_libc_smoke': smoke,
               'frozen_sources_changed': False, 'system_python_changed': False, 'boot_execution_requested': args.execute}
    save(Path(str(prefix) + '.owner.json'), startup)
    code, error, restored = 2, None, False
    try:
        for name, value in (('memfd_create', replacement), ('MFD_CLOEXEC', 1), ('MFD_ALLOW_SEALING', 2)):
            setattr(os, name, value); added.append(name)
        sys.argv = guard_argv
        namespace = {'__name__': '__main__', '__file__': str(GUARD), '__package__': None, '__spec__': None, '__cached__': None}
        try: exec(compile(guard_body, str(GUARD), 'exec'), namespace)
        except SystemExit as exc:
            code = 0 if exc.code is None else exc.code
            require(type(code) is int, 'guard returned a noninteger exit status')
    except BaseException as exc:
        code, error = 2, type(exc).__name__ + ': ' + str(exc)
    finally:
        sys.argv = original_argv
        for name in reversed(added): delattr(os, name)
        restored = all(not hasattr(os, name) for name in NAMES)
        unchanged = sha(read(GUARD)) == GUARD_SHA and sha(read(SOURCE)) == startup['adapter_source_sha256']
        save(Path(str(prefix) + '.exit.json'), {**startup, 'finished_utc': utc(), 'exit_code': code,
             'error': error, 'attributes_restored': restored, 'sources_unchanged': unchanged,
             'adapter_completed': code == 0 and error is None and restored and unchanged})
    return code if error is None and restored and unchanged else 2


if __name__ == '__main__':
    try: raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({'schema': 1, 'status': 'MEMFD_ADAPTER_REFUSED_OR_INCOMPLETE', 'error': type(exc).__name__ + ': ' + str(exc)}), flush=True)
        raise SystemExit(2)
