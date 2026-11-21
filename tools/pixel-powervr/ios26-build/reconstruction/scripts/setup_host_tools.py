#!/usr/bin/env python3
"""Restore only the pinned host build-tool wheels from their recorded inputs."""
from pathlib import Path
import hashlib
import json
import subprocess
import urllib.request
import venv

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def main():
    info = json.loads((ROOT / "provenance/tool-inputs.json").read_text())
    wheels = []
    for record in info["host_wheels"]:
        if "url" in record:
            path = ROOT / "downloads" / record["name"]
            path.parent.mkdir(exist_ok=True)
            if not path.exists():
                with urllib.request.urlopen(record["url"], timeout=60) as response:
                    path.write_bytes(response.read())
        else:
            path = ROOT.parent / "qemu-pixel-android-build/python/wheels" / record["name"]
        if path.stat().st_size != record["bytes"] or sha(path) != record["sha256"]:
            raise RuntimeError(f"Host wheel differs from recorded bytes: {path}")
        wheels.append(str(path))
    target = ROOT / "host-tools"
    if not (target / "bin/python3").exists():
        venv.EnvBuilder(with_pip=True).create(target)
    command = [str(target / "bin/python3"), "-m", "pip", "install", "--no-index", *wheels]
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (ROOT / "logs/host-tools-setup.log").write_text(result.stdout)
    (ROOT / "provenance/host-tools-setup.json").write_text(json.dumps({
        "command": command, "exit_code": result.returncode,
        "source_manifest": "tool-inputs.json",
    }, indent=2) + "\n")
    print(result.stdout)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
