#!/usr/bin/env python3
"""Build the reims-backed native owner; do not run it or contact a device."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent / 'native-gpu-one-region'


def sha(path):
    with path.open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def run(command, output):
    with output.open('w') as log:
        subprocess.run([str(x) for x in command], stdout=log,
                       stderr=subprocess.STDOUT, check=True, timeout=120)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ndk', type=Path, required=True)
    parser.add_argument('--reims-dist', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    dist = args.reims_dist.resolve()
    archive = dist / 'lib/libreims_vgpu.a'
    header = dist / 'include/reims_vgpu.h'
    original = (BASE / 'owner.c').read_text()
    body = original[original.index('static void owner_signal'):original.index('static int ordinary_control')]
    adopted = (ROOT / 'native_owner.h').read_text()
    if adopted[adopted.index('static void owner_signal'):adopted.rindex('#endif')] != body:
        raise RuntimeError('The verified native supervisor changed')
    tools = args.ndk.resolve() / 'toolchains/llvm/prebuilt/linux-x86_64/bin'
    cc = tools / 'aarch64-linux-android35-clang'
    flags = ['-std=c11', '-O2', '-gline-tables-only', '-Wall', '-Wextra', '-Werror',
             '-fPIE', '-pie', '-ffunction-sections', '-fdata-sections',
             '-fdebug-prefix-map=' + str(ROOT.parent) + '=experiments',
             '-fmacro-prefix-map=' + str(ROOT.parent) + '=experiments',
             '-I' + str(header.parent), '-Wl,--gc-sections', '-Wl,--no-undefined',
             '-Wl,--build-id=sha1', '-Wl,-z,max-page-size=16384']
    owner = out / 'reims-native-gpu-owner'
    command = [cc, *flags, ROOT / 'owner.c', archive, '-o', owner,
               '-ldl', '-llog', '-lunwind', '-lm', '-lc']
    run(command, out / 'compile-owner.log')
    run([tools / 'llvm-nm', owner], out / 'owner-symbols.txt')
    symbols = (out / 'owner-symbols.txt').read_text()
    required = ['rvg_producer_create', 'rvg_producer_cpu_begin', 'rvg_producer_native_export',
                'rvg_producer_native_retire', 'rvg_producer_upload', 'rvg_producer_download']
    if any(not re.search(r'\b' + name + r'$', symbols, re.M) for name in required):
        raise RuntimeError('The actual producer C API was not linked')
    run([tools / 'llvm-objdump', '-d', '--disassemble-symbols=main,proof,run_engine', owner],
        out / 'owner-disassembly.txt')
    subprocess.run([str(tools / 'llvm-objcopy'), '--only-keep-debug', str(owner),
                    str(out / 'reims-native-gpu-owner.debug')], check=True)
    subprocess.run([str(tools / 'llvm-strip'), '--strip-unneeded', str(owner)], check=True)
    analysis = out / 'owner-analysis.plist'
    run([cc, '-std=c11', '-Wall', '-Wextra', '-Werror', '-I' + str(header.parent),
         '--analyze', '-Xclang', '-analyzer-output=plist', ROOT / 'owner.c', '-o', analysis],
        out / 'analysis.log')
    diagnostics = plistlib.loads(analysis.read_bytes()).get('diagnostics', [])
    if diagnostics:
        raise RuntimeError(f'Owner static analysis found {len(diagnostics)} diagnostics')
    run([tools / 'llvm-readelf', '-h', '-l', '-d', '--wide', owner], out / 'owner-elf.txt')
    elf = (out / 'owner-elf.txt').read_text()
    loads = [line for line in elf.splitlines() if re.match(r'\s*LOAD\s', line)]
    if not loads or any(int(line.split()[-1], 16) < 16384 for line in loads):
        raise RuntimeError('An ELF load segment is not 16 KiB aligned')
    forbidden = ['na_cpu_memory_preflight', 'na_atomic_calls', 'cached_diagnostic_reference_main']
    if any(re.search(r'\b' + name + r'$', symbols, re.M) for name in forbidden):
        raise RuntimeError('A legacy direct-driver or producer-atomic path survived')
    record = {
        'status': 'HOST_CHECKED_NOT_DEVICE_TESTED',
        'owner': {'bytes': owner.stat().st_size, 'sha256': sha(owner)},
        'archive_sha256': sha(archive), 'header_sha256': sha(header),
        'native_supervisor_matches_verified_source': True,
        'native_supervisor_sha256': hashlib.sha256(body.encode()).hexdigest(),
        'source_sha256': {name: sha(ROOT / name) for name in
                          ['owner.c', 'native_owner.h', 'build.py', 'run.sh']},
        'frozen_native_source_sha256': {name: sha(BASE / name) for name in
                                       ['owner.c', 'owner_control.h', 'native_gpu_protocol.h']},
        'static_analysis_diagnostics': 0,
        'compiler': subprocess.check_output([str(cc), '--version'], text=True).strip(),
        'command': [str(x) for x in command],
        'EL0_engine': 'existing verified QEMU a815e121 package; unchanged',
        'GPU_path': 'reims producer C API, real metal2vulkan-runtime blit',
        'producer_atomics': False,
    }
    (out / 'owner-build.json').write_text(json.dumps(record, indent=2) + '\n')
    shutil.copy2(ROOT / 'run.sh', out / 'run.sh')
    print(json.dumps({'owner': record['owner'], 'host_checks': 'PASS'}))


if __name__ == '__main__':
    main()
