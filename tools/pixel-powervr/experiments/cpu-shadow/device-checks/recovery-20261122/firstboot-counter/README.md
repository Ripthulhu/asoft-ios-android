# Firstboot counter1 recovery

Current physical boundary: **the corrected source bundle and adapter are
installed, and their new read-only preflight passed**. The final displayed
resource observation is **2026-11-22 13:02:27.008628 UTC**. The capture reports
`PREFLIGHT_READY`, accepted true, exit zero, its child reaped, no forced
cleanup, adapter completion and restoration, seven preparation checkpoints,
unchanged inputs and an absent new guard work directory. Its exact stdout is
**21,988 bytes**, SHA-256
`42a0fefd327fd8be51eedb9be6fac4def61a18f5cf8bb274af23d6c093cbe222`.

This is a preflight result. **No counter1 execution owner installation or
launch, new boot, accepted firstboot checkpoint or saved-filesystem inspection
is established by this evidence set.** Attempts **`07-0001`** and
**`07-0002`** remain preserved and unaccepted. The preceding
[memfd recovery record](../firstboot-memfd/README.md) contains their physical
observations and the seven exact receipt pins from the last attempt.

## Physical observations and provenance

The original screenshots are preserved byte for byte beside matching
selected JSON transcriptions. These JSON files are **visual transcriptions,
not raw phone receipt exports**. The
[transcription review](physical-transcriptions-review.json) binds all sixteen
pairs with byte counts and SHA-256 hashes, and records the comparison with
the retained source and transfer manifests.

| Observation | Selected transcription | Original screenshot |
| --- | --- | --- |
| Oversized installer paste left a shell continuation prompt | [Continuation](oversized-transfer-continuation.json) | [Image](oversized-transfer-continuation.jpg) |
| Fresh shell reported UID/GID zero | [Root identity](fresh-shell-root-identity.json) | [Image](fresh-shell-root-identity.jpg) |
| Six new source, receipt, adapter and guard-work paths absent at 12:54:13.617458 UTC | [Path checks](counter1-paths-absent-125413.json) | [Image](counter1-paths-absent-125413.jpg) |
| Replacement transfer created | [Chunk 00](chunk-00.json) | [Image](chunk-00.jpg) |
| All eight chunks verified, then three exact sources installed at 13:00:35.500021 UTC | [Final assembly and install](chunk-09.json) | [Image](chunk-09.jpg) |
| Exact adapter installed at 13:00:56.452289 UTC | [Adapter installation](adapter-installed-130056.json) | [Image](adapter-installed-130056.jpg) |
| Read-only capture started at 13:01:22.335695 UTC | [Preflight startup](preflight-started-130122.json) | [Image](preflight-started-130122.jpg) |
| Read-only preflight passed, with final resources observed at 13:02:27.008628 UTC | [Preflight result](preflight-passed-130227.json) | [Image](preflight-passed-130227.jpg) |

The individual `chunk-01` through `chunk-08` pairs retain each latest
verification line. They have no displayed execution timestamp, so none is
inferred. The failed large paste did not install the new sources: the
subsequent six-path check observed all of them absent before the replacement
transfer. The final source-install receipt is
`/data/local/tmp/pixel-gpu-transfer-sxtv33sh/counter1-guard-inspector-install.json`,
with visually confirmed SHA-256
`7a171b5806060ffe993b781e9dad742a8fe21dc893792fe29e64d0bcbd11f9514f`.

The preflight capture wrapper was PID **21744**, start time **7750712**;
its direct child was PID **21745**, start time **7750735**. The exact displayed
child command was Python `-I -B` followed by the counter1 adapter source,
without `--execute`. The final capture reports that child reaped.
`MemAvailable` was **4,466,745,344 bytes** before and **4,428,693,504 bytes**
after; both exceeded the unchanged **4,026,531,840-byte** launch floor.
Free space was **73,747,447,808** and **73,747,390,464 bytes**, respectively,
both above the separate 4,500,000,000-byte floor. These are observations at
the displayed times, not a guarantee of conditions at a later launch.

## Why a new guard is required

