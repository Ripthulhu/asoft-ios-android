# Resume the Pixel native/GPU work

Checkpoint from 2026-11-21. Continue the fast native EL0 route. An iOS 26 boot
with only TCG is not the requested result. No new native/GPU device test started
during this continuation; file delivery is the current blocker.

## Established state

| Item | Evidence |
| --- | --- |
| Ordinary-app anonymous and memfd fixed-code controls | Passed in the earlier session |
| Actual Metal AIR compute and floating-point tile reads | Passed in the earlier session under the ordinary app UID |
| Original combined uncached-memory/copy-code test | Kernel panic recovered from pstore; current-process LSE phase identified by ELF PC/LR matching |
| Frozen binary identity | Reverified on the phone during this continuation; still SHA-256 `52857d6a36c24827dfbfdb75c9b849e85513d8b55b000050c9bbfd9140e968f8` |
| Earlier parent results before that panic | Unknown; the original run directory has only binary/transfer files, and no expected test log was found |
| New cached-memory diagnostic | Built, host-tested and independently reviewed; default-only device package ready; no phone run |
| Required-native Android QEMU26 | Fully compiled/linked; checker corrected and host-tested; device package ready; no phone loading or guest execution test |
| Integrated native PowerVR guest RAM and iOS 26 boot | Not established |

Do not rerun the frozen uncached producer-atomic diagnostic. Its userspace
timeouts did not contain the asynchronous SError panic. The
[follow-up record](results/2026-11-21/device-resume-followup.json) records the
completed log search and the selected 3,000-byte panic excerpt retained at
`/data/local/tmp/pixel-cached-resume.mdPitH/previous-native-panic.txt`.
The excerpt has not been exported. Parent/child identity remains unknown even
with pstore's PID/TGID 17957 and PPID 17956, because the parent command was not
recovered. Do not infer earlier phase results from that PPID alone.

## Current handoff: upload two prepared ZIPs

The existing Tango tab is now open to this empty phone folder:

`/sdcard/Download/pixel-native-resume-mdPitH`

Use Tango **Upload Files** to upload these prepared packages:

| Package | Bytes | SHA-256 |
| --- | ---: | --- |
| `pixel-cached-memory-device.zip` | 32,965 | `87a0f8f7d97d0981ad66ed2016dfc62b408a6e9ff18048746e2388e6953a09a9` |
| `qemu26-native-required-smoke.zip` | 20,145,138 | `314be50ecafdcc7e9dcffd552a0c7e5e0da1f51a1337024ac66586ca3e264cd0` |

The user only needs to upload the ZIPs. The operator should verify both complete
hashes before extraction and execute the checks through the existing terminal.
See [DEVICE-PACKAGE.md](experiments/cached-memory/DEVICE-PACKAGE.md) for the
cached package's exact extraction layout. The QEMU package replaces the earlier
`04e356...` version: its checker accepts the frozen guest's actual lowercase
T10 `check=ok` and explicitly rejects `check=BAD`. The candidate executable
itself is unchanged.

Automated delivery failed for concrete access reasons. Phone curl could not
validate the certificate using either existing trust store. Chrome blocked
`raw.githubusercontent.com` with `ERR_BLOCKED_BY_CLIENT`, and browser host
restrictions explicitly rejected the saved-file download page on `chatgpt.com`.
No certificate bypass or alternate browser surface was used. The terminal
remained available. Do not keep retrying these blocked routes or ask to rerun
already completed log searches.

## Device work after upload

1. Verify the two ZIP hashes in the upload folder, then unpack into separate
   fresh directories under `/data/local/tmp`. Follow each package's recorded
   layout and preserve the exact bundled files.

2. Run only the cached package's default `--cached-memory` path. Its binary
   hash is `f69664840ba2e7588e196849ea4ce9ff598a8c0081c22e8ac249830fb43f2b9c`.
   Retain output in a regular file so phase records can `fsync`. Producer LSE
   stays disabled; the ordinary-memfd control does exercise aligned LSE before
   Vulkan initialization. A pass must retain the explicit
   `CACHED_MEMORY_BASIC_PASS_ATOMICS_NOT_TESTED` qualification. Do not add
   `--cpu-atomics` automatically.

3. Use the same required-native QEMU package for bounded `-version`,
   `-machine help` and `-accel help` checks under a clean environment with its
   private `lib` directory. These informational checks allocate no guest RAM
   and do not qualify native execution. A separate original loader ZIP is
   unnecessary.

4. Run the package's [ordinary-memfd native benchmark](ios26-build/required-native/README.md).
   The script first checks that required-native plus disabled-native fails,
   then requires guest completion, positive native entry/SVC counts, positive
   native time and successful FP/copy checks. Capture the actual exit status
   and full retained log. Startup readiness alone is not a pass. This is the
   real native engine on ordinary memfd RAM, without GPU memory or iOS images.

5. Interpret each result separately. Root-shell qualification does not establish
   ordinary-app qualification. If both baselines pass, use the proposed
   [one-region native proof](ios26-build/ONE-REGION-NATIVE-PROOF.md) for the next
   narrowly bounded engine/GPU data integration. That design is not implemented.

## Integration boundary

CPU-cached noncoherent allocation is not a drop-in replacement for reims's
current shared-memory contract. Physical-range ownership, cache handoffs,
event/completion ordering, native aliases, copied-code invalidation and GPU
scatter handling remain work. The QEMU build still uses the existing memory
backend. Keep the app's GPU support gate unchanged until the actual combined
contract is implemented and qualified. See the
[memory architecture record](ios26-build/MEMORY-ARCHITECTURE.md).
