#!/usr/bin/env python3
"""Package the linked Android QEMU and its exact ELF dependency closure.

This does not start a guest or execute target binaries on the build host.
"""
from pathlib import Path
import hashlib
import json
import re
import shutil
import stat
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT.parent / "tooling/android-ndk-r29/toolchains/llvm/prebuilt/linux-x86_64/bin"
LIBS = ROOT / "termux-root/data/data/com.termux/files/usr/lib"
SYSTEM = {"libc.so", "libm.so", "libdl.so", "liblog.so", "libandroid.so"}


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inspect(path):
    output = subprocess.check_output(
        [str(TOOLS / "llvm-readelf"), "-h", "-l", "-d", "--wide", str(path)],
        text=True,
    )
    if not re.search(r"Machine:\s+AArch64", output):
        raise RuntimeError(f"Not AArch64: {path}")
    alignments = [int(line.split()[-1], 16) for line in output.splitlines()
                  if re.match(r"\s*LOAD\s", line)]
    if not alignments or any(value < 16384 for value in alignments):
        raise RuntimeError(f"LOAD alignment below 16 KiB: {path}")
    return {
        "bytes": path.stat().st_size,
        "sha256": sha(path),
        "needed": re.findall(r"\(NEEDED\).*\[(.*?)\]", output),
        "soname": re.findall(r"\(SONAME\).*\[(.*?)\]", output),
        "runpath": re.findall(r"\(RUNPATH\).*\[(.*?)\]", output),
        "load_alignments": alignments,
    }


SMOKE = r'''#!/system/bin/sh
# Loader and registration checks only. No guest images or GPU allocations.
set -eu
smoke_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$smoke_root"
sha256sum -c SHA256SUMS
smoke_results="$smoke_root/results/$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir -p "$smoke_results"
run_info() {
    smoke_name=$1
    shift
    # A clean environment prevents inherited ASOFT settings spawning stubs.
    set +e
    env -i PATH=/system/bin LD_LIBRARY_PATH="$smoke_root/lib" \
        /system/bin/timeout -k 2 10 "$smoke_root/bin/qemu-system-aarch64" "$@" \
        > "$smoke_results/$smoke_name.txt" 2>&1
    smoke_status=$?
    set -e
    cat "$smoke_results/$smoke_name.txt"
    printf '%s_EXIT=%s\n' "$smoke_name" "$smoke_status"
    if [ "$smoke_status" -ne 0 ]; then
        printf 'QEMU_LOADER_SMOKE_PASS=0\nRESULTS=%s\n' "$smoke_results"
        exit "$smoke_status"
    fi
}
run_info version -version
run_info machines -machine help
run_info accelerators -accel help
grep -q '^vresearch ' "$smoke_results/machines.txt"
printf 'QEMU_LOADER_SMOKE_PASS=1\nRESULTS=%s\n' "$smoke_results"
'''

README = """Android QEMU loader smoke package

This is the source-built QEMU 11.1.0 fork with native EL0 and the actual reims
C API linked. It is an isolated diagnostic executable, not an app-engine update.
The PowerVR producer/adoption memory backend has not been integrated into it.

Copy or extract the directory to a NEW location below /data/local/tmp, then run:

  sh /data/local/tmp/<new-directory>/loader-smoke.sh

The wrapper verifies every payload hash and runs only -version, -machine help
and -accel help, with a 10 second timeout for each command. It records output
under its own results directory. A clean environment prevents inherited ASOFT
options from starting native stub processes. It does not start a guest, create
disks, allocate GPU-shared memory, change device policy or replace an installed
engine. These checks establish loader/registration behavior only; they do not
qualify native guest execution, GPU integration or an iOS boot.

Keep all bundled libraries together. They are the exact closure of this binary,
from the previously signature/hash-verified Termux package set. The wrapper sets
LD_LIBRARY_PATH to this private lib directory; the original build/Termux RUNPATHs
are retained as recorded in manifest.json. No system or Vulkan driver library is
bundled or replaced. All bundled ELF LOAD segments are 16 KiB aligned.

Sources and build provenance:
  QEMU: alpersamur3/qemu-sptm @ 7a900afb62ddf94713e38ac5a4aafe1d42c9efa8
  qemu26-build-reconstruction/README.md and provenance/qemu-build.json
  qemu26-build-reconstruction/provenance/qemu-android-build.patch
  qemu26-build-reconstruction/provenance/reims-build.json
  qemu26-build-reconstruction/termux-lock.json
"""


