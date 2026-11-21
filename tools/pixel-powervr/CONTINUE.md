# Resume the Pixel native/GPU work

Checkpoint after resuming the previous chat on 2026-11-21. Continue the fast
native EL0 route. An iOS 26 boot with only TCG is not the requested result.

## Established state

| Item | Evidence |
| --- | --- |
| Ordinary-app anonymous and memfd native controls | Passed in the earlier session |
| Actual Metal AIR compute and floating-point tile reads | Passed in the earlier session under the ordinary app UID |
| Original combined uncached-memory/copy-code test | Kernel panic recovered from pstore; current-process LSE phase identified by ELF PC/LR matching |
| Earlier parent results before that panic | Unknown: the parent and child share the same routine, and the original probe log is not yet recovered |
| New cached-memory diagnostic | Built, host-tested and independently reviewed; no phone run |
| Source-built Android QEMU26 | Full compile/link and unchanged incremental replay passed; no phone loading or guest execution test |
| Integrated native PowerVR guest RAM and iOS 26 boot | Not established |

The old phone test is retained for evidence; do not rerun its uncached producer
atomics. A userspace timeout did not prevent the asynchronous SError panic.
See the [recovery record](results/2026-11-21/native-code-cache-panic-recovery.json)
and its [reproducible ELF check](results/2026-11-21/symbolize-native-panic.py).

## Current device-access blocker

The existing Tango tab is the Pixel terminal at
`https://app.tangoapp.dev/device/192.168.50.196:5555/terminal`.
It reconnected and read-only shell commands recovered the panic evidence.
Chrome then reported another extension UI open and blocked further terminal
input. Dismiss that UI and resume the same tab. No new GPU-memory test was
started during this continuation.

## Next device work

1. Locate the retained log without assuming the old handoff's directory spelling:

   ```sh
   find /data/local/tmp -maxdepth 5 -type f -name native-code-cache-root.txt
   ```

   Read the returned file. Also preserve the relevant native-test panic excerpt
   from `/sys/fs/pstore/console-ramoops-0`. Its earlier selected fields were read
   from the terminal; the full raw pstore has not been exported. Keep unrelated
   system logs out of the public repository.

2. Transfer the separate [cached-memory candidate](experiments/cached-memory/README.md)
   to a new directory. Verify its complete hash before use:
   `f69664840ba2e7588e196849ea4ce9ff598a8c0081c22e8ac249830fb43f2b9c`.
   Use the default `--cached-memory` mode only for the first qualification.
   Redirect output to a retained regular file so phase checkpoints can `fsync`.
   The default mode exercises LSE on its ordinary-memfd control, while producer
   LSE remains disabled. A basic pass must retain the explicit
   `ATOMICS_NOT_TESTED` qualification. Do not add `--cpu-atomics` automatically.

3. Run the separate QEMU loader package in a new directory. The existing package
   checks hashes and performs only `-version`, `-machine help`, and `-accel help`.
   It does not allocate guest RAM or invoke GPU work. Keep the exact bundled
   dependency set; the build used matched development/runtime packages.

4. A later ordinary-memfd native-engine benchmark must demonstrate positive
   native-entry statistics and expected guest output. Successful loading and
   native initialization alone do not prove guest execution. Use the reviewed
   [required-native candidate and benchmark recipe](ios26-build/required-native/README.md);
   its separate package is ready. The baseline loader package predates that patch.

## Integration boundary

CPU-cached noncoherent allocation is not a drop-in replacement for reims's
current shared-memory contract. Physical-range ownership, cache handoffs,
event/completion ordering, native aliases, copied-code invalidation and GPU
scatter handling remain work. The QEMU build still uses the existing memory
backend. Keep the app's GPU support gate unchanged until the actual combined
contract is implemented and qualified. See the
[memory architecture record](ios26-build/MEMORY-ARCHITECTURE.md).
