# Continue the native Pixel iOS26 work

## Latest checkpoint: resume5 inspection completed, filesystem acceptance refused

**The resume5 inspection finished at 2026-11-22 20:58:05.315390 UTC and was not accepted.** The actual result-bound projection at **21:11:04.460470 UTC** establishes that the strict root journal initialization check passed, while **Data was refused as `nonempty_journal`**: `start=512`, `end=614400`, with a valid header checksum. Neither filesystem check ran. Its native VM completed normally with all three native witnesses, exit zero and clean unforced cleanup. Wrapper **3218 / 10596300**, inspector **3219 / 10596334**, QEMU **4784 / 10606734**, and observer **31097 / 10563710** are all absent. All bound inputs and preserved receipts remain unchanged. **Do not relaunch any completed attempt.** Start with [the actual resume5 result](device-checks/recovery-20261122/resume5-saved-inspection/RESULT.md).

The owner successfully launched at **20:55:38.023625 UTC**, using the independently verified fresh observer **31097 / 10563710** and its 3,841-byte READY receipt `7e22ccf73c349f9c396a54cba434ec98a93fef0a44028a0856f3ebfd39be5f51`. An earlier submission refused on the unchanged 2,816 MiB memory floor before any execution artifact was created. The subsequent read-only check found all seven execution paths absent and 3,491,127,296 bytes MemAvailable, allowing the same reviewed launcher to proceed. No memory operation was performed during this work.

The [current recovery state](device-checks/recovery-20261122/CURRENT_STATE.md) points to the completed result and its preserved evidence. The completed outcome is published at `2630efc33bebd65a0a61eb9166da4eb0ecca2483`. A separate [Data journal structure diagnostic](device-checks/recovery-20261122/resume5-saved-inspection/data-journal-diagnostic/README.md) now has independently reviewed parser/host sources, 60 passing focused tests, nine source-only installation commands and a separate launcher. It is not yet installed or executed at this preparation checkpoint. Its four fixed native reads cover Data's two headers, JIB and 8 MiB journal. The nonempty-journal refusal remains in force; any later recovery needs a separate fresh copy-on-write descendant and a new clean inspection.

The installed inspector sources and accepted preflight are published at `afd5db2a3c2be063d248f713a3de2dfc7e6250b7`; reviewed inspector sources and preparation are at `77a1223312d4cdff97d4ec14ef70bc8afbcd6997`, and the completed root JIB diagnostic result is at `18b3a1bd8e8eb7f5c78787890edb286715135d2c`.

**Actual resume5 preflight observation: 2026-11-22 20:44:38.734136 UTC.** The revised inspector, supervising owner and sibling observer sources are installed with exact release hashes. Fresh preflight passed with zero owner/inspector exits, clean unforced reap, absent recorded identities, unchanged inputs and unused inspection work. Its actual output is **9,069 bytes**, SHA-256 `4630b5dc921d3bee52d4805cc829e3624144b763d27b53937443e43c69db44f6`, with all 32 digest bytes retained in [the selected observation](device-checks/recovery-20261122/resume5-saved-inspection/physical-observations/preflight-selected.json). Do not rerun this completed preflight. The separately reviewed execution bindings and fresh observer READY were subsequently used for the live launch above.

The resume4 inspection and its observer have finished. Native execution and cleanup were clean, but inspection was rejected at `root_baseline_jib_changed` before fsck. The subsequent bounded JIB diagnostic also finished cleanly. Its actual result-bound summary and range page, observed at **2026-11-22 20:21:20.762494 UTC** and **20:21:32.934758 UTC**, establish exactly one differing byte: baseline flags `0x5` became saved flags `0x1`, with the rest of both 4,096-byte blocks identical. See [the actual diagnostic result](device-checks/recovery-20261122/resume4-saved-inspection/jib-diagnostic/RESULT.md).

A separate [root initialization classification](device-checks/recovery-20261122/resume5-inspector-revision/README.md) has passed 60 tests and an independent rerun. It requires the exact authored baseline JIB and zero baseline journal, only the NeedInit-bit transition, and a valid initialized-empty saved journal before the existing forced read-only filesystem checks. Actual installation, accepted preflight, observer READY, launch and rejected completion are retained; source tests do not establish a physical filesystem pass.

**Do not relaunch the completed firstboot, resume4 inspection, JIB diagnostic, resume5 preflight, resume5 inspection or either observer.** Preserve all prior outputs. Data's transaction contents, full filesystem acceptance, later preparation, GPU completion and APK readiness remain gated. The launch observations below are historical and superseded by this section.

## Historical resume4 launch observation — superseded

**Live observation: 2026-11-22 17:27:01.555304 UTC.** The reviewed execution
launcher started the fresh resume4 owner once. Wrapper **20063 / 9342623** and
inspector **20064 / 9342659** are live. At this observation the inspection work
directory was not yet created and no QEMU identity was recorded; the inspector
was still before native-helper startup. No exit or inspection result exists
yet. The preflight, reviewed sources, all bound inputs, nineteen resume1 failure
pins and sixteen resume2/diagnostic pins remain unchanged.

The independent observer **18179 / 9323114** was launched before the owner and
verified live in its own session. Its actual READY record is **3,839 bytes**,
SHA-256 `98bd34d1c290027db202ce1ea94c57029fe2c520d5c88c601eecd32ca1c9c215`.
All 32 digest bytes were independently verified. The execution launcher checks
its exact source, readiness bytes, live identity, scope and fresh heartbeat
again before spawning. The installed execution launcher is **22,309 bytes**,
SHA-256 `fda158506174594a01366d2c6fb2d1a4d7628fca783ef89d7e0a8d5c490306f5`.

See the [live inspection observation](device-checks/recovery-20261122/resume4-saved-inspection/physical-observations/inspection-running-172701.json)
and [actual observer readiness](device-checks/recovery-20261122/resume4-process-observer/procstat1/physical-observations/observer-ready-172340.json).
**Do not relaunch.** Use the reviewed read-only status and final/pin readers
for this attempt, preserving every current and prior artifact. No revised
saved-filesystem inspection pass, GPU completion or APK readiness is claimed.

### Accepted fresh resume4 preflight

**Accepted preflight observation: 2026-11-22 17:20:15.904994 UTC.** The fresh
resume4 owner and preflight inspector exited zero with clean, unforced reap;
both recorded identities are absent. Bound inputs are unchanged, the fresh
inspection work path is unused, and inspection execution has not started.
Actual preflight stdout is **9,069 bytes**, SHA-256
`d68aa23ba833c8939ace08005c573f11764c104bbbae29a5f0285677c7239bf6`.
All 32 displayed decimal digest bytes were independently verified.

The corrected owner was launched at **17:16:20.452112 UTC**, wrapper
**14189 / 9280543**, inspector **14190 / 9280594**. It cleared the preserved
receipt checks and completed the original full input validation. The installed
owner is **48,469 bytes**, SHA-256
`c5cc01768be23c0a7e3ad1364cb89a3dd8562288ac3c51f5eaef35ce7c039f10`.
It reuses the exact reviewed inspector pair at
`/data/local/tmp/pixel-saved-checks-resume3`; its owner/work paths are fresh
resume4 paths. The observer and inspection owner were subsequently launched as
recorded above.

See the [actual accepted preflight](device-checks/recovery-20261122/resume4-saved-inspection/physical-observations/preflight-accepted-172015.json)
and [independent evidence review](device-checks/recovery-20261122/resume4-saved-inspection/independent-preflight-evidence-review.json).
The preflight is complete: do not rerun it. It is the exact binding consumed by
the running inspection owner; it does not establish filesystem acceptance.

## Preserved resume3 prerequisite refusal and receipt correction

**Physical observation 2026-11-22 17:06:29.127032 UTC.** The revised inspector
pair, resume3 owner/preflight launcher and independent observer sources were
installed with exact reviewed byte counts and hashes. The preflight owner
launched at **17:01:52.504058 UTC**, but refused in its prerequisite checks
before creating the owner directory or starting an inspector child. Wrapper
**6603 / 9193748** is absent. No revised filesystem inspection has run.

The refusal was a historical selected-evidence transcription error in the
preserved resume2 observer's `exit.json` hash. The actual **478-byte** receipt
has SHA-256 `4af8f8a2feeb3e8103bfaf61c8393aa58f94c9ea01e32f06e51bbaee3cdbb920`.
The old selected JSON and installed resume3 owner instead recorded `6` at
zero-based hex offset 40, where the original screenshot and the fresh read
show `0`. All 32 digest bytes were reread at **17:07:17.404781 UTC**. The other
three observer receipt hashes match their historical bindings. This is a
copied-hash error, not observed change to the phone receipt or a filesystem
failure. Preserve the original records, installed sources and refused launch.

See the [selected refusal](device-checks/recovery-20261122/resume3-saved-inspection/physical-observations/preflight-refused-170629.json)
and [fresh receipt identities](device-checks/recovery-20261122/resume3-saved-inspection/physical-observations/prior-observer-pins-170717.json).
The first status reader reported `PENDING` solely because the final preflight
receipt was absent; those earlier observations did not establish liveness.

