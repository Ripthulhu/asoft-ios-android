#!/usr/bin/env python3
"""Finalize the clean second embed from preserved bytes, without starting a VM."""

import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import types

BASE = Path("/data/local/tmp")
WORK = BASE / "asoft-rd-embed-02"
PROBE = BASE / "asoft-rd-source-04/probe_ios26_ramdisk.py"
PROBE_SHA = "891dce3d722c091b4c56e9a2bcba61be22b91d91acd6f8a805d956960bc46b63"
BUILDER_SOURCE = BASE / "asoft-rd-embed-source-02/embed_ramdisk_helper.py"
BUILDER_SHA = "04a94c59a2f674ac4fc5f6f83c9a09c84cefbdf7f4442a185093f53d5bd78879"
VM_SHA = "9c41d2cbfb77fe2a0834aff582e0e1f5f8d60fdd8ee5caf9f80eaa272594f087"
RESULT_SHA = "005fa24dc3f66d93ba8cf199e411381f49f58721e81f4662ce51535a011f494f"
IMAGE_SHA = "648bdd2584050b45bab4ac865192940a12079f75f4b443379565af445c6fb18d"
SIGNED_SHA = "00e39e335386e61ee4c208d186a910b9daad40531b3d81d6feb5a2827f859b55"


def main():
    if os.geteuid() or not sys.flags.isolated or not sys.dont_write_bytecode:
        raise ValueError("use root Python -I -B")
    source = PROBE.read_bytes()
    if hashlib.sha256(source).hexdigest() != PROBE_SHA:
        raise ValueError("prior probe source mismatch")
    probe = types.ModuleType("pinned_ramdisk_probe")
    probe.__file__ = str(PROBE)
    exec(compile(source, str(PROBE), "exec"), vars(probe))
    with open(probe.PREP / "owner.lock", "rb",
              opener=lambda path, flags: os.open(path, flags | os.O_NOFOLLOW)) as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        probe.check_inputs()
        prep, _ = probe.preparation()
        image = WORK / "rd-shell-with-helper.hfs"
        probe.file_pin(image, IMAGE_SHA)
        probe.file_pin(BUILDER_SOURCE, BUILDER_SHA)
        vm = json.loads(probe.file_pin(WORK / "vm-result.json", VM_SHA, body=True))
        old = json.loads(probe.file_pin(WORK / "result.json", RESULT_SHA, body=True))
        cleanup, native = vm["cleanup"], vm["witnesses"]
        probe.require(vm["status"] == "VM_OBSERVATION_COMPLETE" and vm["natural_exit"] is True
                      and cleanup["exit_code"] == 0 and cleanup["echild"] is True
                      and not (cleanup["forced_descendants"] or cleanup["forced_qemu"] or cleanup["errors"])
                      and all(native[key] for key in ("native_initialization", "native_execution", "native_svc_final"))
                      and not native["fatal_markers"] and vm["done_codes"] == [0] and vm["out_sizes"] == [10240],
                      "clean native helper witnesses are incomplete")
        probe.require(old["source_sha256"] == BUILDER_SHA and old["preservation_verified"] is True
                      and old["status"] == "INCOMPLETE" and old["error"].startswith("FileNotFoundError:"),
                      "unexpected original host boundary")
        child = json.loads((WORK / "vm.child.json").read_text())
        probe.require(prep.process_identity(child["pid"]) != child, "previous VM still present")
        out = WORK / "finalized-files"
        accepted_path = WORK / "accepted-result.json"
        probe.require(not os.path.lexists(accepted_path), "additive acceptance already exists")
        out.mkdir(mode=0o700)
        prep.safe_return_tar(WORK / "out.raw", vm["out_sizes"][0], out, ["patch-result.json"])
        guest = json.loads((out / "patch-result.json").read_bytes())
        probe.require(guest == {"schema": 1, "copied": True, "unmounted": True,
                                "readonly_fsck": True, "sha256": SIGNED_SHA}, "HFS guest receipt mismatch")
        probe.file_pin(image, IMAGE_SHA)
        probe.file_pin(WORK / "vm-result.json", VM_SHA)
        probe.file_pin(WORK / "result.json", RESULT_SHA)
        source_path = Path(__file__).resolve()
        receipt = {"schema": 1, "status": "RAMDISK_HELPER_EMBEDDED", "checked_utc": prep.cold.utc(),
                   "finalizer_source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                   "builder_source_sha256": BUILDER_SHA, "original_result_sha256": RESULT_SHA, "vm_sha256": VM_SHA,
                   "image": {"path": str(image), "sha256": IMAGE_SHA, "bytes": image.stat().st_size},
                   "guest": guest, "guest_relaunched": False}
        prep.atomic_json(accepted_path, receipt)
        print(json.dumps(receipt, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
