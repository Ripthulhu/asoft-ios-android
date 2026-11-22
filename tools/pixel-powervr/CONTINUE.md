# Resume the Pixel native/GPU work

For the latest 2026-11-22 device work, start with
[the native iOS26 checkpoint](experiments/cpu-shadow/CONTINUE-PIXEL.md).
It records the accepted native firstboot, the preserved failed saved inspection,
and the fresh inspection with an external process observer being prepared.
The sections below retain the earlier 2026-11-21 qualification history.

Checkpoint from 2026-11-21. Continue the fast native EL0 route. An iOS 26 boot
with only TCG is not the requested result. The strict two-CPU register benchmark,
the bounded one-region native/GPU bridge, and the subsequent real reims-owned
producer bridge have now passed on the Pixel under root with SELinux enforcing.
Read the [reims device checkpoint](ios26-build/reims-producer-native/README.md)
for the current qualified owner and unchanged QEMU binary. Package paths in the
historical sections below belong to their individually named baselines.

The [host-validation follow-up](ios26-build/reims-host-validation/README.md)
records the passing Vulkan alias route and the repaired format/lint/tooling
checks. Its final full gate has 3,001 tests passed, six failed and two skipped;
it is not a green integration checkpoint. General guest-memory/device
integration and iOS 26 boot remain ahead of these proofs.

## Established state

| Item | Evidence |
| --- | --- |
| Ordinary-app anonymous and memfd fixed-code controls | Passed in the earlier session |
| Actual Metal AIR compute and floating-point tile reads | Passed earlier under the ordinary app UID |
| Original uncached-memory/copy-code experiment | Recovered asynchronous SError kernel panic; interrupted process's first LSE phase identified |
| Earlier parent results before that panic | Unknown; expected original test log not found |
| Default cached-memory diagnostic | Root-shell `CACHED_MEMORY_BASIC_PASS_ATOMICS_NOT_TESTED`, exit 0 |
| Required-native Android QEMU | Loader/paused-machine controls passed; real native guest execution observed |
| Unchanged QEMU benchmark correctness | FAILED: TPIDRRO mismatch on both CPUs |
| Separate copied-code TPIDRRO candidate | Strict root-shell native benchmark PASS, including both native T7 witnesses |
| Bounded one-region native/GPU bridge | Root-shell PASS; exact native phases, complete reap, 8,192-word GPU readback |
| Real reims-owned native/GPU producer | Root-shell PASS; same allocation/runtime object, complete serialized handoff |
| Host Vulkan import/map producer alias | PASS; distinct address, 8,192 words, lifetime checks, runtime compute/readback |
| Full host workspace gate after repairs | Format/lint/build pass; 3,001 tests pass, six fail, two skipped |
| Integrated native PowerVR guest RAM / iOS 26 boot | Not established |

Do not rerun the frozen uncached producer-atomic diagnostic. Its userspace
timeouts did not contain the kernel panic. The frozen binary was reverified
as SHA-256 `52857d6a36c24827dfbfdb75c9b849e85513d8b55b000050c9bbfd9140e968f8`.
The [follow-up record](results/2026-11-21/device-resume-followup.json) preserves
the completed log search and retained panic excerpt. Do not infer parent
results from the recovered PPID.

## Completed uploads

Both archive hashes and extracted payload hashes matched before execution.
Do not ask the user to upload the original packages again.

| Package actually tested | Bytes | SHA-256 |
| --- | ---: | --- |
| `pixel-cached-memory-device.zip` | 32,965 | `87a0f8f7d97d0981ad66ed2016dfc62b408a6e9ff18048746e2388e6953a09a9` |
| `qemu26-native-required-smoke.zip` (v1) | 20,145,138 | `314be50ecafdcc7e9dcffd552a0c7e5e0da1f51a1337024ac66586ca3e264cd0` |

Shared transfer folder:
`/sdcard/Download/pixel-native-resume-mdPitH`.

Actual QEMU directory:
`/data/local/tmp/pixel-native-test.JeLCD7/qemu26-native-required-smoke`.

The shell ran as UID 0, `u:r:ksu:s0`, with SELinux enforcing. Frozen experiment
manifests retain their build-time state; later result records describe device
execution. Do not regenerate old archives merely to update their status.

## Cached-memory result

Read [cached-memory-root.json](results/2026-11-21/cached-memory-root.json).
The unchanged frozen binary
`f69664840ba2e7588e196849ea4ce9ff598a8c0081c22e8ac249830fb43f2b9c`
completed the default-only wrapper with diagnostic and runner exit 0.

The producer was type 2, flags `0xb`, 32 KiB, cached and noncoherent. Parent
and fresh child passed ordinary aligned and unaligned accesses; both producer
atomic-call counts remained zero. The separate ordinary-memfd control ran two
LSE calls before Vulkan initialization. After child reap, serialized GPU
readback checked all 8,192 words, and the regular-file final checkpoint completed.

Retain `CACHED_MEMORY_BASIC_PASS_ATOMICS_NOT_TESTED`. Do not add
`--cpu-atomics` automatically. This small root-shell test does not qualify
ordinary-app execution, general guest RAM, concurrent coherence, actual QEMU
provider integration or iOS boot. Code snapshots used ordinary memfd pages.

Complete log copy:
`/sdcard/Download/pixel-native-resume-mdPitH/cached-memory-root-diagnostic.txt`.
The record's SHA-256 is transcribed from the phone, not independently computed
from locally retrieved raw bytes.

## Actual native-engine result