A separate **resume4** owner/preflight/observer package was prepared with
the corrected binding and fresh paths. It reuses the exact already installed
`/data/local/tmp/pixel-saved-checks-resume3` inspector pair. The revised
inspector itself, native execution, cleanup, resource floors and all filesystem
acceptance rules remain unchanged. Obtain an actual accepted fresh preflight
and live independent observer READY binding before launching once.

### Reviewed inspector correction

**Source review completed 2026-11-22 16:51:09 UTC.** The revised inspector
classifies the unchanged baseline iOSRoot alternate boot marker only with exact
corresponding volume-header and JIB bytes, a clean primary, and independently
checked matching empty journal metadata. Both forced read-only fscks and the
post-fsck raw metadata recheck remain mandatory. It also explicitly refuses
runtime inconsistency bit 14 on every header. Data otherwise retains its
existing journal and legacy-bit policy; native execution, cleanup, resource
floors and full-chain preservation are unchanged.

The author and independent reviewer each passed **45 focused tests**, including
negative mutations, host proof/log rejection and a post-fsck header change.
Reviewed host: **32,576 bytes**, SHA-256
`245393bf59b9e731fa9f511b9368e5676f86a8ad0d6b8e03859e73239bf8559c`.
Reviewed guest: **18,979 bytes**, SHA-256
`f52e4d4ec78c08bf73ec37efac8aa6ecb99a5ab2baf174481fda8b286fb49d97`.
See the [revision and rationale](device-checks/recovery-20261122/resume3-inspector-revision/README.md)
and [independent source release](device-checks/recovery-20261122/resume3-inspector-revision/independent-review.json).
The original executed counter1 sources remain preserved unchanged.

The reviewed correction is published at
`78b9c821541ecd0d32452e3e69481123b24154be`; its exact tree, parent and raw message
were verified after a guarded fast-forward and public fetch. See the
[source publication receipt](device-checks/recovery-20261122/resume3-inspector-publication-verified.json).
Never reuse failed output paths or treat unit tests as physical filesystem
acceptance. No revised physical inspection has started or passed.

The completed header diagnosis below is published at
`b1b919ab5b8cd8b652369eb796fe971ccd8d6d6d`; its tree, parent and raw message were
verified after a guarded fast-forward and public fetch. See the
[diagnostic publication receipt](device-checks/recovery-20261122/header-diagnostic-publication-verified.json).

### Completed header diagnosis

**Header observation: 2026-11-22 16:39:46.597544 UTC.** The bounded native
`qemu-img` diagnostic completed all eight current/baseline header reads with
clean, unforced child exits and unchanged disk identities, bound metadata and
tooling. It started no guest VM and performed no mount, replay, repair or fsck.
It did not recompute full disk hashes or establish inspection success.

All eight headers are journaled (bit 13 set), and all eight have runtime
inconsistency bit 14 clear. The exact flags are:

| Volume / header | Saved image | Audited baseline | Relevant difference |
| --- | --- | --- | --- |
| iOSRoot primary | `0x80002100` | `0x80002100` | Clean-unmount bit 8 set; bit 11 clear |
| iOSRoot alternate | `0x80002800` | `0x80002800` | Legacy boot-inconsistency bit 11 set in both |
| Data primary | `0x80002000` | `0x80002100` | Saved primary clean-unmount bit 8 clear |
| Data alternate | `0x80002100` | `0x80002100` | Clean-unmount bit 8 set; bit 11 clear |

The corresponding saved/baseline iOSRoot primary headers have identical
512-byte hashes, as do the corresponding alternate headers. The exact frozen
predicate rejected the **pre-existing iOSRoot alternate bit 11**, not a missing
journal. This is not a filesystem-health verdict or proof that entire
partitions are unchanged. The nonjournaled-root hypothesis is ruled out.

The actual diagnostic receipt is **14,542 bytes**, SHA-256
`d768516e7cc9846e35aefa5f7583797b4cc0c129402a16994965501c69882ba6`.
See the [selected header evidence](device-checks/recovery-20261122/resume2-saved-inspection/header-diagnostic/physical-observations/headers-observed-163946.json)
and its [independent review](device-checks/recovery-20261122/resume2-saved-inspection/header-diagnostic/independent-header-result-evidence-review.json).
The optional compact scalar readers are prepared and reviewed but were not
needed or executed; the full terminal evidence resolved the selected fields.

The exact native tool's synthetic proof passed at **16:35:39.842322 UTC**:
`bs=512,count=3,skip=2` returned precisely the expected third 512-byte block of
an unchanged 2,048-byte input. Its count is an input limit before skip; the
eight header reads therefore use `count=skip+1`. Prior help-only capability
refusals remain preserved. The passed capability receipt is **2,659 bytes**,
SHA-256 `897cb1faaab342ff576fcc8a3e8d958282f0d44fd0162c445457853cf1d8c11c`.

The reviewed correction above is the next implementation step arising from
this evidence. Preserve every old installed source and failed attempt; do not
retroactively accept resume1 or resume2. Firstboot 07-0004 remains accepted;
downstream persona, activation, apps, GPU and APK stages remain blocked on a
valid saved inspection.

The four preceding recovery checkpoints were published and fetched at
`39bf59ca283b68fcb82bf69cd98c5250b022a6b9`. Their exact trees, raw commit messages,
parent chains and 258 file-version entries were independently verified. See the
[publication receipt](device-checks/recovery-20261122/resume2-publication-verified.json)
and [independent publication review](device-checks/recovery-20261122/independent-resume2-publication-review.json).

## Preserved resume2 run: native cleanup clean; guest inspection rejected

**Outcome observed 2026-11-22 16:03:29.505296 UTC.** The retry's native VM
completed with natural exit zero, `echild=true`, no forced QEMU or descendants,
and all native execution witnesses. It ran from **16:02:31.003433** to
**16:02:55.190941 UTC**. This run did not reproduce the prior cleanup rejection;
it does not explain the old PID 13344 or establish a cleanup fix.

The inspector then rejected the returned guest inspection metadata:
`ValueError: guest inspection incomplete; retained metadata classifies the boundary`.
The owner and inspector exited **2**, `accepted=false`, with clean unforced
outer reap. All three recorded owner/inspector/QEMU identities were absent.
The backing chain, preparation/guard records and nineteen prior failure pins
remain unchanged. The failed new work must remain preserved and cannot supply
success pins.

At **16:08:29.576395 UTC**, the bounded guest-result query classified the failure
as **`volume_not_journaled_or_inconsistent` on `iOSRoot`**. Both attachments were
read-only; nothing was mounted, replayed or repaired. GPT and baseline GPT
checks passed. No filesystem checker ran, and neither fsck diagnostic file was
created. The frozen predicate combines a missing journal bit with a set legacy
boot-inconsistency bit, so this code alone did not identify the actual flags
or prove filesystem corruption. The later bounded header diagnostic above
resolved which condition failed. This preserved run's runtime and acceptance
rules remain unchanged.

The five failed-result metadata identities were reread with all **160 decimal
digest bytes** at **16:12:31.539183 UTC** and independently verified. See the
[guest boundary evidence review](device-checks/recovery-20261122/resume2-saved-inspection/procstat1/independent-guest-boundary-evidence-review.json)
and [exact failed-result pins](device-checks/recovery-20261122/resume2-saved-inspection/procstat1/physical-observations/guest-boundary-pins-161231.json).

At **16:04:28.013535 UTC**, the independent observer reported
`OBSERVATION_FINISHED`, no observer errors, no remaining tracked identities and
its own process absent. It retained 2,294 samples, zero thresholded sampling
gaps, thirteen process-read gaps and two unavailable numeric discovery reads.
These finite samples do not establish continuous observation or signal causality.
See the [reviewed inspection outcome](device-checks/recovery-20261122/resume2-saved-inspection/procstat1/independent-outcome-evidence-review.json)
and [final observer projection](device-checks/recovery-20261122/resume2-process-observer/procstat1/physical-observations/observation-finished-160428.json).

### Preserved resume2 launch and preflight

**Execution launched 2026-11-22 16:00:47.836254 UTC. Do not relaunch.**
The fresh saved-inspection owner is **13387 / 8827282**, with inspector
**13388 / 8827298**. At **16:01:27.213913 UTC**, the external observer
**11031 / 8803490** was live in its independent session, had bound those two
identities, and was waiting for the native helper. At that intermediate point,
it reported zero sampling or selected-process read gaps.
The output is `/data/local/tmp/pixel-saved-audit-e9cc754-resume2`; use the
reviewed read-only status and final readers before making any further decision.

