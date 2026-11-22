#!/usr/bin/env python3
"""Build separate generic-trap and iOS-swap native-EL0/EFI fixtures."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess


ROOT = Path(__file__).resolve().parent


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(args, out, name):
    with (out / (name + ".log")).open("w") as log:
        subprocess.run([str(arg) for arg in args], stdout=log,
                       stderr=subprocess.STDOUT, check=True, timeout=120)


def build_mode(tools, out, swap):
    suffix = "-swap" if swap else ""
    defines = ["-DNEF_IOS_SWAP=1"] if swap else []
    guest = out / ("native-efi" + suffix + "-guest.elf")
    owner = out / ("native-efi" + suffix + "-owner")
    guest_command = [
        tools / "clang", "--target=aarch64-none-elf", "-nostdlib", "-fuse-ld=lld",
        "-Wl,--build-id=none", "-Wl,-T," + str(ROOT / "native_efi_guest.ld"),
        *defines, ROOT / "native_efi_guest.S", "-o", guest,
    ]
    owner_command = [
        tools / "aarch64-linux-android29-clang", "-std=c11", "-O2",
        "-Wall", "-Wextra", "-Werror", "-fPIE", "-pie",
        "-Wl,-z,max-page-size=16384", "-Wl,--build-id=sha1",
        *defines, ROOT / "native_efi_owner.c", "-o", owner,
    ]
    run(guest_command, out, "compile-guest" + suffix)
    run(owner_command, out, "compile-owner" + suffix)
    run([tools / "llvm-objdump", "-d", "--section=.payload", guest], out, "native-payload" + suffix)
    run([tools / "llvm-readelf", "-h", "-l", "-d", "--wide", owner], out, "owner-elf" + suffix)
    elf = (out / ("owner-elf" + suffix + ".log")).read_text()
    loads = [line for line in elf.splitlines() if re.match(r"\s*LOAD\s", line)]
    if not loads or any(int(line.split()[-1], 16) < 16384 for line in loads):
        raise RuntimeError("Android supervisor LOAD alignment is below 16 KiB")
    if "AArch64" not in elf:
        raise RuntimeError("Android supervisor is not AArch64")
    symbols = subprocess.check_output([str(tools / "llvm-nm"), str(guest)], text=True)
    (out / ("guest-symbols" + suffix + ".txt")).write_text(symbols)
    if not re.search(r"^000000004008407c T native_efi_tpidrro$", symbols, re.M):
        raise RuntimeError("the native TPIDRRO witness is not at the expected guest PC")
    payload_path = out / ("native-payload" + suffix + ".bin")
    # objcopy otherwise rewrites its input even when only dumping a section.
    run([tools / "llvm-objcopy", "--dump-section", ".payload=" + str(payload_path), guest, "/dev/null"],
        out, "extract-payload" + suffix)
    payload = payload_path.read_bytes()
    if len(payload) != 16384 or struct.unpack_from("<I", payload, 0x7c)[0] != 0xd53bd071:
        raise RuntimeError("guest does not actually read TPIDRRO into x17 at the witness PC")
    if swap:
        if (not re.search(r"^0000000040084080 T native_efi_tpidr$", symbols, re.M) or
                not re.search(r"^0000000040084090 T native_efi_svc$", symbols, re.M) or
                struct.unpack_from("<II", payload, 0x80) != (0xd53bd04d, 0xf940022f) or
                struct.unpack_from("<I", payload, 0x90)[0] != 0xd4001001):
            raise RuntimeError("swap guest must read TPIDR into x13, load data through x17, and SVC at +0x90")
    owner_bytes = owner.read_bytes()
    required_mode = (b"ASOFT_NATIVE_EL0_TPIDRRO=1\0" if swap else
                     b"ASOFT_NATIVE_EL0_TPIDRRO_TRAP=1\0")
    forbidden_mode = (b"ASOFT_NATIVE_EL0_TPIDRRO_TRAP=1\0" if swap else
                      b"ASOFT_NATIVE_EL0_TPIDRRO=1\0")
    if required_mode not in owner_bytes or forbidden_mode in owner_bytes:
        raise RuntimeError("supervisor must select exactly its own TPIDRRO mode")
    return [guest, owner], [guest_command, owner_command]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ndk", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    tools = args.ndk.resolve() / "toolchains/llvm/prebuilt/linux-x86_64/bin"
    artifacts, commands = [], []
    for swap in (False, True):
        built, ran = build_mode(tools, out, swap)
        artifacts.extend(built)
        commands.extend(ran)
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
        "modes": {
            "native": {"tpidrro_mode": "generic_trap", "guest": "native-efi-guest.elf",
                       "owner": "native-efi-owner", "required_trap_reads": 2},
            "native-swap": {
                "tpidrro_mode": "ios_swap", "guest": "native-efi-swap-guest.elf",
                "owner": "native-efi-swap-owner", "generic_trap_enabled": False,
                "tpidrro_values": ["0x100008100", "0x100008140"],
                "native_tpidr_hint": "0x0",
                "el1_tpidr_values": ["0x56780000", "0x56780001"],
                "thread_data_values": ["0x123456789abc0000", "0x123456789abc0001"],
                "native_tpidr_pc": "0x100000080", "svc_return_pc": "0x100000094",
                "guest_register_records_required": 2,
                "native_workers": 1,
                "scope": "authored swap semantics plus exact EFI frames; not an iOS boot or app-UID run",
            },
        },
        "ios_tpidrro_swap_changed": False,
        "producer_cpu_atomics": False,
        "source_sha256": {name: sha(ROOT / name) for name in (
            "native_efi_protocol.h", "native_efi_guest.S", "native_efi_guest.ld",
            "native_efi_owner.c", "native_efi_swap_log.h", "build_native_fixture.py")},
        "commands": [[str(arg) for arg in command] for command in commands],
        "artifacts": {path.name: {"bytes": path.stat().st_size, "sha256": sha(path)}
                      for path in artifacts},
        "gpu_path_complete": False,
    }
    (out / "native-fixture-build.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest["artifacts"]))


if __name__ == "__main__":
    main()
