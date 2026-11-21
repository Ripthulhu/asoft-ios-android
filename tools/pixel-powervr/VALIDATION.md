# Validation record

Updated on 2026-11-21 after running the standalone probes on the physical Pixel
10 Pro XL. The tile-image test passed; the DMA-BUF probe stopped at an
unsupported Vulkan buffer-capability declaration. A Vulkan-owned coherent
allocation passed CPU/GPU sharing under both root and an ordinary app UID,
while a direct CPU page-offset alias was unsupported. The dependency candidate
itself has not executed on the phone. No iOS boot was attempted, and these
results do not establish application-level Pixel GPU support.

## Physical Pixel test

The [device test record](results/2026-11-21/README.md) contains the exact observed
results and captured terminal evidence. Tests ran through Tango's existing ADB
terminal as UID 0 in `u:r:ksu:s0`, with SELinux enforcing. This is root-context
evidence. A separate ordinary-app run is recorded below; no ordinary ADB-shell
execution is claimed.

- PowerVR D-Series DXT-48-1536 MC1; loader 1.4.0; device API 1.4.344;
  driver version `0x006a5136`.
- All four transferred executable/shader hashes matched the pinned package.
- Both tile-image ordering cases passed: 1,024 pixels checked per case, zero
  mismatches, process exit 0. No Vulkan validation layer was enabled for this
  phone run; the probe's `validation_errors: 0` counter is not a layer result.
- The running kernel had `CONFIG_UDMABUF=y`, a registered `/dev/udmabuf`, and
  4 KiB pages. The exporter parameters were 1,024 list entries and 64 MiB.
- DMA-BUF/FD/foreign-queue extensions were present, and host-pointer import was
  absent. The `DMA_BUF_EXT` buffer query for usage `0x23` returned
  `externalMemoryFeatures=0`. The probe exited 3 (`UNSUPPORTED`) before opening
  UDMABUF, exporting pages, or attempting Vulkan import or transfers.
- `cmd gpu vkjson` returned a Binder transaction error. This did not prevent
  the direct Vulkan query/rendering probe from executing.

The follow-up [query-only reporter](VULKAN-CAPS.md) subsequently completed all
51 queries on the phone under requested API 1.3, with exit 0. All 17 DMA-BUF
rows returned features 0; all 17 opaque-FD and 17 Android hardware-buffer rows
returned features 6 (importable and exportable), without a dedicated-only
restriction. These include the exact `0x1ff` and `0x201ff` runtime usage masks.
The reporter confirmed coherent host-visible memory type 1, BDA support, and
sparse binding/residency without sparse residency aliasing.

The reporter's NDK build and static analysis passed. The same C source also
completed all 51 queries under requested APIs 1.3 and 1.4 on lavapipe with the
Khronos validation layer active and no reported validation errors. An
independent source review checked its API/feature gates and query chains.
These host validation-layer results are separate from the phone declarations.

A producer-allocation experiment then passed on the physical Pixel. Version 1,
binary SHA-256 `0daa83ea361129d70cc586cbca58401b2614e907f55383fbdf64ee7258a183d7`,
used a 32,768-byte Vulkan allocation with usage `0x201ff` and memory type 1
(`HOST_VISIBLE | HOST_COHERENT | DEVICE_LOCAL`). Legal opaque-FD export/import,
both Vulkan CPU mappings, native `mmap(MAP_SHARED)` at offset zero, and all
8,192-word CPU/GPU comparisons passed; process exit was 0. This establishes a
small contiguous allocation, not existing-guest-page import or runtime
integration. Captured evidence is in the device record.

Version 2, SHA-256
`f5fb47f842632a196aad9441ce1cc25d313dea2dd5b274d57b43662e0d97c59a`, repeated
those baseline phases successfully, then returned exit 4. Its first offset-map
check requested page 5 but read page 0's first value (`0x7b620000` instead of
`0x7b620005`). It stopped before any scatter writes, repeated-page remapping
or scatter-related GPU commands. This is an unsupported CPU offset contract,
not evidence that the earlier canonical buffer checks failed.