Attempt `07-0002` reached native execution and answered shell sync, then the
old guard rejected a post-stop `query-blockstats` response containing both
`root` and `floppy0`. All five projected top-level/parent/backing failure
counter pairs were integer zero. That attempt never collected `query-block`
evidence proving the extra backend had no medium, so its result remains
`INCOMPLETE` and cannot be accepted retrospectively.

The new guard permits only matching inventories containing `root`, optionally
with the precisely qualified empty default `floppy0`. It binds the root node,
attached device and writable state across the two replies. The optional
floppy must have no node, attached device or inserted medium and the exact
`query-block` fields:

```json
{"device":"floppy0","type":"unknown","locked":false,"removable":true}
```

Every returned failed-write and failed-flush field still requires an actual
integer zero, including all parent/backing nodes. The protocol becomes
`stop` → `query-blockstats` → `query-block` → `quit`, with a five-second bound
on each query. The matching saved-firstboot inspector pins the new guard,
recomputes that predicate, and binds both replies to the actual ordered trace.
Shell-sync, native execution, cleanup, source, session and checkpoint gates
remain required.

The [qualified QEMU source analysis](guard-revision/SOURCE-BASIS.md) explains
the complete empty-backend shape. Its `removable=true` value follows the
qualified implementation's behavior for an unattached backend. Earlier local
candidates requiring false were never installed; only the corrected export
is retained here. The analysis also distinguishes failure counts from the
`account_failed` timing policy and explains the limited meaning of nested
zero-initialized node summaries. No claim is made about the internal return
value of QEMU's stop flush; later raw-journal and read-only filesystem checks
remain mandatory.

## Exact reviewed artifacts

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Firstboot guard | 25,686 | `ea40638312d6ac41607806ecb03c148fbd0677df6ab01480e13fd40536869674` |
| Saved-firstboot inspector | 26,030 | `2b127ecda390b199287358cdad7e6e7774f5b787148aea524e7b0247a2640cf3` |
| Unchanged inspection guest helper | 16,829 | `ada26de8ababb11bb4af20e558708545eb64fd516481359fd5d0ccf6a7cbae2b` |
| Source-bundle installer | 31,389 | `3f2811db3507908a02c79e86ccfb28d248163a0c03267657d12ed110424a41a3` |
| Counter1 memfd adapter | 9,104 | `1402321c22ae98b0ba7094f9e121cb169f2bf4aea38d0272b957f08a26259725` |
| Read-only preflight capture | 25,537 | `a4df944912e700c5a1ac88ce784cbb6e79e7819f016a1175b995dd71da1e933f` |

The byte-exact [guard revision export](guard-revision/README.md) includes its
four-file patch, changed tests, unchanged guest helper, baseline and manifest.
The [final focused receipt](guard-revision/focused-tests-reviewed.json) and
[complete log](guard-revision/focused-tests-reviewed.log) record **57 passing
offline tests**, unchanged source hashes and no physical VM/GPU/device run.
New `query-block` fixtures are source-grounded synthetic evidence. The test
support source is identified in the baseline and differs from the frozen
phone runner; this result is not presented as a physical execution of that
runner.

The [main-source integration record](main-source-integration.json) compares
the four production/test files at Git HEAD
`ac0327bc46f71098c9d7ef94eb6769f610f54f82` with the working-tree copies and
this reviewed export. Every old byte count/hash matches the reviewed
baseline; every integrated file equals the exact tested export. The record
retains the original 57-test receipt without rerunning the suite. Its local
`prepare_ios26.py` support hash is
`adfd8cf927839c96db5bf00bef7e0c9a157839d64a84138320ec53013b790cfc`;
the unchanged frozen phone runner hash is
`c77bc990e56dcb47d651f9c054c41313a6671498a5b2494e96bb522ae868fb1a`.
The separate downstream compatibility integration and 122-test evidence are
recorded in [downstream-counter](../downstream-counter/README.md).

Seven complete qualified QEMU source files are retained under
`qemu-source-basis/7a900afb62ddf94713e38ac5a4aafe1d42c9efa8/`. The original
[source-basis manifest](guard-revision/source-basis.json) keeps its authoring
paths and immutable upstream URLs. The local paths in
[retained-files.json](retained-files.json) map every copied artifact to this
recovery directory with its exact byte length and SHA-256. Original authoring
manifests and README files have not been rewritten.

