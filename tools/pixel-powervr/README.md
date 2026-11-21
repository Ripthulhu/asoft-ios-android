# Pixel PowerVR probes

Android ARM64 execution probes and a query-only reporter for the proposed
graphics paths on a Pixel 10 Pro XL running ASoftware iOS for Android. The
package includes executables, authored shaders, source, build scripts, and
candidate `metal2vulkan`/reims patches for color framebuffer reads and shared
memory.

**Phone results, 2026-11-21: tile-image rendering passed, and a new allocation
created by Vulkan passed opaque-FD export/import and CPU/GPU sharing tests.**
Both results were reproduced in a permission-free diagnostic APK under an
ordinary `untrusted_app_34` UID, as well as in the root shell. Mapping page 5
directly through the exported FD instead exposed page 0's contents; that
CPU-alias phase stopped before writes.
A separate v3 experiment then moved a verified page from a full offset-zero
mapping and passed both CPU/GPU directions, guard checks and cleanup under
root and the ordinary app UID. That is a bounded alternative for one CPU page,
with the GPU buffer still canonical and contiguous.
The original attempt to import existing pages through DMA-BUF remains
unsupported: all 17 tested buffer-usage combinations returned no import
features. The working opaque-FD experiment starts with a new Vulkan allocation;
it does not import arbitrary existing guest pages.
See the [device test record](results/2026-11-21/README.md) for the driver/build,
screenshots, and precise scope. The application and its compatibility check
are unchanged. The included APK is a standalone diagnostic harness; it does
not integrate the candidate into ASoftware or qualify iOS GPU support.

The later [real Metal runtime probe](experiments/runtime-probe/README.md) passed
on-device AIR translation, producer-backed compute and two floating-point
framebuffer-fetch cases under root and the ordinary app UID. Ordinary anonymous
and memfd fixed-code execution also passed in both contexts. A
[native alias test](experiments/native-alias/README.md)
passed two 16 KiB data aliases but failed during direct code execution; its
fresh-child stage was not reached. The fast native EL0 route remains required
and is not yet qualified. The [iOS 26 integration plan](ios26-build/INTEGRATION-PLAN.md)
records the build inputs and remaining engine work.

A separate [copied-code experiment](experiments/native-code-cache/README.md)
caused a **kernel panic during the CPU-memory preflight**. Recovery found
`kernel_panic,asynchronous_serror_interrupt` and a retained pstore record for
`native_code_cac`. The PC/LR pair matches the frozen executable immediately
after the interrupted process's first aligned LSE set call, before its view
check, restore, or copied-code execution. Parent/child identity and any earlier
parent results remain unknown: a later continuation reverified the frozen
binary on the phone, but did not find the expected test log in the retained
run directory or the scoped search. Asynchronous delivery does not identify the exact
faulting instruction or CPU memory attribute. Do not repeat this uncached
producer-memory atomic test; its userspace timeouts cannot contain a kernel
panic. The [recovery record](results/2026-11-21/native-code-cache-panic-recovery.json)
supersedes the original unknown-outcome observation. CPU-cached producer
memory is a separate candidate and needs explicit CPU/GPU cache synchronization.

The separate [cached-memory diagnostic](experiments/cached-memory/README.md)
now passed its default root-shell run with
**`CACHED_MEMORY_BASIC_PASS_ATOMICS_NOT_TESTED`**. The 32 KiB cached,
noncoherent producer allocation passed ordinary CPU accesses, moved aliases,
fresh-exec child checks and serialized CPU/GPU handoffs. Producer LSE remained
disabled; the separate ordinary-memfd control exercised two LSE calls before
Vulkan initialization. See the [retained result](results/2026-11-21/cached-memory-root.json)
for the exact memory flags, exit status and evidence limits. The completed
[Android QEMU build](ios26-build/reconstruction/README.md) is also preserved.
[CONTINUE.md](CONTINUE.md) records the current device and source checkpoint.

