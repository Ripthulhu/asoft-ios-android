#!/usr/bin/env python3
"""Build the pinned isolated QEMU package in a fresh directory; never execute it.

Usage: python3 install-update.py OLD_PACKAGE OUTPUT_PARENT [ZSTD_EXECUTABLE]
Requires Python's standard library and an existing local zstd 1.5.7 CLI.
The caller must verify the update ZIP's published SHA-256 before extraction.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile

UPDATE_MANIFEST_SHA = 'a4f205dc964db27e2a44db9c9a1133fbd90ee7e5e6a09f43a7d5a431ce9bb068'
PACKAGE_MANIFEST_SHA = 'd18bf72d4491fc7a38b8335b79fd7a44221b66b7ff105cefa4d58410d83d946d'
BASE_SHA = '78e6174366fa3522fdcef0e1eca3f606ea3601823148bb69a31e4ecd18c42a35'
BASE_SIZE = 58516208
TARGET_SHA = 'a815e121d487c15cd9c1cec75ca6f43a48b2edf1ab42675bb9cde988b9679145'
TARGET_SIZE = 58529200
PACKAGE_NAME = 'qemu26-native-gpu-one-region-a815e121'
DEFAULT_ZSTD = "/data/data/com.termux/files/usr/bin/zstd"


def digest_file(path):
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError(f"not a regular file (symlinks are rejected): {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check_file(path, size, digest):
    if path.lstat().st_size != size or digest_file(path) != digest:
        raise ValueError(f"size or SHA-256 mismatch: {path}")


def relative_name(name):
    if not isinstance(name, str) or "\\" in name:
        raise ValueError("invalid package path")
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or any(part in (".", "..") for part in path.parts)
            or path.as_posix() != name or "\0" in name):
        raise ValueError(f"unsafe package path: {name!r}")
    return name


def load_update(root):
    path = root / "update.json"
    if digest_file(path) != UPDATE_MANIFEST_SHA:
        raise ValueError("update manifest SHA-256 mismatch")
    update = json.loads(path.read_text())
    if update["format"] != "pixel-qemu-zstd-update-v1" or update["package_name"] != PACKAGE_NAME:
        raise ValueError("unsupported update format or package name")
    if update["base_binary_sha256"] != BASE_SHA or update["target_binary_sha256"] != TARGET_SHA:
        raise ValueError("unexpected update base or target")
    files = {}
    for entry in update["files"]:
        name = relative_name(entry["name"])
        if name in files or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]):
            raise ValueError("duplicate path or malformed SHA-256")
        if not isinstance(entry["bytes"], int) or entry["bytes"] < 0:
            raise ValueError("invalid file size")
        if entry["mode"] not in (0o600, 0o644, 0o700, 0o755):
            raise ValueError("unsupported file permissions")
        expected_source = ("delta" if name == "qemu-system-aarch64" else
                           "base" if name == "el0bench.elf" or name.startswith("lib/") else
                           "payload")
        if entry["source"] != expected_source:
            raise ValueError(f"invalid source for {name}")
        if name.startswith("lib/") and len(PurePosixPath(name).parts) != 2:
            raise ValueError("only direct library files may be reused")
        files[name] = entry
    if len(files) != 25 or "SHA256SUMS" not in files or "qemu-system-aarch64" not in files:
        raise ValueError("unexpected full-package file set")
    return update, files


def verify_package(package, files):
    actual = {p.relative_to(package).as_posix() for p in package.rglob("*") if not p.is_dir()}
    if actual != set(files):
        raise ValueError("reconstructed package has missing or extra files")
    for name, entry in files.items():
        check_file(package / name, entry["bytes"], entry["sha256"])
    sums = package / "SHA256SUMS"
    if digest_file(sums) != PACKAGE_MANIFEST_SHA:
        raise ValueError("full-package SHA256SUMS differs from frozen package")
    declared = {}
    for line in sums.read_text().splitlines():
        digest, name = line.split("  ", 1)
        relative_name(name)
        if name in declared or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("malformed full-package checksum entry")
        declared[name] = digest
    if set(declared) != set(files) - {"SHA256SUMS"}:
        raise ValueError("full-package checksum coverage is incomplete")
    for name, digest in declared.items():
        if digest != files[name]["sha256"]:
            raise ValueError("full-package checksum disagreement")


def copy_exclusive(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with source.open("rb") as src, destination.open("xb") as dst:
        shutil.copyfileobj(src, dst, 1024 * 1024)
        dst.flush()
        os.fsync(dst.fileno())


def main():
    if len(sys.argv) not in (3, 4):
        raise ValueError(__doc__.strip())
    old = Path(sys.argv[1])
    parent = Path(sys.argv[2])
    zstd = Path(sys.argv[3] if len(sys.argv) == 4 else DEFAULT_ZSTD)
    root = Path(__file__).resolve().parent
    os.umask(0o077)
    update, files = load_update(root)
    base = old / "qemu-system-aarch64"
    # All inputs are checked before any output directory is created.
    check_file(base, BASE_SIZE, BASE_SHA)
    patch = root / relative_name(update["delta_name"])
    check_file(patch, update["delta_bytes"], update["delta_sha256"])
    for name, entry in files.items():
        if entry["source"] == "delta":
            continue
        source = (old if entry["source"] == "base" else root / "payload") / name
        check_file(source, entry["bytes"], entry["sha256"])

    destination = None
    try:
        destination = Path(tempfile.mkdtemp(prefix="pixel-native-gpu-verified-", dir=parent))
        package = destination / PACKAGE_NAME
        package.mkdir(mode=0o700)
        for name, entry in files.items():
            if entry["source"] == "delta":
                continue
            source = (old if entry["source"] == "base" else root / "payload") / name
            copy_exclusive(source, package / name)
        binary = package / "qemu-system-aarch64"
        # Explicit units are essential: unitless -M128 means 128 bytes.
        # No --force and an entirely fresh path: nothing existing can be replaced.
        subprocess.run(
            [str(zstd), "-d", "-q", "--patch-from=" + str(base),
             "--memory=128MB", str(patch), "-o", str(binary)],
            check=True, timeout=30,
        )
        check_file(binary, TARGET_SIZE, TARGET_SHA)
        if binary.stat().st_mode & 0o111:
            raise ValueError("decoder unexpectedly made unverified bytes executable")
        verify_package(package, files)
        check_file(base, BASE_SIZE, BASE_SHA)
        # Make executable only after the binary and the entire frozen package pass.
        for name, entry in files.items():
            path = package / name
            os.chmod(path, entry["mode"])
            with path.open("rb") as stream:
                os.fsync(stream.fileno())
        result = {
            "status": "UPDATE_PACKAGE_VERIFIED_NOT_EXECUTED",
            "package": str(package), "binary": str(binary),
            "binary_sha256": TARGET_SHA, "full_package_files_verified": len(files),
            "full_package_zip_sha256": update["full_package_zip_sha256"],
            "base_rechecked": True,
            "runner": str(package / "run-one-region.sh"),
        }
        with (destination / "installation-result.json").open("x") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        print(json.dumps(result, indent=2))
    except BaseException:
        if destination is not None:
            # Only this invocation's freshly-created directory is ever removed.
            shutil.rmtree(destination)
        raise


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"UPDATE_INSTALL_FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
