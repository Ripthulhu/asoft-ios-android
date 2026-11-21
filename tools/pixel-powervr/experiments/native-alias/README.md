# Native-alias / executable-memory experiment

This isolated probe extends the frozen opaque-FD v3 source. It changes no v2/v3
artifact or diagnostic APK and does not install or execute anything on the phone.

```sh
timeout 60 ./native_alias_probe --native-alias
```

## Exact test

The new mode retains v3's Vulkan export/import, CPU/GPU and full native
offset-zero mapping phases. It requires a fully checked allocation of exactly
32 KiB on a 4 KiB host. It selects the 16 KiB interval at offset 16 KiB, host
pages 4–7, leaving pages 0–3 as guards.

1. Verify every word of two separate disposable full offset-zero mappings.
   Move each selected interval into its own fresh 16 KiB-aligned reservation.
   Keep both aliases alive and verify their identity before writing.
2. Change one alias to read-only, write through the other, and check both aliases
   plus all canonical pages. Reverse their roles and repeat.
3. Write exactly `mov w0,#42; ret`, verify the code and all data/guard bytes,
   synchronize the instruction cache, change the code alias from RW to RX, call
   it and require 42. Restore RW and recheck. No individual VMA is requested as
   RWX and no policy changes. Retained canonical/Vulkan RW aliases coexist with
   the RX alias; this is not strict physical-page W^X.
4. Drop only exact owned source/destination intervals; verify all canonical CPU
   views and an independent GPU readback of the canonical buffer.
5. GPU-fill all pages with a new page-distinct pattern and wait for its fence.
   `posix_spawn` a fresh executable instance, and send the real exported FD with
   SCM_RIGHTS over a private Unix sequenced-packet socket. The export FD is
   close-on-exec; data mappings cannot survive exec.
6. The child branch runs before Vulkan initialization, creates no Vulkan device
   and makes no Vulkan calls. It maps the received FD from offset zero, verifies
   the GPU-produced input, and repeats the two-alias/protection/fixed-code test.
7. After the child exits and is reaped, verify all eight canonical pages and an
   independent GPU readback. Original Vulkan allocations, mappings and exported
   FD remain alive throughout. No GPU operation overlaps child CPU access.

## Ownership, bounds and exits

After a successful move the old source interval is an **unowned hole**. Cleanup
keeps only the remaining source prefix/suffix and complete destination
reservation (including its still-owned anonymous guards). It never bulk-unmaps
across the hole. A failing fixed move may already remove its destination, so
that path exits without guessed mapping or Vulkan cleanup. Unexpected cleanup
errors are failures and also use process teardown.

Bounds: GPU fences 5 s; parent watchdog 45 s; child watchdog 10 s; IPC 8 s; reap
2 s; outer timeout 60 s. The child verifies `PR_SET_PDEATHSIG=SIGKILL` and its
expected parent PID. Timeout/cancellation kills and reaps it; if reaping cannot
be established, the parent exits without freeing potentially live backing.

The write stage changes **before** each write; the verified stage advances only
after all CPU bytes/guards agree. A child pass/unsupported report with unverified
writes is rejected. A pass also requires the complete code stage.

| Exit | Meaning for `--native-alias` |
|---:|---|
| 0 | Every requested baseline, alias, protection, execution and fresh-child check passed |
| 1 | Failure: Vulkan/fence error, post-write data/guard mismatch or data-access fault, cleanup failure, timeout, cancellation, malformed child protocol, or other unexpected operation |
| 2 | Required Vulkan capability unavailable |
| 3 | Vulkan baseline passed; full native FD mapping unsupported |
| 6 | Vulkan/full-map baseline passed; new alias/native contract unsupported before alias writes, a permission transition refused, or verified fixed code could not execute/return 42 |

An initial new-view identity mismatch is unsupported before writes. A changed
previously established parent canonical view is failure. Execution refusal is
scoped only after the fixed code and earlier writes were verified; data faults
after writes are failures. Completed stages remain visible. Exit 6 prints
`RESULT=VULKAN_FD_MMAP_PASS_NATIVE_ALIAS_UNSUPPORTED`, never all-PASS. Preserved
legacy options retain v3's exits 4/5; they are not this new mode.

## Build and host fixture

```sh
cc -std=c11 -O2 -Wall -Wextra -Werror native_alias_fixture.c -o native_alias_fixture
./native_alias_fixture
python3 build.py --ndk /path/to/android-ndk-r29
```

The fixture uses the same alias/protection/IPC helpers with an ordinary Linux
memfd. On x86-64 it executes a separately labelled `mov eax,42; ret` sequence;
it does not validate AArch64 execution. It checks fresh-exec SCM_RIGHTS mapping,
bidirectional writes, permissions and exact cleanup. Negative controls reclaim
the moved source hole and verify cleanup leaves that mapping intact, force a
real failed move and verify cleanup refusal, check an empty-socket deadline,
and verify child cancellation/reap. Tiny negative-control forks exist only in
the CPU-only fixture; the phone path uses posix_spawn/exec.

`fixture-result.json` and `fixture.stdout.txt` record the host result.
`build-info.json` and `SHA256SUMS` record Android source/toolchain/artifact hashes;
`BASE-V3.json` pins the unchanged source base. ELF/static-analysis reports and
compressed transfer chunks are alongside them. Build-time candidate status is
separate from subsequent review/freeze and hardware evidence.

## Limits

A phone PASS would qualify only this small allocation and fixed sequence. It
would not test forced discard/refault, QEMU's real native factory/stubs, guest
page-table invalidation, arbitrary gathers, code rewriting, concurrent guest
tasks, RAM-scale allocations or an iOS boot. Refault qualification is a separate
experiment. This probe does not bypass the app GPU gate. The user's required
route retains native EL0 after its actual provider is qualified; TCG-only boot
is not a substitute.

## Root phone result: direct execution failed

The exact frozen binary ran on the Pixel 10 Pro XL on 2026-11-21 under
KernelSU root with SELinux Enforcing. Two simultaneous 16 KiB aliases, both CPU
write directions, all eight canonical pages, the four guard pages, instruction
cache synchronization, and RW-to-RX permissions passed. The fixed code call did
not produce the required return marker. The bounded run ended with exit 1 and
the generic signal/deadline failure marker. The original signal handler did not
record the signal number or fault context, so the cause remains under
investigation; the observed delay is consistent with its watchdog.

**The direct executable-alias contract did not pass.** No fresh child was
started, and no later GPU verification phase ran. The small data-alias passes
do not qualify code fetch or the real native EL0 factory. A separate diagnostic
will compare ordinary executable memory and capture the interruption context.
The frozen binary and original host-validation records remain unchanged.

See the [phone capture](../../results/2026-11-21/native-alias-root.jpg).
