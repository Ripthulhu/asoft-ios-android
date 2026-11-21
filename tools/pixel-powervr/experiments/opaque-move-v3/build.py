#!/usr/bin/env python3
"""Build the isolated Android ARM64 v3 probe; never touches v2 or the app kit."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ndk", type=Path, required=True)
    args = parser.parse_args()
    ndk = args.ndk.resolve()
    tools = ndk / "toolchains/llvm/prebuilt/linux-x86_64/bin"
    compiler = tools / "aarch64-linux-android35-clang"
    flags = [
        "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-fPIE", "-pie",
        "-ffunction-sections", "-fdata-sections", f"-fmacro-prefix-map={ROOT}=.",
        "-Wl,--gc-sections", "-Wl,--no-undefined", "-Wl,--build-id=sha1",
        "-Wl,-z,max-page-size=16384",
    ]
    destination = ROOT / "opaque_fd_probe"
    with tempfile.TemporaryDirectory(prefix="build-", dir=ROOT) as temporary:
        output = Path(temporary) / "opaque_fd_probe"
        subprocess.run([str(compiler), *flags, str(ROOT / "opaque_fd_probe.c"),
                        "-o", str(output), "-lvulkan"], check=True)
        subprocess.run([str(tools / "llvm-strip"), "--strip-unneeded", str(output)], check=True)
        output.replace(destination)
    subprocess.run([str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
                    "--analyze", "-Xclang", "-analyzer-output=plist",
                    str(ROOT / "opaque_fd_probe.c"), "-o", str(ROOT / "static-analysis.plist")], check=True)
    subprocess.run([str(tools / "llvm-readelf"), "-l", "-d", str(destination)],
                   check=True, stdout=(ROOT / "elf-info.txt").open("w"))
    encoded = base64.b64encode(destination.read_bytes()).decode("ascii")
    (ROOT / "opaque_fd_probe.base64").write_text(encoded + "\n", encoding="ascii")
    chunks = [encoded[i:i + 2800] for i in range(0, len(encoded), 2800)]
    (ROOT / "opaque_fd_probe-chunks.json").write_text(json.dumps(chunks, indent=2) + "\n")
    source_names = ["opaque_fd_probe.c", "cpu_alias.h", "cpu_move.h", "cpu_move_fixture.c", "build.py"]
    source_hashes = {name: digest(ROOT / name) for name in source_names}
    info = {
        "version": 3, "binary": "opaque_fd_probe", "bytes": destination.stat().st_size,
        "sha256": digest(destination), "source_sha256": source_hashes,
        "target": "aarch64-linux-android35", "elf_max_page_size": 16384,
        "compiler": subprocess.check_output([str(compiler), "--version"], text=True).strip(),
        "ndk": (ndk / "source.properties").read_text().strip(),
        "build_flags": [f if not f.startswith("-fmacro-prefix-map=") else
                        "-fmacro-prefix-map=<source-root>=." for f in flags] + ["-lvulkan"],
        "base64_characters": len(encoded), "base64_chunks": len(chunks),
        "chunk_max_characters": 2800,
        "move_option": "--move-page",
        "scope": "One CPU page from a disposable verified full offset-zero mmap; canonical GPU buffer stays contiguous.",
        "phone_execution": "Not performed by this build; pending root-owned device test.",
    }
    (ROOT / "build-info.json").write_text(json.dumps(info, indent=2) + "\n")
    (ROOT / "SHA256SUMS").write_text(
        digest(destination) + "  opaque_fd_probe\n" +
        "".join(value + "  " + name + "\n" for name, value in source_hashes.items()))
    print(json.dumps({"bytes": destination.stat().st_size, "sha256": digest(destination),
                      "base64_chunks": len(chunks), "cli": "opaque_fd_probe --move-page"}))


if __name__ == "__main__":
    main()
