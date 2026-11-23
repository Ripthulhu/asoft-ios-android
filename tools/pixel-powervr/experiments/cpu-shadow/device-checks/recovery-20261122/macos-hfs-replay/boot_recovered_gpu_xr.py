"""Reuse the audited 2x boot with a separately built and checked native engine."""

import argparse
import hashlib
import os
from pathlib import Path
import sys
import types

BASE = Path("/data/local/tmp")
CONTROL = BASE / "asoft-recovered-control-01"
BOOT = BASE / "asoft-recovered-gpu-boot-09-xr"
ADAPTER = CONTROL / "boot_recovered_gpu_08_2x.py"
ADAPTER_SHA = "cf1e1d1fe4ce5c078ba410ec3bf635257adcf0d552aa317645364741e3b6ca90"
BASELINE_SHA = "e7dd143c27b6a320fa61954d53e35abcf515dbaa7b9b3fdd11a6da4017b8018c"


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--engine-package", required=True, type=Path)
    cli.add_argument("--engine-sha256", required=True)
    cli.add_argument("--execute", required=True, action="store_true")
    args = cli.parse_args()
    if os.geteuid() != 0 or not sys.flags.isolated or not sys.dont_write_bytecode:
        raise ValueError("requires root Python -I -B")
    if not args.engine_package.is_relative_to(BASE) or args.engine_package.resolve(strict=True) != args.engine_package:
        raise ValueError("engine package must be a canonical path in /data/local/tmp")
    engine = args.engine_package / "bin/qemu-system-aarch64"
    if engine.resolve(strict=True) != engine or digest(engine) != args.engine_sha256:
        raise ValueError("engine does not match the tested candidate")
    if BOOT.exists() or digest(ADAPTER) != ADAPTER_SHA:
        raise ValueError("expected a fresh attempt and the pinned 2x adapter")

    adapter = types.ModuleType("pixel_xr_boot_adapter")
    adapter.__file__ = str(ADAPTER)
    exec(compile(ADAPTER.read_bytes(), str(ADAPTER), "exec"), vars(adapter))
    adapter.proof()
    baseline = CONTROL / "boot_recovered_gpu_05.py"
    body = adapter.load(baseline, "e9ef8a3663c6c6969955abd436f14ef5f81418d85046d9db0625a794d57edb81").decode()
    body = adapter.adapt_once(body, 'BOOT = BASE / "asoft-recovered-gpu-boot-05"', f'BOOT = Path({str(BOOT)!r})')
    body = adapter.adapt_once(
        body, '        cfg = prep.stages.boot_inputs("ios26-wallpaper")',
        '        cfg = prep.stages.boot_inputs("ios26-wallpaper")\n'
        '        patch_launch(prep, plan, paths, cfg["source"])',
    )
    # The accepted preparation result is immutable and the owner lock and
    # live-child checks still run. The historical numeric PID was reused.
    body = adapter.adapt_once(body, "    wait_owner(args.after_preparation_pid)\n", "")

    def patch_launch(prep, plan, paths, logical):
        adapter.patch_launch(prep, plan, paths, logical)
        existing = prep.cold.command

        def command(launch, fd):
            argv, env = existing(launch, fd)
            if digest(Path(argv[0])) != BASELINE_SHA or digest(engine) != args.engine_sha256:
                raise ValueError("unexpected baseline or candidate engine bytes")
            argv[0] = str(engine)
            env["LD_LIBRARY_PATH"] = str(args.engine_package / "lib")
            print(f"XR_NATIVE_ENGINE_SHA256={args.engine_sha256}", flush=True)
            return argv, env

        prep.cold.command = command

    sys.argv = [str(baseline), "--execute", "--after-preparation-pid", "0"]
    return adapter.bind(baseline, body, patch_launch=patch_launch).main()


if __name__ == "__main__":
    raise SystemExit(main())
