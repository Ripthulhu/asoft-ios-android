# Guarded wallpaper preparation

`guard_ios26_wallpaper.py` is a separate execution guard for exactly the frozen
`ios26-wallpaper` stage. Its default is a read-only preflight. It does not alter
the frozen runner, its session, earlier guards or audit sources, or existing
checkpoints. The frozen runner still owns QEMU, its frame descriptor, shutdown,
reaping, and the creation of its own checkpoint.

This source is additional execution provenance. A successful original wallpaper
checkpoint is accepted only together with this guard's successful receipt.

## Required boundary

The preparation session must have completed exactly through `ios26-gpu`. The
mandatory app-copy audit must have passed at its original `ios26-apps` prefix
using the committed auditor pair from
`fe0a649ab7b5135f8b9b6729802c3418e336e347`:

| Source | SHA-256 |
| --- | --- |
| `audit_ios26_apps.py` | `948478f244ea96c40df5693f66bef7c28d4da59dee0db7cc56badac1377232e6` |
| `audit_ios26_apps_guest.py` | `aee8d203cc10fdc2a75d93bed9293d66588190e103cddb50720924c46a43c8c5` |

The guard verifies that audit's raw outputs, actual launch and VM records,
native completion, policy, full input hashes, and exact source identities. It
revalidates the partition audit, firstboot guard, and saved-firstboot inspection
at their respective original prefixes. Earlier receipts never gain credit for
newer checkpoints.

The six original disk generations are partition, firstboot, persona, activation,
apps, and GPU. Every actual backing link, full file hash, identity, and virtual
geometry must match the ordered checkpoint chain. The original decoded OS
input remains bound to the app audit. Wallpaper creates a seventh generation
and copies the exact GPU trustcache to `root.tc`.

## Invocation

Keep the passed audits, their source directories, and all preparation evidence
available at their recorded paths. Place this new source outside the frozen
runner directory. For example, with the actual passed app-audit work directory:

```sh
python3 -B /data/local/tmp/pixel-wallpaper-guard/guard_ios26_wallpaper.py \
  --apps-audit-work /data/local/tmp/pixel-apps-audit-e9cc754 \
  --work /data/local/tmp/pixel-wallpaper-guard-e9cc754
```

This writes nothing and starts nothing. Full identity verification can read
substantial data. Review `PREFLIGHT_READY` and the explicit additional-source
provenance, then repeat the same command with `--execute` to authorize only this
wallpaper stage. The new guard work directory must not exist and must be
outside every input, source, and evidence tree.

The guard reconstructs the original session's locale, helper settings, package,
qualification, tooling, and four frozen source hashes. It has no command-line
switch to weaken the original memory or witness requirements. The iOS guest
uses the copied 3 GiB device tree, four CPUs, and 38.4 MHz timebase. The original
fresh launch threshold remains 3840 MiB of `MemAvailable`; the running threshold
remains 512 MiB. In the qualified QEMU `vresearch` machine, `hw/arm/vresearch.c`
reads `/chosen/dram-size`, and `hw/arm/xnuboot_sptm.c` allocates that amount.
Generic `-m` is not the controlling source for this machine's XNU DRAM.

## Added checks and exact limits

Two narrow hooks surround the original behavior:

1. After the original QMP `stop` acknowledgement, query `query-blockstats` and
   require its exact root-backend structure. Every returned parent/backing node
   must have integer zero `failed_wr_operations` and
   `failed_flush_operations`. Missing, malformed, nonzero, or timed-out
   responses fail inside the original shutdown path; ordinary failures still
   reach its `quit`, wait, and owned reaping. The actual response remains in
   the original VM QMP trace.
2. After the original wallpaper supervisor returns, require the shell
   `__SYNCED__` reply and every original native/GPU/frame/milestone/settling
   witness before allowing the guest stage to return and checkpoint. Bound
   source, evidence, and input identities are checked around these hooks.

The frozen wallpaper stage still uses `fw/bootkc`, `dtree-phone-aod`, and
`root26-gpu.tc`, with its 360-second settling interval and 18,000-second stage
deadline. Its `LastSystemVersion` readiness condition is preserved. This guard
does not independently prove an absent-to-present transition of that key or a
complete UI boot.

`stop_flushed` in the frozen VM result retains its historical meaning: the
original `stop` call returned successfully. The extra counters observe recorded
failed guest writes/flushes. Neither that field nor zero counters exposes the
return value of QEMU's stop-internal flush. Shell sync is an additional witness,
not proof of a clean on-disk journal.

## Acceptance and the next mandatory gate

The guard records its own source SHA, all four frozen source SHAs, the exact
equivalent frozen argv, original input identities/full chains, all prior proof
identities, hook observations, and the actual wallpaper attempt metadata in a
separate directory. Success is `GUARDED_WALLPAPER_COMPLETE` with
`checkpoint_accepted_by_guard=true` and unchanged input proofs.

A late receipt, collection, or final hash failure can occur after the original
checkpoint was written. The guard then reports `INCOMPLETE`, leaves the original
checkpoint untouched, and sets acceptance false. A later tool must refuse that
checkpoint; it must not invent a replacement receipt or adopt it automatically.

Before `ios26-locale` or any further Linux write, run the separate saved-wallpaper
inspection in [IOS26-WALLPAPER-INSPECTION.md](IOS26-WALLPAPER-INSPECTION.md). It
requires this exact successful guard and checks raw journals plus both complete
forced read-only filesystem diagnostics. Preparation and packing still do not
constitute independent cold-boot/UI qualification, and the app support gate
remains unchanged.

## Offline verification

```sh
python3 -B -m unittest -v test_guard_ios26_wallpaper
```

The tests use authored small qcow headers and metadata, the real frozen
checkpoint/shutdown code, and mocked QEMU only. They cover counter, sync,
native/GPU/frame/settling, receipt-write, and post-checkpoint failures; actual
quit/reap behavior; immutable full backing hashes; older-prefix preservation;
committed app-audit receipt acceptance; and refusal of altered raw evidence.
They do not run an iOS guest, Linux helper, mount, or phone operation.
