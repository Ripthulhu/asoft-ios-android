# PowerVR backend candidate

This directory contains standalone phone probes and dependency patches for the
Android fork's Vulkan backend. The patches implement an initial color-fetch
route and memory-import changes needed to investigate PowerVR. They have not
established Pixel GPU support. The app still needs rebuilt native libraries;
hardware execution remains a separate qualification.

## Source bases

| Repository | Branch inspected | Base commit |
|---|---|---|
| `alpersamur3/asoft-ios-android` and `Ripthulhu/asoft-ios-android` | `main` | `b9b930d6d4771daa0c5e2df6104ff45e2567da2d` |
| `alpersamur3/metal2vulkan` | `asoft-android` | `5951098336923a231a011578d8722449a3981034` |
| `alpersamur3/reims-vgpu` | `asoft-android` | `3e0467e64b4c21b6087ae3589388fec5154fb0cb` |

The ordered patches and application instructions are in
[patches/README.md](patches/README.md). [VALIDATION.md](VALIDATION.md) distinguishes
source checks, software Vulkan execution, and outstanding phone tests.

## Color framebuffer reads

The Pixel report in upstream issue 94 advertises `VK_EXT_shader_tile_image` but
neither of the backend's existing attachment-ordering mechanisms. It is another
user's report; this package has not measured the current phone or driver.

The compiler candidate queries the actual tile-image color-read feature and
dynamic rendering, with an effective Vulkan API of at least 1.3. It emits
`TileImageEXT` variables, fixed attachment `Location` decorations,
`TileImageDataEXT`, and `OpColorAttachmentReadEXT`. It does not substitute the
tile extension for rasterization-order attachment access or fragment interlock.
No noncoherent tile-read mode is emitted.

Attachment locations and numeric classes travel in pipeline metadata and the
cache format. These reads need no input-attachment descriptor. Existing
rasterization-order attachment and pixel-interlock choices retain their
priority and established representations.

The runtime candidate supplies matching dynamic-pipeline formats, secondary
command-buffer inheritance, and rendering attachments. Its deferred recorder
owns copies of the pointed-to format and attachment arrays. Ordinary depth and
stencil coattachments use explicit layout transitions and independent aspect
load/store operations.

Each tile-reading draw currently ends its rendering instance. Full memory
barriers run between instances, and load/store operations preserve attachment
contents. This avoids legacy in-pass barriers that are invalid in the tile-image
dynamic path. It adds a store/load boundary per draw; PowerVR performance is
unmeasured.

### Initial rendering scope

| Form | Candidate behavior |
|---|---|
| Single-sample, directly represented float/normalized or unsigned color fetch | Coherent tile-image reads when the real device features permit them |
| Ordinary depth/stencil tests alongside those color attachments | Dynamic attachments and explicit transitions |
| Existing rasterization-order attachment or pixel-interlock support | Retain the existing path |
| Signed, sRGB, extended-range or other converted tile-fetch formats | Typed refusal |
| Multisampling, resolves, multiview, remapped color locations | Typed refusal in the initial dynamic path |
| Mixed legacy input attachments or interlocked storage, shader depth/stencil, fragment imageblocks, rasterization-rate maps, capture/rerouting, color regrouping, indirect-command-buffer replay | Typed refusal where the dynamic contract is not implemented |
| General Metal raster-order groups | Still require the existing interlock mechanism |

The compiler also checks the dataflow of fetched values. Without assuming
defined reads from helper invocations, it refuses cases where those values
could affect covered fragments through derivatives, implicit samples,
subgroup operations, unsafe control/address operations or external stores.
This is a bounded implementation, not general Metal framebuffer-fetch support.

## Sharing the original memory pages

The first memory patch backports capability separation from upstream
[`12a8a907`](https://github.com/steelbrain/metal2vulkan/commit/12a8a907bcdd3c7ae5683ee436e83e42fd6397a4).
The importer can use DMA-BUF when `VK_EXT_external_memory_host` is absent.
Pointer-only operations still refuse inputs that the device cannot import.

The deferred-view patch adds `HostMemory::with_gather_and_dma_buf`. Before a
DMA-BUF fallback, the gather source must materialize the entire aligned CPU
window and explicitly answer `GatherAnswer::Pointer`. The runtime checks that
this mapping is writable on Linux/Android, then asks the file exporter for the
same pages. A copied allocation cannot satisfy that contract. The mapping must
remain alive independently of whether the gather callback is retained.

Reims supplies this paired source for deferred/idle views only when the device
lacks the host-pointer extension. Devices that enable that extension keep the
existing gather policy; its presence still does not guarantee that every
particular pointer is importable.

For a read-only deferred view on a device without the extension, reims reuses
its existing writable-twin mechanism. The twin maps the same file-backed pages
while the original remains deferred and read-only. Writable views can instead
be materialized by the paired source. This policy is per device.

The detached-buffer temporary now requests the existing aliasable allocator.
On Linux/Android this produces sealed memfd backing that remaps and exports
can track. Ordinary reservations and fixed-overwrite machinery retain their
existing roles. The temporary now consumes a file descriptor and inherits the
allocator's fatal file-creation, truncate and sealing failure behavior.

### Conditions still needed on the phone

The runtime needs a kernel exporter for the original pages, access from the
actual app process, compatible `HOST_VISIBLE | HOST_COHERENT` Vulkan memory,
and support for its exact buffer usages, including storage and device address.
Alignment, exporter size/list limits, sparse binding, aliasing, lifetime and
cache ownership remain part of that contract.

The DMA probe uses explicit `DMA_BUF_IOCTL_SYNC` cache handoffs. The runtime
candidate does not add those ioctls, so a probe pass alone does not qualify the
runtime's coherency behavior. The probe reports its required memory class
separately from its transfer result for the same reason.

KernelSU root can reveal an access restriction. It cannot supply an absent
kernel exporter or missing Vulkan semantics. An absent `/dev/udmabuf` alone
does not establish that the driver is missing; inspect registration and kernel
configuration as well. DMA heaps and Android hardware buffers allocate new
storage and do not, by themselves, export arbitrary existing guest pages.

Guest capability advertising remains conservative:
`SupportsResourceDetachBacking` still keys off the host-memory extension at
this dependency base. No capability is advertised merely because these patches
were applied.

## Enabling an application build

Reims must negotiate a Vulkan 1.3 instance only when its loader supports it;
the runtime's default 1.2 instance cannot expose tile images. The candidate
negotiation keeps that default for an older or unqueryable loader, and the
runtime still validates the explicit version and physical device.

The Android repository consumes separately built QEMU/reims/metal2vulkan
libraries. These source patches do not replace those binaries automatically.
Keep the app's support check until the actual patched backends have passed
device tests, then exercise a real iOS boot and rendering workload. Compiler
tests, software Vulkan execution, standalone phone probes, and a successful
Android build each establish different parts of that evidence.

## Primary references

- [Pixel 10 Pro XL report, issue 94](https://github.com/alpersamur3/asoft-ios-android/issues/94).
- [Khronos tile-image proposal](https://docs.vulkan.org/features/latest/features/proposals/VK_EXT_shader_tile_image.html).
- [SPIR-V tile-image extension](https://github.khronos.org/SPIRV-Registry/extensions/EXT/SPV_EXT_shader_tile_image.html).
- [Linux DMA-BUF documentation](https://www.kernel.org/doc/html/latest/driver-api/dma-buf.html).
