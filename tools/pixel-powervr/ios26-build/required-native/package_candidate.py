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


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    build = json.loads((ROOT / "build.json").read_text())
    if not build["baseline_preserved"] or sha(ROOT / "qemu-system-aarch64") != build["binary"]["sha256"]:
        raise RuntimeError("Candidate does not match its successful build record")
    if sha(GUEST) != GUEST_SHA:
        raise RuntimeError("el0bench guest differs from the reviewed existing app asset")
    output = ROOT / "qemu26-native-required-smoke"
    if output.exists():
        raise RuntimeError("Candidate package already exists; retain it and choose a new path")
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
        "binary": build["binary"],
        "el0bench_sha256": GUEST_SHA,
        "libraries": libraries,
        "device_execution": "Not performed",
        "gpu_integration": "No producer/adoption backend integration; benchmark does not configure a GPU",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "README.txt").write_text("""Required-native EL0 memfd benchmark candidate

Extract this package to a new isolated device directory. Run:

  sh /data/local/tmp/<directory>/native-el0-memfd-smoke.sh /data/local/tmp/<directory>

The script verifies hashes, checks that the required-native flag rejects an
explicitly disabled engine, and runs the existing el0bench guest with 512 MiB
ordinary memfd RAM, two vCPUs and two native stub slots. The guest has a
30-second timeout plus a 3-second forced-stop grace period. All logs remain
under a new results/ directory. It must observe positive native entries/SVCs,
native time, a spawned stub, and successful guest correctness/completion checks
before reporting NATIVE_MEMFD_BENCH_PASS=1.

This package was compiled/linked and host-validated but has not run on the
phone. It does not replace an installed engine or configure GPU, iOS images,
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
""")
    paths = sorted(path for path in output.rglob("*") if path.is_file())
    (output / "SHA256SUMS").write_text("".join(
        f"{sha(path)}  {path.relative_to(output).as_posix()}\n" for path in paths))
    archive = ROOT / "qemu26-native-required-smoke.zip"
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
              "device_execution": "Not performed"}
    (ROOT / "package.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
