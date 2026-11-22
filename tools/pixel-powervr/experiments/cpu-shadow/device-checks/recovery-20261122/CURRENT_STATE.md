# Recovery checkpoint — 2026-11-22

## Start here

**The resume4 saved-filesystem inspection has finished and was not accepted.** Its native helper and cleanup completed normally. The remaining refusal is **`root_baseline_jib_changed` on iOSRoot**, before filesystem checks.

Read [the complete result](resume4-saved-inspection/RESULT.md), [current source/status bindings](resume4-saved-inspection/source-status-current.json), and the [prepared JIB diagnostic package](resume4-saved-inspection/jib-diagnostic/README.md).

## Prepared next step

The development checkout was restored from published commit `54f0fa973f4476fc977585557f7acf61bdad4f17`. The bounded root-JIB comparison is now implemented. Its frozen source is **41,544 bytes**, SHA-256 `cf31bf3489bed645dbd59f8e024f6759150f9262f1480e6d9d4ff53f855b9480`; all **28 focused diagnostic tests** passed and were independently rerun successfully. The package separately records its transport and result-reader validation.

The diagnostic derives its two 4,096-byte ranges from the preserved root-header evidence, uses sixteen previously qualified 512-byte reads, and reports scalar fields, hashes and bounded differing-byte ranges. Existing inspection acceptance remains unchanged. See the [scope specification](resume4-saved-inspection/NEXT_JIB_DIAGNOSTIC.md) and the package README for the exact staging, launch and review records.

**The new source has not been installed or run on the phone.** This chat currently lacks access to the originating connected browser session. Restore that browser connection before executing the reviewed seven source-only staging commands and the separate launch command. The actual diagnostic result is still unbound; no detailed result projection is released without a future real observation.

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

The executor became available again with an empty scratch workspace. The prior checkout was absent, so a fresh clone restored the clean published branch at `54f0fa973f4476fc977585557f7acf61bdad4f17`; no old reset or alignment attempt was replayed. See [the restoration record](workspace-restoration-for-jib.json). The previous local commit `0ededd092cf32d697464abc3210d082c2503b284` belonged to the lost checkout and corresponded to the live checkpoint's tree.

Continue with the prepared diagnostic after the originating browser connection is restored. A changed JIB is not yet classified as safe or corrupt. No fsck verdict exists for the completed inspection, and no acceptance gate should be loosened to get past it.