A separately linked [required-native QEMU candidate](ios26-build/required-native/README.md)
now stops on native startup, factory or worker-initialization failures. Its
ordinary-memfd benchmark requires positive native counters and successful guest
checks. It now executed real native guest code on the phone: the retained
stdin-only control recorded 415,727 native entries and 404,036 native SVCs.
Both CPUs passed floating-point and copy checks, but both reported
`T7 tpidr=0x1234 tpidrro=0x0 MISMATCH`. The benchmark therefore **failed
correctness despite QEMU exit zero**. The [native result](results/2026-11-21/qemu-native-root.json)
separates these observations from source diagnosis and the earlier stalled
launch. A later checker revision fixes the CPU-prefixed completion format
without changing that executable. The QEMU candidate still uses the existing
memory backend and has no cached PowerVR provider.
The separately built [generic TPIDRRO trap candidate](ios26-build/tpidrro-trap/README.md)
then **passed the strict root-shell benchmark** without changing the guest.
Each CPU retained writable TPIDR `0x1234`, read its correct guest TPIDRRO,
passed FP/copy/completion checks, and reported two native traps ending at the
exact later T7 read. Its [device result](results/2026-11-21/qemu-tpidrro-trap-root.json)
records 415,536 native entries and 404,036 native SVCs, with runner/QEMU exit 0.
The binary was reconstructed through a verified local delta in the existing
Tango shell; all 22 package files matched before execution.

Both separate root-shell baselines now pass. The
[one-region native proof](ios26-build/ONE-REGION-NATIVE-PROOF.md) is the next
integration under implementation. It has no combined device result yet and
does not enable the app's GPU support gate.

## Ordinary-app test

[app-runtime-probe/README.md](app-runtime-probe/README.md) describes the latest
signed diagnostic APK, versionCode 3 / `1.2-runtime`. All four stages passed on
the Pixel: ordinary anonymous and memfd code execution, actual Metal compute,
and translated floating-point tile fetch. The app requested no permissions,
ran as UID 10441 in `untrusted_app_34`, and global SELinux remained Enforcing.
These are bounded tests, not an integrated native-EL0 engine or iOS boot.

[app-probe-v3/README.md](app-probe-v3/README.md) describes the earlier signed diagnostic APK,
its source, exact payload hashes, installation and report collection. Opening
it runs the query reporter, tile-image probe and opaque-FD v3 `--move-page` experiment under
the app's own UID. It requests no Android permissions and does not use root.
That tested combination passed on the Pixel. The earlier
[v2 diagnostic](app-probe/README.md) is preserved with its direct-offset
counterexample; v3 does not claim to repair that behavior.
The original ADB runner described below remains separate.

## Run on your phone

