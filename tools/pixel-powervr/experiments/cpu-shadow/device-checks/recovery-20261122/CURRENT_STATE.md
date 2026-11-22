# Recovery checkpoint — 2026-11-22

## Start here

**The read-only Apple journal reference run completed on the Pixel.** Apple's
pinned reader matched 49 callback records across all six active lists and
318,976 payload bytes. It found zero further callbacks after the recorded end.
Three synthetic fixtures verified the reader's handling of empty, consecutive,
and stale lists beyond the boundary. The retained extract and diagnostic
receipt retained their pinned hashes. Read [the reference run](apple-journal-reference/README.md).
Data journal replay and filesystem acceptance are still pending.

**The separate Data journal structure diagnostic completed once at 2026-11-22 21:35:42.308919 UTC.** Six transaction-start lists, 49 live payload checksums and target ranges, and all 613,888 active bytes passed the supported structural checks. Four fixed native reads completed with clean unforced child reaping and unchanged disk identities, metadata and tooling. Actual-result-bound readers reverified the retained extracts and reproduced the analysis with the pinned pure parser. Read [the completed diagnostic result](resume5-saved-inspection/data-journal-diagnostic/RESULT.md) and [its current bindings](resume5-saved-inspection/data-journal-diagnostic/source-status-current.json). **Do not relaunch.** The actual result is 13,026 bytes / `6d1829c3a1a4982e4cdcf11a6854fb862f93a12d5025a783331d4a578de28efc`.

No filesystem consistency or replay-safety conclusion follows from that structural check. No replay, mount, repair, fsck or guest VM ran in the diagnostic, and it did not recompute whole-image hashes. A future recovery still requires a separately reviewed fresh copy-on-write descendant and a new accepted inspection. The current saved image and all completed attempts remain preserved.

**The resume5 inspection completed and was not accepted.** Its owner launched at **2026-11-22 20:55:38.023625 UTC** after a transient memory refusal before any execution artifact was created. A read-only observation at **20:55:19.691688 UTC** found 3,491,127,296 bytes MemAvailable, all seven execution paths absent and the same live observer within its readiness deadline. Memory recovered without a compaction, cache-reclaim, process-termination, thaw or policy action during this resume5 work.

The inspection finished at **20:58:05.315390 UTC** with status `INCOMPLETE`; owner and inspector exited 2. The native helper completed normally with native initialization, native execution and final-SVC witnesses, exit zero, no fatal markers and clean unforced cleanup. Both final observations at **20:58:46.670734 UTC** and **21:00:02.936994 UTC** show wrapper **3218 / 10596300**, inspector **3219 / 10596334** and QEMU **4784 / 10606734** absent. The original screenshot filenames incorrectly say `wrapper-present`; the additive interpretation correction preserves those files and records the actual absent state. Inputs and all 19 resume1, 16 resume2/diagnostic and 11 resume4/JIB preservation pins remain unchanged. **Do not relaunch this owner, inspector or observer.**

The actual failure projection at **21:11:04.460470 UTC** proves that the new strict iOSRoot raw-journal classification passed. **Data failed `nonempty_journal`: start 512, end 614400, journal size 8,388,608 bytes, matching stored/computed header checksum 195,764,962.** Neither forced read-only filesystem check ran, and neither diagnostic log exists. No mount, replay or repair occurred. The actual host result is 7,269 bytes / `08ab06ea5b0e1d46a168935df1dbaabeda0daa7ab569b1e001f61e17d7cfc828`. Read [the complete resume5 result](resume5-saved-inspection/RESULT.md) and [the nine independently verified receipt bindings](resume5-saved-inspection/physical-observations/receipt-pins-selected.json).

The failed inspection outcome is published at `2630efc33bebd65a0a61eb9166da4eb0ecca2483`; its tree and parent were independently verified after guarded publication. The [bounded read-only Data journal diagnostic](resume5-saved-inspection/data-journal-diagnostic/README.md) was prepared and published at `caf8e1757ac75a272a5577ae578d7a9918c7c560`, then installed and executed exactly once as recorded above. Its actual result supersedes that preparation checkpoint. The nonempty-journal refusal remains unchanged; no replay or recovery has been implemented or run.

The observer **31097 / 10563710** also finished and is absent. Its actual 3,841-byte READY receipt is `7e22ccf73c349f9c396a54cba434ec98a93fef0a44028a0856f3ebfd39be5f51`; the launcher checked its fresh heartbeat and exact identity before the one successful spawn. The final observer exited zero, with no summary errors, unresolved receipt-publication gaps or remaining recorded identities. Its 2,727 samples include zero reported sampling gaps and three read gaps; the maximum discovery scan interval was 326,163.110562 ms, so continuous descendant discovery is not established.

## Accepted preflight and installed sources

**The revised resume5 inspector, owner and process observer are installed, and the fresh preflight passed.** The actual preflight was observed at **2026-11-22 20:44:38.734136 UTC**: 9,069 bytes, SHA-256 `4630b5dc921d3bee52d4805cc829e3624144b763d27b53937443e43c69db44f6`. Both preflight exit codes were zero, reaping was clean and unforced, recorded identities were absent, inputs were unchanged and the new inspection work directory was unused at that preflight. The inspection subsequently ran and finished as recorded above; that work path is no longer unused. See [the selected physical preflight](resume5-saved-inspection/physical-observations/preflight-selected.json) and its [terminal evidence](resume5-saved-inspection/physical-observations/preflight-accepted.jpg).

The separate execution and observer bindings were finalized and independently reviewed, and their physical launch and completed outcome are recorded above. The preflight is finished and must not be relaunched. No resume5 filesystem acceptance is claimed.