**Fresh preflight observation: 2026-11-22 15:38:40.651056 UTC.** The new
`resume2` saved-inspection owner passed its read-only preflight with clean,
unforced reap, absent recorded processes, unchanged bound inputs and an unused
inspection output path. Raw stdout is **9,070 bytes**, SHA-256
`84b31f4f08744f6adeb20ab5af308b1d10c839803c051d4bba577201a4ad3760`.
Its public inspector output matches the earlier preflight because that output
omits the destination work path; the new source, command, launch and owner
receipts establish the actual fresh invocation.

The new source is `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-saved-inspection-resume2.py`,
**35,799 bytes**, SHA-256
`445f16736ff3f0c4aca2f9d825f4b71b9264bc24b177fe3a8281ca9c6e0f1e0b`.
It retains the existing inspector, runtime, cleanup and acceptance behavior,
while additionally verifying the nineteen preserved failed-inspection bindings.
Fresh preflight launched at **15:37:09.352352 UTC**, wrapper
**32296 / 8685433**, under
`/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume2-owner`.
The future output is `/data/local/tmp/pixel-saved-audit-e9cc754-resume2`.

See the [resume2 package](device-checks/recovery-20261122/resume2-saved-inspection/README.md)
and [independent physical preflight review](device-checks/recovery-20261122/resume2-saved-inspection/independent-preflight-evidence-review.json).
Its 22 focused owner tests and source/transport review passed. The user's raw
prior `owner.json` and `exit.json` uploads exactly match the already verified
phone hashes; preserved copies are in the new package's `supplied-prior-receipts`.

The separate `procstat1` process observer and execution launcher passed source,
installation and actual-readiness review. The observed ready receipt is
**3,839 bytes**, SHA-256
`4c3abfebaeee33ce4c1c59f5195292116b016bc869d27ff5f0e38a5047981a3d`.
The execution launcher checked its exact source, ready bytes, fresh heartbeat,
live identity and independent session twice before starting the owner.
The observer remained outside the inspector's descendant tree and did not
alter the original cleanup code or acceptance rules.
Preserve the failed resume1 work and the already accepted firstboot below.

The first observer candidate was safely held before installation because a
physical self-only probe found no `/proc/<pid>/task/<pid>/children` file on this
phone. Its reviewed sources and transport remain preserved. A separate
`procstat1` observer revision was installed and launched. At **15:49:17.066099 UTC**, an
aggregate-only compatibility probe read all **894** numeric process `stat`
records in **53.212 ms**, with no vanished, denied or malformed entries; its
self identity, parent and pending-signal field checks passed. This supports
bounded process-edge discovery from `stat`; it does not establish any new
inspection outcome. See the [physical compatibility observations](device-checks/recovery-20261122/resume2-process-observer/physical-observations/).

## Preserved resume1 outcome: firstboot accepted; saved inspection rejected

**Latest inspection outcome: 2026-11-22 14:58:55.245032 UTC.** Firstboot
**07-0004 remains accepted**. Its subsequent saved-filesystem inspection is
**INCOMPLETE** and must not release the persona/activation/apps stages.
The inspector and outer owner exited 2; the outer owner cleanly reaped its
inspector without forcing, but did not accept the result. Owner
**12027 / 8432383**, inspector **12044 / 8432415** and QEMU
**13326 / 8442942** were absent at the final observation. The QEMU start tick
was directly reread from `vm.child.json`; an earlier selected transcription
used 8442923, and the read-only collector correctly refused that value.

The QEMU leader exited zero and reported native initialization, execution and
final SVC witnesses with no fatal markers. Its cleanup nevertheless recorded
**`forced_descendants=[13344]`**, which fails the unchanged acceptance rule.
`full_backing_chain_unchanged` and `preparation_and_guard_unchanged` were true,
with no identity error. The guest archive was not extracted or accepted after
the VM supervision rejection. No saved-filesystem success is established.

The exact qualified native source uses a factory and worker processes with
parent-death signals. The frozen supervisor immediately signals remaining
direct children after a nonblocking reap. An in-flight parent-death cascade
and a lingering orphan are both hypotheses; PID 13344's role remains unknown.
The narrow stderr projection found no identifying PID record. Preserve this
failure and use a fresh, separately owned read-only inspection with an external
owned-process observer for diagnosis before changing cleanup behavior.
Do not whitelist the PID, erase its forced entry, weaken the clean-reap gate,
reuse failed paths or release downstream disk mutation.

See the [inspection record](device-checks/recovery-20261122/resume1-saved-inspection/README.md),
[source-backed cleanup analysis](device-checks/recovery-20261122/inspection-cleanup-analysis/README.md)
and [blocked apps-preparation package](device-checks/recovery-20261122/resume1-apps-prep/README.md).
The apps package passed 25 focused tests and independent draft/transport review,
but `INSPECTION_SUCCESS_PINS` remains `None`; no apps owner is released or staged.

### Accepted firstboot evidence

**Latest completed-boot observation: 2026-11-22 14:45:21.641036 UTC.**
Resume1 accepted `GUARDED_FIRSTBOOT_COMPLETE` for **07-0004**. The outer owner
finished at **14:45:16.838924 UTC** with exit/owner-exit zero, `accepted=true`,
clean guard reap, no forced cleanup, no cleanup errors and no wrapper error.
The recorded owner **3271 / 8341942**, guard **3279 / 8341984** and QEMU
**5039 / 8355681** identities were all absent at observation.

The VM returned `VM_OBSERVATION_COMPLETE`: readiness milestone, settling,
shell sync, native initialization, native execution and final native SVC
witnesses were true. Stop/quit were acknowledged, QEMU exited zero and was
reaped without forced cleanup. Original bound inputs were unchanged. The accepted
`ios26-firstboot.json` is **803 bytes**, SHA-256
`0c3418d053477d73d210eb8a22dd28e49cff61ff5140f77b6c97d4c96c8c079e`.
Its attempt is **07-0004** and status is `STAGE_COMPLETE`.

The **14:49:03 UTC** pinned guard-result projection confirmed the repaired
counter boundary on the actual run: root plus the explicitly empty `floppy0`,
all five returned statistics nodes with failed writes/flushes zero, and one
`GUARDED_SUPERVISION_PASSED` event with shell sync. Recursive statistics nodes
are not separate devices. The stop-internal flush return remains unobserved;
the required saved-filesystem inspection is the next gate.

See [resume1 success evidence](device-checks/recovery-20261122/resume1/README.md)
and the independently verified
[nine success bindings](device-checks/recovery-20261122/resume1/physical-observations/success-bindings-144627.json).
Continue with the separately bound
[saved-firstboot inspection package](device-checks/recovery-20261122/resume1-saved-inspection/README.md).
Do not replay the accepted firstboot or any historical owner/cache action.
Do not run persona, activation, apps or other disk-mutation helpers before
`SAVED_FIRSTBOOT_INSPECTION_PASSED` and clean inspection-owner reap.

**`gpu_execution=false` and `gpu_path_complete=false`.** This is an accepted
native firstboot checkpoint, not a completed GPU/UI path or final APK.
All original memory, native execution and ownership requirements remain intact.

The saved-inspection preflight subsequently passed with raw output **9,070
bytes**, SHA-256 `84b31f4f08744f6adeb20ab5af308b1d10c839803c051d4bba577201a4ad3760`,
clean unforced reap, unchanged inputs and absent inspection work. Its separately
reviewed execution launcher started at **14:54:58.850272 UTC**. At
**14:56:26.060073 UTC**, wrapper **12027 / 8432383** and inspector
**12044 / 8432415** were alive, with inspection work and QEMU still absent
during validation. This was an intermediate sample before the rejected final
result above. Its existing source, owner, work and receipts must be preserved;
do not replay this launcher or reuse these paths for a retry.

## Historical resume1 checkpoint: firstboot running at 14:42 UTC

**Latest status observation: 2026-11-22 14:42:41.306331 UTC.** The same resume1
owner **PID 3271 / start 8341942** and guard **PID 3279 / start 8341984** were
alive, and firstboot attempt **07-0004** was present. Its QEMU identity was
**PID 5039 / start 8355681**, also alive. The owner exit receipt and firstboot
checkpoint were absent.

The in-progress VM receipt reported `status=INCOMPLETE`, stage
`ios26-firstboot`, and `error=null`. `native_initialization=true` had been
observed; `native_execution`, `native_svc_final` and `gpu_execution` were still
false at this early sample. This is an active attempt with initial native
setup evidence, **not a completed firstboot or a final failure**. Continue
read-only observation of those exact identities; do not launch another owner
or reuse the attempt/work paths.

Available RAM was **2,869,805,056 bytes** and free swap **1,628,155,904 bytes**.
This is a running-VM sample after allocation; the running floor remains
**512 MiB**, while the unchanged **3,840 MiB** floor applies to fresh launch.
At the earlier 14:41:16 sample, owner/guard were alive and the guard session
existed, but the attempt and QEMU had not yet been observed.

