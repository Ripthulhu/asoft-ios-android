# One-region native EL0 and GPU proof

**Status: PROPOSED / NOT IMPLEMENTED.** Design record, 2026-11-21.

This proposal would connect the actual QEMU native factory and stub path to
one small producer-backed data region. A fixed native EL0 payload would read
GPU-generated input and write a derived result; independent GPU readback would
then check the result and untouched guard pages. The remaining guest memory,
including executable code, would use ordinary memfd RAM.

This document adds no provider, QEMU modification, executable, device action or
product behaviour. It does not assert that the proposed proof has run or that
GPU-backed memory is suitable for general guest RAM.

## Prerequisites and evidence boundary

Device validation of this proposal is conditional on retained passing results
from both of these separate qualifications:

| Prerequisite | Required evidence | What it establishes for this proposal |
| --- | --- | --- |
| [Cached-memory baseline](../experiments/cached-memory/README.md), default mode | Exact executable hash, process identity, complete retained log and exit status; `CACHED_MEMORY_BASIC_PASS_ATOMICS_NOT_TESTED` with the reviewed allocation/mapping shape | The tested cached producer allocation, moved aliases and serial CPU/GPU handoffs completed under that identity; producer atomics remain unqualified |
| [Actual ordinary-memfd native-engine benchmark](required-native/README.md) | Exact package/executable identity and the corrected benchmark's complete passing record, including actual native execution and guest result checks | The required-native QEMU build, factory and workers execute the ordinary-memfd guest successfully under that identity |

Neither result is supplied or assumed by this proposal. A loader check,
successful build, host fixture or native initialization message cannot replace
either prerequisite. A shell result also does not establish ordinary Android
app permissions.

The cached baseline is identified by [build-info.json](../experiments/cached-memory/build-info.json):
binary SHA-256
`f69664840ba2e7588e196849ea4ce9ff598a8c0081c22e8ac249830fb43f2b9c`.
The existing required-native QEMU executable is identified by
[checkpoint-index.json](required-native/checkpoint-index.json): SHA-256
`02fd3b92e1f7747596df8688326af2802a261bf59fdf09222b2a4d7dbb94be74`.
The proposed integration would produce a new, separately identified engine;
those hashes do not describe an engine with a producer provider.

## Exact allocation and provider shape

Reuse the cached diagnostic's shape. A new exact-16-KiB allocation or a direct
partial FD mapping would introduce a different driver operation and is outside
this first proposal.

| Property | Proposed value or rule |
| --- | --- |
| Host page size | 4,096 bytes; reject a different size |
| Vulkan producer allocation | Exactly 32,768 bytes, selected using actual buffer requirement masks and `HOST_VISIBLE | HOST_CACHED`; no uncached fallback |
| Export/import | A real producer-owned `OPAQUE_FD`, with the original allocation size and memory type retained for Vulkan reimport |
| Native source mapping | Full 32,768-byte shared read/write mapping at FD offset zero |
| Guest-exposed interval | 16,384 bytes at backing offset 16,384, covering host pages 4–7 |
| Native destination | One owned, 16-KiB-aligned interval inside the native mirror window; obtain it with the diagnostic's full-map-plus-`mremap` operation |
| Guard data | Host pages 0–3 remain unmodified; final verification covers the complete 32 KiB allocation |
| Permissions | Data only. The provider rejects instruction fetch and any requested executable mapping independently of guest PTE permissions |
| Guest translation | One 16-KiB user-accessible NX leaf at a reserved, non-overlapping GPA; no larger block fill across the region |
| Concurrency | One vCPU, one stub, serial ownership, no CPU access overlapping GPU work |

Keep code, stack, page tables, boot state, trap frames, factory controls,
futexes, counters, dirty bitmaps and result messages in ordinary memfd or
anonymous memory. The producer interval contains no locks, page tables,
instructions or control protocol state. The fixed payload uses reviewed scalar
loads and stores; it performs no producer atomic or producer cache-maintenance
instruction.

