# Reconstructed resume1 firstboot retry

This package continues from `d5453936b8c41c6f75025ba11630cfa2c9781311`. It is a new reconstruction from published counter1 sources, not a byte-for-byte recovery of the lost memory1 draft. Its accepted firstboot attempt is `07-0004`; all earlier failures remain preserved.

## Latest physical state: firstboot accepted and cleanly reaped

At **14:45:21.641036 UTC**, the status observer found the outer owner finished
at **14:45:16.838924 UTC** with exit and owner-exit zero, accepted true, guard
started/reaped true, forced guard false, no cleanup errors and no wrapper
error. The exact owner **3271 / 8341942**, guard **3279 / 8341984** and QEMU
**5039 / 8355681** identities were all absent.

The guard returned `GUARDED_FIRSTBOOT_COMPLETE`, accepted its checkpoint and
reported unchanged bound inputs. The VM result was `VM_OBSERVATION_COMPLETE`,
with readiness, settling, shell sync, native initialization, native execution
and final native SVC witnesses true. QEMU exited zero with stop/quit
acknowledged, no forced QEMU or descendants and no cleanup errors.

The accepted `ios26-firstboot.json` is **803 bytes**, SHA-256
`0c3418d053477d73d210eb8a22dd28e49cff61ff5140f77b6c97d4c96c8c079e`,
and binds `07-0004` with `STAGE_COMPLETE`. The nine actual success-file
bindings were observed at **14:46:27.726786 UTC**, printed as both hex and all
32 digest bytes, and independently checked against the screenshot. They are
recorded in `physical-observations/success-bindings-144627.json`; this is an
explicit selected screen transcription, not a raw receipt export.

A pinned read-only projection at **14:49:03.163081 UTC** confirmed
`COUNTERS_CHECKED`, stop acknowledged, both root and empty `floppy0` backends,
five returned statistics nodes with zero failed writes and flushes, and
`GUARDED_SUPERVISION_PASSED` with shell sync. Recursive statistics nodes are
not additional devices. The guard does not observe the internal stop-flush
return; saved journal/filesystem verification remains mandatory.

`gpu_execution=false` and `gpu_path_complete=false`. Continue with the
separately bound `../resume1-saved-inspection/` package. Do not replay this
firstboot, reuse its paths or mutate later preparation disks before the saved
inspection passes and its owner exits cleanly. No final APK is claimed.

## Historical physical state: firstboot running at 14:42 UTC

At **14:42:41.306331 UTC**, firstboot attempt **`07-0004`** was present and
QEMU **PID 5039 / start 8355681** was alive. The same owner **PID 3271 / start
8341942** and guard **PID 3279 / start 8341984** were still alive. No owner exit
receipt or firstboot checkpoint was present.

The active VM receipt had `status=INCOMPLETE`, stage `ios26-firstboot` and
`error=null`. The `native_initialization` witness was true, while
`native_execution`, `native_svc_final` and `gpu_execution` remained false at this
early observation. This is neither accepted firstboot completion nor a final
failed-attempt result. Continue read-only observation; no second owner may be
launched against these now-used paths.

MemAvailable was **2,869,805,056 bytes** and free swap **1,628,155,904 bytes**.
The post-allocation running memory floor remains **512 MiB**; the **3,840 MiB**
threshold still governs fresh launch. At the preceding **14:41:16.411161 UTC**
sample, owner/guard and the 20,936-byte guard-session file were present, while
`07-0004` was still absent.

At **14:39:54.441785 UTC**, the reviewed launcher returned
`FIRSTBOOT_OWNER_LAUNCHED`. The detached wrapper is **PID 3271 / start 8341942**,
with session/process group **3271**; the launcher was **PID 3269 / start
8341868**. Fresh prerequisites observed **4,073,943,040 bytes / 3,885.21 MiB**
available RAM and **72,982,781,952 bytes** free storage, above the unchanged
**3,840 MiB** and **4,500,000,000-byte** requirements.

The recorded source pins are the finalized owner
`862af55267f7ecd1273faf8f161e4065161f1bf49a5df6614cfb2571fc95d473`, adapter
`ede70023bc1e05b08730b48fab1016c3e665c0e83469509e5b8b74c6f2364ec7`, and accepted
preflight `42a0fefd327fd8be51eebb9be6fac4def61a18f5cf8bb274af23d6c093cbe222`.
This launch record proves the detached owner started. The later status sample
above adds guard/QEMU liveness and `07-0004` creation; **firstboot completion
remains unobserved**. Read current state
with `package/status-owner.command.txt`. Do not repeat the launcher until its
recorded process and receipts have been resolved.

