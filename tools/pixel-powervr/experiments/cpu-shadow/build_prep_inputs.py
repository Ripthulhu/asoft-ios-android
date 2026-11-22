#!/usr/bin/env python3
"""Build current standalone JNI + DEX inputs; no APK and no target execution."""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess

from prep_tools_common import elf_info, entry, git, source_snapshot, write_json


JAVA_NAMES = ["Unpack", "IpswFetch", "Io", "CdnEdges"]
JAVA_BASE = "app/src/main/java/com/asoft/ios/"
NATIVE_BASE = "app/src/main/cpp/"
NATIVE_C = ["unpack.c", "lzfse/lzfse_decode.c", "lzfse/lzfse_decode_base.c",
            "lzfse/lzfse_fse.c", "lzfse/lzvn_decode_base.c"]
TOOL_HASHES = {
    "r8": "58366f77067207c39a17d469de7b05701d2877212a9c55201bcb0af43e59e903",
    "android_jar": "4566663c3876e022b4fa4ced8c8697c4ab1688267f090114fd92d027b32e619b",
    "core_jar": "4279b723c69c851cea46a36d75ffd294649ec041176c0b786bafe62d1d1af1a6",
}


def command(arguments, log):
    arguments = [str(arg) for arg in arguments]
    with log.open("x") as stream:
        subprocess.run(arguments, stdout=stream, stderr=subprocess.STDOUT,
                       check=True, timeout=240, env={**os.environ, "LC_ALL": "C"})
    text = log.read_text()
    if re.search(r"\bwarning\b", text, re.IGNORECASE):
        raise RuntimeError("build emitted a warning; inspect " + str(log))
    return arguments


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "adapter", "ndk", "r8", "android-jar", "core-jar", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    source, adapter, ndk, r8, android_jar, core_jar, out = (
        getattr(args, name).resolve() for name in ("source", "adapter", "ndk", "r8", "android_jar", "core_jar", "out"))
    if out.is_relative_to(source) or out.exists():
        parser.error("--out must be new and outside the source checkout")
    adapter_root = Path(git(adapter.parent, "rev-parse", "--show-toplevel").decode().strip())
    adapter_name = adapter.relative_to(adapter_root).as_posix()
    if adapter.name != "PrepareInputs.java":
        parser.error("--adapter must be the committed PrepareInputs.java")
    native_names = [NATIVE_BASE + "unpack.c", NATIVE_BASE + "CMakeLists.txt"]
    native_names += [path.relative_to(source).as_posix()
                     for path in (source / NATIVE_BASE / "lzfse").iterdir() if path.is_file()]
    java_names = [JAVA_BASE + name + ".java" for name in JAVA_NAMES]
    native = source_snapshot(source, native_names)
    java = source_snapshot(source, java_names)
    adapter_record = source_snapshot(adapter_root, [adapter_name])
    inputs = {"r8": entry(r8), "android_jar": entry(android_jar), "core_jar": entry(core_jar)}
    if any(inputs[name]["sha256"] != expected for name, expected in TOOL_HASHES.items()):
        parser.error("R8 8.7.18 or Android API-35 jars differ from the pinned Google tools")
    tool_dir = ndk / "toolchains/llvm/prebuilt/linux-x86_64/bin"
    cc, nm = tool_dir / "aarch64-linux-android29-clang", tool_dir / "llvm-nm"
    build_files = {name: entry(Path(__file__).resolve().parent / name)
                   for name in ("build_prep_inputs.py", "prep_tools_common.py")}
    compiler = subprocess.check_output([str(cc), "--version"], text=True).strip()
    javac = subprocess.check_output(["java", "com.sun.tools.javac.Main", "-version"], text=True).strip()
    java_home = Path(shutil.which("java")).resolve().parent.parent
    d8 = subprocess.check_output(["java", "-cp", str(r8), "com.android.tools.r8.D8", "--version"], text=True).strip()
    out.mkdir(parents=True, exist_ok=False)
    (out / "lib").mkdir()
    (out / "java").mkdir()
    (out / "classes").mkdir()
    library = out / "lib/libunpack.so"
    c_command = command(
        [cc, "-std=c11", "-O3", "-fPIC", "-shared", "-Wall", "-Werror",
         "-Wno-unused-variable", "-Wno-unused-function", "-Wl,--no-undefined",
         "-Wl,--fatal-warnings", "-Wl,--build-id=sha1", "-Wl,-z,max-page-size=16384",
         "-Wl,-soname,libunpack.so", *[source / NATIVE_BASE / name for name in NATIVE_C],
         "-o", library], out / "native-build.log")
    native_elf = elf_info(library.read_bytes())
    exports = subprocess.check_output([str(nm), "--dynamic", "--defined-only", str(library)], text=True)
    wanted = {"Java_com_asoft_ios_Unpack_" + name for name in ("lzfse", "punchHole", "syncDirectory")}
    actual = {line.split()[-1] for line in exports.splitlines() if "Java_" in line}
    if actual != wanted or native_elf["soname"] != "libunpack.so":
        raise RuntimeError("native library does not implement the exact current Java JNI surface")
    java_command = command(
        ["java", "com.sun.tools.javac.Main", "-source", "8", "-target", "8",
         "-bootclasspath", str(core_jar) + os.pathsep + str(android_jar),
         "-g:none", "-encoding", "UTF-8", "-Xlint:all,-serial,-options", "-Werror", "-d", out / "classes",
         *[source / name for name in java_names], adapter], out / "javac.log")
    classes = sorted((out / "classes").rglob("*.class"))
    if not classes:
        raise RuntimeError("javac produced no classes")
    dex_command = command(
        ["java", "-cp", r8, "com.android.tools.r8.D8", "--release", "--min-api", "29",
         "--lib", android_jar, "--output", out / "java", *classes], out / "d8.log")
    dex = out / "java/classes.dex"
    if sorted(path.name for path in (out / "java").iterdir()) != ["classes.dex"]:
        raise RuntimeError("expected one standalone DEX file")
    if dex.read_bytes()[:4] != b"dex\n":
        raise RuntimeError("D8 did not produce a DEX file")
    if (source_snapshot(source, native_names) != native
            or source_snapshot(source, java_names) != java
            or source_snapshot(adapter_root, [adapter_name]) != adapter_record
            or entry(r8) != inputs["r8"] or entry(android_jar) != inputs["android_jar"]
            or entry(core_jar) != inputs["core_jar"]
            or any(entry(Path(__file__).resolve().parent / name) != record
                   for name, record in build_files.items())):
        raise RuntimeError("committed source or pinned tool changed during the build")
    library.chmod(0o755)
    dex.chmod(0o444)
    native_manifest = {
        "schema": 1, "status": "BUILT_NOT_EXECUTED", "kind": "current_unpack_jni",
        "source": native, "source_rechecked": True, "binary": entry(library, True),
        "command": c_command, "compiler": compiler, "android_api": 29,
        "ndk_properties": entry(ndk / "source.properties"), "elf": native_elf,
        "jni_exports": sorted(wanted), "warnings": 0, "apk_built": False,
        "build_sources": build_files,
        "tool_binaries": {name: entry((tool_dir / name).resolve())
                          for name in (cc.name, "clang", "ld.lld", "llvm-nm")},
    }
    java_manifest = {
        "schema": 1, "status": "BUILT_NOT_EXECUTED", "kind": "standalone_preparation_dex",
        "source": java, "adapter": adapter_record, "source_rechecked": True,
        "binary": entry(dex, True), "native_library": entry(library, True),
        "javac_command": java_command, "d8_command": dex_command,
        "javac": javac, "d8": d8, "tools": inputs, "minimum_android_api": 29,
        "java_language_target": 8, "compiler_system_modules": entry(java_home / "lib/modules"),
        "platform_note": "Unchanged sources compile against Android's core and framework stubs, including its compiler-only lambda stubs. D8 uses Android API-35 library and min-api 29. Host Java API classes are excluded from the compilation boot classpath.",
        "lint_exclusions": {"options": "Java 21 marks source/target 8 obsolete; the explicit Android boot classpath is intentional.",
                            "serial": "Existing IpswFetch.HttpError has no serialVersionUID; source is preserved byte-for-byte."},
        "class_files": {path.relative_to(out / "classes").as_posix(): entry(path) for path in classes},
        "java_sources_copied_unchanged": True, "warnings": 0, "apk_built": False,
        "entrypoint": "com.asoft.ios.PrepareInputs", "build_sources": build_files,
    }
    write_json(out / "lib/unpack-build.json", native_manifest)
    write_json(out / "java/build.json", java_manifest)
    print({"status": "BUILT_NOT_EXECUTED", "jni": entry(library), "dex": entry(dex)})


if __name__ == "__main__":
    main()
