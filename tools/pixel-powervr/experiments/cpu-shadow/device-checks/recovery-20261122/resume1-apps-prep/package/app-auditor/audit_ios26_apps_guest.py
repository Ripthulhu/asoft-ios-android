#!/usr/bin/env python3
"""Read-only comparison of staged system apps and the exact apps-step result.

Only names, counts, metadata, hashes and bounded utility diagnostics leave the
helper. No application code, plist values or image content is returned.
"""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import resource
import stat
import subprocess
import sys
import tempfile
import time
import types


BUILD, VERSION = "23G90", "26.6.2"
SKIP = frozenset(("AppleVisionProApp.app", "Image Playground.app"))
MAX_ENTRIES, MAX_BUNDLES, MAX_DEPTH = 500_000, 512, 128
MAX_PATH, MAX_COMPONENT, MAX_ERRORS = 4096, 1024, 128
MAX_BYTES, MAX_PLIST = 32 << 30, 1 << 20
APFS_LOG_HEADER = b"APP_COPY_APFS_MOUNT readonly; no lax/debug/identity overrides\n"
NO_BOOT = {"boot_complete": False, "gpu_path_complete": False, "applications_launched": False}


class AppsError(Exception):
    def __init__(self, code, path=None):
        self.code, self.path = code, path
        super().__init__(code)

    def record(self):
        return {"code": self.code, **({"path": self.path} if self.path is not None else {})}


def need(condition, code, path=None):
    if not condition:
        raise AppsError(code, path)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def component(name):
    need(type(name) is str and name not in ("", ".", "..") and "/" not in name and
         not any(c in name for c in "\x00\r\n\t") and len(os.fsencode(name)) <= MAX_COMPONENT,
         "unsupported_name")


def metadata(st):
    return {"type": stat.S_IFMT(st.st_mode), "mode": stat.S_IMODE(st.st_mode),
            "uid": st.st_uid, "gid": st.st_gid, "dev": st.st_dev, "ino": st.st_ino,
            "bytes": st.st_size, "links": st.st_nlink}


class Budget:
    def __init__(self):
        self.entries = self.path_bytes = 0

    def add(self, path):
        self.entries += 1
        self.path_bytes += len(os.fsencode(path))
        need(self.entries <= MAX_ENTRIES and self.path_bytes <= 128 << 20,
             "inventory_bound")


