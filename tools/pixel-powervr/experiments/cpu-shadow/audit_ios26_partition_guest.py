#!/usr/bin/env python3
"""Read-only partition audit inside the pinned native Linux helper.

Only metadata, digests, verdicts and unfiltered fsck diagnostics are returned.
No image bytes, plist values, certificates, or file contents enter the report.
"""
import copy
import datetime
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import resource
import stat
import struct
import subprocess
import sys
import time
import uuid
import zlib


DISK_BYTES = 51_541_704_704
SECTOR = 512
PARTITIONS = ((2048, 67_108_864, "iOSRoot"), (67_110_912, 33_554_432, "Data"))
HFS_TYPE = uuid.UUID("48465300-0000-11AA-AA11-00306543ECAC").bytes_le
MAX_PLIST = 32 << 20
MAX_ENTRIES = 500_000
FSTAB = b"/dev/disk0s1 / hfs ro 0 1\n/dev/disk0s2 /private/var hfs rw,nosuid,nodev 0 2\n"


class AuditError(Exception):
    def __init__(self, code, path=None):
        # Never include exception payloads or parsed plist values.
        self.code, self.path = code, path
        super().__init__(code)

    def record(self):
        return {"code": self.code, **({"path": self.path} if self.path is not None else {})}


def demand(ok, code, path=None):
    if not ok:
        raise AuditError(code, path)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def read_at(stream, offset, size):
    stream.seek(offset)
    data = stream.read(size)
    demand(len(data) == size, "short_disk_read")
    return data


def verify_gpt(stream, disk_bytes):
    """Check both on-disk copies; no in-memory recovery by sgdisk is accepted."""
    demand(disk_bytes == DISK_BYTES, "disk_size")
    total = disk_bytes // SECTOR
    mbr = read_at(stream, 0, SECTOR)
    entry = mbr[446:462]
    demand(mbr[510:512] == b"\x55\xaa" and entry[0] == 0 and entry[4] == 0xEE and
           struct.unpack_from("<II", entry, 8) == (1, min(total - 1, 0xFFFFFFFF)) and
           mbr[462:510] == bytes(48), "protective_mbr")
    arrays, guids, headers = [], [], []
    for current, backup, entries_lba in ((1, total - 1, 2), (total - 1, 1, total - 33)):
        raw = read_at(stream, current * SECTOR, SECTOR)
        fields = struct.unpack_from("<8sIIIIQQQQ16sQIII", raw)
        sig, revision, size, crc, reserved, here, other, first, last, guid, array_lba, count, width, array_crc = fields
        demand((sig, revision, size, reserved, here, other, first, last, array_lba, count, width) ==
               (b"EFI PART", 0x10000, 92, 0, current, backup, 34, total - 34, entries_lba, 128, 128),
               "gpt_header_geometry")
        header = bytearray(raw[:size])
        header[16:20] = bytes(4)
        demand(zlib.crc32(header) & 0xFFFFFFFF == crc, "gpt_header_crc")
        demand(guid != bytes(16), "gpt_disk_guid")
        array = read_at(stream, array_lba * SECTOR, count * width)
        demand(zlib.crc32(array) & 0xFFFFFFFF == array_crc, "gpt_entries_crc")
        arrays.append(array)
        guids.append(guid)
        headers.append(digest(raw))
    demand(arrays[0] == arrays[1] and guids[0] == guids[1], "gpt_copies_disagree")
    identifiers = []
    for index, (start, sectors, name) in enumerate(PARTITIONS):
        kind, identifier, first, last, flags, label = struct.unpack_from("<16s16sQQQ72s", arrays[0], index * 128)
        demand((kind, first, last, flags, label) ==
               (HFS_TYPE, start, start + sectors - 1, 0, name.encode("utf-16le").ljust(72, b"\0")),
               "gpt_partition_geometry", "p" + str(index + 1))
        demand(identifier != bytes(16), "gpt_partition_guid")
        identifiers.append(identifier)
    demand(identifiers[0] != identifiers[1] and arrays[0][256:] == bytes(len(arrays[0]) - 256),
           "gpt_extra_or_duplicate_partition")
    return {"status": "PASSED", "disk_bytes": disk_bytes, "primary_header_sha256": headers[0],
            "backup_header_sha256": headers[1], "entries_sha256": digest(arrays[0]),
            "partitions": [{"name": n, "start_sector": s, "sectors": c, "bytes": c * SECTOR}
                           for s, c, n in PARTITIONS]}


