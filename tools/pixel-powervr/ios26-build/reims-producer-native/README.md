# Reims-owned allocation through native EL0 and GPU readback

**Passed on the Pixel 10 Pro XL under root, with SELinux enforcing.** The
successful run began at 2026-11-21 20:25:17 UTC. The
[device record](../../results/2026-11-21/reims-native-gpu-root.json) and
[terminal capture](../../results/2026-11-21/reims-native-gpu-root.jpg) preserve
the observed result, including the initial cache-path startup failure.

The actual reims/metal2vulkan runtime now owns this diagnostic's allocation,
buffer identity, native-export lifetime, upload, noncoherent cache operations
and independent GPU readback. The C owner uses the additive producer API.
The strict native supervisor and QEMU binary are unchanged from the previously
qualified [one-region checkpoint](../native-gpu-one-region/README.md).

## Observed device result

| Check | Result |
| --- | --- |
| Reims allocation | ID 1, runtime object 1, logical/allocation size 32,768 bytes |
| Actual memory | Type 2, flags `0xb`: host-visible, cached, noncoherent; cache atom 1 byte |
| GPU upload and initial CPU visibility | All 8,192 words matched |
| Ownership refusal | Live export blocked CPU end; CPU epoch blocked GPU upload; both returned status 17 |
| Native execution | Six credentialed phases: READY, ENTRY, CODE_MAP, DATA_FAULT, DATA_MAP, COMPLETE |
| Native scalar result | `0x6a1b2c346a1b2c34` became `0x615c5026615c515d` |
| Quiescence before GPU reuse | Clean engine exit 0; leader, factory and stub reaped; `ECHILD=1` |
| Replayed transitions | Native retirement and CPU end both refused with status 17 |
| Independent runtime GPU readback | All 8,192 words matched; eight bytes at offset 16,392 changed |
| CPU visibility after invalidate | All 8,192 words matched |
| Final identity and counters | Same allocation/runtime object; two flushes, two invalidations, two completed submissions |
| Exit | Owner 0, runner 0; `REIMS_NATIVE_GPU_ONE_REGION_PASS` |

The native view is the selected 16 KiB half of a 32 KiB producer allocation.
The fixed target payload runs in native EL0; EL1 setup uses TCG. Code, stack,
page tables and control metadata stay in ordinary memory. No producer atomics
or producer instruction fetch occur. The native worker must exit and the owner
must reap its complete process tree before export retirement and GPU reuse.

## Source and exact artifacts

`checkpoint-index.json` records the SHA-256 and size of every changed source,
record, log and evidence file in this increment, excluding the index itself.
Its paths are relative to the repository root.

The [optional reims patch](../../patches/reims-producer/README.md) prepares commit
`7bbcb042a71b57dba286d33638848c188e5d4799`, tree
`7ec29658bf455090d881b8ef055fdf00394e61b3`, over the original prepared base
`2e568fba381bca9470e2df14c7029c3a402797b0`. Its dependency is the separate
[metal2vulkan retained-backing increment](../../patches/producer-adoption/README.md),
commit `7aaf60f105544b70b4cf25f9eb44ace4b00a61fd`.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Localized real reims static archive | 837,757,360 | `35ae82f7e95a955792b141dde7558bf8bf68510f6787983c525ae0a83abd12ca` |
| Android owner | 18,559,936 | `8ba9ed74da4c4d91e9ca9f2247761ddb977a72a31ea4ab369b66ae8bcccedceb` |
| Existing QEMU | 58,529,200 | `a815e121d487c15cd9c1cec75ca6f43a48b2edf1ab42675bb9cde988b9679145` |
| Complete owner-package ZIP | 8,121,883 | `650e4a188baa81eb45433fba854ef9252697984b603309c73e58552f6edd0d87` |
| Full update ZIP | 1,971,141 | `d128b204e0a11b6d5c63db84c016928a67ff0b68da3f769b77316ef3903991be` |

The downloadable owner package is `reims-native-gpu-8ba9ed74.zip`. It requires
the existing verified QEMU package as its runner argument. It does not replace
the installed app or engine. Executables and the large archive are separate
deliverables; this repository contains their source, patches and provenance.

