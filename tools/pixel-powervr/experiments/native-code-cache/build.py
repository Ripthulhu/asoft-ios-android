#!/usr/bin/env python3
"""Build the isolated native code-cache diagnostic; no device access or install."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import base64
import gzip
import hashlib
import json
import plistlib
import subprocess

ROOT = Path(__file__).resolve().parent
SOURCES = ['opaque_fd_probe.c', 'native_code_cache.h', 'native_code_cache_exec.h', 'native_cpu_memory.h',
           'native_code_cache_fixture.c', 'cpu_alias.h', 'exec_diag.h', 'build.py',
           'BASE-FROZEN.json', 'README.md']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ndk', type=Path, required=True)
    args = parser.parse_args()
    ndk = args.ndk.resolve()
    toolroot = ndk / 'toolchains/llvm/prebuilt/linux-x86_64/bin'
    cc = toolroot / 'aarch64-linux-android35-clang'
    flags = ['-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-fPIE', '-pie',
             '-ffunction-sections', '-fdata-sections', '-fmacro-prefix-map=' + str(ROOT) + '=.',
             '-Wl,--gc-sections', '-Wl,--no-undefined', '-Wl,--build-id=sha1',
             '-Wl,-z,max-page-size=16384']
    name = 'native_code_cache_diagnostic'
    binary = ROOT / name
    subprocess.run([str(cc), *flags, str(ROOT / 'opaque_fd_probe.c'), '-o', str(binary), '-lvulkan'], check=True)
    subprocess.run([str(toolroot / 'llvm-strip'), '--strip-unneeded', str(binary)], check=True)
    analysis = ROOT / (name + '-analysis.plist')
    subprocess.run([str(cc), '-std=c11', '-Wall', '-Wextra', '-Werror', '--analyze',
                    '-Xclang', '-analyzer-output=plist', str(ROOT / 'opaque_fd_probe.c'),
                    '-o', str(analysis)], check=True)
    # Preserve and inspect the complete analyzer output, not merely its XML syntax.
    with analysis.open('rb') as stream:
        diagnostics = plistlib.load(stream).get('diagnostics', [])
    if diagnostics:
        raise RuntimeError(f'Clang static analysis reported {len(diagnostics)} diagnostic(s)')
    elf = subprocess.check_output([str(toolroot / 'llvm-readelf'), '-h', '-l', '-d', '-n', str(binary)], text=True)
    (ROOT / (name + '-elf.txt')).write_text(elf)
    (ROOT / (name + '-disassembly.txt')).write_text(subprocess.check_output(
        [str(toolroot / 'llvm-objdump'), '-d', str(binary)], text=True))
    packed = ROOT / (name + '.gz')
    packed.write_bytes(gzip.compress(binary.read_bytes(), mtime=0))
    encoded = base64.b64encode(packed.read_bytes()).decode('ascii')
    chunks = [encoded[i:i + 2400] for i in range(0, len(encoded), 2400)]
    transfer = ROOT / (name + '-transfer-chunks.json')
    transfer.write_text(json.dumps(chunks, indent=2) + '\n')
    assert gzip.decompress(base64.b64decode(''.join(json.loads(transfer.read_text())))) == binary.read_bytes()
    fixture = ROOT / 'native_code_cache_fixture'
    hostflags = ['-std=c11', '-O2', '-Wall', '-Wextra', '-Werror']
    subprocess.run(['gcc', *hostflags, str(ROOT / 'native_code_cache_fixture.c'), '-o', str(fixture)], check=True)
    fixture_run = subprocess.run([str(fixture)], text=True, capture_output=True, timeout=65)
    (ROOT / 'host-fixture.log').write_text(fixture_run.stdout + fixture_run.stderr)
    if fixture_run.returncode:
        raise RuntimeError(f'ordinary-memfd host fixture failed: exit={fixture_run.returncode}; see host-fixture.log')
    artifact = {'sha256': sha(binary), 'bytes': binary.stat().st_size,
                'gzip_sha256': sha(packed), 'gzip_bytes': packed.stat().st_size,
                'base64_characters': len(encoded), 'transfer_chunks': len(chunks),
                'maximum_chunk_characters': 2400, 'source': 'opaque_fd_probe.c',
                'libraries': ['-lvulkan']}
    info = {'created_utc': datetime.now(timezone.utc).isoformat(),
            'status': 'Candidate; host fixture passed; no phone/device execution is part of this build.',
            'artifacts': {name: artifact}, 'source_sha256': {s: sha(ROOT / s) for s in SOURCES},
            'compiler': subprocess.check_output([str(cc), '--version'], text=True).strip(),
            'ndk_source_properties': (ndk / 'source.properties').read_text(),
            'target': 'aarch64-linux-android35', 'elf_max_page_size': 16384,
            'compile_flags': [f if not f.startswith('-fmacro-prefix-map=') else '-fmacro-prefix-map=<source-root>=.' for f in flags],
            'command_pending_review': name + ' --native-code-cache',
            'fresh_exec_child_option': '--native-code-cache-child',
            'IPC_protocol': 2, 'IPC_variant': 2,
            'parent_process_watchdog_seconds': 60, 'child_watchdog_seconds': 25,
            'per_native_call_watchdog_seconds': 5, 'CPU_memory_preflight_watchdog_seconds': 5,
            'gpu_fence_seconds': 5,
            'static_analysis_diagnostics': len(diagnostics),
            'host_fixture': {'sha256': sha(fixture), 'log_sha256': sha(ROOT / 'host-fixture.log'),
                             'compiler': subprocess.check_output(['gcc', '--version'], text=True).splitlines()[0],
                             'flags': hostflags, 'result': 'PASS', 'architecture': 'x86_64',
                             'GPU_or_OPAQUE_FD_or_phone_tested': False},
            'scope': {'instruction_bytes_copied': True, 'data_backing_preserved': True,
                      'native_AArch64_CPU_execution_requested': True,
                      'required_AArch64_HWCAP': ['ATOMICS', 'LRCPC', 'USCAT'],
                      'CPU_memory_preflight': ['aligned_64bit_ldsetal_ldclral_round_trip', 'unaligned_64bit_ldr_str_within_one_16byte_granule'],
                      'unaligned_atomicity_or_Normal_memory_attributes_proven': False,
                      'TCG_used': False, 'direct_GPU_backing_execution': False,
                      'physical_W_X_or_concurrent_invalidation_proven': False,
                      'actual_QEMU_native_EL0_integration': False,
                      'code_cache_return_sequence_per_process': [42, 43, 42]},
            'base': json.loads((ROOT / 'BASE-FROZEN.json').read_text())}
    (ROOT / 'build-info.json').write_text(json.dumps(info, indent=2) + '\n')
    checks = [*SOURCES, name, name + '.gz', name + '-transfer-chunks.json', name + '-elf.txt',
              name + '-disassembly.txt', name + '-analysis.plist', fixture.name,
              'host-fixture.log', 'build-info.json']
    (ROOT / 'SHA256SUMS').write_text(''.join(sha(ROOT / path) + '  ' + path + '\n' for path in checks))
    print(json.dumps(artifact, indent=2))


if __name__ == '__main__':
    main()
