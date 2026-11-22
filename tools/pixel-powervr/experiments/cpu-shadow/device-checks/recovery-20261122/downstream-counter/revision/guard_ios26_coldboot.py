#!/usr/bin/env python3
"""Separate final cold-boot provenance and host-memory guard.

Default planning starts nothing and writes nothing. The frozen cold owner
retains its command, supervision, frame descriptor and ordered cleanup. This
wrapper adds exact preparation/evidence bindings and narrow memory hooks.
"""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import sys
import types


STAGE = "ios26-pack"
STAGES = ("shared-fetch", "shared-unpack", "shared-build", "ios26-fetch", "ios26-decrypt",
          "ios26-rootfs", "ios26-partition", "ios26-firstboot", "ios26-persona", "ios26-activation",
          "ios26-apps", "ios26-gpu", "ios26-wallpaper", "ios26-locale", STAGE)
RAM_GIB = 3
PRELAUNCH_MIB = 3840
RUNNING_MIB = 512
COLD_SHA256 = "6a57ed164864eef20aeffd34b14b675a8ac597c20583c9f179414a36b4ccbdeb"
DT_SHA256 = "6931310e1318a6397ee2d7eead966bd0fcdeaae9c10038ca2f2aa01de1a45f7e"
WALLPAPER_SOURCES = {
    "guard_ios26_wallpaper.py": "e563fcc7425187c9f0079ecbe206f01e5c4be69168a6937aaefd22283a98262f",
    "inspect_ios26_wallpaper.py": "df7400ccbe03c3882cd3afcb2ecf892ffde635a2773480192354347320033c99",
    "inspect_ios26_wallpaper_guest.py": "0b3f83d3dd7fd74b0c1ee9008c90b874b237b0a8e818fca70e71ab67a19f1b1b",
}
PACK_FILES = {"root.tc": "root26s-aod.tc", "fw/bootkc": "bootkc", "fw/sptm": "sptm", "fw/txm": "txm",
              "rd-shell.hfs": "rd-shell.hfs", "dtree-phone": "dtree-root26v-smp4-19m2",
              "dtree-phone-aod": "dtree-root26v-smp4-19m2-aod"}
DISK_BYTES = 51_541_704_704
NO_BOOT = {"boot_complete": False, "gpu_path_complete": False, "app_gate_changed": False}


def sha(body):
    return hashlib.sha256(body).hexdigest()


def canonical(value, exists=True):
    path = Path(value).absolute()
    if path != path.resolve(strict=exists) or any(c in str(path) for c in ",\r\n\x00"):
        raise ValueError("noncanonical or unsupported path")
    return path


def read(path, limit=4 << 20):
    path = canonical(path)
    if not stat.S_ISREG(path.lstat().st_mode) or path.stat().st_size > limit:
        raise ValueError("nonregular or oversized source/metadata file")
    return path.read_bytes()


def module_from(body, path):
    module = types.ModuleType("bound_" + Path(path).stem)
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def approved_module(path, expected):
    path = canonical(path)
    body = read(path)
    if sha(body) != expected:
        raise ValueError("unreviewed prerequisite source: " + path.name)
    return module_from(body, path), body


def checkpoint_inventory(prep, work, session):
    """Exactly through-pack; old proof consumers receive reconstructed prefixes."""
    expected = list(STAGES)
    if tuple(prep.stages.STAGES) != STAGES:
        raise ValueError("frozen preparation stage order changed")
    if {p.name for p in (work / "checkpoints").iterdir()} != {name + ".json" for name in expected}:
        raise ValueError("final cold boot requires exactly the completed through-pack boundary")
    rows, hashes, artifacts, prior, previous = {}, {}, {}, {}, None
    for name in expected:
        path = work / "checkpoints" / (name + ".json")
        body = read(path)
        row = json.loads(body)
        if (row.get("schema") != 1 or row.get("status") != "STAGE_COMPLETE" or row.get("stage") != name or
                row.get("session_sha256") != prep.digest(session) or row.get("previous_sha256") != previous or
                type(row.get("artifacts")) is not dict):
            raise ValueError("invalid through-pack checkpoint chain")
        for logical, record in row["artifacts"].items():
            prep.stages.relative(logical)
            prep.stages.relative(record["path"])
        artifacts.update(row["artifacts"])
        if name != STAGE:
            prior.update(row["artifacts"])
        rows[name], hashes[str(path)] = row, sha(body)
        previous = hashes[str(path)]
    return {"completed": expected, "rows": rows, "hashes": hashes, "artifacts": artifacts, "prior": prior}


