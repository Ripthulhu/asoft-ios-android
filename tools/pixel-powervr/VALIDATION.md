# Validation record

Prepared on 2026-11-21. No physical phone or Vulkan GPU execution was performed
for this package. No iOS boot was attempted. The package is a testable
development handoff, not a declaration of Pixel GPU support.

## Android programs and authored shaders

`build.py` completed successfully with Android NDK r29
(`29.0.14206865`, Clang 21), targeting `aarch64-linux-android35`.
Both C programs built with `-Wall -Wextra -Werror`. Both compiled shaders passed
`spirv-val --target-env vulkan1.3`. Exact tool version output and source hashes
are in `build-info.json`; binary and shader hashes are in `SHA256SUMS`.

Additional checks:

- Clang static analysis completed without diagnostics for both C sources.
- ELF inspection: AArch64 PIE, `/system/bin/linker64`, all LOAD alignments
  `0x4000` (16 KiB), Android `libvulkan.so`, `libdl.so`, and `libc.so` dependencies.
- Fragment disassembly contains `TileImageColorReadAccessEXT`,
  `SPV_EXT_shader_tile_image`, `TileImageEXT`, and `OpColorAttachmentReadEXT`.
  Its execution modes do not include a noncoherent tile-read mode.
- Python syntax checks, shell syntax checks and packaged checksum verification
  passed.

The DMA-BUF source was separately reviewed for FD ownership, cache handoffs,
queue ownership, bounded fences, pending-resource cleanup, and per-page
comparisons. The unexported guard limitation is stated in the code and README.

## ADB runner behavior

The portable harness is `tests/check_runner.py`. It invokes an explicit local
fake ADB executable with synthetic package fixtures. It never invokes real ADB
or a phone. On the Linux/Python build host:

```text
ALL_OUTPUTS_SYNTHETIC=true
RUNNER_SHA256=6459f9684930c463a52880aeb743ca64b565ef38d9cc2d1355ecfc5ecd2237d7
TOTAL_SCENARIOS=21
PASSED_SCENARIOS=21
FAILED_BEHAVIOR_SCENARIOS=0
```

The cases cover successful sequencing, root denial, device selection,
unsupported and blocked capabilities, internal GPU timeout status, remote
process timeout, host subprocess timeout, abnormal termination, bad checksum,
push failure, unsafe or unexpected temporary-directory output, `--no-root`,
and `--keep-remote`.

The checks specifically establish that a bad checksum performs no ADB calls,
untrusted temporary paths cause no push or cleanup, cleanup uses only the
validated temporary directory, and a failed GPU probe stops later GPU work.
They do not establish Windows execution or phone-driver behavior.

To rerun the synthetic tests on a Unix-like host:

```sh
python3 tests/check_runner.py
```

Add `--keep-output` to retain the temporary mock traces and JSON summary.

## Dependency candidate

The memory-import backport has 17 passing focused host-memory tests, a
passing targeted clippy run, and a passing targeted Rustdoc build with warnings
denied. Its tests use mock Vulkan
dispatch. See [patches/README.md](patches/README.md) for scope, provenance and
remaining integration conditions. Full renderer and guest qualification are
outstanding.