The proposed QEMU adapter is `memory_region_init_ram_ptr()` plus a separate,
explicit provider descriptor. That descriptor needs the exact region identity,
reserved GPA, exposed length, backing length, backing offset, owned FD,
factory FD index and NX policy. Validate identity and bounds before using it;
do not recognize special storage by a reusable FD number alone.

Resolve the descriptor in `mirror_fill()` before the generic
`memory_region_get_fd()` path. Do not place the opaque FD in `RAMBlock.fd` to
make it look like ordinary file RAM: the existing `qemu_ram_alloc_from_fd()`
path obtains a size with `lseek()` and can request file growth. Its file
semantics are not the producer contract. `memory_region_init_ram_ptr()` uses
`RAM_PREALLOC`, leaving backing-pointer ownership with the provider. Its RAM
registration still invokes dump/advice hooks, including `MADV_HUGEPAGE` and
`MADV_DONTFORK`; record these new driver-entry boundaries and check their
observed behaviour. See the pinned source references below.

The stub provider would map the full FD at offset zero, verify the intended
payload identity, then move the selected interval into the owned native
window. Track the remaining source prefix until native use ends, matching the
reviewed diagnostic lifetime. A failed fixed move leaves ownership uncertain;
terminate the isolated process without speculative unmapping. No Vulkan-owned
mapping is moved. Disable speculative neighbour fills for this proof, and
reject unsupported lengths, offsets or permissions instead of routing them
through ordinary FD mapping.

## Factory registration: ordinary RAM first

Before any stub is spawned, register and acknowledge both backing descriptors:

| Factory index | Backing | Mapping rule |
| --- | --- | --- |
| 0 | Ordinary guest memfd RAM | Existing ordinary RAM/code mapping path |
| 1 | The producer allocation's real FD | Explicit provider: full offset-zero map, then selected 16-KiB move |

This ordering is required by the inspected implementation. `stub_ram_ready()`
returns success as soon as `nram_q` is nonzero; registering the producer first
would suppress the ordinary RAM-FD handoff. The code-cache selection also
assumes ordinary RAM occupies index zero. `FAC_RECV_FD` updates the factory's
FD table, but already-forked stubs do not acquire later FDs merely because the
shared table changed. Complete both handoffs before `FAC_SPAWN`, and fail if
either acknowledgement or descriptor identity is inconsistent.

Factory, stub and QEMU metadata continue to use ordinary memory. The reviewed
RAM registration and native bookkeeping do use atomics on their metadata;
that is distinct from executing an atomic on the producer payload.

## Require proof of the target's native execution

`ASOFT_NATIVE_EL0_REQUIRED=1` currently requires successful initialization and
worker setup. It does not prohibit all later TCG fallback. In the inspected
`handle_trap()`, a `FILL_UNSUPPORTED` result from `mirror_fill()` sets
`tcg_until_el1` and returns execution to TCG. Correct GPU readback plus positive
global native statistics could therefore pass while the target data operation
actually ran in TCG.

The proposed proof needs an additional, narrowly scoped gate for its fixed EL0
payload interval and special producer region. Unsupported mapping or
instruction handling during that payload must fail the experiment. Ordinary
TCG execution of the tiny guest's kernel/setup code remains part of the hybrid
engine; it cannot count as completion of the producer EL0 payload.

A passing record must establish the following ordered chain:

1. The hashed, fixed payload entered the intended native stub at its expected
   initial PC. Its executable backing is ordinary memfd RAM.
2. The expected producer load/store fault was reported by that stub at the
   expected payload PC, with the expected data address and access kind.
3. The stub acknowledged installation of the exact producer descriptor and
   selected interval. Mapping success alone is not a payload result.
4. The payload completed its reviewed load, calculation and store without a
   TCG fallback inside the gated interval. A native completion trap at the
   expected PC reports the expected value through registers or ordinary
   control memory, tied to the same execution and mapping generation.
5. After all writers are gone, independent GPU readback matches the derived
   result and every unchanged byte, including the four guard pages.

