#!/usr/bin/env python3
"""Verified relocation of the explicitly authorized inactive reims caches."""
from pathlib import Path, PurePosixPath
from collections import defaultdict
import datetime
import fcntl
import hashlib
import json
import os
import posixpath
import shutil
import stat
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parent
RECEIPT = ROOT / "resource-preparation.json"
SOURCE = Path("/home/agent/.cache/reims-pixel-cpu-shadow-capabilities")
RUNTIME = Path("/workspace/scratch/3ef77e3b5dde/metal2vulkan-paged-shadow")
ANDROID = Path("/dev/shm/reims-pixel-cpu-shadow-target")
HOST = Path("/home/agent/.cache/reims-pixel-capabilities-target")
ARCHIVE = Path("/tmp/reims-pixel-capabilities-host-target-e9cc754.tar.zst")
OLD_ARCHIVE = Path("/tmp/pixel-cpu-shadow-prior-builds.tar.zst")
EXPECTED = {
    str(ARCHIVE): "13c4a006e87a11afe29ab8f052a2c28673233a308e684fe53b4ec0665be897c5",
    str(OLD_ARCHIVE): "d8f010a060efa106c65aee446399d0d5f57c3a6e90a52757e55b7dfc85462ca5",
}
MIN_MEMORY = 4 << 30
DISK_RESERVE = 1536 << 20
state = {
    "schema": 1, "kind": "reims_verified_resource_preparation",
    "status": "IN_PROGRESS", "destination_root": str(ROOT),
    "authorized_scope": "Offload three specified inactive caches/archives; restore exact e9 host graph behind its original logical path",
    "builds_started": False, "tests_started": False, "phone_operations_performed": False,
    "actions": [], "samples": [], "decisions": [],
}

def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

def write(path, value):
    path = Path(path)
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

def record():
    write(RECEIPT, state)

def identity(path):
    row = Path(path).lstat()
    return {"device": row.st_dev, "inode": row.st_ino, "mode": stat.S_IMODE(row.st_mode),
            "uid": row.st_uid, "gid": row.st_gid, "bytes": row.st_size,
            "mtime_ns": row.st_mtime_ns, "ctime_ns": row.st_ctime_ns, "links": row.st_nlink}

def stable_signature(row):
    return tuple(getattr(row, key) for key in ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid",
                                               "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink"))

