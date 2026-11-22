# Continue the native Pixel iOS26 work

This is a recovery index, not a live monitor. Recheck the phone before starting
another owner. Last recorded state: **2026-11-22 06:13:37 UTC**. The rootfs
helper was still running; no iOS boot or partition-audit pass is claimed.

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
| Separate partition auditor | 49 offline tests, independent review and real formatter raw-layout rehearsal passed; updated sources staged | [audit procedure](IOS26-PARTITION-AUDIT.md) |
| Firstboot execution guard | 18 offline tests and review passed; source staged, no physical boot yet | [firstboot guard](IOS26-FIRSTBOOT-GUARD.md) |
| Saved-firstboot inspector | 28 offline tests and review passed; sources staged, no physical inspection yet | [saved-disk inspection](IOS26-SAVED-FIRSTBOOT-INSPECTION.md) |
| App-copy auditor | 41 authored host tests and review passed; sources staged, no physical app audit yet | [copy audit](IOS26-APPS-AUDIT.md) |
| Wallpaper guard and inspector | 24 guard and 12 inspector tests plus review passed; sources staged, no physical wallpaper check yet | [staging and order](device-checks/wallpaper-checks-4d900c9/README.md) |

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
| Current separate audit sources | `/data/local/tmp/pixel-boot-checks-ebbc9c0/auditor` |
| Firstboot guard source | `/data/local/tmp/pixel-boot-checks-ebbc9c0/firstboot` |
| Saved-firstboot inspector sources | `/data/local/tmp/pixel-saved-checks-d4e0ac0` |
| App-copy auditor sources | `/data/local/tmp/pixel-app-checks-0126693` |
| Wallpaper guard and inspector sources | `/data/local/tmp/pixel-wallpaper-checks-4d900c9` |
| Intended fresh audit work | `/data/local/tmp/pixel-audit-e9cc754` |
| Intended fresh guard work | `/data/local/tmp/pixel-firstboot-guard-e9cc754` |
| Intended saved-firstboot inspection work | `/data/local/tmp/pixel-saved-audit-e9cc754` |
| Intended app-copy audit work | `/data/local/tmp/pixel-app-audit-e9cc754` |
| Intended wallpaper guard work | `/data/local/tmp/pixel-wallpaper-guard-e9cc754` |
| Intended saved-wallpaper inspection work | `/data/local/tmp/pixel-wallpaper-check-e9cc754` |
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

## Active owner at the recorded boundary

The disk owner selects `--through ios26-partition`, with network enabled and
**without** `--allow-guest-boots`. It cannot select first boot.

Under the transfer/owner base, inspect `ios26-disk-owner-f4d64db.json`,
`ios26-disk-exit-f4d64db.json` if present, and
`ios26-disk-run-f4d64db.log`. Its exact launcher is preserved in
[run_disks.py](device-checks/preparation-iphone-f4d64db/run_disks.py).
Recorded wrapper PID: 29240; runner PID: 29241, starttime: 4673281.
PID identity must be revalidated; do not act on a reused or unrelated PID.

The first five stages are complete: shared-fetch, shared-unpack, shared-build,
ios26-fetch and ios26-decrypt. Last running attempt was `attempts/05-0001`,
`ios26-rootfs`; at 06:13:37 UTC it reported 7.9 GB copied and positive native
execution, with no error (about 101 minutes elapsed). The two cryptex copies
have finished; the main OS-tree copy started at 05:01:32 UTC. The next stage
is `ios26-partition`. The original helper deadline is 7,200 seconds. Last power
check at 05:47 UTC: AC, 75%, battery 24.7 C; available
memory remained above the running bound. Do not infer completion from age.

The top-level preparation `result.json` can still describe the last completed
boundary while a new owner is running. Use the current owner/exit record,
checkpoint inventory and latest attempt `vm-result.json` together. Inspect
only selected protocol/counter lines for exported evidence; full guest serial
logs and firmware stay on the phone.

## Next decisions

1. Check the existing owner before launching any process. Do not run another
   VM or GPU job concurrently. Let the current rootfs/partition owner finish.
   Preserve any failed attempt and fix its concrete cause without fallback.
2. Require exit zero, the complete hash-linked partition checkpoint, native
   witnesses, natural helper exit and clean owned reap. Export metadata only.
3. Run the separate auditor's preflight, then execution, using the exact
   command below. The preparation checkpoint boundary must end exactly at
   `ios26-partition`. No later stage may run before this audit is resolved.
