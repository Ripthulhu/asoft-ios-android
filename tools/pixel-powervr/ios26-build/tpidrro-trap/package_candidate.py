#!/usr/bin/env python3
"""Package the reviewed generic TPIDRRO candidate without target execution."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import stat
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "qemu-tpidrro-trap"
BASE = ROOT.parent / "qemu26-build-reconstruction"
QUALIFIED = BASE / "dist/qemu26-loader-smoke"
TOOLS = ROOT.parent / "tooling/android-ndk-r29/toolchains/llvm/prebuilt/linux-x86_64/bin"
GUEST = ROOT.parent / "asoft-ios-android/app/src/main/assets/el0bench.elf"
GUEST_SHA = "0454b4988e32f7476fd19c205343f436a702a70f69b1a5fb4d115c26ab64d98f"
NAME = "qemu26-tpidrro-trap-smoke"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inspect_elf(path):
    text = subprocess.check_output([str(TOOLS / "llvm-readelf"), "-h", "-l", "-d",
                                    "--wide", str(path)], text=True)
    if "AArch64" not in text:
        raise RuntimeError(f"Unexpected ELF architecture: {path}")
    loads = [line.split() for line in text.splitlines() if re.match(r"\s*LOAD\s", line)]
    if not loads or any(int(line[-1], 16) < 16384 or
                        int(line[1], 16) % 16384 != int(line[2], 16) % 16384
                        for line in loads):
        raise RuntimeError(f"ELF is not compatible with 16 KiB LOAD pages: {path}")
    return {"bytes": path.stat().st_size, "sha256": sha(path),
            "needed": re.findall(r"\(NEEDED\).*\[(.*?)\]", text),
            "minimum_load_alignment": min(int(line[-1], 16) for line in loads)}


def main():
    output = ROOT / NAME
    archive = ROOT / (NAME + ".zip")
    record_path = ROOT / "package.json"
    if output.exists() or archive.exists() or record_path.exists():
        raise RuntimeError("Package already exists; retain it and select a new identity")
    build = json.loads((ROOT / "build.json").read_text())
    if not build["baseline_preserved"] or sha(ROOT / "qemu-system-aarch64") != build["binary"]["sha256"]:
        raise RuntimeError("Candidate differs from its successful build record")
    if sha(SOURCE / "target/arm/tcg/native-el0.c") != build["source_sha256"]:
        raise RuntimeError("Native source changed after the recorded compilation")
    if sha(GUEST) != GUEST_SHA:
        raise RuntimeError("The pinned unmodified guest changed")
    tests = json.loads((ROOT / "host-validation.json").read_text())
    if not tests or not all(case["pass"] for case in tests.values()):
        raise RuntimeError("Host validation is incomplete")
    review = json.loads((ROOT / "review.json").read_text())
    if review["native_source_sha256"] != build["source_sha256"]:
        raise RuntimeError("Review does not cover the compiled source")
    (output / "lib").mkdir(parents=True)
    shutil.copyfile(ROOT / "qemu-system-aarch64", output / "qemu-system-aarch64")
    (output / "qemu-system-aarch64").chmod(0o755)
    previous = json.loads((QUALIFIED / "manifest.json").read_text())
    for name, entry in previous["files"].items():
        if not entry["package_path"].startswith("lib/"):
            continue
        original = QUALIFIED / entry["package_path"]
        if sha(original) != entry["sha256"]:
            raise RuntimeError(f"Previously qualified dependency changed: {name}")
        shutil.copyfile(original, output / "lib" / name)
        (output / "lib" / name).chmod(0o755)
    shutil.copyfile(GUEST, output / "el0bench.elf")
    script = "native-el0-tpidrro-trap-smoke.sh"
    shutil.copyfile(SOURCE / "scripts" / script, output / script)
    (output / script).chmod(0o755)
    for name in ("native-el0-tpidrro-trap.patch", "native-el0-required-plus-tpidrro-trap.patch",
                 "source-base.json"):
        shutil.copyfile(ROOT / name, output / name)
    shutil.copyfile(ROOT / "base-qemu-android-build.patch", output / "qemu-android-build.patch")
    elf = {path.relative_to(output).as_posix(): inspect_elf(path)
           for path in [output / "qemu-system-aarch64", *sorted((output / "lib").iterdir())]}
    available = {Path(name).name for name in elf} | set(previous["system_libraries"])
    missing = sorted({needed for entry in elf.values() for needed in entry["needed"]
                      if needed not in available})
    if missing:
        raise RuntimeError(f"Missing ELF dependencies: {missing}")
    manifest = {
        "kind": "isolated opt-in generic TPIDRRO native qualification",
        "qemu_source_base": build["base_commit"],
        "native_source_sha256": build["source_sha256"],
        "build_record_sha256": sha(ROOT / "build.json"),
        "host_validation_sha256": sha(ROOT / "host-validation.json"),
        "review_record_sha256": sha(ROOT / "review.json"),
        "incremental_patch_sha256": sha(ROOT / "native-el0-tpidrro-trap.patch"),
        "full_source_patch_sha256": sha(ROOT / "native-el0-required-plus-tpidrro-trap.patch"),
        "android_patch_sha256": sha(output / "qemu-android-build.patch"),
        "guest_sha256": GUEST_SHA,
        "runner_sha256": sha(output / script),
        "system_libraries": previous["system_libraries"],
        "elf_files": elf,
        "device_execution": "Not performed for this candidate",
        "gpu_integration": "None; ordinary memfd RAM and executable memfd code cache only",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "README.txt").write_text("""Generic TPIDRRO trap: separate, unrun native candidate