You need Python 3.10 or later and Google's
[Android platform-tools](https://developer.android.com/tools/releases/platform-tools)
on your computer. Use an existing authorized USB or network ADB connection.
Close any running iOS session before the GPU tests.

1. Extract the complete package, or open this directory in the repository.
2. Check that `adb devices` lists your phone as `device`.
3. Run the command below from this directory. When requested, authorize the
   ADB shell's root access in KernelSU.
4. Return the generated `pixel-powervr-results-*.txt` file for interpretation.

Windows:

```powershell
py -3 run.py
```

Linux or macOS:

```sh
python3 run.py
```

`run.cmd` and `run.sh` are convenience wrappers. If ADB is not on PATH, pass its
full path, for example:

```powershell
py -3 run.py --adb "C:\Android\platform-tools\adb.exe"
```

For a network connection, connect using `adb connect PHONE_ADDRESS:PORT` first.
If more than one device is attached, use `--serial` with the exact identifier
shown by `adb devices`. `--no-root` runs only the shell tests.

The runner verifies the four executable/shader checksums, copies files into a
fresh `/data/local/tmp/pixel-powervr.*` directory, runs tests sequentially, and
removes that directory afterward. It collects the phone/build identity, kernel
configuration where readable, relevant memory-exporter nodes, and Android's
Vulkan report. It uses root for a second memory test and kernel diagnostics.
It does not change SELinux, device-node permissions, kernel modules, boot images,
or ASoftware settings.

GPU fences have five-second limits. Each probe also has a 60-second process
timeout. A failed or crashed probe stops later GPU tests and leaves the partial
report. Capability-unavailable results allow the remaining independent tests.
`--keep-remote` retains the temporary files for manual investigation.

## What the tests establish

### Ordered framebuffer reads

`tile_image_probe` queries and enables `VK_EXT_shader_tile_image` and its
`shaderTileImageColorReadAccess` feature. It uses dynamic rendering and coherent
color reads; it does not enable the noncoherent execution mode.

It draws overlapping full-screen triangles into a 32 x 32 single-sample
`R8G8B8A8_UINT` attachment. Every fragment reads the existing color and updates
three exact integer recurrences. The first detects lost updates; the others
depend on primitive order. Every pixel must match the expected result.

| Case | Operation | Expected RGBA bytes |
|---|---|---|
| Within one draw | 32 overlapping primitives | `[32, 208, 208, 255]` |
| Across draws | Two draws of 32 primitives, no intervening barrier | `[64, 160, 160, 255]` |

A pass establishes these integer, single-sample color-ordering cases on the
tested driver. It does not establish Metal translation, floating-point formats,
MSAA, depth/stencil behavior, general raster-order groups, or iOS rendering.
The `shaderTileImageCoherentReadAccelerated` property is reported, but a false
value is not a capability failure: that property concerns acceleration.

### Sharing the original CPU memory with Vulkan

`dmabuf_probe` creates an eight-page `memfd` with `F_SEAL_SHRINK`, then asks
`UDMABUF_CREATE_LIST` to export four discontiguous pages in order `{5, 0, 7, 2}`.
It queries and imports that actual FD as a storage/transfer-capable Vulkan
buffer. The tests check both directions:

- CPU writes through the original memfd mapping, then GPU copy and CPU readback
  verify every exported word.
- GPU fills each logical page with a different value, then the CPU checks the
  original mapped pages and their order.

The program uses DMA-BUF cache-maintenance calls, foreign queue ownership
transfers, fenced submissions, and readback invalidation when required. It also
reports CPU-visible values of the unexported guard pages. Those guards are
outside the exported DMA-BUF's cache-maintenance range, so their CPU-visible
values cannot prove the absence of all out-of-bounds GPU writes.

The memory probe reports whether a compatible `HOST_VISIBLE | HOST_COHERENT`
memory type exists and prefers it. The candidate runtime still requires that
class; a transfer-only pass using another class does not satisfy that runtime
requirement.

This is a small-buffer test. It does not establish shader access, device
addresses, sparse binding, images, large guest RAM windows, arbitrary malloc
import, Android app sandbox access, or complete ASoftware compatibility.

## Reading results

The report records each program's exit code. The runner itself can finish
successfully even when a capability is unavailable; read the probe results.

| Probe result | Meaning and next investigation |
|---|---|
| Tile `PASS` (0) | The two tested color-ordering cases work. This supports implementing a genuine tile-image lowering and dynamic-rendering backend. |
| Tile `UNSUPPORTED` (2) | A required API, feature, format, or resource capability is absent. The extension's name alone is insufficient. |
| DMA `PASS` (0) | The tested original-page transfer route works. Also check its runtime memory-class result before treating the candidate importer as eligible. |
| DMA `BLOCKED` (2) | A prerequisite is inaccessible or absent. Compare shell/root results and `/dev/udmabuf` diagnostics. |
| DMA `UNSUPPORTED` (3) | The tested exporter or Vulkan import contract is unavailable. The log names the missing step. |
| Either probe `FAIL` (1), timeout, or crash | Stop further GPU work and inspect the saved API result or byte mismatch. The runner does this automatically. |

If root succeeds where shell is blocked, we have evidence of a permissions or
policy boundary. If the kernel has no exporter, UID 0 cannot supply its missing
implementation. An absent device node alone is not proof that the kernel lacks
the driver: the diagnostic also checks its registered device and kernel config.

The tested phone does have a built-in, registered UDMABUF exporter. Its observed
failure was the Vulkan buffer-capability query, before node access or memory
export. [VULKAN-CAPS.md](VULKAN-CAPS.md) describes a follow-up reporter that
compares individual buffer usages and the exact runtime contract without
allocating GPU resources or submitting work. All 51 queries have now completed
on the Pixel. The original ADB runner still runs only the tile-image and DMA-BUF
execution probes. [MEMORY-PATHS.md](MEMORY-PATHS.md) explains what the tested
producer allocation changes and what reims integration still requires.
[OPAQUE-FD.md](OPAQUE-FD.md) documents the producer probe and its phase-specific
exit codes, including the observed unsupported page-offset mapping.
The [separate v3 experiment](experiments/opaque-move-v3/README.md) preserves the
exact source and executable for the successful one-page move.

`CONFIG_UDMABUF` is a built-in boolean in the inspected Linux/Pixel kernel source,
not a promise that a generic loadable `udmabuf.ko` can be installed. KernelSU
support does not establish which options your running kernel has enabled.
DMA heaps and Android hardware buffers allocate their own storage; their
availability does not prove they can export arbitrary existing guest pages.

## Candidate backend patches

See [patches/README.md](patches/README.md) for the ordered dependency patches.
They add a genuine tile-image compiler and dynamic-rendering path, separate
DMA-BUF imports from host-pointer support, and adapt deferred/readonly memory
views and detached-buffer backing. Their bounded rendering scope and remaining
device requirements are described in [BACKEND.md](BACKEND.md).

The patches are not applied automatically by the probe package or Android build.
Keep the app's support gate honest until the actual rendering and memory paths
have been implemented and exercised.

## Rebuild from source

The included binaries target ARM64 Android API 35 and use 16 KiB ELF segment
alignment. They link to Android's system Vulkan loader. Build using Android NDK
r29 and recent `glslangValidator` and `spirv-val` on PATH:

```sh
python3 build.py --ndk /path/to/android-ndk-r29
```

Use `--glslang` and `--spirv-val` for explicit executable paths. The NDK r29
bundled shader compiler is too old for this shader extension; use a newer
standalone glslang build. `build.py` downloads nothing. It recompiles both
shaders and C programs, validates SPIR-V, strips binaries, then refreshes
`SHA256SUMS` and `build-info.json`. The latter records the actual tool versions
and source hashes. See [VALIDATION.md](VALIDATION.md) for the checks performed
on this package and their limits.

## Primary references

- [Pixel 10 Pro XL upstream report, issue 94](https://github.com/alpersamur3/asoft-ios-android/issues/94).
  This is another user's driver report, not a measurement of your phone.
- [Khronos: VK_EXT_shader_tile_image](https://docs.vulkan.org/refpages/latest/refpages/source/VK_EXT_shader_tile_image.html).
- [Khronos: SPV_EXT_shader_tile_image](https://github.khronos.org/SPIRV-Registry/extensions/EXT/SPV_EXT_shader_tile_image.html).
- [Khronos: shader tile-image properties](https://docs.vulkan.org/refpages/latest/refpages/source/VkPhysicalDeviceShaderTileImagePropertiesEXT.html).
- [Linux DMA-BUF documentation](https://www.kernel.org/doc/html/latest/driver-api/dma-buf.html).
- [Linux UDMABUF implementation](https://github.com/torvalds/linux/blob/v6.6/drivers/dma-buf/udmabuf.c).
- [Khronos: importing an external-memory FD](https://docs.vulkan.org/refpages/latest/refpages/source/VkImportMemoryFdInfoKHR.html).
- [Upstream DMA-BUF-only importer change](https://github.com/steelbrain/metal2vulkan/commit/12a8a907bcdd3c7ae5683ee436e83e42fd6397a4).

The original probe code is MIT-licensed; dependency patches retain their
projects' original licensing. See the included notices.