**The preceding resume4 saved-filesystem inspection has finished and was not accepted.** Its native helper and cleanup completed normally. Its refusal was **`root_baseline_jib_changed` on iOSRoot**, before filesystem checks.

Read [the complete result](resume4-saved-inspection/RESULT.md), [current source/status bindings](resume4-saved-inspection/source-status-current.json), and the [prepared JIB diagnostic package](resume4-saved-inspection/jib-diagnostic/README.md).

## Historical root JIB diagnostic checkpoint — completed before resume5

The reviewed diagnostic was installed and completed on the phone. All sixteen bounded native image-tool reads completed cleanly. The two 4,096-byte root JIBs differ only at byte 3: the baseline flags value `0x5` became `0x1` in the saved image. Journal locations and sizes are unchanged. The actual result is 14,246 bytes, SHA-256 `5d39c9a0fb16c794577abaf4ab7155ee5f352d46cb7027e03b571055f10d5061`; its receipt and result-bound readers were independently reviewed. See [the complete JIB diagnostic result](resume4-saved-inspection/jib-diagnostic/RESULT.md).

This was consistent with the documented clearing of the journal NeedInit bit, but that diagnostic did not evaluate the journal header or perform fsck. Resume4 remains rejected. The root-only classification was subsequently implemented, tested, installed and exercised by resume5 as recorded above. Its raw root gate now passes; the Data journal is the remaining raw-gate refusal.

The phone browser connection was restored for these observations. The prior completed firstboot, resume4 inspection and JIB diagnostic must not be relaunched.

## Reviewed resume5 preparation — subsequently executed

The [strict root initialization revision](resume5-inspector-revision/README.md) passed 60 focused tests and an independent rerun. Its host source is 37,444 bytes / `30eaaffc42aa73bf95488f3ca504d7c56344fbada0aaed746904ed1f4f78fd3e`; its guest source is 20,929 bytes / `96c559bac19a3c36a4e26c2cf57b75cbafdfd5879de6e4fceb582b2c07a9b51a`.

The fresh resume5 owner/source-only packet and separate preflight are independently released. Its [staging order](resume5-saved-inspection/staging-order.json) and [transport release](resume5-saved-inspection/independent-source-staging-review.json) are preserved. All sources were subsequently installed through their exact reviewed commands, with matching byte counts and hashes. The [independent installation review](resume5-saved-inspection/physical-observations/independent-source-installation-review.json) verifies both inspector files, the owner and its preflight launcher. The [fresh observer package](resume5-process-observer/procstat1/README.md) also has its own source/transport release and [actual installation evidence](resume5-process-observer/procstat1/physical-observations/source-installation.jpg). Observer READY and inspection execution are recorded above; accepted completion remains a later gate.

## Preserve this state

- The guarded first-boot success remains preserved; do not replay that boot.
- Resume4 owner, inspector, QEMU and observer are finished. Do not replay their launch commands.
- Resume5 inspection, preflight, observer and Data journal diagnostic are finished. Do not replay their launch commands.
- Keep the native EL0 plus kernel TCG design; there is no TCG-only fallback.
- Keep the filesystem, native, cleanup, memory/storage and preservation gates.
- The GPU path is incomplete and the APK gate remains closed.
- Keep prior attempts, the supplied `owner.json` and `exit.json`, all receipts, installed sources and selected evidence.
- Raw Apple images, raw headers/JIB payloads, raw guest logs and private file inventories remain off the repository.

## Actual phone paths

| Item | Path |
| --- | --- |
| Completed Data diagnostic | /data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-data-journal-diagnostic-resume5 |
| Installed Data diagnostic host | /data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-data-journal-diagnostic-resume5.py |
| Installed pure Data parser | /data/local/tmp/pixel-gpu-transfer-sxtv33sh/parse-ios26-data-journal-resume5.py |
| Current resume5 inspector | /data/local/tmp/pixel-saved-checks-resume5 |
| Current resume5 owner source | /data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-saved-inspection-resume5.py |
| Completed resume5 preflight owner | /data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume5-owner |
| Completed resume5 inspection work | /data/local/tmp/pixel-saved-audit-e9cc754-resume5 |
| Completed resume5 observer output | /data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume5-observer-procstat1 |
| Completed owner | /data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume4-owner |
| Completed inspection | /data/local/tmp/pixel-saved-audit-e9cc754-resume4 |
| Completed observer | /data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume4-observer-procstat1 |
| Reused installed inspector | /data/local/tmp/pixel-saved-checks-resume3 |
| Installed owner source | /data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-saved-inspection-resume4.py |

The recorded identities were wrapper 20063/9342623, inspector 20064/9342659, QEMU 21484/9363754 and observer 18179/9323114. All were absent in the final bounded receipt reads.

## Development recovery

The executor disconnected after the live checkpoint `77ec7b95012380659196358a578aad301f8bf8c1`. The browser survived, so the actual final failure and all nine metadata receipt pins were recovered. This checkpoint is published directly through GitHub.

The executor became available again with an empty scratch workspace. The prior checkout was absent, so a fresh clone restored the clean published branch at `54f0fa973f4476fc977585557f7acf61bdad4f17`; no old reset or alignment attempt was replayed. See [the restoration record](workspace-restoration-for-jib.json). The previous local commit `0ededd092cf32d697464abc3210d082c2503b284` belonged to the lost checkout and corresponded to the live checkpoint's tree.

Continue from the actual completed resume5 result and Data journal diagnostic at the top of this file. The root raw journal proof passes and the supported Data record structure is verified, while Data replay and overall filesystem health remain unaccepted. Preserve the existing native, filesystem, memory, cleanup and application gates.
