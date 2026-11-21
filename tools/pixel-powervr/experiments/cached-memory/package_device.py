#!/usr/bin/env python3
"""Package the frozen default-only Pixel diagnostic; never rebuild or run it."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import sys
import zipfile
import zlib


BINARY_NAME = "cached_memory_diagnostic"
BINARY_SHA256 = "f69664840ba2e7588e196849ea4ce9ff598a8c0081c22e8ac249830fb43f2b9c"
BINARY_BYTES = 61280
PREFIX = "pixel-cached-memory-device"
FIXED_TIME = (2026, 11, 21, 0, 0, 0)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_frozen(source: Path) -> int:
    count = 0
    for line in (source / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected, separator, name = line.partition("  ")
        relative = PurePosixPath(name)
        if (not separator or len(expected) != 64 or relative.is_absolute()
                or ".." in relative.parts or not relative.parts):
            raise ValueError("Malformed frozen manifest entry")
        if digest((source / relative).read_bytes()) != expected:
            raise ValueError(f"Frozen manifest mismatch: {name}")
        count += 1
    if not count:
        raise ValueError("Empty frozen manifest")
    data = (source / BINARY_NAME).read_bytes()
    if len(data) != BINARY_BYTES or digest(data) != BINARY_SHA256:
        raise ValueError("Unexpected executable: only the frozen candidate may be packaged")
    return count


def package(source: Path, output: Path) -> dict[str, object]:
    frozen_count = verify_frozen(source)
    if output.exists():
        raise ValueError(f"Refusing to overwrite an existing archive: {output}")
    source_inputs = ["DEVICE-PACKAGE.md", "run-cached-memory.sh", "package_device.py"]
    provenance = {
        "schema": 1,
        "package": PREFIX,
        "status": "Prepared for manual upload; no phone execution performed by packaging.",
        "binary": {"filename": BINARY_NAME, "bytes": BINARY_BYTES, "sha256": BINARY_SHA256},
        "command": [BINARY_NAME, "--cached-memory"],
        "runner_accepts_arguments": False,
        "producer_cpu_atomics_requested": False,
        "ordinary_memfd_control_exercises_LSE": True,
        "outer_timeout_seconds": 65,
        "outer_timeout_signal": "KILL",
        "kernel_panic_contained": False,
        "frozen_manifest": {
            "sha256": digest((source / "SHA256SUMS").read_bytes()),
            "entries_verified": frozen_count,
        },
        "build_info_sha256": digest((source / "build-info.json").read_bytes()),
        "packaging_input_sha256": {
            name: digest((source / name).read_bytes()) for name in source_inputs
        },
        "scope": "Cached producer basic diagnostic; not QEMU or general guest-RAM qualification.",
    }
    payload = {
        "README.md": (source / "DEVICE-PACKAGE.md").read_bytes(),
        "PROVENANCE.json": (json.dumps(provenance, indent=2, sort_keys=True) + "\n").encode(),
        "run-cached-memory.sh": (source / "run-cached-memory.sh").read_bytes(),
        BINARY_NAME: (source / BINARY_NAME).read_bytes(),
    }
    payload["SHA256SUMS"] = "".join(
        f"{digest(payload[name])}  {name}\n" for name in sorted(payload)
    ).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with output.open("xb") as stream:
            created = True
            with zipfile.ZipFile(stream, mode="w", compression=zipfile.ZIP_DEFLATED,
                                 compresslevel=9, strict_timestamps=True) as archive:
                for name in sorted(payload):
                    info = zipfile.ZipInfo(f"{PREFIX}/{name}", FIXED_TIME)
                    info.create_system = 3
                    mode = 0o700 if name in (BINARY_NAME, "run-cached-memory.sh") else 0o600
                    info.external_attr = (stat.S_IFREG | mode) << 16
                    info.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(info, payload[name], compresslevel=9)
        with zipfile.ZipFile(output) as archive:
            if archive.testzip() is not None:
                raise ValueError("ZIP CRC verification failed")
            expected_names = [f"{PREFIX}/{name}" for name in sorted(payload)]
            if archive.namelist() != expected_names:
                raise ValueError("ZIP members differ from planned payload")
            for name, data in payload.items():
                if archive.read(f"{PREFIX}/{name}") != data:
                    raise ValueError(f"ZIP payload verification failed: {name}")
            for line in payload["SHA256SUMS"].decode().splitlines():
                expected, name = line.split("  ", 1)
                if digest(archive.read(f"{PREFIX}/{name}")) != expected:
                    raise ValueError(f"Packaged checksum mismatch: {name}")
        if verify_frozen(source) != frozen_count:
            raise ValueError("Frozen manifest changed while packaging")
    except BaseException:
        if created:
            output.unlink(missing_ok=True)
        raise
    return {
        "output": str(output),
        "bytes": output.stat().st_size,
        "sha256": digest(output.read_bytes()),
        "binary_sha256": BINARY_SHA256,
        "frozen_manifest_entries_verified": frozen_count,
        "package_members": sorted(payload),
        "ZIP_CRC_and_payload_SHA256": "PASS",
        "phone_execution": False,
        "python": sys.version.split()[0],
        "zlib": zlib.ZLIB_RUNTIME_VERSION,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path,
                        help="New ZIP path; an existing file is never overwritten")
    args = parser.parse_args()
    try:
        result = package(Path(__file__).resolve().parent, args.output.resolve())
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        parser.exit(1, f"Packaging failed: {error}\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