Use a result derived from the GPU-generated input, rather than a constant
that could be written without reading the producer data. The implementation
must define the small allowed trap sequence and reject an unexpected escape
from it. Positive entry/SVC/time counters, a startup message or a ready worker
are supporting diagnostics, not substitutes for this target-specific witness.

## Serial ownership and GPU handoffs

One launch can demonstrate GPU-to-native and native-to-GPU transfer:

1. The Vulkan owner creates and retains the allocation, export FD, any imported
   Vulkan alias and canonical mappings. It flushes any prior host writes,
   generates the input with the GPU, records a transfer-to-host barrier, waits
   successfully for the fence, then invalidates the retained Vulkan mappings.
2. The owner stops touching producer bytes. It launches the isolated QEMU
   process, whose factory receives both FDs before spawning the worker.
3. QEMU and its stub perform the fixed native payload using the provider above.
   The Vulkan owner submits no GPU work and performs no producer cache
   maintenance during this CPU ownership interval.
4. The owner validates the target-specific result and establishes that QEMU,
   the factory and every worker have terminated and been reaped.
5. Only after successful result and lifetime checks, the owner flushes the
   complete retained Vulkan allocation mappings, submits an independent GPU
   readback, waits for completion and verifies all 32 KiB.

Use offset zero and `VK_WHOLE_SIZE` over the full retained Vulkan mappings,
as in the cached diagnostic. Flush dirty host data before GPU reads or
overwrite. Invalidate only after the device-to-host barrier and successful
host wait, and never invalidate unflushed host modifications. The child and
stub make no Vulkan cache API calls; the owner coordinates the entire handoff.

These are valid Vulkan range and ordering rules, not proof that every native
alias has compatible cache attributes. Coverage of POSIX, moved and
cross-process aliases remains a driver-specific property under test. Calling
`vkFlushMappedMemoryRanges()` or `vkInvalidateMappedMemoryRanges()` does not
repair an incompatible alias policy. Neither `HOST_CACHED` nor `smaps` exposes
the ARM PTE AttrIndx/MAIR values needed to establish that policy directly.

## Lifetime, failure handling and retained phases

Waiting for the QEMU PID is insufficient. The existing factory and stubs use
`PR_SET_PDEATHSIG(SIGKILL)` but have no complete owner-side descendant reap
protocol. `native_el0_quiesce()` kicks parked native vCPUs; it does not destroy
or reap the process tree.

The proposed owner must control an isolated process group and collect every
descendant exit, for example using subreaper status and exact process ownership
or pidfds where available. Do not signal a possibly reused numeric PID.
PDEATHSIG is supporting protection, not a successful handoff acknowledgement.
The existing child startup check tests only `getppid() == 1`: with a subreaper,
an orphan can instead be adopted by that subreaper. Check the exact expected
parent identity around each fork and verify the parent-death setup, or ensure
the owner forcibly terminates and reaps its entire isolated group before any
producer handoff. This lifetime mechanism is part of the unimplemented work.

Retain all producer handles and mappings until no possible writer remains.
Timeout, malformed identity, unexpected fallback, an unverified mutation,
uncertain mapping ownership or an unreaped process prevents success-path cache
maintenance and GPU readback. Cleanup must respect possibly in-flight GPU work
and live CPU users rather than infer quiescence from a missing response.

Use a bounded process budget, bounded child/factory waits and explicit cleanup
states. Retain a fresh log with executable/package hashes, UID, role, PID,
parent identity, selected memory flags, region geometry and mapping generation.
Flush and `fsync` phase records before allocation/map/move, first producer
access, native entry/completion, descendant shutdown, cache maintenance and GPU
submission. Keep the watchdog armed through final result persistence. These
records help locate a failure; a userspace watchdog cannot contain an
interconnect or kernel panic.

## Interpretation of a future pass

A complete pass would show that the actual native factory/stub path can use
this particular producer-backed interval for the tested scalar data accesses,
with GPU input and readback across explicit serial ownership boundaries. It
would be a concrete engine integration result beyond standalone copied-code
execution.

