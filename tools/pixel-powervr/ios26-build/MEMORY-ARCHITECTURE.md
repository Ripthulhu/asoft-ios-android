# Pixel memory architecture audit

Read-only source audit, 2026-11-21. This is an implementation decision record,
not a claim that an iOS guest or native EL0 engine has run on the Pixel.

Sources inspected: metal2vulkan `ffda2ffd9485b6796ad8ca49bc024bf97401342c`
in `metal2vulkan-pixel-runtime`, reims
`2e568fba381bca9470e2df14c7029c3a402797b0` in `reims-pixel-memfd`, and QEMU
`7a900afb62ddf94713e38ac5a4aafe1d42c9efa8` in `qemu-pixel-producer-review`.
The independent producer-adoption worktree adds placement/token/owner lifetime
support; that addition does not implement GPU alias tracking.

## Current proven boundary

Root reports the frozen real runtime probe `0291f977...` passed both producer
compute and tile rendering on the physical Pixel. AIR translation happened on
the phone, followed by real Vulkan execution/readback. The producer test used
one contiguous 32 KiB allocation; the CPU move changed a CPU view, not its GPU
buffer layout. The later native-alias probe reached successful 16 KiB data
aliases and RW-to-RX protection, but did not complete the generated function
call. Its generic failure does not yet identify the signal or exact cause.

## The existing resident table is not a page table

`crates/metal2vulkan/src/memory/roots.rs` describes a pointer as `(root, offset)`.
The resident search resolves a loaded guest address once to an allocation root.
Pointer arithmetic retains that root. `lower/access/dynamic.rs::base_with` reads
one host base; `wide_at`, atomics and copy lowering use that base plus offsets.
`lower/access/psb.rs::prepare` likewise obtains one host base for a static slot.

Consequently, adding one `ResidentRange` per physical page is insufficient.
Crossing the first page either fails containment or accesses the next physical
bytes of that page's allocation, instead of the next logical page.
`bind/resident.rs::resident_set` also drops contained ranges and trims overlaps
with host and guest offsets advancing together. It is not an override map.
Runtime `buffer.rs::resident` returns one range and `live_buffers.rs` retains
one range per buffer.

| Consumer | Current contract | Required change for fragmented GPU bytes |
|---|---|---|
| Ordinary buffer arguments and loaded pointers | One VkBuffer/BDA root | New segmented backing and translation for every leaf/atomic/copy access, while preserving logical bounds and pointer identity |
| Argument buffers and unnamed residents | Loaded pointers resolve through resident roots | Publish logical roots and stable page mappings with command-lifetime ownership; retain all transitively resident allocations |
| Vertex attributes | Both fixed-function and pulled fetch paths exist | Explicitly select pulled fetch for fragmented inputs and route those reads through segmented access |
| Index and indirect inputs | `draw_source.rs::IndexBind` binds a real contiguous VkBuffer | Hardware-contiguous binding, or a separate semantically complete transformation/materialization path; existing rewrite passes solve specific index semantics only |
| Texel buffers | Real VkBufferView (`buffer_texture.rs`) | Separate shader lowering or a contiguous materialized view |
| IOSurface/2D textures | Surface first becomes a whole buffer; wrapped Vulkan buffers use shadow images | Fragmented buffer support and ordered shadow transfers. Existing wrapped-buffer textures are not a same-page image path |

The producer-adoption descriptor is therefore a useful contiguous bridge, not
general scatter support. Resolve CPU aliases to allocation identity, device
identity and source offset; coalesce adjacent runs; accept a resource only if
source offset equals one base plus logical offset throughout its full bind
span. Multiple input ranges are not automatically scatter: reims deliberately
cuts contiguous runs into smaller pieces.

Multiple contiguous VkBuffers over the same allocation additionally need a
physical alias key and access ranges. `buffer.rs::alias` currently covers host
imports only; wrapped buffers have distinct resource identities. An opaque
backing-owner token supplies lifetime, not hazard identity.

## Sparse route: narrow qualification only

The Vulkan sparse chapter permits fully bound noncontiguous buffers with
`sparseBinding`. Its separate aliasing rules require sparse-alias creation
flags for data-consistent aliased sparse resources. The Pixel reports
`sparseResidencyAliased=false`. Generic host-accessible buffer alias wording is
not a safe waiver for that explicit sparse requirement.

A defensible small experiment would fence earlier work, destroy the ordinary
producer VkBuffer, retain VkDeviceMemory and its CPU/FD mappings, and create one
fully bound sparse buffer with each selected physical page present once and no
other GPU binding. Query the exact `SPARSE_BINDING` flags, OPAQUE_FD handle and
usage first, and honor the returned memory alignment/type constraints. This
would qualify single-owner gathering, not repeated pages or simultaneously
overlapping guest resources. Existing `gather.rs` cannot simply consume the
producer allocation: it imports host-pointer chunks and creates sparse buffers.

Primary references:

- https://docs.vulkan.org/spec/latest/chapters/sparsemem.html#sparsememory-aliasing
- https://docs.vulkan.org/refpages/latest/refpages/source/VkBufferCreateFlagBits.html
- https://docs.vulkan.org/refpages/latest/refpages/source/VkSparseMemoryBind.html
- https://docs.vulkan.org/spec/latest/chapters/resources.html#resources-memory-aliasing

## A staging backend can preserve native EL0, but is a separate design

Ordinary memfd RAM can remain the CPU/native-stub backing while separate Vulkan
buffers hold GPU data. This does not require disabling native EL0. It does
require explicit coherence and cannot be described as shared physical pages.

Submission/completion copies alone are insufficient:

