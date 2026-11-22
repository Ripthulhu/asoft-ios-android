# Recovery checkpoint — 2026-11-22

## Start here

**The resume4 saved-filesystem inspection has finished and was not accepted.** Its native helper and cleanup completed normally. The remaining refusal is **`root_baseline_jib_changed` on iOSRoot**, before filesystem checks.

Read [the complete result](resume4-saved-inspection/RESULT.md), [current source/status bindings](resume4-saved-inspection/source-status-current.json), and the [prepared JIB diagnostic package](resume4-saved-inspection/jib-diagnostic/README.md).

## Root JIB diagnostic completed

The reviewed diagnostic was installed and completed on the phone. All sixteen bounded native image-tool reads completed cleanly. The two 4,096-byte root JIBs differ only at byte 3: the baseline flags value `0x5` became `0x1` in the saved image. Journal locations and sizes are unchanged. The actual result is 14,246 bytes, SHA-256 `5d39c9a0fb16c794577abaf4ab7155ee5f352d46cb7027e03b571055f10d5061`; its receipt and result-bound readers were independently reviewed. See [the complete JIB diagnostic result](resume4-saved-inspection/jib-diagnostic/RESULT.md).

This is consistent with the documented clearing of the journal NeedInit bit, but the diagnostic did not evaluate the journal header or perform fsck. The resume4 saved inspection remains rejected. The next step is a separately tested root-only classification requiring an exact authored baseline, a zero baseline journal and a valid initialized-empty saved journal, followed by all existing forced read-only filesystem, native lifecycle and preservation checks in a fresh inspection. No revised inspector has been installed or executed at this diagnostic result checkpoint.

The phone browser connection was restored for these observations. The prior completed firstboot, resume4 inspection and JIB diagnostic must not be relaunched.

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

Continue with the separately reviewed root journal initialization classification and a fresh inspection package. The JIB difference is now measured, while journal emptiness and filesystem health remain unproven. Preserve the existing native, filesystem, memory, cleanup and application gates.
