#!/usr/bin/env python3
"""Build the Android arm64 tile-fetch fixture with an installed NDK."""

import argparse
from pathlib import Path
import struct
import subprocess
import sys


def run(*argv):
    subprocess.run(argv, check=True)


def assemble(tool, source, output):
    args = [str(tool), "--target-env", "vulkan1.3"]
    first = subprocess.run([*args, str(source), "-o", str(output)],
                           check=False, capture_output=True, text=True)
    if first.returncode == 0:
        return
    if "Invalid capability 'TileImageColorReadAccessEXT'" not in first.stderr:
        raise RuntimeError(first.stderr.strip())

    # The NDK's older assembler lacks the extension's names. Assemble the
    # same operand words and replace one temporary four-word instruction.
    text = source.read_text()
    for symbol, word in (("TileImageColorReadAccessEXT", "!4166"),
                         ("TileImageDataEXT 0 0 0 2 Unknown", "!4173 0 0 0 2 0"),
                         ("TileImageEXT", "!4172"),
                         ("OpColorAttachmentReadEXT", "OpCopyObject")):
        if symbol not in text:
            raise RuntimeError("tile shader changed: " + symbol)
        text = text.replace(symbol, word)
    temporary = output.with_suffix(".legacy.spvasm")
    temporary.write_text(text)
    run(*args, str(temporary), "-o", str(output))

    data = output.read_bytes()
    words = list(struct.unpack("<" + "I" * (len(data) // 4), data))
    if words[0] != 0x07230203:
        raise RuntimeError("assembler did not produce SPIR-V")
    ops, replace = {}, []
    i = 5
    while i < len(words):
        count, opcode = words[i] >> 16, words[i] & 0xffff
        if not count or i + count > len(words):
            raise RuntimeError("invalid SPIR-V instruction size")
        ops.setdefault(opcode, []).append(words[i + 1:i + count])
        if (count, opcode) == (4, 83):  # OpCopyObject
            replace.append(i)
        i += count
    tiles = ops.get(25, [[]])[0]
    pointers = ops.get(32, [[]])[0]
    if (len(replace) != 1 or [4166] not in ops.get(17, []) or
            tiles[2:3] != [4173] or pointers[1:2] != [4172]):
        raise RuntimeError("legacy assembly failed to preserve tile-image operands")
    words[replace[0]] = (4 << 16) | 4160  # OpColorAttachmentReadEXT
    output.write_bytes(struct.pack("<" + "I" * len(words), *words))
    print("Used the legacy NDK assembler with verified tile-image instruction words.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ndk", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--host", choices=("linux-x86_64", "windows-x86_64", "darwin-x86_64"),
                        default={"linux": "linux-x86_64", "win32": "windows-x86_64",
                                 "darwin": "darwin-x86_64"}.get(sys.platform))
    args = parser.parse_args()
    src = Path(__file__).resolve().parent
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    suffix = ".exe" if args.host == "windows-x86_64" else ""
    shaders = args.ndk / "shader-tools" / args.host
    clang = args.ndk / "toolchains" / "llvm" / "prebuilt" / args.host / "bin" / ("clang" + suffix)

    glslc = shaders / ("glslc" + suffix)
    for shader in ("feedback.vert", "negative.frag", "negative-depth.vert"):
        run(str(glslc), "--target-env=vulkan1.3", str(src / shader),
            "-o", str(out / (shader + ".spv")))
    assemble(shaders / ("spirv-as" + suffix), src / "feedback.frag.spvasm", out / "feedback.frag.spv")
    target = "--target=aarch64-linux-android29"
    obj = out / "tile_fetch.o"
    run(str(clang), target, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-c",
        str(src / "tile_fetch.c"), "-o", str(obj))
    run(str(clang), target, "-Wl,-z,max-page-size=16384", "-Wl,--strip-all", str(obj),
        "-lvulkan", "-o", str(out / "tile_fetch"))


if __name__ == "__main__":
    main()
