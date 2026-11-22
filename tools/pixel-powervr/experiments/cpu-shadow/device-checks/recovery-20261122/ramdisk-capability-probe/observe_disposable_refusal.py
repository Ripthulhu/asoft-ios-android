#!/usr/bin/env python3
"""Project the pinned disposable HFS attempt without starting a VM."""

import hashlib
import json
from pathlib import Path
import re

BASE = Path("/data/local/tmp")
RUN = BASE / "asoft-rd-probe-06/run"
PREP = BASE / "asoft-rd-fixture-01"
PINS = {
    RUN / "result.json": (21335, "61a48cb59e15ae7068f4dd3a78583f2189b1818af84b6bd234aed3c1a65ea475"),
    RUN / "serial.txt": (29587, "b1086e177b319fc6fd88fa4c80363459ce7cf4ef392474755d7b689d52939b12"),
}
FIXTURE_SHA256 = "d0e6bc14344cb1908e30a353840365141caea8bdecbb2b9625282aac730168d0"
EXPECTED_ERROR = "ValueError: guest helper disposable HFS mount did not complete successfully"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def pinned_bytes(path):
    size, expected = PINS[path]
    require(path.resolve(strict=True) == path, "unexpected receipt path")
    with path.open("rb") as stream:
        body = stream.read(size + 1)
    require(len(body) == size and hashlib.sha256(body).hexdigest() == expected, "receipt pin mismatch")
    return body


def mount_refusal(serial):
    serial = serial.replace(b"\r", b"")
    pattern = rb"(?ms)^@@(P[0-9a-f]{16})S@@\n(.*?)^@@\1E@@$"
    matches = []
    for command in re.finditer(pattern, serial):
        block = command[2]
        if re.search(rb"(?m)^System Policy: mount_hfs\(\d+\) deny\(1\) file-mount /mnt/asoft-recovery$", block):
            matches.append(block)
    require(len(matches) == 1, "expected exactly one nonce-bound System Policy refusal")
    require(re.findall(rb"(?m)^ASOFT_HELPER_EXIT (\d+)$", matches[0]) == [b"1"]
            and b"mount_hfs: Operation not permitted\n" in matches[0],
            "policy refusal and mount exit did not agree")
    return {"operation": "file-mount", "mountpoint": "/mnt/asoft-recovery", "mount_exit": 1}


def inspect_qmp(records, image):
    block_queries = 0
    node_queries = 0
    for row in records:
        command = row["request"]["execute"]
        if command not in ("query-block", "query-named-block-nodes"):
            continue
        reply = row["response"]["return"]
        if command == "query-block":
            block_queries += 1
            require(len(reply) == 1, "unexpected number of attached devices")
            device, = reply
            inserted = device["inserted"]
            require(device["device"] == "disposable" and inserted["file"] == str(image)
                    and inserted["drv"] == "raw" and inserted["ro"] is False
                    and inserted.get("backing_file_depth", 0) == 0, "unexpected attached device")
        else:
            node_queries += 1
            require(len(reply) == 2 and {node["drv"] for node in reply} == {"file", "raw"}
                    and all(node["file"] == str(image) for node in reply), "unexpected block node inventory")
    require(block_queries == node_queries == 4, "missing QMP block rechecks")
    return block_queries


def main():
    receipt = json.loads(pinned_bytes(RUN / "result.json"))
    require(receipt["status"] == "INCOMPLETE" and receipt["error"] == EXPECTED_ERROR,
            "unexpected probe disposition")
    cleanup = receipt["cleanup"]
    native = receipt["native_witnesses"]
    require(cleanup["exit_code"] == 0 and cleanup["echild"] is True and cleanup["quit_acknowledged"] is True
            and not (cleanup["forced_qemu"] or cleanup["forced_descendants"] or cleanup["errors"]),
            "probe did not clean up")
    require(all(native[key] for key in ("native_initialization", "native_execution", "native_svc_final"))
            and not native["fatal_markers"], "missing native evidence")
    require(receipt["bound_inputs_reverified"] is True and receipt["guest_helper"]["inspect_root_executed"] is True
            and receipt["guest_helper"]["unmount_exercised"] is False, "unexpected guest activity")
    for label in ("owner", "child"):
        process = receipt[label]
        try:
            raw = Path(f"/proc/{process['pid']}/stat").read_text()
        except FileNotFoundError:
            continue
        ticks = int(raw.rsplit(")", 1)[1].split()[19])
        require(ticks != process["start_ticks"], f"probe {label} is still running")
    image = RUN / "disposable.hfs"
    for path in (image, PREP / "disposable.hfs"):
        require(path.resolve(strict=True) == path and path.stat().st_size == 96 << 20, "wrong disposable image")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        require(digest == FIXTURE_SHA256, "disposable image bytes changed")
    result = mount_refusal(pinned_bytes(RUN / "serial.txt"))
    result.update(status="DISPOSABLE_HFS_MOUNT_DENIED", block_inventory_checks=inspect_qmp(receipt["qmp"], image),
                  fixture_sha256=FIXTURE_SHA256, fixture_bytes_unchanged=True, native_vm_cleanup_verified=True,
                  unmount_exercised=False, replay_exercised=False, saved_data_attached=False)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