def fsck_verdict(returncode, output):
    lines = [re.sub(r"^\s*\*\*\s*", "", line).strip() for line in output.splitlines()]
    positives = [i for i, line in enumerate(lines) if re.fullmatch(r"The volume .+ appears to be OK\.", line)]
    forbidden = (r"\b(?:errors?|corrupt(?:ed|ion)?|invalid|repair(?:ed|ing)?|skipped|skipping|modified|"
                 r"failed|failure|cannot|unable|damaged|incomplete)\b|no checking performed|quickcheck|"
                 r"not checked|not clean|could not|non-empty journal|only read [^\n]*bytes from journal|"
                 r"journal[^\n]*(?:replay|dirty)|(?:replay|dirty)[^\n]*journal")
    reasons = []
    if returncode != 0:
        reasons.append("nonzero_exit")
    if len(positives) != 1:
        reasons.append("missing_or_repeated_clean_summary")
    if re.search(forbidden, output, re.I):
        reasons.append("negative_or_skipped_diagnostic")
    # A lone clean-looking footer does not prove that a forced full check ran.
    checked = "\n".join(lines[:positives[0]]) if len(positives) == 1 else ""
    for phase in (r"Checking Extents Overflow file\.", r"Checking Catalog file\.",
                  r"Checking volume bitmap\.", r"Checking volume information\."):
        if re.search(phase, checked, re.I) is None:
            reasons.append("missing_check_phase")
            break
    return {"status": "PASSED" if not reasons else "INCOMPLETE", "exit_code": returncode,
            "diagnostic_sha256": digest(output.encode()), "reasons": reasons}


class Tree:
    """Directory-fd traversal: absolute guest symlinks are never followed."""
    def __init__(self, root):
        self.fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)

    def close(self):
        os.close(self.fd)

    def _parent(self, name):
        parts = name.split("/")
        demand(all(p and p not in (".", "..") for p in parts), "unsafe_tree_path", name)
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

    def open(self, name):
        parent, leaf = self._parent(name)
        try:
            fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            try:
                demand(stat.S_ISREG(os.fstat(fd).st_mode), "not_regular", name)
                return os.fdopen(fd, "rb")
            except BaseException:
                os.close(fd)
                raise
        finally:
            os.close(parent)

    def read(self, name):
        try:
            with self.open(name) as stream:
                data = stream.read(MAX_PLIST + 1)
            demand(len(data) <= MAX_PLIST, "metadata_file_too_large", name)
            return data
        except (OSError, ValueError):
            raise AuditError("metadata_read_failed", name) from None

    def sha(self, name):
        value = hashlib.sha256()
        try:
            with self.open(name) as stream:
                for data in iter(lambda: stream.read(1 << 20), b""):
                    value.update(data)
        except OSError:
            raise AuditError("file_read_failed", name) from None
        return value.hexdigest()

    def inventory(self):
        entries = {}

        def visit(fd, relative):
            demand(len(entries) < MAX_ENTRIES, "too_many_entries")
            st = os.fstat(fd)
            entries[relative] = node(st)
            with os.scandir(fd) as listing:
                names = sorted(item.name for item in listing)
            for name in names:
                path = relative + "/" + name if relative else name
                st = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if stat.S_ISDIR(st.st_mode):
                    child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    try:
                        visit(child, path)
                    finally:
                        os.close(child)
                else:
                    demand(len(entries) < MAX_ENTRIES, "too_many_entries")
                    entries[path] = node(st)
                    if stat.S_ISLNK(st.st_mode):
                        entries[path]["target"] = os.readlink(name, dir_fd=fd)
        try:
            visit(self.fd, "")
        except OSError:
            raise AuditError("tree_walk_failed") from None
        return entries


def node(st):
    return {"type": stat.S_IFMT(st.st_mode), "mode": stat.S_IMODE(st.st_mode), "uid": st.st_uid,
            "gid": st.st_gid, "dev": st.st_dev, "ino": st.st_ino, "rdev": st.st_rdev,
            "bytes": st.st_size}


