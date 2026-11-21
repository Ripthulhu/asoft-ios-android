#!/usr/bin/env python3
"""Configure the pinned QEMU fork against real Android libraries, offline."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
SOURCE = WORKSPACE / "qemu-pixel-android-build"
NDK = WORKSPACE / "tooling/android-ndk-r29"
TOOLS = NDK / "toolchains/llvm/prebuilt/linux-x86_64/bin"
PREFIX = ROOT / "termux-root/data/data/com.termux/files/usr"
BUILD = ROOT / "qemu-out"


def sha(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def main():
    reims = ROOT / "reims-dist"
    archive = reims / "lib/libreims_vgpu.a"
    info = json.loads((ROOT / "provenance/reims-build.json").read_text())
    if info["exit_code"] != 0 or not archive.exists():
        raise RuntimeError("A successful actual reims Android static build is required")
    if sha(archive) != info["static_library"]["sha256"]:
        raise RuntimeError("The staged reims archive does not match its build record")
    log_text = (ROOT / "logs/reims-android-release.log").read_text()
    native = re.findall(r"native-static-libs: (.+)", log_text)
    if not native:
        raise RuntimeError("rustc did not report the static link's native dependencies")
    native_libs = native[-1].strip()
    pc = reims / "lib/pkgconfig/reims-vgpu.pc"
    pc.write_text(f'''# Android cross-build reconstruction; see provenance/reims-build.json.
prefix=${{pcfiledir}}/../..
libdir=${{prefix}}/lib
includedir=${{prefix}}/include

Name: reims-vgpu
Description: Pinned Vulkan reims C API for the Android QEMU link
Version: 0.1.0
Libs: -L${{libdir}} -lreims_vgpu
Libs.private: {native_libs}
Cflags: -I${{includedir}}
''')
    env = os.environ.copy()
    env.update({
        "PATH": str(ROOT / "host-tools/bin") + os.pathsep + str(TOOLS) + os.pathsep + env["PATH"],
        "PKG_CONFIG": str(ROOT / "scripts/target-pkg-config.py"),
        "AR": str(TOOLS / "llvm-ar"),
        "NM": str(TOOLS / "llvm-nm"),
        "RANLIB": str(TOOLS / "llvm-ranlib"),
        "STRIP": str(TOOLS / "llvm-strip"),
    })
    cflags = [
        "-O2", "-fno-emulated-tls", "-I" + str(PREFIX / "include"),
        "-ffile-prefix-map=" + str(SOURCE) + "=/qemu-sptm",
        "-ffile-prefix-map=" + str(ROOT) + "=/qemu26-build",
    ]
    ldflags = [
        "-L" + str(PREFIX / "lib"),
        "-Wl,-rpath-link," + str(PREFIX / "lib"),
        "-Wl,-z,max-page-size=16384", "-Wl,-z,common-page-size=16384",
        str(ROOT / "android-port/libandroid-setjmp.a"), "-llog",
    ]
    command = [
        str(SOURCE / "configure"),
        "--prefix=/pixel26-qemu",
        "--target-list=aarch64-softmmu",
        "--cpu=aarch64", "--cross-prefix=aarch64-linux-android-",
        "--cc=" + str(TOOLS / "aarch64-linux-android29-clang"),
        "--cxx=" + str(TOOLS / "aarch64-linux-android29-clang++"),
        "--host-cc=gcc",
        "--python=" + str(ROOT / "host-tools/bin/python3"),
        "--ninja=" + str(ROOT / "host-tools/bin/ninja"),
        "--extra-cflags=" + " ".join(cflags),
        "--extra-ldflags=" + " ".join(ldflags),
        "--without-default-features", "--disable-download",
        "--enable-system", "--enable-tcg", "--enable-kvm",
        "--enable-reims-vgpu", "--enable-nettle", "--enable-pixman",
        "--enable-fdt=system", "--enable-slirp", "--enable-zstd",
        "--enable-iconv", "--enable-coroutine-pool", "--enable-pie",
        "--disable-tools", "--disable-docs", "--disable-rust",
        "--disable-guest-agent", "--disable-werror",
        "--audio-drv-list=", "--enable-trace-backends=nop",
    ]
    BUILD.mkdir(exist_ok=True)
    provenance = {
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=SOURCE, text=True).strip(),
        "source_version": (SOURCE / "VERSION").read_text().strip(),
        "source_patch": subprocess.check_output(["git", "diff"], cwd=SOURCE, text=True),
        "command": command,
        "environment_overrides": {k: env[k] for k in ["PATH", "PKG_CONFIG", "AR", "NM", "RANLIB", "STRIP"]},
        "reims_archive_sha256": sha(archive),
        "reims_native_static_libs": native_libs,
        "reims_pc_sha256": sha(pc),
        "keycodemapdb_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=SOURCE / "subprojects/keycodemapdb", text=True).strip(),
        "native_el0": "Retained through target/arm/tcg/native-el0.c in the AArch64 TCG target; runtime operation is not established by a build.",
        "release_identity": "This is a source rebuild of the pinned QEMU fork, not a claim of byte identity or source provenance for the v0.1.6 release ELF.",
        "gpu_memory_backend": "Unmodified existing reims backend; the Pixel producer/adoption path is not integrated in this build.",
    }
    log = ROOT / "logs/qemu-configure.log"
    with log.open("w") as out:
        result = subprocess.run(command, cwd=BUILD, env=env, stdout=out, stderr=subprocess.STDOUT)
    provenance.update({
        "exit_code": result.returncode,
        "ended_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "log_sha256": sha(log),
    })
    (ROOT / "provenance/qemu-configure.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(f"QEMU_CONFIGURE_EXIT={result.returncode}; log={log}")
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
