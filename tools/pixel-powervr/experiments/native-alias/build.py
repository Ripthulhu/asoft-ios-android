#!/usr/bin/env python3
"""Build this isolated native-alias candidate; do not install or contact a phone."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import base64
import gzip
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ndk', type=Path, required=True)
    args = parser.parse_args()
    ndk = args.ndk.resolve()
    tools = ndk / 'toolchains/llvm/prebuilt/linux-x86_64/bin'
    compiler = tools / 'aarch64-linux-android35-clang'
    flags = ['-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-fPIE', '-pie',
             '-ffunction-sections', '-fdata-sections', '-fmacro-prefix-map=' + str(ROOT) + '=.',
             '-Wl,--gc-sections', '-Wl,--no-undefined', '-Wl,--build-id=sha1',
             '-Wl,-z,max-page-size=16384']
    binary = ROOT / 'native_alias_probe'
    subprocess.run([str(compiler), *flags, str(ROOT / 'opaque_fd_probe.c'), '-o', str(binary), '-lvulkan'], check=True)
    subprocess.run([str(tools / 'llvm-strip'), '--strip-unneeded', str(binary)], check=True)
    subprocess.run([str(compiler), '-std=c11', '-Wall', '-Wextra', '-Werror', '--analyze',
                    '-Xclang', '-analyzer-output=plist', str(ROOT / 'opaque_fd_probe.c'),
                    '-o', str(ROOT / 'static-analysis.plist')], check=True)
    elf = subprocess.check_output([str(tools / 'llvm-readelf'), '-h', '-l', '-d', '-n', str(binary)], text=True)
    (ROOT / 'elf-info.txt').write_text(elf)
    packed = gzip.compress(binary.read_bytes(), mtime=0)
    (ROOT / 'native_alias_probe.gz').write_bytes(packed)
    encoded = base64.b64encode(packed).decode('ascii')
    chunks = [encoded[i:i + 2400] for i in range(0, len(encoded), 2400)]
    (ROOT / 'transfer-chunks.json').write_text(json.dumps(chunks, indent=2) + '\n')
    names = ['opaque_fd_probe.c', 'cpu_alias.h', 'cpu_move.h', 'native_alias.h',
             'native_exec.h', 'native_alias_fixture.c', 'build.py', 'BASE-V3.json']
    info = {
        'created_utc': datetime.now(timezone.utc).isoformat(), 'version': 'native-alias-v1',
        'status': 'Candidate pending independent review; no phone execution by this build.',
        'binary': binary.name, 'sha256': digest(binary), 'bytes': binary.stat().st_size,
        'source_sha256': {n: digest(ROOT / n) for n in names},
        'target': 'aarch64-linux-android35', 'elf_max_page_size': 16384,
        'ndk_source_properties': (ndk / 'source.properties').read_text(),
        'compiler': subprocess.check_output([str(compiler), '--version'], text=True).strip(),
        'compile_flags': [f if not f.startswith('-fmacro-prefix-map=') else '-fmacro-prefix-map=<source-root>=.' for f in flags] + ['-lvulkan'],
        'gzip_bytes': len(packed), 'gzip_sha256': digest(ROOT / 'native_alias_probe.gz'),
        'base64_characters': len(encoded), 'transfer_chunks': len(chunks), 'chunk_max_characters': 2400,
        'cli': 'native_alias_probe --native-alias',
        'scope': 'Small32KiB producer allocation; two16KiB aliases, protection transitions, fixed AArch64 return42 and fresh exec SCM_RIGHTS child. No real native EL0 factory or RAM-scale test.',
        'deadlines': {'vulkan_fence_seconds': 5, 'parent_watchdog_seconds': 45, 'child_watchdog_seconds': 10,
                      'ipc_seconds': 8, 'reap_seconds': 2, 'recommended_outer_seconds': 60},
    }
    (ROOT / 'build-info.json').write_text(json.dumps(info, indent=2) + '\n')
    (ROOT / 'SHA256SUMS').write_text(''.join(digest(ROOT / n) + '  ' + n + '\n'
        for n in [binary.name, 'native_alias_probe.gz', *names]))
    print(json.dumps({k:info[k] for k in ['sha256','bytes','gzip_bytes','gzip_sha256','transfer_chunks','cli']}, indent=2))


if __name__ == '__main__':
    main()
