#!/usr/bin/env python3
"""Prepare an isolated Android pkg-config view and QEMU's Termux setjmp port."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
NDK = WORKSPACE / "tooling/android-ndk-r29"
TOOLS = NDK / "toolchains/llvm/prebuilt/linux-x86_64/bin"
PREFIX = ROOT / "termux-root/data/data/com.termux/files/usr"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    pcdir = ROOT / "target-pkgconfig"
    pcdir.mkdir(exist_ok=True)
    records = []
    for original in sorted((PREFIX / "lib/pkgconfig").glob("*.pc")):
        destination = pcdir / original.name
        destination.write_text(original.read_text().replace(
            "/data/data/com.termux/files/usr", str(PREFIX)))
        records.append({"name": original.name, "original_sha256": sha(original),
                        "relocated_sha256": sha(destination)})
    (ROOT / "provenance/relocated-pkgconfig.json").write_text(
        json.dumps(records, indent=2) + "\n")
    wrapper = ROOT / "scripts/target-pkg-config.py"
    wrapper.write_text('''#!/usr/bin/env python3
from pathlib import Path
import os
import sys
root = Path(__file__).resolve().parents[1]
env = os.environ.copy()
env["PKG_CONFIG_LIBDIR"] = os.pathsep.join([
    str(root / "target-pkgconfig"),
    str(root / "reims-dist/lib/pkgconfig"),
])
env["PKG_CONFIG_PATH"] = ""
env.pop("PKG_CONFIG_SYSROOT_DIR", None)
os.execve("/usr/bin/pkg-config", ["pkg-config", *sys.argv[1:]], env)
''')
    wrapper.chmod(0o755)

    # These files are unmodified, hash-verified copies of the pinned Termux port.
    # The private symbol implementation is linked into this executable only.
    source = ROOT / "android-port"
    (source / "private").mkdir(parents=True, exist_ok=True)
    records = json.loads((ROOT / "provenance/termux-setjmp.json").read_text())
    for item in records:
        original = ROOT / "provenance/termux-setjmp" / item["name"]
        if sha(original) != item["sha256"]:
            raise RuntimeError(f"setjmp source hash mismatch: {original}")
        relative = item["name"].replace("private-", "private/", 1)
        shutil.copyfile(original, source / relative)
    commands = [
        [str(TOOLS / "aarch64-linux-android29-clang"), "-O2", "-fPIC",
         "-I", str(source), "-c", str(source / "setjmp.S"),
         "-o", str(source / "setjmp.o")],
        [str(TOOLS / "llvm-ar"), "rcsD", str(source / "libandroid-setjmp.a"),
         str(source / "setjmp.o")],
    ]
    with (ROOT / "logs/android-setjmp-build.log").open("w") as log:
        for command in commands:
            subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT)
    (ROOT / "provenance/android-setjmp-build.json").write_text(json.dumps({
        "commands": commands,
        "archive_sha256": sha(source / "libandroid-setjmp.a"),
        "archive_bytes": (source / "libandroid-setjmp.a").stat().st_size,
        "scope": "Private QEMU coroutine portability shim from the pinned Termux package; no system library or policy alteration.",
        "runtime_status": "Not executed on the phone by this build preparation.",
    }, indent=2) + "\n")
    print(f"Prepared {len(records)} setjmp sources and {len(list(pcdir.glob('*.pc')))} target pkg-config files")


if __name__ == "__main__":
    main()
