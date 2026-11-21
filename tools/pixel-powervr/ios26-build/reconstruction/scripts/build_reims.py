#!/usr/bin/env python3
"""Cross-build the pinned reims C API for the reconstructed QEMU link."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
SOURCE = WORKSPACE / "reims-pixel-android-link"
M2V = WORKSPACE / "metal2vulkan-tile-runtime"
NDK = WORKSPACE / "tooling/android-ndk-r29"
TOOLS = NDK / "toolchains/llvm/prebuilt/linux-x86_64/bin"
TARGET = Path("/home/agent/.cache/pixel26-reims-android")
CARGO = "/home/agent/.cargo/bin/cargo"


def sha(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def localize(built, dist):
    """Mirror xtask/src/dist/linux.rs using the target LLVM tools."""
    work = ROOT / "reims-localized"
    work.mkdir(exist_ok=True)
    obj = work / "reims_vgpu.o"
    commands = []
    commands.append([str(TOOLS / "ld.lld"), "-r", "--whole-archive", str(built),
                     "--no-whole-archive", "-o", str(obj)])
    subprocess.run(commands[-1], check=True)
    nm_args = [str(TOOLS / "llvm-nm"), "-g", "--defined-only", "-P"]
    def globals_for(path):
        output = subprocess.check_output([*nm_args, str(path)], text=True)
        return [line.split()[0] for line in output.splitlines()
                if len(line.split()) >= 2 and len(line.split()[1]) == 1]
    api = sorted(n for n in globals_for(obj) if n.startswith("rvg_"))
    if not api:
        raise RuntimeError("The real archive has no rvg_ C API symbols")
    keep = work / "keep-global-symbols"
    keep.write_text("\n".join(api) + "\n")
    commands.append([str(TOOLS / "llvm-objcopy"), "--keep-global-symbols=" + str(keep), str(obj)])
    subprocess.run(commands[-1], check=True)
    archive = dist / "lib/libreims_vgpu.a"
    archive.unlink(missing_ok=True)
    commands.append([str(TOOLS / "llvm-ar"), "rcsD", str(archive), str(obj)])
    subprocess.run(commands[-1], check=True)
    actual = sorted(globals_for(archive))
    if actual != api:
        raise RuntimeError("Localized archive exposes symbols outside the expected rvg_ C API")
    return {"commands": commands, "raw_archive_sha256": sha(built),
            "raw_archive_bytes": built.stat().st_size,
            "public_symbols": api, "public_symbol_count": len(api),
            "upstream_recipe": "xtask/src/dist/linux.rs::localize; target LLVM tools substituted for host ld/nm/objcopy/ar"}


def main():
    env = os.environ.copy()
    env.update({
        "CARGO_TARGET_DIR": str(TARGET),
        "CARGO_BUILD_JOBS": "2",
        "CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER": str(TOOLS / "aarch64-linux-android29-clang"),
        "CC_aarch64_linux_android": str(TOOLS / "aarch64-linux-android29-clang"),
        "AR_aarch64_linux_android": str(TOOLS / "llvm-ar"),
        "CARGO_ENCODED_RUSTFLAGS": "\x1f".join([
            "-Dwarnings", "-Adead_code", "-C", "target-feature=+lse,+rcpc",
            "-C", "link-arg=-Wl,-z,max-page-size=16384",
            "--remap-path-prefix", f"{SOURCE}=/reims-vgpu",
            "--remap-path-prefix", f"{M2V}=/metal2vulkan",
        ]),
    })
    command = [CARGO, "+1.98.1", "rustc", "--offline", "--locked", "--release", "--target",
               "aarch64-linux-android", "-p", "reims-vgpu-c", "--lib",
               "--no-default-features", "--features", "vulkan", "--", "--print", "native-static-libs"]
    info = {
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "command": command,
        "source": str(SOURCE),
        "reims_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=SOURCE, text=True).strip(),
        "metal2vulkan_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=M2V, text=True).strip(),
        "ndk_source_properties": (NDK / "source.properties").read_text(),
        "rustc": subprocess.check_output(["/home/agent/.cargo/bin/rustc", "+1.98.1", "-vV"], text=True),
        "environment_overrides": {k: env[k] for k in env if k.startswith(("CARGO_", "CC_aarch64", "AR_aarch64"))},
        "native_el0_policy": "QEMU native EL0 retained; this library build does not qualify its memory provider",
        "feature_spoofing": False,
        "warning_exception": "dead_code only: Android does not construct the desktop window presenter. Original denied-warning build is preserved; all other Rust warnings remain denied.",
        "lse2_codegen_note": "Hardware LSE2 remains a source requirement. No unstable Rust lse2 flag is required to assemble the explicit source instructions.",
        "cpu_requirements": "AArch64 with LSE, LSE2 atomicity, RCpc: explicit source guest/raw/aarch64.rs contracts; not a generic Armv8 binary",
    }
    log = ROOT / "logs/reims-android-release.log"
    with log.open("w") as output:
        result = subprocess.run(command, cwd=SOURCE, env=env, stdout=output, stderr=subprocess.STDOUT)
    info["exit_code"] = result.returncode
    info["ended_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    info["log_sha256"] = sha(log)
    patch = subprocess.check_output(["git", "diff", "--", "Cargo.toml"], cwd=SOURCE)
    (ROOT / "provenance/reims-path-override.patch").write_bytes(patch)
    if (SOURCE / "Cargo.lock").exists():
        shutil.copyfile(SOURCE / "Cargo.lock", ROOT / "provenance/reims-Cargo.lock")
        info["cargo_lock_sha256"] = sha(SOURCE / "Cargo.lock")
    if result.returncode == 0:
        dist = ROOT / "reims-dist"
        (dist / "lib").mkdir(exist_ok=True)
        (dist / "include").mkdir(exist_ok=True)
        (dist / "lib/pkgconfig").mkdir(exist_ok=True)
        library = TARGET / "aarch64-linux-android/release/libreims_vgpu_c.a"
        info["localization"] = localize(library, dist)
        shutil.copyfile(SOURCE / "crates/reims-vgpu-c/include/reims_vgpu.h", dist / "include/reims_vgpu.h")
        archive = dist / "lib/libreims_vgpu.a"
        info["static_library"] = {"bytes": archive.stat().st_size, "sha256": sha(archive)}
        print("REIMS_STATICLIB_BUILT", info["static_library"], flush=True)
    (ROOT / "provenance/reims-build.json").write_text(json.dumps(info, indent=2, sort_keys=True) + "\n")
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