- Reims `resources/buffer/shared.rs` currently treats shared bytes as always
  guest-valid; `synchronize_with_cpu` is a no-op and `needs_sync` is false.
- Metal permits GPU work, a CPU event callback, and more GPU work inside one
  command buffer. Download must finish before publishing a CPU-visible signal;
  upload must occur after the corresponding CPU wait resolves.
- Runtime `command_buffer/batches.rs` already splits at such boundaries.
  `completion.rs::finish` currently publishes event reachability and wakes the
  scheduler before final command completion. A download hook after the usual
  completed callback would be too late.
- Independent per-resource replicas break overlapping physical aliases within
  one dispatch, including GPU atomic operations. End-of-batch merging cannot
  reconstruct their required single-location ordering. GPU atomics do not by
  themselves require CPU/GPU concurrent atomics, but replicas still cannot
  silently implement a cross-agent atomic/polling protocol if one is relied on.
- Whole-buffer copyback can overwrite CPU changes to bytes the GPU did not
  write. Access metadata is conservative, not a byte-accurate dirty mask.
- Loaded argument pointers, resource residency, multiple queues and IOSurface
  shadow images must join the same physical-page coherence/version model.

A bounded staging prototype should therefore initially admit only fully
enumerated disjoint resource pages, explicit ownership handoffs and no concurrent
CPU updates. It should refuse overlapping writable replicas, untracked dynamic
residency and unsupported event boundaries. Its first tests should include a
GPU-to-CPU-to-GPU shared-event exchange within one command buffer, overlapping
resource refusal before submission, and copyback preceding completion/status
visibility. That is a scoped diagnostic, not a general iOS compatibility claim.

Transfer cost is the sum of uploaded and downloaded dirty bytes per handoff,
plus copying overhead and extra storage. Illustratively, copying a 1920x1080
RGBA8 surface both ways at 60 Hz is about 0.995 GB/s of payload; CPU memcpy alone
reads and writes that payload, before GPU/shadow-image traffic. This is arithmetic,
not a measured Pixel bandwidth or frame-rate estimate. Whole resident-set copies
would be much more expensive than selected dirty ranges.

Primary event example:
https://developer.apple.com/documentation/metal/synchronizing-events-between-a-gpu-and-the-cpu

## Native executable bytes may use ordinary CPU memory

QEMU `target/arm/tcg/native-el0.c` already has a separate ordinary memfd code
cache (`cc_create`, 16 KiB slots), shared by stubs, and anonymous private code
copies (`patched_copy_install`). Both execute instructions natively. A producer
RAM policy could extend those mechanisms to clean read-only executable pages;
that would preserve the native engine rather than selecting TCG-only execution.

It is not already implemented: `cc_fill` returns `CC_CLEAN` for pages needing no
rewrites; `mirror_fill` and `fill_neighbours` then map guest RAM directly.
Writable executable pages bypass the copied-code path. Current cache comparison
occurs on refill, so a general extension must handle frame reuse, executable
aliases, JIT/self-modification, code/data reads and guest instruction-cache
maintenance. The `IC IVAU` helper found in `target/arm/helper.c` is guarded by
`CONFIG_USER_ONLY`, and does not establish cache refresh in this system engine.
No stale copied writable-code path should be enabled as a shortcut.

Frozen native probe disassembly has a correct `BLR`/return comparison and cache
maintenance sequence. Diagnostic follow-up should record signal/PC/LR/phase and
check the two instruction words again after RX protection, with ordinary-memfd
and anonymous controls. This is being handled separately by the native-probe
agent. The failed direct call alone does not identify a GPU driver restriction.

The subsequent root diagnostic supplied by the device operator on 2026-11-21
records SIGALRM 14, si_code 128 at 45,000 ms, in `call_fixed_code` after 44,845 ms
in that phase. PC equals the target's first instruction; LR points back into the
diagnostic; x0 is 0x2f rather than the expected 42. The post-RX target, second
alias and canonical data view still contained exactly `52800540,d65f03c0` at
155 ms. Ordinary anonymous-memory and memfd controls passed. This establishes
a bounded failed direct call despite successful data/protection checks; it does
not identify why instruction execution made no observable progress. A copied
native-code route remains a candidate requiring its own coherence tests.

Memory performance and atomics remain independent gates. PowerVR type 1 reports
HOST_VISIBLE|HOST_COHERENT|DEVICE_LOCAL, without HOST_CACHED. Those flags do not
measure native CPU performance or establish ARM Normal-memory access semantics.
The current reims `guest/ptr/raw/aarch64.rs` unconditionally emits LSE and RCpc
instructions and relies on FEAT_LSE2 for certain unaligned within-granule
accesses. The reconstructed build must declare that CPU requirement; device
qualification should retain HWCAP_ATOMICS, HWCAP_LRCPC and HWCAP_USCAT evidence
(NDK r29 `asm/hwcap.h`, bits 8, 15 and 25), and test the actual chosen RAM
provider's access semantics. Successful shader readback does not settle this.

## Recommended order

1. Finish the bounded native execution diagnosis and the ordinary-process data
   alias qualification; native EL0 remains mandatory.
2. Integrate the additive contiguous adoption API with an explicit allocation
   registry and physical alias/hazard policy, refusing fragmented resources.
3. Qualify the single-owner sparse primitive only if it changes a concrete
   runtime design decision; do not promote it to general alias support.
4. Choose explicitly between a substantial segmented shader-access backend and
   a restricted staging backend. Neither is an environment switch. Preserve
   typed refusals and test the concrete semantic gaps before enabling an iOS gate.

No product source, device policy, feature flag or application gate was changed
for this audit.
