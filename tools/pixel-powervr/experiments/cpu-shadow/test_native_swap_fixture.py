#!/usr/bin/env python3
"""Compile the swap log verifier on the host and reject incomplete/wrong witnesses.

Only the standalone log parser executes. No QEMU, Android ELF, GPU or guest code
runs here. build_native_fixture.py separately checks the compiled guest's actual
register-read opcodes and PCs with the Android NDK.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parent


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def register_line(phase, **changes):
    # Independent expected protocol values; intentionally not parsed from C.
    values = dict(phase=phase, tpidrro=0x100008100 + phase * 64, tpidr=0,
                  data=0x123456789abc0000 + phase,
                  el1_tpidr=0x56780000 + phase, el1_tpidrro=0x100008100 + phase * 64,
                  read_pc=0x10000007c, svc_return=0x100000094)
    values.update(changes)
    return "NATIVE_EFI_SWAP_REGISTERS " + " ".join(
        name + "=" + format(value, "016x") for name, value in values.items()) + "\n"


def main():
    compiler = shutil.which("cc")
    if compiler is None:
        raise RuntimeError("a host C compiler is required")
    work = Path(tempfile.mkdtemp(prefix="pixel-native-swap-witness-", dir="/tmp"))
    wrapper = work / "check.c"
    wrapper.write_text('''#define _GNU_SOURCE
#include <stdbool.h>
#include <stdint.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "native_efi_protocol.h"
#include "native_efi_swap_log.h"
int main(int argc, char **argv) {
    return argc == 2 && verify_log(argv[1]) ? 0 : 1;
}
''')
    parser = work / "check"
    subprocess.run([compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                    "-I" + str(ROOT), str(wrapper), "-o", str(parser)], check=True)
    init = "native-el0: required initialization ready mode=stubs; native execution required\n"
    boot = "NATIVE_EFI_SWAP_BOOT_EL1\n"
    phase0 = "NATIVE_EFI_SWAP_PHASE_0_REGISTERS_OK\n"
    phase1 = "NATIVE_EFI_SWAP_PHASE_1_REGISTERS_OK\n"
    complete = "NATIVE_EFI_SWAP_GUEST_COMPLETE\n"
    stats = "native-el0: enters 4 svc 2 faults 2 kicks 0 unsupported 0 tpidrro-patched 2\n"
    gpu = ("vresearch-pvg-reims: cpu-shadow chunks=1 views=1 prepared=2 finished=2 "
           "uploaded=32768 scattered=0\n")
    good = init + boot + register_line(0) + phase0 + register_line(1) + phase1 + complete + stats + gpu
    cases = {"complete": (good, True), "crlf": (good.replace("\n", "\r\n"), True)}
    for label, old in (("no-native-init", init), ("no-boot", boot),
                       ("no-phase-zero", phase0), ("no-phase-one", phase1),
                       ("no-completion", complete), ("no-native-stats", stats), ("no-gpu-work", gpu)):
        cases[label] = (good.replace(old, ""), False)
    changes = {
        "stale-tls-pointer": {"tpidrro": 0x100008100},
        "stale-tls-data": {"data": 0x123456789abc0000},
        "generic-tpidr-semantics": {"tpidr": 0x56780001},
        "lost-guest-tpidr": {"el1_tpidr": 0},
        "changed-guest-tpidrro": {"el1_tpidrro": 0x100008100},
        "wrong-read-pc": {"read_pc": 0x100000080},
        "wrong-svc-pc": {"svc_return": 0x100000090},
        "duplicate-phase": {"phase": 0},
    }
    for label, fields in changes.items():
        # phase is a positional argument; preserve dictionary field ordering.
        replacement = register_line(fields.pop("phase", 1), **fields)
        cases[label] = (good.replace(register_line(1), replacement), False)
    cases.update({
        "duplicate-register-record": (good.replace(register_line(0), register_line(0) * 2), False),
        "truncated-register-record": (good.replace(register_line(1), register_line(1)[:-12] + "\n"), False),
        "trailing-register-text": (good.replace(register_line(1), register_line(1).rstrip() + " junk\n"), False),
        "completion-before-phase": (good.replace(complete, "").replace(phase0, complete + phase0), False),
        "duplicate-completion": (good + complete, False),
        "generic-trap-activated": (good + "native-el0: tpidrro-trap ready mode=stubs code=memfd\n", False),
        "generic-guest-completion": (good + "NATIVE_EFI_GUEST_COMPLETE\n", False),
        "guest-failure-after-completion": (good + "NATIVE_EFI_SWAP_GUEST_FAIL\n", False),
        "tcg-fallback": (good + "native-el0: staying on TCG\n", False),
        "native-svc-missing": (good.replace("enters 4 svc 2", "enters 4 svc 1"), False),
        "late-extra-svc": (good + stats.replace("svc 2", "svc 3"), False),
        "incomplete-gpu-work": (good.replace("uploaded=32768", "uploaded=16384"), False),
        "unsettled-gpu-epoch": (good.replace("prepared=2", "prepared=3"), False),
        "generic-only": (init + "NATIVE_EFI_PHASE_0_REGISTERS_OK\nNATIVE_EFI_PHASE_1_REGISTERS_OK\n"
                         + "NATIVE_EFI_GUEST_COMPLETE\n" + stats + gpu, False),
    })
    for name, (content, accepted) in cases.items():
        log = work / (name + ".log")
        log.write_text(content)
        result = subprocess.run([str(parser), str(log)], capture_output=True, text=True,
                                timeout=5, env={**os.environ, "LC_ALL": "C"})
        if (result.returncode == 0) != accepted:
            raise AssertionError((name, result.returncode, result.stdout, result.stderr))
    report = {
        "status": "HOST_SWAP_WITNESS_PARSER_PASS", "cases": len(cases),
        "accepted": [name for name, (_, accepted) in cases.items() if accepted],
        "rejected": [name for name, (_, accepted) in cases.items() if not accepted],
        "source_sha256": {name: digest(ROOT / name) for name in (
            "native_efi_protocol.h", "native_efi_swap_log.h", "test_native_swap_fixture.py")},
        "gpu_executed": False, "native_guest_executed": False, "apple_guest_executed": False,
    }
    (work / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": str(work / "result.json"), **report}, indent=2))


if __name__ == "__main__":
    main()