The same query, tile and v2 executables were then run by the permission-free
diagnostic APK, SHA-256
`2da38f13b10998a7fd394f265c1e2b0824c40a6f88e9f7461e005ea85b548093`.
The app observed UID 10441 and `u:r:untrusted_app_34:s0:c185,c257,c512,c768`;
the query and opaque programs also printed UID/EUID 10441. All 51 matrix rows
had the same handle-specific outcomes as root. Both tile cases passed, and
the opaque probe passed its Vulkan/full-native-map phases before the identical
page-offset counterexample. Stage exits were **query 0, tile 0, opaque v2 4**.
The app reported unsupported capabilities rather than an overall PASS. The
root shell confirmed SELinux remained enforcing; the app itself could not
read the global enforcing file.

The diagnostic APK's Java/D8 build, signature, binary manifest (no requested
permissions), extracted native payload hashes and ARM64/16 KiB ELF identities
were verified. Its Activity launches native children directly from the
installation's `nativeLibraryDir`, records the ordinary UID/domain before
execution, and enforces bounded waits and stop-on-failure behavior. An
independent source review found no blocker. This qualifies the tested app
context, not the separately rebuilt ASoftware app. Exact provenance is under
[app-probe/](app-probe/README.md).

The v2 native build passed NDK r29 `-Wall -Wextra -Werror` and Clang static
analysis. Its Vulkan baseline passed under lavapipe with Khronos validation
and synchronization validation requested. Lavapipe's raw opaque-FD map did
not expose payload bytes, so that run stopped before native writes. The shared
CPU alias helpers also passed a separate ordinary-memfd fixture covering page
order, all-page guards, repeated remapping, bounds rejection and partial-setup
cleanup. That fixture does not establish opaque-FD or GPU behavior.

The [v3 follow-up](experiments/opaque-move-v3/README.md), binary SHA-256
`987d6950f1654753dab838c41b02d5072872bd8a5ab7f4b6681b1427f83eeb30`, then passed
with `--move-page` in the root shell and ordinary diagnostic APK. It verified
all 8,192 words in a disposable full offset-zero mapping, moved page 5 into a
fresh one-page reservation, checked all 1,024 moved words before writing,
checked CPU writes against all eight canonical pages and independent GPU
readback, checked GPU writes through the moved view, and completed exact-range
cleanup. All seven unselected pages remained correct. There was no refault,
repeated moved alias or scattered GPU test.

The v3 APK SHA-256 was
`16c4343fcd733c4df2a9ee024001554edebf140749866e60dab650d9ae5025f4`. It upgraded
only the same-signer diagnostic package to version 1.1-v3, retaining UID 10441
and the same `untrusted_app_34` domain. At 2026-11-21 14:30:43 UTC it completed
query, tile and opaque move with exits **0, 0, 0** and no timeout or crash.
The native and shader hashes were verified by the running app. The v2
direct-offset failure remains a separate preserved result.

The v3 ordinary-memfd fixture additionally verified that cleanup preserves an
independent mapping placed in the vacated source hole. A child forced a real
failed move and verified cleanup refusal. The Android build, static analysis,
ELF checks and independent source review passed; software Vulkan stopped at
its expected non-payload native-map guard before the new move phase. Exact
records are in the experiment directory and [app-probe-v3/](app-probe-v3/README.md).

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

## Combined metal2vulkan candidate

The final combined dependency revision is
`ffda2ffd9485b6796ad8ca49bc024bf97401342c`, tree
`9fe786a921829ccdb51b2d977c0dbf30f7173962`. It uses runtime version `1499`
and runtime source fingerprint
`828b3ee0938abc07b8a99f167dd3ebeb98f2897b445ceb0adda2b7bd75acba14`.
The source pin was regenerated using the existing validation build script and
checked against the formatted source. The refusal inventory also passed its
check, with zero variants lacking a reach mark.

### Runtime and memory

**34 selected runtime tests passed on that combined revision.**

