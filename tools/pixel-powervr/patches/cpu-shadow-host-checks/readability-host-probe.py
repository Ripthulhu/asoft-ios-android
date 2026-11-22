#!/usr/bin/env python3
"""Check one self process_vm_readv without a project build or GPU operation.

Portable adaptation of the exact stdin program preserved alongside this file.
It has not been executed as part of the recorded 2026-11-22 diagnostic.
Prints JSON; --output additionally creates a new file and refuses to overwrite.
"""

import argparse
import ctypes
import datetime
import errno
import json
import os
from pathlib import Path


class Iovec(ctypes.Structure):
    _fields_ = [("iov_base", ctypes.c_void_p), ("iov_len", ctypes.c_size_t)]


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, help="create a new JSON receipt; must not exist")
args = parser.parse_args()

libc = ctypes.CDLL(None, use_errno=True)
libc.process_vm_readv.argtypes = [
    ctypes.c_int,
    ctypes.POINTER(Iovec),
    ctypes.c_ulong,
    ctypes.POINTER(Iovec),
    ctypes.c_ulong,
    ctypes.c_ulong,
]
libc.process_vm_readv.restype = ctypes.c_ssize_t
source = ctypes.c_ubyte(0x5A)
dest = ctypes.c_ubyte(0)
local = Iovec(ctypes.addressof(dest), 1)
remote = Iovec(ctypes.addressof(source), 1)
ctypes.set_errno(0)
count = libc.process_vm_readv(
    os.getpid(), ctypes.byref(local), 1, ctypes.byref(remote), 1, 0
)
error = ctypes.get_errno()
status = {
    line.split(":", 1)[0]: line.split(":", 1)[1].strip()
    for line in Path("/proc/self/status").read_text().splitlines()
    if line.startswith(("Seccomp:", "Seccomp_filters:", "NoNewPrivs:"))
}
result = {
    "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "scope": (
        "Read-only host diagnostic of process_vm_readv on one byte of this process's "
        "own initialized writable memory; not a project test or GPU job."
    ),
    "call": "process_vm_readv(getpid(), &local, 1, &remote, 1, 0)",
    "requested_bytes": 1,
    "expected_byte": source.value,
    "returned_count": count,
    "errno": error,
    "errno_name": errno.errorcode.get(error),
    "errno_text": os.strerror(error),
    "destination_byte": dest.value,
    "proc_status": status,
}
rendered = json.dumps(result, indent=2)
if args.output is not None:
    with args.output.open("x") as receipt:
        receipt.write(rendered + "\n")
print(rendered)
