#!/usr/bin/env python3
"""Install only the byte-pinned outer owner source and an exclusive receipt."""
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
TARGET = BASE / 'run-ios26-firstboot-owner-memfd1.py'
RECEIPT = BASE / 'ios26-firstboot-owner-memfd1-install.json'
EXPECTED_BYTES = 24980
EXPECTED_SHA256 = '771742c200d2d64c54cdd18db7bcd1cba4fc242999f16376531e0d9803f9a3d5'
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
            receipt = {'schema': 1, 'kind': 'firstboot_outer_owner_source_install',
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
