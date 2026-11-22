# Continue the native Pixel iOS26 work

## Source recovery: 2026-11-22

The installed pin1 owner has now been [recovered byte for byte](device-checks/recovery-20261122/recovered-owner-sources/README.md) from the user's supplied file. Its 35,614 bytes match the previously recorded SHA-256 `b7337a992b5c9c651aae1085c358a27c5d2c8b41998398afd5a4f5ba40c6e2e7`. Reversing the single documented preflight-pin byte also recovers the exact rejected-v1 source, verified against its original complete hash. Both historical sources and their provenance are now preserved in the repository; they were not executed again.

The workspace restarted without the old checkout. A partial, shallow checkout of the published checkpoint has been restored, preserving all unmaterialized paths in the Git index. The original installer/transport packages, all unpublished local evidence and the unstaged memory1 drafts still need recovery or explicit reconstruction. This source recovery does not release the next owner or change the physical result below.

## Latest recorded physical checkpoint: 2026-11-22 13:46:34 UTC

Read the [workspace-disconnect recovery checkpoint](device-checks/recovery-20261122/workspace-disconnect/README.md) before taking action. It supersedes the historical status and next-attempt commands below. All seven preparation checkpoints and the separate partition audit remain accepted. Firstboot attempts **07-0001, 07-0002 and 07-0003** are preserved and incomplete; there is no accepted firstboot or saved inspection.

The corrected 13:02:27 preflight digest is `42a0fefd327fd8be51eebb9be6fac4def61a18f5cf8bb274af23d6c093cbe222` (21,988 bytes). The original selected transcription had a one-character error, which caused a safe launcher refusal. The separate pin1 owner then ran 07-0003 and stopped before QEMU at **3,818 MiB available versus 3,840 MiB required**, with clean outer reap and unchanged inputs. Its owner/work paths now contain preserved failure evidence and must not be reused.

One targeted Android app compaction preserved the same frozen process and showed a **62.45 MiB** system-wide available-memory increase. At the later sample, available RAM was **3,626.59 MiB**, below the unchanged firstboot floor. No app was killed, no manual thaw/cache drop/global setting change was requested, and no memory threshold was reduced.

The development executor became unavailable during final review of the fresh **memory1** transport. **No memory1 installation, new preflight or next owner launch occurred.** The next possible attempt is **07-0004**, with fresh memory1 paths, a newly observed read-only preflight, completed source/transport review and sufficient current resources. The disconnect checkpoint records exact review limits and the local files that had not been published; the source-recovery section above records what has since been recovered.

## Historical checkpoint8 status (superseded by the note above)

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
