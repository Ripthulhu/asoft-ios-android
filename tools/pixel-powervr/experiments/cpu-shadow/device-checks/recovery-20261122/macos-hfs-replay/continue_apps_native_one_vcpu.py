#!/usr/bin/env python3
"""Retry the read-only native app audit after a multi-vCPU stub crash."""
import json
from pathlib import Path
import types

BASE = Path("/data/local/tmp")
CONTROL = BASE / "asoft-recovered-control-01"
FAILED = BASE / "asoft-continue-04"


def checked_source(path, digest):
    import hashlib
    body = path.read_bytes()
    if path.resolve(strict=True) != path or hashlib.sha256(body).hexdigest() != digest:
        raise ValueError("changed prior evidence or source: " + str(path))
    return body


def main():
    source = CONTROL / "continue_apps_with_apfs_proof.py"
    apfs = types.ModuleType("source_bound_retry")
    apfs.__file__ = str(source)
    exec(compile(checked_source(source, "fa17b8ef1e14093e37ab38db2e61fe88bca93753b160775825ab37336c11e06d"),
                 str(source), "exec"), vars(apfs))
    finished = json.loads(checked_source(FAILED / "result.json",
        "4a79e599d45064a4065f49dd2820f260b710d0661d94099c5a0cd5eb444bfcb8"))
    observed = json.loads(checked_source(FAILED / "apps-audit/vm-result.json",
        "756acbe7bc77a1770aee3fe5f2f0a937c9f8817292a29c31116a2161d9766735"))
    log = checked_source(FAILED / "apps-audit/qemu-stderr.txt",
        "9c0f8b63c624696e3402b8b1f57b30cb4d16c82d2b8c0956312ba80670f0c0be")
    apfs.require(finished["status"] == "INCOMPLETE" and observed["natural_exit"] and
                 observed["cleanup"]["exit_code"] == -6 and observed["cleanup"]["echild"] and
                 not observed["cleanup"]["forced_qemu"] and not observed["cleanup"]["forced_descendants"] and
                 b"off the alt stack" in log and b"died while running vCPU" in log,
                 "previous native stub crash was not reproduced by the pinned evidence")

    original_once = apfs.once

    def once(code, old, new):
        if new == 'WORK = BASE / "asoft-continue-04"':
            new = 'WORK = BASE / "asoft-continue-05"'
        return original_once(code, old, new)

    original_driver = apfs.mount_bound_driver

    def driver_with_one_audit_vcpu():
        driver = original_driver()
        apfs.require(set(finished["stages"]) == set(driver.STAGES), "unexpected prior stage inventory")
        original_load = driver.load

        def load(path, digest):
            module = original_load(path, digest)
            if path != driver.GUARD:
                return module
            original_frozen = module.load_frozen

            def load_frozen(*args):
                prepare = original_frozen(*args)
                original_helper = prepare.helper_command

                def helper(plan, attempt, disks):
                    if attempt != driver.WORK / "apps-audit":
                        return original_helper(plan, attempt, disks)
                    audit_plan = dict(plan)
                    audit_plan["session"] = dict(plan["session"], helper_vcpus=1)
                    argv, env = original_helper(audit_plan, attempt, disks)
                    apfs.require(env["ASOFT_NATIVE_EL0"] == env["ASOFT_NATIVE_EL0_REQUIRED"] == "1",
                                 "native EL0 must stay required")
                    env["ASOFT_NATIVE_EL0_STUBS"] = "2"
                    return argv, env

                prepare.helper_command = helper
                return prepare

            module.load_frozen = load_frozen
            return module

        driver.load = load
        return driver

    apfs.once = once
    apfs.mount_bound_driver = driver_with_one_audit_vcpu
    return apfs.main()


if __name__ == "__main__":
    raise SystemExit(main())
