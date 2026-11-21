#!/usr/bin/env python3
"""Build only the query-only Android ARM64 Vulkan reporter using an existing NDK.

Does not rebuild shaders or either execution probe. Run after build.py when
rebuilding the complete kit, so SHA256SUMS contains this reporter's entry too.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent
RELATIVE_BINARY = "bin/vulkan_caps"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str]) -> None:
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ndk", type=Path, default=os.environ.get("ANDROID_NDK_HOME"))
    args = parser.parse_args()
    if not args.ndk:
        raise RuntimeError("Specify --ndk /path/to/android-ndk-r29 or set ANDROID_NDK_HOME.")
    hosts = {
        "Linux": ("linux-x86_64", "", ""),
        "Darwin": ("darwin-x86_64", "", ""),
        "Windows": ("windows-x86_64", ".exe", ".cmd"),
    }
    if platform.system() not in hosts:
        raise RuntimeError("Unsupported build host: " + platform.system())
    host, executable, wrapper = hosts[platform.system()]
    ndk = args.ndk.resolve()
    tools = ndk / "toolchains" / "llvm" / "prebuilt" / host / "bin"
    compiler = tools / ("aarch64-linux-android35-clang" + wrapper)
    strip = tools / ("llvm-strip" + executable)
    if not compiler.is_file() or not strip.is_file():
        raise RuntimeError("NDK ARM64 API 35 compiler/strip not found under " + str(tools))

    source = ROOT / "src" / "vulkan_caps.c"
    destination = ROOT / RELATIVE_BINARY
    destination.parent.mkdir(exist_ok=True)
    flags = [
        "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-fPIE", "-pie",
        "-ffunction-sections", "-fdata-sections",
        "-fmacro-prefix-map=" + str(ROOT) + "=.",
        "-Wl,--gc-sections", "-Wl,--no-undefined", "-Wl,--build-id=sha1",
        "-Wl,-z,max-page-size=16384",
    ]
    with tempfile.TemporaryDirectory(prefix=".vulkan-caps-", dir=destination.parent) as temp:
        output = Path(temp) / "vulkan_caps"
        run([str(compiler), *flags, str(source), "-o", str(output), "-lvulkan"])
        run([str(strip), "--strip-unneeded", str(output)])
        output.replace(destination)

    manifest = ROOT / "SHA256SUMS"
    entries = manifest.read_text(encoding="utf-8").splitlines() if manifest.exists() else []
    # Preserve the existing probes' entries; this helper touches only its own.
    entries = [line for line in entries if line.partition("  ")[2] != RELATIVE_BINARY]
    entries.append(sha256(destination) + "  " + RELATIVE_BINARY)
    manifest.write_text("\n".join(entries) + "\n", encoding="utf-8", newline="\n")
    info = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "target": "aarch64-linux-android35",
        "elf_max_page_size": 16384,
        "ndk_source_properties": (ndk / "source.properties").read_text(encoding="utf-8"),
        "compiler": subprocess.check_output([str(compiler), "--version"], text=True).strip(),
        "compile_flags": [flag if not flag.startswith("-fmacro-prefix-map=")
                          else "-fmacro-prefix-map=<package-root>=." for flag in flags] + ["-lvulkan"],
        "source_sha256": {"src/vulkan_caps.c": sha256(source)},
        "artifact_sha256": {RELATIVE_BINARY: sha256(destination)},
        "artifact_bytes": destination.stat().st_size,
        "scope": "Physical-device capability queries only; no VkDevice, GPU allocation, resource, queue, or submission.",
        "hardware_execution": "Not performed by the build; see VULKAN-CAPS.md for manual use and validation scope.",
    }
    (ROOT / "build-info-vulkan-caps.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    print("Built query-only reporter. Existing execution probes were not rebuilt.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print("Error: " + str(error), file=sys.stderr)
        raise SystemExit(1)
