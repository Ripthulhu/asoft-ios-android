#!/usr/bin/env python3
"""Freeze a standalone reims owner and locally verify its delta reconstruction."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent
BASE_SHA = 'a815e121d487c15cd9c1cec75ca6f43a48b2edf1ab42675bb9cde988b9679145'


def sha(path):
    with path.open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def zip_tree(root, path, prefix=''):
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source in sorted(p for p in root.rglob('*') if p.is_file()):
            info = zipfile.ZipInfo(prefix + source.relative_to(root).as_posix(), (2026, 11, 21, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100000 | (source.stat().st_mode & 0o777)) << 16
            archive.writestr(info, source.read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'owner-build', 'reims-build', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    old = args.base.resolve()
    base = old / 'qemu-system-aarch64'
    assert base.stat().st_size == 58529200 and sha(base) == BASE_SHA
    owner_record = json.loads((args.owner_build / 'owner-build.json').read_text())
    reims_record = json.loads((args.reims_build / 'provenance/reims-build.json').read_text())
    assert reims_record['exit_code'] == 0 and reims_record['source_stable_during_build']
    assert reims_record['dependency_stable_during_build']
    for root, snapshot in [(Path(reims_record['source']), reims_record['source_after']),
                           (Path(reims_record['metal2vulkan_source']), reims_record['dependency_after'])]:
        for name, expected in snapshot['changed_files_sha256'].items():
            assert (not (root / name).exists()) if expected is None else sha(root / name) == expected
    assert owner_record['archive_sha256'] == reims_record['static_library']['sha256']
    for name, expected in owner_record['source_sha256'].items():
        assert sha(ROOT / name) == expected
    owner = args.owner_build / 'reims-native-gpu-owner'
    assert sha(owner) == owner_record['owner']['sha256']
    header = args.reims_build / 'reims-dist/include/reims_vgpu.h'
    assert sha(header) == owner_record['header_sha256']
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    name = 'reims-native-gpu-' + sha(owner)[:8]
    package = out / name
    package.mkdir()
    for source, dest in [(owner, 'reims-native-gpu-owner'), (ROOT / 'run.sh', 'run.sh'),
                         (args.owner_build / 'owner-build.json', 'owner-build.json'),
                         (args.reims_build / 'provenance/reims-build.json', 'reims-build.json'),
                         (header, 'reims_vgpu.h')]:
        shutil.copyfile(source, package / dest)
    (package / 'README.txt').write_text(
        'Explicit reims producer -> required native EL0 -> runtime GPU readback.\n'
        'Run: /system/bin/sh run.sh /absolute/verified/qemu26-native-gpu-one-region-a815e121\n'
        'The runner verifies both packages and retains logs in a new results directory.\n'
        'This package does not replace the app, change its GPU gate, or qualify iOS boot.\n'
        'No producer atomics, concurrent ownership, or general guest-memory remapping.\n')
    for path in package.iterdir():
        path.chmod(0o755 if path.name in {'reims-native-gpu-owner', 'run.sh'} else 0o644)
    (package / 'SHA256SUMS').write_text(''.join(
        sha(p) + '  ' + p.name + '\n' for p in sorted(package.iterdir())))
    (package / 'SHA256SUMS').chmod(0o644)
    full_zip = out / (name + '.zip')
    zip_tree(package, full_zip, name + '/')
    update = out / 'update-package'
    update.mkdir()
    (update / 'payload').mkdir()
    delta = update / 'owner-delta.zst'
    subprocess.run(['zstd', '--single-thread', '-19', '--long=27', '--patch-from=' + str(base),
                    str(owner), '-o', str(delta)], check=True, timeout=180)
    delta.chmod(0o600)
    files = []
    for path in sorted(package.iterdir()):
        source = 'delta' if path.name == 'reims-native-gpu-owner' else 'payload'
        files.append({'name': path.name, 'source': source, 'bytes': path.stat().st_size,
                      'sha256': sha(path), 'mode': path.stat().st_mode & 0o777})
        if source == 'payload':
            shutil.copyfile(path, update / 'payload' / path.name)
    write_json(update / 'update.json', {'format': 'pixel-reims-native-update-v1',
        'package_name': name, 'delta_sha256': sha(delta), 'delta_bytes': delta.stat().st_size,
        'files': files})
    installer = (ROOT / 'install-update.py').read_text().replace(
        "UPDATE_MANIFEST_SHA = 'SET_BY_PACKAGE_BUILDER'", 'UPDATE_MANIFEST_SHA = ' + repr(sha(update / 'update.json')))
    (update / 'install-update.py').write_text(installer)
    update_zip = out / 'reims-native-update.zip'
    zip_tree(update, update_zip)
    with tempfile.TemporaryDirectory(prefix='reims-native-reconstruct-') as temp:
        result = json.loads(subprocess.check_output(['python3', str(update / 'install-update.py'),
            str(old), temp, shutil.which('zstd')], text=True, timeout=45))
        for item in files:
            assert sha(Path(result['package']) / item['name']) == item['sha256']
    encoded = base64.b64encode(update_zip.read_bytes()).decode()
    (out / 'update-base64.txt').write_text(encoded)
    record = {'package': str(package), 'files': len(files),
        'owner_sha256': sha(owner), 'base_binary_sha256': BASE_SHA,
        'full_zip': {'path': str(full_zip), 'bytes': full_zip.stat().st_size, 'sha256': sha(full_zip)},
        'update_zip': {'path': str(update_zip), 'bytes': update_zip.stat().st_size, 'sha256': sha(update_zip)},
        'installer_sha256': sha(update / 'install-update.py'),
        'host_reconstruction': 'PASS; all bytes verified; diagnostic not executed'}
    write_json(out / 'package.json', record)
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
