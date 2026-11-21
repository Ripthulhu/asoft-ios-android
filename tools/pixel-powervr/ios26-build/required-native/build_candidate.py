#!/usr/bin/env python3
"""Compile the changed TU and relink against frozen, unchanged baseline objects."""
from pathlib import Path
import hashlib
import json
import re
import shlex
import subprocess

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "qemu-native-required"
BASE = ROOT.parent / "qemu26-build-reconstruction"
BUILD = BASE / "qemu-out"
OLD_SOURCE = ROOT.parent / "qemu-pixel-android-build"
TOOLS = ROOT.parent / "tooling/android-ndk-r29/toolchains/llvm/prebuilt/linux-x86_64/bin"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(args, name):
    log = ROOT / (name + ".log")
    with log.open("w") as output:
        result = subprocess.run(args, cwd=BUILD, stdout=output, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f"{name} failed ({result.returncode}); see {log}")
    return {"command": args, "cwd": str(BUILD), "exit_code": result.returncode,
            "log": str(log), "log_sha256": sha(log)}


def main():
    baseline = json.loads((BASE / "provenance/qemu-build.json").read_text())
    if sha(BUILD / "qemu-system-aarch64") != baseline["unstripped_binary"]["sha256"]:
        raise RuntimeError("Baseline linked binary changed")
    commands = json.loads((BUILD / "compile_commands.json").read_text())
    original = next(c for c in commands if c["file"].endswith("/native-el0.c"))
    args = shlex.split(original["command"])
    args = [a.replace("../../qemu-pixel-android-build", str(SOURCE))
            .replace(str(OLD_SOURCE), str(SOURCE)) for a in args]
    obj = ROOT / "native-el0-required.o"
    for option, value in (("-o", obj), ("-MQ", obj), ("-MF", ROOT / "native-el0-required.o.d")):
        args[args.index(option) + 1] = str(value)
    record = {"base_commit": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=SOURCE, text=True).strip(),
        "scope": "Changed TU compiled and full executable relinked against the frozen baseline objects; no target execution",
        "source_sha256": sha(SOURCE / "target/arm/tcg/native-el0.c"),
        "baseline_binary_sha256": baseline["unstripped_binary"]["sha256"]}
    record["compile"] = run(args, "compile")
    record["object_sha256"] = sha(obj)
    link_commands = json.loads(subprocess.check_output(
        [str(BASE / "host-tools/bin/ninja"), "-t", "compdb", "-x", "c_LINKER_RSP"],
        cwd=BUILD, text=True))
    link = next(c for c in link_commands if c["output"] == "qemu-system-aarch64")
    args = shlex.split(link["command"])
    old_object = original["output"]
    if args.count(old_object) != 1:
        raise RuntimeError("Expected exactly one baseline native-el0 object in link")
    args[args.index(old_object)] = str(obj)
    unstripped = ROOT / "qemu-system-aarch64.unstripped"
    args[args.index("-o") + 1] = str(unstripped)
    record["link"] = run(args, "link")
    binary = ROOT / "qemu-system-aarch64"
    subprocess.run([str(TOOLS / "llvm-strip"), "--strip-unneeded", "-o", str(binary), str(unstripped)], check=True)
    elf = subprocess.check_output([str(TOOLS / "llvm-readelf"), "-h", "-l", "-d", "--wide", str(binary)], text=True)
    (ROOT / "elf.txt").write_text(elf)
    loads = [line for line in elf.splitlines() if re.match(r"\s*LOAD\s", line)]
    if not loads or any(int(line.split()[-1], 16) < 16384 for line in loads):
        raise RuntimeError("Candidate lost 16 KiB LOAD alignment")
    needed = re.findall(r"\(NEEDED\).*\[(.*?)\]", elf)
    if needed != baseline["elf_needed"]:
        raise RuntimeError("Candidate dependency closure differs from baseline")
    record["binary"] = {"bytes": binary.stat().st_size, "sha256": sha(binary)}
    record["unstripped_sha256"] = sha(unstripped)
    record["elf_needed"] = needed
    record["load_segments"] = loads
    record["baseline_preserved"] = sha(BUILD / "qemu-system-aarch64") == baseline["unstripped_binary"]["sha256"]
    if not record["baseline_preserved"]:
        raise RuntimeError("Baseline binary was unexpectedly changed")
    (ROOT / "build.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"binary": record["binary"], "baseline_preserved": record["baseline_preserved"]}, indent=2))


if __name__ == "__main__":
    main()
