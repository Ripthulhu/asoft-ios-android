#!/usr/bin/env python3
"""Small, dependency-free integrity helpers shared with the phone extractor."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import subprocess


APK = {
    "url": "https://github.com/alpersamur3/asoft-ios-android/releases/download/v0.1.6/ASoftware-iOS-Android-0.1.6.apk",
    "bytes": 109357759,
    "sha256": "befbcc1b31d83f166870010300a2a302e3570a7d3622d8de9c02fd896eeaa0cf",
}
ENTRYPOINTS = {
    "qemu_img": "tools/qemu-img", "java_dex": "java/classes.dex",
    "native_unpack": "lib/libunpack.so", "helper_kernel": "helper/Image16k.gz",
    "helper_initrd": "helper/initrd.gz", "setup_manifest": "setup/asoft-setup.json",
}
SYSTEM_LIBS = {"libc.so", "libm.so", "libdl.so", "libz.so", "liblog.so", "libandroid.so"}
LIBRARIES = (
    "libandroid-support.so", "libbz2.so.1.0", "libcrypto.so.3", "libcurl.so",
    "libffi.so", "libglib-2.0.so.0", "libgmp.so", "libgnutls.so",
    "libhogweed.so.6", "libiconv.so", "libidn2.so", "libnettle.so.8",
    "libnghttp2.so", "libnghttp3.so", "libngtcp2.so", "libngtcp2_crypto_ossl.so",
    "libp11-kit.so", "libpcre2-8.so", "libssh2.so", "libssl.so.3",
    "libtasn1.so", "libunistring.so", "libz.so.1", "libzstd.so.1",
)
PHONE_FILES = (
    "adhoc.py", "autolock.py", "gestalt.py", "ipa-hashes.py", "ipa-place.py", "locale.py",
    "prelude.sh", "jobs/ios26-activation.sh", "jobs/ios26-apps.sh", "jobs/ios26-gpu.sh",
    "jobs/ios26-ipa.sh", "jobs/ios26-locale.sh", "jobs/ios26-partition.sh",
    "jobs/ios26-persona.sh", "jobs/ios26-rootfs.sh", "jobs/ios26-screen.sh", "jobs/shared-build.sh",
)
PAYLOAD_NAMES = {"setup/phone/" + name for name in PHONE_FILES} | {
    "setup/asoft-setup.json", "java/classes.dex", "java/build.json", "lib/libunpack.so", "lib/unpack-build.json",
}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def entry(path, mode=False):
    info = Path(path).lstat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("not a regular file: " + str(path))
    result = {"bytes": info.st_size, "sha256": sha(path)}
    if mode:
        result["mode"] = stat.S_IMODE(info.st_mode)
    return result


def matches(path, record, mode=False):
    expected = {key: record[key] for key in ("bytes", "sha256")}
    if mode:
        expected["mode"] = record["mode"]
    return entry(path, mode) == expected


def relpath(name):
    if (not isinstance(name, str) or not name or "\\" in name or "\x00" in name
            or any(ord(char) < 32 for char in name)):
        raise ValueError("invalid relative path")
    path = PurePosixPath(name)
    if path.is_absolute() or path.as_posix() != name or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError("unsafe relative path: " + name)
    return name


def regular_under(root, name):
    """Refuse symlinks in any input component, including the final component."""
    relpath(name)
    current = Path(root)
    for component in PurePosixPath(name).parts:
        current /= component
        if current.is_symlink():
            raise ValueError("symlink input: " + str(current))
    if not stat.S_ISREG(current.lstat().st_mode):
        raise ValueError("input is not a regular file: " + str(current))
    return current


def record_valid(record):
    if (type(record.get("bytes")) is not int or record["bytes"] < 0
            or not isinstance(record.get("sha256"), str)
            or re.fullmatch(r"[0-9a-f]{64}", record["sha256"]) is None
            or type(record.get("mode")) is not int or record["mode"] not in (0o444, 0o644, 0o755)):
        raise ValueError("invalid file identity")


def load_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=unique)


def write_json(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def elf_info(data):
    """Parse just ELF64 LE load/dynamic metadata; execute no target code."""
    if len(data) < 64 or data[:7] != b"\x7fELF\x02\x01\x01":
        raise ValueError("expected ELF64 little-endian")
    header = struct.unpack_from("<16sHHIQQQIHHHHHH", data)
    if header[1:3] != (3, 183) or header[9] != 56 or not 1 <= header[10] <= 128:
        raise ValueError("expected AArch64 ET_DYN with standard program headers")
    offset, size, count = header[5], header[9], header[10]
    if offset + size * count > len(data):
        raise ValueError("truncated ELF program headers")
    segments = [struct.unpack_from("<IIQQQQQQ", data, offset + i * size) for i in range(count)]
    for segment in segments:
        if segment[2] + segment[5] > len(data):
            raise ValueError("ELF segment exceeds file")
    loads = [segment for segment in segments if segment[0] == 1]
    if not loads or any(p[7] < 16384 or p[2] % 16384 != p[3] % 16384 for p in loads):
        raise ValueError("ELF requires congruent 16 KiB LOAD segments")
    dynamic = [segment for segment in segments if segment[0] == 2]
    if len(dynamic) != 1:
        raise ValueError("expected exactly one ELF dynamic table")
    values = {}
    table = dynamic[0]
    terminated = False
    for position in range(table[2], table[2] + table[5] - 15, 16):
        tag, value = struct.unpack_from("<qQ", data, position)
        if tag == 0:
            terminated = True
            break
        values.setdefault(tag, []).append(value)
    if not terminated or len(values.get(5, [])) != 1 or len(values.get(10, [])) != 1:
        raise ValueError("malformed ELF dynamic string table")
    address, length = values[5][0], values[10][0]
    holders = [p for p in loads if p[3] <= address and address + length <= p[3] + p[5]]
    if len(holders) != 1:
        raise ValueError("ELF dynamic strings are not file-backed")
    strings_at = holders[0][2] + address - holders[0][3]
    strings = data[strings_at:strings_at + length]
    def string(index):
        if index >= len(strings) or b"\0" not in strings[index:]:
            raise ValueError("invalid ELF string index")
        return strings[index:strings.index(b"\0", index)].decode("ascii")
    interpreters = [p for p in segments if p[0] == 3]
    if len(interpreters) > 1:
        raise ValueError("multiple ELF interpreters")
    interpreter = None
    if interpreters:
        p = interpreters[0]
        raw = data[p[2]:p[2] + p[5]]
        if not raw.endswith(b"\0"):
            raise ValueError("unterminated ELF interpreter")
        interpreter = raw[:-1].decode("ascii")
    sonames = values.get(14, [])
    if len(sonames) > 1:
        raise ValueError("multiple ELF SONAMEs")
    needed = [string(index) for index in values.get(1, [])]
    if len(needed) != len(set(needed)) or any("/" in name or not name for name in needed):
        raise ValueError("invalid ELF dependency name")
    return {"machine": "AArch64", "type": "DYN", "needed": needed,
            "soname": string(sonames[0]) if sonames else None,
            "interpreter": interpreter,
            "runpath": [string(index) for index in values.get(29, [])],
            "rpath": [string(index) for index in values.get(15, [])],
            "minimum_load_alignment": min(p[7] for p in loads)}


def dependency_closure(root):
    names = ["tools/qemu-img", "lib/libunpack.so"] + ["lib/" + name for name in LIBRARIES]
    details = {name: elf_info(regular_under(root, name).read_bytes()) for name in names}
    if details["tools/qemu-img"]["interpreter"] != "/system/bin/linker64":
        raise ValueError("qemu-img must use Android's 64-bit linker")
    available = set(LIBRARIES) | {"libunpack.so"}
    reached = set()
    pending = ["tools/qemu-img", "lib/libunpack.so"]
    while pending:
        name = pending.pop()
        if name in reached:
            continue
        reached.add(name)
        info = details[name]
        if name.startswith("lib/") and info["soname"] not in (None, name[4:]):
            raise ValueError("library name disagrees with SONAME: " + name)
        for needed in info["needed"]:
            if needed in SYSTEM_LIBS:
                continue
            if needed not in available:
                raise ValueError("missing non-system dependency: " + needed)
            pending.append("lib/" + needed)
    if reached != set(names):
        raise ValueError("bundle contains libraries outside the complete dependency closure")
    return {"system_libraries": sorted(SYSTEM_LIBS), "elf": details,
            "library_path": "lib", "requires_explicit_ld_library_path": True}


def git(source, *arguments):
    return subprocess.check_output(["git", "--no-optional-locks", "-C", str(source), *arguments],
                                   env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})


def source_snapshot(source, names):
    source = Path(source)
    head = git(source, "rev-parse", "HEAD").decode().strip()
    files = {}
    for name in sorted(set(names)):
        path = regular_under(source, name)
        tree_record = git(source, "ls-tree", "-z", head, "--", relpath(name)).split(b"\0")
        if len(tree_record) != 2 or not tree_record[0]:
            raise ValueError("source path is not one committed regular file: " + name)
        metadata, committed_name = tree_record[0].split(b"\t", 1)
        mode, kind, _ = metadata.split()
        if mode not in (b"100644", b"100755") or kind != b"blob" or committed_name.decode() != name:
            raise ValueError("source input has an unsafe Git mode: " + name)
        committed = git(source, "cat-file", "blob", head + ":" + relpath(name))
        actual = entry(path)
        if actual != {"bytes": len(committed), "sha256": hashlib.sha256(committed).hexdigest()}:
            raise ValueError("input differs from committed source: " + name)
        files[name] = {**actual, "git_blob": git(source, "rev-parse", head + ":" + name).decode().strip()}
    return {"commit": head, "tree": git(source, "rev-parse", head + "^{tree}").decode().strip(),
            "files": files}