def packed_inputs(prep, work, inventory, wallpaper_chain):
    """Full actual bytes for the standalone pack and each retained predecessor."""
    if prep.stages.PACK_FILES != PACK_FILES or len(wallpaper_chain) != 7:
        raise ValueError("reviewed final pack or wallpaper ancestry changed")
    locale = inventory["rows"]["ios26-locale"]["artifacts"]
    if set(locale) != {"root.qcow2"}:
        raise ValueError("locale checkpoint has unexpected outputs")
    packed = inventory["rows"][STAGE]["artifacts"]
    names = {"ios26/" + name for name in PACK_FILES.values()} | {"ios26/root26s-aod.qcow2", "ios26/install.json"}
    if set(packed) != names:
        raise ValueError("packed assets are missing or have unexpected entries")
    disk = canonical(prep.contained(work, packed["ios26/root26s-aod.qcow2"]["path"]))
    assets = disk.parent
    attempt = canonical(inventory["rows"][STAGE].get("attempt", ""))
    if attempt.parent != work / "attempts" or not re.fullmatch(r"14-\d{4}", attempt.name) or assets != attempt / "files/ios26":
        raise ValueError("packed assets are outside the original owned pack attempt")
    if ({p.name for p in assets.iterdir()} != {Path(name).name for name in names} or
            any(not stat.S_ISREG(p.lstat().st_mode) or p.stat().st_nlink != 1 for p in assets.iterdir())):
        raise ValueError("packed asset directory must contain only its nine ordinary unlinked files")
    files, bindings = {}, {}

    def bind(record):
        path = canonical(prep.contained(work, record["path"]))
        before = prep.cold.readonly_identity(path)
        actual = prep.file_record(path, work)
        if actual != record or prep.cold.readonly_identity(path) != before:
            raise ValueError("complete packed/predecessor bytes or identity changed")
        binding = {"identity": before, "record": actual}
        if str(path) in bindings and bindings[str(path)] != binding:
            raise ValueError("one input path has conflicting identities")
        bindings[str(path)] = binding
        return path, binding

    for logical, record in packed.items():
        path, binding = bind(record)
        if path != assets / Path(logical).name:
            raise ValueError("pack record redirects outside its declared asset layout")
        files[logical] = binding
    for logical, name in PACK_FILES.items():
        record = inventory["prior"][logical]
        bind(record)
        copied = packed["ios26/" + name]
        if (record["bytes"], record["sha256"]) != (copied["bytes"], copied["sha256"]):
            raise ValueError("packed firmware/tree/trustcache differs from its prepared source")
    info = json.loads(read(assets / "install.json"))
    session = json.loads(read(work / "session.json"))
    if (info.get("format") != 1 or info.get("what") != "ios26" or info.get("build") != "23G90" or
            info.get("prepared_by") != "standalone native-required stages" or
            info.get("session_sha256") != prep.digest(session) or any(info.get(k) is not v for k, v in NO_BOOT.items())):
        raise ValueError("packed install identity differs from the completed preparation")
    locale_path, locale_binding = bind(locale["root.qcow2"])
    expected_chain = [str(locale_path), *[item["identity"]["path"] for item in wallpaper_chain]]
    if (len(expected_chain) != len(set(expected_chain)) or
            [item["path"] for item in prep.cold.qcow_chain(locale_path)] != expected_chain or
            locale["root.qcow2"].get("backing_chain") != [str(Path(p).relative_to(work)) for p in expected_chain]):
        raise ValueError("actual locale backing chain differs from the guarded wallpaper ancestry")
    if [item["path"] for item in prep.cold.qcow_chain(disk)] != [str(disk)] or packed["ios26/root26s-aod.qcow2"].get("backing_chain") != [str(disk.relative_to(work))]:
        raise ValueError("final packed disk must be standalone with no retained backing")
    for row in [locale_binding, files["ios26/root26s-aod.qcow2"], *wallpaper_chain]:
        path, actual = bind(row["record"])
        if actual != row:
            raise ValueError("retained disk identity changed during full binding")
        with path.open("rb") as stream:
            header = stream.read(32)
        if len(header) != 32 or struct.unpack_from(">Q", header, 24)[0] != DISK_BYTES:
            raise ValueError("packed or retained disk virtual geometry changed")
    return {"assets": str(assets), "files": files, "locale_chain": [locale_binding, *wallpaper_chain],
            "packed_disk": files["ios26/root26s-aod.qcow2"], "bindings": bindings}


