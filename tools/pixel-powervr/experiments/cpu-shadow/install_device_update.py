#!/usr/bin/env python3
"""Reconstruct a verified GPU-test package in a fresh directory; never execute it.

Use the SHA-256 printed by package_device_tests.py as --manifest-sha. The update
archive must also be checked against its separately published SHA-256 before
extracting this installer. Existing packages are read, never modified.
Use --base for legacy v1 updates, or --base-package for per-file v2 updates.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile


def sha(path):
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("not a regular file: " + str(path))
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def relative(name):
    if not isinstance(name, str) or not name or "\\" in name or "\0" in name:
        raise ValueError("invalid relative path")
    path = PurePosixPath(name)
    if not path.parts or path.is_absolute() or path.as_posix() != name or any(
            part in (".", "..") for part in path.parts):
        raise ValueError("unsafe relative path: " + name)
    return name


def check(path, entry):
    if (not isinstance(entry["bytes"], int) or entry["bytes"] < 0 or
            not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]) or
            path.lstat().st_size != entry["bytes"] or sha(path) != entry["sha256"]):
        raise ValueError("size or SHA-256 mismatch: " + str(path))


def copy(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with source.open("rb") as src, destination.open("xb") as dst:
        shutil.copyfileobj(src, dst, 1024 * 1024)
        dst.flush()
        os.fsync(dst.fileno())


def verified_package(root, expected=None):
    """Check a complete qualification package, including modes and exact paths."""
    if not stat.S_ISDIR(root.lstat().st_mode):
        raise ValueError("base package is not a real directory")
    if expected is not None:
        check(root / "package.json", expected["manifest"])
        check(root / "SHA256SUMS", expected["checksums"])
    identity = {name: {"bytes": (root / filename).stat().st_size,
                       "sha256": sha(root / filename)}
                for name, filename in (("manifest", "package.json"),
                                       ("checksums", "SHA256SUMS"))}
    manifest = json.loads((root / "package.json").read_text())
    if (manifest["kind"] != "authored native EL0 and real GPU qualification" or
            manifest["status"] != "BUILT_NOT_EXECUTED" or manifest["android_apk"] is not False):
        raise ValueError("base is not a qualification package")
    records = dict(manifest["files"])
    for name in records:
        relative(name)
        if name in ("package.json", "SHA256SUMS"):
            raise ValueError("base manifest contains a reserved file name")
    records.update({"package.json": {**identity["manifest"], "mode": 0o644},
                    "SHA256SUMS": {**identity["checksums"], "mode": 0o644}})
    actual = set()
    for path in root.rglob("*"):
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ValueError("base package contains a nonregular file: " + str(path))
        actual.add(path.relative_to(root).as_posix())
    if actual != set(records):
        raise ValueError("base package contains missing or extra files")
    for name, record in records.items():
        check(root / name, record)
        if (record["mode"] not in (0o600, 0o644, 0o700, 0o755) or
                stat.S_IMODE((root / name).stat().st_mode) != record["mode"]):
            raise ValueError("base package mode differs: " + name)
    declared = {}
    for line in (root / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        relative(name)
        if name in declared or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("invalid base package checksum list")
        declared[name] = digest
    if declared != {name: record["sha256"] for name, record in records.items()
                    if name != "SHA256SUMS"}:
        raise ValueError("incomplete or inconsistent base package checksums")
    return manifest, records, identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    bases = parser.add_mutually_exclusive_group(required=True)
    bases.add_argument("--base", type=Path, help="legacy baseline for a v1 update")
    bases.add_argument("--base-package", type=Path,
                       help="complete verified qualification package for a v2 update")
    parser.add_argument("--out-parent", type=Path, required=True)
    parser.add_argument("--manifest-sha", required=True)
    parser.add_argument("--zstd", type=Path,
                        default=Path("/data/data/com.termux/files/usr/bin/zstd"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    manifest = root / "update.json"
    if not re.fullmatch(r"[0-9a-f]{64}", args.manifest_sha) or sha(manifest) != args.manifest_sha:
        parser.error("update manifest differs from the expected SHA-256")
    update = json.loads(manifest.read_text())
    version = update["format"]
    if version not in ("pixel-gpu-test-update-v1", "pixel-gpu-test-update-v2"):
        parser.error("unsupported update format")
    per_file = version == "pixel-gpu-test-update-v2"
    if per_file != (args.base_package is not None):
        parser.error("v1 requires --base; v2 requires --base-package")
    package_name = relative(update["package_name"])
    if len(PurePosixPath(package_name).parts) != 1:
        parser.error("package name must be one path component")
    base_root = args.base_package if per_file else args.base
    if per_file and args.out_parent.resolve().is_relative_to(base_root.resolve()):
        parser.error("--out-parent must be outside the read-only base package")
    base = base_root / "qemu-system-aarch64"
    if per_file:
        _, base_files, _ = verified_package(base_root, update["base_package"])
    else:
        check(base, update["base_binary"])
    entries = update["files"]
    names = set()
    # Verify all inputs before creating an output directory.
    for entry in entries:
        name = relative(entry["name"])
        if name in names or entry["mode"] not in (0o600, 0o644, 0o700, 0o755):
            parser.error("duplicate name or invalid file mode")
        names.add(name)
        source = entry["source"]
        if source == "base":
            if per_file:
                if name not in base_files:
                    parser.error("reused file is absent from the verified base")
            elif not name.startswith("lib/") or len(PurePosixPath(name).parts) != 2:
                parser.error("only direct library files may be reused")
            check(base_root / name, entry)
        elif source == "payload":
            check(root / "payload" / name, entry)
        elif source == "delta":
            patch = relative(entry["patch"]["name"])
            if not patch.startswith("delta/"):
                parser.error("invalid delta location")
            check(root / patch, entry["patch"])
            if per_file:
                original = entry["base_file"]
                if relative(original["name"]) != name or name not in base_files:
                    parser.error("delta must use its same-name verified base file")
                check(base_root / name, original)
        else:
            parser.error("unknown file source")
    required = {"qemu-system-aarch64", "native-efi-owner", "native-efi-guest.elf",
                "package.json", "SHA256SUMS"}
    if not required.issubset(names):
        parser.error("update lacks a required test-package file")

    os.umask(0o077)
    destination = Path(tempfile.mkdtemp(prefix="pixel-cpu-shadow-", dir=args.out_parent))
    package = destination / package_name
    try:
        package.mkdir(mode=0o700)
        for entry in entries:
            name = entry["name"]
            target = package / name
            if entry["source"] == "delta":
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                dictionary = base_root / entry["base_file"]["name"] if per_file else base
                subprocess.run([
                    str(args.zstd), "-d", "-q", "--patch-from=" + str(dictionary),
                    "--memory=128MB", str(root / entry["patch"]["name"]),
                    "-o", str(target)], check=True, timeout=60)
                if target.stat().st_mode & 0o111:
                    raise ValueError("decoder made unverified bytes executable")
            else:
                origin = base_root if entry["source"] == "base" else root / "payload"
                copy(origin / name, target)
            check(target, entry)
        actual = {p.relative_to(package).as_posix() for p in package.rglob("*") if not p.is_dir()}
        if actual != names:
            raise ValueError("package contains missing or extra files")
        declared = {}
        for line in (package / "SHA256SUMS").read_text().splitlines():
            digest, name = line.split("  ", 1)
            name = relative(name)
            if name in declared or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("invalid package checksum list")
            declared[name] = digest
        if declared != {entry["name"]: entry["sha256"] for entry in entries
                        if entry["name"] != "SHA256SUMS"}:
            raise ValueError("incomplete or inconsistent package checksums")
        if per_file:
            verified_package(base_root, update["base_package"])
        else:
            check(base, update["base_binary"])
        for entry in entries:
            target = package / entry["name"]
            target.chmod(entry["mode"])
            with target.open("rb") as stream:
                os.fsync(stream.fileno())
        result = {
            "status": "GPU_TEST_PACKAGE_VERIFIED_NOT_EXECUTED",
            "package": str(package), "files_verified": len(entries),
            "update_manifest_sha256": args.manifest_sha,
            "qemu_sha256": next(e["sha256"] for e in entries
                                if e["name"] == "qemu-system-aarch64"),
            "base_rechecked": True, "android_apk": False,
            "gpu_path_complete": False,
        }
        if per_file:
            result["base_package"] = update["base_package"]
            result["update_format"] = version
        with (destination / "installation.json").open("x") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        print(json.dumps(result, indent=2))
    except BaseException:
        # Only this invocation's newly created, unpublished directory is removed.
        shutil.rmtree(destination)
        raise


if __name__ == "__main__":
    main()
