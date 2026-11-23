#!/usr/bin/env python3
"""Test the recovered iOS wallpaper boot with the app's 2x display size."""
import hashlib
import inspect
import json
import os
from pathlib import Path
import struct
import sys
import time
import types

BASE = Path("/data/local/tmp")
CONTROL = BASE / "asoft-recovered-control-01"
RECOVERY = BASE / "asoft-data-copy-recovery-gpu06"
AUDIT = BASE / "asoft-gpu-resume-input-audit-07"
LAYERS = (
    RECOVERY / "recovered.qcow2",
    BASE / "asoft-recovered-gpu-boot-06/files/root.qcow2",
    BASE / "asoft-data-copy-recovery-gpu05/recovered.qcow2",
    BASE / "asoft-recovered-gpu-boot-05/files/root.qcow2",
)
WIDTH, HEIGHT = 786, 1704


def need(ok, msg):
    if not ok:
        raise ValueError(msg)


def read(path):
    return json.loads(path.read_bytes())


def load(path, pin):
    code = path.read_bytes()
    need(path.resolve(strict=True) == path and hashlib.sha256(code).hexdigest() == pin,
         "pinned source changed: " + path.name)
    return code


def bind(path, code, **extras):
    module = types.ModuleType("bound_" + path.stem)
    module.__file__ = str(path)
    vars(module).update(extras)
    exec(compile(code, str(path), "exec"), vars(module))
    return module


def adapt_once(body, before, after):
    need(body.count(before) == 1, "display adapter mismatch")
    return body.replace(before, after)


def proof():
    manifest = read(RECOVERY / "manifest.json")
    audit_session = read(AUDIT / "inspection-session.json")
    audit = read(AUDIT / "result.json")
    summary = audit["guest_result"]
    need(manifest["status"] == "RECOVERED_DATA_COPY_VERIFIED" and
         audit_session["recovered_wallpaper_sha256"] == manifest["new_overlay_sha256"] and
         audit_session["portable_recovery_manifest_sha256"] ==
         hashlib.sha256((RECOVERY / "manifest.json").read_bytes()).hexdigest() and
         audit["status"] == "SAVED_FIRSTBOOT_INSPECTION_PASSED" and
         audit["full_backing_chain_unchanged"] and audit["natural_exit"] and
         summary["raw_metadata_unchanged"] and summary["readonly_attachments"] and
         all(summary["fsck"][v]["status"] == summary["journals"][v]["status"] == "PASSED"
             for v in ("iOSRoot", "Data")), "the recovered display-test disk hasn't passed")
    return manifest["new_overlay_sha256"]


def scale_tree(cold, image):
    props = [v["display-scale"] for k, v in cold.tree_properties(image).items()
             if k.rsplit("/", 1)[-1] == "chosen" and "display-scale" in v]
    need(len(props) == 1 and props[0][1] == 4, "unexpected ADT scale property")
    position, _ = props[0]
    need(struct.unpack_from("<I", image, position)[0] == 3, "expected the original 3x tree")
    return image[:position] + struct.pack("<I", 2) + image[position+4:]