def wallpaper_inspection_acceptance(state, inspection_work, receipt, result, guard_files):
    """Validate the saved wallpaper proof at its own prefix, never through-pack."""
    prep, inspector, guard = state["prep"], state["wallpaper_inspector"], state["wallpaper_guard"]
    session, inventory = state["plan"]["session"], state["wallpaper_inventory"]
    source_dir = canonical(receipt["source_directory"])
    sources = {name: WALLPAPER_SOURCES[name] for name in inspector.SOURCES}
    dependencies = {str(state["raw_source"]): inspector.RAW_SHA256,
                    str(state["partition_source"]): inspector.PARTITION_SHA256,
                    str(state["wallpaper_guard_source"]): WALLPAPER_SOURCES["guard_ios26_wallpaper.py"]}
    if (receipt.get("schema") != 1 or receipt.get("kind") != "ios26_saved_wallpaper_inspection" or
            receipt.get("prep_work") != str(state["prep_work"]) or receipt.get("runner_dir") != str(state["runner"]) or
            receipt.get("prep_session_sha256") != sha(read(state["prep_work"] / "session.json")) or
            receipt.get("frozen_sources") != session["runner_sources"] or
            receipt.get("guard_work") != str(state["wallpaper_guard_work"]) or
            receipt.get("guard_source") != str(state["wallpaper_guard_source"]) or
            receipt.get("guard_source_sha256") != WALLPAPER_SOURCES["guard_ios26_wallpaper.py"] or
            receipt.get("wallpaper_guard_files") != guard_files or receipt.get("guard_checkpoint") != state["wallpaper_guard_result"]["checkpoint"] or
            receipt.get("apps_audit") != state["apps_audit"] or receipt.get("checkpoints") != inventory["hashes"] or
            receipt.get("disk_chain") != state["wallpaper_chain"] or receipt.get("baseline") != state["wallpaper_chain"][1] or
            receipt.get("inspector_sources") != sources or receipt.get("dependency_files") != dependencies or
            receipt.get("runtime") != session["runtime"] or receipt.get("qualification_sha256") != session["qualification"]["qualification_sha256"] or
            receipt.get("tooling_manifest_sha256") != session["tooling_manifest_sha256"] or
            receipt.get("helper_ram_mib") != session["helper_ram_mib"] or receipt.get("helper_vcpus") != session["helper_vcpus"] or
            receipt.get("readonly") is not True or receipt.get("mounts_allowed") is not False or
            receipt.get("replay_allowed") is not False or receipt.get("repair_allowed") is not False or
            receipt.get("native_required") is not True or receipt.get("tcg_retry") is not False or
            any(receipt.get(k) is not v for k, v in NO_BOOT.items())):
        raise ValueError("saved wallpaper inspection does not bind its exact original prefix and approved source")
    bounds = receipt.get("bounds", {})
    if (type(bounds.get("helper_seconds")) is not int or not 1 <= bounds["helper_seconds"] <= 14400 or
            type(bounds.get("max_log_mib")) is not int or not 8 <= bounds["max_log_mib"] <= 64 or
            type(bounds.get("min_free_mib")) is not int or bounds["min_free_mib"] < 1536 or
            type(bounds.get("min_available_mib")) is not int or bounds["min_available_mib"] < 512):
        raise ValueError("saved wallpaper inspection bounds changed")
    if (result.get("schema") != 1 or result.get("status") != "SAVED_WALLPAPER_INSPECTION_PASSED" or
            result.get("inspection_session_sha256") != prep.digest(receipt) or
            result.get("full_disk_chain_unchanged") is not True or result.get("preparation_and_prior_evidence_unchanged") is not True or
            any(result.get(k) is not v for k, v in NO_BOOT.items())):
        raise ValueError("successful unchanged saved-wallpaper inspection is mandatory")
    state["app"].require_native(result)
    attempt = canonical(result.get("attempt", ""))
    if attempt != inspection_work / "a1" or json.loads(read(attempt / "inspection-result.json")) != result:
        raise ValueError("saved-wallpaper result copies or owned attempt disagree")
    policy = json.loads(read(attempt / "expected-policy.json"))
    if (policy.get("schema") != 1 or policy.get("kind") != "ios26_saved_wallpaper_inspection" or
            not re.fullmatch(r"[0-9a-f]{32}", policy.get("inspection_nonce", "")) or
            policy.get("inspection_session_sha256") != prep.digest(receipt) or
            policy.get("raw_guest_sha256") != inspector.RAW_SHA256 or policy.get("partition_guest_sha256") != inspector.PARTITION_SHA256):
        raise ValueError("saved-wallpaper policy belongs to another inspection/dependency")
    launch_path = attempt / "launch.json"
    launch = json.loads(read(launch_path))
    if result.get("launch") != {"path": str(launch_path), "sha256": sha(read(launch_path))}:
        raise ValueError("saved-wallpaper actual launch identity changed")
    disks = [{"path": attempt / "in.tar", "format": "raw", "readonly": True, "serial": "in"},
             {"path": attempt / "out.raw", "format": "raw", "readonly": False, "serial": "out"},
             {"path": Path(state["wallpaper_chain"][0]["identity"]["path"]), "format": "qcow2", "readonly": True, "serial": "d0"},
             {"path": Path(state["wallpaper_chain"][1]["identity"]["path"]), "format": "qcow2", "readonly": True, "serial": "d1"}]
    argv, env = prep.helper_command(state["plan"], attempt, disks)
    if launch != {"command": argv, "environment": env, "deadline_seconds": bounds["helper_seconds"]}:
        raise ValueError("saved-wallpaper actual helper launch differs from exact read-only/native attachments")
    vm = json.loads(read(attempt / "vm-result.json"))
    if (vm.get("stage") != "saved-wallpaper-inspection" or vm.get("status") != "VM_OBSERVATION_COMPLETE" or
            not prep.vm_success(vm, True) or vm.get("natural_exit") is not True or
            vm.get("witnesses") != result["native_witnesses"] or vm.get("cleanup") != result["cleanup"] or len(vm.get("out_sizes", [])) != 1):
        raise ValueError("saved-wallpaper actual native completion/cleanup differs from its receipt")
    names = {"inspection/result.json", "inspection/fsck-system.txt", "inspection/fsck-data.txt"}
    if set(result.get("outputs", {})) != names:
        raise ValueError("complete saved-wallpaper metadata output inventory required")
    files = {**state["apps_audit"]["files"], **guard_files, **dependencies}
    for name, record in result["outputs"].items():
        path = prep.verify_artifact(record, inspection_work)
        if path != attempt / "files" / name:
            raise ValueError("saved-wallpaper output is outside its owned collection")
        files[str(path)] = sha(read(path))
    if inspector.guest_pass({"prep": prep, "auditor": state["auditor"]}, attempt / "files/inspection", policy) != result.get("guest_result"):
        raise ValueError("saved-wallpaper raw journal/fsck result differs from its receipt")
    for path in (inspection_work / "inspection-session.json", inspection_work / "result.json",
                 attempt / "inspection-result.json", attempt / "expected-policy.json", launch_path, attempt / "vm-result.json"):
        files[str(path)] = sha(read(path))
    for name, expected in sources.items():
        files[str(canonical(source_dir / name))] = expected
    if any(sha(read(path)) != expected for path, expected in files.items()):
        raise ValueError("saved-wallpaper prerequisite source/evidence changed during validation")
    return {"work": str(inspection_work), "source_directory": str(source_dir), "source_hashes": sources,
            "inspection_session_sha256": sha(read(inspection_work / "inspection-session.json")),
            "inspection_result_sha256": sha(read(inspection_work / "result.json")),
            "checkpoints": inventory["hashes"], "files": files}