Read [qemu-native-root.json](results/2026-11-21/qemu-native-root.json).
The unchanged QEMU is 58,513,456 bytes, SHA-256
`02fd3b92e1f7747596df8688326af2802a261bf59fdf09222b2a4d7dbb94be74`.
The pinned guest SHA-256 is
`0454b4988e32f7476fd19c205343f436a702a70f69b1a5fb4d115c26ab64d98f`.

Loader checks, native-enabled `-version`, and a paused native-enabled QMP
machine passed. The initial inherited-stdin guest attempt ended 137 with no
guest output. A later early-execution control ran native code. An intervening
`RLIMIT_FSIZE` control was invalid because it prevented creation of the
512 MiB RAM memfd; exclude it from engine diagnosis.

The final control changed only the original script's stdin to `/dev/null`.
It completed in six seconds including wrapper work, with QEMU exit 0,
415,727 native entries and 404,036 native SVCs. Both CPUs passed T6/T10 and
printed `EXIT 0`, but both also printed:

```text
T7 tpidr=0x1234 tpidrro=0x0 MISMATCH
```

The runner correctly returned 1 and `NATIVE_MEMFD_BENCH_PASS=0`.
The generic native path can read host TPIDRRO instead of the guest's value.
The existing iOS-specific swap mode has different semantics and does not fix
this generic benchmark. The stdin-only success narrows the launch issue; its
exact internal cause remains unresolved. These counters are execution evidence,
not a speed comparison.

Full runner/summary copies in the shared folder are
`qemu-native-stdin-control.txt` and `qemu-native-stdin-control-summary.txt`.
The repository contains an unmodified [terminal capture](results/2026-11-21/native-stdin-control-root.png)
and labelled transcriptions, not downloaded raw logs.

## Completed native register qualification

The separate [TPIDRRO candidate](ios26-build/tpidrro-trap/README.md) passed under
the same root-shell identity. Read
[qemu-tpidrro-trap-root.json](results/2026-11-21/qemu-tpidrro-trap-root.json).
Its new binary SHA-256 is
`78e6174366fa3522fdcef0e1eca3f606ea3601823148bb69a31e4ecd18c42a35`.
The exact current package path is:

`/data/local/tmp/pixel-tpidrro-verified-1x7qrquh/qemu26-tpidrro-trap-smoke`

The suffix's first character is digit `1`, verified by its printed codepoint.
The runner and QEMU exited 0. Both CPUs passed T6/T7/T10 and completion, with
writable TPIDR `0x1234` and guest TPIDRRO `0xabcd0000` / `0xabcd0001`.
Each reported two native TPIDRRO traps, last PC `0x100000768`, so T0 alone
cannot supply the witness. Statistics recorded 415,536 native entries and
404,036 native SVCs. The wrapper elapsed time was seven seconds; this is not
a speed comparison. The guest was unchanged and stdin remained `/dev/null`.

The result directory is `results/tpidrro-trap-20261121T174900Z-23728` beneath
that package. Full runner, summary, selected proof, process context, installation
and transfer records were also copied to the shared upload folder with the
`qemu-tpidrro-trap-` prefix. The selected
[terminal capture](results/2026-11-21/native-tpidrro-trap-root.png) is retained
in the repository. Raw phone logs have not been exported into this checkout.

The new mode preserves writable TPIDR, traps exact TPIDRRO reads in copied
read-only pages, and requires native stubs plus the ordinary memfd code cache.
Default and existing iOS behavior remain separate. This qualifies the pinned
benchmark under root, not ordinary-app QEMU or the GPU provider.

A checker-only v2 package also exists for the old executable. It fixes
CPU-prefixed completion syntax but cannot repair the observed register failure.
Do not request upload of that intermediate package as the fix.

## Transfer constraints

Phone certificate validation and browser host restrictions blocked the prior
automated download routes. They remain intact: do not retry blocked hosts,
disable certificate verification or switch browser surfaces to bypass them.
The existing Tango shell remains available. Installed Termux zstd 1.5.7 and
Python 3.14.8 execute successfully. The new candidate was delivered as an
exact local delta through that shell, without a network request: all 18 parts
and the complete 1,973,809-byte update archive verified before extraction.
The reviewed installer reconstructed all 22 frozen files in a new directory
and rechecked the original binary before applying executable permissions.
See [transfer provenance](ios26-build/tpidrro-transfer/README.md). No additional
manual upload was needed. Terminal settings were restored after transfer.

A Tango log-download attempt timed out and reset browser control. Reclaim the
same existing Tango tab if needed; do not repeat that download loop. Complete
logs remain on the phone.

## Integration boundary

The [one-region native proof](ios26-build/ONE-REGION-NATIVE-PROOF.md) and the
[reims-owned handoff](ios26-build/reims-producer-native/README.md) both passed.
Each used a selected 16 KiB native data view of a 32 KiB cached producer
allocation, exact native fault/map/completion witnesses, and the fully reaped
three-process tree before independent GPU readback of all 8,192 words. These
are fixed scalar payloads with serialized ownership. The target payload used
native EL0, with TCG for EL1 setup, and no producer atomics.

The next integration work is shared product-device/region ownership, native
mapping updates, guest gather/remap registration, resource lifetime hooks,
and CPU/GPU transitions at every guest-visible event. General guest RAM,
concurrent vCPUs, ordinary-app bridge execution, suspend/resume and iOS boot
remain unqualified. Keep the retained native witnesses and complete-reap
requirements when extending the bridge.

CPU-cached noncoherent memory cannot silently replace reims's current shared
memory. Physical-range ownership, cache handoffs, completion ordering, native
aliases, copied-code invalidation and GPU scatter handling remain work.
Keep the application's GPU support gate unchanged until the actual combined
contract is implemented and qualified. See the
[memory architecture record](ios26-build/MEMORY-ARCHITECTURE.md).
