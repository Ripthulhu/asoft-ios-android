# Pixel PowerVR memory paths

Audit date: 2026-11-21. **The current same-page DMA-BUF route is refused by the
phone's Vulkan buffer queries. Producer-owned backing is a separate engineering
path; it is not implemented as guest RAM by these patches.**

## Evidence and source revisions

The inspected prepared sources are reconstructible from the ordered patch
manifests; their commit IDs are not claims that these dependency branches were
published separately:

| Prefix used below | Prepared revision | Patch manifest |
|---|---|---|
| R: `reims-vgpu` | `2e568fba381bca9470e2df14c7029c3a402797b0` | [reims-series.json](patches/reims-series.json) |
| M: `metal2vulkan` | `ffda2ffd9485b6796ad8ca49bc024bf97401342c` | [metal2vulkan-series.json](patches/metal2vulkan-series.json) |

The physical Pixel 10 Pro XL reported PowerVR D-Series DXT-48-1536 MC1,
driver `26.1@6967606` / `0x006a5136`, device API 1.4.344. The root capability
reporter completed using an effective Vulkan API of 1.3. The execution evidence
below identifies the ordinary application context subsequently tested.

| Observed declaration or result | Meaning and limit |
|---|---|
| All 17 `DMA_BUF_EXT` buffer usage rows: features `0x0` | No import/export support in this matrix; includes runtime `0x1ff` and BDA `0x201ff`. All queried create flags were zero. |
| All 17 `OPAQUE_FD` rows: features `0x6` | Importable and exportable, not dedicated-only. The 32 KiB v1 execution test below qualifies one concrete allocation. |
| All 17 Android hardware-buffer rows: features `0x6` | Same declared buffer support; does not establish a usable AHardwareBuffer allocation or persistent CPU access. |
| `VK_EXT_external_memory_host` absent | Existing arbitrary host-pointer import cannot be selected. |
| Memory type 1: flags `0x7` | Device-local, host-visible, host-coherent. Actual buffer requirements and imported payloads must allow this type. |
| Sparse binding/residency-buffer: true; residency-aliased: false | Sparse binding alone does not qualify overlapping page gathers. `SPARSE_ALIASED` cannot be enabled. |
| BDA and BDA capture/replay: true | Feature declarations, not shader-address execution results. |
| Original DMA probe: unsupported before exporter open | No memfd export or DMA-BUF memory round trip occurred. Kernel UDMABUF presence does not override Vulkan refusal. |

See [the device record](results/2026-11-21/README.md) and
[the reporter contract](VULKAN-CAPS.md). **The v1 producer probe passed on the
phone as root: a 32,768-byte Vulkan allocation, opaque-FD export/import, both
Vulkan mappings, and native `MAP_SHARED` at offset zero all shared the tested
bytes in both CPU/GPU directions; exit status was zero.**

Both buffers required 32,768 bytes with 4,096-byte alignment, type mask `0x7`
and no dedicated allocation. Memory type 1 (`0x7`) was selected. The two Vulkan
mappings were distinct and page-aligned; the exported FD reported size 32,768
and mode `0600`. Each full-range check covered 8,192 words. Native writes were
visible through both Vulkan mappings and GPU readback; GPU fills were visible
through all three CPU mappings.