def preparation_context(inspection_work):
    """Reconstruct preserved scopes without invoking any earlier exact-boundary preflight."""
    receipt = json.loads(read(inspection_work / "inspection-session.json"))
    result = json.loads(read(inspection_work / "result.json"))
    inspector, _ = approved_module(Path(receipt["source_directory"]) / "inspect_ios26_wallpaper.py", WALLPAPER_SOURCES["inspect_ios26_wallpaper.py"])
    approved_module(Path(receipt["source_directory"]) / "inspect_ios26_wallpaper_guest.py", WALLPAPER_SOURCES["inspect_ios26_wallpaper_guest.py"])
    guard_source = canonical(receipt["guard_source"])
    guard, _ = approved_module(guard_source, WALLPAPER_SOURCES["guard_ios26_wallpaper.py"])
    guard_work = canonical(receipt["guard_work"])
    guarded = json.loads(read(guard_work / "guard-session.json"))
    guarded_result = json.loads(read(guard_work / "result.json"))
    observations = json.loads(read(guard_work / "guard-observations.json"))
    audit_work = canonical(guarded["apps_audit"]["work"])
    audited = json.loads(read(audit_work / "apps-audit-session.json"))
    audited_result = json.loads(read(audit_work / "result.json"))
    directory = canonical(audited["source_directory"])
    app, app_body = approved_module(directory / "audit_ios26_apps.py", guard.APP_AUDITOR_SOURCES["audit_ios26_apps.py"])
    app_guest, guest_body = approved_module(directory / "audit_ios26_apps_guest.py", guard.APP_AUDITOR_SOURCES["audit_ios26_apps_guest.py"])
    first_work = canonical(audited["prior_evidence"]["inspection_work"])
    first_receipt = json.loads(read(first_work / "inspection-session.json"))
    first_result = json.loads(read(first_work / "result.json"))
    first_directory = canonical(first_receipt["source_directory"])
    first_sources = {name: app.APPROVED[name] for name in ("inspect_ios26_firstboot.py", "inspect_ios26_firstboot_guest.py")}
    if (first_receipt.get("inspector_sources") != first_sources or
            first_receipt.get("guard_source_sha256") != app.APPROVED["guard_ios26_firstboot.py"]):
        raise ValueError("earlier firstboot inspection/guard source identity changed")
    first_inspector, _ = app.approved_module(first_directory / "inspect_ios26_firstboot.py")
    _, raw_body = app.approved_module(first_directory / "inspect_ios26_firstboot_guest.py")
    firstguard, _ = app.approved_module(first_receipt["guard_source"])
    auditor, partition_body = app.approved_module(first_receipt["partition_guest_source"])
    work, runner = canonical(first_receipt["prep_work"]), canonical(first_receipt["runner_dir"])
    session = json.loads(read(work / "session.json"))
    if (session.get("kind") != "standalone_ios26_preparation" or session.get("native_required") is not True or
            session.get("tcg_retry") is not False or session.get("guest_ram_gib") != RAM_GIB or session.get("timebase_hz") != 38_400_000 or
            session.get("runner_sources", {}).get("cold_boot_ios26.py") != COLD_SHA256 or
            session.get("runner_sources", {}).get("cold_boot_dt.py") != DT_SHA256):
        raise ValueError("unsupported final cold/native/RAM/frozen-source contract")
    prep = firstguard.load_frozen(runner, session["runner_sources"])
    parsed, equivalent = firstguard.runner_arguments(prep, session, work, runner)
    parsed.through, parsed.execute = STAGE, False
    equivalent[equivalent.index("--through") + 1] = guard.STAGE
    plan = prep.preflight(parsed)
    inventory = checkpoint_inventory(prep, work, session)
    if (plan["session"] != session or plan["completed"] != inventory["completed"] or plan["remaining"] or
            plan["artifacts"] != inventory["artifacts"] or plan["through"] != STAGE or plan["helper_smoke"] or
            plan["network_stages"] or plan["guest_boot_stages"] or plan["manifest"]["os"]["ios26"]["vars"]["OS"] != Path(app.OS_LOGICAL).name):
        raise ValueError("exact completed through-pack preparation was not reproduced")
    prior = app.saved_inspection(first_inspector, firstguard, prep, first_work, first_receipt, first_result,
                                  guard.prefix(inventory, app.STAGE), plan, session)
    app_inputs = app.full_inputs(prep, work, guard.prefix(inventory, app.STAGE))
    state = {"prep": prep, "plan": plan, "inventory": inventory, "prep_work": work, "runner": runner,
        "firstguard": firstguard, "app": app, "app_guest": app_guest, "auditor": auditor,
        "app_receipt": audited, "prior_evidence": prior, "app_inputs": app_inputs,
        "wallpaper_guard": guard, "wallpaper_inspector": inspector,
        "wallpaper_guard_source": guard_source, "wallpaper_guard_work": guard_work,
        "wallpaper_guard_result": guarded_result, "raw_source": first_directory / "inspect_ios26_firstboot_guest.py",
        "partition_source": canonical(first_receipt["partition_guest_source"])}
    state["apps_audit"] = guard.app_audit_acceptance(app, state, audit_work, audited, audited_result, prior, app_inputs,
        {"audit_ios26_apps.py": app_body, "audit_ios26_apps_guest.py": guest_body})
    wallpaper = guard.prefix(inventory, guard.STAGE)
    state["wallpaper_inventory"] = wallpaper
    state["wallpaper_chain"] = guard.full_disks(prep, work, wallpaper)
    original_plan = dict(plan, completed=wallpaper["completed"], artifacts=wallpaper["artifacts"],
                         through=guard.STAGE, remaining=[], network_stages=[], guest_boot_stages=[])
    original = dict(state, inventory=wallpaper, plan=original_plan,
                    disk_chain=state["wallpaper_chain"], equivalent_argv=equivalent)
    bound = guard.guard_acceptance(original, guard_work, guarded, guarded_result, observations)
    state["wallpaper_inspection"] = wallpaper_inspection_acceptance(state, inspection_work, receipt, result, bound)
    state["packed"] = packed_inputs(prep, work, inventory, state["wallpaper_chain"])
    return state