class Tree:
    """All component traversal uses directory fds and O_NOFOLLOW."""
    def __init__(self, root=None, fd=None):
        self.fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW) if fd is None else fd

    def close(self):
        os.close(self.fd)

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        self.close()

    def parent(self, name):
        parts = name.split("/")
        need(len(parts) <= MAX_DEPTH and len(os.fsencode(name)) <= MAX_PATH, "path_bound")
        for part in parts:
            component(part)
        fd = os.dup(self.fd)
        try:
            for part in parts[:-1]:
                newer = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = newer
            return fd, parts[-1]
        except BaseException:
            os.close(fd)
            raise

    def child(self, name):
        parent, leaf = self.parent(name)
        try:
            return Tree(fd=os.open(leaf, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent))
        finally:
            os.close(parent)

    def lstat(self, name):
        parent, leaf = self.parent(name)
        try:
            return os.stat(leaf, dir_fd=parent, follow_symlinks=False)
        finally:
            os.close(parent)

    def open(self, name):
        parent, leaf = self.parent(name)
        try:
            fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            try:
                need(stat.S_ISREG(os.fstat(fd).st_mode), "not_regular", name)
                return os.fdopen(fd, "rb")
            except BaseException:
                os.close(fd)
                raise
        finally:
            os.close(parent)

    def read(self, name):
        with self.open(name) as stream:
            body = stream.read(MAX_PLIST + 1)
        need(len(body) <= MAX_PLIST, "plist_bound", name)
        return body

    def checksum(self, name, expected):
        value, count = hashlib.sha256(), 0
        with self.open(name) as stream:
            before = metadata(os.fstat(stream.fileno()))
            need(before == expected, "file_identity_changed", name)
            for body in iter(lambda: stream.read(1 << 20), b""):
                count += len(body)
                need(count <= expected["bytes"] <= MAX_BYTES, "file_read_bound", name)
                value.update(body)
            need(count == expected["bytes"] and metadata(os.fstat(stream.fileno())) == before,
                 "file_short_or_changed", name)
        return value.hexdigest()

    def inventory(self, budget):
        entries, unique, directories, total = {}, set(), set(), 0
        device = os.fstat(self.fd).st_dev

        def record(path, st):
            nonlocal total
            budget.add(path)
            need(len(os.fsencode(path)) <= MAX_PATH and st.st_dev == device, "path_or_device_changed", path)
            node = metadata(st)
            need(node["type"] in (stat.S_IFDIR, stat.S_IFREG, stat.S_IFLNK), "unsupported_entry_type", path)
            if node["type"] == stat.S_IFLNK:
                need(node["links"] == 1, "linked_symlink_unsupported", path)
            if node["type"] == stat.S_IFREG:
                key = node["dev"], node["ino"]
                if key not in unique:
                    total += node["bytes"]
                    unique.add(key)
                need(0 <= node["bytes"] <= MAX_BYTES and total <= MAX_BYTES, "tree_byte_bound", path)
            entries[path] = node

        def visit(fd, relative, depth):
            need(depth <= MAX_DEPTH, "tree_depth_bound")
            st = os.fstat(fd)
            identity = st.st_dev, st.st_ino
            need(identity not in directories, "directory_alias_unsupported", relative)
            directories.add(identity)
            record(relative, st)
            with os.scandir(fd) as listing:
                names = []
                for item in listing:
                    need(len(names) < MAX_ENTRIES - budget.entries, "directory_entry_bound")
                    names.append(item.name)
            names.sort()
            for name in names:
                component(name)
                path = relative + "/" + name if relative else name
                st = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if stat.S_ISDIR(st.st_mode):
                    child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    try:
                        need((os.fstat(child).st_dev, os.fstat(child).st_ino) == (st.st_dev, st.st_ino),
                             "directory_identity_changed", path)
                        visit(child, path, depth + 1)
                    finally:
                        os.close(child)
                else:
                    record(path, st)
                    if stat.S_ISLNK(st.st_mode):
                        target = os.readlink(name, dir_fd=fd)
                        need(len(os.fsencode(target)) <= MAX_PATH, "symlink_target_bound", path)
                        entries[path]["target"] = target
        visit(self.fd, "", 0)
        return entries


def version_identity(tree):
    for name in ("System/Library/CoreServices/SystemVersion.plist",
                 "System/Library/CoreServices/SystemVersion-iOS.plist"):
        try:
            st = tree.lstat(name)
        except FileNotFoundError:
            continue
        need(stat.S_ISREG(st.st_mode), "system_version_not_regular", name)
        body = tree.read(name)
        try:
            value = plistlib.loads(body)
        except Exception:
            raise AppsError("system_version_parse") from None
        need(type(value) is dict and type(value.get("ProductBuildVersion")) is str and
             type(value.get("ProductVersion")) is str and
             (value["ProductBuildVersion"], value["ProductVersion"]) == (BUILD, VERSION),
             "system_version_mismatch")
        return {"status": "PASSED", "build": BUILD, "version": VERSION,
                "path": name, "bytes": len(body), "sha256": sha(body)}
    raise AppsError("system_version_missing")


def relationships(entries, tags=None):
    groups = {}
    for path, node in entries.items():
        if node["type"] == stat.S_IFREG:
            key = ((tags[path],) if tags is not None else ()) + (node["dev"], node["ino"])
            groups.setdefault(key, []).append(path)
    return sorted(sorted(paths) for paths in groups.values() if len(paths) > 1)


