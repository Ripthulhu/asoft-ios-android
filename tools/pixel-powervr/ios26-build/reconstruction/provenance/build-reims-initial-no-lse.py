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
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    env = os.environ.copy()
    env.update({
        "CARGO_TARGET_DIR": str(TARGET),
        "CARGO_BUILD_JOBS": "2",
        "CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER": str(TOOLS / "aarch64-linux-android29-clang"),
        "CC_aarch64_linux_android": str(TOOLS / "aarch64-linux-android29-clang"),
        "AR_aarch64_linux_android": str(TOOLS / "llvm-ar"),
        "CARGO_ENCODED_RUSTFLAGS": "\x1f".join([
            "-Dwarnings", "-C", "link-arg=-Wl,-z,max-page-size=16384",
            "--remap-path-prefix", f"{SOURCE}=/reims-vgpu",
            "--remap-path-prefix", f"{M2V}=/metal2vulkan",
        ]),
    })
    command = [CARGO, "+1.98.1", "rustc", "--offline", "--release", "--target",
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
        library = TARGET / "aarch64-linux-android/release/libreims_vgpu.a"
        shutil.copyfile(library, dist / "lib/libreims_vgpu.a")
        shutil.copyfile(SOURCE / "crates/reims-vgpu-c/include/reims_vgpu.h", dist / "include/reims_vgpu.h")
        info["static_library"] = {"bytes": library.stat().st_size, "sha256": sha(library)}
        print("REIMS_STATICLIB_BUILT", info["static_library"], flush=True)
    (ROOT / "provenance/reims-build.json").write_text(json.dumps(info, indent=2, sort_keys=True) + "\n")
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