def mem_available_kib(body):
    """Require exactly one complete, correctly labelled /proc/meminfo value."""
    if not isinstance(body, bytes) or not 0 < len(body) <= 1 << 20:
        raise ValueError("empty or excessive /proc/meminfo")
    lines = body.decode("ascii", errors="strict").splitlines()
    selected = [line for line in lines if line.split(":", 1)[0].strip() == "MemAvailable"]
    if len(selected) != 1:
        raise ValueError("missing or duplicate MemAvailable")
    match = re.fullmatch(r"MemAvailable:[ \t]+([0-9]+)[ \t]+kB", selected[0])
    if match is None or len(match[1]) > 16:
        raise ValueError("malformed MemAvailable or units")
    value = int(match[1])
    if value >= 1 << 53:
        raise ValueError("excessive MemAvailable")
    return value


def memory_bytes():
    with Path("/proc/meminfo").open("rb") as stream:
        return stream.read((1 << 20) + 1)


class MemoryObservations:
    """Bounded samples with a permanent failure latch, including read failures."""
    def __init__(self, reader=memory_bytes):
        self.reader = reader
        self.samples = []
        self.sample_count = 0
        self.violation = None
        self.launch_attempts = 0
        self.prelaunch_passed = False
        self.runtime_samples = 0
        self.storage_errors = []
        self.launch_tree = None
        self.launch_command = None

    def latch(self, reason, phase):
        if self.violation is None:
            self.violation = {"phase": phase, "reason": reason}

    def sample(self, phase, minimum_mib):
        self.sample_count += 1
        row = {"sequence": self.sample_count, "phase": phase, "minimum_kib": minimum_mib * 1024,
               "passed": False}
        try:
            value = mem_available_kib(self.reader())
            row.update(available_kib=value, available_mib=value / 1024,
                       passed=value >= minimum_mib * 1024)
            if not row["passed"]:
                self.latch("MemAvailable below required floor", phase)
        except Exception as error:
            row["error"] = type(error).__name__ + ": " + str(error)
            self.latch("MemAvailable missing, malformed or unreadable", phase)
        if len(self.samples) < 256:
            self.samples.append(row)
        else:
            self.latch("memory sample bound exceeded", phase)
        if phase != "prelaunch":
            self.runtime_samples += 1
        return row

    def report(self):
        return {"schema": 1, "prelaunch_floor_mib": PRELAUNCH_MIB, "running_floor_mib": RUNNING_MIB,
                "launch_attempts": self.launch_attempts, "prelaunch_passed": self.prelaunch_passed,
                "runtime_samples": self.runtime_samples, "sample_count": self.sample_count,
                "samples": list(self.samples), "violation": self.violation,
                "storage_errors": list(self.storage_errors), "launch_tree": self.launch_tree,
                "launch_command": self.launch_command,
                "passed": (self.launch_attempts == 1 and self.prelaunch_passed and self.runtime_samples > 0
                           and self.violation is None and not self.storage_errors)}


def launch_tree(cold, plan):
    """The qualified vresearch machine allocates RAM from this actual ADT."""
    if (type(plan.get("ram_gib")) is not int or plan["ram_gib"] != RAM_GIB or
            type(plan.get("scale")) is not int or plan["scale"] != 3):
        raise ValueError("final cold boot requires exactly 3 GiB and the prepared 3x tree")
    source = read(plan["dtree"], 16 << 20)
    copied = read(Path(plan["run_dir"]) / "input-device-tree", 16 << 20)
    patched = read(Path(plan["run_dir"]) / "device-tree", 16 << 20)
    expected = cold.expected_tree(source, RAM_GIB, 3)
    if copied != source or patched != expected or cold.expected_tree(patched, RAM_GIB, 3) != patched:
        raise ValueError("actual launch tree differs from reviewed 3 GiB/38400000 Hz geometry")
    return {"source_sha256": sha(source), "copied_sha256": sha(copied), "patched_sha256": sha(patched),
            "ram_bytes": RAM_GIB << 30, "timebase_hz": 38_400_000, "vcpus": 4, "display_scale": 3,
            "allocation_source": "qualified vresearch /chosen/dram-size"}


