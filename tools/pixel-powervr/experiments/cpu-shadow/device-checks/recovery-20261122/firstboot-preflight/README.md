# Firstboot input preflight accepted; memory gate unmet

The staged guard's read-only preflight returned **`PREFLIGHT_READY`** and was
accepted. Its foreground child exited zero and was reaped, without force,
wrapper error or cleanup errors. **No firstboot was requested or launched.**
The guard work directory remained absent.

The [startup observation](startup-observation.json) records wrapper
16577/start 7298099 and preflight child 16590/start 7298363 at **11:46:03 UTC**.
The [completion observation](completion-observation.json) and
[terminal screenshot](firstboot-preflight-114711.jpg) retain selected results
and the final resource reading at **11:47:11 UTC**. These are screenshot
transcriptions, not exact-byte exports of the phone's receipt files.

## Accepted inputs

The exact preflight command is in [manifest.json](manifest.json). It invokes
the existing `guard_ios26_firstboot.py` with `-B` and the actual passed audit,
auditor source, frozen runner and intended fresh guard-work paths. It contains
no `--execute`. The equivalent execution argv printed inside the guard's plan
was not invoked.

The accepted output is 21,952 bytes, SHA-256
`eda974e4e726b0164f8c5bbcda232c972db53622e22b1736f1091717b2e4713b`.
It identifies seven preparation checkpoints, guard source
`8f98fafd603385b5d3aa20331acc7e536020b6ae136f8690bd190efbeb09845c`,
and the passed partition audit result
`542dcf281cbcfb0016d74eda8dbb7a84db799e390e857321f519de4e0f1a7146`.
The guard performed its complete source, session, audit, checkpoint, artifact
and runtime/tooling preflight. The capture separately rechecked the guard and
audit-result hashes and the still-absent guard work directory on completion.

## Resource gate

| Observation (UTC) | MemAvailable bytes | Firstboot floor met? | Free work bytes |
|---|---:|---|---:|
| 11:46:03 | 3,572,097,024 | No | 74,044,506,112 |
| 11:47:11 | 3,940,978,688 | No | 74,044,493,824 |

The unchanged firstboot floor is **3,840 MiB = 4,026,531,840 bytes**. The final
reading was **3,758.41 MiB**, short by **81.59 MiB** (85,553,152 bytes).
Both readings satisfied the separate 4.5-billion-byte free-space requirement.
A semantic `PREFLIGHT_READY` result does not waive the memory floor.

The capture retained raw battery, power and thermal observations. The final
battery status was `Not charging`, capacity 74, with USB online. The recorded
thermal values are raw readings with their sensor names; they are not a thermal
qualification. No app was stopped and no memory or power setting was changed.

## Recovery and next step

The exact [capture source](capture_firstboot_preflight.py) and
[executed transport](capture-firstboot-preflight.command.txt) are preserved.
Source parsing, source/argv pins and transport round-trip checks passed, and
independent review found no blocker. This 147-line capture only owns the
foreground read-only guard; it cannot launch a boot.

Its phone files use the prefix:

```text
/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-firstboot-guard-preflight-ebbc9c0
```

The suffixes are `.command.json`, `.owner.json`, `.stdout.json` and `.exit.json`.
Do not rerun this capture over those exclusive files. Inspect the retained
receipt and fresh resources before planning any execution owner.

The next permitted stage is the existing [guarded firstboot](../../../IOS26-FIRSTBOOT-GUARD.md),
with a fresh available-memory reading meeting 3,840 MiB, adequate free space,
reviewed physical conditions and owned process/receipt recovery. Keep its
existing source, session, 3 GiB guest, native requirements and thresholds.
After an accepted guarded firstboot, the separate saved-filesystem/journal
inspection remains mandatory before any later Linux disk mutation.

Actual iOS setup boot, final GPU/UI qualification, application-UID coverage and
the APK gate remain incomplete. No phone VM remains running from this capture.
