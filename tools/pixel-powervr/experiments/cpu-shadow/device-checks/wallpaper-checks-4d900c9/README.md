# Wallpaper checks staged on the Pixel

The wallpaper execution guard and saved-disk inspector were installed at
`/data/local/tmp/pixel-wallpaper-checks-4d900c9` at
`2026-11-22T06:11:59.382855+00:00`. This is a verified source-staging record.
Neither the wallpaper boot nor its saved-disk inspection has run.

The source changes are author commits `079a9da383812b1851ee325f6c659143f36e0af9`
and `ba93f4836f96b8db531b258609dc7099b1274272`, integrated as `80da59d` and
`4d900c9fe28c16a13d1113ed70538e947ab220d4`. A later documentation-only correction distinguishes
attempted detachment from successful cleanup.

| Installed source | Bytes | SHA-256 |
|---|---:|---|
| `guard_ios26_wallpaper.py` | 37,959 | `a92e26604ec76d2280528ad396a961a8cda901e29177f87887d5b7ce8b495c44` |
| `inspect_ios26_wallpaper.py` | 16,969 | `6519303a9094510ecef88399d815f2079c871dbb8d49b1494c95950c1f937f5a` |
| `inspect_ios26_wallpaper_guest.py` | 3,042 | `0b3f83d3dd7fd74b0c1ee9008c90b874b237b0a8e818fca70e71ab67a19f1b1b` |

The 16,780-byte transport ZIP has SHA-256
`a680011ed0ebb698aad70b1a5b5711ee4f824a9a29b09c95e4669186b1688375`.
The phone verified the whole archive, exact regular-file inventory, lengths,
modes and per-file hashes before installation to a fresh root-owned directory.
It then rehashed the three installed sources and all eleven earlier frozen,
firstboot, partition, saved-inspector and app-auditor sources.

[install.json](install.json) is the exact 2,591-byte phone receipt. Its export
was verified against SHA-256
`540903d5a310af46d20d7355d330fb9b877b52aba27e5c5cb9a43c23e17afdf0`.
Both physical-execution flags remain false.

[Host validation](../../host-checks/wallpaper-guards.json) records the 24 guard
and 12 inspector tests, final source review, and the scope of the retained
test evidence. It also records the verified custom-machine RAM contract:
qualified QEMU allocates XNU DRAM from the patched tree's
`/chosen/dram-size`. Existing source and thresholds are unchanged.

## Required order

After `APP_COPY_AUDIT_PASSED`, run only the original GPU helper. At the exact
GPU-completed boundary, preflight the separate guard:

```sh
/data/data/com.termux/files/usr/bin/python -B \
  /data/local/tmp/pixel-wallpaper-checks-4d900c9/guard_ios26_wallpaper.py \
  --apps-audit-work /data/local/tmp/pixel-app-audit-e9cc754 \
  --work /data/local/tmp/pixel-wallpaper-guard-e9cc754
```

Add `--execute` after that concrete preflight and fresh memory check.
Require `GUARDED_WALLPAPER_COMPLETE` bound to the actual checkpoint and
supervision evidence, including shell sync and zero reported failed guest
writes/flushes. These counters do not expose QMP stop's internal flush return.
The original migration, settling, native/GPU/frame and cleanup requirements
remain mandatory.

Before the Linux locale helper, preflight the saved-disk inspector:

```sh
/data/data/com.termux/files/usr/bin/python -B \
  /data/local/tmp/pixel-wallpaper-checks-4d900c9/inspect_ios26_wallpaper.py \
  --guard-work /data/local/tmp/pixel-wallpaper-guard-e9cc754 \
  --work /data/local/tmp/pixel-wallpaper-check-e9cc754
```

Add `--execute` only after the accepted guard and concrete preflight. Require
`SAVED_WALLPAPER_INSPECTION_PASSED` before locale. It checks both raw journals
before any complete unmounted read-only filesystem check, with full backing
identities and clean native exit/reap.

The [wallpaper guard](../../IOS26-WALLPAPER-GUARD.md) and
[saved-wallpaper inspection](../../IOS26-WALLPAPER-INSPECTION.md) explain the
exact receipt, boundary and unsupported-state rules. These gates do not
establish a usable final UI or completion of the GPU project.