class LaunchProxy:
    """Replace one module reference, never the shared subprocess module."""
    def __init__(self, original, cold, plan, observations, before_launch=None):
        self.original, self.cold, self.plan, self.observations = original, cold, plan, observations
        self.qemu = str(Path(plan["package"]) / "qemu-system-aarch64")
        self.before_launch = before_launch

    def __getattr__(self, name):
        return getattr(self.original, name)

    def Popen(self, argv, *positional, **keywords):
        if not isinstance(argv, (list, tuple)) or not argv or argv[0] != self.qemu:
            return self.original.Popen(argv, *positional, **keywords)
        observed = self.observations
        observed.launch_attempts += 1
        if observed.launch_attempts != 1 or positional:
            raise ValueError("exactly one qualified cold QEMU launch is permitted")
        inherited = keywords.get("pass_fds")
        if type(inherited) is not tuple or len(inherited) != 1 or type(inherited[0]) is not int or inherited[0] < 0:
            raise ValueError("qualified cold launch must inherit exactly its frame descriptor")
        expected_argv, expected_env = self.cold.command(self.plan, inherited[0])
        if (list(argv) != expected_argv or keywords.get("env") != expected_env or
                keywords.get("stdin") != self.original.DEVNULL or keywords.get("stderr") != self.original.STDOUT or
                keywords.get("start_new_session") is not True or not callable(keywords.get("preexec_fn")) or
                set(keywords) != {"env", "stdin", "stdout", "stderr", "pass_fds", "start_new_session", "preexec_fn"}):
            raise ValueError("actual Popen differs from the frozen qualified cold command/owner contract")
        if self.before_launch is not None:
            self.before_launch()
        observed.launch_tree = launch_tree(self.cold, self.plan)
        observed.launch_command = {"command": expected_argv, "environment": expected_env,
                                   "frozen_command_unchanged": True}
        sample = observed.sample("prelaunch", PRELAUNCH_MIB)
        observed.prelaunch_passed = sample["passed"] and observed.violation is None
        if not observed.prelaunch_passed:
            raise ValueError("fresh MemAvailable must be at least 3840 MiB immediately before QEMU")
        # Intentionally the final expression: no fallible post-spawn work may
        # prevent the frozen caller from assigning and cleaning up its child.
        return self.original.Popen(argv, *positional, **keywords)


@contextlib.contextmanager
def installed_memory_hooks(cold, plan, observed, before_launch=None):
    original_subprocess, original_storage, original_shutdown = cold.subprocess, cold.storage_report, cold.shutdown

    def storage(run, args):
        try:
            report = original_storage(run, args)
            if type(report) is not dict or type(report.get("within_bounds")) is not bool:
                raise ValueError("frozen storage report has an invalid shape")
        except Exception as error:
            failure = type(error).__name__ + ": " + str(error)
            observed.storage_errors.append(failure)
            report = {"within_bounds": False, "storage_report_error": failure}
        observed.sample("storage_report", RUNNING_MIB)
        report = dict(report)
        report["memory"] = observed.report()
        report["within_bounds"] = report["within_bounds"] and observed.violation is None and not observed.storage_errors
        return report

    def shutdown(*args, **kwargs):
        try:
            observed.sample("pre_shutdown", RUNNING_MIB)
        except BaseException:
            # Monitoring must never replace or interrupt the owner's cleanup.
            try:
                observed.latch("pre-shutdown memory observation failed", "pre_shutdown")
            except BaseException:
                pass
        finally:
            return original_shutdown(*args, **kwargs)

    cold.subprocess = LaunchProxy(original_subprocess, cold, plan, observed, before_launch)
    cold.storage_report, cold.shutdown = storage, shutdown
    try:
        yield
    finally:
        cold.subprocess, cold.storage_report, cold.shutdown = original_subprocess, original_storage, original_shutdown


