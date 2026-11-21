# Pixel PowerVR probes

Two Android ARM64 execution probes and a query-only reporter for the proposed
graphics paths on a Pixel 10 Pro XL running ASoftware iOS for Android. The
package includes executables, authored shaders, source, build scripts, and
candidate `metal2vulkan`/reims patches for color framebuffer reads and shared
memory.

**Phone result, 2026-11-21: the tile-image probe passed both cases on the
Pixel's PowerVR GPU under KernelSU root. The DMA-BUF probe returned
`UNSUPPORTED` because Vulkan did not advertise import support for its
storage/transfer buffer.** It stopped before exporting or importing memory.
See the [device test record](results/2026-11-21/README.md) for the driver/build,
screenshots, and precise scope. The application and its compatibility check
are unchanged; this remains a source candidate and diagnostic kit, not an APK
with qualified PowerVR support.

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
allocating GPU resources or submitting work. That reporter has host validation
and source review, but has not yet run on the Pixel. The existing ADB runner
still runs only the two execution probes.

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
