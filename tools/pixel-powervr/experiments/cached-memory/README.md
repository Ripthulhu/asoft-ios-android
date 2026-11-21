# Cached producer memory diagnostic

This separate diagnostic requires a Vulkan producer memory type with both
`HOST_VISIBLE` and `HOST_CACHED`. It refuses coherent but uncached producer
memory. On the recorded Pixel driver, type 2 advertises these properties and
lacks `HOST_COHERENT`; the code selects by properties and actual buffer memory
requirements, rather than hard-coding the type index.

The earlier frozen code-cache diagnostic remains unchanged. Recovered pstore
reports an asynchronous SError kernel panic in its process. Matching the saved
PC/LR to the frozen binary places exception delivery after the first aligned
LSE set call in that process on type-1 producer memory. This symbolization is
an inference; asynchronous delivery does not identify the exact offending
instruction. The interrupted process had not reached its own copied-code
phase. Parent-versus-child identity and any earlier parent results remain
unknown without the original run log.
A userspace timeout cannot contain that failure. This
diagnostic therefore keeps producer LSE disabled unless the separate
`--cpu-atomics` option is supplied. Passing ordinary accesses does not qualify
atomics or reims guest RAM.

## Modes

```sh
cached_memory_diagnostic --cached-memory
cached_memory_diagnostic --cached-memory --cpu-atomics
```

The first command performs ordinary aligned and unaligned 64-bit loads/stores
on its own cached producer pages. The second additionally performs one aligned
`ldsetal` and one `ldclral`, restoring the changed bit and verifying every alias
and guard page. The option is transmitted to the fresh child and echoed in its
reply using protocol 3; a disagreement fails the run.

Both modes first run the memory-access and copied-code sequence on an ordinary
memfd, before creating a Vulkan instance. That separately labelled control does
exercise aligned LSE when the required CPU features are advertised. It cannot
establish that the GPU allocation has equivalent CPU attributes.

## Exact sequence

1. Check the 4,096-byte host page size. Selected data aliases and code snapshots
   are 16,384 bytes. The producer allocation must be exactly 32,768 bytes.
2. Run the ordinary-memfd control: two moved aliases, ordinary aligned and
   unaligned accesses, aligned LSE, and native copied-code returns 42, 43, 42.
3. Query the exact runtime buffer usage and OPAQUE_FD import/export support.
   Select a compatible cached producer type. Allocate and map the producer,
   export its real FD and reimport a duplicate on the same Vulkan device with
   the original allocation size and memory type. An independent coherent
   allocation provides GPU readback; no LSE targets that readback allocation.
4. Verify CPU aliases, CPU-to-GPU readback and fenced GPU-to-CPU page patterns.
   Flush both Vulkan memory-object aliases over their complete mapped
   allocations before a GPU read or overwrite. After fenced GPU writes, invalidate
   both mappings before CPU reads. Offset zero and `VK_WHOLE_SIZE` satisfy the
   noncoherent-atom alignment rules without rounding outside an allocation.
5. Verify a native full offset-zero FD mapping before writing it. Move pages
   4–7 from two disposable full mappings into owned aligned reservations. Verify
   selected pages and all guard pages before each phase.
6. Run ordinary aligned and within-granule unaligned 64-bit load/store checks,
   restore the exact bytes and verify all views. Only with `--cpu-atomics`, run
   the separately checkpointed aligned LSE set/clear pair.
7. Copy verified instruction bytes into a new ordinary memfd for each of the
   native 42, 43, 42 calls. Only that ordinary code-cache VMA becomes executable;
   GPU producer pages remain data. Verify the result through independent GPU
   readback after an explicit host-to-device handoff.
8. Fence a new GPU-generated input, invalidate host caches, then start a fresh
   exec child. Pass the actual producer FD over a private SCM_RIGHTS socket.
   The child creates its own full map and repeats the selected CPU/code checks.
   It makes no Vulkan calls. Reap it before the parent checks data, flushes the
   cached allocation and submits the final GPU readback.

No CPU writes overlap GPU work. Dirty host data is flushed before any GPU
overwrite. Both Vulkan memory objects, the real export FD and canonical maps
remain alive through child completion and final readback.

Those Vulkan cache-maintenance ranges and handoffs apply to the retained
Vulkan mappings. Their coverage of the driver-specific POSIX, moved and fresh
child mappings is itself under test, and depends on compatible cache
attributes. Calling the Vulkan APIs does not establish or repair that native
alias contract; even a passing small test cannot prove it for arbitrary aliases.

## Evidence and limits

The program prints selected memory flags, noncoherent atom size and the relevant
`/proc/self/smaps` sections for its own mappings. `smaps` reports VMA flags and
page sizes; it does **not** expose the ARM PTE AttrIndx or MAIR cacheability
attributes. `HOST_CACHED` is the Vulkan allocation contract, not direct proof
that every driver-specific native alias has Normal write-back PTEs.

Phase markers are flushed and `fsync`ed when stdout is a regular file. Redirect
the output to a fresh retained file for a device run. A terminal or pipe is
explicitly labelled non-durable. These checkpoints help locate a failure after
a reboot; they cannot prevent a GPU/interconnect/kernel failure.

The basic success marker is
`RESULT=CACHED_MEMORY_BASIC_PASS_ATOMICS_NOT_TESTED`. With explicit producer LSE
enabled it is `RESULT=CACHED_MEMORY_OPT_IN_ATOMICS_PASS`. Neither establishes
cross-core atomicity, unaligned single-copy atomicity, all reims memory
instructions, concurrent CPU/GPU coherence, native QEMU stub execution, large
guest RAM, scattered GPU resources or iOS boot. The copied-code sequence does
not test JIT invalidation or concurrent execution.

This is a producer-backed diagnostic with explicit ownership handoffs. The
current runtime's coherent shared-buffer contract cannot silently adopt its
noncoherent memory; integration needs real flush/invalidate boundaries and
physical-alias tracking.

## Bounds and build

The retained code-cache machinery keeps a 60-second parent limit, 25-second
fresh-child limit, 5-second CPU/call limits and 5-second GPU-fence limits.
Malformed requests, mismatched flags, unknown writes and unreaped children
cannot produce a pass. Failed uncertain moves or in-flight GPU work terminate
the process without speculative cleanup. No device settings are changed.

```sh
python3 build.py --ndk /path/to/android-ndk-r29
```

The build targets Android API 35 AArch64, with 16-KiB ELF alignment. It retains
hashes, symbolized disassembly, detached debug lines, a Clang static-analysis
report and bounded transfer chunks. The CPU-only x86-64 host fixture checks
default and opt-in modes in both parent and fresh child, exact alias cleanup,
bounded cancellation and refusal to select uncached producer types. Its pass
is not evidence of Android, Vulkan or Pixel execution.
