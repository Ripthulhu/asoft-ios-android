#!/usr/bin/env python3
"""Build the Android ARM64 probes from the included source; downloads nothing.

Requires Android NDK r29, a modern glslangValidator supporting
GL_EXT_shader_tile_image, and modern spirv-val. The NDK r29 bundled shader
compiler is too old for the tile-image extension.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent


def run(command: list[str]) -> None:
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, check=True)


def resolve_tool(name: str) -> str:
    found = shutil.which(name)
    if not found:
        raise RuntimeError(f"Required tool not found: {name}")
    return found


def version(command: list[str]) -> str:
    return subprocess.check_output(command, text=True, encoding="utf-8", errors="replace").strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ndk", type=Path, default=os.environ.get("ANDROID_NDK_HOME"))
    parser.add_argument("--glslang", default="glslangValidator")
    parser.add_argument("--spirv-val", default="spirv-val")
    args = parser.parse_args()
    if not args.ndk:
        raise RuntimeError("Specify --ndk /path/to/android-ndk-r29 or set ANDROID_NDK_HOME.")
    system = platform.system()
    if system == "Windows":
        host, executable, wrapper = "windows-x86_64", ".exe", ".cmd"
    elif system == "Darwin":
        host, executable, wrapper = "darwin-x86_64", "", ""
    elif system == "Linux":
        host, executable, wrapper = "linux-x86_64", "", ""
    else:
        raise RuntimeError("Unsupported build host: " + system)
    ndk = args.ndk.resolve()
    tools = ndk / "toolchains" / "llvm" / "prebuilt" / host / "bin"
    compiler = tools / ("aarch64-linux-android35-clang" + wrapper)
    strip = tools / ("llvm-strip" + executable)
    if not compiler.is_file() or not strip.is_file():
        raise RuntimeError("NDK ARM64 API 35 compiler/strip not found under " + str(tools))
    glslang = resolve_tool(args.glslang)
    validator = resolve_tool(args.spirv_val)
    destination = ROOT / "bin"
    destination.mkdir(exist_ok=True)
    for stage in ("vert", "frag"):
        shader = ROOT / "shaders" / ("tile_image." + stage)
        output = destination / (shader.name + ".spv")
        run([glslang, "-V", "--target-env", "vulkan1.3", "-S", stage,
             "-o", str(output), str(shader)])
        run([validator, "--target-env", "vulkan1.3", str(output)])
    for name in ("tile_image_probe", "dmabuf_probe"):
        output = destination / name
        run([str(compiler), "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
             "-fPIE", "-pie", "-ffunction-sections", "-fdata-sections",
             "-fmacro-prefix-map=" + str(ROOT) + "=.",
             "-Wl,--gc-sections", "-Wl,--no-undefined", "-Wl,--build-id=sha1",
             "-Wl,-z,max-page-size=16384", str(ROOT / "src" / (name + ".c")),
             "-o", str(output), "-lvulkan"])
        run([str(strip), "--strip-unneeded", str(output)])
    artifacts = sorted(p for p in destination.iterdir()
                       if p.name in {"tile_image_probe", "dmabuf_probe",
                                     "tile_image.vert.spv", "tile_image.frag.spv"})
    (ROOT / "SHA256SUMS").write_text(
        "".join(sha256(path) + "  " + path.relative_to(ROOT).as_posix() + "\n"
                for path in artifacts), encoding="utf-8", newline="\n")
    source_files = sorted((ROOT / "src").glob("*.c")) + sorted((ROOT / "shaders").glob("*"))
    info = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "target": "aarch64-linux-android35", "elf_max_page_size": 16384,
        "ndk_source_properties": (ndk / "source.properties").read_text(encoding="utf-8"),
        "compiler": version([str(compiler), "--version"]),
        "glslang": version([glslang, "--version"]),
        "spirv_val": version([validator, "--version"]),
        "source_sha256": {p.relative_to(ROOT).as_posix(): sha256(p) for p in source_files},
        "hardware_execution": "Not performed by the build. Run run.py on the target phone.",
    }
    (ROOT / "build-info.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    print("Built and shader-validated. No phone or GPU was tested by this build.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print("Error: " + str(error), file=sys.stderr)
        raise SystemExit(1)