def inventory(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("inventory root must be the real owned input")
    rows, links, link_counts = {}, defaultdict(list), {}
    def visit(item, relative):
        before = item.lstat()
        base = {"mode": stat.S_IMODE(before.st_mode), "uid": before.st_uid,
                "gid": before.st_gid, "mtime_ns": before.st_mtime_ns}
        if stat.S_ISDIR(before.st_mode):
            rows[relative] = dict(base, kind="directory")
            for child in sorted(item.iterdir(), key=lambda p: p.name):
                visit(child, child.name if relative == "." else relative + "/" + child.name)
        elif stat.S_ISREG(before.st_mode):
            rows[relative] = dict(base, kind="file", bytes=before.st_size, sha256=sha(item))
            key = (before.st_dev, before.st_ino)
            links[key].append(relative)
            link_counts[key] = before.st_nlink
        elif stat.S_ISLNK(before.st_mode):
            rows[relative] = dict(base, kind="symlink", target=os.readlink(item))
        else:
            raise ValueError("unexpected special cache entry: " + str(item))
        if stable_signature(before) != stable_signature(item.lstat()):
            raise ValueError("input changed while inventoried: " + str(item))
    visit(path, ".")
    unique_bytes = 0
    for key, names in links.items():
        names.sort()
        if link_counts[key] != len(names):
            raise ValueError("external regular-file hardlink would not be preserved: " + names[0])
        unique_bytes += rows[names[0]]["bytes"]
        for name in names:
            rows[name]["hardlink_group"] = names[0]
    return {"entries": rows, "entry_count": len(rows), "unique_regular_bytes": unique_bytes}

def save_inventory(name, value):
    path = ROOT / "inventories" / (name + ".json")
    write(path, value)
    return {"path": str(path), "sha256": sha(path), "entry_count": value["entry_count"],
            "unique_regular_bytes": value["unique_regular_bytes"]}

def durable_copy(path, snapshot):
    path = Path(path)
    seen, directories = set(), []
    for relative, row in snapshot["entries"].items():
        item = path if relative == "." else path / relative
        if row["kind"] == "directory":
            directories.append(item)
        elif row["kind"] == "file" and row["hardlink_group"] not in seen:
            seen.add(row["hardlink_group"])
            fd = os.open(item, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    for directory in sorted(directories, key=lambda value: len(value.parts), reverse=True) + [path.parent]:
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

def resources(phase):
    mem = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        fields = line.split()
        if fields[0].rstrip(":") in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree", "Shmem"):
            mem[fields[0].rstrip(":") + "_bytes"] = int(fields[1]) * 1024
    disks = {}
    for path in ("/workspace", "/home/agent", "/dev/shm", "/tmp"):
        value = shutil.disk_usage(path)
        disks[path] = {"total_bytes": value.total, "used_bytes": value.used, "free_bytes": value.free}
    result = {"phase": phase, "utc": utc(), "memory": mem, "filesystems": disks}
    state["samples"].append(result)
    record()
    return result

def require_space(bytes_needed):
    available = shutil.disk_usage(ROOT).free
    if available < bytes_needed + DISK_RESERVE:
        raise ValueError("insufficient workspace space for verified copy plus reserve")
    return available

def matching(value, roots):
    value = value.removesuffix(" (deleted)")
    return any(value == root or value.startswith(root + "/") for root in roots)

def idle(paths):
    roots = {str(Path(p).absolute()) for p in paths}
    roots.update(str(Path(p).resolve()) for p in paths)
    owners, unreadable = [], []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        pid = int(proc.name)
        try:
            for name in ("cwd", "exe"):
                try:
                    target = os.readlink(proc / name)
                except FileNotFoundError:
                    continue
                if matching(target, roots):
                    owners.append({"pid": pid, "kind": name, "path": target})
            for fd in (proc / "fd").iterdir():
                try:
                    target = os.readlink(fd)
                except FileNotFoundError:
                    continue
                if matching(target, roots):
                    owners.append({"pid": pid, "kind": "fd", "path": target})
            for line in (proc / "maps").read_text().splitlines():
                fields = line.split(maxsplit=5)
                if len(fields) == 6 and matching(fields[5], roots):
                    owners.append({"pid": pid, "kind": "mapping", "path": fields[5]})
        except FileNotFoundError:
            continue
        except PermissionError:
            unreadable.append(pid)
    observation = {"utc": utc(), "paths": sorted(roots), "owners": owners, "unreadable_pids": unreadable}
    state.setdefault("ownership_checks", []).append(observation)
    record()
    if owners or unreadable:
        raise ValueError("cache ownership could not be established as inactive")

def run(command, label):
    log = ROOT / (label + ".log")
    with log.open("xb") as stream:
        done = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
        stream.flush()
        os.fsync(stream.fileno())
    result = {"argv": command, "exit_code": done.returncode, "log": str(log), "log_sha256": sha(log)}
    state.setdefault("commands", []).append(result)
    record()
    if done.returncode:
        raise ValueError("owned resource operation failed: " + label)

def source_identity():
    def git(path, arguments):
        return subprocess.check_output(["git", *arguments], cwd=path,
            env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"), text=True).strip()
    return {"reims_head": git(SOURCE, ["rev-parse", "HEAD"]),
        "reims_status": git(SOURCE, ["status", "--porcelain"]),
        "cargo_manifest_sha256": sha(SOURCE / "Cargo.toml"),
        "cargo_lock_sha256": sha(SOURCE / "Cargo.lock"),
        "runtime_head": git(RUNTIME, ["rev-parse", "HEAD"]),
        "runtime_status": git(RUNTIME, ["status", "--porcelain"])}

def offload(source, target, label, expected_sha=None):
    source, target = Path(source), Path(target)
    if source.is_symlink() or target.exists() or target.is_symlink():
        raise ValueError("offload source/target is not the expected fresh real path")
    idle([source, target, "/home/agent/.cache/reims-pixel-cpu-shadow-target"] if source == ANDROID else [source, target])
    before = inventory(source)
    if expected_sha is not None and (before["entries"]["."].get("sha256") != expected_sha or not source.is_file()):
        raise ValueError("archive does not match the previously verified SHA")
    original_id = identity(source)
    require_space(before["unique_regular_bytes"])
    action = {"kind": "verified_offload", "logical_path": str(source), "destination": str(target),
        "before_identity": original_id, "source_inventory": save_inventory(label + "-source", before),
        "status": "COPYING"}
    state["actions"].append(action)
    record()
    run(["cp", "-a", "--", str(source), str(target)], label + "-copy")
    copied, still_original = inventory(target), inventory(source)
    if copied != before or still_original != before or identity(source) != original_id:
        raise ValueError("complete copied inventory/hash or source stability verification failed")
    durable_copy(target, copied)
    action["copied_inventory"] = save_inventory(label + "-copied", copied)
    action["complete_inventory_hash_mode_mtime_hardlink_match"] = True
    action["copied_files_and_directories_fsynced"] = True
    action["copied_identity"] = identity(target)
    action["status"] = "VERIFIED_BEFORE_RELEASE"
    record()
    idle([source, target])
    backup = source.with_name(source.name + ".offload-" + ROOT.name.rsplit("-", 1)[-1])
    if backup.exists() or backup.is_symlink():
        raise ValueError("temporary source backup already exists")
    os.rename(source, backup)
    try:
        os.symlink(str(target), source, target_is_directory=target.is_dir())
        if source.resolve(strict=True) != target or inventory(target) != before or inventory(backup) != before:
            raise ValueError("logical replacement no longer reaches the verified complete copy")
    except BaseException:
        if source.is_symlink() and os.readlink(source) == str(target):
            source.unlink()
        if not source.exists() and not source.is_symlink():
            os.rename(backup, source)
        raise
    action["temporary_original_backup"] = str(backup)
    action["logical_symlink_identity"] = identity(source)
    action["logical_symlink_target"] = os.readlink(source)
    action["status"] = "VERIFIED_LOGICAL_REPLACEMENT"
    record()
    idle([backup, target])
    if backup.is_dir():
        shutil.rmtree(backup)
    else:
        backup.unlink()
    action["original_released_only_after_verification"] = True
    action["status"] = "OFFLOADED"
    record()
    resources(label + "-complete")
    print(label + ": OFFLOADED", flush=True)

def archive_layout(path):
    entries, hardlinks, regular = {}, {}, set()
    process = subprocess.Popen(["zstd", "-dc", str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
            for member in archive:
                name = member.name.rstrip("/")
                parts = PurePosixPath(name).parts
                if (not parts or parts[0] != "debug" or name.startswith("/") or
                        any(part in ("", ".", "..") for part in parts) or name in entries):
                    raise ValueError("unsafe or duplicate host archive member")
                if member.isdir():
                    kind = "directory"
                elif member.isfile():
                    kind = "file"
                    regular.add(name)
                elif member.islnk():
                    kind = "file"
                    hardlinks[name] = member.linkname
                elif member.issym():
                    kind = "symlink"
                    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), member.linkname))
                    if member.linkname.startswith("/") or not (resolved == "debug" or resolved.startswith("debug/")):
                        raise ValueError("escaping host archive symlink")
                else:
                    raise ValueError("unsupported host archive entry")
                entries[name] = {"kind": kind, "bytes": member.size, "mode": member.mode}
        while process.stdout.read(1 << 20):
            pass
        process.stdout.close()
        error = process.stderr.read().decode()
        if process.wait() or error:
            raise ValueError("archive listing/decompression failed")
    except BaseException:
        process.kill()
        process.wait()
        raise
    groups = defaultdict(list)
    for name in regular | set(hardlinks):
        target, seen = name, set()
        while target in hardlinks:
            if target in seen:
                raise ValueError("cyclic archive hardlink")
            seen.add(target)
            target = hardlinks[target]
        if target not in regular:
            raise ValueError("archive hardlink has no internal regular target")
        groups[target].append(name)
    group_by_name = {}
    for names in groups.values():
        for name in names:
            group_by_name[name] = min(names)
    return entries, group_by_name

def restore_host():
    destination = ROOT / "host-target"
    idle([HOST, destination, ARCHIVE])
    if HOST.is_symlink() or destination.exists():
        raise ValueError("host target no longer has its expected real-directory shape")
    prior_root_stat = HOST.stat()
    before, before_id = inventory(HOST), identity(HOST)
    if any(name == "debug" or name.startswith("debug/") for name in before["entries"]):
        raise ValueError("host target already has a live debug graph")
    if sha(ARCHIVE) != EXPECTED[str(ARCHIVE)]:
        raise ValueError("host archive changed before restore")
    members, groups = archive_layout(ARCHIVE)
    require_space(sum(m["bytes"] for m in members.values()) + before["unique_regular_bytes"])
    action = {"kind": "restore_verified_host_graph", "logical_path": str(HOST), "destination": str(destination),
        "before_identity": before_id, "tiny_prior_inventory": save_inventory("host-prior-tiny", before),
        "archive": str(ARCHIVE), "archive_sha256": EXPECTED[str(ARCHIVE)], "archive_member_count": len(members),
        "status": "RESTORING"}
    state["actions"].append(action)
    record()
    run(["cp", "-a", "--", str(HOST), str(destination)], "host-skeleton-copy")
    run(["tar", "--zstd", "-xpf", str(ARCHIVE), "-C", str(destination)], "host-archive-restore")
    run(["tar", "--zstd", "--compare", "-f", str(ARCHIVE), "-C", str(destination)], "host-archive-compare")
    os.utime(destination, ns=(prior_root_stat.st_atime_ns, prior_root_stat.st_mtime_ns), follow_symlinks=False)
    restored = inventory(destination)
    rows = restored["entries"]
    if set(rows) != set(before["entries"]) | set(members):
        raise ValueError("restored host graph contains missing or unexplained entries")
    for name, row in before["entries"].items():
        if rows[name] != row:
            raise ValueError("host metadata skeleton changed during archive restore")
    for name, entry in members.items():
        if rows[name]["kind"] != entry["kind"] or rows[name]["mode"] != entry["mode"]:
            raise ValueError("archive type/mode differs after restoration")
        if entry["kind"] == "file" and rows[name]["hardlink_group"] != groups[name]:
            raise ValueError("archive hardlink relationship was not preserved")
    if inventory(HOST) != before or identity(HOST) != before_id:
        raise ValueError("tiny original host target changed")
    durable_copy(destination, restored)
    action["restored_inventory"] = save_inventory("host-restored", restored)
    action["tar_full_content_and_metadata_compare_exit_code"] = 0
    action["complete_inventory_and_hardlink_match"] = True
    action["restored_files_and_directories_fsynced"] = True
    action["status"] = "VERIFIED_BEFORE_SWITCH"
    record()
    idle([HOST, destination, ARCHIVE])
    backup = HOST.with_name(HOST.name + ".pre-disk-" + ROOT.name.rsplit("-", 1)[-1])
    if backup.exists() or backup.is_symlink():
        raise ValueError("prior host backup path already exists")
    os.rename(HOST, backup)
    try:
        os.symlink(str(destination), HOST, target_is_directory=True)
        if HOST.resolve(strict=True) != destination or inventory(backup) != before:
            raise ValueError("host logical path or preserved tiny backup mismatch")
    except BaseException:
        if HOST.is_symlink() and os.readlink(HOST) == str(destination):
            HOST.unlink()
        if not HOST.exists() and not HOST.is_symlink():
            os.rename(backup, HOST)
        raise
    action["retained_prior_directory"] = str(backup)
    action["retained_prior_identity"] = identity(backup)
    action["logical_symlink_identity"] = identity(HOST)
    action["logical_symlink_target"] = os.readlink(HOST)
    action["status"] = "RESTORED"
    record()
    resources("host-restored")
    print("host-target: RESTORED", flush=True)

def main():
    (ROOT / "inventories").mkdir()
    (ROOT / "archives").mkdir()
    state["started_utc"], state["script_sha256"] = utc(), sha(__file__)
    state["source_before"] = source_identity()
    if state["source_before"]["reims_head"] != "e9cc7541e4edee4896d9564b3056bb2799595d3f":
        raise ValueError("candidate source revision changed")
    resources("before")
    offload(ANDROID, ROOT / "android-target", "android-target")
    offload(ARCHIVE, ROOT / "archives" / ARCHIVE.name, "host-archive", EXPECTED[str(ARCHIVE)])
    restore_host()
    available = resources("before-optional-prior-archive")["memory"]["MemAvailable_bytes"]
    if available < MIN_MEMORY:
        state["decisions"].append({"utc": utc(), "reason": "Available RAM below requested 4 GiB after primary relocation",
                                   "available_bytes": available, "offload_old_prior_archive": True})
        record()
        offload(OLD_ARCHIVE, ROOT / "archives" / OLD_ARCHIVE.name, "older-prior-archive", EXPECTED[str(OLD_ARCHIVE)])
    else:
        state["decisions"].append({"utc": utc(), "available_bytes": available, "offload_old_prior_archive": False,
                                   "reason": "Requested 4 GiB available-memory threshold already met"})
    state["source_after"] = source_identity()
    if state["source_after"] != state["source_before"]:
        raise ValueError("source or local Cargo override changed during resource preparation")
    final = resources("after")
    state["source_and_override_unchanged"] = True
    state["memory_threshold_bytes"] = MIN_MEMORY
    state["workspace_reserve_bytes"] = DISK_RESERVE
    if final["memory"]["MemAvailable_bytes"] < MIN_MEMORY or final["filesystems"]["/workspace"]["free_bytes"] < DISK_RESERVE:
        raise ValueError("verified relocation completed but final resource headroom is insufficient")
    state["status"] = "RESOURCES_PREPARED_NO_BUILD"
    state["finished_utc"] = utc()
    record()
    print(json.dumps({"status": state["status"], "receipt": str(RECEIPT), "final": final}, indent=2), flush=True)

if __name__ == "__main__":
    lock = os.open(ROOT / "owner.lock", os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            main()
        except BaseException as error:
            state["status"] = "INCOMPLETE"
            state["error"] = type(error).__name__ + ": " + str(error)
            state["finished_utc"] = utc()
            record()
            print(json.dumps({"status": state["status"], "error": state["error"], "receipt": str(RECEIPT)}, indent=2), flush=True)
            raise
    finally:
        os.close(lock)