def typed(value):
    """Exact semantic plist identity, including bool/int/float distinctions."""
    kind = type(value)
    if kind is dict:
        demand(all(type(k) is str for k in value), "non_string_plist_key")
        return ["dict", [[k, typed(value[k])] for k in sorted(value)]]
    if kind is list:
        return ["list", [typed(v) for v in value]]
    if kind is bytes:
        return ["bytes", value.hex()]
    if kind in (str, bool, int, type(None)):
        return [kind.__name__, value]
    if kind is float:
        return ["float", value.hex()]
    if kind is datetime.datetime:
        return ["datetime", value.isoformat()]
    if kind is plistlib.UID:
        return ["uid", value.data]
    raise AuditError("unsupported_plist_type")


def load_dict(tree, entries, name, absent_ok=False):
    if name not in entries:
        demand(absent_ok, "missing_plist", name)
        return {}
    demand(entries[name]["type"] == stat.S_IFREG, "plist_not_regular", name)
    try:
        data = plistlib.loads(tree.read(name))
    except (ValueError, TypeError, OverflowError, plistlib.InvalidFileException):
        raise AuditError("plist_parse_failed", name) from None
    demand(type(data) is dict, "plist_not_dictionary", name)
    typed(data)
    return data


def nested(data, key, path):
    if key not in data:
        data[key] = {}
    demand(type(data[key]) is dict, "plist_nested_type", path)
    return data[key]


def expected_changes(source, entries, labels, build, version):
    files, dirs = {}, {"": (0, 0, 0o755)}

    def directory(name, owner=None, mode=None):
        # Only exact required parents are allowed additions. No subtree waiver.
        parts = name.split("/")
        for end in range(1, len(parts) + 1):
            parent = "/".join(parts[:end])
            if parent not in entries:
                dirs.setdefault(parent, (0, 0, 0o755))
            else:
                demand(entries[parent]["type"] == stat.S_IFDIR, "tweak_parent_type", parent)
        previous = entries.get(name, {"uid": 0, "gid": 0, "mode": 0o755})
        dirs[name] = ((owner if owner is not None else (previous["uid"], previous["gid"])) +
                      (previous["mode"] if mode is None else mode,))

    def change(path, data, uid, gid, mode):
        directory(path.rpartition("/")[0])
        files[path] = {"value": data, "owner_mode": (uid, gid, mode)}

    prefs = "mobile/Library/Preferences"
    updates = {
        "com.apple.migration": {"LastSystemVersion": build,
            "DMUserDataDisposition": {"SyntheticDidUpgrade": False, "buildVersion": build}},
        "com.apple.springboard": {"BKNoWatchdogs": True, "SBMinimumLockscreenIdleTime": 60,
            "FBLaunchWatchdogExceptions": {"com.apple.purplebuddy": 100.0}, "MCForceShowCloudConfigurationUI": False},
        "com.apple.purplebuddy": {"SetupDone": True, "SetupFinishedAllSteps": True, "SetupVersion": 11,
            "daemonizeNeedsToRun": False},
        "com.apple.purplebuddy.notbackedup": {k: False for k in (
            "ShouldRunDiagnosticsMiniBuddy", "ShouldRunHSA2MiniBuddy", "ShouldRunKeychainSyncMiniBuddy",
            "ShouldRunMesaMiniBuddy", "ShouldRunPaymentMiniBuddy", "ShouldRunStandardMiniBuddy", "SilentICDPUpgrade")},
        "com.apple.managedconfiguration.notbackedup": {"LockdownActivationIndicatesCloudConfigurationAvailable": False},
        "com.apple.Accessibility": {"HomeButtonAssistantPreference": 2},
    }
    for name, values in updates.items():
        path = prefs + "/" + name + ".plist"
        data = copy.deepcopy(load_dict(source, entries, path, True))
        data.update(values)
        change(path, data, 501, 501, 0o600)
    directory(prefs, (501, 501))
    profiles = "mobile/Library/UserConfigurationProfiles"
    path = profiles + "/UserSettings.plist"
    data = copy.deepcopy(load_dict(source, entries, path, True))
    nested(data, "restrictedValue", path)["maxInactivity"] = {"value": 300}
    change(path, data, 501, 501, 0o644)
    for suffix in ("EffectiveUserSettings.plist", "PublicInfo/PublicEffectiveUserSettings.plist"):
        path = profiles + "/" + suffix
        if path in entries:
            data = copy.deepcopy(load_dict(source, entries, path))
            nested(nested(data, "restrictedValue", path), "maxInactivity", path)["value"] = 300
            change(path, data, 501, 501, 0o644)
    directory(profiles, (501, 501), 0o755)
    change("keybags/systembag.kb", {"KeyBagKeys": b"SWEET"}, 0, 0, 0o600)
    directory("keybags", (0, 0), 0o700)
    path = "db/com.apple.xpc.launchd/disabled.plist"
    data = copy.deepcopy(load_dict(source, entries, path, True))
    data.update({label: True for label in labels})
    change(path, data, 0, 0, 0o644)
    containers = []
    prefix = "containers/Data/System/"
    suffix = "/.com.apple.mobile_container_manager.metadata.plist"
    for path in sorted(entries):
        if path.startswith(prefix) and path.endswith(suffix) and "/" not in path[len(prefix):-len(suffix)]:
            meta = load_dict(source, entries, path)
            if meta.get("MCMMetadataIdentifier") == "com.apple.mobileactivationd":
                containers.append(path[:-len(suffix)])
    demand(len(containers) <= 1, "ambiguous_activation_container")
    if containers:
        internal = containers[0] + "/Library/internal"
        change(internal + "/data_ark.plist", {"-ActivationState": "Activated", "-BrickState": False,
            "-BuildVersion": build, "-ProductVersion": version, "-DataMigrationCompleted": True,
            "-PreSydroDataMigrationCompleted": True}, 501, 501, 0o600)
        directory(internal, (501, 501), 0o755)
    return files, dirs, bool(containers)


