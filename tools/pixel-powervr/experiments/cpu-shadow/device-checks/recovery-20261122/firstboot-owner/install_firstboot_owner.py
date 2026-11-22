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
TARGET = BASE / 'run-ios26-firstboot-owner-ebbc9c0.py'
RECEIPT = BASE / 'ios26-firstboot-owner-ebbc9c0-install.json'
EXPECTED_BYTES = 18957
EXPECTED_SHA256 = '605f194f89cc59dd4025e587a0fc2239920b0850e089943bca9e9ea0656eee57'
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
