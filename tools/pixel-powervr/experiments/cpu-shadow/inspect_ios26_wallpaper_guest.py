#!/usr/bin/env python3
"""Wallpaper-specific adapter for the unchanged reviewed raw journal/fsck code.

No historical result is read or rewritten here. This fresh helper run executes
the exact raw implementation against the wallpaper disk and its GPU predecessor,
then labels its new receipt with the actual wallpaper inspection context.
"""
import hashlib
import json
from pathlib import Path
import sys
import types


RAW_SHA256 = "ada26de8ababb11bb4af20e558708545eb64fd516481359fd5d0ccf6a7cbae2b"
PARTITION_SHA256 = "6874b9b6b68c7fb50c3f9cf05c1b6a86a53f8fed75863c00a6ad9254b1640593"


def sha(body):
    return hashlib.sha256(body).hexdigest()


def load(path, expected):
    body = Path(path).read_bytes()
    if sha(body) != expected:
        raise ValueError("raw inspection dependency hash mismatch")
    module = types.ModuleType("bound_" + Path(path).stem)
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def inspect(raw, partition, device, predecessor, policy, out):
    if (policy.get("raw_guest_sha256") != RAW_SHA256 or policy.get("partition_guest_sha256") != PARTITION_SHA256 or
            policy.get("kind") != "ios26_saved_wallpaper_inspection"):
        raise ValueError("wallpaper raw implementation policy mismatch")
    result = raw.inspect_disks(partition, device, predecessor, policy, out)
    original_kind, original_status = result.get("kind"), result.get("status")
    if original_kind != "ios26_saved_firstboot_inspection":
        raise ValueError("reviewed raw implementation protocol changed")
    result.update(kind="ios26_saved_wallpaper_inspection",
                  status="SAVED_WALLPAPER_INSPECTION_PASSED" if original_status == "SAVED_FIRSTBOOT_INSPECTION_PASSED" else "INCOMPLETE",
                  raw_implementation={"guest_sha256": RAW_SHA256, "partition_guest_sha256": PARTITION_SHA256,
                                      "returned_kind": original_kind, "returned_status": original_status})
    return result


def main():
    device, predecessor, policy_file, raw_file, partition_file, output = sys.argv[1:]
    out = Path(output)
    out.mkdir(mode=0o700)
    try:
        policy = json.loads(Path(policy_file).read_text())
        raw = load(raw_file, RAW_SHA256)
        partition = load(partition_file, PARTITION_SHA256)
        result = inspect(raw, partition, device, predecessor, policy, out)
    except Exception as error:
        result = {"schema": 1, "kind": "ios26_saved_wallpaper_inspection", "status": "INCOMPLETE",
                  "errors": [{"code": "wallpaper_inspection_setup_failed", "type": type(error).__name__}]}
    (out / "result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    # The native job runner exports tar only for command success. The host
    # separately requires complete passing metadata, matching nonce and logs.
    print("SAVED_WALLPAPER_INSPECTION_RESULT " + result["status"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