The reviewed launcher had returned `FIRSTBOOT_OWNER_LAUNCHED` at
**14:39:54.441785 UTC** after passing its fresh prerequisites.
The wrapper identity is **PID 3271 / start 8341942 / session 3271**; the launcher
was PID 3269 / start 8341868. The launch receipt reported
`FIRSTBOOT_OWNER_LAUNCHED`, with **4,073,943,040 bytes / 3,885.21 MiB** available
RAM against the unchanged **4,026,531,840-byte / 3,840 MiB** floor, and
**72,982,781,952 bytes** free storage against the **4,500,000,000-byte** floor.

The owner, guard and QEMU are now observed alive with **07-0004** present.
The attempt outcome remains pending. Do not replay the launcher while its process/state
is unresolved. Use the [resume1 read-only status observer](device-checks/recovery-20261122/resume1/package/status_resume1_owner.py)
and recorded process identities; preserve all existing source, launch and
attempt evidence. No firstboot success, saved inspection or complete GPU path
is claimed.

Before that launch, one reviewed **`sync` followed by `drop_caches=3`** request
completed at **14:39:24.831751 UTC**. System MemAvailable changed from
**3,848,491,008** to **4,000,583,680 bytes**, an observed increase of
**152,092,672 bytes / 145.046875 MiB**. Original input stat identities and the
kernel OOM-kill counter were unchanged. No process kill, manual thaw or
persistent policy change was requested. The later launch took its own fresh
resource reading; the cache-action sample alone was still below the launch
floor and was not treated as execution clearance. The same measured cache
operation must not be replayed over its exclusive receipt.

The installed owner remains **42,490 bytes**, SHA-256
`862af55267f7ecd1273faf8f161e4065161f1bf49a5df6614cfb2571fc95d473`;
the adapter is **9,101 bytes**, SHA-256
`ede70023bc1e05b08730b48fab1016c3e665c0e83469509e5b8b74c6f2364ec7`.
The owner binds the freshly accepted **21,988-byte** resume1 preflight
`42a0fefd327fd8be51eebb9be6fac4def61a18f5cf8bb274af23d6c093cbe222`.
See the [resume1 record](device-checks/recovery-20261122/resume1/README.md) for
source, transfer, correction, preflight and launch provenance.

## Earlier resume1 checkpoint: installed, launch refused before execution

**Last execution-status observation: 2026-11-22 14:34:00 UTC.** Continue from the
[resume1 recovery record](device-checks/recovery-20261122/resume1/README.md).
The full published checkout at `d5453936b8c41c6f75025ba11630cfa2c9781311` was restored.
The lost memory1 draft was explicitly reconstructed as a new resume1 package;
no byte-for-byte recovery of the unpublished memory1 files is claimed.

The adapter, corrected capture, finalized owner and detached launcher are now
installed with verified complete hashes. Fresh read-only preflight passed at
**14:28:05 UTC**, with clean reap/restoration, unchanged inputs, seven checkpoints
and absent guard work. Stdout is **21,988 bytes**, SHA-256
`42a0fefd327fd8be51eebb9be6fac4def61a18f5cf8bb274af23d6c093cbe222`.
The same output digest as the historical preflight is expected: the guard output
does not include the external work path; the new capture/adapter receipts bind
the actual resume1 command, argv, work and process identities.

The first capture had refused a one-character error in the historical selected
`07-0003` adapter-exit digest. Fresh raw-file verification and exact writer
reconstruction established the corrected pin
`d83951e8edc29c2eac4c1b6b8e5f2c3176f6c75a7e2659b008afdeade88af4b3`.
All seven other pins matched. Separate pin1 capture/owner sources preserve the
original source, transport and failure record; see the resume1 erratum.

At approximately **14:33 UTC**, the reviewed launcher refused its read-only
resource check with **3,960,205,312 bytes / 3,776.75 MiB available**, below the
unchanged **3,840 MiB** floor. This was before detached-owner or guard creation.
At **14:34:00.593198 UTC**, the owner directory, owner/exit receipts,
`07-0004` and firstboot checkpoint were absent. Available RAM was
**3,925,786,624 bytes**, with **1,621,983,232 bytes** of free swap.
The installed sources remain ready, but a later launch requires new physical
resource and ownership checks. It is not necessary to recreate the accepted
preflight merely because this launcher refused before execution.

A later guarded Android compaction check skipped its action because free swap
was **1,622,302,720 bytes**, below 20% of **8,153,968,640 bytes** total swap.
That sample had **3,878,334,464 bytes** available RAM. No compaction request or
compaction receipt was created by that check. The later cache action and owner launch are recorded in the latest checkpoint
above.

All seven preparation checkpoints and the separate partition audit remain
accepted. Firstboot attempts **07-0001, 07-0002 and 07-0003** remain preserved and
incomplete; **07-0004 had not started** at the 14:34 observation. There is no accepted
firstboot, saved-firstboot inspection or final APK. `gpu_path_complete=false`.
Guest **3 GiB / 4 CPUs**, running floor **512 MiB**, native/sync/counter
requirements and the separate saved-filesystem inspection remain unchanged.
The source-only saved-inspection successor is being prepared separately and
cannot execute until it is bound to a genuinely accepted firstboot.

## Historical source recovery: 2026-11-22

The installed pin1 owner has now been [recovered byte for byte](device-checks/recovery-20261122/recovered-owner-sources/README.md) from the user's supplied file. Its 35,614 bytes match the previously recorded SHA-256 `b7337a992b5c9c651aae1085c358a27c5d2c8b41998398afd5a4f5ba40c6e2e7`. Reversing the single documented preflight-pin byte also recovers the exact rejected-v1 source, verified against its original complete hash. Both historical sources and their provenance are now preserved in the repository; they were not executed again.

The workspace restarted without the old checkout. A partial, shallow checkout of the published checkpoint has been restored, preserving all unmaterialized paths in the Git index. The original installer/transport packages, all unpublished local evidence and the unstaged memory1 drafts still need recovery or explicit reconstruction. This source recovery does not release the next owner or change the physical result below.

## Historical physical checkpoint: 2026-11-22 13:46:34 UTC

Read the [workspace-disconnect recovery checkpoint](device-checks/recovery-20261122/workspace-disconnect/README.md) before taking action. It supersedes the historical status and next-attempt commands below. All seven preparation checkpoints and the separate partition audit remain accepted. Firstboot attempts **07-0001, 07-0002 and 07-0003** are preserved and incomplete; there is no accepted firstboot or saved inspection.

The corrected 13:02:27 preflight digest is `42a0fefd327fd8be51eebb9be6fac4def61a18f5cf8bb274af23d6c093cbe222` (21,988 bytes). The original selected transcription had a one-character error, which caused a safe launcher refusal. The separate pin1 owner then ran 07-0003 and stopped before QEMU at **3,818 MiB available versus 3,840 MiB required**, with clean outer reap and unchanged inputs. Its owner/work paths now contain preserved failure evidence and must not be reused.

One targeted Android app compaction preserved the same frozen process and showed a **62.45 MiB** system-wide available-memory increase. At the later sample, available RAM was **3,626.59 MiB**, below the unchanged firstboot floor. No app was killed, no manual thaw/cache drop/global setting change was requested, and no memory threshold was reduced.

The development executor became unavailable during final review of the fresh **memory1** transport. **No memory1 installation, new preflight or next owner launch occurred.** The next possible attempt is **07-0004**, with fresh memory1 paths, a newly observed read-only preflight, completed source/transport review and sufficient current resources. The disconnect checkpoint records exact review limits and the local files that had not been published; the source-recovery section above records what has since been recovered.

## Historical checkpoint8 status (superseded by the latest checkpoint)

This is a recovery index, not a live monitor. Recheck the phone before starting
another owner. Latest recorded activity: **2026-11-22 13:02:27 UTC**. Preparation
has completed all seven checkpoints and the separate native partition audit
passed both full HFS checks with unchanged inputs and clean native reap.
Firstboot attempts **07-0001** and **07-0002** remain preserved and incomplete:
the first stopped before QEMU at Python's missing memfd binding; the second
reached native/readiness/settle/shell-sync witnesses but failed the old
one-backend counter selector. Neither is an accepted firstboot checkpoint.

The [reviewed counter1 correction](device-checks/recovery-20261122/firstboot-counter/README.md)
is now installed in separate source directories. It requires ordered post-stop
`query-blockstats` and `query-block` replies, the unique writable root, and an
exact no-medium witness for the qualified empty `floppy0` backend if present.
Every returned failed-write/flush counter must remain exact integer zero.
Its fresh read-only preflight is **`PREFLIGHT_READY`**, accepted, exited zero
and reaped, with restored process-local Python attributes, unchanged inputs,
seven checkpoints and the new guard work directory still absent. Actual stdout
is 21,988 bytes, SHA-256
`42a0fefd327fd8be51eebb9be6fac4def61a18f5cf8bb274af23d6c093cbe222`.
The execution owner has not yet been installed or launched at this boundary.
Only a fresh **07-0003** may be accepted under this source revision.