def preflight(args):
    if not args.wallpaper_inspection_work or not args.work:
        raise ValueError("required --wallpaper-inspection-work and --work")
    if not 30 <= args.seconds <= 1800 or args.min_free_mib < 1024 or not 1 <= args.max_log_mib <= 64:
        raise ValueError("cold guard requires 30..1800 seconds, >=1024 MiB free and 1..64 MiB logs")
    if any(not marker or any(c in marker for c in "\n\r\0") for marker in args.expect_serial):
        raise ValueError("serial markers must be nonempty single-line literals")
    inspection_work, work = canonical(args.wallpaper_inspection_work), canonical(args.work, False)
    if work.exists() or not work.parent.is_dir() or len(str(work)) > 55:
        raise ValueError("fresh guard work requires an existing parent and at most 55 characters")
    state = preparation_context(inspection_work)
    prep, cold, session = state["prep"], state["prep"].cold, state["plan"]["session"]
    source = canonical(__file__)
    roots = state["wallpaper_guard"].output_roots(state) | {inspection_work, state["wallpaper_guard_work"],
        state["wallpaper_guard_source"].parent, canonical(state["wallpaper_inspection"]["source_directory"]), source.parent}
    if any(work.is_relative_to(root) or root.is_relative_to(work) for root in roots):
        raise ValueError("cold guard output must be outside every input/source/evidence tree")
    argv = ["--assets", state["packed"]["assets"], "--package", session["package"],
        "--qualification", session["qualification_file"], "--qemu-img", str(Path(session["tooling"]) / "tools/qemu-img"),
        "--qemu-img-lib", str(Path(session["tooling"]) / "lib"), "--dt-tool", str(state["runner"] / "cold_boot_dt.py"),
        "--run-dir", str(work / "cold"), "--variant", "aod", "--ram-gib", "3", "--scale", "3",
        "--seconds", str(args.seconds), "--min-free-mib", str(args.min_free_mib), "--max-log-mib", str(args.max_log_mib)]
    for marker in args.expect_serial:
        argv += ["--expect-serial", marker]
    cold_args = cold.parser().parse_args(argv)
    # The frozen preflight requires its new run's parent to exist. The wrapper
    # itself must remain read-only, so validate using the fresh outer work path
    # and then derive the equally fresh nested run without creating either.
    cold_args.run_dir = work
    checked = cold.preflight(cold_args)
    if checked.get("status") != "PREFLIGHT_READY":
        raise ValueError("frozen cold preflight refused: " + "; ".join(checked.get("blockers", [])))
    cold_args.run_dir = work / "cold"
    checked["plan"]["run_dir"] = str(cold_args.run_dir)
    checked["command"], checked["environment"] = cold.command(checked["plan"], "INHERITED_MEMFD")
    if len(str(cold_args.run_dir / "console.sock").encode()) >= 108:
        raise ValueError("nested cold run path is too long for Unix sockets")
    if (checked["plan"]["source_disk"] != state["packed"]["packed_disk"]["identity"]["path"] or
            checked["plan"]["disk_chain"] != [state["packed"]["packed_disk"]["identity"]] or
            checked["plan"]["ram_gib"] != RAM_GIB or checked["plan"]["scale"] != 3 or
            checked["plan"]["qualification"] != session["qualification"]):
        raise ValueError("frozen cold plan differs from exact packed assets/qualification")
    bindings = dict(state["packed"]["bindings"])
    for row in state["app_inputs"]:
        name = row["identity"]["path"]
        if name in bindings and bindings[name] != row:
            raise ValueError("app/packed predecessor bindings disagree")
        bindings[name] = row
    bound = dict(state["wallpaper_inspection"]["files"])
    bound.update(state["inventory"]["hashes"])
    bound[str(state["prep_work"] / "session.json")] = sha(read(state["prep_work"] / "session.json"))
    bound.update({str(state["runner"] / name): expected for name, expected in session["runner_sources"].items()})
    bound[str(source)] = sha(read(source))
    receipt = {"schema": 1, "kind": "ios26_final_coldboot_guard", "guard_source": str(source),
        "guard_source_sha256": bound[str(source)], "prep_work": str(state["prep_work"]), "runner_dir": str(state["runner"]),
        "prep_session_sha256": bound[str(state["prep_work"] / "session.json")], "frozen_sources": session["runner_sources"],
        "through": STAGE, "checkpoints": state["inventory"]["hashes"], "packed": state["packed"],
        "wallpaper_inspection": state["wallpaper_inspection"], "apps_audit": state["apps_audit"],
        "bound_files": bound, "input_bindings": bindings,
        "prior_input_identities": state["prior_evidence"]["frozen_input_identities"],
        "runtime": session["runtime"], "qualification_sha256": session["qualification"]["qualification_sha256"],
        "tooling_manifest_sha256": session["tooling_manifest_sha256"], "cold_preflight": checked,
        "equivalent_frozen_cold_argv": [sys.executable, "-B", str(state["runner"] / "cold_boot_ios26.py"), *argv, "--boot"],
        "memory_policy": {"ram_gib": RAM_GIB, "prelaunch_minimum_mib": PRELAUNCH_MIB, "running_minimum_mib": RUNNING_MIB,
            "sampling": "exact Popen, original approximately 10-second storage reports, pre-shutdown and final report",
            "permanent_failure_latch": True, "missing_or_malformed_is_failure": True, "hard_realtime_guarantee": False},
        "expected_serial": list(args.expect_serial), "native_required": True, "tcg_retry": False,
        "frozen_command_unchanged": True, "original_witness_status_required": "WITNESSES_OBSERVED",
        "scope": "bounded final cold native/GPU/explicit-serial observation; no automatic UI or product qualification", **NO_BOOT}
    state.update(work=work, cold_args=cold_args, cold_preflight=checked, receipt=receipt)
    return state


def unchanged_inputs(state, full=True):
    prep, receipt, work = state["prep"], state["receipt"], state["prep_work"]
    for path, expected in receipt["bound_files"].items():
        if sha(read(path)) != expected:
            raise ValueError("bound source/checkpoint/prior proof changed: " + Path(path).name)
    inventory = checkpoint_inventory(prep, work, state["plan"]["session"])
    if inventory["hashes"] != receipt["checkpoints"]:
        raise ValueError("completed through-pack boundary changed")
    for row in receipt["input_bindings"].values():
        path = canonical(row["identity"]["path"])
        if prep.cold.readonly_identity(path) != row["identity"]:
            raise ValueError("packed/retained input identity changed")
        if full and prep.file_record(path, work) != row["record"]:
            raise ValueError("full packed/retained input bytes or backing chain changed")
    for original in receipt["prior_input_identities"].values():
        if prep.cold.readonly_identity(original["path"]) != original:
            raise ValueError("original prerequisite input identity changed")
    assets = canonical(receipt["packed"]["assets"])
    if {p.name for p in assets.iterdir()} != {Path(name).name for name in receipt["packed"]["files"]}:
        raise ValueError("packed directory inventory changed")
    if full:
        prep.recheck(state["plan"])


