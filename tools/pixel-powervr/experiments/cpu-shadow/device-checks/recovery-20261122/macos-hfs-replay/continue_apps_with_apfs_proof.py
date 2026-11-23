#!/usr/bin/env python3
"""Use the physically observed APFS-FUSE source identity in the read-only app audit."""
import hashlib
import json
from pathlib import Path
import types

BASE = Path("/data/local/tmp")
CONTROL = BASE / "asoft-recovered-control-01"
ID_WORK = BASE / "asoft-apfs-identity-01"
ID_PIN = "597409bf6c88cf49e7a4e5e8aa1542da1e2673e721a12e276d148511002371c9"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def exact(path, pin):
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == pin and path.resolve(strict=True) == path,
            "changed pinned source or result: " + str(path))
    return raw.decode("utf-8")


def once(source, original, updated):
    require(source.count(original) == 1, "source adapter no longer matches exactly")
    return source.replace(original, updated)


def module(name, path, body):
    out = types.ModuleType(name)
    out.__file__ = str(path)
    exec(compile(body, str(path), "exec"), vars(out))
    return out


def verify_mount_probe():
    row = json.loads(exact(ID_WORK / "files/mount-identity.json", ID_PIN))
    result = json.loads((ID_WORK / "vm-result.json").read_bytes())
    cleanup = result["cleanup"]
    require(row["type"] == "fuse" and row["source_is_image_alias"] is True and
            row["source_is_attached_block"] is False and row["root"] == "/" and
            {"ro", "nosuid", "nodev", "noexec"} <= set(row["options"]) and
            result["status"] == "VM_OBSERVATION_COMPLETE" and result["natural_exit"] and
            result["witnesses"]["native_svc_final"] and cleanup["echild"] and
            not cleanup["forced_qemu"] and not cleanup["forced_descendants"] and not cleanup["errors"],
            "APFS source-identity probe wasn't accepted")


def mount_bound_driver():
    source = CONTROL / "continue_recovered_chain_grace.py"
    driver_code = exact(source, "6de8efcdcf93d6b9de4a357f696d0ad3ad6ca81a435e19f0b563650c41a7029b")
    driver_code = once(driver_code, "guest_path.read_bytes()", "guest.BOUND_SOURCE")
    driver = module("bound_preparation_with_apfs", source, driver_code)
    original_load = driver.load

    def load(path, digest):
        if path.parent != driver.APP_SOURCE:
            return original_load(path, digest)
        body = exact(path, digest)
        if path.name == "audit_ios26_apps_guest.py":
            body = once(body,
                'need(row["type"] in ("fuse", "fuse.apfs-fuse") and row["source"] == "apfs-fuse", "apfs_mount_identity")',
                '''alias = target.parent / "source.dmg"
        need(row["type"] == "fuse" and row["source"] == str(alias) and alias.is_symlink() and
             alias.resolve(strict=True) == Path(loop) and stat.S_ISBLK(os.stat(loop).st_mode),
             "apfs_mount_identity")
        row["image_alias_resolves_to_attached_source"] = True''')
            body = once(body, 'readonly_mount(target, "apfs")',
                               'readonly_mount(target, "apfs", devices["os"])')
        elif path.name == "audit_ios26_apps.py":
            body = once(body,
                'row.get("type") not in ("fuse", "fuse.apfs-fuse") or row.get("source") != "apfs-fuse"',
                '''row.get("type") != "fuse" or row.get("image_alias_resolves_to_attached_source") is not True or
                                    not re.fullmatch(r"/tmp/apps-audit-[A-Za-z0-9_-]+/source\\.dmg", row.get("source", ""))''')
        else:
            raise ValueError("unexpected app audit source")
        loaded = module("bound_" + path.stem, path, body)
        loaded.BOUND_SOURCE = body.encode("utf-8")
        return loaded

    driver.load = load
    return driver


def main():
    verify_mount_probe()
    previous = CONTROL / "continue_apps_with_root_proof.py"
    body = exact(previous, "0d5ed9798d8713a329bdb1cb215feb1fb91449dea6be0b43ffb0d45b7373a77f")
    body = once(body, 'PREVIOUS = BASE / "asoft-continue-02"', 'PREVIOUS = BASE / "asoft-continue-03"')
    body = once(body, 'WORK = BASE / "asoft-continue-03"', 'WORK = BASE / "asoft-continue-04"')
    body = once(body, '"code": "volume_not_journaled_or_inconsistent"', '"code": "apfs_mount_identity"')
    body = once(body, 'path.is_relative_to(PREVIOUS)', 'path.is_relative_to(BASE / "asoft-continue-02")')
    retry = module("bound_apfs_identity_retry", previous, body)
    retry.load_driver = mount_bound_driver
    return retry.main()


if __name__ == "__main__":
    raise SystemExit(main())
