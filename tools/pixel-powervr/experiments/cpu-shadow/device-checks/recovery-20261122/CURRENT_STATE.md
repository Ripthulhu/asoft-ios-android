# Recovery checkpoint — 2026-11-22

## Start here

**The resume4 saved-filesystem inspection has finished and was not accepted.** Its native helper and cleanup completed normally. The remaining refusal is **`root_baseline_jib_changed` on iOSRoot**, before filesystem checks.

Read [the complete result](resume4-saved-inspection/RESULT.md), [current source/status bindings](resume4-saved-inspection/source-status-current.json), and [the next JIB diagnostic specification](resume4-saved-inspection/NEXT_JIB_DIAGNOSTIC.md).

## Preserve this state

- The guarded first-boot success remains preserved; do not replay that boot.
- Resume4 owner, inspector, QEMU and observer are finished. Do not replay their launch commands.
- Keep the native EL0 plus kernel TCG design; there is no TCG-only fallback.
- Keep the filesystem, native, cleanup, memory/storage and preservation gates.
- The GPU path is incomplete and the APK gate remains closed.
- Keep prior attempts, the supplied `owner.json` and `exit.json`, all receipts, installed sources and selected evidence.
- Raw Apple images, raw headers/JIB payloads, raw guest logs and private file inventories remain off the repository.

## Actual phone paths

| Item | Path |
| --- | --- |
| Completed owner | /data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume4-owner |
| Completed inspection | /data/local/tmp/pixel-saved-audit-e9cc754-resume4 |
| Completed observer | /data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume4-observer-procstat1 |
| Reused installed inspector | /data/local/tmp/pixel-saved-checks-resume3 |
| Installed owner source | /data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-saved-inspection-resume4.py |

The recorded identities were wrapper 20063/9342623, inspector 20064/9342659, QEMU 21484/9363754 and observer 18179/9323114. All were absent in the final bounded receipt reads.

## Development recovery

The executor disconnected after the live checkpoint `77ec7b95012380659196358a578aad301f8bf8c1`. The browser survived, so the actual final failure and all nine metadata receipt pins were recovered. This checkpoint is published directly through GitHub.

The executor is still unavailable. When access returns, inspect local changes and refs, fetch `pixel10-gpu-integration`, and use a fresh checkout/worktree or otherwise preserve local work before alignment. Do not assume that the failed post-disconnect local alignment ran. The previous local commit was `0ededd092cf32d697464abc3210d082c2503b284`, corresponding to the live checkpoint's tree.

Continue by implementing, testing and reviewing a narrow read-only comparison of the actual saved/baseline root JIBs. A changed JIB is not yet classified as safe or corrupt. No fsck verdict exists for this attempt, and no acceptance gate should be loosened to get past it.
