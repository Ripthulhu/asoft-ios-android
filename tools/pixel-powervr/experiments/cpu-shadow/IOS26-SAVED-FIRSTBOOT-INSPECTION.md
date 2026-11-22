# Saved firstboot: separate read-only journal and filesystem gate

`inspect_ios26_firstboot.py` inspects the saved output of exactly one accepted
`ios26-firstboot` stage. It creates no preparation checkpoint and does not resume
preparation. Its default is read-only preflight. Physical execution is a separate,
explicit `--execute` action after the firstboot guard succeeds.

The gate is needed because the pinned Linux hfsprogs `journal_replay()` is a stub,
and its `IsJournalEmpty()` can return “empty” after a read/format failure or a
checksum mismatch. A clean-looking fsck footer alone cannot authorize a later
Linux write to a disk that Darwin has modified.

## Run

Keep these two new source files together in their own source directory:

```text
inspect_ios26_firstboot.py
inspect_ios26_firstboot_guest.py
```

The approved firstboot guard source, its three receipts, its actual attempt
metadata, both source files of the **passed** partition auditor, the four frozen
preparation files, the qualified package, tooling and every original preparation
artifact must remain at their receipt-bound paths. The inspector does not copy,
edit, replace, adopt or repair those records.

For example, with a fresh short output path:

```sh
python3 -B /data/local/tmp/pixel-inspector/inspect_ios26_firstboot.py \
  --guard-work /data/local/tmp/pixel-firstboot-guard-e9cc754 \
  --work /data/local/tmp/pixel-saved-audit-e9cc754
```

After reviewing that preflight, execute the same command with `--execute`.
Use a new output directory for every attempt. A previous `INCOMPLETE` directory
is evidence to retain, not a resumable checkpoint. The example assumes those
source and guard directories have been staged and exist; staging is not done by
this tool.

Execution inherits the session's helper RAM and CPU count. It uses the frozen
native-required 16 KiB Linux helper, 38.4 MHz counter and process owner. The
current 2,048 MiB helper requires a fresh **2,816 MiB MemAvailable** before launch.
The runtime floor remains 512 MiB, free-storage floor 1,536 MiB, combined log
bound 64 MiB and default helper deadline 7,200 seconds. The deadline can be
shortened or raised to at most 14,400 seconds; the memory/storage floors cannot
be weakened. This helper's memory requirement does not change the separate
3,840 MiB firstboot memory gate.

No network, Apple download, iOS launch, APK operation or GPU test is part of this
inspection.

## Exact ownership and provenance

Before execution, the inspector requires:

1. The approved guard source hash and `GUARDED_FIRSTBOOT_COMPLETE` receipt,
   including `checkpoint_accepted_by_guard: true`. A firstboot checkpoint left
   behind by a later guard evidence failure is insufficient.
2. The unchanged current firstboot checkpoint, exact ordered preceding chain,
   actual firstboot attempt, shell `__SYNCED__` witness and the actual ordered
   QMP `stop` → `query-blockstats` → `quit` trace. All returned failed-write and
   failed-flush counters must still validate as zero.
3. The separately passed partition audit at **its original earlier prefix**,
   with the actual auditor source hashes, raw output hashes, clean filesystem
   verdicts, native execution and cleanup. Firstboot is not retroactively added
   to that audit's scope.
4. The original full preparation artifact checks, matching 17-case qualification,
   shared runtime provenance and exact pinned tooling inventory.
5. Full SHA-256, file identity and qcow2-chain checks for **both** the saved
   firstboot overlay and its recorded audited predecessor. No extra, missing,
   redirected or external backing member is accepted.

Execution acquires the existing preparation `owner.lock` with a read-only file
descriptor and nonblocking exclusive flock. It refuses live owned children,
rechecks every bound input and creates only a fresh inspection directory and
its own lock. The original session/checkpoints/four runner files remain frozen.
Both disk files are attached with `readonly=on`; the predecessor is attached
separately as the reference for an untouched journal.

The helper launch uses the verified frozen `helper_command()` and
`supervise_vm()` without hooks or changes. A successful result needs positive
native initialization/execution, the helper's unique `ASOFT: done 0` and output
size, natural QEMU exit, exit code zero, `ECHILD` and no forced cleanup. Complete
disk and backing hashes are checked again after either success or failure.

The firstboot guard's historical `stop_flushed` field means that its original
`stop` call returned successfully. It does not expose the return value of
QEMU's internal flush. This inspection adds observed saved journal/filesystem
state; it does not rewrite that earlier evidence or claim a stronger flush
acknowledgement.

## Raw journal rules

The guest performs no mount. It reads GPT sectors, the primary and alternate
volume headers, JIB allocation blocks and journal headers directly from the
read-only devices. Both GPT copies require their real on-disk CRCs, reciprocal
LBAs and exact original geometry:

| Volume | Start sector | Sectors | Size |
|---|---:|---:|---:|
| iOSRoot | 2,048 | 67,108,864 | 32 GiB |
| Data | 67,110,912 | 33,554,432 | 16 GiB |

The disk size is 51,541,704,704 bytes. The saved GPT must equal the audited
predecessor GPT. Both volume headers must describe the authored HFSX version 5,
4,096-byte allocation geometry and agree on the journal discovery block and
volume identity. JIB and journal locations must match the predecessor, remain
inside the volume and avoid reserved or recorded inline metadata ranges.
Relocated, resized, external, nonjournaled or unknown layouts remain
`INCOMPLETE` for a separate source-based classification.