At **14:39:24.831751 UTC**, a preceding reviewed one-time cache request completed:
`sync` followed by `drop_caches=3`. MemAvailable changed from **3,848,491,008** to
**4,000,583,680 bytes**, an observed **152,092,672-byte / 145.046875 MiB** increase.
The original input stat identities and OOM-kill counter remained unchanged.
No process kill or manual thaw was requested, and no persistent policy change
was requested.
The post-action sample was still below the launch floor; the later launcher
used a separate fresh sample. The action's exclusive receipt must be retained.

The new guard/attempt outcome remains pending at this authored boundary.
`gpu_path_complete=false`; no accepted firstboot, saved inspection or final APK
is claimed. Existing failed attempts remain historical evidence.

## Earlier physical state: installed, launcher refused before execution

The finalized owner and launcher were installed through all seven reviewed
owner-transfer commands, with complete source hash verification. At
approximately **14:33 UTC**, `package/launch-owner.command.txt` returned
`FIRSTBOOT_LAUNCH_REFUSED_OR_INCOMPLETE` because its read-only resource check
observed **3,960,205,312 bytes / 3,776.75 MiB MemAvailable**, below the unchanged
**3,840 MiB** requirement. The failure occurred in prerequisites before the
launcher reserved a launch receipt or started the detached owner.

The **14:34:00.593198 UTC** status observation found the owner directory,
owner receipt, exit receipt and `07-0004` absent, with no firstboot checkpoint.
It reported **3,925,786,624 bytes** available RAM and **1,621,983,232 bytes** free
swap. No new owner, guard or QEMU was started by the refused launch. The
installed source and accepted preflight remain preserved; a later launch must
freshly satisfy the same ownership, source and resource requirements.

A subsequent guarded Android compaction check observed free swap of
**1,622,302,720 bytes**, below 20% of **8,153,968,640 bytes** total swap, and
available RAM of **3,878,334,464 bytes**. It skipped the action before requesting
compaction or creating its action receipt. The subsequent cache operation and owner launch are recorded in the latest
section above.

At that 14:34 observation, firstboot remained incomplete with only the three
preserved earlier attempts: `07-0004` was absent, no firstboot checkpoint existed,
and `gpu_path_complete=false`. These selected prelaunch observations supplement
the later owner launch and the source/preflight evidence below.

## Physical pin correction before preflight

The first installed capture refused at the historical `07-0003` adapter-exit pin before creating capture/adapter receipts or starting a child. A fresh raw-file read matched all seven other pins. The adapter-exit file was 2,055 bytes, with SHA-256 `d83951e8edc29c2eac4c1b6b8e5f2c3176f6c75a7e2659b008afdeade88af4b3`; the historical selected transcription used `0` instead of `b` at digest character 46. All 32 observed digest bytes were decoded independently. Reconstructing the raw exit writer output from its already-pinned startup and observed exit fields matched the complete current file byte-for-byte.

`adapter-exit-pin-erratum.json` preserves the exact observation. The original source, transport, selected recovery record and refusal remain intact. New `capture_resume1_preflight_pin1.py` and `run_firstboot_owner_UNRELEASED_pin1.py` each differ by exactly that one source byte. The fresh capture source target is `capture-ios26-firstboot-resume1-pin1.py`. At correction time, the same capture prefix remained unused; its installer required all capture and adapter-phase receipts and new guard work to be absent.

`package/install-capture-pin1.command.txt` is a 2,102-byte bounded command. It verifies the complete original installed capture, derives and verifies the corrected source, then creates a separate source and receipt exclusively. It starts no preflight. `package/run-readonly-preflight-pin1.command.txt` runs the corrected read-only capture. Independent review accepted this correction. Two offline byte/transport tests passed; three local installer execution tests were skipped because the development container is not root. No physical preflight result is claimed by this correction.

## Accepted preflight and reviewed execution package

