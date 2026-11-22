#!/usr/bin/env python3
"""Run one real-device EFI diagnostic with a fresh cache and loaded Vulkan validation."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("build", "icd", "layers", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--fragmented", action="store_true")
    args = parser.parse_args()
    record = json.loads((args.build / "build.json").read_text())
    binary = Path(record["binary"]["path"])
    library = Path(record["library"]["path"])
    for key in ("source", "header", "library", "binary"):
        if sha(record[key]["path"]) != record[key]["sha256"]:
            parser.error("build input/output changed: " + key)
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    cache = out / "cache"
    cache.mkdir()
    chosen = {
        "REIMS_VGPU_CPU_SHADOW": "1",
        "VK_ICD_FILENAMES": str(args.icd.resolve()),
        "VK_INSTANCE_LAYERS": "VK_LAYER_KHRONOS_validation",
        "VK_LAYER_ENABLES": "VK_VALIDATION_FEATURE_ENABLE_SYNCHRONIZATION_VALIDATION_EXT",
        "VK_LAYER_PATH": str(args.layers.resolve()),
        "VK_LOADER_DEBUG": "error,warn,layer",
        "XDG_CACHE_HOME": str(cache),
    }
    env = os.environ.copy()
    env.pop("HOME", None)
    env.update(chosen)
    command = [str(binary), *(["--fragmented"] if args.fragmented else [])]
    log = out / "validation.log"
    start = time.monotonic()
    timed_out = False
    with log.open("w") as output:
        process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT,
                                   env=env, start_new_session=True)
        try:
            code = process.wait(timeout=35)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGKILL)
            code = process.wait(timeout=5)
    data = log.read_text(errors="replace")
    results = [line for line in data.splitlines() if line.startswith('{"status"')]
    result = json.loads(results[-1]) if results else None
    errors = [line for line in data.splitlines()
              if re.search(r"Validation Error|SYNC-HAZARD|\bVUID-", line)]
    instance = 'Insert instance layer "VK_LAYER_KHRONOS_validation"' in data
    device = 'Inserted device layer "VK_LAYER_KHRONOS_validation"' in data
    unchanged = sha(library) == record["library"]["sha256"]
    passed = (not timed_out and code == 0 and not errors and instance and device and
              unchanged and result is not None and result["status"] == "EFI_CPU_SHADOW_PASS" and
              result["fragmented"] == args.fragmented)
    report = {
        "command": command, "exit": code, "timed_out": timed_out, "pass": passed,
        "environment": chosen, "child_HOME_removed": True,
        "utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": time.monotonic() - start,
        "result": result, "validation_instance_loaded": instance,
        "validation_device_loaded": device, "validation_error_lines": errors,
        "runtime_unchanged": unchanged,
        "runtime_library_sha256": sha(library), "binary_sha256": sha(binary),
        "log_sha256": sha(log), "build_record_sha256": sha(args.build / "build.json"),
        "gpu_path_complete": False,
    }
    (out / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