**v2 repeated those successful phases, then returned CPU-scatter unsupported
(exit 4).** Its requested CPU page order was `{5,0,7,2}`. The first check,
slot 0 / source page 5 / word 0, read `0x7b620000` (page 0's value), rather than
`0x7b620005`. It stopped before any scatter writes; the later repeated-alias
remap and scatter-related GPU checks did not run. Cleanup completed. This is a
counterexample to the FD-offset mapping contract reims needs, not proof about
every offset or the exporter's implementation. No scattered GPU resource,
integrated guest RAM, or runtime adoption was tested.

The ordinary diagnostic APK reproduced query/tile PASS, producer/full native mapping PASS, and the same page-5/page-0 mismatch with opaque exit 4.
App and native UID/EUID were 10441; SELinux domain `untrusted_app_34`, target SDK 35.
This qualifies those standalone probes in that app context; the rebuilt ASOFT application and other execution domains remain untested.

**v3 `--move-page` passed as root and in the tested ordinary app (exit 0).** A separate full offset-zero mapping
was verified across 8,192 words before page 5 was moved into a fresh one-page
reservation. The moved page's 1,024 initial words were correct. Writes reached
all canonical views and GPU readback while seven guard pages stayed unchanged;
GPU fill reached the moved page. Cleanup released only the five-page source
prefix, two-page suffix and destination, leaving the vacated source hole alone.
This proves one alternative CPU page move, preserving v2's direct-offset
failure. The app run completed at `2026-11-21T14:30:43Z`, UID/EUID 10441,
domain `u:r:untrusted_app_34:s0:c185,c257,c512,c768`, target SDK 35;
query, tile and opaque-move stages all exited zero. GPU page gather was not tested.

## Boundaries in the current code

| Boundary and actual source paths | Existing contract |
|---|---|
| R `crates/reims-vgpu-c/src/device.rs`, `crates/reims-vgpu-c/src/device/unix.rs`: `RvgMemoryRange`, `RvgMemoryRangeFile`, configuration conversion | Caller supplies a stable CPU address and optional FD/offset per RAM range. File-backed memory must be a `MAP_SHARED` mapping of that FD at that offset; registration duplicates the FD and validates its extent. No Vulkan/AHB owner token is carried. |
| R `crates/reims-vgpu-vulkan/src/os.rs`, `crates/reims-vgpu-vulkan/src/os/linux/files.rs`, `crates/reims-vgpu-vulkan/src/os/linux/vm.rs` | `GuestRamFile` and file-piece tracking resolve CPU aliases back to original file offsets. `remap_shared_overwrite` builds aliases with `MAP_SHARED | MAP_FIXED` over owned reservations. A `vkMapMemory` pointer alone supplies no equivalent file/remap contract. |
| R `crates/reims-vgpu-core/src/memory/map.rs`, `crates/reims-vgpu-vulkan/src/os/linux/deferred.rs` | Guest physical ranges become CPU-contiguous views, including scattered pages. Deferred views retain backing metadata and materialize file pieces on demand. |
| R `crates/reims-vgpu-vulkan/src/gpu/device.rs`, `crates/reims-vgpu-vulkan/src/gpu/backing.rs`, `crates/reims-vgpu-vulkan/src/os/linux/import.rs` | Guest no-copy buffers and heaps enter `os::host_memory`; gather/replacement preserves shared pages, deallocators, address placement and in-flight lifetimes. Replacement uses fresh backing rather than remapping under a live import. |
| M `crates/metal2vulkan-runtime/src/buffer_descriptor.rs`, `crates/metal2vulkan-runtime/src/heap.rs` | Ordinary Shared buffers and heaps already allocate Vulkan-owned, persistently mapped memory. Heap placement supports contiguous views and Metal address placement; it is not arbitrary page gather. |
| M `crates/metal2vulkan-runtime/src/wrapped_buffer.rs`, `crates/metal2vulkan-runtime/examples/adopted_buffer.rs` | `Device::new_buffer_with_vk_buffer` accepts a bound caller-owned buffer, `VkBufferMemory` and optional CPU pointer, bypassing host/FD import. Shared storage requires coherent read/write mapping, full runtime usage and required BDA allocation flags. |
| M `crates/metal2vulkan-runtime/src/gather.rs`, `crates/metal2vulkan-runtime/src/host_memory.rs` | `GatherPiece` carries host ranges, not owned Vulkan allocations. `gather_granule` requires the pointer importer; `host_chunk` imports host memory. Existing sparse-bind mechanics do not supply a producer-owned route. |
| M `crates/metal2vulkan-runtime/src/rebind.rs`, `crates/metal2vulkan-runtime/src/interop.rs`, `crates/metal2vulkan-runtime/src/buffer.rs` | Rebinding requires a host-backed `HostCell`. Wrapped/ordinary owned buffers lack it. Public interop exposes a buffer/offset and CPU contents, but no general runtime allocation-owner/export API. |

The wrapper fixes address placement to `Any`, rejects sparse buffers, and has
no public adopted-heap constructor or release callback. The caller must retain
its buffer, allocation and mapping through all runtime uses and submitted work.
There is no existing AHardwareBuffer allocation/import/ownership integration
in these inspected reims and m2v paths.

## Meaning of the producer-owned results

The probes use **new Vulkan-owned storage**, not existing memfd pages. Their
opaque import uses the original allocation size/type and consumes a duplicate
FD; the retained export FD supplies the separate native mapping observations.
The GPU uses one contiguous imported buffer and a third independent readback
allocation, with memory dependencies and bounded fences. CPU mappings are not
external queue families. Native opaque-FD mmap/mremap behavior is driver-specific.
Do not relabel arbitrary memfds or query `vkGetMemoryFdPropertiesKHR` for opaque FDs.

The 32 KiB results do not qualify refaulted pages, repeated moved aliases,
long-lived views, guest-sized allocations, shader BDA access, runtime adoption
or iOS boot. Moving CPU mappings does not construct matching GPU page aliases.

## Integration changes still required

1. **Create an allocation/session boundary before RAM registration.** The C API
   currently consumes an existing memory map. Expose producer allocation on the
   same runtime logical device that will consume it, before the CPU engine takes
   its RAM pointer, and retain an owner token across all views. Standalone probe
   handles cannot simply be passed into a different runtime `VkDevice`.
2. **Add a CPU alias provider.** The existing FD-offset path fails this payload.
   v3 supplies a possible basis: disposable full offset-zero views and explicit
   page moves with exact surviving-range ownership. Reims needs allocation/page
   identity and alias creation/destruction, beyond `Backing { fd, offset }`.
   Refault, repeated aliases, protections and deferred-view lifetime need qualification.
3. **Bridge before `os::host_memory`.** In reims' `gpu/device.rs` and `gpu/backing.rs`,
   recognize owned allocation/offset/type, CPU mapping and lifetime provenance.
   The first bounded runtime target is a contiguous owned range adopted through
   m2v's existing `new_buffer_with_vk_buffer`, using the consumer device's usage,
   BDA and sharing requirements. Sending its pointer through `HostMemory` would
   re-enter the unavailable host-import path. This bridge is not implemented.
4. **Keep GPU gather a separate contract.** Initially refuse resources requiring
   unsupported scattered GPU views. Current gather imports host chunks; it needs
   a new route for producer allocations. The Pixel cannot enable `SPARSE_ALIASED`.
   Any sparse design needs its exact buffer flags, external contract, granule and
   alias semantics qualified; the flags-zero matrix and CPU move are not that proof.
5. **Preserve rebind, heap and command lifetimes.** Add an explicit owned-backing
   variant or suitable adoption APIs for pinned addresses, heaps, detach/rebind
   and deferred destruction. Sharedness and synchronization must survive
   overlapping resources. Replacing no-copy with copy needs a distinct dirty
   tracking and synchronization design, not a descriptor substitution.

AHardwareBuffer is a conditional alternative allocator, not a same-page
exporter. A buffer import needs a BLOB allocation with GPU-data-buffer usage and
the allocation-specific size/type information. `AHardwareBuffer_lock` grants
temporary access and may copy or reformat; its pointer is not a substitute for
the runtime's persistent coherent mapping. No raw native-handle FD layout is
assumed. Its CPU alias and lifetime requirements remain to be solved.

## Primary specification references

- [External buffer properties](https://docs.vulkan.org/refpages/latest/refpages/source/VkExternalMemoryProperties.html): capability bits have separate meanings.
- [Opaque import parameters](https://docs.vulkan.org/refpages/latest/refpages/source/VkMemoryAllocateInfo.html) and [FD ownership](https://docs.vulkan.org/refpages/latest/refpages/source/VkImportMemoryFdInfoKHR.html).
- [External handle types](https://docs.vulkan.org/refpages/latest/refpages/source/VkExternalMemoryHandleTypeFlagBits.html): opaque handles are not arbitrary memory files.
- [Memory aliasing](https://docs.vulkan.org/spec/latest/chapters/resources.html) and [sparse aliasing](https://docs.vulkan.org/spec/latest/chapters/sparsemem.html).
- [Android hardware-buffer extension](https://docs.vulkan.org/refpages/latest/refpages/source/VK_ANDROID_external_memory_android_hardware_buffer.html): mapping, locking and import semantics.
- [Android common 6.12 mremap implementation](https://android.googlesource.com/kernel/common/+/refs/tags/android16-6.12-2025-06_r3/mm/mremap.c): a related kernel baseline, not the exact running Pixel source.
