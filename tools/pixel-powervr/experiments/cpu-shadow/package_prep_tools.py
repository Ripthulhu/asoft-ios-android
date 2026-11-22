#!/usr/bin/env python3
"""Package a small pinned extraction plan; keep the existing qualification package untouched."""
import argparse
from pathlib import Path
import shutil
import stat
import zipfile

from extract_prep_tools import RELEASE_SHA, release_record, validate_plan
from prep_tools_common import (APK, ENTRYPOINTS, PAYLOAD_NAMES, PHONE_FILES, entry,
                               load_json, matches, regular_under, source_snapshot,
                               write_json)


ROOT = Path(__file__).resolve().parent
BOOT_SOURCE = "app/src/main/java/com/asoft/ios/"


def deterministic_zip(root, out):
    with zipfile.ZipFile(out, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            name = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "apk", "inputs-build", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    source, apk, built, out = (getattr(args, name).absolute()
                               for name in ("source", "apk", "inputs_build", "out"))
    if out.exists() or out.is_symlink() or out.resolve().is_relative_to(source.resolve()):
        parser.error("--out must be new and outside the source checkout")
    release = release_record()
    if not matches(apk, APK):
        parser.error("--apk differs from the exact pinned released APK")
    source_names = ["setup/asoft-setup.json"] + ["setup/phone/" + name for name in PHONE_FILES]
    provenance_names = [BOOT_SOURCE + name + ".java" for name in
                        ("PhoneSetup26", "Helper", "Unpack", "IpswFetch", "CdnEdges", "Io")]
    source_record = source_snapshot(source, source_names + provenance_names)
    inputs = {name: entry(regular_under(built, name)) for name in
              ("java/classes.dex", "java/build.json", "lib/libunpack.so", "lib/unpack-build.json")}
    native, java = load_json(built / "lib/unpack-build.json"), load_json(built / "java/build.json")
    if native["source"]["commit"] != source_record["commit"] or java["source"]["commit"] != source_record["commit"]:
        parser.error("current JNI, Java, and setup source commits must agree")
    if (not matches(built / "lib/libunpack.so", native["binary"])
            or not matches(built / "lib/libunpack.so", java["native_library"])
            or not matches(built / "java/classes.dex", java["binary"])):
        parser.error("JNI/DEX bytes do not match their build records")
    # The pinned APK is used to prove the plan's full exact source identity here,
    # and again on the phone before any whitelisted member is extracted.
    with zipfile.ZipFile(apk) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            parser.error("APK has duplicate member names")
        import hashlib
        for record in release["files"].values():
            data = archive.read(record["origin"]["member"])
            if len(data) != record["bytes"] or hashlib.sha256(data).hexdigest() != record["sha256"]:
                parser.error("APK member differs from the pinned whitelist")
    out.mkdir(parents=True, exist_ok=False)
    stager = out / "stager"
    stager.mkdir()
    files = dict(release["files"])
    for name in sorted(PAYLOAD_NAMES):
        origin = source if name in source_names else built
        path = regular_under(origin, name)
        target = stager / "payload" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        target.chmod(0o644)
        expected = source_record["files"][name] if name in source_names else inputs[name]
        if not matches(target, expected):
            raise RuntimeError("copied payload differs from its frozen source: " + name)
        mode = 0o755 if name == "lib/libunpack.so" else 0o444 if name == "java/classes.dex" else 0o644
        files[name] = {**entry(target), "mode": mode,
                       "origin": {"kind": "payload", "path": "payload/" + name}}
    sources = {}
    for name in ("extract_prep_tools.py", "prep_tools_common.py", "prep_tools_release.json"):
        path = regular_under(ROOT, name)
        shutil.copyfile(path, stager / name)
        (stager / name).chmod(0o644)
        sources[name] = entry(path)
    plan = {
        "schema": 1, "kind": "standalone_ios26_preparation_plan", "apk": APK,
        "release_manifest_sha256": RELEASE_SHA, "files": files,
        "entrypoints": ENTRYPOINTS, "requires_qualified_qemu": True,
        "provenance": {
            "current_source": source_record, "java_adapter": java["adapter"],
            "release_tag_commit": release["tag_commit"],
            "release_signature_certificate_sha256": release["release_signature_certificate_sha256"],
            "native_release_build_reproduced": False,
            "source_mix": "Current committed setup manifest, phone scripts, Java and JNI; pinned released APK qemu-img/dependencies, Linux helper and setup scripts/steps/tools.",
            "excluded_old_libunpack": release["excluded_old_libunpack"],
            "qemu_img_version": release["qemu_img_version"],
            "extractor_sources": sources,
            "native_qemu": "Supplied separately by the exact 17-case qualified CPU-shadow package.",
            "apple_inputs_included": False, "apk_built": False,
        },
    }
    validate_plan(plan, release)
    write_json(stager / "tooling-plan.json", plan)
    if (source_snapshot(source, source_names + provenance_names) != source_record
            or any(entry(built / name) != record for name, record in inputs.items())
            or not matches(apk, APK)):
        raise RuntimeError("an input changed while creating the extraction plan")
    archive_path = out / "prep-tooling-stager.zip"
    deterministic_zip(stager, archive_path)
    receipt = {
        "schema": 1, "status": "PACKAGED_NOT_EXECUTED", "files": len(files),
        "installed_bytes": sum(row["bytes"] for row in files.values()),
        "phone_apk": APK, "plan": entry(stager / "tooling-plan.json"),
        "archive": {"path": str(archive_path), **entry(archive_path)},
        "source_rechecked": True, "apk_built": False, "apple_inputs_included": False,
        "extract_command": ["python3", "extract_prep_tools.py", "--apk", "APK_PATH",
                            "--plan", "tooling-plan.json", "--plan-sha", entry(stager / "tooling-plan.json")["sha256"],
                            "--out", "NEW_TOOL_BUNDLE"],
    }
    write_json(out / "package-build.json", receipt)
    print(receipt)


if __name__ == "__main__":
    main()