def owner_mode(entry):
    return entry["uid"], entry["gid"], entry["mode"]


def hardlinks(entries):
    groups = {}
    for path, entry in entries.items():
        if entry["type"] == stat.S_IFREG:
            groups.setdefault((entry["dev"], entry["ino"]), []).append(path)
    return sorted(sorted(paths) for paths in groups.values() if len(paths) > 1)


def compare_data(source, destination, labels, build="23G90", version="26.6.2"):
    src, dst = source.inventory(), destination.inventory()
    changed, dirs, activation = expected_changes(source, src, labels, build, version)
    expected_paths = set(src) | set(changed) | set(dirs)
    errors = []

    def fail(code, path=None):
        if len(errors) < 128:
            errors.append({"code": code, **({"path": path} if path is not None else {})})

    for path in sorted(expected_paths - set(dst)):
        fail("missing_data_entry", path)
    for path in sorted(set(dst) - expected_paths):
        fail("unexpected_data_entry", path)
    hashes = hashlib.sha256()
    regular = total = 0
    for path in sorted(expected_paths & set(dst)):
        entry = dst[path]
        if path in changed:
            spec = changed[path]
            if entry["type"] != stat.S_IFREG or owner_mode(entry) != spec["owner_mode"]:
                fail("tweaked_file_metadata", path)
                continue
            try:
                actual = load_dict(destination, dst, path)
                if typed(actual) != typed(spec["value"]):
                    fail("tweaked_plist_semantics", path)
            except AuditError as error:
                fail(error.code, path)
            continue
        if path in dirs:
            if entry["type"] != stat.S_IFDIR or owner_mode(entry) != dirs[path]:
                fail("tweak_directory_metadata", path)
            continue
        old = src[path]
        if (entry["type"], owner_mode(entry)) != (old["type"], owner_mode(old)):
            fail("copied_entry_metadata", path)
            continue
        if old["type"] == stat.S_IFREG:
            left, right = source.sha(path), destination.sha(path)
            regular += 1
            total += old["bytes"]
            if entry["bytes"] != old["bytes"] or left != right:
                fail("copied_file_digest", path)
            hashes.update(json_bytes([path, old["bytes"], left, right]) + b"\n")
        elif old["type"] == stat.S_IFLNK:
            if old["target"] != entry["target"]:
                fail("copied_symlink_target", path)
        elif old["type"] != stat.S_IFDIR and old["rdev"] != entry["rdev"]:
            fail("copied_special_device", path)
    if hardlinks(src) != hardlinks(dst):
        fail("hardlink_equivalence")
    return {"status": "PASSED" if not errors else "INCOMPLETE", "source_entries": len(src),
            "data_entries": len(dst), "checked_unchanged_files": regular, "checked_unchanged_bytes": total,
            "comparison_sha256": hashes.hexdigest(), "validated_tweak_files": len(changed),
            "activation_applicable": activation, "errors": errors,
            "error_limit": 128, "unexplained_entries_allowed": False}


