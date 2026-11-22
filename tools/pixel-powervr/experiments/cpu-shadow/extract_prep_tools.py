#!/usr/bin/env python3
"""Extract a pinned, whitelisted standalone tool bundle from an existing APK.

This reads files only from the exact released APK and hash-pinned local payload.
It does not download, install an APK, execute native code, or alter the baseline.
"""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import stat
import tempfile
import zipfile

from prep_tools_common import (APK, ENTRYPOINTS, PAYLOAD_NAMES, dependency_closure,
                               entry, load_json, matches, record_valid, regular_under,
                               relpath, sha, write_json)


ROOT = Path(__file__).resolve().parent
RELEASE_SHA = "1ac38457ea9d274926ef4098e39659de559e593a3c7134b695e23a6316f6db02"


def release_record():
    path = regular_under(ROOT, "prep_tools_release.json")
    if sha(path) != RELEASE_SHA:
        raise ValueError("release whitelist differs from the reviewed pinned inventory")
    record = load_json(path)
    if record["schema"] != 1 or record["apk"] != APK:
        raise ValueError("incorrect release whitelist")
    return record


def validate_plan(plan, release):
    if (type(plan.get("schema")) is not int or plan["schema"] != 1
            or plan.get("kind") != "standalone_ios26_preparation_plan"
            or plan.get("apk") != APK or plan.get("release_manifest_sha256") != RELEASE_SHA
            or plan.get("entrypoints") != ENTRYPOINTS or plan.get("requires_qualified_qemu") is not True):
        raise ValueError("unrecognized or unpinned extraction plan")
    files = plan.get("files")
    if not isinstance(files, dict) or set(files) != set(release["files"]) | PAYLOAD_NAMES:
        raise ValueError("tool inventory differs from the exact whitelist")
    for name, record in files.items():
        relpath(name)
        record_valid(record)
        if set(record) != {"bytes", "sha256", "mode", "origin"}:
            raise ValueError("unexpected file record fields")
        if name in release["files"]:
            if record != release["files"][name]:
                raise ValueError("APK member differs from the pinned whitelist: " + name)
        elif record["origin"] != {"kind": "payload", "path": "payload/" + name}:
            raise ValueError("payload input mapping is not exact: " + name)
        if name == "lib/libunpack.so" and record["mode"] != 0o755:
            raise ValueError("current JNI library must be executable")
        if name == "java/classes.dex" and record["mode"] != 0o444:
            raise ValueError("DEX must be read-only (0444) before Android loads it")
        if name not in ("lib/libunpack.so", "java/classes.dex") and name in PAYLOAD_NAMES and record["mode"] != 0o644:
            raise ValueError("current source and metadata payload must have mode 0644")
    if not isinstance(plan.get("provenance"), dict):
        raise ValueError("missing source provenance")
    return files


def verify_inputs(apk, plan_path, plan_sha, release):
    if plan_path.is_symlink() or not stat.S_ISREG(plan_path.lstat().st_mode):
        raise ValueError("plan is not a regular file")
    if sha(plan_path) != plan_sha:
        raise ValueError("plan SHA256 mismatch")
    plan = load_json(plan_path)
    files = validate_plan(plan, release)
    if not matches(apk, APK):
        raise ValueError("whole APK byte count or SHA256 mismatch")
    for name in sorted(PAYLOAD_NAMES):
        path = regular_under(plan_path.parent, files[name]["origin"]["path"])
        if not matches(path, files[name]):
            raise ValueError("payload identity mismatch: " + name)
    return plan


def copy_verified(source, target, record):
    digest, total = hashlib.sha256(), 0
    with target.open("xb") as output:
        os.chmod(target, 0o600)
        for chunk in iter(lambda: source.read(1 << 20), b""):
            total += len(chunk)
            if total > record["bytes"]:
                raise ValueError("input exceeds its pinned length")
            output.write(chunk)
            digest.update(chunk)
        output.flush()
        os.fsync(output.fileno())
    if total != record["bytes"] or digest.hexdigest() != record["sha256"]:
        raise ValueError("input byte count or SHA256 changed while copying")