This candidate addresses the observed stock T7 mismatch without editing the
guest or weakening its checks. ASOFT_NATIVE_EL0_TPIDRRO_TRAP=1 copies read-only
executable pages into the memfd code cache and turns exact TPIDRRO reads into
handled UDF traps. The writable guest TPIDR remains native. The existing iOS
swap mode and default mode remain unchanged; the new mode rejects iOS swap,
in-process execution, disabled code cache, writable executable pages and
unsupported executable mapping/cache paths.

Extract into a NEW isolated /data/local/tmp directory, keeping lib/ together:

  sh /data/local/tmp/<directory>/native-el0-tpidrro-trap-smoke.sh /data/local/tmp/<directory>

The runner checks package hashes and negative configuration cases. It runs
the exact existing el0bench.elf with 512 MiB ordinary memfd RAM, two CPUs and
two native stub slots, stdin=/dev/null, and a 30-second bound plus a three-second
forced-stop grace period. It creates new results/ logs. It requires both CPUs'
T6/T7/T10 success and EXIT0, positive native SVC/time evidence, copied-code
activity and each CPU's >=2 TPIDRRO traps with last-PC at the actual T7 read,
0x100000768. Any MISMATCH, BAD copy result or nonzero guest exit fails.

Only NATIVE_TPIDRRO_TRAP_BENCH_PASS=1 is a successful qualification. Constructor
readiness and code-map request counts alone do not prove execution. This
candidate has compiled/linked and passed host tests and independent review,
but has NOT run on the phone. It does not establish iOS boot, ordinary-app
permissions, GPU-backed native RAM or a producer/adoption bridge.

The cache reserves a sparse 1 GiB memfd. Do not cap process file size below
that amount to constrain logs: the limit also applies to the code/RAM memfds.
The strict copied-code policy is for this pinned static read-only fixture;
concurrent writable aliases, self-modifying code and instruction-byte data
inspection are not qualified. Existing kernel/unsupported-instruction TCG
paths remain part of the hybrid engine.

Source base: alpersamur3/qemu-sptm 7a900afb62ddf94713e38ac5a4aafe1d42c9efa8
For a clean base, apply qemu-android-build.patch and
native-el0-required-plus-tpidrro-trap.patch (disjoint files).
The smaller native-el0-tpidrro-trap.patch is INCREMENTAL: use it only after the
required-native patch with SHA-256 f8894bf7f907301b4c18fd708fa162e50a1a4b337a55ce9072a4fdbf547cbef3.
Do not stack the incremental and full source patches. source-base.json records
the exact prerequisite identities; the full patch includes source tests and
docs/devel/native-el0-tpidrro-trap.rst. Build records retain the original
workspace paths and must be adapted explicitly for another checkout.
""")
    paths = sorted(p for p in output.rglob("*") if p.is_file())
    (output / "SHA256SUMS").write_text("".join(
        f"{sha(path)}  {path.relative_to(output).as_posix()}\n" for path in paths))
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path in sorted(p for p in output.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo((Path(NAME) / path.relative_to(output)).as_posix(), (2026, 11, 21, 0, 0, 0))
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | stat.S_IMODE(path.stat().st_mode)) << 16
            z.writestr(info, path.read_bytes())
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise RuntimeError("ZIP CRC verification failed")
    record = {"archive": str(archive), "bytes": archive.stat().st_size, "sha256": sha(archive),
              "payload_files": len(paths), "elf_files": len(elf), "dependency_closure_complete": True,
              "minimum_load_alignment": min(v["minimum_load_alignment"] for v in elf.values()),
              "binary": build["binary"], "device_execution": "Not performed for this candidate"}
    record_path.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
