#!/usr/bin/env python3
"""Build only the configured Android system emulator; retain validation facts."""
from pathlib import Path
import datetime
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "qemu-out"
TOOLS = ROOT.parent / "tooling/android-ndk-r29/toolchains/llvm/prebuilt/linux-x86_64/bin"


def sha(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def main():
    configure = json.loads((ROOT / "provenance/qemu-configure.json").read_text())
    if configure["exit_code"] != 0:
        raise RuntimeError("QEMU configure did not succeed")
    configs = {p.name: p.read_text() for p in BUILD.glob("*config*.h")}
    required = {"CONFIG_ARM_VRESEARCH", "CONFIG_REIMS_VGPU", "CONFIG_TCG"}
    joined = "\n".join(configs.values())
    config_evidence = {}
    for name in required:
        # Meson emits some enabled booleans as a valueless #define and
        # Kconfig-derived selections as #define NAME 1. Both are genuine
        # enabled selections; an #undef or a numeric zero must not pass.
        pattern = r"^#define[ \t]+" + name + r"(?:[ \t]+1)?[ \t]*$"
        if not re.search(pattern, joined, re.M):
            raise RuntimeError(f"The generated build does not enable {name}")
        config_evidence[name] = {
            file: re.findall(pattern, content, re.M)
            for file, content in configs.items() if re.search(pattern, content, re.M)
        }
    commands = json.loads((BUILD / "compile_commands.json").read_text())
    native = [c for c in commands if c["file"].endswith("target/arm/tcg/native-el0.c")]
    if not native:
        raise RuntimeError("native-el0.c is absent from the configured compile commands")
    command = [str(ROOT / "host-tools/bin/ninja"), "-C", str(BUILD), "-j2", "qemu-system-aarch64"]
    record = {
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "command": command,
        "required_config": sorted(required),
        "config_evidence": config_evidence,
        "native_el0_compile_commands": native,
        "scope": "Cross-build only; target executable is not run on the x86-64 host or phone.",
    }
    log = ROOT / "logs/qemu-build.log"
    with log.open("w") as out:
        result = subprocess.run(command, stdout=out, stderr=subprocess.STDOUT)
    record.update({"exit_code": result.returncode,
                   "ended_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   "log_sha256": sha(log)})
    if result.returncode == 0:
        binary = BUILD / "qemu-system-aarch64"
        symbols = subprocess.check_output([str(TOOLS / "llvm-nm"), "--defined-only", str(binary)], text=True)
        record["unstripped_binary"] = {"bytes": binary.stat().st_size, "sha256": sha(binary)}
        record["native_el0_symbols"] = [line for line in symbols.splitlines() if "native_el0" in line]
        if not record["native_el0_symbols"]:
            raise RuntimeError("Linked emulator lacks native_el0 symbols")
        out = ROOT / "dist"
        out.mkdir(exist_ok=True)
        stripped = out / "qemu-system-aarch64"
        subprocess.run([str(TOOLS / "llvm-strip"), "--strip-unneeded", "-o", str(stripped), str(binary)], check=True)
        report = subprocess.check_output([str(TOOLS / "llvm-readelf"), "-h", "-l", "-d", "-n", "--wide", str(stripped)], text=True)
        (ROOT / "logs/qemu-elf.txt").write_text(report)
        load_lines = [line for line in report.splitlines() if re.match(r"\s*LOAD\s", line)]
        if not load_lines or any(int(line.split()[-1], 16) < 16384 for line in load_lines):
            raise RuntimeError("Not every QEMU LOAD segment has at least 16 KiB alignment")
        record["stripped_binary"] = {"bytes": stripped.stat().st_size, "sha256": sha(stripped)}
        record["elf_needed"] = re.findall(r"\(NEEDED\).*\[(.*?)\]", report)
        record["load_segments"] = load_lines
    (ROOT / "provenance/qemu-build.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"QEMU_BUILD_EXIT={result.returncode}; log={log}")
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