4. Require `PARTITION_AUDIT_PASSED`, both unfiltered full HFS checks, precise
   Data-copy/tweak agreement, unchanged disk/preparation identities and clean
   native ownership. An unexplained HFS internal entry is a finding to classify,
   not permission to add a broad exemption.
5. Run the reviewed [firstboot guard](IOS26-FIRSTBOOT-GUARD.md), which retains
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
   only through `ios26-apps`. Then require the staged [app-copy auditor](IOS26-APPS-AUDIT.md)
   to return `APP_COPY_AUDIT_PASSED` before running the GPU helper. It checks
   source bytes/types/modes/owners and per-copy link relationships for new
   bundles, and exact preservation of the preceding Applications tree.
   The imported `m2-peek.sh`/`apply-apps.sh` can hide a copy error; stage
   completion alone does not prove the intended app inventory.
8. After the GPU helper, use the [staged wallpaper guard](device-checks/wallpaper-checks-4d900c9/README.md)
   and require `GUARDED_WALLPAPER_COMPLETE`. Then require the separate saved
   inspection to return `SAVED_WALLPAPER_INSPECTION_PASSED` before the Linux
   locale mutation. The linked staging record gives both exact commands.
9. After all preparation stages, use the coherent final asset directory with
   the independent [cold-boot/UI harness](IOS26-COLD-BOOT.md). Do not mix
   intermediate trees, kernel, disk or trustcache files. That independent
   harness also needs the same fresh/running memory gates applied explicitly;
   its current source does not enforce them merely through `--ram-gib 3`.

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

After its physical pass, use the guard with:

```sh
/data/data/com.termux/files/usr/bin/python -B \
  /data/local/tmp/pixel-boot-checks-ebbc9c0/firstboot/guard_ios26_firstboot.py \
  --audit-work /data/local/tmp/pixel-audit-e9cc754 \
  --auditor-dir /data/local/tmp/pixel-boot-checks-ebbc9c0/auditor \
  --runner-dir /data/local/tmp/pixel-prep-runner-f4d64db \
  --work /data/local/tmp/pixel-firstboot-guard-e9cc754
```

Then, after a successful guarded firstboot:

```sh
/data/data/com.termux/files/usr/bin/python -B \
  /data/local/tmp/pixel-saved-checks-d4e0ac0/inspect_ios26_firstboot.py \
  --guard-work /data/local/tmp/pixel-firstboot-guard-e9cc754 \
  --work /data/local/tmp/pixel-saved-audit-e9cc754
```

Both are read-only preflights; add `--execute` only after the preceding actual
gate and concrete preflight pass. The [exact staging receipts](device-checks/boot-checks-ebbc9c0/README.md)
bind all five installed sources and both transport ZIPs. They establish
transfer identity, not a physical audit or boot outcome.

After the later helpers complete exactly through `ios26-apps`, use:

```sh
/data/data/com.termux/files/usr/bin/python -B \
  /data/local/tmp/pixel-app-checks-0126693/audit_ios26_apps.py \
  --inspection-work /data/local/tmp/pixel-saved-audit-e9cc754 \
  --work /data/local/tmp/pixel-app-audit-e9cc754
```

This is also preflight by default. The [exact app staging receipt](device-checks/app-checks-0126693/README.md)
binds both installed sources and confirms the nine earlier source hashes
still matched. The physical application-copy audit remains pending.

Session settings remain Europe/Amsterdam, 24-hour clock, empty region, 4 CPUs,
2,048 MiB Linux helper and 3 GiB iOS guest. Fresh memory gates are 2,816 MiB for
the helper and 3,840 MiB for iOS. Running low-memory stop is 512 MiB. Do not
weaken these gates or free unrelated apps' memory to force a launch.

Qualified QEMU allocates XNU DRAM from the copied tree's `/chosen/dram-size`;
the frozen preparation verifies the exact `expected_tree(original, 3, 3)`
bytes. The [source-grounded RAM record](host-checks/wallpaper-guards.json)
identifies the pinned machine allocation path and unchanged thresholds.

## Publication and local continuity

GitHub connector commits have different commit IDs from local commits but
identical verified trees. The last source checkpoint before this note maps
local `0aba7cf9b289338dc906d92c4f12ea3cd1fe493f` to remote
`67669173207f827e8fa1981b4a67a21071d5975f`, tree
`9be9537a8da84468d43c83f4d470515404010773`. Use a fresh head/expected-SHA lease;
never force-push. Later history may supersede this pair.

The active local checkout is
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
