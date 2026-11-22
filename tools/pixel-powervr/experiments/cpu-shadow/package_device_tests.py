#!/usr/bin/env python3
"""Package already built GPU diagnostics and a verified incremental device update.

This never builds, installs, or runs an Android app. The base package is read
without changing it. Additional authored diagnostics can be supplied as payloads.
--base retains the v1 old-QEMU dictionary workflow. --base-package opts into v2:
reuse unchanged files and patch each changed ELF against its same-name old file.
--delta-base NEW_PAYLOAD=BASE_FILE opts into v3 for an explicitly named verified
ELF dictionary. Named targets must be new ELF payloads larger than one MiB.
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

from install_device_update import relative, verified_package


ROOT = Path(__file__).resolve().parent
RESERVED_PAYLOAD_NAMES = {"package.json", "SHA256SUMS", "update.json",
                          "install_device_update.py"}
NATIVE_GUESTS = {"native-efi-guest.elf", "native-efi-swap-guest.elf"}
NATIVE_ARTIFACTS = NATIVE_GUESTS | {"native-efi-owner", "native-efi-swap-owner"}
MIN_DELTA_BYTES = 1024 * 1024


def sha(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def entry(path):
    return {"bytes": path.stat().st_size, "sha256": sha(path)}


def is_elf(path):
    with path.open("rb") as stream:
        return stream.read(4) == b"\x7fELF"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("qemu", "fixture", "ndk", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    bases = parser.add_mutually_exclusive_group(required=True)
    bases.add_argument("--base", type=Path, help="legacy baseline; creates a v1 update")
    bases.add_argument("--base-package", type=Path,
                       help="complete verified package; v2, or v3 with --delta-base")
    parser.add_argument("--payload", type=Path, action="append", default=[])
    parser.add_argument("--delta-base", action="append", default=[], metavar="NEW_PAYLOAD=BASE_FILE",
                        help="v3: compress a new >1 MiB ELF against a named verified base ELF")
    parser.add_argument("--zstd", default="zstd")
    args = parser.parse_args()
    qemu, fixture, ndk, out = (getattr(args, name).resolve()
                             for name in ("qemu", "fixture", "ndk", "out"))
    per_file = args.base_package is not None
    if args.delta_base and not per_file:
        parser.error("--delta-base requires --base-package (v3)")
    named_dictionaries = {}
    for selector in args.delta_base:
        if selector.count("=") != 1:
            parser.error("--delta-base must be NEW_PAYLOAD=BASE_FILE")
        name, dictionary = selector.split("=", 1)
        try:
            relative(name)
            relative(dictionary)
        except ValueError as error:
            parser.error(str(error))
        if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name) or
                name in named_dictionaries):
            parser.error("duplicate or unsafe --delta-base target: " + name)
        named_dictionaries[name] = dictionary
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
    if set(fixture_record["artifacts"]) != NATIVE_ARTIFACTS:
        parser.error("native fixture must contain the independent trap and swap cases")
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
        "native-fixture-build.json": fixture / "native-fixture-build.json",
    }
    inputs.update({name: fixture / name for name in sorted(NATIVE_ARTIFACTS)})
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
    for name, dictionary in named_dictionaries.items():
        if name not in inputs or name in base_files:
            parser.error("--delta-base target must be a new payload: " + name)
        if (inputs[name].stat().st_size <= MIN_DELTA_BYTES or
                name in NATIVE_GUESTS or not is_elf(inputs[name])):
            parser.error("--delta-base target must be a new >1 MiB Android ELF: " + name)
        if dictionary not in base_files or dictionary in RESERVED_PAYLOAD_NAMES:
            parser.error("--delta-base dictionary is absent from the verified base: " + dictionary)
        if not is_elf(base / dictionary):
            parser.error("--delta-base dictionary must be a verified ELF: " + dictionary)
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
        executable = is_elf(target)
        mode = 0o755 if executable and name not in NATIVE_GUESTS else 0o644
        target.chmod(mode)
        records[name] = {**source_record, "mode": mode}
        if executable and name not in NATIVE_GUESTS:
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
        elif (name in elf and record["bytes"] > MIN_DELTA_BYTES and
              (not per_file or old is not None or name in named_dictionaries)):
            patch = update / "delta" / (name + ".zst")
            patch.parent.mkdir(parents=True, exist_ok=True)
            dictionary_name = named_dictionaries.get(name, name) if per_file else "qemu-system-aarch64"
            dictionary = base / dictionary_name
            subprocess.run([args.zstd, "-q", "-19", "--patch-from=" + str(dictionary),
                            str(package / name), "-o", str(patch)], check=True, timeout=180)
            item.update(source="delta", patch={"name": patch.relative_to(update).as_posix(), **entry(patch)})
            if per_file:
                original = base_files[dictionary_name]
                item["base_file"] = {"name": dictionary_name, "bytes": original["bytes"],
                                     "sha256": original["sha256"]}
        else:
            target = update / "payload" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(package / name, target)
            item["source"] = "payload"
        files.append(item)
    version = ("pixel-gpu-test-update-v3" if named_dictionaries else
               "pixel-gpu-test-update-v2" if per_file else "pixel-gpu-test-update-v1")
    update_record = {"format": version,
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
    if named_dictionaries:
        result["named_delta_dictionaries"] = named_dictionaries
    (out / "package-build.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
