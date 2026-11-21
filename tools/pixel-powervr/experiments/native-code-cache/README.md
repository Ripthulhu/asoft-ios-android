# Bounded native code-cache diagnostic

This is a separate experiment from the frozen direct-execution probes. It
keeps the two data aliases on the actual Vulkan producer's exported OPAQUE_FD
and **copies the verified 16 KiB instruction image** into an ordinary memfd.
The CPU executes the copied `mov w0, #42; ret` / `mov w0, #43; ret` instructions
natively at EL0. No TCG translation is used. The actual QEMU native EL0 engine
is not modified, linked, started, or validated by this diagnostic.

## Exact experiment

1. Create the existing small coherent Vulkan producer/import/readback baseline,
   retain the real exported FD, and verify the full offset-zero native map.
2. Move host pages 4–7 from each of two disposable full maps into separate
   owned, 16 KiB aligned reservations. Keep all producer data aliases on their
   original backing and verify every initial byte.
3. Print `AT_HWCAP`/`AT_HWCAP2` and require `ATOMICS`, `LRCPC`, and `USCAT` before
   the AArch64 memory preflight. On the selected owned pages, use one aligned
   64-bit `ldsetal` to set an originally clear bit, check both aliases and all
   canonical/guard pages, then `ldclral` to restore it and check again. Separately
   execute one explicit 64-bit `ldr`/`str` at offset 4 within a 16-byte aligned
   granule, change its value, check all views, restore it, and check again.
   This phase has a combined 5-second limit. Both instructions and all changed
   bytes are bounded; no other allocation or external memory is touched.
4. Verify bidirectional pattern writes through both aliases and all four untouched
   guard pages. Write the fixed return-42 code through the producer data alias,
   verify all three CPU views against the complete deterministic 32 KiB expected
   image, and make both selected data alias VMAs read-only.
5. Create a new, size-sealed ordinary 16 KiB memfd, map it RW, copy all 16 KiB
   from the verified read-only producer alias, and verify the full snapshot.
   Synchronize the cache over the whole 16 KiB span and change the new VMA to
   RX. Read back and verify the RX image, then execute under a 5-second limit.
6. After the call returns, unmap the exact owned code-cache VMA and close its
   ordinary memfd. Only then update the producer code to 43 and repeat with a
   new memfd; dispose of that generation, update to 42, and repeat again.
   Stage numbers remain increasing for all three generations.
7. Verify canonical producer/imported/native views and GPU readback after the
   parent sequence. Fence a distinct GPU-generated initial image for a child.
8. Start a fresh `posix_spawn` / exec child before its entry point makes any
   Vulkan API call. Send the **same actual exported producer FD** over the
   inherited private SOCK_SEQPACKET socket using SCM_RIGHTS. Its distinct
   `--native-code-cache-child` entry point requires protocol 2, variant 2, the
   fixed geometry, and a close-on-exec received FD. The child makes its own
   full map, runs the same memory preflight and data/code-cache sequence, and
   cleans up. The reply includes a separate memory-restoration state.
9. Reap the child and check reply/exit agreement before the parent touches
   producer data again. Verify all canonical pages and GPU readback against
   the child's final deterministic image, including all guards. Keep producer
   and imported Vulkan allocations, the full native map, and the real export
   FD alive until these checks complete.

Only the ordinary code-cache VMA receives PROT_EXEC. The producer aliases
remain R or RW. No individual W+X VMA is requested. The canonical and Vulkan
RW aliases remain available, so **strict physical W^X is not claimed**. This
single-threaded sequential snapshot experiment proves no concurrent mutation,
execution, invalidation, or cache-replacement safety in the real engine.
It is neither direct execution from GPU backing nor a solution to guest RAM
sharing at scale.

Successful aligned atomics and ordinary unaligned accesses qualify only those
individual operations. They do not determine the CPU page-table memory type,
prove cross-core or unaligned atomicity, exercise RCpc instructions, or establish
all of reims's FEAT_LSE2 assumptions. `HOST_COHERENT` is a Vulkan property and
does not itself establish those CPU contracts. CPU cache performance is not
measured. The LSE instructions are restricted to two target-specific functions
called only after the HWCAP check; the whole executable is not built for an
unconditionally higher instruction-set baseline.

