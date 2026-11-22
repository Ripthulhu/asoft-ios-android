#!/usr/bin/env python3
"""Reconstruct the real small ZIP locally and check refusal/cleanup boundaries."""
import argparse
import json
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import zipfile

from prep_tools_common import entry, load_json, matches, relpath, sha, write_json


def tree(root):
    return {path.relative_to(root).as_posix(): {**entry(path, True), "mtime_ns": path.stat().st_mtime_ns}
            for path in sorted(root.rglob("*")) if path.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("package", "apk", "ndk", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    package, apk, ndk, out = (getattr(args, name).resolve() for name in ("package", "apk", "ndk", "out"))
    if out.exists():
        parser.error("--out must be new")
    receipt = load_json(package / "package-build.json")
    archive = package / "prep-tooling-stager.zip"
    if not matches(archive, receipt["archive"]):
        parser.error("small ZIP does not match its package receipt")
    before = {"apk": {**entry(apk, True), "mtime_ns": apk.stat().st_mtime_ns}, "package": tree(package)}
    out.mkdir(parents=True)
    stager = out / "stager"
    stager.mkdir()
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError("duplicate small-ZIP path")
        for item in z.infolist():
            name = relpath(item.filename)
            if item.is_dir() or stat.S_IFMT(item.external_attr >> 16) != stat.S_IFREG:
                raise ValueError("small ZIP must contain regular files only")
            target = stager / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(z.read(item))
            target.chmod(0o644)
    plan_path = stager / "tooling-plan.json"
    plan = load_json(plan_path)
    if not matches(plan_path, receipt["plan"]):
        raise ValueError("plan differs from receipt after ZIP extraction")
    expected_stager = {"extract_prep_tools.py", "prep_tools_common.py", "prep_tools_release.json", "tooling-plan.json"}
    expected_stager |= {row["origin"]["path"] for row in plan["files"].values() if row["origin"]["kind"] == "payload"}
    if set(tree(stager)) != expected_stager:
        raise ValueError("small ZIP inventory differs from the exact plan")
    def run(source, target, expected_sha):
        return subprocess.run([sys.executable, "-B", str(source / "extract_prep_tools.py"),
                               "--apk", str(apk), "--plan", str(source / "tooling-plan.json"),
                               "--plan-sha", expected_sha, "--out", str(target)],
                              capture_output=True, text=True, timeout=60)
    sentinel = out / "preserved-sibling"
    sentinel.write_bytes(b"preserved standalone prep verification sibling\n")
    sentinel.chmod(0o640)
    sentinel_before = entry(sentinel, True)
    bundle = out / "bundle"
    good = run(stager, bundle, receipt["plan"]["sha256"])
    (out / "extract.stdout").write_text(good.stdout)
    (out / "extract.stderr").write_text(good.stderr)
    if good.returncode != 0:
        raise RuntimeError(good.stderr)
    result = json.loads(good.stdout)
    manifest = load_json(bundle / "tooling-manifest.json")
    if set(tree(bundle)) != set(plan["files"]) | {"tooling-manifest.json"}:
        raise ValueError("installed bundle inventory differs")
    for name, row in plan["files"].items():
        expected = {key: row[key] for key in ("bytes", "sha256", "mode")}
        if entry(bundle / name, True) != expected or manifest["files"][name] != expected:
            raise ValueError("installed bytes/mode differ: " + name)
    # Independently compare the minimal Python ELF parser against NDK readelf.
    readelf = ndk / "toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf"
    for name, info in manifest["dependencies"]["elf"].items():
        text = subprocess.check_output([str(readelf), "--wide", "-h", "-l", "-d", str(bundle / name)], text=True)
        needed = re.findall(r"\(NEEDED\).*\[(.*?)\]", text)
        loads = [line.split() for line in text.splitlines() if re.match(r"\s*LOAD\s", line)]
        if ("AArch64" not in text or needed != info["needed"] or not loads
                or any(int(row[-1], 16) < 16384 or int(row[1], 16) % 16384 != int(row[2], 16) % 16384 for row in loads)):
            raise ValueError("independent readelf check failed: " + name)
    failures = []
    for case in ("payload_hash", "payload_symlink", "unapproved_member", "mismatched_jni_record"):
        bad = out / ("bad-" + case)
        shutil.copytree(stager, bad)
        changed = load_json(bad / "tooling-plan.json")
        if case == "payload_hash":
            with (bad / "payload/java/classes.dex").open("ab") as stream:
                stream.write(b"tampered")
        elif case == "payload_symlink":
            target = bad / "payload/java/classes.dex"
            target.unlink()
            target.symlink_to(stager / "payload/java/classes.dex")
        elif case == "unapproved_member":
            changed["files"]["tools/qemu-img"]["origin"]["member"] = "lib/arm64-v8a/libqemu.so"
        else:
            target = bad / "payload/lib/unpack-build.json"
            record = load_json(target)
            record["binary"]["sha256"] = "0" * 64
            target.write_text(json.dumps(record))
            changed["files"]["lib/unpack-build.json"].update(entry(target))
        (bad / "tooling-plan.json").write_text(json.dumps(changed))
        target = out / ("refused-" + case)
        failed = run(bad, target, sha(bad / "tooling-plan.json"))
        if failed.returncode == 0 or target.exists() or list(out.glob(".prep-tools-*")):
            raise ValueError("negative case published output or leaked temporary state: " + case)
        failures.append({"case": case, "exit": failed.returncode,
                         "error": failed.stderr.splitlines()[-1], "no_output": True, "no_temp_leak": True})
        shutil.rmtree(bad)
    after = {"apk": {**entry(apk, True), "mtime_ns": apk.stat().st_mtime_ns}, "package": tree(package)}
    if before != after or entry(sentinel, True) != sentinel_before:
        raise ValueError("a baseline input or neighboring file was modified")
    report = {
        "schema": 1, "status": "HOST_ACTUAL_PREPARATION_TOOLS_RECONSTRUCTION_PASS",
        "package": receipt["archive"], "plan": receipt["plan"],
        "tooling_manifest": entry(bundle / "tooling-manifest.json"),
        "files": len(manifest["files"]), "installed_bytes": result["bytes"],
        "all_bytes_modes_inventory_match": True, "independent_readelf_objects": len(manifest["dependencies"]["elf"]),
        "baseline_bytes_modes_mtimes_unchanged": True, "sibling_preserved": True,
        "negative_cases": failures, "native_execution": False, "phone_execution": False,
        "apple_inputs": False, "apk_installed": False,
    }
    write_json(out / "host-reconstruction.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