def compare_apps(source, baseline, current):
    budget = Budget()
    src, old, dst = (tree.inventory(budget) for tree in (source, baseline, current))
    roots = {path for path in src if path and "/" not in path}
    need(0 < len(roots) <= MAX_BUNDLES, "source_bundle_count")
    for name in roots:
        need(name.endswith(".app") and not name.startswith((".", "-")) and src[name]["type"] == stat.S_IFDIR,
             "source_bundle_name_or_type", name)
    for entries in (old, dst):
        for name, node in entries.items():
            if name and "/" not in name and name.endswith(".app"):
                need(node["type"] == stat.S_IFDIR, "destination_bundle_not_directory", name)
    eligible = roots - SKIP
    need(eligible, "no_eligible_source_bundles")
    preexisting, new = sorted(eligible & set(old)), sorted(eligible - set(old))
    new_set = set(new)
    expected, tags, origin = dict(old), {p: "preexisting" for p in old}, {p: baseline for p in old}
    for path, node in src.items():
        bundle = path.split("/", 1)[0]
        if bundle not in new_set:
            continue
        need(not node["mode"] & 0o6000, "source_setid_unsupported", path)
        expected[path] = dict(node, uid=0, gid=80 if path == bundle else 0,
                              mode=0o775 if path == bundle else node["mode"])
        tags[path], origin[path] = "new:" + bundle, source
    errors, accumulator, cached = [], hashlib.sha256(), {}

    def fail(code, path=None):
        if len(errors) < MAX_ERRORS:
            errors.append({"code": code, **({"path": path} if path is not None else {})})

    for path in sorted(set(expected) - set(dst)):
        fail("missing_entry", path)
    for path in sorted(set(dst) - set(expected)):
        fail("unexpected_entry", path)
    files = total = copied_files = 0
    for path in sorted(set(expected) & set(dst)):
        want, got = expected[path], dst[path]
        if any(want[key] != got[key] for key in ("type", "mode", "uid", "gid")):
            fail("entry_metadata", path)
            continue
        row = [path, want["type"], want["mode"], want["uid"], want["gid"]]
        if want["type"] == stat.S_IFREG:
            if want["bytes"] != got["bytes"]:
                fail("file_size", path)
                continue
            tree = origin[path]
            original = (old if tree is baseline else src)[path]
            values = []
            for view, item in ((tree, original), (current, got)):
                key = id(view), item["dev"], item["ino"]
                if key not in cached:
                    cached[key] = view.checksum(path, item)
                values.append(cached[key])
            if values[0] != values[1]:
                fail("file_contents", path)
            files += 1
            total += want["bytes"]
            copied_files += tags[path] != "preexisting"
            row += [want["bytes"], values[0], values[1]]
        elif want["type"] == stat.S_IFLNK:
            if want["target"] != got["target"]:
                fail("symlink_text", path)
            row += [want["target"], got["target"]]
        accumulator.update(json_bytes(row) + b"\n")
    expected_links, actual_links = relationships(expected, tags), relationships(dst)
    if expected_links != actual_links:
        fail("hardlink_relationships")
    return {"status": "PASSED" if not errors else "INCOMPLETE", "errors": errors, "error_limit": MAX_ERRORS,
            "source_bundles": len(roots), "new_bundles": new, "preserved_source_name_matches": preexisting,
            "explicit_source_skips": sorted(roots & SKIP), "new_copy_exercised": bool(new),
            "source_entries": len(src), "predecessor_entries": len(old), "destination_entries": len(dst),
            "checked_files": files, "checked_logical_bytes": total, "new_files": copied_files,
            "comparison_sha256": accumulator.hexdigest(), "hardlink_groups": len(actual_links),
            "hardlink_relationship_sha256": sha(json_bytes(actual_links)), "global_nlink_compared": False,
            "unexplained_entries_allowed": False, "xattrs_acls_resource_forks_validated": False}