def patch_launch(prep, plan, paths, logical):
    digest = proof()
    chain = prep.cold.qcow_chain(LAYERS[0])
    need([r["path"] for r in chain] == [*map(str, LAYERS), *plan["artifacts"][logical]["backing_chain"]] and
         prep.cold.sha(LAYERS[0]) == digest, "the accepted recovery changed")
    paths[logical] = LAYERS[0]
    plan["artifacts"][logical] = {"path": str(LAYERS[0]), "sha256": digest,
                                 "backing_chain": [r["path"] for r in chain]}

    def display_tree(input_tree, launch_tree):
        expected_3x = prep.cold.expected_tree(input_tree.read_bytes(), 3, 3)
        actual = launch_tree.read_bytes()
        need(actual == expected_3x, "unexpected original tree edits")
        two_x = scale_tree(prep.cold, actual)
        need(two_x == prep.cold.expected_tree(scale_tree(prep.cold, input_tree.read_bytes()), 3, 2),
             "unexpected 2x tree edits")
        launch_tree.write_bytes(two_x)

    stage = inspect.getsource(prep.guest_stage)
    for old, new in (("[1179, 2556]", "[786, 1704]"),
                     ("(attempt / \"cache\").mkdir()", 'display_tree(dt, attempt / "device-tree")\n    (attempt / "cache").mkdir()')):
        stage = adapt_once(stage, old, new)
    need(stage.count("1179 * 2556 * 4") == 2, "unexpected memfd geometry")
    stage = stage.replace("1179 * 2556 * 4", "786 * 1704 * 4")
    sampler = inspect.getsource(prep.supervise_vm)
    need(sampler.count("1179, 2556") == 2, "unexpected capture geometry")
    sampler = sampler.replace("1179, 2556", "786, 1704")
    # Rebind before the new stage is built so it sees the amended supervisor.
    sampler_globals = dict(vars(prep))
    exec(compile(sampler, prep.__file__, "exec"), sampler_globals)
    prep.supervise_vm = sampler_globals["supervise_vm"]
    stage_globals = dict(vars(prep), display_tree=display_tree)
    exec(compile(stage, prep.__file__, "exec"), stage_globals)
    prep.guest_stage = stage_globals["guest_stage"]

    original_command = prep.cold.command

    def command(launch, fd):
        deadline = time.monotonic() + 600
        while prep.mem_available_mib() < 5120:
            need(time.monotonic() < deadline, "five GiB of Android launch headroom unavailable")
            time.sleep(5)
        argv, env = original_command(launch, fd)
        need(launch["frame_size"] == [WIDTH, HEIGHT] and env["ASOFT_NATIVE_EL0_REQUIRED"] == "1",
             "native launch or selected framebuffer differs")
        env["ASOFT_NATIVE_EL0_STUBS"] = "12"
        print(json.dumps({"launch_mem_available_mib": prep.mem_available_mib(),
                          "native_stub_limit": 12, "frame_size": [WIDTH, HEIGHT]}), flush=True)
        return argv, env

    prep.cold.command = command


def main():
    need(sys.argv[1:] == ["--execute", "--after-preparation-pid", "29017"] and
         sys.flags.isolated and sys.dont_write_bytecode and os.geteuid() == 0,
         "requires root Python -I -B and explicit --execute")
    audit_path = CONTROL / "inspect_checkpoint_gpu07.py"
    adapter = bind(audit_path, load(audit_path,
                   "f9a21b59dac91c58cbf7becc8f12c7ffd9afea9cf784d610d5cba785c3129ba7"))
    retained_path = CONTROL / "inspect_recovered_gpu_boot_05.py"
    waiter = adapter.module(retained_path, adapter.load(retained_path,
                            "63bf97d0e939b081308940352ce76e7ecc3be2602600d4e74e6089048fb2cf81"))
    waiter.wait_for(27046)
    proof()
    source = CONTROL / "boot_recovered_gpu_05.py"
    body = load(source, "e9ef8a3663c6c6969955abd436f14ef5f81418d85046d9db0625a794d57edb81").decode()
    body = adapt_once(body, 'BOOT = BASE / "asoft-recovered-gpu-boot-05"',
                           'BOOT = BASE / "asoft-recovered-gpu-boot-07"')
    body = adapt_once(body, '        cfg = prep.stages.boot_inputs("ios26-wallpaper")',
                           '        cfg = prep.stages.boot_inputs("ios26-wallpaper")\n'
                           '        patch_launch(prep, plan, paths, cfg["source"])')
    return bind(source, body, patch_launch=patch_launch).main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"status": "REFUSED", "error": type(error).__name__ + ": " + str(error)}), flush=True)
        raise SystemExit(2)
