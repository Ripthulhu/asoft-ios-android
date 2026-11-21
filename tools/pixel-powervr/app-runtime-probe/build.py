#!/usr/bin/env python3
"""Build the permission-free app probe with an existing Android SDK, without Gradle.

The default tool paths match the official archives recorded in
provenance/sdk-downloads.json. No network requests or SDK installation occur here.
The existing v2 local test signing key is required; no new key is generated.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import xml.etree.ElementTree as ET
import zipfile


ROOT = Path(__file__).resolve().parent
PACKAGE = "com.ripthulhu.pixelpowervr.probe"
CPU_CONTROL_SHA256 = "d58320129c9a2092096a12cd4acdfb0345a8936208c54b9d64f1187d3be26ca9"
RUNTIME_SHA256 = "0291f97791c1b6f84c12a31a6213573f35d45c308ce306cca1505a06932b89f4"
EXPECTED_CERTIFICATE_SHA256 = "1be8112cbcd1eb86ff6085b63f07dd0ca68e9f4d354079b0076e9c3ea2134256"
ANDROID = "{http://schemas.android.com/apk/res/android}"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*command: str | Path) -> str:
    arguments = [str(item) for item in command]
    print("+ " + " ".join(arguments), flush=True)
    result = subprocess.run(arguments, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.stdout:
        print(result.stdout, end="", flush=True)
    result.check_returncode()
    return result.stdout


def verify_elf(path: Path) -> dict:
    data = path.read_bytes()
    if data[:6] != b"\x7fELF\x02\x01":
        raise ValueError(f"Not little-endian ELF64: {path}")
    elf_type, machine = struct.unpack_from("<HH", data, 16)
    if elf_type != 3 or machine != 183:
        raise ValueError(f"Not ARM64 PIE: {path}")
    offset = struct.unpack_from("<Q", data, 32)[0]
    size, count = struct.unpack_from("<HH", data, 54)
    load_alignments = []
    interpreter = None
    for index in range(count):
        entry = offset + index * size
        kind = struct.unpack_from("<I", data, entry)[0]
        if kind == 1:
            load_alignments.append(struct.unpack_from("<Q", data, entry + 48)[0])
        elif kind == 3:
            start = struct.unpack_from("<Q", data, entry + 8)[0]
            length = struct.unpack_from("<Q", data, entry + 32)[0]
            interpreter = data[start:start + length].rstrip(b"\0").decode("ascii")
    if not load_alignments or any(alignment < 16384 for alignment in load_alignments):
        raise ValueError(f"ELF PT_LOAD alignment is below 16 KiB: {path}")
    if interpreter != "/system/bin/linker64":
        raise ValueError(f"Unexpected ELF interpreter: {path}: {interpreter}")
    return {"machine": "AArch64", "type": "ET_DYN (PIE)", "interpreter": interpreter,
            "load_alignments": load_alignments, "sha256": sha256(path), "bytes": len(data)}


def validate_manifest() -> None:
    manifest = ET.parse(ROOT / "AndroidManifest.xml").getroot()
    if manifest.attrib.get("package") != PACKAGE:
        raise ValueError("Wrong package")
    if manifest.attrib.get(ANDROID + "versionCode") != "3" or manifest.attrib.get(ANDROID + "versionName") != "1.2-runtime":
        raise ValueError("Wrong runtime test upgrade version")
    if any(element.tag.startswith("uses-permission") for element in manifest):
        raise ValueError("Probe must request no Android permissions")
    if ANDROID + "sharedUserId" in manifest.attrib:
        raise ValueError("Probe must not have a shared UID")
    app = manifest.find("application")
    expected = {"debuggable": "false", "allowBackup": "false", "extractNativeLibs": "true"}
    for key, value in expected.items():
        if app is None or app.attrib.get(ANDROID + key) != value:
            raise ValueError(f"Incorrect manifest application attribute: {key}")
    if [element.tag for element in app] != ["activity"]:
        raise ValueError("Unexpected Android components")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-tools", type=Path, default=ROOT / "toolchain/sdk/android-16")
    parser.add_argument("--android-jar", type=Path, default=ROOT / "toolchain/sdk/android-36/android.jar")
    parser.add_argument("--signing-keystore", type=Path, default=ROOT / "build/signing/probe-test.p12")
    parser.add_argument("--runtime-probe", type=Path, required=True)
    parser.add_argument("--cpu-exec-control", type=Path, required=True)
    options = parser.parse_args()
    build_tools = options.build_tools.resolve()
    android_jar = options.android_jar.resolve()
    key = options.signing_keystore.resolve()
    if not key.is_file():
        raise FileNotFoundError("Reuse the v2 test signing key with --signing-keystore: " + str(key))
    for path in [android_jar, *(build_tools / name for name in ("aapt", "aapt2", "d8", "zipalign", "apksigner", "core-lambda-stubs.jar"))]:
        if not path.is_file():
            raise FileNotFoundError(path)
    validate_manifest()
    build = ROOT / "build"
    dist = ROOT / "dist"
    for directory in (build / "classes", build / "dex", build / "assets", dist):
        directory.mkdir(parents=True, exist_ok=True)
    for old in (build / "classes").rglob("*.class"):
        old.unlink()
    for old in (build / "dex").glob("*.dex"):
        old.unlink()
    runtime = options.runtime_probe.resolve()
    if sha256(runtime) != RUNTIME_SHA256:
        raise ValueError("The reviewed real runtime binary was not supplied")
    library = build / "native/arm64-v8a/libpixel_runtime_probe.so"
    library.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(runtime, library)
    control = options.cpu_exec_control.resolve()
    if sha256(control) != CPU_CONTROL_SHA256:
        raise ValueError("The reviewed CPU-only execution control was not supplied")
    control_library = library.parent / "libcpu_exec_control.so"
    shutil.copy2(control, control_library)
    libs = [control_library, library]
    native = {"lib/arm64-v8a/" + path.name: verify_elf(path) for path in libs}
    payload_hashes = {key: item["sha256"] for key, item in native.items()}
    (build / "assets/payload-sha256.txt").write_text(
        "".join(f"{value}  {key}\n" for key, value in sorted(payload_hashes.items())), encoding="utf-8")

    run("java", "com.sun.tools.javac.Main", "-source", "8", "-target", "8", "-Xlint:-options",
        "-bootclasspath", str(build_tools / "core-lambda-stubs.jar") + os.pathsep + str(android_jar),
        "-d", build / "classes", *sorted((ROOT / "src").rglob("*.java")))
    run(build_tools / "d8", "--release", "--min-api", "35", "--lib", android_jar,
        "--output", build / "dex", *sorted((build / "classes").rglob("*.class")))
    unsigned = build / "unsigned.apk"
    run(build_tools / "aapt2", "link", "--manifest", ROOT / "AndroidManifest.xml",
        "-I", android_jar, "-A", build / "assets", "-o", unsigned)
    with zipfile.ZipFile(unsigned, "a", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as apk:
        for dex in sorted((build / "dex").glob("*.dex")):
            apk.write(dex, dex.name)
        for library in libs:
            apk.write(library, "lib/arm64-v8a/" + library.name)
    aligned = build / "aligned.apk"
    run(build_tools / "zipalign", "-P", "16", "-f", "4", unsigned, aligned)
    apk = dist / "pixel-powervr-runtime-probe.apk"
    run(build_tools / "apksigner", "sign", "--ks", key, "--ks-key-alias", "probe", "--ks-pass", "pass:android",
        "--key-pass", "pass:android", "--v1-signing-enabled", "false", "--v2-signing-enabled", "true",
        "--v3-signing-enabled", "true", "--v4-signing-enabled", "false", "--out", apk, aligned)
    signature = run(build_tools / "apksigner", "verify", "--verbose", "--print-certs", apk)
    badging = run(build_tools / "aapt", "dump", "badging", apk)
    permissions = run(build_tools / "aapt", "dump", "permissions", apk)
    manifest_dump = run(build_tools / "aapt", "dump", "xmltree", apk, "AndroidManifest.xml")
    alignment = run(build_tools / "zipalign", "-c", "-P", "16", "4", apk)
    if "uses-permission" in permissions or f"package: {PACKAGE}" not in permissions:
        raise ValueError("Binary manifest permission verification failed")
    if ("application-debuggable" in badging or "targetSdkVersion:'35'" not in badging
            or "versionCode='3'" not in badging or "versionName='1.2-runtime'" not in badging):
        raise ValueError("Binary manifest target/debuggable verification failed")
    if "android:extractNativeLibs" not in manifest_dump:
        raise ValueError("Binary manifest extraction flag missing")
    with zipfile.ZipFile(apk) as final_zip:
        for key_name, expected_hash in payload_hashes.items():
            if hashlib.sha256(final_zip.read(key_name)).hexdigest() != expected_hash:
                raise ValueError("Packaged payload checksum mismatch: " + key_name)
        if any(final_zip.getinfo(key_name).compress_type != zipfile.ZIP_DEFLATED for key_name in native):
            raise ValueError("Native payload must be compressed for install-time extraction")
        if len(final_zip.namelist()) != len(set(final_zip.namelist())):
            raise ValueError("Duplicate APK entries")
    verification = "\n".join([signature, badging, permissions, manifest_dump, alignment])
    (dist / "verification.txt").write_text(verification, encoding="utf-8")
    cert_line = next(line for line in signature.splitlines() if "certificate SHA-256 digest:" in line)
    if cert_line.split(": ", 1)[1] != EXPECTED_CERTIFICATE_SHA256:
        raise ValueError("APK must use the same local test signer as the installed v2 test app")
    metadata = {
        "created_utc": datetime.now(timezone.utc).isoformat(), "package": PACKAGE,
        "version_code": 3, "version_name": "1.2-runtime", "runtime_modes": ["--producer", "--tile"],
        "previous_test_apk_sha256": "16c4343fcd733c4df2a9ee024001554edebf140749866e60dab650d9ae5025f4",
        "apk": apk.name, "bytes": apk.stat().st_size, "sha256": sha256(apk),
        "certificate_sha256": cert_line.split(": ", 1)[1], "min_sdk": 35, "target_sdk": 35,
        "compile_sdk": 36, "debuggable": False, "permissions": [], "native": native,
        "payload_sha256": payload_hashes, "native_commands": [
            ["libcpu_exec_control.so", "--cpu-exec-anon"],
            ["libcpu_exec_control.so", "--cpu-exec-memfd"],
            ["libpixel_runtime_probe.so", "--producer", "--cache-root", "<app files>/runtime-caches"],
            ["libpixel_runtime_probe.so", "--tile", "--cache-root", "<app files>/runtime-caches"]],
        "timeout_seconds": [10, 10, 60, 60],
        "hardware_execution": "Not performed by this build; ordinary-app runtime qualification pending. Native executable alias probe is intentionally not included after its root failure.",
        "source_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in
                          [ROOT / "AndroidManifest.xml", ROOT / "build.py", *sorted((ROOT / "src").rglob("*.java"))]},
        "tools": {"android_jar": sha256(android_jar), "build_tools_source_properties":
                  (build_tools / "source.properties").read_text(encoding="utf-8")},
    }
    (dist / "build-info.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    (dist / "SHA256SUMS").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in sorted(dist.iterdir())
                if path.is_file() and path.name != "SHA256SUMS"), encoding="utf-8")
    print(json.dumps({key: metadata[key] for key in ("apk", "bytes", "sha256", "certificate_sha256")}, indent=2))


if __name__ == "__main__":
    main()