| Selection | Passed | What it establishes |
|---|---:|---|
| `gather::` | 4 | Existing piece/chunk rules; complete aligned materialization window; refusal of pieces/errors as a persistent-pointer answer |
| `tests::host_memory` | 17 | Import routing, alignment, memory-class and writability contracts, including mock dispatch with the host-pointer extension absent |
| `dynamic` | 10 | Six new pure metadata/shape/recorder tests, one actual dynamic-rendering execution test, and three existing matching tests |
| Exact feature-enable chain | 1 | Actual Vulkan dynamic-rendering and tile-image feature members |
| Exact priming eligibility | 1 | The routed command inventory respects the API/feature gate |
| Existing legacy inline-split/readback regression | 1 | The default Vulkan 1.2 rendering route still executes and produces its expected output |

The dynamic execution used Debian Mesa lavapipe 25.0.7 with LLVM 19.1.7 and the
Khronos validation layer 1.4.309. `VK_DRIVER_FILES` selected the CPU driver,
`VK_LAYER_PATH` selected the supplied layer, and
`VK_INSTANCE_LAYERS=VK_LAYER_KHRONOS_validation` enforced its availability.
No physical GPU was involved.

The authored test runs ordinary owned shaders through the runtime's actual
pipeline, secondary inheritance, deferred recorder, and dynamic-rendering
commands. It asserts exactly two begin/end rendering pairs, checks every
readback pixel, and makes the second draw depend on preserved color, depth and
stencil. It completed without Vulkan validation errors. The software driver
has no tile-image extension, so this does not execute a tile-read instruction
or qualify PowerVR ordering.

All-feature runtime Clippy (`--lib --tests`, `-D warnings`) and targeted Rustdoc
(`--all-features --no-deps`, `RUSTDOCFLAGS=-D warnings`) passed. The tests and
Clippy used `RUSTFLAGS="--cfg m2v_cpu_icd"`, one Cargo build job and
`CARGO_PROFILE_TEST_DEBUG=0`. The test filters above were run with one test
thread and no output capture by the Rust harness. The last three exact tests
used the resulting executable directly; they did not trigger another build.

The same source without the gather integration, runtime revision `9d824ae`,
previously passed 13 selected rendering/gate tests and Clippy. An initial
execution failure exposed missing dynamic-command priming; that was corrected
before either recorded passing runtime revision.

### Compiler

Five focused public-API integration tests passed with real authored AIR inputs
and mandatory `spirv-val`; no validator was skipped. They cover scalar
float/normalized reads, mixed normalized/unsigned/half attachments, actual
feature and API requirements, attachment metadata, cache round-tripping, the
existing ROAA/interlock choices, and typed refusals for unsupported formats,
MSAA, raster-order groups and derivative-dependent tile reads. Compiler
library plus this integration target passed Clippy with `-D warnings`.

The full translator lib-test harness did not execute: attempts to compile that
monolithic target were SIGKILLed in this environment. The smaller public-API
target supplies the focused evidence above; it does not stand in for the
entire workspace gate or a shader corpus census.

### Release-mode measurements

The final combined revision `ffda2ffd` also passed all five focused compiler
integration tests in release mode, with mandatory LLVM and SPIR-V tools and
no tooling skips. The repository's release profile was unchanged, including
its incremental setting; the build used one Cargo job.

Tool versions were Rust 1.98.0, NDK r29 LLVM assembler 21.0.0, and SPIRV-Tools
2025.1. The build command was:

```sh
cargo test -p metal2vulkan --all-features --release --test tile_image --no-run --offline
```

The resulting executable ran with `--nocapture --test-threads=1`, then again
with those arguments and
`--exact tile_image_air_pipeline_carries_real_requirements_and_descriptor_free_locations`.
Kernel RSS came from `wait4`; process-group RSS was sampled approximately every
millisecond during execution and included concurrently live validation tools.

| Execution after the build | Wall time | Kernel peak RSS | Sampled process-group peak |
|---|---:|---:|---:|
| All five focused tests, serially | 239.245 ms | 13.848 MiB | 18.441 MiB |
| Positive three-row translation/validation batch | 82.395 ms | 13.219 MiB | 17.902 MiB |