### Initialized journal

Only JIB flags `1` (in-volume, initialized) enter this path. The inspector
requires consistent `JNLx` magic and endian marker, a size matching the JIB,
the 512-byte sector header, and a correct checksum of the first **44 bytes**
with checksum bytes 36–39 zeroed and unsigned 32-bit arithmetic. The sequence
number and sector padding are outside that checksum.

The frozen launch's exact `virtio-blk-pci,drive=root` device is checked without
block-size overrides. In the pinned QEMU source, the qcow2 backend has no block
size probe and is not a filter, so `blkconf_blocksizes()` falls back to
`BDRV_SECTOR_SIZE = 512`; virtio exposes that value. The inspector therefore
does not infer the sector size from an untrusted journal header.

Block-list header size must be a sector multiple, fit the journal buffer, and
be representable by its 16-byte entries and 16-bit count. Acceptance is not
limited to the “typical” 4–16 KiB range. Unrecognized configurations are refused.

Both cursors must be aligned, at or after the header and **strictly below** the
journal size; then `start == end` must hold. A cursor equal to the size is an
explicitly **unsupported representation**, not a declaration of corruption.
The available primary format note does not settle that boundary case, and the
matching kernel normalization code was not available for review. No implicit
wrap or repair is performed. Numeric cursor/size/checksum metadata and a header
digest are retained for classification when these checks fail.

An initialized empty journal's inactive payload is not required to be zero and
is not interpreted. Old inactive transaction bytes have no bearing on the
empty-range decision.

### Untouched formatter journal

JIB flags `5` (in-volume plus NeedInit) are accepted only when both journal
regions have the exact authored formatter state, with unchanged volume-header
bytes. The JIB must have the
bitmap-derived allocation block (257 for iOSRoot, 129 for Data), the original
8 MiB journal immediately after it, the exact 180-byte JIB contents, `0xdb`
padding to byte 511 and zero remainder of its allocation block. Both complete
volume headers must be byte-identical between saved and predecessor disks.
The complete journal must be zero in both disks, with matching digests.

A generic zero-looking header, a NeedInit bit on an initialized predecessor,
changed header/JIB bytes or a single nonzero journal byte does not qualify.
This checks the journal's raw uninitialized state; it does not discover journal
files by names or remount/reclassify the earlier copied Data tree.

## Filesystem checks and outcome

Only after **both** raw journal gates pass does the guest create the exact
read-only partition loop views. Each must report its expected size and
read-only state and must be unmounted. It runs:

```text
fsck.hfsplus -f -n LOOP
```

The existing passed auditor's byte-identical GPT, command, loop and strict fsck
helpers are a hash-bound dependency; its mount and tree-comparison routines are
not called. Both full unfiltered logs require exit zero, a unique positive clean
summary and actual extents, catalog, bitmap and volume-information check phases.
Skipped/incomplete checks, journal read/replay diagnostics, repair/error text and
nonzero exits fail. Each check has a 1,200-second deadline and a 4 MiB output
limit. Detachment is attempted for every created loop, including after a later
failure; any cleanup failure prevents a pass. Raw GPT and journal observations
are reread after successful checks.

The fresh directory contains:

```text
inspection-session.json
result.json
a1/expected-policy.json
a1/launch.json
a1/vm-result.json
a1/files/inspection/result.json
a1/files/inspection/fsck-system.txt
a1/files/inspection/fsck-data.txt
```

Early guest failures may return only their metadata result. They remain
`INCOMPLETE`; missing filesystem logs cannot produce a pass. The host binds
all returned file hashes to a fresh nonce and inspection-session digest.

Only `SAVED_FIRSTBOOT_INSPECTION_PASSED`, with unchanged complete backing-chain
hashes and unchanged preparation/guard inputs, satisfies this gate for later
separately reviewed preparation work. It is not a general permission to mutate
these input files. It does not establish final cold boot, UI behavior, native
GPU qualification of iOS, or final app support; those flags remain false.

## Source basis and offline verification

- [Apple TN1150, HFS Plus Volume Format](https://developer.apple.com/library/archive/technotes/tn/tn1150.html):
  volume-header/JIB discovery, journal endian/magic/size/checksum and empty
  transaction-range semantics.
- The byte-matched hfsprogs 540.1.linux3 source: `SVerify1.c` supplies the exact
  44-byte checksum boundary and shows its permissive error behavior;
  `newfs_hfs.c` and `makehfs.c:WriteJournalInfo` establish the formatter layout.
- Pinned QEMU source `755b88fad8a2771a8e3e207133a54898b740cd7f`:
  `hw/block/block.c`, `hw/block/virtio-blk.c`, `block.c`, `block/qcow2.c`,
  `include/block/block-common.h` establish the default 512-byte sector path.

Run the focused host suite from this directory:

```sh
python3 -B -m unittest -v test_inspect_ios26_firstboot
```

Tests use authored sparse byte ranges, literal checksum vectors, synthetic qcow2
headers and mocked helper/utility calls. They cover valid endian forms,
checksum/magic/size/cursor refusals, inactive payload acceptance, exact NeedInit
comparison, journal failures preventing all fsck execution, cleanup, receipt
and backing-hash changes, default preflight, lock conflict and actual safe
return-tar extraction. They do not run any phone, guest, GPU, mount or image
operation. Physical results must be recorded separately after execution.
