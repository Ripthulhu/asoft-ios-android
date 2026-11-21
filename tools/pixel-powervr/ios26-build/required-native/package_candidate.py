#!/usr/bin/env python3
"""Package the candidate and ordinary-memfd benchmark without running it."""
from pathlib import Path
import hashlib
import json
import shutil
import stat
import zipfile

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "qemu-native-required"
BASE = ROOT.parent / "qemu26-build-reconstruction"
LIBRARY_INPUT = BASE / "dist/qemu26-loader-smoke"
GUEST = ROOT.parent / "asoft-ios-android/app/src/main/assets/el0bench.elf"
GUEST_SHA = "0454b4988e32f7476fd19c205343f436a702a70f69b1a5fb4d115c26ab64d98f"
PACKAGE_NAME = "qemu26-native-required-smoke-v2"
PREVIOUS_PACKAGE_SHA = "314be50ecafdcc7e9dcffd552a0c7e5e0da1f51a1337024ac66586ca3e264cd0"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    build = json.loads((ROOT / "build.json").read_text())
    if not build["baseline_preserved"] or sha(ROOT / "qemu-system-aarch64") != build["binary"]["sha256"]:
        raise RuntimeError("Candidate does not match its successful build record")
    if sha(GUEST) != GUEST_SHA:
        raise RuntimeError("el0bench guest differs from the reviewed existing app asset")
    output = ROOT / PACKAGE_NAME
    archive = ROOT / (PACKAGE_NAME + ".zip")
    record_path = ROOT / "package-v2.json"
    if output.exists() or archive.exists() or record_path.exists():
        raise RuntimeError("Candidate package or record already exists; retain it and choose a new path")
    (output / "lib").mkdir(parents=True)
    shutil.copyfile(ROOT / "qemu-system-aarch64", output / "qemu-system-aarch64")
    (output / "qemu-system-aarch64").chmod(0o755)
    qualified = json.loads((LIBRARY_INPUT / "manifest.json").read_text())
    libraries = {}
    for name, entry in qualified["files"].items():
        if not entry["package_path"].startswith("lib/"):
            continue
        path = LIBRARY_INPUT / entry["package_path"]
        if sha(path) != entry["sha256"]:
            raise RuntimeError(f"Qualified library changed: {name}")
        shutil.copyfile(path, output / "lib" / name)
        (output / "lib" / name).chmod(0o755)
        libraries[name] = entry["sha256"]
    shutil.copyfile(GUEST, output / "el0bench.elf")
    shutil.copyfile(SOURCE / "scripts/native-el0-memfd-smoke.sh", output / "native-el0-memfd-smoke.sh")
    (output / "native-el0-memfd-smoke.sh").chmod(0o755)
    shutil.copyfile(ROOT / "native-el0-required.patch", output / "native-el0-required.patch")
    manifest = {
        "kind": "isolated native EL0 ordinary-memfd benchmark candidate",
        "qemu_source_base": build["base_commit"],
        "native_required_patch_sha256": sha(ROOT / "native-el0-required.patch"),
        "build_record_sha256": sha(ROOT / "build.json"),
        "host_test_record_sha256": sha(ROOT / "constructor-tests.json"),
        "benchmark_log_test_record_sha256": sha(ROOT / "benchmark-log-tests.json"),
        "package_revision": 2,
        "previous_package_sha256": PREVIOUS_PACKAGE_SHA,
        "revision_scope": "Guest CPU-prefix completion checker, host fixtures and documentation; executable unchanged",
        "binary": build["binary"],
        "el0bench_sha256": GUEST_SHA,
        "libraries": libraries,
        "device_execution": "This revised package has not been run on the device",
        "gpu_integration": "No producer/adoption backend integration; benchmark does not configure a GPU",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "README.txt").write_text("""Required-native EL0 memfd benchmark candidate, checker revision 2

Extract this package to a new isolated device directory. Run:

  sh /data/local/tmp/<directory>/native-el0-memfd-smoke.sh /data/local/tmp/<directory>

The script verifies hashes, checks that the required-native flag rejects an
explicitly disabled engine, and runs the existing el0bench guest with 512 MiB
ordinary memfd RAM, two vCPUs and two native stub slots. The guest has a
30-second timeout plus a 3-second forced-stop grace period. All logs remain
under a new results/ directory. It must observe positive native entries/SVCs,
native time, a spawned stub, and successful guest correctness/completion checks
before reporting NATIVE_MEMFD_BENCH_PASS=1.
The existing guest's T10 success string is lowercase check=ok; check=BAD is
always rejected. Guest output uses a [cpuN] prefix: the checker requires
[cpu0] EXIT 0 faults=... and rejects any CPU's nonzero signed exit, including
mixed successful/failed lines. Fifteen host log-checker fixtures passed.

This revision changes the script, fixtures and documentation; its compiled
executable is byte-for-byte unchanged. This revised package has not run on the
phone. The previous package's ZIP identity is preserved separately; its initial
guest attempt timed out without guest output. This checker correction neither
explains that stall nor establishes native execution. The 30-second limit is
a diagnostic bound, stricter than the app's default 120-second limit.

It does not replace an installed engine or configure GPU, iOS images,
disks, networking or device policy. The existing reims GPU-memory backend is
unchanged. A shell result qualifies only that shell identity/permissions.

The constructor-ready message is not evidence of active guest execution.
The included source patch explains deferred checks and remaining runtime
limitations. Keep the matched private libraries together; the script uses its
own LD_LIBRARY_PATH and clears inherited ASOFT/Vulkan environment settings.

Source base: alpersamur3/qemu-sptm @ 7a900afb62ddf94713e38ac5a4aafe1d42c9efa8
Additional Android configuration patch and matched dependency provenance:
qemu26-build-reconstruction/provenance/qemu-android-build.patch
qemu26-build-reconstruction/README.md
The included native-required patch does not contain meson.build. It and the
separate Android Meson patch touch different files and can be applied together.
""")
    paths = sorted(path for path in output.rglob("*") if path.is_file())
    (output / "SHA256SUMS").write_text("".join(
        f"{sha(path)}  {path.relative_to(output).as_posix()}\n" for path in paths))
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as stream:
        for path in sorted(p for p in output.rglob("*") if p.is_file()):
            item = zipfile.ZipInfo((Path(output.name) / path.relative_to(output)).as_posix(), (2026, 11, 21, 0, 0, 0))
            item.create_system = 3
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = (stat.S_IFREG | stat.S_IMODE(path.stat().st_mode)) << 16
            stream.writestr(item, path.read_bytes())
    with zipfile.ZipFile(archive) as stream:
        if stream.testzip() is not None:
            raise RuntimeError("Archive CRC validation failed")
    record = {"archive": str(archive), "bytes": archive.stat().st_size,
              "sha256": sha(archive), "payload_files": len(paths),
              "package_revision": 2,
              "previous_package_sha256": PREVIOUS_PACKAGE_SHA,
              "executable_unchanged": True,
              "device_execution": "This revised package has not been run on the device"}
    record_path.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
