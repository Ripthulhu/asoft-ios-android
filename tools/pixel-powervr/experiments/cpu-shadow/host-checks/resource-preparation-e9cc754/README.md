# Disk-backed resource preparation for e9cc754

This records the bounded, reversible cache preparation completed on
2026-11-22 before the separate host header check. Final status:
`RESOURCES_PREPARED_NO_BUILD`. Neither preparation attempt started builds,
tests, VMs, GPU work, or phone operations. The reims source at
`e9cc7541e4edee4896d9564b3056bb2799595d3f`, its existing local Cargo path
overrides, and runtime source at
`51c322d883ea723d290c931b3b2013c50f5e4934` remained unchanged.

## Exact evidence and the interrupted first attempt

`source-files.json` identifies the original path, byte count, and SHA-256 of
each of the 12 byte-identical receipts, scripts, and small logs copied here.
`SHA256SUMS` covers this directory's files. The initial receipt remains
`INCOMPLETE`; the continuation receipt retains its own successful outcome.
Neither receipt was rewritten to combine the two attempts.
The initial script retains its original trailing blank line, which
`git diff --check` reports; its bytes and recorded hash are unchanged.

The initial attempt verified and offloaded the Android target and e9 host
archive, preserving their logical paths as symlinks. Host restoration then
stopped before extraction with `ReadError: empty file`. The observed
decompressor diagnostic was that the archive was a symbolic link and was
being ignored. Direct `zstd` commands refuse these symlink arguments by
default. The resolved archive still matched the pinned SHA-256
`13c4a006e87a11afe29ab8f052a2c28673233a308e684fe53b4ec0665be897c5`.

The continuation binds the original script and receipt hashes, revalidates
both completed offloads, and supplies that verified resolved regular-file
path to the original restoration functions. It leaves the required logical
symlink and initial evidence unchanged. Its raw output is retained as
`continuation/execution.log`. Initial terminal output was not saved as a
separate raw log; its structured failure receipt and the two empty copy
command logs are preserved exactly. The scripts are historical execution
evidence tied to these specific paths and identities, not general rerun
entry points.

## Preserved logical paths

For the destination descriptions below:

- `INITIAL` is `/workspace/scratch/3ef77e3b5dde/native-runtime-build/reims-resource-prep-e9cc754-9d8jiytv`.
- `CONTINUATION` is `/workspace/scratch/3ef77e3b5dde/native-runtime-build/reims-resource-prep-e9cc754-cont-rbqa7m4m`.

| Logical path | Preserved destination |
| --- | --- |
| `/home/agent/.cache/reims-pixel-cpu-shadow-target` | Its existing symlink to `/dev/shm/reims-pixel-cpu-shadow-target` is unchanged. |
| `/dev/shm/reims-pixel-cpu-shadow-target` | `INITIAL/android-target` |
| `/tmp/reims-pixel-capabilities-host-target-e9cc754.tar.zst` | `INITIAL/archives/reims-pixel-capabilities-host-target-e9cc754.tar.zst` |
| `/tmp/pixel-cpu-shadow-prior-builds.tar.zst` | `CONTINUATION/archives/pixel-cpu-shadow-prior-builds.tar.zst` |
| `/home/agent/.cache/reims-pixel-capabilities-target` | `CONTINUATION/host-target` |

The tiny original host target remains intact at
`/home/agent/.cache/reims-pixel-capabilities-target.pre-disk-rbqa7m4m`.
Direct `zstd` consumers of either archive must resolve the preserved
symlink to the verified regular file explicitly.

## Verification and resulting headroom

Every offload required complete file-content hashes, ownership, modes,
mtimes, symlink targets, and regular-file hardlink relationships to match
before releasing the duplicate tmpfs original. Process ownership scans
found no visible users or unreadable process records. Verified copies were
fsynced before release. Host restoration also required a successful full
`tar --compare`, exact archive-member and hardlink checks, and preservation
of the tiny target's metadata, including its root mtime.

The restored host inventory contains 2,037 entries and 1,972,345,101 unique
regular-file bytes. All 10 complete inventory JSON files remain outside
Git; `inventory-references.json` records their retained absolute paths and
verified hashes. These inventories describe the preparation boundary, not
the contents of caches after later authorized builds.

| Observation | Before preparation | Final sample, 06:40:18 UTC |
| --- | ---: | ---: |
| Available RAM | 2,778,038,272 bytes | 4,642,836,480 bytes (4.32 GiB) |
| Workspace free disk | 8,065,187,840 bytes | 4,339,798,016 bytes (4.04 GiB) |
| `/dev/shm` used | 983,932,928 bytes | 0 bytes |
| Swap | 0 bytes | 0 bytes |

After host restoration, available RAM was 4,250,181,632 bytes, below the
required 4 GiB. Only then was the older prior-builds archive offloaded. The
final sample passed both the 4 GiB available-memory gate and the 1,536 MiB
workspace reserve. This is resource preparation evidence, not a measured
peak-memory guarantee or a header, full-check, suite, or guest-boot result.
The later host header check is recorded separately.

No cache contents, compiled outputs, archive binaries, or full inventories
are included in this directory.
