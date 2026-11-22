#!/usr/bin/env python3
"""Package already built GPU diagnostics and a verified incremental device update.

This never builds, installs, or runs an Android app. The base package is read
without changing it. Additional authored diagnostics can be supplied as payloads.
--base retains the v1 old-QEMU dictionary workflow. --base-package opts into v2:
reuse unchanged files and patch each changed ELF against its same-name old file.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import subprocess
import zipfile

from install_device_update import verified_package


ROOT = Path(__file__).resolve().parent
RESERVED_PAYLOAD_NAMES = {"package.json", "SHA256SUMS", "update.json",
                          "install_device_update.py"}


def sha(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def entry(path):
    return {"bytes": path.stat().st_size, "sha256": sha(path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("qemu", "fixture", "ndk", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    bases = parser.add_mutually_exclusive_group(required=True)
    bases.add_argument("--base", type=Path, help="legacy baseline; creates a v1 update")
    bases.add_argument("--base-package", type=Path,
                       help="complete verified qualification package; creates a v2 update")
    parser.add_argument("--payload", type=Path, action="append", default=[])
    parser.add_argument("--zstd", default="zstd")
    args = parser.parse_args()
    qemu, fixture, ndk, out = (getattr(args, name).resolve()
                             for name in ("qemu", "fixture", "ndk", "out"))
    per_file = args.base_package is not None
    base = (args.base_package if per_file else args.base).resolve()
    if per_file and out.is_relative_to(base):
        parser.error("--out must be outside the read-only base package")
    readelf = ndk / "toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf"
    qemu_record = json.loads((qemu / "qemu-build.json").read_text())
    fixture_record = json.loads((fixture / "native-fixture-build.json").read_text())
    if per_file:
        previous, base_files, base_identity = verified_package(base)
        base_manifest = base / "package.json"
        dependencies = previous["files"]
    else:
        base_manifest = base / "manifest.json"
        previous = json.loads(base_manifest.read_text())
        dependencies = previous["elf_files"]
    if not qemu_record["baseline_preserved"] or entry(qemu / "qemu-system-aarch64") != qemu_record["binary"]:
        parser.error("candidate QEMU differs from its successful build record")
    for name, record in fixture_record["artifacts"].items():
        if entry(fixture / name) != record:
            parser.error("native fixture differs from its build record: " + name)
    for name, digest in fixture_record["source_sha256"].items():
        if sha(ROOT / name) != digest:
            parser.error("native fixture source changed after building: " + name)
    if not per_file and sha(base / "qemu-system-aarch64") != previous["elf_files"]["qemu-system-aarch64"]["sha256"]:
        parser.error("base QEMU differs from its manifest")

    inputs = {
        "qemu-system-aarch64": qemu / "qemu-system-aarch64",
        "qemu-build.json": qemu / "qemu-build.json",
        "native-efi-owner": fixture / "native-efi-owner",
        "native-efi-guest.elf": fixture / "native-efi-guest.elf",
        "native-fixture-build.json": fixture / "native-fixture-build.json",
    }
    for name, record in dependencies.items():
        if name.startswith("lib/"):
            if len(Path(name).parts) != 2 or sha(base / name) != record["sha256"]:
                parser.error("base dependency differs from manifest: " + name)
            inputs[name] = base / name
    for path in args.payload:
        path = path.resolve()
        if (path.name in inputs or path.name in RESERVED_PAYLOAD_NAMES or
                not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", path.name) or
                not path.is_file()):
            parser.error("duplicate, reserved, unsafe or missing extra payload: " + str(path))
        inputs[path.name] = path
    out.mkdir(parents=True, exist_ok=False)
    package_name = "cpu-shadow-qualification"
    package = out / package_name
    update = out / "device-update"
    package.mkdir()
    (update / "payload").mkdir(parents=True)
    (update / "delta").mkdir()
    records = {}
    elf = {}
    for name, source in inputs.items():
        target = package / name
        target.parent.mkdir(parents=True, exist_ok=True)
        source_record = entry(source)
        shutil.copyfile(source, target)
        if entry(target) != source_record or entry(source) != source_record:
            raise RuntimeError("input changed during packaging: " + name)
        with target.open("rb") as stream:
            executable = stream.read(4) == b"\x7fELF"
        mode = 0o755 if executable and name != "native-efi-guest.elf" else 0o644
        target.chmod(mode)
        records[name] = {**source_record, "mode": mode}
        if executable and name != "native-efi-guest.elf":
            report = subprocess.check_output([str(readelf), "-h", "-l", "-d", "--wide", str(target)], text=True)
            loads = [line.split() for line in report.splitlines() if re.match(r"\s*LOAD\s", line)]
            if "AArch64" not in report or not loads or any(
                    int(line[-1], 16) < 16384 or int(line[1], 16) % 16384 != int(line[2], 16) % 16384
                    for line in loads):
                raise RuntimeError("bad Android ELF architecture/alignment: " + name)
            elf[name] = {"needed": re.findall(r"\(NEEDED\).*\[(.*?)\]", report),
                         "minimum_load_alignment": min(int(line[-1], 16) for line in loads)}
    available = {Path(name).name for name in elf} | set(previous["system_libraries"])
    missing = sorted({needed for info in elf.values() for needed in info["needed"] if needed not in available})
    if missing:
        raise RuntimeError("missing dependencies: " + str(missing))
    manifest = {
        "kind": "authored native EL0 and real GPU qualification",
        "status": "BUILT_NOT_EXECUTED", "android_apk": False,
        "gpu_path_complete": False, "files": records, "elf": elf,
        "system_libraries": previous["system_libraries"],
        "qemu_build_sha256": sha(qemu / "qemu-build.json"),
        "native_fixture_build_sha256": sha(fixture / "native-fixture-build.json"),
        "base_package_manifest_sha256": sha(base_manifest),
    }
    (package / "package.json").write_text(json.dumps(manifest, indent=2) + "\n")
    records["package.json"] = {**entry(package / "package.json"), "mode": 0o644}
    (package / "SHA256SUMS").write_text("".join(
        f"{record['sha256']}  {name}\n" for name, record in sorted(records.items())))
    records["SHA256SUMS"] = {**entry(package / "SHA256SUMS"), "mode": 0o644}

    files = []
    for name, record in sorted(records.items()):
        item = {"name": name, **record}
        old = base_files.get(name) if per_file else None
        unchanged = (old is not None and
                     all(old[key] == record[key] for key in ("bytes", "sha256")))
        if unchanged or (not per_file and name.startswith("lib/")):
            item["source"] = "base"
        elif (name in elf and record["bytes"] > 1024 * 1024 and
              (not per_file or old is not None)):
            patch = update / "delta" / (name + ".zst")
            patch.parent.mkdir(parents=True, exist_ok=True)
            dictionary = base / name if per_file else base / "qemu-system-aarch64"
            subprocess.run([args.zstd, "-q", "-19", "--patch-from=" + str(dictionary),
                            str(package / name), "-o", str(patch)], check=True, timeout=180)
            item.update(source="delta", patch={"name": patch.relative_to(update).as_posix(), **entry(patch)})
            if per_file:
                item["base_file"] = {"name": name, "bytes": old["bytes"], "sha256": old["sha256"]}
        else:
            target = update / "payload" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(package / name, target)
            item["source"] = "payload"
        files.append(item)
    update_record = {"format": "pixel-gpu-test-update-v2" if per_file else "pixel-gpu-test-update-v1",
                     "package_name": package_name, "files": files}
    if per_file:
        # Pin and recheck the complete base; a file changed during patching invalidates the update.
        verified_package(base, base_identity)
        update_record["base_package"] = base_identity
    else:
        update_record["base_binary"] = entry(base / "qemu-system-aarch64")
    (update / "update.json").write_text(json.dumps(update_record, indent=2) + "\n")
    shutil.copyfile(ROOT / "install_device_update.py", update / "install_device_update.py")
    archive = out / "device-update.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
        for path in sorted(p for p in update.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(path.relative_to(update).as_posix(), (2026, 11, 21, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zipped.writestr(info, path.read_bytes())
    with zipfile.ZipFile(archive) as zipped:
        if zipped.testzip() is not None:
            raise RuntimeError("update ZIP integrity check failed")
    result = {"package": str(package), "update_archive": str(archive),
              "archive": entry(archive), "update_manifest_sha256": sha(update / "update.json"),
              "files_verified": len(files), "dependency_closure_complete": True,
              "android_apk": False, "status": "BUILT_NOT_EXECUTED"}
    if per_file:
        result["update_format"] = update_record["format"]
        result["base_package"] = base_identity
    (out / "package-build.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