It would not establish producer atomics, cross-core or unaligned atomicity,
concurrent CPU/GPU coherence, every native memory attribute, RAM-scale
operation, arbitrary FD offsets, scattered GPU resources, general reims guest
RAM semantics, producer-backed page tables/stack/code, JIT invalidation, or iOS
boot. The existing coherent shared-buffer runtime cannot adopt noncoherent
memory without real ownership and physical-alias tracking. See
[MEMORY-ARCHITECTURE.md](MEMORY-ARCHITECTURE.md) and
[INTEGRATION-PLAN.md](INTEGRATION-PLAN.md).

## Pinned implementation references

The source audit uses QEMU commit
`7a900afb62ddf94713e38ac5a4aafe1d42c9efa8`; the required-native delta is preserved
in [native-el0-required.patch](required-native/native-el0-required.patch) and
[build.json](required-native/build.json). Function names below refer to that
source baseline; the proposed provider and payload gate do not exist there.

| Pinned source | Functions or data | Relevance |
| --- | --- | --- |
| [QEMU native EL0 implementation](https://github.com/alpersamur3/qemu-sptm/blob/7a900afb62ddf94713e38ac5a4aafe1d42c9efa8/target/arm/tcg/native-el0.c) | `stub_ram_ready()`, `ram_fd_index()`, `factory_main()`, `StubShm.ram_fd` | Registration order, FD transfer and fork inheritance |
| Same native implementation | `mirror_fill()`, `stub_do_fill_locked()`, `fill_neighbours()` | Generic FD mapping assumptions and proposed provider boundary |
| Same native implementation | `handle_trap()`, `native_el0_try()` | Existing fallback paths and need for a target-specific native witness |
| Same native implementation | `stub_main()`, `factory_main()`, `native_el0_quiesce()` | Parent-death checks, worker lifetime and limits of quiescing |
| [QEMU memory regions](https://github.com/alpersamur3/qemu-sptm/blob/7a900afb62ddf94713e38ac5a4aafe1d42c9efa8/system/memory.c) | `memory_region_init_ram_ptr()`, `memory_region_set_ram_ptr()` | Externally owned pointer adapter |
| [QEMU physical memory](https://github.com/alpersamur3/qemu-sptm/blob/7a900afb62ddf94713e38ac5a4aafe1d42c9efa8/system/physmem.c) | `qemu_ram_alloc_from_ptr()`, `qemu_ram_alloc_internal()`, `ram_block_add()`, `reclaim_ramblock()` | `RAM_PREALLOC` ownership, metadata and registration hooks |
| Same physical-memory implementation | `get_file_size()`, `qemu_ram_alloc_from_fd()`, `file_ram_alloc()` | File-size/growth assumptions to avoid for OPAQUE_FD |
| [Cached diagnostic](../experiments/cached-memory/native_code_cache.h) | `na_alias_prepare()`, `na_alias_move()`, `na_alias_drop()` | Exact full-map/move shape and owned-range cleanup to reuse |
| [Cached Vulkan diagnostic](../experiments/cached-memory/opaque_fd_probe.c) | `resources()`, `host_to_device()`, `device_to_host()` | Producer selection, full mapped ranges and serial cache handoffs |

Primary Vulkan rules:

- [VkMappedMemoryRange](https://docs.vulkan.org/refpages/latest/refpages/source/VkMappedMemoryRange.html): mapped-range and noncoherent-atom boundaries.
- [vkFlushMappedMemoryRanges](https://docs.vulkan.org/refpages/latest/refpages/source/vkFlushMappedMemoryRanges.html): host writes and availability; unmapping does not implicitly flush.
- [vkInvalidateMappedMemoryRanges](https://docs.vulkan.org/refpages/latest/refpages/source/vkInvalidateMappedMemoryRanges.html): prior device synchronization and the prohibition on invalidating unflushed host writes.

Any implementation must be reviewed against its resulting source and retained
device evidence. This proposed design alone supplies neither an execution
result nor a general memory-backend contract.