The user requested safe RAM reclamation and confirmed the 16 GB phone.
The [earlier memory observations](device-checks/recovery-20261122/memory/README.md)
and this new preflight met the unchanged **3,840 MiB** launch floor without
reclamation. The latest available-memory reading is **4,428,693,504 bytes**
(about **4.12 GiB**). No cache drop, app trim, process termination or threshold
change was performed. No phone VM or host check remains running at this
recorded boundary. The Linux host check is separately blocked by self-read
`EPERM`.

## Recovery session on November 22

Remote `eca3cb6c9f07e5a865ba255f23fca56bdfdc5511` preserved the previous
chat's final checkpoint. The next session restored the source checkout from
that branch; the older transient host checkout and tools were absent.

The phone owner survived. Read-only snapshots showed the rootfs disk growing
and fresh native execution. At 11:10:34 UTC the original owner had accepted
`ios26-rootfs` and started partition `06-0001`. At **11:22:26 UTC**, the observer
found both helpers complete, all seven checkpoints present and the owner
cleanly exited at **11:18:02 UTC**. The top-level result now reads
`PREPARATION_CHECKPOINT`, ending at `ios26-partition`; its earlier failed
`05-0001` result has been superseded while that attempt's evidence remains.
See the [recovery observations](device-checks/recovery-20261122/README.md) for
exact scope and selected screenshot transcriptions. Full source/checkpoint
and generated-disk validation was then accepted by the separate audit
preflight at **11:30:18 UTC**, with its wrapper and auditor cleanly exited.
The [audit owner record](device-checks/recovery-20261122/audit-owner/README.md)
retains that accepted boundary and the exact reviewed source. Its separate
execution launcher ran at **11:35:34 UTC**. The first **11:36:12 UTC** sample
confirmed the new owner/auditor/QEMU identities alive. At **11:38:42 UTC**,
the same owner had cleanly completed the audit: both fsck checks passed,
input identities remained unchanged and all three processes were absent.
The [firstboot preflight](device-checks/recovery-20261122/firstboot-preflight/README.md)
then accepted the exact audited boundary at **11:47:11 UTC**. Its memory check
remained below the firstboot floor, so no boot execution was requested at that
boundary. Later [fresh memory readings](device-checks/recovery-20261122/memory/README.md)
met the floor without cache drops, app trimming or process termination.
At **12:06:51 UTC**, the reviewed detached firstboot owner launched after fresh
resource/physical checks. The first two observations found the owner and guard
live during input validation. Exact source, transport, install/launch receipts
and selected [physical observations](device-checks/recovery-20261122/firstboot-owner/README.md)
are retained for recovery. At **12:10:21 UTC**, the owner and guard were absent,
cleanly exited with status 2, and the guard reported a missing Python memfd API
before VM startup. Original bound inputs were unchanged and no firstboot
checkpoint was written. A subsequent one-page libc smoke passed; the
[compatibility record](device-checks/recovery-20261122/firstboot-memfd/README.md)
preserves exact source, raw receipt identity and selected physical evidence.

The compatibility adapter was installed at **12:19:39 UTC** and its new
read-only preflight was accepted at the **12:21:05 UTC** observation. The
original guard and four frozen runner files were unchanged. The new owner
launched at **12:24:54 UTC**, with 3,945.48 MiB available and unchanged memory
gates. At **12:29:44 UTC**, attempt 07-0002 was running with native execution;
at **12:30:46 UTC**, it had cleanly exited after the guard rejected the
post-stop backend shape. Readiness, settling, shell-sync and final native
witnesses were present, but the counter check and firstboot checkpoint were
not accepted. The adapter restored its added Python attributes and recorded
unchanged sources. The [compatibility record](device-checks/recovery-20261122/firstboot-memfd/README.md)
retains both the active observation and the later incomplete result.
The **12:34:28 UTC** read-only metadata projection identified the exact
two-backend response that the old one-row predicate rejected. Both failed-I/O
counters were integer zero in all five returned rows. Recursive node summaries
are not independent backend failure accounting, and no returned zero proves
the internal stop-flush result. The recorded `account_failed` flag controls
failed-operation timing contributions, not whether failed operations are
counted. A future corrected guard
must prove the extra backend has no attached medium and retain the unique
root, complete counter and original ownership/checkpoint requirements.

The explicit counter1 revision and its saved inspector passed **57 focused
offline tests** with unchanged tested source bytes. The original 30,606-byte
clipboard transport left an unfinished shell quotation; no installer ran.
A fresh terminal confirmed all six new source/receipt/work paths absent at
**12:54:13 UTC**. The separately reviewed bounded transport then verified all
eight chunks and the complete original installer before installing the three
new sources at **13:00:35 UTC**. The bound memfd adapter was installed at
**13:00:56 UTC**. Its read-only preflight started at **13:01:22 UTC** and was
accepted at **13:02:27 UTC**, with clean reap, restored attributes, preserved
prior failures and sufficient fresh memory. The [counter1 evidence](device-checks/recovery-20261122/firstboot-counter/README.md)
retains the exact source basis, tests, original failed transport, bounded
transfer and selected physical observations. This does not accept either old
attempt or prove a new physical boot.

The restored host work is under
`/workspace/scratch/abcabc3f01ae/host-clock-fix`; the Reims edit worktree is
`clock-worktree`, with exact reconstructed metal2vulkan in
`metal2vulkan-full`. Build tools are under
`/workspace/scratch/abcabc3f01ae/host-tooling`, with their environment in
`environment.json` and `env.sh`. The exact earlier Rust, LLVM assembler,
nextest and CMake identities have been restored. This host reconstruction does
not replace the qualified phone runtime.

The [new host-check record](host-checks/recovery-20261122/README.md) preserves
ten stopped attempts and the [ten ordered source increments](../../patches/cpu-shadow-host-checks/README.md)
through tree `4a87638743e4cb6a7e004c20e68ac8c66440d5d2`. They fix diagnostic
clock/lint issues, complete C harness coverage, and check invalid gamma,
cursor-glyph and local-task read ranges before allocating their destinations.
Run 09 passed those regressions and recorded **2,653 passing tests**, then
stopped at a Vulkan lifetime fixture whose fixed-duration busy shader did not
hold the preceding command in flight. The tenth increment replaces that
timing assumption with an explicit queue gate, retaining preceding write
overlap and all lifetime/byte checks. Run 10 passed those lifetime tests and
recorded **2,805 passing tests**, then stopped because this host returns
`EPERM` for self `process_vm_readv`, preventing the import test's intended
error path. That environment blocker is recorded without weakening the test
or production behavior. The full Linux check, runtime integration and macOS
behavior gates remain open; no host check remains running. The historical
notes below preserve the previous session's paths and observations.

## Goal and constraints

Continue the native EL0 / PowerVR route on the rooted Pixel 10 Pro XL. The user
has authorized the root-backed preparation and physical checks. Keep progress
on `Ripthulhu/asoft-ios-android`, branch `pixel10-gpu-integration`. No final APK
until the real GPU path is complete. No TCG-only fallback. The Linux and iOS
kernel portions still use TCG in the established hybrid route. Preserve all
verified predecessors and failed attempts. Never publish Apple binaries,
shaders, serialized Apple descriptors, or logs containing Apple code.

`gpu_path_complete=false`: actual iOS cold boot/UI, application-UID execution,
broader native/PAC coverage and the required complete integration checks remain
open. The experimental runtime capability changes are not merged into the
original reims integration branch.

## Completed evidence

