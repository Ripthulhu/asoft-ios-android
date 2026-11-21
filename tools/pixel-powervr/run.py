#!/usr/bin/env python3
"""Run the two synthetic probes sequentially through an existing ADB connection.

Uses only a fresh /data/local/tmp directory on the phone. Root is used for the
second memory test and kernel diagnostics, not to change device policy.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parent
BINARIES = ("tile_image_probe", "dmabuf_probe")
ARTIFACTS = BINARIES + ("tile_image.vert.spv", "tile_image.frag.spv")


def capture(command: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", timeout=timeout,
        check=False,
    )


def verify_binaries() -> None:
    manifest = ROOT / "SHA256SUMS"
    if not manifest.is_file():
        raise RuntimeError("SHA256SUMS is missing. Use the complete package or run build.py first.")
    hashes: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, separator, filename = line.partition("  ")
        if separator:
            hashes[filename] = digest
    for binary in ARTIFACTS:
        relative = "bin/" + binary
        path = ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"Missing {relative}. Run build.py or use the complete package.")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != hashes.get(relative):
            raise RuntimeError(f"Checksum mismatch for {relative}; no file was sent to the phone.")


def choose_device(adb: str, requested: str | None) -> list[str]:
    result = capture([adb, "devices"], 20)
    if result.returncode:
        raise RuntimeError("ADB could not list devices:\n" + result.stdout)
    devices: dict[str, str] = {}
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[1] in {"device", "offline", "unauthorized", "recovery", "sideload"}:
            devices[fields[0]] = fields[1]
    if requested:
        if devices.get(requested) != "device":
            raise RuntimeError("The selected ADB device is absent, unauthorized, or not booted into Android.")
        return [adb, "-s", requested]
    ready = [serial for serial, state in devices.items() if state == "device"]
    if len(ready) != 1 or len(devices) != 1:
        raise RuntimeError(
            "Connect and authorize one Android phone, or select it explicitly with --serial. "
            "Check 'adb devices' and the USB debugging prompt on the phone."
        )
    return [adb, "-s", ready[0]]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", default="adb", help="Path to adb or adb.exe")
    parser.add_argument("--serial", help="Choose one device when more than one is connected")
    parser.add_argument("--no-root", action="store_true", help="Skip the KernelSU/root memory run")
    parser.add_argument("--keep-remote", action="store_true", help="Keep this run's temporary probe directory")
    parser.add_argument("--output", type=Path, help="Destination text report")
    args = parser.parse_args()

    adb = shutil.which(args.adb)
    if not adb:
        raise RuntimeError("ADB was not found. Add Android platform-tools to PATH, or use --adb /path/to/adb.")
    verify_binaries()
    device = choose_device(adb, args.serial)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output = (args.output or ROOT / f"pixel-powervr-results-{stamp}.txt").resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    remote: str | None = None
    with output.open("x", encoding="utf-8", newline="\n") as report:
        report.write("Pixel PowerVR synthetic probe report\nUTC: " + stamp + "\n")
        report.write("No iOS boot is performed by this package. No device policy is changed.\n")
        report.flush()

        def run(label: str, arguments: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
            print(label + "...", flush=True)
            report.write("\n=== " + label + " ===\n")
            report.flush()
            try:
                result = capture(device + arguments, timeout)
            except subprocess.TimeoutExpired as error:
                text = error.stdout or ""
                if isinstance(text, bytes):
                    text = text.decode("utf-8", errors="replace")
                report.write(text + f"\nHOST_TIMEOUT after {timeout}s\n")
                report.flush()
                raise RuntimeError(f"{label} exceeded {timeout}s. Partial report: {output}") from error
            report.write(result.stdout)
            report.write(f"\nexit_code: {result.returncode}\n")
            report.flush()
            for line in result.stdout.splitlines():
                if line.startswith(("RESULT", "result:", "BLOCKED", "UNSUPPORTED", "FAIL", "PASS")):
                    print("  " + line, flush=True)
            return result

        def probe(label: str, command: str, allowed_exit_codes: set[int]) -> None:
            result = run(label, ["shell", command], 75)
            # Only a pass or an explicitly documented capability-unavailable
            # result may continue. The probes' own bounded fence waits return
            # FAIL (1), while shells can encode many different fatal signals.
            if result.returncode not in allowed_exit_codes:
                raise RuntimeError(
                    f"{label} failed, timed out, or terminated unexpectedly "
                    f"(exit code {result.returncode}). Stopping further GPU work; "
                    f"partial report: {output}"
                )

        try:
            created = run("Create temporary probe directory", ["shell", "mktemp -d /data/local/tmp/pixel-powervr.XXXXXX"], 20)
            candidate = created.stdout.strip()
            if created.returncode or not re.fullmatch(r"/data/local/tmp/pixel-powervr\.[A-Za-z0-9]+", candidate):
                raise RuntimeError("Could not create a verified temporary directory on the phone.")
            remote = candidate
            for name in ARTIFACTS:
                pushed = run("Copy " + name, ["push", str(ROOT / "bin" / name), remote + "/" + name], 30)
                if pushed.returncode:
                    raise RuntimeError("ADB push failed for " + name)
            pushed = run("Copy diagnostic script", ["push", str(ROOT / "collect_device.sh"), remote + "/collect_device.sh"], 30)
            if pushed.returncode:
                raise RuntimeError("ADB push failed for diagnostic script")
            permission = run("Set executable bits on probe files", ["shell", "chmod 0755 " + remote + "/tile_image_probe " + remote + "/dmabuf_probe"], 20)
            if permission.returncode:
                raise RuntimeError("Could not mark probe files executable")
            run("Shell environment and Vulkan report", ["shell", "sh " + remote + "/collect_device.sh --gpu"], 45)
            probe("Tile-image ordering test as shell", "timeout 60 " + remote + "/tile_image_probe --shader-dir " + remote, {0, 2})
            probe("DMA-BUF test as shell", "timeout 60 " + remote + "/dmabuf_probe", {0, 2, 3})
            if not args.no_root:
                print("Approve root for the ADB shell in KernelSU if prompted.", flush=True)
                root = run("Check KernelSU root", ["shell", "su -c id"], 45)
                if root.returncode == 0 and re.search(r"\buid=0\b", root.stdout):
                    run("Root environment and kernel configuration", ["shell", "su -c 'sh " + remote + "/collect_device.sh'"], 45)
                    probe("DMA-BUF test as root", "su -c 'timeout 60 " + remote + "/dmabuf_probe'", {0, 2, 3})
                else:
                    report.write("ROOT_RUN_SKIPPED: su did not provide uid 0.\n")
                    print("Root was unavailable; the shell results are still saved.")
        finally:
            if remote and not args.keep_remote:
                run("Remove this run's temporary directory", ["shell", "rm -rf " + remote], 20)
            elif remote:
                print("Temporary files retained at " + remote)
    print("\nReport: " + str(output))
    print("Send that text file back. A probe PASS does not establish that iOS renders correctly.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, KeyboardInterrupt) as error:
        print("Error: " + str(error), file=sys.stderr)
        raise SystemExit(1)
