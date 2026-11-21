#!/usr/bin/env python3
"""Freeze a full package and verified delta from the passed TPIDRRO package."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent
BASE_SHA = '78e6174366fa3522fdcef0e1eca3f606ea3601823148bb69a31e4ecd18c42a35'
BASE_SIZE = 58516208


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def zip_tree(root, output, prefix=''):
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for path in sorted(p for p in root.rglob('*') if p.is_file()):
            item = zipfile.ZipInfo(prefix + path.relative_to(root).as_posix(), (2026, 11, 21, 0, 0, 0))
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = (0o100000 | (path.stat().st_mode & 0o777)) << 16
            z.writestr(item, path.read_bytes())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for arg in ('base', 'engine-source', 'engine-build', 'owner-build', 'out'):
        p.add_argument('--' + arg, type=Path, required=True)
    a = p.parse_args()
    out = a.out.resolve(); out.mkdir(parents=True, exist_ok=False)
    old = a.base.resolve(); old_binary = old / 'qemu-system-aarch64'
    assert old_binary.stat().st_size == BASE_SIZE and sha(old_binary) == BASE_SHA
    binary = a.engine_build / 'qemu-system-aarch64'
    binary_sha = sha(binary)
    engine_record = json.loads((a.engine_build / 'build.json').read_text())
    for name, expected in engine_record['sources'].items():
        assert sha(a.engine_source / name) == expected
    assert (a.engine_source / 'target/arm/tcg/native_gpu_protocol.h').read_bytes() == (ROOT / 'native_gpu_protocol.h').read_bytes()
    owner_record = json.loads((a.owner_build / 'owner-build.json').read_text())
    for name, expected in owner_record['source_sha256'].items():
        assert sha(ROOT / name) == expected
    assert sha(a.owner_build / 'native-gpu-owner') == owner_record['owner']['sha256']
    assert sha(a.owner_build / 'native-gpu-guest.elf') == owner_record['guest']['sha256']
    name = 'qemu26-native-gpu-one-region-' + binary_sha[:8]
    package = out / name; package.mkdir()
    shutil.copytree(old / 'lib', package / 'lib')
    for file in ('el0bench.elf', 'native-el0-tpidrro-trap-smoke.sh'):
        shutil.copy2(old / file, package / file)
    shutil.copy2(binary, package / 'qemu-system-aarch64')
    for file in ('native-gpu-owner', 'native-gpu-guest.elf', 'run-one-region.sh',
                 'owner-build.json', 'engine-guard-checks.json'):
        shutil.copy2(a.owner_build / file, package / file)
    shutil.copy2(ROOT / 'native_gpu_protocol.h', package / 'native_gpu_protocol.h')
    patch = subprocess.check_output(['git', 'diff', 'HEAD', '--', 'target/arm/tcg/native-el0.c',
            'target/arm/tcg/native-el0.h', 'hw/arm/virt.c', 'meson.build'], cwd=a.engine_source)
    header = (ROOT / 'native_gpu_protocol.h').read_text().splitlines()
    patch += ('diff --git a/target/arm/tcg/native_gpu_protocol.h b/target/arm/tcg/native_gpu_protocol.h\n'
              'new file mode 100644\n--- /dev/null\n+++ b/target/arm/tcg/native_gpu_protocol.h\n'
              f'@@ -0,0 +1,{len(header)} @@\n' + ''.join('+' + line + '\n' for line in header)).encode()
    (package / 'qemu-native-gpu-combined.patch').write_bytes(patch)
    subprocess.run(['git', 'apply', '--check', '--reverse', str(package / 'qemu-native-gpu-combined.patch')],
                   cwd=a.engine_source, check=True)
    (package / 'README.txt').write_text('''Isolated Pixel 10 Pro XL scalar native/GPU proof.

First run: /system/bin/sh run-one-region.sh --memfd-control
After a successful control: /system/bin/sh run-one-region.sh --gpu

Each invocation creates a private results directory and verifies every package
file before executing. All six credentialed native events must be persisted and
acknowledged. A clean QEMU exit and complete descendant reap are mandatory before
the GPU may read the allocation. No producer atomic operations are requested.

The fixed ten-instruction native EL0 payload reads a GPU-filled input and writes
one aligned eight-byte output. Code, page tables and stack use ordinary memfd RAM.
The helper independently checks all 8192 words through a GPU copy/readback after
the native workers have stopped. The producer is HOST_CACHED, with explicit full
allocation flush/invalidate and serialized handoffs. There is no uncached fallback.

EL1 setup uses TCG; the fixed EL0 payload is required to run in the native worker.
This is not a general guest-RAM, producer-atomics, concurrent CPU/GPU, app UID,
Metal/iOS frame-rendering or iOS 26 boot qualification. A kernel panic cannot be
contained by userspace timeouts. Product GPU gating remains unchanged.

native-el0-tpidrro-trap-smoke.sh is the previously qualified two-CPU register
regression runner; it does not enable this new GPU-provider mode.
''')
    write_json(package / 'manifest.json', {
        'scope': 'fixed scalar native EL0 / one 16KiB view of 32KiB cached allocation',
        'status_at_package_freeze': 'HOST_CHECKS_PASS_DEVICE_TEST_PENDING',
        'base_commit': engine_record['base_commit'], 'engine_sources': engine_record['sources'],
        'qemu_sha256': binary_sha, 'qemu_bytes': binary.stat().st_size,
        'owner': owner_record['owner'], 'guest': owner_record['guest'],
        'payload_sha256': owner_record['payload_page_sha256'],
        'review': 'Root source review and host tests; no completed independent worker review (authentication blocked)',
        'initial_native_warnings': 11, 'virt_warnings': 0,
        'ordinary_memfd_control_required_before_GPU': True})
    executable = {'qemu-system-aarch64', 'native-gpu-owner', 'run-one-region.sh', 'native-el0-tpidrro-trap-smoke.sh'}
    for path in package.rglob('*'):
        if path.is_file(): path.chmod(0o755 if path.name in executable or path.parent.name == 'lib' else 0o644)
    (package / 'SHA256SUMS').write_text(''.join(sha(path) + '  ' + path.relative_to(package).as_posix() + '\n'
        for path in sorted(p for p in package.rglob('*') if p.is_file())))
    full_zip = out / (name + '.zip'); zip_tree(package, full_zip, name + '/')
    update = out / 'update-package'; update.mkdir(); (update / 'payload').mkdir()
    delta = update / 'qemu-delta.zst'
    subprocess.run(['zstd', '--single-thread', '-19', '--long=27', '--patch-from=' + str(old_binary),
                    str(binary), '-o', str(delta)], check=True, timeout=120)
    # zstd copies input permissions to its compressed output, and decompression
    # propagates them again. Transfer data must never carry executable bits.
    delta.chmod(0o600)
    files = []
    for path in sorted(p for p in package.rglob('*') if p.is_file()):
        rel = path.relative_to(package).as_posix()
        source = 'delta' if rel == 'qemu-system-aarch64' else 'base' if rel.startswith('lib/') or rel == 'el0bench.elf' else 'payload'
        files.append({'name': rel, 'source': source, 'bytes': path.stat().st_size,
                      'sha256': sha(path), 'mode': path.stat().st_mode & 0o777})
        if source == 'base': assert sha(old / rel) == sha(path)
        elif source == 'payload':
            dest = update / 'payload' / rel; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest)
    manifest = {'format': 'pixel-qemu-zstd-update-v1', 'package_name': name,
                'base_binary_bytes': BASE_SIZE, 'base_binary_sha256': BASE_SHA,
                'target_binary_sha256': binary_sha, 'delta_name': delta.name,
                'delta_sha256': sha(delta), 'delta_bytes': delta.stat().st_size,
                'full_package_zip_sha256': sha(full_zip), 'files': files}
    write_json(update / 'update.json', manifest)
    template = ROOT.parents[1] / 'ios26-build/tpidrro-transfer/install-update.py'
    installer = template.read_text()
    replacements = {'UPDATE_MANIFEST_SHA': sha(update / 'update.json'),
                    'PACKAGE_MANIFEST_SHA': sha(package / 'SHA256SUMS'),
                    'BASE_SHA': BASE_SHA, 'BASE_SIZE': BASE_SIZE, 'TARGET_SHA': binary_sha,
                    'TARGET_SIZE': binary.stat().st_size, 'PACKAGE_NAME': name}
    for key, value in replacements.items():
        installer, count = re.subn(r'^' + key + r' = .+$', key + ' = ' + repr(value), installer, flags=re.M)
        assert count == 1
    installer = installer.replace('len(files) != 22', 'len(files) != ' + str(len(files)))
    installer = installer.replace('pixel-tpidrro-verified-', 'pixel-native-gpu-verified-')
    installer = installer.replace('package / "native-el0-tpidrro-trap-smoke.sh"', 'package / "run-one-region.sh"')
    (update / 'install-update.py').write_text(installer)
    update_zip = out / 'native-gpu-update.zip'; zip_tree(update, update_zip)
    with tempfile.TemporaryDirectory(prefix='native-gpu-delta-check-') as work:
        result = subprocess.check_output(['python3', str(update / 'install-update.py'), str(old), work, shutil.which('zstd')], text=True, timeout=45)
        decoded = json.loads(result)
        reconstructed = Path(decoded['package'])
        for entry in files: assert sha(reconstructed / entry['name']) == entry['sha256']
    encoded = base64.b64encode(update_zip.read_bytes()).decode()
    (out / 'update-base64.txt').write_text(encoded)
    record = {'package': str(package), 'package_files': len(files),
        'full_zip': {'path': str(full_zip), 'sha256': sha(full_zip), 'bytes': full_zip.stat().st_size},
        'update_zip': {'path': str(update_zip), 'sha256': sha(update_zip), 'bytes': update_zip.stat().st_size},
        'installer_sha256': sha(update / 'install-update.py'), 'manifest_sha256': sha(update / 'update.json'),
        'base_binary_sha256': BASE_SHA, 'target_binary_sha256': binary_sha,
        'host_reconstruction': 'PASS all frozen files matched; QEMU not executed'}
    write_json(out / 'package.json', record)
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
