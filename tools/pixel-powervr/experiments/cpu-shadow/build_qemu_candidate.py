#!/usr/bin/env python3
"""Relink a separate QEMU GPU-integration candidate against a new reims archive.

Reuse the preserved Android baseline's unchanged objects. Compile all four
changed translation units and retain the complete commands and source hashes.
No app packaging, installation, or target execution is performed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess


CHANGED = ("hw/arm/xnuboot_sptm.c", "hw/arm/virt.c",
           "hw/arm/vresearch_pvg_reims.c", "target/arm/tcg/native-el0.c")


def sha(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def run(command, cwd, log):
    with log.open("w") as stream:
        subprocess.run([str(arg) for arg in command], cwd=cwd, stdout=stream,
                       stderr=subprocess.STDOUT, check=True, timeout=300)
    return {"command": [str(arg) for arg in command], "cwd": str(cwd),
            "log": str(log), "log_sha256": sha(log)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "baseline", "library", "include", "ndk", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    source, baseline, library, include, ndk, out = (
        getattr(args, name).resolve()
        for name in ("source", "baseline", "library", "include", "ndk", "out"))
    build = baseline / "qemu-out"
    header = include / "reims_vgpu.h"
    tools = ndk / "toolchains/llvm/prebuilt/linux-x86_64/bin"
    original = json.loads((baseline / "provenance/qemu-build.json").read_text())
    baseline_binary = build / "qemu-system-aarch64"
    baseline_sha = sha(baseline_binary)
    if baseline_sha != original["unstripped_binary"]["sha256"]:
        parser.error("the preserved baseline executable does not match its provenance")
    if library.suffix != ".a" or not library.is_file():
        parser.error("--library must be the new Android reims static archive")
    if "rvg_device_cpu_shadow_counts" not in header.read_text():
        parser.error("--include must contain the matching CPU-shadow C API")
    out.mkdir(parents=True, exist_ok=True)
    source_hashes = {name: sha(source / name) for name in CHANGED}
    library_sha, header_sha = sha(library), sha(header)
    compilation = json.loads((build / "compile_commands.json").read_text())
    records = []
    replacements = {}
    for name in CHANGED:
        old = next(item for item in compilation if item["file"].endswith("/" + name))
        command = shlex.split(old["command"])
        command[command.index("-c") + 1] = str(source / name)
        obj = out / (name.replace("/", "_") + ".o")
        for flag, value in (("-o", obj), ("-MQ", obj), ("-MF", str(obj) + ".d")):
            command[command.index(flag) + 1] = str(value)
        # Other headers remain the baseline's unchanged source/configuration.
        command[1:1] = ["-I" + str(include),
                        "-ffile-prefix-map=" + str(source) + "=/qemu-sptm"]
        record = run(command, build, obj.with_suffix(".log"))
        record.update(source=name, source_sha256=source_hashes[name],
                      object_sha256=sha(obj))
        records.append(record)
        replacements[old["output"]] = str(obj)
    links = json.loads(subprocess.check_output(
        [str(baseline / "host-tools/bin/ninja"), "-t", "compdb", "-x", "c_LINKER_RSP"],
        cwd=build, text=True))
    link = next(item for item in links if item["output"] == "qemu-system-aarch64")
    command = shlex.split(link["command"])
    for old, new in replacements.items():
        if command.count(old) != 1:
            raise RuntimeError("expected exactly one baseline object: " + old)
        command[command.index(old)] = new
    libraries = [index for index, arg in enumerate(command)
                 if arg.endswith("/libreims_vgpu.a")]
    if len(libraries) != 1:
        raise RuntimeError("expected exactly one baseline reims archive")
    command[libraries[0]] = str(library)
    unstripped = out / "qemu-system-aarch64.unstripped"
    command[command.index("-o") + 1] = str(unstripped)
    linked = run(command, build, out / "link.log")
    binary = out / "qemu-system-aarch64"
    subprocess.run([str(tools / "llvm-strip"), "--strip-unneeded", "-o",
                    str(binary), str(unstripped)], check=True)
    elf = subprocess.check_output(
        [str(tools / "llvm-readelf"), "-h", "-l", "-d", "--wide", str(binary)], text=True)
    (out / "elf.txt").write_text(elf)
    loads = [line for line in elf.splitlines() if re.match(r"\s*LOAD\s", line)]
    if not loads or any(int(line.split()[-1], 16) < 16384 for line in loads):
        raise RuntimeError("the candidate lost 16 KiB ELF LOAD alignment")
    needed = re.findall(r"\(NEEDED\).*\[(.*?)\]", elf)
    if needed != original["elf_needed"]:
        raise RuntimeError("the candidate's dynamic dependencies changed")
    if sha(library) != library_sha or sha(header) != header_sha or any(
            sha(source / name) != value for name, value in source_hashes.items()):
        raise RuntimeError("source or runtime inputs changed during the candidate build")
    if sha(baseline_binary) != baseline_sha:
        raise RuntimeError("the preserved baseline executable changed during this build")
    record = {
        "status": "BUILT_NOT_EXECUTED", "android_apk": False,
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=source, text=True).strip(),
        "source_sha256": source_hashes,
        "runtime_archive_sha256": library_sha, "runtime_header_sha256": header_sha,
        "baseline_binary_sha256": baseline_sha, "baseline_preserved": True,
        "compile": records, "link": linked,
        "binary": {"bytes": binary.stat().st_size, "sha256": sha(binary)},
        "elf_needed": needed, "load_segments": loads,
        "gpu_path_complete": False,
    }
    (out / "qemu-build.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record["binary"]))


if __name__ == "__main__":
    main()
