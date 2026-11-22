#!/usr/bin/env python3
"""Install only the byte-pinned process-local memfd adapter and an exclusive receipt."""
import base64
import datetime
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import stat

BASE = Path('/data/local/tmp/pixel-gpu-transfer-sxtv33sh')
TARGET = BASE / 'run-ios26-firstboot-memfd-adapter-memfd1.py'
RECEIPT = BASE / 'ios26-firstboot-memfd-adapter-memfd1-install.json'
EXPECTED_BYTES = 9097
EXPECTED_SHA256 = 'e981d6d561b821641a6993b2aa96b84fa63776ccd1a7bc8cb314d1261ae899a8'
PAYLOAD = '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'


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def install():
    if os.geteuid() != 0 or BASE.resolve(strict=True) != BASE or not BASE.is_dir():
        raise ValueError('root and canonical existing transfer directory required')
    if os.path.lexists(TARGET) or os.path.lexists(RECEIPT):
        raise FileExistsError('source or install receipt already exists; preserve both')
    compressed = base64.b64decode(PAYLOAD, validate=True)
    with gzip.GzipFile(fileobj=io.BytesIO(compressed), mode='rb') as stream:
        source = stream.read(EXPECTED_BYTES + 1)
    if len(source) != EXPECTED_BYTES or hashlib.sha256(source).hexdigest() != EXPECTED_SHA256:
        raise ValueError('embedded source length or SHA256 differs')
    # Reserve both names before writing. An interrupted staging attempt remains
    # visible and cannot be retried over an existing source or receipt.
    source_fd = os.open(TARGET, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    try:
        receipt_fd = os.open(RECEIPT, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(source_fd, 'wb', closefd=False) as stream:
                stream.write(source)
                stream.flush()
                os.fsync(stream.fileno())
            os.fchmod(source_fd, 0o644)
            os.fsync(source_fd)
            check_fd = os.open(TARGET, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(check_fd, 'rb') as stream:
                info = os.fstat(stream.fileno())
                copied = stream.read(EXPECTED_BYTES + 1)
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or
                    info.st_size != EXPECTED_BYTES or info.st_uid != 0 or
                    stat.S_IMODE(info.st_mode) != 0o644 or copied != source):
                raise ValueError('installed source identity or readback differs')
            receipt = {'schema': 1, 'kind': 'firstboot_memfd_adapter_source_install',
                       'installed_utc': utc(), 'source': str(TARGET), 'bytes': len(copied),
                       'sha256': hashlib.sha256(copied).hexdigest(), 'mode': '0644',
                       'execution_started': False, 'auditor_sources_changed': False,
                       'frozen_runner_changed': False}
            with os.fdopen(receipt_fd, 'w', closefd=False) as stream:
                json.dump(receipt, stream, indent=2)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            directory = os.open(BASE, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
            return receipt
        finally:
            os.close(receipt_fd)
    finally:
        os.close(source_fd)


def main():
    try:
        print(json.dumps(install(), indent=2), flush=True)
        return 0
    except Exception as exc:
        print(json.dumps({'schema': 1, 'status': 'SOURCE_INSTALL_REFUSED_OR_INCOMPLETE',
                          'error': type(exc).__name__ + ': ' + str(exc),
                          'execution_started': False, 'preserve_existing_artifacts': True}), flush=True)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
