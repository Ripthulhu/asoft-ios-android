#!/usr/bin/env python3
"""Verify the frozen signed Termux index, then extract selected development packages.

No package maintainer scripts or target executables are run. Existing downloads
are accepted only when they match the lock; unrelated host files are untouched.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import json
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    lock = json.loads((ROOT / "termux-lock.json").read_text())
    for item in lock["metadata"]:
        path = ROOT / item["path"]
        if digest(path) != item["sha256"]:
            raise SystemExit(f"Metadata hash mismatch: {path}")
    trust = ROOT / "provenance/gnupg"
    trust.mkdir(mode=0o700, exist_ok=True)
    verify = subprocess.run([
        "gpg", "--no-options", "--homedir", str(trust),
        "--no-default-keyring", "--keyring", str(ROOT / "provenance/termux-autobuilds.gpg"),
        "--keyring", str(ROOT / "provenance/grimler.gpg"),
        "--batch", "--status-fd", "1", "--verify", str(ROOT / "downloads/termux-InRelease"),
    ], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (ROOT / "provenance/termux-signature.txt").write_text(verify.stdout)
    verify.check_returncode()
    if f"VALIDSIG {lock['signer_fingerprint']} " not in verify.stdout:
        raise SystemExit("Signed index did not match the pinned signer")

    def fetch(item):
        path = ROOT / "downloads" / Path(item["Filename"]).name
        if not path.exists():
            req = urllib.request.Request(lock["repository"] + item["Filename"],
                                         headers={"User-Agent": "qemu26-build-reconstruction"})
            with urllib.request.urlopen(req, timeout=45) as response:
                data = response.read()
            if len(data) != int(item["Size"]) or hashlib.sha256(data).hexdigest() != item["SHA256"]:
                raise RuntimeError(f"Downloaded package mismatch: {item['Package']}")
            path.write_bytes(data)
        if path.stat().st_size != int(item["Size"]) or digest(path) != item["SHA256"]:
            raise RuntimeError(f"Cached package mismatch: {path}")
        return item, path

    with ThreadPoolExecutor(max_workers=3) as pool:
        downloaded = list(pool.map(fetch, lock["packages"]))
    for item, path in downloaded:
        subprocess.run(["dpkg-deb", "-x", str(path), str(ROOT / "termux-root")], check=True)
        print(f"VERIFIED {item['Package']} {item['Version']} {item['SHA256']}", flush=True)
    print(f"EXTRACTED {len(downloaded)} packages; target code and maintainer scripts not executed")


if __name__ == "__main__":
    main()