def inspect_journal(inspector, stream, base, size, approved):
    """Linux may change VH allocation counters; journal bytes must stay approved."""
    volume, headers = inspector.volume_headers(stream, base, size)
    info, jib = inspector.journal_info(stream, base, size, volume)
    need(volume["geometry"] == approved["volume"]["geometry"] and info == approved["journal_info"],
         "journal_identity_changed_after_inspection")
    need(volume["attributes"][0] & (1 << 8) and not volume["attributes"][0] & (1 << 15),
         "volume_not_clean_unmounted")
    inspector.no_metadata_overlap(headers, info["jib_offset"], info["offset"], info["bytes"], size)
    if info["flags"] == 1:
        verdict = inspector.initialized_header(inspector.read_at(stream, base + info["offset"], inspector.SECTOR), info)
        need(verdict == approved["journal"], "initialized_journal_changed_after_inspection")
    else:
        block, body = inspector.authored_jib(size)
        need(approved["journal"].get("state") == "UNTOUCHED_AUTHORED_NEEDINIT" and
             volume["geometry"]["jib_block"] == block and jib == body, "needinit_not_authored")
        value = inspector.zero_region(stream, base + info["offset"], info["bytes"])
        need(value == approved["journal"]["journal_sha256"], "needinit_journal_changed")
        verdict = {"status": "PASSED", "state": "AUTHORED_UNINITIALIZED_JOURNAL_PRESERVED",
                   "journal_sha256": value, "whole_volume_unchanged_claimed": False}
    return {"status": "PASSED", "volume": volume, "journal_info": info, "journal": verdict}


def mounted_at(target):
    matches = []
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        fields = line.split()
        if fields[4] == str(target):
            pivot = fields.index("-")
            matches.append({"device": fields[2], "root": fields[3], "options": fields[5].split(","),
                            "type": fields[pivot + 1], "source": fields[pivot + 2]})
    need(len(matches) <= 1, "ambiguous_mount")
    return matches[0] if matches else None


def readonly_mount(target, kind, loop=None):
    row = mounted_at(target)
    need(row is not None and row["root"] == "/" and {"ro", "nosuid", "nodev", "noexec"} <= set(row["options"]),
         "mount_not_readonly")
    if kind == "hfsplus":
        st = os.stat(loop)
        need(row["type"] == kind and row["device"] == "%d:%d" % (os.major(st.st_rdev), os.minor(st.st_rdev)),
             "hfs_mount_identity")
    else:
        need(row["type"] in ("fuse", "fuse.apfs-fuse") and row["source"] == "apfs-fuse", "apfs_mount_identity")
    return row


def apfs_command(image, mountpoint):
    # In this pinned tool -f means Fusion device; -l permits corrupt fallback.
    return ["apfs-fuse", "-o", "ro,nosuid,nodev,noexec,allow_other", str(image), str(mountpoint)]


def bounded_log():
    resource.setrlimit(resource.RLIMIT_FSIZE, (4 << 20, 4 << 20))