| Checkpoint | Recorded outcome | Evidence |
|---|---|---|
| e9cc754 GPU qualification | All 17 physical cases passed, natural exit/reap, exact package and seven-check GPU probe | [core run](device-checks/core-run-e9cc754/README.md) |
| Standalone tool reconstruction | 121 files verified; current JNI/Java image decode and qemu-img checks passed | [tools and helper](device-checks/preparation-tools-1528a782/README.md) |
| Authored native Linux helper | Exact nonce/hash/16 KiB result, 8,080 native entries, 3,373 SVCs, natural exit | [tools and helper](device-checks/preparation-tools-1528a782/README.md) |
| Shared fetch/unpack/build | Matched kernel/trees, shell ramdisk and GPU bundle; 864,281 native entries, natural exit | [shared preparation](device-checks/preparation-shared-f4d64db/README.md) |
| iPhone fetch/decrypt | Authenticated SystemOS/OS outputs; 14,776,532,992 plaintext bytes, encrypted inputs retained | [iPhone inputs](device-checks/preparation-iphone-f4d64db/README.md) |
| Native rootfs retry `05-0002` and partition `06-0001` | All seven preparation checkpoints accepted; completed native VM records, clean owner exit and all recorded processes absent | [recovery observation](device-checks/recovery-20261122/README.md#preparation-completion) |
| Separate partition auditor | Prior offline/formatter checks retained; physical native audit accepted at 11:38:42 UTC; both full fsck checks passed, inputs unchanged, clean owned reap | [audit owner](device-checks/recovery-20261122/audit-owner/README.md) |
| Firstboot execution guard | Both failed attempts preserved; counter1 correction installed and its fresh preflight accepted; no accepted firstboot checkpoint yet | [counter1 recovery](device-checks/recovery-20261122/firstboot-counter/README.md), [compatibility retry](device-checks/recovery-20261122/firstboot-memfd/README.md) |
| Saved-firstboot inspector | Matching counter1 source installed; 57 combined focused guard/inspector tests passed; no physical saved-disk inspection yet | [saved-disk inspection](IOS26-SAVED-FIRSTBOOT-INSPECTION.md) |
| App-copy auditor | Counter1 prerequisite pins reviewed and included in 122 focused downstream tests; revised source integrated in repository, not yet staged on phone; no physical app audit | [downstream revision](device-checks/recovery-20261122/downstream-counter/README.md), [copy audit](IOS26-APPS-AUDIT.md) |
| Wallpaper guard and inspector | Counter1 two-query protocol/pins reviewed and included in the same 122 downstream tests; revised sources need fresh staging and physical checks | [downstream revision](device-checks/recovery-20261122/downstream-counter/README.md) |
| Final cold-boot guard | Revised prerequisite pins reviewed and included in the same downstream tests; new source needs staging and physical final boot | [downstream revision](device-checks/recovery-20261122/downstream-counter/README.md), [cold-boot guard](IOS26-COLD-BOOT-GUARD.md) |

Host Vulkan synchronization validation and phone diagnostics are separate
evidence. The phone does not have Khronos validation layers. Keep the retained
unsupported/fault counters and runtime precision notes visible; do not turn
these outcomes into zero-warning or trap-free claims.

## Exact phone locations

The connected Tango terminal is
`https://app.tangoapp.dev/device/192.168.50.196:5555/terminal` (root shell).

| Item | Absolute phone path |
|---|---|
| Transfer/owner base | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh` |
| Immutable qualified package | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/pixel-cpu-shadow-ksceynt6/cpu-shadow-qualification` |
| Seventeen-case report | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/qualification-e9cc754/qualification.json` |
| Verified tooling | `/data/local/tmp/pixel-tools-1528a782` |
| Frozen preparation sources | `/data/local/tmp/pixel-prep-runner-f4d64db` |
| Preparation work/session | `/data/local/tmp/pixel-prep-e9cc754` |
| Read-only retry status observer | `/data/local/tmp/pixel-status-retry-f4d64db.py` |
| Current separate audit sources | `/data/local/tmp/pixel-boot-checks-ebbc9c0/auditor` |
| Preserved original firstboot guard source | `/data/local/tmp/pixel-boot-checks-ebbc9c0/firstboot` |
| Current counter1 firstboot guard source | `/data/local/tmp/pixel-boot-checks-counter1/firstboot` |
| Preserved original saved-firstboot inspector sources | `/data/local/tmp/pixel-saved-checks-d4e0ac0` |
| Current counter1 saved-firstboot inspector sources | `/data/local/tmp/pixel-saved-checks-counter1` |
| Preserved pre-counter1 app-copy auditor sources | `/data/local/tmp/pixel-app-checks-0126693` |
| Preserved pre-counter1 wallpaper guard and inspector sources | `/data/local/tmp/pixel-wallpaper-checks-4d900c9` |
| Preserved pre-counter1 final cold-boot guard source | `/data/local/tmp/pixel-cold-check-fac6c40` |
| Completed audit work | `/data/local/tmp/pixel-audit-e9cc754` |
| Preserved failed firstboot guard work | `/data/local/tmp/pixel-firstboot-guard-e9cc754` |
| Preserved firstboot outer owner receipts | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-firstboot-owner-ebbc9c0` |
| Preserved memfd retry guard work | `/data/local/tmp/pixel-firstboot-guard-e9cc754-memfd1` |
| Preserved memfd retry owner receipts | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-firstboot-owner-memfd1` |
| Preserved memfd1 adapter | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-firstboot-memfd-adapter-memfd1.py` |
| Current counter1 process-local memfd adapter | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-firstboot-memfd-adapter-counter1.py` |
| Counter1 source-install receipt | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/counter1-guard-inspector-install.json` |
| Intended counter1 guard work | `/data/local/tmp/pixel-firstboot-guard-e9cc754-counter1` |
| Intended counter1 owner receipts | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-firstboot-owner-counter1` |
| Intended saved-firstboot inspection work | `/data/local/tmp/pixel-saved-audit-e9cc754` |
| Intended app-copy audit work | `/data/local/tmp/pixel-app-audit-e9cc754` |
| Intended wallpaper guard work | `/data/local/tmp/pixel-wallpaper-guard-e9cc754` |
| Intended saved-wallpaper inspection work | `/data/local/tmp/pixel-wallpaper-check-e9cc754` |
| Intended final cold-boot work | `/data/local/tmp/pixel-final-cold-e9cc754` |
| Termux Python | `/data/data/com.termux/files/usr/bin/python` |

Tooling manifest SHA256:
`a5461ecf2e41d4966f783dfca620d3d700f9aa1bc76dd5fa745ec54666e764b2`.
Preparation session digest:
`9ce5f5b8e4953ac54fddd854c5b4a606c2b9866814af6b1d520c2b590e987a6b`.

The frozen four sources are bound by the preparation session. Do not replace
them with newer checkout files. Their SHA256 identities are:

```text
c77bc990e56dcb47d651f9c054c41313a6671498a5b2494e96bb522ae868fb1a  prepare_ios26.py
89e242b0c98dd994a04cabaeadc52f8d566ff3fd33fae37e1979ab81fd32b952  prepare_ios26_stages.py
6a57ed164864eef20aeffd34b14b675a8ac597c20583c9f179414a36b4ccbdeb  cold_boot_ios26.py
6931310e1318a6397ee2d7eead966bd0fcdeaae9c10038ca2f2aa01de1a45f7e  cold_boot_dt.py
```

The local runner has a later telemetry-only elapsed-time correction; the phone
deliberately retains f4d64db. Physical VM timestamp spans are authoritative for
duration when the old last-poll `elapsed_seconds` field differs.

## Preparation owner and historical attempts

At the latest **11:22:26 UTC** recovery boundary, the preparation owner had
exited zero at 11:18:02 UTC with clean owned reap. Partition `06-0001` finished
at 11:17:42 UTC, after rootfs `05-0002` finished at 11:05:37 UTC. Seven
checkpoints are accepted through `ios26-partition`. Wrapper 27799/start 5485624,
runner 27801/start 5485639, rootfs QEMU 28210/start 5491577 and partition QEMU
26348/start 7058379 are absent. The startup details below retain those earlier
identities for provenance; recheck before starting a new owner.

The fresh disk owner selects `--through ios26-partition` and adds the supported
`--helper-seconds 21600`. It retains the original network permission, but its
remaining plan contains no network or iOS guest-boot stages. It has no
`--allow-guest-boots` and cannot select first boot. Both remaining helpers have
their own six-hour bound. The session, frozen sources and memory settings are
unchanged; neither the selected boundary nor helper deadline enters the session
digest.

Under the transfer base, the completed preparation owner directory is
`ios26-disks-retry-f4d64db`. Read its `owner.json`, `exit.json` if present,
`command.json` and `run.log`. The wrapper is
`run-ios26-disks-retry-f4d64db.py`; its separate log is
`ios26-disks-retry-wrapper-f4d64db.log`. Wrapper source SHA-256:
`6ed877eba0114375409dce5146c0e7187fca06af6ab587cddbd2aab836b9d38a`.
It started at `2026-11-22T06:43:51.411279+00:00`, wrapper PID 27799/starttime
5485624, runner PID 27801/starttime 5485639. The fresh helper launched at
`2026-11-22T06:44:50.213024+00:00`: QEMU PID 28210/start_ticks 5491577,
attempt `05-0002`. Its actual launch records 21,600 seconds, unchanged 2,048 MiB
RAM, four vCPUs, eight native stubs and read-only original inputs. The exact
[startup snapshot](device-checks/preparation-retry-f4d64db/README.md) preserves
the wrapper, owner, preflight and launch bytes. At 07:20:58 UTC all three
process identities still matched. The 07:20:50 periodic VM sample had positive
native execution and no error field, with no final witness or cleanup. The
container file was 6,824,198,144 bytes, with 6,830,845,952 allocated filesystem
bytes; neither value is guest filesystem usage or virtual capacity. Revalidate
PID and start-time identity before acting. Do not signal reused or unrelated
processes.

The reviewed observer is now staged and was run at that boundary. It only
reads bounded metadata and process identities; its zero exit is not a pass:

```sh
/data/data/com.termux/files/usr/bin/python -I -B /data/local/tmp/pixel-status-retry-f4d64db.py
```

Add `--json` for structured selected metadata. Its source SHA256 is
`899331a986db310d04af2ee076792d00c3ed64e8403f73b6e02efa897427c462`.
The [receipt and observation](device-checks/preparation-retry-f4d64db/README.md#read-only-status-after-reconnecting)
retain the exact installation record separately from the UI transcript.

The original `05-0001` rootfs attempt timed out at the configured 7,200-second
deadline after the watcher displayed 9.3 GiB of occupied guest filesystem
space (labelled "GB" by the helper). This was not an exact copied-byte count. Its owner exited 2 at
`2026-11-22T06:32:41.647600+00:00`. Native execution was witnessed; QMP stop and
quit were acknowledged, QEMU exited 0 and was reaped without forced children.
The helper did not finish naturally and no completion protocol/checkpoint was
accepted. The final `elapsed_seconds` near 7,196 is the last periodic sample,
not a different deadline. At 06:34:26 UTC the old wrapper 29240, runner 29241
and QEMU 30892 were absent; the relevant-owner scan was empty. All old owner,
exit, logs and partial disk files remain intact. Exact metadata was exported
before the retry; the [exact failed-attempt evidence](device-checks/preparation-disks-f4d64db/README.md)
retains that incomplete outcome and its final counters. Its retained launcher is
[run_disks.py](device-checks/preparation-iphone-f4d64db/run_disks.py).

The first five stages remain complete: shared-fetch, shared-unpack, shared-build,
ios26-fetch and ios26-decrypt. Retry preflight exited 0 and reported exactly
`[ios26-rootfs, ios26-partition]` remaining. Rootfs creates fresh `05-0002`,
then successful partitioning creates `06-0001`; partial `05-0001` is never
reused. The actual new `launch.json` records `deadline_seconds=21600`.
The historical 07:20:58 UTC observation had 103,987,073,024 free bytes and
2,272,305,152 bytes MemAvailable.
Last power observation at 06:33:50 UTC was AC, 75%, 24.2 C.

The top-level preparation `result.json` can still describe the last completed
boundary while a new owner is running. Use the current owner/exit record,
checkpoint inventory and latest attempt `vm-result.json` together. Inspect
only selected protocol/counter lines for exported evidence; full guest serial
logs and firmware stay on the phone.

## Next decisions

1. Recheck the completed preparation owner, all seven linked checkpoints and
   native/natural/clean helper results before launching any process. Do not run
   concurrent VM or GPU jobs. Preserve failed attempts and their evidence.
2. Require exit zero, the complete hash-linked partition checkpoint, native
   witnesses, natural helper exit and clean owned reap. Export metadata only.
3. The separate audit has completed under the [reviewed outer owner](device-checks/recovery-20261122/audit-owner/README.md).
   Recheck its accepted result and absent identities; do not repeat installation,
   preflight or execution launch. The exact auditor command below is provenance.
   Preparation remains exactly at `ios26-partition`, ready for the guard preflight.
4. Require `PARTITION_AUDIT_PASSED`, both unfiltered full HFS checks, precise
   Data-copy/tweak agreement, unchanged disk/preparation identities and clean
   native ownership. An unexplained HFS internal entry is a finding to classify,
   not permission to add a broad exemption.
5. Preserve the [failed firstboot owner](device-checks/recovery-20261122/firstboot-owner/README.md),
   its guard work and 07-0001. Do not rerun its installer, launcher or old
   preflight capture. The failure occurred before QEMU at Python's missing
   memfd binding; unchanged inputs, no checkpoint and clean owner reap were
   observed. The [real libc smoke](device-checks/recovery-20261122/firstboot-memfd/README.md)
   passed, and the explicitly bound process-local adapter/preflight/retry ran.
   Preserve its separate owner/guard work and failed 07-0002 as well. Do not
   rerun commands 04 through 07 in the
   [immutable adapter package](device-checks/recovery-20261122/firstboot-memfd/package/README.md).
   Its command 08 is a read-only observer for that exact owner. The new failure
   is the strict post-stop root-backend selector, after successful guest sync
   and native witnesses. The exact saved response has `root` plus `floppy0`;
   the selected readback found integer-zero failed-write/flush counters in all
   five returned rows. Require an explicit post-stop no-medium witness before
   allowing the additional floppy backend in a future guard version. Do not
   retroactively accept 07-0002, infer internal flush success from zero counters, reuse
   either failed disk, or relabel either result as passed. Any correction must
   retain exact source/invocation provenance, fresh preflight/work/attempt and
   every memory, identity, counter and ownership gate. The separately installed
   counter1 revision now has an accepted read-only preflight bound to the
   actual stdout identity above. Finalize its new owner against those bytes,
   recheck fresh resources and absent identities, and allow only new 07-0003.
   Do not repeat successful source-install or preflight-capture commands.
   The corrected
   [guard](IOS26-FIRSTBOOT-GUARD.md) retains
   the session settings and original owner while requiring the shell-sync
   witness and zero reported guest write/flush failures after QMP stop. The
   guard stops at firstboot. Require `GUARDED_FIRSTBOOT_COMPLETE` bound to the
   actual checkpoint; an original checkpoint alone is insufficient. The
   historical `stop_flushed` field is not proof of QMP's internal flush return.
6. Run the [saved-firstboot inspector](IOS26-SAVED-FIRSTBOOT-INSPECTION.md)
   before any subsequent Linux disk mutation. It requires the successful
   guard, full unchanged backing-chain identities, raw empty-journal checks
   and both complete read-only fsck passes. The pinned Linux fsck does not
   implement journal replay. A nonempty or unsupported journal remains a
   finding; no replay, repair or broad exemption is authorized by a pass label.
7. After the accepted saved-firstboot inspection, run the original helpers
   only through `ios26-apps`. Stage the exact [counter1 downstream revision](device-checks/recovery-20261122/downstream-counter/README.md)
   in fresh source paths with explicit receipts; the preserved old downstream
   installations have incompatible prerequisite pins. Then require the revised [app-copy auditor](IOS26-APPS-AUDIT.md)
   to return `APP_COPY_AUDIT_PASSED` before running the GPU helper. It checks
   source bytes/types/modes/owners and per-copy link relationships for new
   bundles, and exact preservation of the preceding Applications tree.
   The imported `m2-peek.sh`/`apply-apps.sh` can hide a copy error; stage
   completion alone does not prove the intended app inventory.
8. After the GPU helper, use the newly staged [counter1 wallpaper guard](IOS26-WALLPAPER-GUARD.md)
   and require `GUARDED_WALLPAPER_COMPLETE`. Then require the separate saved
   inspection to return `SAVED_WALLPAPER_INSPECTION_PASSED` before the Linux
   locale mutation. The [old staging record](device-checks/wallpaper-checks-4d900c9/README.md)
   remains historical provenance; fresh counter1 source and command receipts are required.
9. After the accepted saved-wallpaper check, complete locale and pack. At that
   exact boundary use the newly staged [counter1 final cold-boot guard](IOS26-COLD-BOOT-GUARD.md),
   which retains the independent cold owner and its original witness rules.
   It binds the coherent packed assets and full ancestry, verifies the actual
   three-GiB launch tree, and adds fresh/running memory checks. Preflight is
   the default; execution uses `--boot` and explicit `--expect-serial` literals
   chosen from actual understood iOS milestones. No marker is invented in
   this index. Missing serial/native/GPU/frame evidence cannot be replaced by
   a passing memory check. Human frame review remains required.

```sh
/data/data/com.termux/files/usr/bin/python -B \
  /data/local/tmp/pixel-boot-checks-ebbc9c0/auditor/audit_ios26_partition.py \
  --prep-work /data/local/tmp/pixel-prep-e9cc754 \
  --runner-dir /data/local/tmp/pixel-prep-runner-f4d64db \
  --work /data/local/tmp/pixel-audit-e9cc754
```

The command above is read-only preflight. Add `--execute` only after checking
its concrete result and the completed preparation owner. Both audit source
files must remain together. Their installed hashes are
`6988d94e975ebd43dd022eb3303b5c6722a05755a1b0614d780343e577065687`
(host) and
`6874b9b6b68c7fb50c3f9cf05c1b6a86a53f8fed75863c00a6ad9254b1640593`
(guest). The old `pixel-partition-auditor-40da3c3` staging remains preserved,
but it is superseded by the exact journal-aware sources above.

The original firstboot command below is historical provenance. Its work
directory now contains preserved failure evidence; do not execute it again:

```sh
/data/data/com.termux/files/usr/bin/python -B \
  /data/local/tmp/pixel-boot-checks-ebbc9c0/firstboot/guard_ios26_firstboot.py \
  --audit-work /data/local/tmp/pixel-audit-e9cc754 \
  --auditor-dir /data/local/tmp/pixel-boot-checks-ebbc9c0/auditor \
  --runner-dir /data/local/tmp/pixel-prep-runner-f4d64db \
  --work /data/local/tmp/pixel-firstboot-guard-e9cc754
```

After an accepted counter1 guarded firstboot, the matching saved inspector must
consume that successful guard's actual work directory. Do not execute it
before an accepted current guard and its own concrete read-only preflight:

```sh
/data/data/com.termux/files/usr/bin/python -B \
  /data/local/tmp/pixel-saved-checks-counter1/inspect_ios26_firstboot.py \
  --guard-work /data/local/tmp/pixel-firstboot-guard-e9cc754-counter1 \
  --work /data/local/tmp/pixel-saved-audit-e9cc754
```

Both commands default to read-only preflight. The original guard execution
requires the explicit process-local memfd compatibility path on this Python
build. The inspector's Linux helper does not require that adapter. Add
`--execute` only after the preceding actual gate and concrete preflight pass.
The [exact staging receipts](device-checks/boot-checks-ebbc9c0/README.md)
bind all five installed sources and both transport ZIPs. They establish
transfer identity, not a physical audit or boot outcome.

The following app-audit command preserves the earlier staged invocation. Its
old prerequisite pins cannot consume counter1 results; do not execute it.
After the later helpers complete exactly through `ios26-apps`, use a freshly
staged, receipt-bound counter1 auditor as described above:

```sh
/data/data/com.termux/files/usr/bin/python -B \
  /data/local/tmp/pixel-app-checks-0126693/audit_ios26_apps.py \
  --inspection-work /data/local/tmp/pixel-saved-audit-e9cc754 \
  --work /data/local/tmp/pixel-app-audit-e9cc754
```

The historical command is also preflight by default. The [exact app staging receipt](device-checks/app-checks-0126693/README.md)
binds both installed sources and confirms the nine earlier source hashes
still matched. The physical application-copy audit remains pending.

Session settings remain Europe/Amsterdam, 24-hour clock, empty region, 4 CPUs,
2,048 MiB Linux helper and 3 GiB iOS guest. Fresh memory gates are 2,816 MiB for
the helper and 3,840 MiB for iOS. Running low-memory stop is 512 MiB. Do not
weaken these gates. The user's later request authorizes safe, measured RAM
reclamation if needed; it does not authorize indiscriminate app termination,
loss of app state, checkpoint deletion or protection/policy changes. Fresh
readings already met the floor without any reclamation at 11:54 and 11:58 UTC,
and again at the 13:02:27 UTC counter1 preflight boundary.

Qualified QEMU allocates XNU DRAM from the copied tree's `/chosen/dram-size`;
the frozen preparation verifies the exact `expected_tree(original, 3, 3)`
bytes. The [source-grounded RAM record](host-checks/wallpaper-guards.json)
identifies the pinned machine allocation path and unchanged thresholds.

## Publication and local continuity

The recovered checkout for this session is
`/workspace/scratch/abcabc3f01ae/asoft-ios-android`. Host source and tool paths
are recorded in the recovery section above. The first verified recovery
publication maps local `e698660c12e7d4f31263fdbc3632f17ac6a1a49e` to remote
`cfa9d5b1c92887bfa62fc508bf447d62e6b87612`, with identical tree
`9fc3e3f90b64b098692fb8cfc8877e8a703bc503`. The third verified publication
(before the new complete-preparation/audit records) maps local
`1d0476f744d6aca5d1071e133c59ae4864dbe869` to remote
`8d70355c161d4c07e4b8993676b92735eb6c7fe1`, identical tree
`213652457ab5d85032cb7c43f28dd0c14a2a108a`. The next audit/host checkpoint
maps local `96017821ca5d28a6367d90b5ee9fc3864f6ec733` to remote
`2fa8c3c2c1fec14e2f24b41cd841b03adb212898`, identical tree
`d41f1e8463fc4e51718b8e25467a0ab990c1fd7b`. Read the current branch head before
publishing further work and use its expected-SHA lease; never force-push.

The later fresh-memory checkpoint maps local
`7410a282e4ee226f83404426aa69be6dc0e66be9` to remote
`fdde0a54764362ac2553b036a39fc370ce04e948`, identical tree
`71f29f1ba4251c6743030ca5a8206d2ee74bc34a`. It records the user's safe RAM
request and the naturally sufficient headroom before firstboot launch.

The preserved-firstboot checkpoint maps local
`ac0327bc46f71098c9d7ef94eb6769f610f54f82` to remote
`34802e9a7fb5a2e6309547087d4008710a1debbc`, identical tree
`25bcdba0201ab17118827e9bf2214979f09681a3`. It records both incomplete firstboot
attempts, the passed memfd smoke and adapter preflight, native readiness/sync
on 07-0002, its rejected two-backend statistics, and exact retained receipt
identities. It does not accept a firstboot checkpoint.

### Previous session history (superseded local paths)

The following paragraphs preserve earlier provenance. Their transient paths
were absent when this session began; use the restored locations above for
current work. The historical test outcomes remain evidence of those runs.

GitHub connector commits have different commit IDs from local commits but
identical verified trees. The last source checkpoint before this note maps
local `0df632bb10a9375315a7c8dcda9d037c9b1dd907` to remote
`a2a69e37d5ac72e2d103ec2d9e51cfa939ac5b77`, tree
`671c64ce5b7025ff797c4ff53d62233c023b9454`. Use a fresh head/expected-SHA lease;
never force-push. Later history may supersede this pair.

The previous session's local checkout was
`/workspace/scratch/3ef77e3b5dde/asoft-ios-android`. Publication receipts and
verified exports are next door under `native-runtime-build`; those transient
paths supplement the committed evidence. The independent auditor authoring
worktree is `/home/agent/.cache/asoft-pixel-cold-boot`. The journal classifier
was authored in `/home/agent/.cache/asoft-pixel-hfs-journal-audit`, commit
`e9c6c2dad78645dc2160dc5168dff3391273ffbf`, integrated as `ebbc9c0`.
The saved-firstboot inspector author commit `28f0f5bc` became `d4e0ac0`.
The inactive `target-producer-adoption/debug/incremental` compiler cache was
removed after checking its generated-file shapes, absent build processes and
retained qualified runtime/QEMU hashes. This reclaimed about 7.015 GiB; the
workspace then had about 7.513 GiB free. The exact path and observations are in
[the cleanup receipt](host-checks/workspace-cache-cleanup.json). Parent target
outputs, every source/worktree, all packages and phone evidence were retained.

The [host caches and retained archives](host-checks/resource-preparation-e9cc754/README.md)
have since been copied, completely
verified and moved from tmpfs to disk behind their unchanged logical paths.
The host graph was restored with full tar comparison and a 2,037-entry
inventory. The tiny prior host target and the initial interrupted relocation
receipt remain intact. Final readiness at 06:40:18 UTC was 4.324 GiB available
RAM and 4.042 GiB free disk, with no swap. This is observed headroom, not a
measured peak bound for a full check.

The exact pinned [header check](host-checks/header-e9cc754/README.md) passed at
06:42:44 UTC in 1.268 seconds; the committed header and Cargo override hashes
were unchanged. Its raw evidence is under
`native-runtime-build/host-header-check-e9cc754`.

The first actual full check stopped at a rustfmt difference in
`crates/reims-vgpu-c/tests/cpu_shadow_core.rs`, after manifest and header checks
passed. [Exact evidence and the formatting follow-up](host-checks/xtask-e9cc754-rustfmt-stop/README.md)
retain the original partial result and clean owned cleanup. The test-only
formatting fix is author `a42a1e68dbf255103b9589162014ff2fbee0784a`, integrated
in the root capability worktree as `bda933b9592262dd85d8723e5c47cfe6886b6c25`,
tree `c603324e4e499668f5ae4133cfe14b39f4491275`. Production source objects,
the physical e9 package and existing qualification exports remain unchanged.
The root capability worktree is
`/home/agent/.cache/reims-pixel-cpu-shadow-capabilities`; its only uncommitted
change is the established Cargo dependency-path override.

The next full check at `bda933b` passed manifest, header and formatting, then
stopped in all-feature Clippy because the diagnostic probe needs an explicit
`RVG_CPU_SHADOW_LLVM_AS`. Its retained result is
`native-runtime-build/host-xtask-check-bda933b/result.json`; source identities
were unchanged and owned cleanup completed. The next Clippy command had
already started before the sampled failure detection; no later pass is
claimed. The required assembler was installed at
`/workspace/scratch/95f3cf369f81/tooling/android-ndk-r29/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-as`.
This is the exact path in the successful physical package's runtime-build
metadata; the executable reports LLVM 21.0.0 and has SHA-256
`3c9a80d96a7c71624c0ce7cc2c36ef71032a8fb2e772dd0fde26ddda568b80cc`.
The [third check](host-checks/xtask-bda933b-clippy-clock-stop/README.md) used that
verified assembler, starting at 07:14:14 UTC. It passed manifest/header/fmt and
stopped at 07:15:12 UTC when all-feature Clippy rejected five direct
`Instant::now` calls in `cpu_shadow_probe.rs`. Owned cleanup completed without
SIGKILL or remaining processes; all source, prerequisite and assembler
identities stayed unchanged. This is another `INCOMPLETE` result, not a full
check pass. Its exact raw log and owner evidence are preserved. At that historical boundary, a source-only
correction to use the existing awake-time clock service was under review and
no next check had been launched. The recovery section above supersedes this
status. Complete integration and
macOS behavior-suite gates remain open; partial checks are not a merge pass.
