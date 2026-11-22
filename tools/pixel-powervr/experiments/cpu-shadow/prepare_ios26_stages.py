"""Declarative port of PhoneSetup26's phone schedule, not the PC manifest schedule.

No commands run at import. Original helper bodies are read from the separately
verified tooling bundle; this module supplies their established files/variables.
All writable disks become fresh attempt-owned disks or overlays in the runner.
"""
from pathlib import PurePosixPath
import re
import shlex


STAGES = (
    "shared-fetch", "shared-unpack", "shared-build", "ios26-fetch", "ios26-decrypt",
    "ios26-rootfs", "ios26-partition", "ios26-firstboot", "ios26-persona",
    "ios26-activation", "ios26-apps", "ios26-gpu", "ios26-wallpaper",
    "ios26-locale", "ios26-pack",
)
NETWORK = {"shared-fetch", "shared-unpack", "ios26-fetch", "ios26-decrypt"}
GUEST_BOOTS = {"ios26-firstboot", "ios26-wallpaper"}
# Conservative per-stage additional GB, including preservation of encrypted
# inputs and predecessor disks. No automatic source reclamation or hole punching.
SPACE_GB = dict(zip(STAGES, (1.1, 1.6, 2.5, 10.3, 11.0, 16.0, 18.5, 3.0,
                            1.0, 1.0, 4.5, 1.5, 4.0, 1.0, 12.0)))


def relative(name):
    path = PurePosixPath(name)
    if (not isinstance(name, str) or not name or str(path) != name or
            path.is_absolute() or any(p in (".", "..") for p in path.parts) or
            any(c in name for c in "\x00\r\n\t") or not re.fullmatch(r"[A-Za-z0-9_./+-]+", name)):
        raise ValueError("invalid logical artifact path: " + repr(name))
    return name


def variables(manifest, locale):
    result = dict(manifest["shared"]["vars"])
    result.update(manifest["os"]["ios26"]["vars"])
    result["TIMEBASE"] = "38400000"
    result["KEEPSAM"] = "0"
    patches = manifest["os"]["ios26"]["dscPatches"]
    for target, source in (("POSTERBOARD", "posterBoard"), ("LOCKLONGPRESS", "lockLongPress"), ("AOD", "aod")):
        result[target] = " ".join(patches[source])
    for i, name in enumerate(patches["files"]):
        result["DSC" + str(i)] = name
    args = ["--tz", locale["timezone"], "--clock", str(locale["clock"])]
    if locale["region"]:
        args += ["--region", locale["region"]]
    result["LOCALE"] = shlex.join(args)
    return result


def fill(text, values):
    for key, value in values.items():
        text = text.replace("{" + key + "}", str(value))
    unknown = re.findall(r"(?<!\$)\{([A-Z][A-Z0-9_]*)\}", text)
    if unknown:
        raise ValueError("unresolved job placeholders: " + ", ".join(sorted(set(unknown))))
    return text


def downloads(manifest, shared):
    if shared:
        source = manifest["shared"]["sources"]["cloudos"]
        known = {r["name"]: r for r in manifest["os"]["ios26"]["sources"]["cloudos"]["members"]}
        members = [dict(known.get(r["name"], {}), **r) for r in source["members"]]
        mapping = [(r, relative("cloudos/" + r["name"])) for r in members]
        files = manifest["shared"]["files"]
        plugin = manifest["shared"]["vars"]["PLUGIN"]
        urls = [(files["sysroot"], "downloads/ios_sysroot.tar.gz"),
                (files["dtFixup"], "tools/qemu-sptm/scripts/darwin/vresearch_dt_fixup.py"),
                (files["gpuPlugin"], relative("downloads/" + plugin))]
    else:
        source = manifest["os"]["ios26"]["sources"]["iphone"]
        mapping = [(r, relative("iphone/" + PurePosixPath(r["name"]).name)) for r in source["members"]]
        urls = []
    return {"source": source, "members": mapping, "urls": urls}


def unpack_operations(manifest, shared):
    v = dict(manifest["shared"]["vars"], **manifest["os"]["ios26"]["vars"])
    if shared:
        return [
            ("im4p", "cloudos/Firmware/all_flash/DeviceTree.vphone600ap.im4p", "cloud/vphone600ap.adt"),
            ("im4p", "cloudos/kernelcache.research.vphone600", "cloud/kernelcache.research.vphone600.decompressed"),
            ("im4p", "cloudos/Firmware/sptm.vresearch1.release.im4p", "fw/sptm"),
            ("im4p", "cloudos/Firmware/txm.iphoneos.research.im4p", "fw/txm"),
            ("im4p", "cloudos/" + v["RAMDISK"], "install/work/rd.apfs"),
            ("aea", "cloudos/" + v["IMG"] + ".aea", "install/work/gpu-img/" + v["IMG"]),
        ]
    return [("aea", "iphone/" + v[key] + ".aea", "os/" + v[key]) for key in ("SYSOS", "OS")]


