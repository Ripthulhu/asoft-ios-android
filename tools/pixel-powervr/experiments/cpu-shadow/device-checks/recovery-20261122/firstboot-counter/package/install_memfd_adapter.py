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
TARGET = BASE / 'run-ios26-firstboot-memfd-adapter-counter1.py'
RECEIPT = BASE / 'ios26-firstboot-memfd-adapter-counter1-install.json'
EXPECTED_BYTES = 9104
EXPECTED_SHA256 = '1402321c22ae98b0ba7094f9e121cb169f2bf4aea38d0272b957f08a26259725'
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
