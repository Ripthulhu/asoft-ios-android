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
TARGET = BASE / 'run-ios26-partition-audit-ebbc9c0.py'
RECEIPT = BASE / 'ios26-partition-audit-ebbc9c0-install.json'
EXPECTED_BYTES = 18144
EXPECTED_SHA256 = 'af4b1478e37b52cf223bc86bf41df2c23f83d31dd5de287cfaabe64d0983bfe7'
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
            receipt = {'schema': 1, 'kind': 'partition_audit_outer_owner_source_install',
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