The positive batch includes LLVM assembly, pipeline compilation, cache checks,
SPIR-V validation and disassembly. Within it, `compile_render_pipeline` took:

| Authored row | Compiler call duration |
|---|---:|
| R32Float scalar, slowest timed compiler call | 2.446111 ms |
| R8Unorm scalar | 1.812842 ms |
| BGRA8Unorm + RGBA32Uint + RG16Float, largest authored row | 2.136334 ms |

The per-call numbers exclude external assembly and validation; the complete
batch time includes them. Both complete measured executions were within the
20-second and 500-MiB limits enforced by the measurement harness. These are
observed measurements for the authored rows on this build host, with no
allocator-level or arbitrary-corpus performance claim and no extrapolation to
Pixel speed.

The clean release build itself took 490.095 seconds and had a kernel peak RSS
of 3,337,352 KiB. That is Rust compilation infrastructure, measured separately
from shader translation. It is not part of the execution timing table.

## Patch reconstruction

[patches/metal2vulkan-series.json](patches/metal2vulkan-series.json) records the
ordered patch files, source revisions, SHA-256 hashes and tree hashes. Applying
that series to its exact base in an isolated Git index reproduced every
intermediate source tree and the final combined tree. The existing initial
memory patch was preserved byte for byte. This check performs no build and
makes no hardware claim.

## Reims integration

The prepared reims revision is
`2e568fba381bca9470e2df14c7029c3a402797b0`, tree
`f94e8a04f9e1c461e5db1aaa4c4935135edc4cbe`. Tests and the Android check used
combined metal2vulkan revision `ffda2ffd` through explicit Cargo patch
configuration; the repository's dependency pins were unchanged.

**32 distinct selected native tests passed. Three existing tests failed in this
environment.** The seven new native regressions are included in those 32:
three deferred/read-only policy cases, the sealed-memfd lifetime test, and
three loader/API-version cases. The memory tests verify that the writable
view shares the original file pages, preserves the original protection and
address translation, and retains the existing deallocator/keep-alive order.

The wider CPU-only rerun reported 30 passes and these three failures:

- `os::linux::import::tests::a_gather_of_pages_without_a_file_dies`
- `os::linux::vm::tests::a_remap_that_fails_part_way_changes_nothing`
- `os::linux::vm::tests::readable_follows_the_protection`

They reach the unchanged anonymous-memory readability path. Independent checks
confirmed `process_vm_readv` returns `-1` with `EPERM` even for a valid one-byte
read from the same process's own buffer in this container. The relevant VM test
bodies and `readable`/`read_probe` implementation are unchanged from the base;
the gather path consults readability before its missing-file rejection.
These test results remain failures. No assertion or product fallback was changed
to mask the environment restriction.

The two additional backing tests initially lacked a working Vulkan device.
Retried in fresh processes with the same lavapipe driver and enforced validation
layer used above, both passed:

- `gpu::backing::tests::replace_answers_as_metal`
- `gpu::backing::tests::a_detached_objects_alias_is_given_back_once_the_runtime_lets_go`

The original detached-buffer allocation patch also has 38 affected core tests
passing. Temporarily restoring its old anonymous-allocation call made the new
regression fail as intended; the aliasable call was restored. Those core tests
were not rerun in the final native pass because the core allocation patch did
not change.

### Android compilation

Rust 1.98.1 with the Android NDK r29 linker configuration completed:

```text
cargo check -p reims-vgpu-c --no-default-features --features vulkan --target aarch64-linux-android
```

The actual invocation also supplied the local candidate dependency overrides.
The check completed in 2m19s. It emitted seven existing dead-code warnings from
the untouched `reims-vgpu-window` crate and no errors. This verifies Android
conditional compilation and Rust/API wiring through the C facade. It does not
establish a linked Android library, an APK, or device execution.

[patches/reims-series.json](patches/reims-series.json) records successful
reconstruction of every intermediate tree and the final reims tree from the
exact base, with the initial allocator patch preserved byte for byte.