def audit_disks(auditor, inspector, apps_device, activation_device, os_device, policy, out):
    started = time.monotonic()
    result = {"schema": 1, "kind": "ios26_apps_copy_audit", "status": "INCOMPLETE", **NO_BOOT,
              "errors": [], "cleanup_errors": [], "readonly_inputs": False, "readonly_mounts": {},
              "replayed": False, "repaired": False, "audit_nonce": policy.get("audit_nonce"),
              "policy_sha256": sha(json_bytes(policy)), "journals": {}, "fsck": {}, "gpt": {}}
    loops, mounts, workspace = [], [], None
    raw_handles = {}
    try:
        need(policy.get("schema") == 1 and re.fullmatch(r"[0-9a-f]{32}", policy.get("audit_nonce", "")) and
             type(policy.get("os_bytes")) is int and 0 < policy["os_bytes"] <= 32 << 30,
             "invalid_policy")
        devices = {}
        for name, supplied, size in (("apps", apps_device, auditor.DISK_BYTES),
                                     ("activation", activation_device, auditor.DISK_BYTES),
                                     ("os", os_device, policy["os_bytes"])):
            real = str(Path(supplied).resolve(strict=True))
            need(re.fullmatch(r"/dev/vd[a-z]+", real) and stat.S_ISBLK(os.stat(real).st_mode), "unexpected_device")
            need(auditor.command(["blockdev", "--getro", real]) == "1" and
                 int(auditor.command(["blockdev", "--getsize64", real])) == size, "input_not_readonly_exact")
            devices[name] = real
        need(len(set(devices.values())) == 3, "aliased_input_devices")
        result["readonly_inputs"] = True
        start, sectors, _ = auditor.PARTITIONS[0]
        for name in ("activation", "apps"):
            stream = open(devices[name], "rb", buffering=0)
            raw_handles[name] = stream
            result["gpt"][name] = auditor.verify_gpt(stream, auditor.DISK_BYTES)
            result["journals"][name] = inspect_journal(inspector, stream, start * 512, sectors * 512,
                                                       policy["approved_system_journal"])
        need(result["gpt"]["activation"] == result["gpt"]["apps"], "gpt_changed_in_apps_stage")
        workspace = Path(tempfile.mkdtemp(prefix="apps-audit-", dir="/tmp"))
        for name in ("activation", "apps"):
            loop = auditor.command(auditor.loop_command(devices[name], start, sectors))
            need(re.fullmatch(r"/dev/loop[0-9]+", loop), "unexpected_loop")
            loops.append(loop)
            need(auditor.command(["blockdev", "--getro", loop]) == "1" and
                 int(auditor.command(["blockdev", "--getsize64", loop])) == sectors * 512,
                 "loop_not_readonly_exact")
            auditor.ensure_unmounted(loop)
            log = out / ("fsck-" + name + ".txt")
            with log.open("xb") as stream:
                checked = subprocess.run(["fsck.hfsplus", "-f", "-n", loop], stdin=subprocess.DEVNULL,
                    stdout=stream, stderr=subprocess.STDOUT, timeout=1200, check=False, preexec_fn=bounded_log)
            need(log.stat().st_size <= 4 << 20, "fsck_log_bound")
            result["fsck"][name] = auditor.fsck_verdict(checked.returncode, log.read_text(encoding="utf-8", errors="strict"))
            need(result["fsck"][name]["status"] == "PASSED", "fsck_not_clean", name)
        for name, loop in zip(("activation", "apps"), loops):
            target = workspace / name
            target.mkdir()
            mounts.append((target, "hfsplus"))
            auditor.command(auditor.mount_command(loop, target))
            result["readonly_mounts"][name] = readonly_mount(target, "hfsplus", loop)
        image, target = workspace / "source.dmg", workspace / "os"
        os.symlink(devices["os"], image)
        target.mkdir()
        mounts.append((target, "apfs"))
        with (out / "apfs-mount.txt").open("xb") as stream:
            stream.write(APFS_LOG_HEADER)
            stream.flush()
            checked = subprocess.run(apfs_command(image, target), stdin=subprocess.DEVNULL, stdout=stream,
                stderr=subprocess.STDOUT, timeout=60, check=False, preexec_fn=bounded_log)
        need(checked.returncode == 0, "apfs_mount_failed")
        result["readonly_mounts"]["os"] = readonly_mount(target, "apfs")
        with Tree(target) as mounted_os:
            try:
                st = mounted_os.lstat("root")
            except FileNotFoundError:
                st = None
            need(st is None or stat.S_ISDIR(st.st_mode), "apfs_root_not_directory")
            with (mounted_os.child("root") if st is not None else Tree(fd=os.dup(mounted_os.fd))) as os_root, \
                    Tree(workspace / "activation") as before_root, Tree(workspace / "apps") as after_root:
                result["systems"] = {name: version_identity(tree) for name, tree in
                                     (("os", os_root), ("activation", before_root), ("apps", after_root))}
                identities = {(r["path"], r["bytes"], r["sha256"]) for r in result["systems"].values()}
                need(len(identities) == 1, "original_os_version_plist_differs")
                with os_root.child("private/var/staged_system_apps") as source, \
                        before_root.child("Applications") as baseline, after_root.child("Applications") as current:
                    result["comparison"] = compare_apps(source, baseline, current)
                    need(result["comparison"]["status"] == "PASSED", "apps_comparison_failed")
        for name, stream in raw_handles.items():
            need(auditor.verify_gpt(stream, auditor.DISK_BYTES) == result["gpt"][name] and
                 inspect_journal(inspector, stream, start * 512, sectors * 512,
                                 policy["approved_system_journal"]) == result["journals"][name],
                 "raw_metadata_changed")
        result["raw_metadata_unchanged"] = True
        result["status"] = "APP_COPY_AUDIT_PASSED"
    except AppsError as error:
        result["errors"].append(error.record())
    except (auditor.AuditError, inspector.InspectionError) as error:
        result["errors"].append({"code": error.code})
    except Exception as error:
        result["errors"].append({"code": "unexpected_exception", "type": type(error).__name__})
    finally:
        for target, kind in reversed(mounts):
            try:
                if mounted_at(target) is not None:
                    auditor.command(["fusermount", "-u", str(target)] if kind == "apfs" else ["umount", str(target)])
                need(mounted_at(target) is None, "mount_remained")
            except Exception:
                result["cleanup_errors"].append("unmount_" + kind)
        for loop in reversed(loops):
            try:
                auditor.ensure_unmounted(loop)
                auditor.command(["losetup", "--detach", loop])
            except Exception:
                result["cleanup_errors"].append("detach_loop")
        for stream in raw_handles.values():
            try:
                stream.close()
            except OSError:
                result["cleanup_errors"].append("close_raw_input")
        if workspace is not None:
            try:
                if (workspace / "source.dmg").is_symlink():
                    (workspace / "source.dmg").unlink()
                for name in ("os", "apps", "activation"):
                    if (workspace / name).exists():
                        (workspace / name).rmdir()
                workspace.rmdir()
            except OSError:
                result["cleanup_errors"].append("remove_mount_directory")
        log = out / "apfs-mount.txt"
        if log.exists() and log.stat().st_size > 4 << 20:
            result["cleanup_errors"].append("apfs_log_bound")
        if result["cleanup_errors"]:
            result["status"] = "INCOMPLETE"
        result["elapsed_seconds"] = time.monotonic() - started
    return result


def dependency(path, expected):
    body = Path(path).read_bytes()
    need(sha(body) == expected, "dependency_source_hash")
    module = types.ModuleType("bound_" + Path(path).stem)
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def main():
    apps, activation, original, policy_path, auditor_path, inspector_path, output = sys.argv[1:]
    out = Path(output)
    out.mkdir(mode=0o700)
    try:
        policy = json.loads(Path(policy_path).read_text())
        auditor = dependency(auditor_path, policy["partition_guest_sha256"])
        inspector = dependency(inspector_path, policy["firstboot_guest_sha256"])
        result = audit_disks(auditor, inspector, apps, activation, original, policy, out)
    except Exception as error:
        result = {"schema": 1, "status": "INCOMPLETE", "errors": [{"code": "setup_failed", "type": type(error).__name__}]}
    body = json.dumps(result, sort_keys=True, indent=2).encode() + b"\n"
    need(len(body) <= 4 << 20, "result_bound")
    (out / "result.json").write_bytes(body)
    print("APP_COPY_AUDIT_RESULT " + result["status"], flush=True)
    return 0  # Retain failures through the helper's success-only tar channel.


if __name__ == "__main__":
    raise SystemExit(main())
