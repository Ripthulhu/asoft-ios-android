#!/usr/bin/env python3
"""Use the pinned read-only inspector on the verified Data recovery descendant."""
import hashlib
import json
from pathlib import Path
import signal
import sys
import types

BASE = Path("/data/local/tmp")
PINNED = BASE / "pixel-saved-checks-resume5"
GUARD = BASE / "pixel-firstboot-guard-e9cc754-resume1"
WORK = BASE / "asoft-recovered-audit-01"
RECOVERY = BASE / "asoft-data-copy-recovery-01"
LAYER = RECOVERY / "recovered.qcow2"
PIN = "edd1213461f0cf5b83b8e4e3e1c6b299ec56b20746f68c4b394c93bcbbac8735"
MANIFEST = "1379e1e3cdd4b3180c1efe20757fc3afc366e01d426d705d806cd07ae8d33729"
SOURCE_PINS = {
    "inspect_ios26_firstboot.py": "30eaaffc42aa73bf95488f3ca504d7c56344fbada0aaed746904ed1f4f78fd3e",
    "inspect_ios26_firstboot_guest.py": "96c559bac19a3c36a4e26c2cf57b75cbafdfd5879de6e4fceb582b2c07a9b51a",
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def pinned(path, digest):
    require(path.resolve(strict=True) == path and path.is_file() and path.stat().st_nlink == 1,
            "noncanonical or multiply linked input: " + str(path))
    body = path.read_bytes()
    require(hashlib.sha256(body).hexdigest() == digest, "input hash differs: " + str(path))
    return body


def bind_layer(prep, original):
    receipt = json.loads(pinned(RECOVERY / "manifest.json", MANIFEST))
    require(receipt["status"] == "RECOVERED_DATA_COPY_VERIFIED" and
            receipt["new_overlay_sha256"] == PIN and receipt["source_sha256"] == original["record"]["sha256"] and
            receipt["outside_data_allocations"] == 0 and receipt["direct_data_readback_bytes"] == 16 << 30 and
            receipt["read_only_data_fsck_passed"] is True, "recovery prerequisites changed")
    pinned(LAYER, PIN)
    chain = prep.cold.qcow_chain(LAYER)
    require(len(chain) == 3 and Path(chain[0]["path"]) == LAYER and
            chain[1]["path"] == original["identity"]["path"], "recovered backing chain differs")
    return prep.cold.readonly_identity(LAYER)


def stop(number, _frame):
    raise InterruptedError("inspection interrupted: " + str(number))


def main():
    require(sys.argv[1:] == ["--execute"] and sys.flags.isolated and sys.dont_write_bytecode,
            "use isolated Python -I -B and explicit --execute")
    bodies = {name: pinned(PINNED / name, pin) for name, pin in SOURCE_PINS.items()}
    path = PINNED / "inspect_ios26_firstboot.py"
    inspector = types.ModuleType("pinned_inspection")
    inspector.__file__ = str(path)
    exec(compile(bodies[path.name], str(path), "exec"), vars(inspector))
    args = inspector.parser().parse_args(["--guard-work", str(GUARD), "--work", str(WORK),
                                            "--inspection-seconds", "360", "--execute"])
    state = inspector.preflight(args)
    prep = state["prep"]
    original = state["receipt"]["backing_chain"][0]
    require(state["disk"] == Path(original["identity"]["path"]), "original firstboot disk differs")
    layer_identity = bind_layer(prep, original)
    state["receipt"]["recovered_descendant"] = {
        "identity": layer_identity, "sha256": PIN, "recovery_manifest_sha256": MANIFEST,
    }
    state["disk"] = LAYER
    unchanged = inspector.unchanged_inputs

    def verify(current, full=True):
        unchanged(current, full)
        require(bind_layer(prep, original) == layer_identity, "recovered layer identity changed")

    inspector.unchanged_inputs = verify
    print("Read-only inspection preflight accepted for recovered descendant", flush=True)
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, stop)
    result = inspector.execute(state, args)
    print(json.dumps({name: result.get(name) for name in
                      ("status", "error", "identity_error", "native_witnesses", "natural_exit")}),
          flush=True)
    return 0 if result["status"] == "SAVED_FIRSTBOOT_INSPECTION_PASSED" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, InterruptedError) as error:
        print(json.dumps({"status": "REFUSED", "error": str(error)}), flush=True)
        raise SystemExit(2)
