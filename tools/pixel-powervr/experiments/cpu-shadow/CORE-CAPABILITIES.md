# Authored core capability qualification

The optional core fixture sends authored guest MMIO/FIFO traffic through the real
C API and an isolated task. It checks the actual capability answers, a buffer
whose guest record carries the private flag, a shared heap child, GPU writes,
discard, fragmented rebind, preservation of old backing and gap pages, settled
CPU-shadow counters, and task deletion. It runs once with argument buffers
enabled and once with them disabled. Those runs check the argument-buffer
configuration gates; they do not dispatch an argument-buffer shader through the
C API or establish an Apple guest boot.

## Recorded physical checkpoint

Experimental reims `e9cc754` passed the complete seventeen-case Pixel suite,
including both core configurations. The
[`physical evidence`](device-checks/core-run-e9cc754/README.md) preserves all 53
exported files, exact Android runtime/header and binary correspondence, actual
v3 host/phone reconstruction and a terminal screenshot. Both new cases completed
the resource paths above with four chunks, eight views, two prepared/finished
epochs, 294,912 uploaded bytes and 98,400 scattered bytes. This establishes the
authored workloads on that exact candidate/device; Apple cold boot, app-UID
execution, required full integration checks and broader guest behavior remain
separate gates.

## Build from committed inputs

First build the candidate Android runtime and matching generated C header. Then
link this standalone fixture; the helper never executes it:

```sh
python3 build_core_fixture.py \
  --source /absolute/reims-candidate \
  --include /absolute/runtime/include \
  --library /absolute/runtime/lib/libreims_vgpu.a \
  --ndk /absolute/android-ndk-r29 \
  --out /absolute/core-fixture
```

The output directory must be new and outside the reims checkout. The helper
requires the C fixture, Python generator and every Python guest ABI builder to
match committed source. It checks the same inventory and HEAD after generation
and again after linking, with hashes for the generated header, runtime header,
static archive, local API-29 memfd shim and build script. Local Cargo path
overrides do not enter those generator inputs.

The Android build uses AArch64/API 29, PIE, 16 KiB LOAD alignment and fatal C and
linker warnings. `core-fixture-build.json` records the exact input and output
hashes, compiler, commands, static linkage, ELF dependencies and
`BUILT_NOT_EXECUTED` status. The output binary is `cpu-shadow-core`.

Include both the binary and `core-fixture-build.json` in the qualification
package. Before claiming the fixture qualifies the packaged QEMU runtime,
compare the core record's `library.sha256` and `header.sha256` with
`runtime_archive_sha256` and `runtime_header_sha256` in `qemu-build.json`.
The generic payload option preserves file hashes; it does not establish that
two independent build records used the same runtime.

## Transfer the new binary with an explicit dictionary

Keep the ordinary package invocation's QEMU, native fixture, authored qualifier,
shader, EFI and updated runner payloads. Add these options when using an already
verified package as the base:

```text
--base-package /absolute/previous/cpu-shadow-qualification
--payload /absolute/core-fixture/cpu-shadow-core
--payload /absolute/core-fixture/core-fixture-build.json
--delta-base cpu-shadow-core=efi-memfd-integration
```

Only `--delta-base` selects update format v3. It names an existing verified ELF
from the pinned base package as the compression dictionary for a new ELF payload
larger than one MiB. Existing files still use their same-name dictionaries;
unchanged files are reused. The base package is never modified. Without this
option, `--base-package` keeps v2 behavior, and `--base` keeps legacy v1 behavior.

The installer requires `--base-package` for v3. It verifies the complete base,
the selected dictionary's membership, bytes and hash, patch bytes, reconstructed
output and checksum inventory. New cross-name targets must decode to executable
ELFs; decoded bytes remain non-executable until every check and the final base
recheck succeed. A failure removes only the invocation's new output directory.
Use the separately recorded ZIP hash and update-manifest hash as before.

## Select all seventeen cases explicitly

```sh
python3 run_device_tests.py \
  --package /absolute/installed/cpu-shadow-qualification \
  --out /absolute/new-qualification-results \
  --core-capabilities
```

The flag requires the checked `cpu-shadow-core` binary and adds cases `core` and
`core-no-argument-buffers`. Each receives a fresh cache, the explicit system
CPU-shadow environment, a 50-second supervisor limit, complete success markers,
and the existing descendant cleanup checks. The fixture itself has a 45-second
alarm. The result records `core_capabilities_requested: true` and reaches success
only after all seventeen cases and the final package recheck pass.

Without the flag the runner retains the existing fifteen-case contract, so
earlier packages remain usable. Product qualification must deliberately select
the expanded gate; the presence of an extra binary alone does not run it.

## Host checks

`test_device_updates.py` uses synthetic, non-runnable AArch64 ELF containers with
real `readelf` and `zstd`. It reconstructs v1/v2/v3 packages and exercises selector,
dictionary, path, content, mode, output-cleanup and format refusals. It runs no
native program or GPU work. `test_core_fixture.py` verifies the committed-source
gate using a temporary authored Git repository, without compiling C.

`host-checks/core-packaging.json` records those checks and the independent
read-only source review. Physical execution and final runtime provenance remain
separate evidence.