def verify_build_records(root):
    native = load_json(root / "lib/unpack-build.json")
    java = load_json(root / "java/build.json")
    if (native.get("kind") != "current_unpack_jni" or java.get("kind") != "standalone_preparation_dex"
            or native.get("source_rechecked") is not True or java.get("source_rechecked") is not True
            or native.get("warnings") != 0 or java.get("warnings") != 0
            or native.get("apk_built") is not False or java.get("apk_built") is not False):
        raise ValueError("JNI/DEX inputs lack successful source-bound build records")
    if (not matches(root / "lib/libunpack.so", native["binary"])
            or not matches(root / "lib/libunpack.so", java["native_library"])
            or not matches(root / "java/classes.dex", java["binary"])):
        raise ValueError("JNI or DEX differs from its matching build record")
    expected = sorted("Java_com_asoft_ios_Unpack_" + name
                      for name in ("lzfse", "punchHole", "syncDirectory"))
    if native.get("jni_exports") != expected:
        raise ValueError("JNI record lacks the complete current Unpack surface")
    with (root / "java/classes.dex").open("rb") as stream:
        magic = stream.read(8)
    if len(magic) != 8 or magic[:4] != b"dex\n" or not magic[4:7].isdigit() or magic[7] != 0:
        raise ValueError("invalid DEX header")
    if native["source"]["commit"] != java["source"]["commit"]:
        raise ValueError("JNI and Java source commits do not match")


def extract(apk, plan_path, plan_sha, out):
    # Everything up to mkdtemp is read-only. Existing outputs are never touched.
    if out.exists() or out.is_symlink():
        raise ValueError("output already exists")
    if not out.parent.is_dir() or out.parent.is_symlink():
        raise ValueError("output parent must already exist as a real directory")
    release = release_record()
    plan = verify_inputs(apk, plan_path, plan_sha, release)
    files = plan["files"]
    with zipfile.ZipFile(apk) as archive:
        members = archive.infolist()
        if len(members) != len({item.filename for item in members}):
            raise ValueError("APK contains duplicate ZIP members")
        lookup = {item.filename: item for item in members}
        for record in release["files"].values():
            item = lookup.get(record["origin"]["member"])
            if item is None or item.file_size != record["bytes"] or item.is_dir():
                raise ValueError("APK lacks the exact whitelisted member")
            mode = item.external_attr >> 16
            if stat.S_IFMT(mode) not in (0, stat.S_IFREG):
                raise ValueError("APK member is not a regular file")
        temporary = Path(tempfile.mkdtemp(prefix=".prep-tools-", dir=out.parent))
        try:
            for name, record in sorted(files.items()):
                target = temporary / name
                target.parent.mkdir(parents=True, exist_ok=True)
                origin = record["origin"]
                if origin["kind"] == "apk":
                    with archive.open(origin["member"], "r") as stream:
                        copy_verified(stream, target, record)
                else:
                    with regular_under(plan_path.parent, origin["path"]).open("rb") as stream:
                        copy_verified(stream, target, record)
            dependencies = dependency_closure(temporary)
            if any(dependencies["elf"][name] != info for name, info in release["elf"].items()):
                raise ValueError("released ELF metadata differs from the inspected inventory")
            verify_build_records(temporary)
            # Recheck every source before making any staged payload executable.
            if verify_inputs(apk, plan_path, plan_sha, release) != plan:
                raise ValueError("input plan changed during extraction")
            records = {}
            for name, record in sorted(files.items()):
                path = temporary / name
                if not matches(path, record):
                    raise ValueError("staged output failed its final hash check")
                path.chmod(record["mode"])
                records[name] = entry(path, True)
            manifest = {
                "schema": 1, "kind": "standalone_ios26_preparation_tools",
                "status": "VERIFIED_NOT_EXECUTED", "files": records,
                "entrypoints": ENTRYPOINTS, "requires_qualified_qemu": True,
                "dependencies": dependencies,
                "provenance": {**plan["provenance"], "apk": APK,
                               "plan_sha256": plan_sha, "release_manifest_sha256": RELEASE_SHA,
                               "file_origins": {name: record["origin"] for name, record in files.items()},
                               "input_files_rechecked": True, "apk_installed": False},
            }
            write_json(temporary / "tooling-manifest.json", manifest)
            (temporary / "tooling-manifest.json").chmod(0o644)
            for directory, dirs, _ in os.walk(temporary):
                Path(directory).chmod(0o755)
            if out.exists() or out.is_symlink():
                raise ValueError("output appeared during extraction")
            temporary.rename(out)
        except BaseException:
            if temporary.exists():
                shutil.rmtree(temporary)
            raise
    return {"status": "VERIFIED_NOT_EXECUTED", "out": str(out),
            "tooling_manifest": entry(out / "tooling-manifest.json"),
            "files": len(files), "bytes": sum(row["bytes"] for row in files.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("apk", "plan", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--plan-sha", required=True)
    args = parser.parse_args()
    # Do not resolve input leaf symlinks before regular-file checks.
    import json
    print(json.dumps(extract(args.apk.absolute(), args.plan.absolute(), args.plan_sha, args.out.absolute())))


if __name__ == "__main__":
    main()
