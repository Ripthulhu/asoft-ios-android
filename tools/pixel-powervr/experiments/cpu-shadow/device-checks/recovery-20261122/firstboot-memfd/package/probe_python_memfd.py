#!/usr/bin/env python3
"""Report Python/libc capabilities; --smoke uses one ephemeral sealed memfd page.

No persistent file, VM, process, policy change or module monkey-patch.
"""
import argparse
import ctypes
import datetime
import errno
import fcntl
import json
import mmap
import os
import stat
import sys

# AOSP bionic linux/memfd.h: MFD_CLOEXEC=0x0001, MFD_ALLOW_SEALING=0x0002.
MFD_CLOEXEC, MFD_ALLOW_SEALING = 1, 2
SEAL_NAMES = ('F_ADD_SEALS', 'F_GET_SEALS', 'F_SEAL_GROW', 'F_SEAL_SHRINK', 'F_SEAL_SEAL')


def probe(smoke=False):
    result = {'schema': 1, 'observed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'python': sys.version, 'executable': sys.executable, 'platform': sys.platform,
              'page_bytes': os.sysconf('SC_PAGE_SIZE'), 'os_memfd_create': hasattr(os, 'memfd_create'),
              'os_constants': {n: getattr(os, n, None) for n in ('MFD_CLOEXEC', 'MFD_ALLOW_SEALING')},
              'fcntl_constants': {n: getattr(fcntl, n, None) for n in ('F_GETFD', 'FD_CLOEXEC', *SEAL_NAMES)},
              'smoke_requested': smoke, 'persistent_files_created': False, 'vm_started': False}
    library = ctypes.CDLL(None, use_errno=True)
    function = getattr(library, 'memfd_create', None)
    result['libc_memfd_create_symbol'] = function is not None
    if not smoke: return result
    fd = mapping = None
    detail = result['smoke'] = {'status': 'INCOMPLETE', 'flags': 3, 'mapping_closed': False, 'fd_closed': False}
    try:
        if function is None: raise RuntimeError('libc memfd_create symbol unavailable; no fallback')
        if any(type(getattr(fcntl, n, None)) is not int for n in ('F_GETFD', 'FD_CLOEXEC', *SEAL_NAMES)):
            raise RuntimeError('required Python fcntl constants unavailable')
        for name, expected in (('MFD_CLOEXEC', 1), ('MFD_ALLOW_SEALING', 2)):
            if hasattr(os, name) and getattr(os, name) != expected: raise ValueError('unexpected ' + name)
        if (fcntl.F_SEAL_GROW, fcntl.F_SEAL_SHRINK, fcntl.F_SEAL_SEAL) != (4, 2, 1):
            raise ValueError('seal bits differ from reviewed Linux UAPI')
        size = result['page_bytes']
        if not 1024 <= size <= 65536: raise ValueError('unsupported bounded page size')
        function.argtypes = [ctypes.c_char_p, ctypes.c_uint]; function.restype = ctypes.c_int
        ctypes.set_errno(0)
        fd = function(b'pixel-python-memfd-probe', MFD_CLOEXEC | MFD_ALLOW_SEALING)
        if fd < 0:
            error = ctypes.get_errno(); fd = None
            raise OSError(error, os.strerror(error))
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 0 or info.st_size != 0:
            raise ValueError('unexpected anonymous memfd identity')
        detail['cloexec'] = bool(fcntl.fcntl(fd, fcntl.F_GETFD) & fcntl.FD_CLOEXEC)
        detail['inheritable'] = os.get_inheritable(fd)
        if not detail['cloexec'] or detail['inheritable']: raise ValueError('CLOEXEC contract failed')
        os.ftruncate(fd, size)
        seals = fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL
        fcntl.fcntl(fd, fcntl.F_ADD_SEALS, seals)
        detail['seals'] = fcntl.fcntl(fd, fcntl.F_GET_SEALS)
        if detail['seals'] != seals: raise ValueError('seal readback differs')
        mapping = mmap.mmap(fd, size)
        payload = b'pixel-memfd-probe'
        mapping[:len(payload)] = payload
        detail['mapped_readwrite'] = mapping[:len(payload)] == payload
        detail['fd_read_alias'] = os.pread(fd, len(payload), 0) == payload
        for name, target in (('grow', size + 1), ('shrink', size - 1)):
            try: os.ftruncate(fd, target)
            except OSError as exc:
                detail[name + '_refused_errno'] = exc.errno
                if exc.errno != errno.EPERM: raise
            else: raise ValueError('sealed ' + name + ' unexpectedly succeeded')
        if not detail['mapped_readwrite'] or not detail['fd_read_alias']: raise ValueError('memfd mapping alias differs')
        detail.update(status='MEMFD_SMOKE_PASSED', bytes=size)
    except Exception as exc:
        detail.update(status='INCOMPLETE', error=type(exc).__name__ + ': ' + str(exc))
    finally:
        for name, item, closer in (('mapping', mapping, lambda value: value.close()), ('fd', fd, os.close)):
            if item is not None:
                try: closer(item); detail[name + '_closed'] = True
                except Exception as exc: detail.update(status='INCOMPLETE', cleanup_error=type(exc).__name__ + ': ' + str(exc))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke', action='store_true'); parser.add_argument('--json', action='store_true')
    args = parser.parse_args(); result = probe(args.smoke)
    if args.json: print(json.dumps(result, indent=2), flush=True)
    else:
        print('MEMFD CAPABILITY', result['observed_utc'])
        print('python=', result['python'].splitlines()[0], 'platform=', result['platform'], 'page_bytes=', result['page_bytes'])
        print('os.memfd_create=', result['os_memfd_create'], 'os_constants=', json.dumps(result['os_constants']))
        print('fcntl_constants=', json.dumps(result['fcntl_constants']))
        print('libc.memfd_create=', result['libc_memfd_create_symbol'], 'smoke_requested=', result['smoke_requested'])
        if 'smoke' in result: print('ephemeral_smoke=', json.dumps(result['smoke'], separators=(',', ':')))
        print('persistent_files_created=false vm_started=false')
    raise SystemExit(0 if not args.smoke or result.get('smoke', {}).get('status') == 'MEMFD_SMOKE_PASSED' else 2)
