#!/usr/bin/env python3
"""Reproduce the address inference; never execute the retained diagnostic."""
import hashlib
import json
from pathlib import Path
import re
import struct


def main():
    here = Path(__file__).resolve().parent
    report = json.loads((here / "native-code-cache-panic-recovery.json").read_text())
    experiment = here.parents[1] / "experiments/native-code-cache"
    data = (experiment / "native_code_cache_diagnostic").read_bytes()
    assert hashlib.sha256(data).hexdigest() == report["frozen_binary"]["sha256"]
    assert data[:6] == b"\x7fELF\x02\x01", "expected ELF64 little-endian"
    assert struct.unpack_from("<H", data, 18)[0] == 183, "expected AArch64"
    phoff = struct.unpack_from("<Q", data, 32)[0]
    phentsize, phnum = struct.unpack_from("<HH", data, 54)
    assert phentsize == 56
    executable = []
    for index in range(phnum):
        kind, flags, _, va, _, size, _, align = struct.unpack_from(
            "<IIQQQQQQ", data, phoff + index * phentsize
        )
        if kind == 1 and flags & 1:
            executable.append((va, va + size, align))
    assert executable
    pc = int(report["panic"]["pc"], 16)
    lr = int(report["panic"]["lr"], 16)
    candidates = set()
    for begin, end, align in executable:
        assert align == 0x4000
        low = pc % align
        for page in range(begin // align, (end - 1) // align + 1):
            offset = page * align + low
            if begin <= offset < end:
                bias = pc - offset
                if any(start <= lr - bias < stop for start, stop, _ in executable):
                    candidates.add(bias)
    assert len(candidates) == 1, f"ambiguous load bias: {sorted(candidates)}"
    bias = candidates.pop()
    instructions = {}
    for line in (experiment / "native_code_cache_diagnostic-disassembly.txt").read_text().splitlines():
        match = re.match(r"\s*([0-9a-f]+):\s+[0-9a-f]{8}\s+(.+)", line)
        if match:
            instructions[int(match[1], 16)] = " ".join(match[2].split())
    result = {
        "binary_sha256": report["frozen_binary"]["sha256"],
        "inferred_load_bias": hex(bias),
        "pc_offset": hex(pc - bias),
        "lr_offset": hex(lr - bias),
        "instructions": {hex(address): instructions[address] for address in
                         (0xc710, 0xc714, 0xc728, 0xc73c, 0xc740, 0xc750, 0xec44)},
        "scope": "Address inference only; asynchronous SError delivery is not a precise fault attribution."
    }
    assert pc - bias == int(report["symbolization"]["pc_offset"], 16)
    assert lr - bias == int(report["symbolization"]["lr_offset"], 16)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