def job(stage, manifest):
    v = dict(manifest["shared"]["vars"], **manifest["os"]["ios26"]["vars"])
    result = {"name": stage, "disks": [], "files": [], "out": [], "scratch": [], "scratch_bytes": 8 << 30}

    def disk(logical, mode, source=None, at=None, size=None):
        result["disks"].append({"logical": relative(logical), "mode": mode,
                                "source": relative(source or logical), "at": at or logical, "size": size})

    if stage == "shared-build":
        disk("install/work/rd.apfs", "ro", at="/root/ios26/rd/rd.apfs")
        disk("install/work/gpu-img/" + v["IMG"], "ro", at="cloudos/" + v["IMG"])
        result["files"] = ["downloads/ios_sysroot.tar.gz", "cloudos/Firmware/" + v["RAMDISK"] + ".trustcache",
                           "fw/dtree.orig", "cloud/kernelcache.research.vphone600.decompressed", "tools/qemu-sptm",
                           "cloudos/Firmware/" + v["IMG"] + ".aea.trustcache", "downloads/" + v["PLUGIN"]]
        result["out"] = ["rd-shell.hfs", "cloud/rd.trustcache.im4p", "dtree-smp4", "dtree-phone",
                         "dtree-phone-aod", "fw/bootkc", "install/work/gpu"]
    elif stage == "ios26-rootfs":
        disk("os/" + v["OS"], "ro")
        disk("os/" + v["SYSOS"], "ro")
        disk("iphone/" + v["APPOS"], "ro")
        disk("root26.qcow2", "new", size=32 << 30)
        result["files"] = ["downloads/ios_sysroot.tar.gz", "iphone/" + v["OS"] + ".aea.trustcache",
                           "iphone/" + v["SYSOS"] + ".aea.trustcache", "iphone/" + v["APPOS"] + ".trustcache"]
        result["out"] = ["root26.qcow2.hashes", "root26.tc"]
    elif stage == "ios26-partition":
        disk("root26.qcow2", "ro")
        disk("root26g.qcow2", "new", source="root26.qcow2", size="partition")
    elif stage == "ios26-persona":
        disk("root26g.qcow2", "overlay")
    elif stage == "ios26-activation":
        disk("root26-activation.qcow2", "overlay", source="root26g.qcow2")
        result["files"], result["out"] = ["root26.tc"], ["root26-activation.tc"]
    elif stage == "ios26-apps":
        disk("root26-apps.qcow2", "overlay", source="root26-activation.qcow2")
        disk("os/" + v["OS"], "ro")
        result["files"], result["out"] = ["root26-activation.tc"], ["root26-apps.tc"]
        result["scratch"] = ["dsc", "dscpatch", "dscpatch-pb", "dscpatch-lp", "dscpatch-edge", "dscpatch-aod"]
        result["scratch_bytes"] = 12 << 30
    elif stage == "ios26-gpu":
        disk("root26-gpu.qcow2", "overlay", source="root26-apps.qcow2")
        result["files"], result["out"] = ["root26-apps.tc", "install/work/gpu/" + v["BUNDLE"]], ["root26-gpu.tc"]
    elif stage == "ios26-locale":
        disk("root.qcow2", "overlay")
    else:
        raise ValueError("not a helper stage: " + stage)
    for name in result["files"] + result["out"] + result["scratch"]:
        relative(name)
    return result


def boot_inputs(stage):
    if stage == "ios26-firstboot":
        return {"source": "root26g.qcow2", "output": "root26g.qcow2",
                "kernel": "cloud/kernelcache.research.vphone600.decompressed", "tree": "dtree-phone",
                "trustcache": "root26.tc", "settle_seconds": 30, "deadline_seconds": 3600}
    if stage == "ios26-wallpaper":
        return {"source": "root26-gpu.qcow2", "output": "root.qcow2", "kernel": "fw/bootkc",
                "tree": "dtree-phone-aod", "trustcache": "root26-gpu.tc", "settle_seconds": 360,
                "deadline_seconds": 18000}
    raise ValueError("not a guest-boot stage")


PACK_FILES = {
    "root.tc": "root26s-aod.tc", "fw/bootkc": "bootkc", "fw/sptm": "sptm", "fw/txm": "txm",
    "rd-shell.hfs": "rd-shell.hfs", "dtree-phone": "dtree-root26v-smp4-19m2",
    "dtree-phone-aod": "dtree-root26v-smp4-19m2-aod",
}
