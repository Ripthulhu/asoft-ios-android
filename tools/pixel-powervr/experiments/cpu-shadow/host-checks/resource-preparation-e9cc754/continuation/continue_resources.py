#!/usr/bin/env python3
"""Continue only the verified resource preparation after zstd's symlink refusal."""
from pathlib import Path
import fcntl
import hashlib
import importlib.util
import json
import os
import sys

ROOT = Path(__file__).resolve().parent
PRIOR = ROOT.parent / "reims-resource-prep-e9cc754-9d8jiytv"
SCRIPT_SHA = "11befc928a1a6f2730b7069f9703b66df4a7f50b1e982cccec1563893b0b75fd"
RECEIPT_SHA = "ec940aa85dcf468e87a867df314526953ba77444798ca2bc04574ecd994692b0"

def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

if digest(PRIOR / "prepare_resources.py") != SCRIPT_SHA or digest(PRIOR / "resource-preparation.json") != RECEIPT_SHA:
    raise ValueError("prior preparation evidence changed")
prior = json.loads((PRIOR / "resource-preparation.json").read_text())
if prior["status"] != "INCOMPLETE" or prior["error"] != "ReadError: empty file":
    raise ValueError("unexpected prior preparation boundary")
if [action["status"] for action in prior["actions"]] != ["OFFLOADED", "OFFLOADED"]:
    raise ValueError("unexpected prior completed operations")

spec = importlib.util.spec_from_file_location("verified_resource_preparation", PRIOR / "prepare_resources.py")
prep = importlib.util.module_from_spec(spec)
sys.dont_write_bytecode = True
spec.loader.exec_module(prep)
prep.ROOT, prep.RECEIPT = ROOT, ROOT / "resource-preparation.json"
prep.state["destination_root"] = str(ROOT)
prep.state["started_utc"] = prep.utc()
prep.state["script_sha256"] = digest(Path(__file__))
prep.state["prior_preparation"] = {"directory": str(PRIOR), "script_sha256": SCRIPT_SHA,
    "receipt_sha256": RECEIPT_SHA, "status": "INCOMPLETE", "completed_offloads_revalidated": []}
prep.state["continuation_reason"] = "zstd rejects the preserved logical symlink by default; use its verified resolved archive path"

def main():
    (ROOT / "inventories").mkdir()
    (ROOT / "archives").mkdir()
    prep.state["source_before"] = prep.source_identity()
    if prep.state["source_before"] != prior["source_before"]:
        raise ValueError("candidate source/override changed since the initial preparation")
    prep.resources("continuation-before")
    expected_logicals = {str(prep.ANDROID), str(prep.ARCHIVE)}
    if {action["logical_path"] for action in prior["actions"]} != expected_logicals:
        raise ValueError("unexpected prior offload identity")
    for index, action in enumerate(prior["actions"]):
        logical, destination = Path(action["logical_path"]), Path(action["destination"])
        prep.idle([logical, destination])
        if (not logical.is_symlink() or os.readlink(logical) != str(destination)
                or logical.resolve(strict=True) != destination
                or prep.identity(logical) != action["logical_symlink_identity"]):
            raise ValueError("completed logical offload changed")
        saved = action["copied_inventory"]
        inventory_path = Path(saved["path"])
        if digest(inventory_path) != saved["sha256"]:
            raise ValueError("prior complete inventory changed")
        recorded = json.loads(inventory_path.read_text())
        current = prep.inventory(destination)
        if current != recorded:
            raise ValueError("completed disk copy no longer matches its complete inventory")
        proof = prep.save_inventory("prior-offload-" + str(index) + "-reverified", current)
        prep.state["prior_preparation"]["completed_offloads_revalidated"].append({
            "logical_path": str(logical), "destination": str(destination), "inventory": proof})
        prep.record()

    logical_archive = prep.ARCHIVE
    resolved_archive = logical_archive.resolve(strict=True)
    archive_sha = prep.EXPECTED[str(logical_archive)]
    if digest(resolved_archive) != archive_sha:
        raise ValueError("resolved archive does not match the fixed e9 archive identity")
    prep.state["archive_read_path"] = {"logical_path": str(logical_archive),
        "resolved_path": str(resolved_archive), "sha256": archive_sha,
        "reason": "Keep the required logical symlink; pass the exact verified regular file to zstd"}
    prep.ARCHIVE = resolved_archive
    prep.EXPECTED[str(resolved_archive)] = archive_sha
    prep.restore_host()
    available = prep.resources("before-optional-prior-archive")["memory"]["MemAvailable_bytes"]
    if available < prep.MIN_MEMORY:
        prep.state["decisions"].append({"utc": prep.utc(), "available_bytes": available,
            "offload_old_prior_archive": True,
            "reason": "Available RAM below requested 4 GiB after primary relocation and host restoration"})
        prep.record()
        prep.offload(prep.OLD_ARCHIVE, ROOT / "archives" / prep.OLD_ARCHIVE.name,
                     "older-prior-archive", prep.EXPECTED[str(prep.OLD_ARCHIVE)])
    else:
        prep.state["decisions"].append({"utc": prep.utc(), "available_bytes": available,
            "offload_old_prior_archive": False,
            "reason": "Requested 4 GiB available-memory threshold already met"})
    prep.state["source_after"] = prep.source_identity()
    if prep.state["source_before"] != prep.state["source_after"]:
        raise ValueError("candidate source/override changed during continuation")
    if digest(PRIOR / "prepare_resources.py") != SCRIPT_SHA or digest(PRIOR / "resource-preparation.json") != RECEIPT_SHA:
        raise ValueError("prior preparation evidence changed during continuation")
    final = prep.resources("after")
    prep.state["source_and_override_unchanged"] = True
    prep.state["prior_preparation_receipt_unchanged"] = True
    prep.state["memory_threshold_bytes"] = prep.MIN_MEMORY
    prep.state["workspace_reserve_bytes"] = prep.DISK_RESERVE
    if (final["memory"]["MemAvailable_bytes"] < prep.MIN_MEMORY
            or final["filesystems"]["/workspace"]["free_bytes"] < prep.DISK_RESERVE):
        raise ValueError("verified continuation completed but final resource headroom is insufficient")
    prep.state["status"] = "RESOURCES_PREPARED_NO_BUILD"
    prep.state["finished_utc"] = prep.utc()
    prep.record()
    print(json.dumps({"status": prep.state["status"], "receipt": str(prep.RECEIPT), "final": final}, indent=2), flush=True)

if __name__ == "__main__":
    lock = os.open(ROOT / "owner.lock", os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            main()
        except BaseException as error:
            prep.state["status"] = "INCOMPLETE"
            prep.state["error"] = type(error).__name__ + ": " + str(error)
            prep.state["finished_utc"] = prep.utc()
            prep.record()
            print(json.dumps({"status": "INCOMPLETE", "error": prep.state["error"],
                "receipt": str(prep.RECEIPT)}, indent=2), flush=True)
            raise
    finally:
        os.close(lock)
