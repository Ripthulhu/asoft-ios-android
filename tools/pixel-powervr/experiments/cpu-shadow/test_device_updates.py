#!/usr/bin/env python3
"""Exercise real v1/v2 packaging and zstd reconstruction with synthetic data.

The ELF containers have AArch64 headers for real readelf inspection, but contain
no runnable program. No native code is compiled or executed and no device is used.
Requires Python, readelf (GNU or LLVM), and zstd on the host PATH.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parent
ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def entry(path):
    return {"bytes": path.stat().st_size, "sha256": sha(path)}


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.chmod(0o644)


def save_json(path, value):
    save(path, (json.dumps(value, indent=2) + "\n").encode())


def elf(length, seed):
    # One aligned read-only LOAD segment. There is no entry point or machine code.
    identity = b"\x7fELF" + bytes([2, 1, 1, 0]) + bytes(8)
    header = struct.pack("<16sHHIQQQIHHHHHH", identity, 3, 183, 1,
                         0, 64, 0, 0, 64, 56, 1, 64, 0, 0)
    segment = struct.pack("<IIQQQQQQ", 1, 4, 0, 0, 0, length, length, 16384)
    pattern = hashlib.sha256(seed).digest()
    return header + segment + (pattern * ((length - 120 + 31) // 32))[:length - 120]


def snapshot(directory):
    return {path.relative_to(directory).as_posix():
            {**entry(path), "mode": stat.S_IMODE(path.stat().st_mode)}
            for path in sorted(directory.rglob("*")) if path.is_file()}


def qemu_fixture(folder, data):
    save(folder / "qemu-system-aarch64", data)
    save_json(folder / "qemu-build.json", {
        "test_fixture": "synthetic non-runnable ELF; no build performed",
        "baseline_preserved": True, "binary": entry(folder / "qemu-system-aarch64"),
    })


def package(work, label, base_flag, base, qemu, fixture, ndk, payloads):
    out = work / label
    command = [sys.executable, str(ROOT / "package_device_tests.py"),
               "--qemu", str(qemu), "--fixture", str(fixture), base_flag, str(base),
               "--ndk", str(ndk), "--out", str(out), "--zstd", shutil.which("zstd")]
    for path in payloads:
        command.extend(["--payload", str(path)])
    subprocess.run(command, check=True, capture_output=True, text=True, env=ENV)
    build = json.loads((out / "package-build.json").read_text())
    assert entry(out / "device-update.zip") == build["archive"]
    extracted = work / (label + "-zip")
    extracted.mkdir()
    with zipfile.ZipFile(out / "device-update.zip") as archive:
        assert archive.testzip() is None
        for info in archive.infolist():
            assert stat.S_ISREG(info.external_attr >> 16)
            assert stat.S_IMODE(info.external_attr >> 16) == 0o644
        archive.extractall(extracted)
    assert sha(extracted / "update.json") == build["update_manifest_sha256"]
    return out, extracted, json.loads((extracted / "update.json").read_text())


def install(work, label, update, base_flag, base, expected_package=None):
    output = work / (label + "-install")
    output.mkdir()
    save(output / "preserve.txt", b"existing sibling must survive\n")
    before = snapshot(output)
    result = subprocess.run([
        sys.executable, str(update / "install_device_update.py"), base_flag, str(base),
        "--out-parent", str(output), "--manifest-sha", sha(update / "update.json"),
        "--zstd", shutil.which("zstd"),
    ], capture_output=True, text=True, env=ENV)
    if expected_package is None:
        assert result.returncode != 0, "tampered update was accepted: " + label
        assert snapshot(output) == before, "failed install changed existing data: " + label
        assert list(output.iterdir()) == [output / "preserve.txt"], label
        return result.stderr
    assert result.returncode == 0, (label, result.stderr)
    report = json.loads(result.stdout)
    assert report["status"] == "GPU_TEST_PACKAGE_VERIFIED_NOT_EXECUTED"
    assert report["base_rechecked"] is True
    assert snapshot(Path(report["package"])) == snapshot(expected_package)
    assert entry(output / "preserve.txt") == {key: before["preserve.txt"][key]
                                             for key in ("bytes", "sha256")}
    return report


def main():
    readelf = shutil.which("llvm-readelf") or shutil.which("readelf")
    assert readelf and shutil.which("zstd"), "readelf and zstd are required"
    work = Path(tempfile.mkdtemp(prefix="pixel-update-roundtrip-", dir="/tmp"))
    ndk = work / "readelf-tools"
    tool = ndk / "toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf"
    tool.parent.mkdir(parents=True)
    tool.symlink_to(readelf)
    old = work / "legacy-base"
    save(old / "qemu-system-aarch64", elf(65536, b"legacy QEMU dictionary"))
    save(old / "lib/libfixture.so", elf(16384, b"dependency"))
    save_json(old / "manifest.json", {
        "elf_files": {name: entry(old / name) for name in
                      ("qemu-system-aarch64", "lib/libfixture.so")},
        "system_libraries": [],
    })
    old_before = snapshot(old)
    fixture = work / "native-fixture"
    save(fixture / "native-efi-owner", elf(16384, b"owner"))
    save(fixture / "native-efi-guest.elf", b"synthetic guest data, never executed\n")
    save(fixture / "native-efi-swap-owner", elf(16384, b"swap owner"))
    save(fixture / "native-efi-swap-guest.elf", b"synthetic swap guest data, never executed\n")
    save_json(fixture / "native-fixture-build.json", {
        "test_fixture": "synthetic transport inputs; no native build performed",
        "artifacts": {name: entry(fixture / name) for name in
                      ("native-efi-owner", "native-efi-guest.elf",
                       "native-efi-swap-owner", "native-efi-swap-guest.elf")},
        "source_sha256": {},
    })
    size = 1048576 + 16384
    first_qemu = work / "qemu-one"
    first_payloads = work / "payloads-one"
    qemu_data = elf(size, b"candidate QEMU")
    qualifier_data = elf(size, b"standalone qualifier")
    qemu_fixture(first_qemu, qemu_data)
    save(first_payloads / "cpu_shadow_qualification", qualifier_data)
    save(first_payloads / "efi-memfd-integration", elf(size, b"EFI fixture"))
    save(first_payloads / "note.txt", b"old small payload\n")
    first, first_zip, first_update = package(
        work, "v1", "--base", old, first_qemu, fixture, ndk,
        sorted(first_payloads.iterdir()))
    assert first_update["format"] == "pixel-gpu-test-update-v1"
    assert len([item for item in first_update["files"] if item["source"] == "delta"]) == 3
    install(work, "v1-ok", first_zip, "--base", old, first / "cpu-shadow-qualification")
    assert snapshot(old) == old_before

    base = first / "cpu-shadow-qualification"
    base_before = snapshot(base)
    second_qemu = work / "qemu-two"
    changed_qemu = bytearray(qemu_data)
    changed_qemu[-100:-96] = b"new!"
    qemu_fixture(second_qemu, changed_qemu)
    second_payloads = work / "payloads-two"
    changed_qualifier = bytearray(qualifier_data)
    changed_qualifier[-200:-196] = b"v002"
    save(second_payloads / "cpu_shadow_qualification", changed_qualifier)
    save(second_payloads / "efi-memfd-integration",
         (first_payloads / "efi-memfd-integration").read_bytes())
    save(second_payloads / "note.txt", b"new small payload\n")
    second, second_zip, second_update = package(
        work, "v2", "--base-package", base, second_qemu, fixture, ndk,
        sorted(second_payloads.iterdir()))
    assert second_update["format"] == "pixel-gpu-test-update-v2"
    files = {item["name"]: item for item in second_update["files"]}
    for name in ("qemu-system-aarch64", "cpu_shadow_qualification"):
        assert files[name]["source"] == "delta"
        assert files[name]["base_file"] == {"name": name, **entry(base / name)}
    assert files["efi-memfd-integration"]["source"] == "base"
    assert files["native-efi-owner"]["source"] == "base"
    assert files["native-efi-swap-owner"]["source"] == "base"
    assert files["native-efi-swap-guest.elf"]["source"] == "base"
    assert files["native-efi-swap-guest.elf"]["mode"] == 0o644
    assert files["note.txt"]["source"] == "payload"
    assert not (second_zip / "delta/efi-memfd-integration.zst").exists()
    install(work, "v2-ok", second_zip, "--base-package", base,
            second / "cpu-shadow-qualification")
    assert snapshot(base) == base_before

    failures = []
    for label in ("base-content", "base-manifest", "base-mode", "base-extra"):
        broken = work / label
        shutil.copytree(base, broken)
        if label == "base-content":
            path = broken / "efi-memfd-integration"
            with path.open("r+b") as stream:
                stream.seek(-1, 2)
                stream.write(b"!")
        elif label == "base-manifest":
            with (broken / "package.json").open("a") as stream:
                stream.write(" ")
        elif label == "base-mode":
            (broken / "efi-memfd-integration").chmod(0o644)
        else:
            save(broken / "unexpected.txt", b"extra")
        damaged_before = snapshot(broken)
        install(work, label, second_zip, "--base-package", broken)
        assert snapshot(broken) == damaged_before
        failures.append(label)

    for label in ("payload-tamper", "patch-tamper", "wrong-dictionary",
                  "dictionary-hash", "unsafe-path", "decoded-hash"):
        broken = work / label
        shutil.copytree(second_zip, broken)
        update = json.loads((broken / "update.json").read_text())
        changed = {item["name"]: item for item in update["files"]}
        if label == "payload-tamper":
            save(broken / "payload/note.txt", b"bad payload")
        elif label == "patch-tamper":
            save(broken / files["qemu-system-aarch64"]["patch"]["name"], b"bad patch")
        elif label == "wrong-dictionary":
            changed["qemu-system-aarch64"]["base_file"]["name"] = "efi-memfd-integration"
        elif label == "dictionary-hash":
            changed["qemu-system-aarch64"]["base_file"]["sha256"] = "0" * 64
        elif label == "unsafe-path":
            changed["note.txt"]["name"] = "../escape"
        else:
            changed["qemu-system-aarch64"]["sha256"] = "0" * 64
        save_json(broken / "update.json", update)
        install(work, label, broken, "--base-package", base)
        failures.append(label)
    install(work, "v1-wrong-option", first_zip, "--base-package", base)
    install(work, "v2-wrong-option", second_zip, "--base", old)
    failures.extend(["v1-wrong-option", "v2-wrong-option"])
    nested = subprocess.run([
        sys.executable, str(second_zip / "install_device_update.py"),
        "--base-package", str(base), "--out-parent", str(base),
        "--manifest-sha", sha(second_zip / "update.json"),
        "--zstd", shutil.which("zstd"),
    ], capture_output=True, text=True, env=ENV)
    assert nested.returncode != 0 and "outside the read-only base" in nested.stderr
    nested = subprocess.run([
        sys.executable, str(ROOT / "package_device_tests.py"),
        "--qemu", str(second_qemu), "--fixture", str(fixture),
        "--ndk", str(ndk), "--base-package", str(base),
        "--out", str(base / "must-not-create"),
    ], capture_output=True, text=True, env=ENV)
    assert nested.returncode != 0 and "outside the read-only base" in nested.stderr
    failures.extend(["installer-output-inside-base", "packager-output-inside-base"])
    assert snapshot(old) == old_before and snapshot(base) == base_before
    assert not (work / "escape").exists()

    report = {
        "status": "HOST_V1_V2_UPDATE_ROUNDTRIP_PASS",
        "scope": "Synthetic non-runnable ELF data; real readelf and zstd; no native build or execution.",
        "packager_sha256": sha(ROOT / "package_device_tests.py"),
        "installer_sha256": sha(ROOT / "install_device_update.py"),
        "test_sha256": sha(Path(__file__)),
        "v1_files_roundtripped": len(first_update["files"]),
        "v2_files_roundtripped": len(second_update["files"]),
        "v2_delta_files": [item["name"] for item in second_update["files"] if item["source"] == "delta"],
        "v2_reused_files": [item["name"] for item in second_update["files"] if item["source"] == "base"],
        "v2_patch_bytes": sum(item["patch"]["bytes"] for item in second_update["files"] if item["source"] == "delta"),
        "negative_cases_passed": failures,
        "base_packages_preserved": True, "exact_hashes_and_modes": True,
        "failed_install_cleaned_only_own_directory": True,
        "gpu_tested": False, "android_device_executed": False,
    }
    save_json(work / "rehearsal.json", report)
    print(json.dumps({"report": str(work / "rehearsal.json"), **report}, indent=2))


if __name__ == "__main__":
    main()