The corrected read-only capture physically passed at the 14:28:05 UTC observation, with `PREFLIGHT_READY`, exit zero, clean reap, restored process-local Python attributes, unchanged sources/inputs, seven checkpoints and absent new guard work. Its stdout is 21,988 bytes, SHA-256 `42a0fefd327fd8be51eebb9be6fac4def61a18f5cf8bb274af23d6c093cbe222`. All 32 printed decimal digest bytes independently matched that hash. See `preflight-observation-142805.json` for the selected observation.

The guard stdout happens to match the older counter1 preflight because it does not include the external guard-work path. The new capture and adapter receipts bind the actual resume1 command, guard argv, work path and process identities. The old capture was not substituted. Available memory was 4,123,975,680 bytes at the after sample; execution still requires fresh resource checks.

`package/run_firstboot_owner.py` now binds that physically observed output and can accept only `07-0004`. Its finalized source, detached launcher and bounded owner transfer passed independent review. The blocked owner drafts remain preserved. Staging and launch are separate: `package/owner-transfer/` contains seven commands of at most 5,098 bytes and only installs the owner and launcher. `package/launch-owner.command.txt` verifies the exact launcher before invoking its existing ownership, source, preflight and resource prerequisites.

The subsequent launcher invocation and pre-execution memory refusal are recorded above. Five finalization/owner-transfer tests passed; they verify the only two finalization fields, exact source pins, full bundle reconstruction and all bounded commands.

The adapter preserves the complete counter1 memfd implementation; its only three changes are the adapter source path, guard-work path and adapter-receipt prefix. The unchanged counter1 guard remains at `/data/local/tmp/pixel-boot-checks-counter1/firstboot/guard_ios26_firstboot.py`, SHA-256 `ea40638312d6ac41607806ecb03c148fbd0677df6ab01480e13fd40536869674`.

The capture and owner preserve the prior attempt 1/2 validation bodies unchanged. A new validator binds all eight published raw-file pins for the pre-QEMU `07-0003` memory refusal; checks its original launcher and adapter source hashes, invocation, process identities and absent processes; and retains the failed attempt's no-launch/no-success boundary. It does not interpret missing cleanup fields as a successful QEMU exit. Historical attempts remain incomplete.

The capture requires exactly the three preserved firstboot attempts and an absent firstboot checkpoint. It prints the new stdout digest both as grouped hexadecimal and all 32 decimal bytes. The finalized owner binds that actual captured output and may accept only the single new attempt `07-0004`.

## Paths

| Purpose | Phone path |
|---|---|
| Adapter | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-firstboot-memfd-adapter-resume1.py` |
| Preserved original capture source | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/capture-ios26-firstboot-resume1.py` |
| Accepted corrected capture source | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/capture-ios26-firstboot-resume1-pin1.py` |
| Capture prefix | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-firstboot-guard-preflight-resume1` |
| Fresh guard work | `/data/local/tmp/pixel-firstboot-guard-e9cc754-resume1` |
| Execution owner directory | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-firstboot-owner-resume1` |

The existing 3 GiB guest, four CPUs, 3,840 MiB launch floor, 512 MiB running floor, native/sync witnesses, ordered counter queries and separate saved-filesystem inspection requirement are unchanged.

## Bounded staging

`package/preflight-transfer/` contains seven ordered commands: begin, five chunks and assemble/install. Every command is at most 5,090 bytes. The manifest binds each chunk, the complete encoded payload, decoded bundle and both source files. All transfer files, source files and receipts use exclusive creation. Assembly installs only the adapter and read-only capture; it never starts either. Interrupted or existing paths must be preserved.

The original `package/run-readonly-preflight.command.txt` invocation is preserved with its pin refusal. The separate corrected invocation, `package/run-readonly-preflight-pin1.command.txt`, produced the accepted preflight. Both use isolated Python with bytecode writing disabled and no `--execute` argument. The accepted capture receipts now exist and must not be replayed or overwritten.

## Offline validation

`python -B test_resume1_package.py` passed 15 tests. These cover exact predecessor preservation, blocked owner/default preflight mode, all eight recovery pins, changed-receipt refusal, live historical process refusal, PID reuse, old-attempt launch/success refusal, rechecking preserved failures after a future success, and exact reconstruction of every bounded command and the two-file bundle.

Independent review separately reconstructed the preflight commands and bundle, checked all pin values and reviewed the source deltas. The subsequent one-byte pin correction and finalized owner/launcher/transport also passed independent review. See the independent review receipts, `package/source-manifest.json`, the explicit pin erratum and `package/owner-finalization.json` for the successive identities and release boundaries.
