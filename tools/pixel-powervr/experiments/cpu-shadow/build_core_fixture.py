#!/usr/bin/env python3
"""Build the authored C API/MMIO fixture against an existing Android static runtime.

The generator, C program and guest ABI builders must match committed reims source.
This links one API-29/16-KiB diagnostic; it never runs it or builds an APK.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
FIXTURE = "crates/reims-vgpu-c/tests/c/cpu_shadow_core"
BUILDERS = "tests/suite/pgtest"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def entry(path):
    return {"bytes": path.stat().st_size, "sha256": sha(path)}


def git(source, *arguments):
    return subprocess.check_output(
        ["git", "--no-optional-locks", "-C", str(source), *arguments],
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})


def source_snapshot(source):
    """Hash all generator imports and refuse missing, untracked or changed inputs."""
    head = git(source, "rev-parse", "HEAD").decode().strip()
    tracked = git(source, "ls-tree", "-rz", "--full-tree", head, "--",
                  FIXTURE + ".c", FIXTURE + ".py", BUILDERS)
    blobs = {}
    for record in tracked.split(b"\0"):
        if not record:
            continue
        metadata, raw_name = record.split(b"\t", 1)
        mode, kind, blob = metadata.decode().split()
        name = raw_name.decode()
        if name.startswith(BUILDERS + "/") and not name.endswith(".py"):
            continue
        if kind != "blob" or mode not in ("100644", "100755"):
            raise RuntimeError("source input is not a committed regular file: " + name)
        blobs[name] = blob
    required = {FIXTURE + ".c", FIXTURE + ".py", BUILDERS + "/abi.py",
                BUILDERS + "/resources_build.py", BUILDERS + "/scenario.py"}
    if not required.issubset(blobs):
        raise RuntimeError("commit the C fixture, generator and ABI builders before linking")
    actual_builders = {path.relative_to(source).as_posix()
                       for path in (source / BUILDERS).rglob("*.py")}
    if actual_builders != {name for name in blobs if name.startswith(BUILDERS + "/")}:
        raise RuntimeError("guest ABI builder files differ from the committed inventory")
    files = {}
    for name, blob in sorted(blobs.items()):
        path = source / name
        if not stat.S_ISREG(path.lstat().st_mode):
            raise RuntimeError("source input is not a regular file: " + name)
        record = entry(path)
        committed = git(source, "cat-file", "blob", blob)
        if (record["bytes"] != len(committed) or
                record["sha256"] != hashlib.sha256(committed).hexdigest()):
            raise RuntimeError("source input differs from its committed bytes: " + name)
        files[name] = {**record, "git_blob": blob}
    return {"path": str(source), "commit": head,
            "tree": git(source, "rev-parse", head + "^{tree}").decode().strip(),
            "files": files}


def command(arguments, log):
    with log.open("x") as stream:
        subprocess.run([str(arg) for arg in arguments], stdout=stream,
                       stderr=subprocess.STDOUT, check=True, timeout=180)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "include", "library", "ndk", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    source, include, library, ndk, out = (
        getattr(args, name).resolve() for name in ("source", "include", "library", "ndk", "out"))
    if out.is_relative_to(source):
        parser.error("--out must be outside the read-only reims source checkout")
    header = include / "reims_vgpu.h"
    compatibility = ROOT / "android_memfd_compat.c"
    if not header.is_file() or not library.is_file() or library.suffix != ".a":
        parser.error("the matching C header and Android static runtime archive must exist")
    with library.open("rb") as stream:
        if stream.read(8) != b"!<arch>\n":
            parser.error("--library must be a regular static archive")
    if "rvg_device_cpu_shadow_counts" not in header.read_text():
        parser.error("the runtime header lacks the actual CPU-shadow counters")
    snapshot = source_snapshot(source)
    inputs = {str(path): entry(path) for path in (header, library, compatibility, Path(__file__).resolve())}
    tools = ndk / "toolchains/llvm/prebuilt/linux-x86_64/bin"
    cc = tools / "aarch64-linux-android29-clang"
    readelf = tools / "llvm-readelf"
    out.mkdir(parents=True, exist_ok=False)
    generated = out / "cpu_shadow_core_data.h"
    generator = [sys.executable, "-I", "-B", source / (FIXTURE + ".py"), generated]
    command(generator, out / "generate.log")
    generated_record = entry(generated)
    if source_snapshot(source) != snapshot:
        raise RuntimeError("committed source changed while generating guest traffic")
    binary = out / "cpu-shadow-core"
    invocation = [cc, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-pedantic",
                  "-fPIE", "-pie", "-ffunction-sections", "-fdata-sections",
                  "-I" + str(include), "-I" + str(out), "-Wl,--gc-sections",
                  "-Wl,--no-undefined", "-Wl,--fatal-warnings", "-Wl,--build-id=sha1",
                  "-Wl,-z,max-page-size=16384", source / (FIXTURE + ".c"),
                  compatibility, library, "-ldl", "-llog", "-lunwind", "-lm", "-lc",
                  "-o", binary]
    command(invocation, out / "compile.log")
    if (source_snapshot(source) != snapshot or entry(generated) != generated_record or
            any(entry(Path(path)) != record for path, record in inputs.items())):
        raise RuntimeError("a source, generated header, C header, or library changed during linking")
    command([readelf, "-h", "-l", "-d", "--wide", binary], out / "elf.txt")
    elf = (out / "elf.txt").read_text()
    loads = [line.split() for line in elf.splitlines() if re.match(r"\s*LOAD\s", line)]
    if ("AArch64" not in elf or not re.search(r"Type:\s+DYN\b", elf) or not loads or
            any(int(line[-1], 16) < 16384 or
                int(line[1], 16) % 16384 != int(line[2], 16) % 16384 for line in loads)):
        raise RuntimeError("core fixture must be AArch64 PIE with congruent 16 KiB LOAD segments")
    needed = re.findall(r"\(NEEDED\).*\[(.*?)\]", elf)
    if any("reims" in name for name in needed):
        raise RuntimeError("core fixture unexpectedly depends on a shared reims runtime")
    manifest = {
        "status": "BUILT_NOT_EXECUTED", "kind": "authored_c_api_mmio_core_capability_fixture",
        "android_apk": False, "source": snapshot, "source_rechecked": True,
        "generator_command": [str(arg) for arg in generator],
        "generated_header": {"path": str(generated), **generated_record},
        "header": {"path": str(header), **inputs[str(header)]},
        "library": {"path": str(library), **inputs[str(library)], "linkage": "static"},
        "extra_sources": {str(compatibility): inputs[str(compatibility)]},
        "build_script_sha256": inputs[str(Path(__file__).resolve())]["sha256"],
        "binary": {"path": str(binary), **entry(binary)},
        "command": [str(arg) for arg in invocation],
        "compiler": subprocess.check_output([str(cc), "--version"], text=True).strip(),
        "android_api": 29, "minimum_load_alignment": min(int(line[-1], 16) for line in loads),
        "needed": needed, "expected_reims_feature": "guest-arm64 (16 KiB guest pages)",
        "run_environment": {"REIMS_VGPU_CPU_SHADOW": "1"},
        "run_arguments": [[], ["--no-argument-buffers"]],
        "gpu_tested": False, "apple_guest_tested": False, "gpu_path_complete": False,
    }
    (out / "core-fixture-build.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest["binary"]))


if __name__ == "__main__":
    main()
