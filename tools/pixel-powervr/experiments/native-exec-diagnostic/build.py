#!/usr/bin/env python3
"""Build isolated execution diagnostics. No installation or device access."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import base64
import gzip
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ndk', type=Path, required=True)
    args = parser.parse_args()
    ndk = args.ndk.resolve()
    tools = ndk / 'toolchains/llvm/prebuilt/linux-x86_64/bin'
    cc = tools / 'aarch64-linux-android35-clang'
    flags = ['-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-fPIE', '-pie',
             '-ffunction-sections', '-fdata-sections', '-fmacro-prefix-map=' + str(ROOT) + '=.',
             '-Wl,--gc-sections', '-Wl,--no-undefined', '-Wl,--build-id=sha1',
             '-Wl,-z,max-page-size=16384']
    artifacts = {}
    for name, source, libraries in [('cpu_exec_control', 'cpu_exec_control.c', []),
                                    ('native_exec_diagnostic', 'opaque_fd_probe.c', ['-lvulkan'])]:
        binary = ROOT / name
        subprocess.run([str(cc), *flags, str(ROOT / source), '-o', str(binary), *libraries], check=True)
        subprocess.run([str(tools / 'llvm-strip'), '--strip-unneeded', str(binary)], check=True)
        subprocess.run([str(cc), '-std=c11', '-Wall', '-Wextra', '-Werror', '--analyze',
                        '-Xclang', '-analyzer-output=plist', str(ROOT / source),
                        '-o', str(ROOT / (name + '-analysis.plist'))], check=True)
        (ROOT / (name + '-elf.txt')).write_text(subprocess.check_output(
            [str(tools / 'llvm-readelf'), '-h', '-l', '-d', '-n', str(binary)], text=True))
        (ROOT / (name + '-disassembly.txt')).write_text(subprocess.check_output(
            [str(tools / 'llvm-objdump'), '-d', str(binary)], text=True))
        packed = ROOT / (name + '.gz')
        packed.write_bytes(gzip.compress(binary.read_bytes(), mtime=0))
        encoded = base64.b64encode(packed.read_bytes()).decode('ascii')
        chunks = [encoded[i:i + 2400] for i in range(0, len(encoded), 2400)]
        (ROOT / (name + '-transfer-chunks.json')).write_text(json.dumps(chunks, indent=2) + '\n')
        artifacts[name] = {'sha256': sha(binary), 'bytes': binary.stat().st_size,
            'gzip_sha256': sha(packed), 'gzip_bytes': packed.stat().st_size,
            'base64_characters': len(encoded), 'transfer_chunks': len(chunks),
            'libraries': libraries, 'source': source}
    sources = ['opaque_fd_probe.c', 'native_alias.h', 'native_exec.h', 'cpu_alias.h', 'cpu_move.h',
               'exec_diag.h', 'cpu_exec_control.h', 'cpu_exec_control.c', 'build.py',
               'BASE-NATIVE-ALIAS-FROZEN.json']
    info = {'created_utc': datetime.now(timezone.utc).isoformat(), 'status': 'Candidate; device execution is not part of this build.',
        'artifacts': artifacts, 'source_sha256': {n: sha(ROOT / n) for n in sources},
        'compiler': subprocess.check_output([str(cc), '--version'], text=True).strip(),
        'ndk_source_properties': (ndk / 'source.properties').read_text(),
        'target': 'aarch64-linux-android35', 'elf_max_page_size': 16384,
        'compile_flags': [f if not f.startswith('-fmacro-prefix-map=') else '-fmacro-prefix-map=<source-root>=.' for f in flags],
        'cpu_control_commands': ['cpu_exec_control --cpu-exec-anon', 'cpu_exec_control --cpu-exec-memfd'],
        'cpu_control_watchdog_seconds': 5,
        'gpu_command_pending_review': 'native_exec_diagnostic --native-alias',
        'original_frozen_binary_sha256': '83ec274ef8643f2a40e5e12978560b289659fbdee4dd3c4db5fb3439513d69fe'}
    (ROOT / 'build-info.json').write_text(json.dumps(info, indent=2) + '\n')
    checks = [*sources, *artifacts, *(n + '.gz' for n in artifacts)]
    (ROOT / 'SHA256SUMS').write_text(''.join(sha(ROOT / n) + '  ' + n + '\n' for n in checks))
    print(json.dumps(artifacts, indent=2))


if __name__ == '__main__':
    main()