@contextlib.contextmanager
def own_coldboot(state):
    original = os.open(state["prep_work"] / "owner.lock", os.O_RDONLY | os.O_NOFOLLOW)
    owned = None
    try:
        if not stat.S_ISREG(os.fstat(original).st_mode):
            raise ValueError("preparation owner lock is not regular")
        try:
            fcntl.flock(original, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("preparation still has another owner") from None
        state["prep"].refuse_live_children(state["prep_work"])
        unchanged_inputs(state, True)
        state["work"].mkdir(mode=0o700)
        owned = os.open(state["work"] / "owner.lock", os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        fcntl.flock(owned, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state["prep"].atomic_json(state["work"] / "guard-session.json", state["receipt"])
        yield
    finally:
        if owned is not None:
            os.close(owned)
        os.close(original)


def execute(state):
    prep, cold = state["prep"], state["prep"].cold
    observed = MemoryObservations()
    with own_coldboot(state):
        result = {"schema": 1, "status": "INCOMPLETE", "started_utc": cold.utc(),
            "guard_session_sha256": prep.digest(state["receipt"]), "guest_started": False,
            "original_result": None, "original_witness_status": None,
            "all_bound_inputs_unchanged": False, "memory_passed": False, **NO_BOOT}
        try:
            # No prep stage is executed here. The original single cold owner
            # still creates the overlay, owns the frame and reaps its child.
            with installed_memory_hooks(cold, state["cold_preflight"]["plan"], observed,
                                        lambda: unchanged_inputs(state, False)):
                original = cold.boot(state["cold_preflight"], state["cold_args"])
            result["guest_started"] = original.get("guest_started") is True
            result["original_witness_status"] = original.get("status")
            path = state["work"] / "cold/result.json"
            if json.loads(read(path)) != original:
                raise ValueError("frozen cold result was not durably retained unchanged")
            result["original_result"] = {"path": str(path), "sha256": sha(read(path))}
            if result["guest_started"]:
                launch_path = state["work"] / "cold/launch.json"
                launch = json.loads(read(launch_path))
                if observed.launch_command is None or launch != {k: observed.launch_command[k] for k in ("command", "environment")}:
                    raise ValueError("actual cold launch differs from the exact guarded Popen")
                result["actual_launch"] = {"path": str(launch_path), "sha256": sha(read(launch_path))}
            if (original.get("status") == "WITNESSES_OBSERVED" and
                    cold.witness_status(original, state["cold_args"].expect_serial) != "WITNESSES_OBSERVED"):
                raise ValueError("original cold success no longer satisfies its unchanged witness rules")
        except BaseException as error:
            result["error"] = type(error).__name__ + ": " + str(error)
        finally:
            # Supervision/ordered shutdown has returned before full-file hashes.
            # Do not install any raising signal or timing hooks during cleanup.
            with prep.cleanup_signals():
                try:
                    unchanged_inputs(state, True)
                    result["all_bound_inputs_unchanged"] = True
                except Exception as error:
                    result["identity_error"] = type(error).__name__ + ": " + str(error)
                memory = observed.report()
                result["memory_passed"] = memory["passed"]
                if (not result.get("error") and result["guest_started"] and result["original_witness_status"] == "WITNESSES_OBSERVED" and
                        result["all_bound_inputs_unchanged"] and result["memory_passed"]):
                    result["status"] = "WITNESSES_OBSERVED"
                prep.atomic_json(state["work"] / "memory-observations.json", memory)
                result["memory_observations"] = {"path": str(state["work"] / "memory-observations.json"),
                    "sha256": sha(read(state["work"] / "memory-observations.json"))}
                result["finished_utc"] = cold.utc()
                prep.atomic_json(state["work"] / "result.json", result)
        return result


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--wallpaper-inspection-work")
    p.add_argument("--work")
    p.add_argument("--seconds", type=int, default=900)
    p.add_argument("--min-free-mib", type=int, default=1024)
    p.add_argument("--max-log-mib", type=int, default=64)
    p.add_argument("--expect-serial", action="append", default=[], help="explicit original-harness literal witness; no automatic milestone")
    p.add_argument("--boot", action="store_true", help="execute only the single guarded final cold observation")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        state = preflight(args)
        result = {"schema": 1, "status": "PREFLIGHT_READY", "guard_session": state["receipt"], **NO_BOOT}
        if args.boot:
            result = execute(state)
    except (Exception, KeyboardInterrupt) as error:
        result = {"schema": 1, "status": "INCOMPLETE", "error": type(error).__name__ + ": " + str(error), **NO_BOOT}
    print(json.dumps(result, indent=2), flush=True)
    return 0 if result["status"] in ("PREFLIGHT_READY", "WITNESSES_OBSERVED") else 2


if __name__ == "__main__":
    raise SystemExit(main())