def check_system(root):
    tree = Tree(root)
    try:
        build = version = None
        selected = None
        for name in ("System/Library/CoreServices/SystemVersion.plist",
                     "System/Library/CoreServices/SystemVersion-iOS.plist"):
            try:
                data = tree.read(name)
            except AuditError as error:
                if error.code == "metadata_read_failed":
                    # Only a genuinely absent leaf can select the alternate name.
                    parent, leaf = tree._parent(name)
                    try:
                        try:
                            os.stat(leaf, dir_fd=parent, follow_symlinks=False)
                        except FileNotFoundError:
                            continue
                    finally:
                        os.close(parent)
                raise
            try:
                value = plistlib.loads(data)
            except Exception:
                raise AuditError("system_version_parse") from None
            demand(type(value) is dict, "system_version_type")
            build, version = value.get("ProductBuildVersion"), value.get("ProductVersion")
            selected = name
            break
        demand(type(build) is str and type(version) is str and (build, version) == ("23G90", "26.6.2"),
               "system_version_mismatch")
        demand(tree.read("private/etc/fstab") == FSTAB, "fstab_contents")
        with tree.open("private/etc/fstab") as stream:
            st = os.fstat(stream.fileno())
        return {"status": "PASSED", "build": build, "version": version, "version_path": selected,
                "fstab_sha256": digest(FSTAB), "fstab_owner_mode": [st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)]}
    finally:
        tree.close()


def command(argv, seconds=30):
    try:
        result = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=seconds, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise AuditError("utility_execution_failed", argv[0]) from None
    demand(result.returncode == 0 and len(result.stdout) < 1 << 20 and len(result.stderr) < 1 << 20,
           "utility_nonzero_or_output_limit", argv[0])
    return result.stdout.decode("utf-8", "strict").strip()


def ensure_unmounted(device):
    major_minor = "%d:%d" % (os.major(os.stat(device).st_rdev), os.minor(os.stat(device).st_rdev))
    rows = Path("/proc/self/mountinfo").read_text().splitlines()
    demand(not any(row.split()[2] == major_minor for row in rows), "fsck_volume_mounted")


def loop_command(device, start, sectors):
    return ["losetup", "--read-only", "--find", "--show", "--offset", str(start * SECTOR),
            "--sizelimit", str(sectors * SECTOR), device]


def mount_command(loop, mountpoint):
    return ["mount", "-t", "hfsplus", "-o", "ro,nosuid,nodev,noexec", loop, str(mountpoint)]


def fsck_output_bound():
    resource.setrlimit(resource.RLIMIT_FSIZE, (4 << 20, 4 << 20))