## Bounds and failure handling

The parent process has a 60-second internal limit. Each indirect fixed-code
call tightens that same timer to at most 5 seconds; return restores only the
remaining original process budget. The fresh child is limited to 25 seconds;
IPC is limited to 25 seconds and reap/cancellation to 2 seconds. Normal Vulkan
fences retain their existing 5-second bound. Parent-death SIGKILL is armed and
checked before the child receives or maps the FD.
The asynchronous signal handler never kills a numeric child PID: a reap could
already have made that number reusable. Normal cancellation checks child
ownership and performs a bounded kill/reap; parent exit is covered by the
child's checked parent-death signal and parent-PID handshake.

Expected-image stages advance before writes and become verified only after
all CPU views agree. A failure after unverified writes cannot become an
unsupported/pass result. A failed or uncertain fixed move exits the process
without speculative cleanup. Exact cleanup retains the full owned destination
reservation, releases only the known source prefix/suffix, and never unmaps
the vacated source hole. Pending GPU work or unreaped child ownership also
ends only by process exit. No device settings or SELinux policy are changed.

The memory preflight separately marks its state **dirty before each modifying
instruction** and restored only after every expected CPU view and guard agrees.
A synchronous fault while dirty exits with failure and reports that state to the
parent; the parent reaps the child and stops without later GPU access. A missing
CPU feature or a fault before any unverified modification is an unsupported
result. No signal handler attempts to repair or continue a faulting transaction.

## Build and inspect

```sh
python3 build.py --ndk /workspace/scratch/95f3cf369f81/tooling/android-ndk-r29
```

Build target: API 35 AArch64, `-O2 -Wall -Wextra -Werror`, PIE, 16 KiB ELF LOAD
alignment. The build retains Clang static analysis, ELF metadata, disassembly,
source/build hashes, a reproducible gzip, and validated base64 transfer chunks
of at most 2,400 characters.

The independent host fixture uses **ordinary memfd backing for both the data
producer and code cache** and x86-64 instructions. It checks the same complete
expected images, sequential replacements, fresh exec/SCM_RIGHTS path, owned
cleanup including a deliberately reused vacated source hole, refusal to clean
an uncertain failed move, empty-socket deadline, and bounded child cancellation.
It does not establish anything about PowerVR, Vulkan OPAQUE_FD behavior,
AArch64 execution, or the phone. Its memory preflight uses x86-64 operations and
explicitly labels the absence of AArch64 feature validation. Its output is
`host-fixture.log`.

After independent source review, the root agent may separately transfer and
run the frozen binary using:

```sh
native_code_cache_diagnostic --native-code-cache
```

Full success is `RESULT=NATIVE_CODE_CACHE_PASS` with **both** parent and fresh
child memory preflights and 42→43→42 results, child reaped, and the final all-page
GPU readback. Exit 6 is a CPU-memory/code-cache/data-alias capability refusal;
1 is failure (including a fault with unverified preflight writes); 2 is Vulkan
capability unavailable; 3 is native exported-FD mmap unavailable. The older
`--native-alias` option is not accepted by this isolated binary.

## Relationship to the actual engine

The read-only reference `qemu-pixel-producer-review/target/arm/tcg/native-el0.c`
contains `cc_create`, `cc_fill`, and `patched_copy_install`. This diagnostic
tests the feasibility of native CPU execution from copied ordinary memory
while retaining GPU-backed data aliases. It does not implement their slot
lookup, instruction rewriting, guest-address installation, locking, or
invalidation semantics. `cc_fill` currently classifies clean code separately;
read-only clean code can bypass its ordinary-memfd cache, and writable-code
invalidation remains an integration question. No inference of iOS boot,
native engine compatibility, or performance is justified from this probe.

`BASE-FROZEN.json` records the untouched original probe/diagnostic hashes and
the read-only actual-engine source hash used as context.