The [adapter source](package/run_guard_memfd_adapter.py) changes only the
source/guard/work paths, guard pin and receipt suffixes from the passed memfd1
adapter. Its libc call, argument conversion, flags, errno handling and
restoration behavior are unchanged. It consumes the existing one-page smoke
receipt with SHA-256
`57d7239160422a858ed9882191c5012fd20a20d5b790f482be15013266f313bd`;
no repeat probe or system Python change is required.

## Bounded source transfer

The original [large transport](package/01-install-counter1-checks.command.txt)
is retained as historical evidence of the attempted delivery. It remains
30,606 bytes, SHA-256
`7391ab715e57698fec52a7f065c31e08f1ee82562cf45357a1651b4f92abe968`.

The replacement [transport manifest](package/chunked-checks-transfer-v1/transport-manifest.json)
binds ten commands: `00_begin_transfer`, eight chunk writes, then
`09_assemble_and_install`. Its maximum individual command is **5,821 bytes**.
The transfer directory is:

```text
/data/local/tmp/pixel-gpu-transfer-sxtv33sh/counter1-checks-installer-transfer-v1
```

Each command uses Python `-I -B -c`. Initialization exclusively creates the
directory and pinned manifest. Each chunk is exclusively written, fsynced and
read back. Final assembly requires exactly the expected inventory and checks
all chunk hashes, the joined encoded payload and the bounded decompressed
installer. It saves the exact original installer, reserves execution once,
and invokes those unchanged bytes. Success or failure receives a separate
execution-exit record. Existing or partially written artifacts cause refusal;
they are not deleted or overwritten.

Independent source and in-memory transport review confirmed all ten payloads
and the reassembled **31,389-byte** installer. This verification performed no
device operation and did not execute the helpers. The later physical
screenshots now record commands 00 through 09 completing, all eight chunk
digests matching, the three sources installed and `EXACT INSTALLER RETURNED`.
The installer's `execution_started=false` field records that this action did
not execute the installed guard or inspector.

## Installation and preflight prerequisites

| Purpose | Fresh phone path |
| --- | --- |
| Guard source | `/data/local/tmp/pixel-boot-checks-counter1/firstboot/guard_ios26_firstboot.py` |
| Saved inspector source directory | `/data/local/tmp/pixel-saved-checks-counter1` |
| Source-bundle installation receipt | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/counter1-guard-inspector-install.json` |
| Memfd adapter source | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-firstboot-memfd-adapter-counter1.py` |
| New guard work | `/data/local/tmp/pixel-firstboot-guard-e9cc754-counter1` |

After the source bundle is verified, the separate
[adapter installation command](package/02-install-counter1-adapter.command.txt)
stages the adapter without execution. The
[preflight capture command](package/03-capture-counter1-preflight.command.txt)
runs only the adapter's default read-only preflight, without `--execute`.
Its [capture source](package/capture_counter1_preflight.py) binds all three
installed check sources, the existing smoke and partition audit, and both
preserved failures. It verifies the seven exact `07-0002` receipt pins,
actual attempt metadata, original incomplete counter event, restored adapter,
clean outer exit and absence of the recorded old process identities before
and after the preflight. The fresh guard work must remain absent.

The actual accepted counter1 preflight stdout is now pinned above. That
**21,988-byte** result must be used when finalizing the new execution owner;
the earlier memfd1 preflight pin must not be reused for the revised guard.
Provisional owner, launcher and status sources are omitted from this retained
package. Their future installation and execution need their own evidence.

Any later execution must preserve both failures, create only fresh attempt
`07-0003`, retain the **3 GiB guest**, **3,840 MiB fresh-launch** and **512 MiB
running** memory floors, satisfy the separate free-space requirement, and
use the existing owned-child deadline/reap rules. An accepted firstboot must
then pass its separate saved-filesystem inspection. No new boot, GPU-path or
application completion is established by these source or transport artifacts.
