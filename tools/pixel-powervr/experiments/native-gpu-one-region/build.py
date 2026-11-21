#!/usr/bin/env python3
"""Build/review the isolated scalar owner and guest; never access the device."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, output):
    with output.open('w') as log:
        subprocess.run([str(x) for x in args], check=True, stdout=log, stderr=subprocess.STDOUT, timeout=60)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ndk', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    tools = a.ndk.resolve() / 'toolchains/llvm/prebuilt/linux-x86_64/bin'
    cc = tools / 'aarch64-linux-android35-clang'
    flags = ['-std=c11', '-O2', '-gline-tables-only', '-Wall', '-Wextra', '-Werror',
             '-fPIE', '-pie', '-ffunction-sections', '-fdata-sections',
             '-fdebug-prefix-map=' + str(ROOT.parent) + '=experiments',
             '-fmacro-prefix-map=' + str(ROOT.parent) + '=experiments',
             '-Wl,--gc-sections', '-Wl,--no-undefined', '-Wl,--build-id=sha1', '-Wl,-z,max-page-size=16384']
    owner = out / 'native-gpu-owner'
    run([cc, *flags, ROOT / 'owner.c', '-o', owner, '-lvulkan'], out / 'compile-owner.log')
    symbols = subprocess.check_output([str(tools / 'llvm-nm'), str(owner)], text=True)
    (out / 'owner-symbols.txt').write_text(symbols)
    for forbidden in ['cached_diagnostic_reference_main', 'memfd_control', 'na_exercise',
                      'na_atomic_calls', 'native_fd_roundtrip', 'native_code_cache_roundtrip',
                      'na_child_entry', 'na_cpu_memory_preflight']:
        if re.search(r'\b' + forbidden + r'$', symbols, re.M):
            raise RuntimeError('Unrelated legacy path survived section GC: ' + forbidden)
    run([tools / 'llvm-objdump', '-d', owner], out / 'owner-disassembly.txt')
    subprocess.run([str(tools / 'llvm-objcopy'), '--only-keep-debug', str(owner), str(out / 'native-gpu-owner.debug')], check=True)
    subprocess.run([str(tools / 'llvm-strip'), '--strip-unneeded', str(owner)], check=True)
    analysis = out / 'owner-analysis.plist'
    run([cc, '-std=c11', '-Wall', '-Wextra', '-Werror', '--analyze', '-Xclang',
         '-analyzer-output=plist', ROOT / 'owner.c', '-o', analysis], out / 'analysis.log')
    diagnostics = plistlib.loads(analysis.read_bytes()).get('diagnostics', [])
    if diagnostics:
        raise RuntimeError(f'Owner static analysis found {len(diagnostics)} diagnostics')
    run([tools / 'llvm-readelf', '-h', '-l', '-d', '--wide', owner], out / 'owner-elf.txt')
    elf = (out / 'owner-elf.txt').read_text()
    loads = [line for line in elf.splitlines() if re.match(r'\s*LOAD\s', line)]
    assert loads and all(int(line.split()[-1], 16) >= 16384 for line in loads)
    guest = out / 'native-gpu-guest.elf'
    run([tools / 'clang', '--target=aarch64-none-elf', '-nostdlib', '-Wl,-T,' + str(ROOT / 'guest.ld'),
         '-Wl,--build-id=none', '-Wl,-z,max-page-size=16384', ROOT / 'guest.S', '-o', guest], out / 'compile-guest.log')
    run([tools / 'llvm-readelf', '-h', '-l', '-s', '--wide', guest], out / 'guest-elf.txt')
    run([tools / 'llvm-objdump', '-d', guest], out / 'guest-disassembly.txt')
    page = out / 'payload-page.bin'
    subprocess.run([str(tools / 'llvm-objcopy'), '--dump-section', '.payload=' + str(page), str(guest)], check=True)
    code_sha = re.search(r'NGP_CODE_SHA256_HEX "([a-f0-9]+)"', (ROOT / 'native_gpu_protocol.h').read_text())[1]
    assert page.stat().st_size == 16384 and sha(page) == code_sha
    words = [0xd2c00022, 0x91401042, 0xf9400040, 0x93c03401, 0xd2009c21,
             0x9104dc21, 0xf9000441, 0xd289c8f0, 0xd4001001, 0xd4200000]
    assert page.read_bytes() == b''.join(w.to_bytes(4, 'little') for w in words) + bytes(16384 - 40)
    fixture = out / 'owner-host-fixture'
    run(['gcc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', ROOT / 'owner_fixture.c', '-o', fixture], out / 'compile-fixture.log')
    run([fixture], out / 'host-fixture.log')
    copied = ['native_gpu_protocol.h', 'owner.c', 'owner_control.h', 'owner_fixture.c',
              'guest.S', 'guest.ld', 'build.py', 'run-one-region.sh']
    cache = ROOT.parent / 'cached-memory'
    frozen = ['opaque_fd_probe.c', 'cpu_alias.h', 'cached_policy.h', 'native_code_cache.h',
              'native_code_cache_exec.h', 'native_cpu_memory.h', 'exec_diag.h']
    info = {'status': 'HOST_CHECKED_NOT_DEVICE_TESTED',
            'owner': {'bytes': owner.stat().st_size, 'sha256': sha(owner)},
            'guest': {'bytes': guest.stat().st_size, 'sha256': sha(guest)},
            'payload_page_sha256': code_sha, 'payload_instructions': 10,
            'source_sha256': {name: sha(ROOT / name) for name in copied},
            'frozen_Vulkan_source_sha256': {name: sha(cache / name) for name in frozen},
            'static_analysis_diagnostics': 0, 'legacy_entry_and_atomic_experiments_removed_by_section_GC': True,
            'host_fixture': {'sha256': sha(fixture), 'log_sha256': sha(out / 'host-fixture.log'),
                             'GPU_tested': False, 'Android_tested': False},
            'compiler': subprocess.check_output([str(cc), '--version'], text=True).strip()}
    (out / 'owner-build.json').write_text(json.dumps(info, indent=2) + '\n')
    shutil.copy2(ROOT / 'run-one-region.sh', out / 'run-one-region.sh')
    print(json.dumps({'owner': info['owner'], 'guest': info['guest'], 'host_checks': 'PASS'}))


if __name__ == '__main__':
    main()
