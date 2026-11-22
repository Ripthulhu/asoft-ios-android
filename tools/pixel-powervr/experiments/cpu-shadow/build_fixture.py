#!/usr/bin/env python3
"""Link the real-device EFI fixture against an already built reims library.

This builds one command-line diagnostic, never an Android app or APK.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess


ROOT = Path(__file__).resolve().parent


def sha(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def command(args, log):
    with log.open("w") as stream:
        subprocess.run([str(arg) for arg in args], stdout=stream,
                       stderr=subprocess.STDOUT, check=True, timeout=180)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include", type=Path, required=True,
                        help="directory containing the matching reims_vgpu.h")
    parser.add_argument("--library", type=Path, required=True,
                        help="the actual rebuilt reims static archive or shared library")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--ndk", type=Path, help="cross-build for Android AArch64/API 29")
    parser.add_argument("--cc", default="cc", help="host C compiler when --ndk is absent")
    args = parser.parse_args()
    include = args.include.resolve()
    library = args.library.resolve()
    header = include / "reims_vgpu.h"
    source = ROOT / "efi_memfd_integration.c"
    if not header.is_file() or not library.is_file():
        parser.error("the matching runtime library and generated C header must already exist")
    if "rvg_device_cpu_shadow_counts" not in header.read_text():
        parser.error("the runtime header lacks the real-device CPU-shadow counters")
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    binary = out / "efi-memfd-integration"
    flags = ["-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
             "-fPIE", "-pie", "-ffunction-sections", "-fdata-sections",
             "-I" + str(include), "-Wl,--gc-sections", "-Wl,--no-undefined",
             "-Wl,--build-id=sha1"]
    extra_sources = []
    if args.ndk:
        tools = args.ndk.resolve() / "toolchains/llvm/prebuilt/linux-x86_64/bin"
        cc = tools / "aarch64-linux-android29-clang"
        readelf = tools / "llvm-readelf"
        flags += ["-Wl,-z,max-page-size=16384"]
        libs = ["-ldl", "-llog", "-lunwind", "-lm", "-lc"]
        if library.suffix == ".a":
            extra_sources.append(ROOT / "android_memfd_compat.c")
    else:
        cc = shutil.which(args.cc)
        readelf = shutil.which("readelf")
        if not cc or not readelf:
            parser.error("a host C compiler and readelf must be available")
        libs = ["-ldl", "-lpthread", "-lrt", "-lutil", "-lm"]
    if library.suffix == ".so":
        # The fixture remains tied to this exact library, whose hash is recorded.
        flags += ["-Wl,-rpath," + str(library.parent)]
    inputs = {str(path): sha(path) for path in (source, header, library, *extra_sources)}
    invocation = [cc, *flags, source, *extra_sources, library, *libs, "-o", binary]
    command(invocation, out / "compile.log")
    if any(sha(Path(path)) != value for path, value in inputs.items()):
        raise RuntimeError("a source, header, or library changed during linking")
    command([readelf, "-h", "-l", "-d", "--wide", binary], out / "elf.txt")
    elf = (out / "elf.txt").read_text()
    if args.ndk:
        loads = [line for line in elf.splitlines() if re.match(r"\s*LOAD\s", line)]
        if not loads or any(int(line.split()[-1], 16) < 16384 for line in loads):
            raise RuntimeError("Android ELF LOAD alignment is below 16 KiB")
        if "AArch64" not in elf:
            raise RuntimeError("Android fixture is not AArch64")
    manifest = {
        "status": "BUILT_NOT_EXECUTED",
        "kind": "standalone_real_device_api_diagnostic",
        "android_apk": False,
        "source": {"path": str(source), "sha256": inputs[str(source)]},
        "header": {"path": str(header), "sha256": inputs[str(header)]},
        "library": {"path": str(library), "sha256": inputs[str(library)]},
        "extra_sources": {str(path): inputs[str(path)] for path in extra_sources},
        "binary": {"path": str(binary), "sha256": sha(binary),
                   "bytes": binary.stat().st_size},
        "command": [str(arg) for arg in invocation],
        "compiler": subprocess.check_output([str(cc), "--version"], text=True).strip(),
        "expected_reims_feature": "guest-arm64 (16 KiB guest pages)",
        "run_environment": {"REIMS_VGPU_CPU_SHADOW": "1"},
        "native_guest_execution_tested": False,
        "gpu_path_complete": False,
    }
    (out / "build.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest["binary"]))


if __name__ == "__main__":
    main()