def main():
    build = json.loads((ROOT / "provenance/qemu-build.json").read_text())
    if build["exit_code"] != 0:
        raise RuntimeError("No successful linked QEMU build")
    binary = ROOT / "dist/qemu-system-aarch64"
    if sha(binary) != build["stripped_binary"]["sha256"]:
        raise RuntimeError("QEMU binary does not match its build record")
    qualified = json.loads((ROOT / "provenance/termux-elf-closure.json").read_text())
    hashes = {entry["sha256"] for entry in qualified["resolved"].values()}
    package = ROOT / "dist/qemu26-loader-smoke"
    if package.exists():
        raise RuntimeError(f"Output already exists; retain it and choose a new package path: {package}")
    (package / "bin").mkdir(parents=True)
    (package / "lib").mkdir()
    entries = {}
    pending = ["qemu-system-aarch64"]
    while pending:
        name = pending.pop()
        if name in SYSTEM or name in entries:
            continue
        source = binary if name == binary.name else LIBS / name
        record = inspect(source)
        if name != binary.name and record["sha256"] not in hashes:
            raise RuntimeError(f"Library is absent from the qualified input closure: {name}")
        # Some small Termux compatibility libraries omit DT_SONAME. The
        # exact requested filename and qualified content hash still identify
        # those files; reject only an explicit conflicting SONAME.
        if name != binary.name and record["soname"] and record["soname"] != [name]:
            raise RuntimeError(f"SONAME mismatch for {name}: {record['soname']}")
        target = package / ("bin" if name == binary.name else "lib") / name
        shutil.copyfile(source, target)
        target.chmod(0o755)
        record["package_path"] = target.relative_to(package).as_posix()
        record["source_path"] = source.relative_to(ROOT).as_posix()
        entries[name] = record
        pending.extend(record["needed"])
    manifest = {
        "kind": "isolated Android QEMU loader smoke package",
        "build_record_sha256": sha(ROOT / "provenance/qemu-build.json"),
        "configure_record_sha256": sha(ROOT / "provenance/qemu-configure.json"),
        "system_libraries": sorted(SYSTEM),
        "runtime_backend": "Unmodified existing reims backend; no producer/adoption integration",
        "device_execution": "Not yet established",
        "files": dict(sorted(entries.items())),
    }
    (package / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (package / "README.txt").write_text(README)
    (package / "loader-smoke.sh").write_text(SMOKE)
    (package / "loader-smoke.sh").chmod(0o755)
    files = sorted(path for path in package.rglob("*") if path.is_file())
    (package / "SHA256SUMS").write_text("".join(
        f"{sha(path)}  {path.relative_to(package).as_posix()}\n" for path in files))
    archive = ROOT / "dist/qemu26-loader-smoke.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        for path in sorted(p for p in package.rglob("*") if p.is_file()):
            entry = zipfile.ZipInfo((Path(package.name) / path.relative_to(package)).as_posix(), (2026, 11, 21, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.create_system = 3
            entry.external_attr = (stat.S_IFREG | stat.S_IMODE(path.stat().st_mode)) << 16
            output.writestr(entry, path.read_bytes())
    record = {"archive": str(archive), "bytes": archive.stat().st_size,
              "sha256": sha(archive), "non_system_libraries": len(entries) - 1,
              "device_execution": "Not yet established"}
    (ROOT / "provenance/qemu-smoke-package.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