def guest_audit(device, policy, out):
    result = {"schema": 1, "status": "INCOMPLETE", "kind": "ios26_readonly_partition_audit",
              "started_monotonic": time.monotonic(), "errors": [], "cleanup_errors": [],
              "readonly_attachment": False, "fsck": {}, "boot_complete": False, "gpu_path_complete": False,
              "policy_sha256": digest(json_bytes(policy)), "audit_nonce": policy.get("audit_nonce")}
    loops, mounted, trees = [], [], []
    try:
        demand(type(policy) is dict and policy.get("schema") == 1 and
               type(policy.get("trim_labels")) is list and policy["trim_labels"] and
               all(type(x) is str and re.fullmatch(r"[A-Za-z0-9_.-]+", x) for x in policy["trim_labels"]),
               "invalid_authored_policy")
        demand(type(policy.get("audit_nonce")) is str and re.fullmatch(r"[0-9a-f]{32}", policy["audit_nonce"]),
               "missing_audit_nonce")
        real = str(Path(device).resolve(strict=True))
        demand(re.fullmatch(r"/dev/vd[a-z]+", real) and stat.S_ISBLK(os.stat(real).st_mode), "unexpected_disk_device")
        demand(command(["blockdev", "--getro", real]) == "1", "attachment_not_readonly")
        size = int(command(["blockdev", "--getsize64", real]))
        result["readonly_attachment"] = True
        with open(real, "rb", buffering=0) as stream:
            result["gpt"] = verify_gpt(stream, size)
        for index, (start, sectors, name) in enumerate(PARTITIONS):
            loop = command(loop_command(real, start, sectors))
            demand(re.fullmatch(r"/dev/loop[0-9]+", loop), "unexpected_loop_device")
            loops.append(loop)
            demand(command(["blockdev", "--getro", loop]) == "1" and
                   int(command(["blockdev", "--getsize64", loop])) == sectors * SECTOR, "loop_view_not_readonly_exact")
            ensure_unmounted(loop)
            log = out / ("fsck-system.txt" if index == 0 else "fsck-data.txt")
            try:
                with log.open("xb") as stream:
                    checked = subprocess.run(["fsck.hfsplus", "-f", "-n", loop], stdin=subprocess.DEVNULL,
                        stdout=stream, stderr=subprocess.STDOUT, timeout=1200, check=False, preexec_fn=fsck_output_bound)
                demand(log.stat().st_size <= 4 << 20, "fsck_log_limit")
                output = log.read_text(encoding="utf-8", errors="strict")
                result["fsck"][name] = fsck_verdict(checked.returncode, output)
            except subprocess.TimeoutExpired:
                result["fsck"][name] = {"status": "INCOMPLETE", "reasons": ["timeout"]}
        demand(len(result["fsck"]) == 2 and all(v["status"] == "PASSED" for v in result["fsck"].values()),
               "fsck_not_clean")
        for loop, suffix in zip(loops, ("root", "data")):
            target = Path("/tmp/partition-audit-" + suffix)
            target.mkdir(mode=0o700)
            command(mount_command(loop, target))
            mounted.append(target)
            rows = Path("/proc/self/mountinfo").read_text().splitlines()
            matches = [line.split() for line in rows if line.split()[4] == str(target)]
            demand(len(matches) == 1 and "ro" in matches[0][5].split(","), "mount_not_readonly")
        result["system"] = check_system(mounted[0])
        # Open each private/var component with no-follow directory fds.
        system = Tree(mounted[0])
        trees.append(system)
        parent, leaf = system._parent("private/var")
        try:
            source = Tree.__new__(Tree)
            source.fd = os.open(leaf, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        finally:
            os.close(parent)
        trees.append(source)
        target = Tree(mounted[1])
        trees.append(target)
        result["data_copy"] = compare_data(source, target, policy["trim_labels"], result["system"]["build"],
                                           result["system"]["version"])
        demand(result["data_copy"]["status"] == "PASSED", "data_copy_not_exact")
        result["status"] = "PARTITION_AUDIT_PASSED"
    except AuditError as error:
        result["errors"].append(error.record())
    except Exception as error:
        result["errors"].append({"code": "unexpected_exception", "type": type(error).__name__})
    finally:
        for tree in reversed(trees):
            try:
                tree.close()
            except OSError:
                result["cleanup_errors"].append("close_tree")
        for target in reversed(mounted):
            try:
                command(["umount", str(target)])
            except AuditError:
                result["cleanup_errors"].append("unmount")
        for loop in reversed(loops):
            try:
                ensure_unmounted(loop)
                command(["losetup", "--detach", loop])
            except AuditError:
                result["cleanup_errors"].append("detach_loop")
        if result["cleanup_errors"]:
            result["status"] = "INCOMPLETE"
        result["elapsed_seconds"] = time.monotonic() - result.pop("started_monotonic")
    return result


def main():
    # A completed *failed* audit still returns its metadata through job-run's
    # success-only tar channel. The host independently requires the audit pass.
    device, policy_file, output = sys.argv[1:]
    out = Path(output)
    out.mkdir(mode=0o700)
    try:
        policy = json.loads(Path(policy_file).read_text())
        result = guest_audit(device, policy, out)
    except Exception as error:
        result = {"schema": 1, "status": "INCOMPLETE", "errors": [{"code": "audit_setup_failed", "type": type(error).__name__}]}
    (out / "result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print("PARTITION_AUDIT_RESULT " + result["status"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
