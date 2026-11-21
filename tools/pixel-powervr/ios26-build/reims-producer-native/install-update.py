#!/usr/bin/env python3
"""Reconstruct a hash-pinned owner in a fresh directory; execute no diagnostic."""
import hashlib
import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile

UPDATE_MANIFEST_SHA = '89cd23679295a245099fde4ab02e31a1225fb983726a8c2a99775e761612f63c'
BASE_SHA = 'a815e121d487c15cd9c1cec75ca6f43a48b2edf1ab42675bb9cde988b9679145'
BASE_SIZE = 58529200


def sha(path):
    with path.open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def check(path, digest, size):
    if path.is_symlink() or not path.is_file() or path.stat().st_size != size or sha(path) != digest:
        raise RuntimeError('File identity mismatch: ' + str(path))


def main():
    if len(sys.argv) != 4:
        raise SystemExit('Usage: install-update.py /verified/engine-package /output-parent /path/to/zstd')
    os.umask(0o077)
    here = Path(__file__).resolve().parent
    engine, parent, zstd = [Path(p) for p in sys.argv[1:]]
    if any(not p.is_absolute() for p in (engine, parent, zstd)):
        raise RuntimeError('All supplied paths must be absolute')
    base = engine / 'qemu-system-aarch64'
    check(base, BASE_SHA, BASE_SIZE)
    manifest = here / 'update.json'
    if manifest.is_symlink() or sha(manifest) != UPDATE_MANIFEST_SHA:
        raise RuntimeError('Update manifest identity mismatch')
    spec = json.loads(manifest.read_text())
    if spec['format'] != 'pixel-reims-native-update-v1':
        raise RuntimeError('Unknown format')
    name = spec['package_name']
    if not name.startswith('reims-native-gpu-') or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in name):
        raise RuntimeError('Invalid package name')
    files = spec['files']
    wanted = {'reims-native-gpu-owner', 'run.sh', 'owner-build.json', 'reims-build.json',
              'reims_vgpu.h', 'README.txt', 'SHA256SUMS'}
    if len(files) != len(wanted) or {x['name'] for x in files} != wanted:
        raise RuntimeError('Unexpected package file set')
    delta = here / 'owner-delta.zst'
    check(delta, spec['delta_sha256'], spec['delta_bytes'])
    if delta.stat().st_mode & 0o111:
        raise RuntimeError('Transfer delta must not be executable')
    for item in files:
        expected_source = 'delta' if item['name'] == 'reims-native-gpu-owner' else 'payload'
        expected_mode = 0o755 if item['name'] in {'reims-native-gpu-owner', 'run.sh'} else 0o644
        if item['source'] != expected_source or item['mode'] != expected_mode:
            raise RuntimeError('Invalid source or final mode')
        if expected_source == 'payload':
            check(here / 'payload' / item['name'], item['sha256'], item['bytes'])
    if {p.name for p in (here / 'payload').iterdir()} != wanted - {'reims-native-gpu-owner'}:
        raise RuntimeError('Unexpected payload file')
    # Nothing is written until the complete input and base identities have passed.
    private = Path(tempfile.mkdtemp(prefix='pixel-reims-verified-', dir=parent))
    package = private / name
    package.mkdir(mode=0o700)
    owner = package / 'reims-native-gpu-owner'
    subprocess.run([str(zstd), '-d', '-q', '--memory=128MB', '--patch-from=' + str(base),
                    str(delta), '-o', str(owner)], check=True, timeout=30)
    if owner.stat().st_mode & 0o111:
        raise RuntimeError('Unverified decoder output is executable')
    for item in files:
        dest = package / item['name']
        if item['source'] == 'payload':
            with dest.open('xb') as output:
                output.write((here / 'payload' / item['name']).read_bytes())
        check(dest, item['sha256'], item['bytes'])
    check(base, BASE_SHA, BASE_SIZE)
    if {p.name for p in package.iterdir()} != wanted:
        raise RuntimeError('Unexpected reconstructed file')
    # Only fully verified files acquire their final executable permissions.
    for item in files:
        (package / item['name']).chmod(item['mode'])
    result = {'package': str(package), 'engine': str(engine), 'files_verified': len(files),
              'owner_sha256': sha(owner), 'diagnostic_executed': False}
    (private / 'installation-result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