`reims-build.json` records the exact Cargo resolution, Rust/NDK tools, stable
before/after source snapshots, raw archive and localized exports. The actual
build used Rust 1.98.1, NDK r29 and one compiler job. The existing Android
desktop-window `dead_code` exception is recorded; other Rust warnings remain
errors. The machine-specific dependency override and lockfile are retained as
build inputs, separate from the portable source patch. Every changed tested
source file matches its committed blob and the reconstructed patch tree.

`owner-build.json` records static linking against that archive, exact supervisor
reuse, required C symbols, zero Clang static-analysis findings and 16 KiB ELF
load alignment. Its immutable status describes the pre-device build. The later
device record above supplies the completed qualification.

## Host validation and limits

| Check | Result |
| --- | --- |
| Actual ownership and registry source tests | 7 passed |
| Actual C export source/header boundary tests | 2 passed |
| New producer/example Clippy harness | Passed with warnings denied; actual source symlinks |
| C API and window Clippy with Vulkan and SDL no-link | Passed with warnings denied |
| Changed Rust formatting | Passed |
| Real runtime upload, owned AIR compute and independent readback | Passed on lavapipe, all 8,192 words |
| Public-owner release with CPU/native leases retained | Passed |
| Abandoned CPU epoch | Later CPU and GPU access refused |
| Khronos validation | Instance/device layer insertion observed; synchronization setting enabled; no VUID or synchronization-hazard diagnostics reported |
| Lavapipe POSIX alias preflight | Refused: the opaque FD did not expose the diagnostic's expected byte layout |
| Full `cargo xtask check` | Failed on unchanged formatting/lint findings and missing CMake |

The runtime example's canonical-only mode does not qualify opaque-FD POSIX
mapping. Its explicit alias run exited 1 before registration or writes, with
`OPAQUE_FD_POSIX_ALIAS_UNQUALIFIED`. Pixel uses the separately qualified full-map
and selected-view provider in the unchanged native engine. These are distinct
results; the failed host alias route is not counted as a pass.

`host-validation.json` and the complete selected logs identify every check.
The broader gate's failures remain visible. No comparison, expected file or
baseline lint was loosened. The only newly reported loop lint was corrected
before the final Android build. The unchanged QEMU register regression was not
rerun. `source-review.json` records root's direct review; parallel workers were
authentication-blocked, so there is no independent worker sign-off.

## Startup correction and transfer

The first invocation of this same owner exited 134 before producer creation.
Reims selected `/.cache/reims-vgpu-vulkan` from the root-shell environment; the
runtime refused Android's read-only root. The corrected runner creates a new
empty cache under its private result directory, removes `HOME` only in the
owner child's environment, and supplies `XDG_CACHE_HOME` for the runtime's
existing fallback. The caller's environment and security settings stay intact.
The owner binary is byte-for-byte unchanged. The successful run used this
corrected runner and a fresh cache.

The initial owner update used 18 checked terminal parts. The launcher correction
needed one 26,669-byte payload archive plus the unchanged, re-hashed owner delta.
The phone reconstructed and verified all seven package files, rechecked the
existing QEMU package, and only then executed the runner. Local reconstruction
of both transfer forms also verified all seven files without execution.

`package.json`, `update.json`, `transfer.json`, `install-update.py`,
`assemble-transfer.py` and `package-SHA256SUMS` identify the final artifacts.
`startup-cache-failure/` preserves the earlier package metadata. The
[experiment directory](../../experiments/reims-native-gpu/README.md) contains
the build, packaging, transfer and evidence-collection tools.

Complete raw logs and a machine-readable record for both attempts were copied
into the phone's project download directory. Local device fields and phone-side
hashes are explicitly console transcriptions; the raw logs were not downloaded.
The browser JPEG was preserved byte-for-byte.

## Next integration boundary

This completes the allocation identity, retained lifetime and noncoherent
ownership layer for an explicit serialized native/reims handoff. The C
constructor still owns a selected device; it is not attached to an existing
`RvgDevice`. Rust `Producer::new` can accept the embedding's actual logical
device. Equal physical adapter IDs do not prove that logical-device identity.

The product still needs shared-device/region ownership, native mapping updates,
guest gather/remap registration and resource-lifetime hooks, and CPU/GPU handoffs
at every guest-visible event. Fragmented resources require a separate design.
Dynamic mappings, concurrent vCPUs, producer atomics, app UID, suspend/resume,
and an iOS 26 boot or frame remain unqualified. The product GPU gate is unchanged.
