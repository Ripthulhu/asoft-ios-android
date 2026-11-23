#!/usr/bin/env python3
"""Recover interrupted native wallpaper-boot Data on a fresh descendant."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import types

BASE = Path("/data/local/tmp")
TOOLING = BASE / "asoft-portable-replay-input-01"
SOURCE_WORK = BASE / "asoft-recovered-gpu-boot-05"
SOURCE = SOURCE_WORK / "files/root.qcow2"
GPU = BASE / "asoft-continue-05/attempts/11-0001/files/root26-gpu.qcow2"
WORK = BASE / "asoft-data-copy-recovery-gpu05"
CHECK = BASE / "asoft-offline-hfs-check-gpu05"
TOOL = BASE / "asoft-portable-replay-test-01/hfsx-recover-raw"
CHECKER = TOOLING / "check_pixel_offline_hfs.py"
RAW = TOOLING / "recover_pixel_data_copy.py"
GUARD = BASE / "pixel-boot-checks-counter1/firstboot/guard_ios26_firstboot.py"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def load(path, pin):
    body = path.read_bytes()
    require(path.resolve(strict=True) == path and hashlib.sha256(body).hexdigest() == pin,
            "pinned input differs: " + str(path))
    module = types.ModuleType("verified_" + path.stem)
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), vars(module))
    return module


def ensure_stopped(raw):
    vm = json.loads((SOURCE_WORK / "vm-result.json").read_bytes())
    clean = vm["cleanup"]
    w = vm["witnesses"]
    require(vm["error"] == "RuntimeError: VM low-memory stop bound" and not vm.get("milestone") and
            all(w[n] for n in ("native_initialization", "native_execution", "gpu_execution", "frame_captured")) and
            not w["fatal_markers"] and clean["stop_flushed"] and clean["quit_acknowledged"] and
            clean["exit_code"] == 0 and clean["echild"] and
            not clean["forced_qemu"] and not clean["forced_descendants"] and not clean["errors"],
            "suspended GPU boot did not stop and flush cleanly")
    commands = [r["request"]["execute"] for r in vm["qmp"]]
    require(commands[-4:] == ["stop", "query-blockstats", "query-block", "quit"],
            "unexpected post-stop QMP order")
    stats, blocks = (r["response"]["return"] for r in vm["qmp"][-3:-1])
    root = next(r for r in blocks if r.get("device") == "root")
    require(root["inserted"]["file"] == str(SOURCE), "wrong QMP root")
    guard = load(GUARD, "ea40638312d6ac41607806ecb03c148fbd0677df6ab01480e13fd40536869674")
    proof = guard.failed_io_counters(stats, blocks)
    info = json.loads(raw.run("info", "--output=json", SOURCE))
    require(info.get("format") == "qcow2" and info.get("full-backing-filename") == str(GPU),
            "interrupted boot has the wrong parent")
    raw.run("check", "--output=json", SOURCE)
    return proof


def export(raw):
    WORK.mkdir(mode=0o700)
    overlay, pending = (WORK / name for name in ("recovered.qcow2", "pending-data.raw"))
    raw.run("create", "-f", "qcow2", "-F", "qcow2", "-b", SOURCE, overlay)
    raw.identity(overlay)
    raw.run("convert", "--image-opts", "-O", "raw",
            raw.options(overlay, raw.DATA_START, raw.DATA_SIZE), pending)
    require(pending.stat().st_size == raw.DATA_SIZE, "wrong Data size")
    with pending.open("rb") as stream:
        stream.seek(1024)
        primary = stream.read(512)
        require(hashlib.sha256(primary).hexdigest() ==
                "e8cc36da1430d67eaf8498d2708b21fa9759ed11eac2f670183ab6d20a7cb7e0",
                "Data primary differs from the read-only probe")
        stream.seek(4096 * struct.unpack_from(">I", primary, 12)[0])
        jib = stream.read(4096)
        flag, (offset, size) = struct.unpack_from(">I", jib)[0], struct.unpack_from(">QQ", jib, 36)
        require(flag == 1 and 4096 <= offset < offset + size <= raw.DATA_SIZE - 4096,
                "unexpected Data journal geometry")
        stream.seek(offset)
        header = stream.read(512)
        endian = ">" if header[:4] == b"JNLx" else "<"
        require(header[:4] in (b"JNLx", b"xLNJ") and
                struct.unpack_from(endian + "QQ", header, 8) == (1073152, 4076032),
                "Data cursors differ from the stopped boot")
    pending.chmod(0o400)
    raw.write_receipt(WORK / "prepared.json", {
        "status": "DATA_COPY_PREPARED", "source_sha256": raw.PINS[SOURCE],
        "pending_data_sha256": raw.sha256(pending), "new_overlay_sha256": raw.sha256(overlay),
    })
    return pending


def main():
    require(sys.argv[1:] == ["--execute"] and sys.flags.isolated and sys.dont_write_bytecode and
            os.geteuid() == 0, "requires root Python -I -B and explicit --execute")
    raw = load(RAW, "b1fc00bd919ca0d2694643218a7cc22d2bd0f45fcfb19b8c82bf1b0a28d2ec7d")
    raw.SOURCE, raw.PARENT = SOURCE, GPU
    raw.PINS = {
        raw.QEMU: "1bd2fd6b968c492d0263436c260af2a8c2ee807cf4afd4fd2abb3300446e2440",
        SOURCE: "163c2124429aee5e0ea74175158772d67f69a7a0c2d17cb579cb078c0028b7cc",
        GPU: "90a8b4b99cc496aabf9ba071c5764a006076fe56494ea40bbe243c4cd8305db6",
        SOURCE_WORK / "result.json": "cfd96af5bc9f4b59d5c479dc900222c8ac54a5b896df8ba21c30eb73937e9358",
        SOURCE_WORK / "vm-result.json": "ee4ef7e5496010841602618841c01eb407b9d649a8e4e49fd4562e1fdeeb093e",
        TOOL: "5fcdc7e9370a9613e96a9d7aea4ebfc21b4d16413d9a8ec4d1d63b4af3ef564e",
        CHECKER: "5ab3255ee8084b9f9bc607d8a24beda78237301b9ffa653faf550fc9f5c7cb29",
    }
    with (raw.PREP / "owner.lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        raw.check_originals()
        qmp = ensure_stopped(raw)
        require(shutil.disk_usage(BASE).free >= 36 << 30, "insufficient space to start recovery")
        pending = export(raw)
        require(shutil.disk_usage(WORK).free >= 34 << 30, "insufficient space for replay scratch and output")
        restored = WORK / "recovered-data.raw"
        print("Replaying the pending Data journal on detached copies", flush=True)
        replay = subprocess.run([str(TOOL), str(pending), str(restored)], check=True, capture_output=True,
                                timeout=900, env={**os.environ, "GOMEMLIMIT": "200MiB", "GOMAXPROCS": "2"})
        with (WORK / "portable.json").open("xb") as f:
            f.write(replay.stdout)
        restored.chmod(0o400)
        digest = raw.sha256(restored)
        fcntl.flock(lock, fcntl.LOCK_UN)
        print("Checking recovered Data in the native Linux helper", flush=True)
        subprocess.run([sys.executable, "-I", "-B", str(CHECKER), "--execute", str(restored),
                        digest, str(CHECK)], check=True, timeout=420)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        vm = json.loads((CHECK / "vm-result.json").read_bytes())
        clean = vm["cleanup"]
        require(vm["natural_exit"] and vm["witnesses"]["native_execution"] and clean["echild"] and
                clean["exit_code"] == 0 and not clean["forced_qemu"] and
                not clean["forced_descendants"] and not clean["errors"], "Data checker did not exit cleanly")
        print("Verifying recovered Data and its QCOW2 boundaries", flush=True)
        raw.publish(WORK, CHECK / "verification.json", False)
        raw.write_receipt(WORK / "stop-proof.json", {"source_sha256": raw.PINS[SOURCE], "qmp": qmp,
                      "manifest_sha256": raw.sha256(WORK / "manifest.json")})
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        print(json.dumps({"status": "INCOMPLETE", "error": str(error),
                          "stderr": (error.stderr or b"").decode(errors="replace")[-1100:]}), flush=True)
        raise SystemExit(2)
