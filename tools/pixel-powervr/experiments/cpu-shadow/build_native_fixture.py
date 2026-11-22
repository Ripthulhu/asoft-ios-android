#!/usr/bin/env python3
"""Build the authored native-EL0/EFI guest and its ordinary-memfd supervisor."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parent


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(args, out, name):
    with (out / (name + ".log")).open("w") as log:
        subprocess.run([str(arg) for arg in args], stdout=log,
                       stderr=subprocess.STDOUT, check=True, timeout=120)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ndk", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    tools = args.ndk.resolve() / "toolchains/llvm/prebuilt/linux-x86_64/bin"
    guest = out / "native-efi-guest.elf"
    owner = out / "native-efi-owner"
    guest_command = [
        tools / "clang", "--target=aarch64-none-elf", "-nostdlib", "-fuse-ld=lld",
        "-Wl,--build-id=none", "-Wl,-T," + str(ROOT / "native_efi_guest.ld"),
        ROOT / "native_efi_guest.S", "-o", guest,
    ]
    owner_command = [
        tools / "aarch64-linux-android29-clang", "-std=c11", "-O2",
        "-Wall", "-Wextra", "-Werror", "-fPIE", "-pie",
        "-Wl,-z,max-page-size=16384", "-Wl,--build-id=sha1",
        ROOT / "native_efi_owner.c", "-o", owner,
    ]
    run(guest_command, out, "compile-guest")
    run(owner_command, out, "compile-owner")
    run([tools / "llvm-objdump", "-d", "--section=.payload", guest], out, "native-payload")
    run([tools / "llvm-readelf", "-h", "-l", "-d", "--wide", owner], out, "owner-elf")
    elf = (out / "owner-elf.log").read_text()
    loads = [line for line in elf.splitlines() if re.match(r"\s*LOAD\s", line)]
    if not loads or any(int(line.split()[-1], 16) < 16384 for line in loads):
        raise RuntimeError("Android supervisor LOAD alignment is below 16 KiB")
    if "AArch64" not in elf:
        raise RuntimeError("Android supervisor is not AArch64")
    symbols = subprocess.check_output([str(tools / "llvm-nm"), str(guest)], text=True)
    (out / "guest-symbols.txt").write_text(symbols)
    if not re.search(r"^000000004008407c T native_efi_tpidrro$", symbols, re.M):
        raise RuntimeError("the native TPIDRRO witness is not at the expected guest PC")
    manifest = {
        "status": "BUILT_NOT_EXECUTED",
        "android_apk": False,
        "requires_new_qemu_device_backend": True,
        "qemu_test_switch": "ASOFT_VIRT_REIMS_TEST=1",
        "cpu_ram": "ordinary size-sealed writable memfd",
        "guest_virtual_frame": "0x100004000",
        "guest_physical_frame": "0x41000000",
        "native_witness_pc": "0x10000007c",
        "phases": 2,
        "pixels_per_phase": 4096,
        "generic_tpidrro_trap_only_for_authored_guest": True,
        "ios_tpidrro_swap_changed": False,
        "producer_cpu_atomics": False,
        "source_sha256": {name: sha(ROOT / name) for name in (
            "native_efi_protocol.h", "native_efi_guest.S", "native_efi_guest.ld",
            "native_efi_owner.c", "build_native_fixture.py")},
        "commands": [[str(arg) for arg in command] for command in (
            guest_command, owner_command)],
        "artifacts": {path.name: {"bytes": path.stat().st_size, "sha256": sha(path)}
                      for path in (guest, owner)},
        "gpu_path_complete": False,
    }
    (out / "native-fixture-build.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest["artifacts"]))


if __name__ == "__main__":
    main()
