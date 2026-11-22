# Read-only audit of the prepared iOS26 partition disk

`audit_ios26_partition.py` checks the **completed `ios26-partition` boundary**
before the first iOS setup boot. It is a separate tool and work directory. It
does not modify the frozen preparation runner, checkpoint files, partition
disk, or any predecessor. Its default is a read-only preflight; `--execute`
explicitly starts the already qualified native Linux helper.

The original `mk-root26g.sh` pipes the Data `rsync` through a filter and discards
its status. Some filesystem-check statuses are also discarded. A successful
helper exit and `qemu-img check` therefore do not establish that the Data tree
was copied completely. This audit supplies that additional gate.

## Run at the partition boundary

Keep these **two new files together**, in a separate source directory:

- `audit_ios26_partition.py`
- `audit_ios26_partition_guest.py`

Point `--runner-dir` to the existing, unchanged directory containing the four
Python files used for the physical preparation session. The tool reads their
hashes from `PREP/session.json`, hashes all four files **before importing any
of them**, and compiles those exact bytes without a bytecode cache. A newer
checkout is not a substitute for the frozen sources. The preparation session
must have every checkpoint through `ios26-partition` and no later checkpoint.

```sh
/data/data/com.termux/files/usr/bin/python -B audit_ios26_partition.py \
  --prep-work /data/local/tmp/pixel-prep-e9cc754 \
  --runner-dir /absolute/path/to/the/existing/frozen/runner \
  --work /data/local/tmp/pixel-audit-e9cc754
```

Replace the runner path with its actual existing location. After reviewing the
printed preflight, add **`--execute`** to the same command. Use a fresh audit
work directory for every attempt; a failed audit is retained, not overwritten.
The work path must have an existing parent and be at most 55 characters long.
Do not run preparation, another VM, or GPU diagnostics concurrently.

The package, physical qualification, tooling receipt, helper RAM and vCPU
count are derived from the existing preparation session. The frozen gate still
requires all **17 physical cases**, including `core` and
`core-no-argument-buffers`, matching logs, exact package hashes, and identical
runtime archive/header provenance for the core fixture and QEMU. The reviewed
tooling manifest and every tooling file are checked again. This audit never
downloads firmware, builds an APK, changes the app support gate, or tries a
TCG-only fallback.

Execution holds the existing preparation lock through a **read-only file
descriptor**, checks for existing live owned children, and writes only under
the fresh audit root. It retains the original helper process ownership,
PDEATHSIG/subreaper, QMP cleanup and native-execution requirements. A pass needs
positive native initialization and execution, exactly one `ASOFT: done 0`,
natural QEMU exit 0, complete reap, and no forced cleanup. A helper protocol
success alone never becomes an audit pass.

## What must pass

The partition output must be a standalone qcow2 with no backing file and an
exact virtual size of **51,541,704,704 bytes**. Its full file SHA256 must match
the completed checkpoint before execution. The same full hash, file identity,
preparation session, checkpoint chain and source identities are checked after
the helper, including when the helper or comparison fails. Other predecessor
artifacts are retained and identified by the checkpoint chain; this separate
audit does not redundantly rehash every downloaded or decrypted predecessor.

QEMU opens the final disk with `readonly=on`. Inside the helper, the audit
requires `blockdev --getro` to report 1, validates the protective MBR and both
raw GPT copies, and verifies both header and entry-array CRCs independently.
It does not accept a utility's reconstructed in-memory partition table.

| Volume | Start sector | Sector count | Byte offset | Length |
|---|---:|---:|---:|---:|
| `iOSRoot` | 2,048 | 67,108,864 | 1,048,576 | 32 GiB |
| `Data` | 67,110,912 | 33,554,432 | 34,360,786,944 | 16 GiB |

Both HFS partitions must have their exact authored labels, GUID types, flags,
and geometry, with no extra partition entries. For each partition the tool
creates a fresh `losetup --read-only --offset ... --sizelimit ...` view, checks
its read-only state and exact length, and confirms that it is unmounted.

It then runs **`fsck.hfsplus -f -n` directly on both unmounted views**. The full
combined stdout/stderr is retained. Both actual exit codes must be 0; each log
must show the extent, catalog, bitmap and volume-information check phases and
exactly one positive `appears to be OK` result. Skipped/abbreviated checks,
repair or modification, incomplete reads, corrupt state, and journal replay or
nonempty-journal diagnostics fail the audit. `NO WRITE ACCESS` and `(NO WRITE)`
are valid read-only banners. No repair or replay is attempted.

Only after both checks pass are the volumes mounted separately with
`ro,nosuid,nodev,noexec`, followed by verification of the actual mount flags.
The Data mount never covers P1's underlying `private/var`. The comparison:

- walks both trees through directory file descriptors and `O_NOFOLLOW`;
- compares all path sets, types, numeric owners and permission bits;
- hashes the full contents of every unchanged regular file on both sides;
- compares symlink target strings without following them;
- compares hard-link relationships among the copied paths, while allowing a
  source link to a path outside the copied subtree to be absent on Data;
- allows only exact authored plist replacements/merges and required parent
  directories, validating their full semantic content, owners and modes.

The six preference plists, user/effective auto-lock settings, system keybag,
disabled-service plist and optional activation data are reconstructed from
the source tree and the pinned authored scripts' rules. Unrelated source keys
must remain identical, including strict `bool`/`int`/`float` node types. An
existing unparseable source plist is a failure. Optional files and the
activation container are selected from the **source**, then required in Data.
There are no broad preference, container, or hidden-file exemptions. Unexplained
filesystem-internal entries also fail for explicit classification; do not
delete them or broaden an exemption just to obtain a pass.

### Exact Data journal classification before first boot

The pinned `mk-root26g.sh` runs `mkfs.hfsplus -s -J -v Data`. Its formatter
creates two ordinary catalog files at the new volume root, independently of
the copied `private/var` tree. Linux's HFS+ directory iterator hides its
hard-link storage directory, but does not hide these two regular files.
The audit therefore validates their complete authored identity separately:

| Data-root file | Catalog ID | Bytes | UID:GID / permission bits | Raw offset within Data |
|---|---:|---:|---|---:|
| `.journal` | 16 | 8,388,608 | 0:0 / `0000` | 532,480 |
| `.journal_info_block` | 17 | 4,096 | 0:0 / `0000` | 528,384 |

Both must be regular no-follow files with exactly one link and the expected
mounted sector count. Either name appearing in the **source** `private/var`
tree is a collision and fails. These are the only classified additions;
ordinary copied entries, authored preference changes, and every unexplained
entry retain the same checks.

The classification requires both raw volume headers to identify the exact
16 GiB HFSX v5 volume, 4 KiB allocation blocks, the journaled attribute and
JIB allocation block 129. The primary header must indicate a clean, unmounted
volume without the software-lock attribute. Both headers must describe the formatter's 128-block bitmap
at allocation block 1. Recorded inline metadata extents must stay within the
volume and outside the JIB/journal range. The existing full forced fsck gates
remain responsible for the complete allocation/catalog trees.

The two **raw catalog records** must also retain the exact formatter identity
and forks: `.journal` has exactly 2,048 allocated blocks in one extent starting
at block 130, and `.journal_info_block` has exactly one block at 129. Each
80-byte data-fork descriptor must match completely, including logical size,
zero clump size, total allocation and seven empty extent slots; each resource
fork must be entirely zero. This check closes a specific Linux-observation
gap: HFS+ `st_blocks` is derived from logical size, and its block mapping stops
at logical EOF, so neither excludes otherwise consistent extra allocation or
a nonempty resource fork. The pinned fsck permits such allocation.

The catalog reader is deliberately bounded: it accepts only a complete inline
extent map, the authored 8,192-byte node format and binary key order, and reads
at most 64 linked leaves through the root-directory key prefix. It validates
node/record bounds, link continuity and key order, and refuses catalog extent
overflow, unsupported layouts, missing or repeated records, or cycles. It
does not replace the existing full fsck. The report retains hashes of the two
validated records and their fork metadata, with no raw catalog content.

The journal info block must match **all 4,096 authored bytes**: the 180-byte
big-endian structure has flags **5** (`JournalInFS | JournalNeedInit`), the
exact offset and 8 MiB size above, and zero device-signature/reserved fields;
bytes 180–511 contain the formatter's `0xdb` padding, and bytes 512–4095 are
zero. Its pointer must be aligned, in bounds and disjoint from the info block.
The entire raw 8 MiB journal must be zero. This is the formatter's intentional
uninitialized state, not a malformed initialized journal. The pinned fsck's
`IsJournalEmpty` explicitly treats `JournalNeedInit` as empty.

The same bytes must be present in the two mounted files. Read-only Linux
`FIGETBSZ`/`FIBMAP` calls additionally require **every** logical filesystem
block to map to the exact raw range and require an unmapped block at EOF.
This rejects relocated all-zero files even when their hashes match. The
queries use the filesystem block unit returned by `FIGETBSZ`, not the helper's
16 KiB memory-page size. An unsupported or denied mapping query fails; there
is no content-only fallback. They do not allocate blocks or request writes.

An initialized journal with flags **1** is explicitly refused as
`initialized_journal_outside_pre_firstboot_scope`. Other flag combinations,
wrong identities or bounds, nonzero journal data, altered JIB padding, and
raw/mounted disagreement also fail. Extra allocated data extents, nonempty
resource forks and unsupported catalog layouts fail independently of matching
mounted bytes. No generic journal-header rule is used
to excuse arbitrary journal contents.

#### Utility and source provenance

The helper initrd is the already pinned release asset, SHA-256
`7dff81e88f5e6261ae206c6c481f53748374d76ebd433be7b263f34c571a4a24`.
Its two utility files match the corresponding files in the official Ubuntu
Noble arm64 package **byte for byte**:

| Object | Bytes | SHA-256 |
|---|---:|---|
| `mkfs.hfsplus` | 69,752 | `13230fafb7be0e4b209b490f95be4e6fb115ab1d1dad0ef0afff5a579ff00ddb` |
| `fsck.hfsplus` | 336,592 | `cb4531925cc7a8df80e3f17bab7664834f0e208856e54b56b1b0eec89d8fec74` |
| `hfsprogs_540.1.linux3-5build3_arm64.deb` | 162,602 | `03e294bc518639ad4685f263788b49d46a396ef92bb9792746454df357134760` |
| `hfsprogs_540.1.linux3-5build3.dsc` | 2,165 | `38f6c39fecc7b4375891ee12a9e58d50e6091f8c94d9e7486703212b30d44ad1` |
| `hfsprogs_540.1.linux3.orig.tar.gz` | 411,205 | `b01b203a97f9a3bf36a027c13ddfc59292730552e62722d690d33bd5c24f5497` |
| `hfsprogs_540.1.linux3-5build3.debian.tar.xz` | 36,700 | `ac4171210d6174d6071988e850beb447e1c60bdf0f17cd7656e27690179b2042` |

Official package/source files are in the
[Ubuntu hfsprogs archive](https://ports.ubuntu.com/ubuntu-ports/pool/universe/h/hfsprogs/).
The [source control file](https://ports.ubuntu.com/ubuntu-ports/pool/universe/h/hfsprogs/hfsprogs_540.1.linux3-5build3.dsc)
records the matching upstream and Debian-patch SHA-256s. The relevant source
is `newfs_hfs.tproj/{newfs_hfs.c,makehfs.c}` (`hfsplus_params`, `InitVH`,
`InitCatalogRoot_HFSPlus`, `WriteJournalInfo`) and
`fsck_hfs.tproj/dfalib/SVerify1.c` (`IsJournalEmpty`). The latter package's
`CatalogCheck.c::CheckFile` permits logical size below total allocation, which
is why the additional exact fork comparison is necessary. The Debian patches do not
change these journal construction rules. The
[maintained source view](https://sources.debian.org/src/hfsprogs/540.1.linux3-5/newfs_hfs.tproj/makehfs.c/)
and [Apple HFS+ format specification](https://developer.apple.com/library/archive/technotes/tn/tn1150.html)
provide the corresponding catalog/JIB layouts.

The pinned helper kernel identifies itself as Linux **6.12.114**. Inspection
of that upstream stable version supplies the directory and ioctl semantics:
[HFS+ directory iteration](https://github.com/gregkh/linux/blob/v6.12.114/fs/hfsplus/dir.c),
[HFS+ inode/bmap operations](https://github.com/gregkh/linux/blob/v6.12.114/fs/hfsplus/inode.c),
[HFS+ block mapping](https://github.com/gregkh/linux/blob/v6.12.114/fs/hfsplus/extents.c),
[generic ioctl implementation](https://github.com/gregkh/linux/blob/v6.12.114/fs/ioctl.c),
and [ioctl definitions](https://github.com/gregkh/linux/blob/v6.12.114/include/uapi/linux/fs.h).
Runtime block-map checks establish the actual mounted linkage; the kernel
version string alone is not presented as proof of a reproducible kernel build.

This classifier applies only to the untouched pre-firstboot boundary. The
pinned Linux build's `journal_replay` in `SVerify1.c` is a stub returning 0,
despite the comment in `root26-do.sh` claiming replay. After Darwin initializes
the journal, explicit guest sync and a separate read-only inspection of the
saved initialized journal are required before considering any later Linux
mutation. A clean-looking helper exit does not establish that replay occurred.

The build and version must be `23G90` / `26.6.2` from P1's system-version
plist. P1's `private/etc/fstab` must be a regular no-follow file containing the
exact authored two mount lines. Its owner/mode are reported rather than given
an invented chmod rule: the original script only truncates/writes that file.
The scope covers the copy's bytes/types/owner/mode/link relationships and exact
authored Data changes. It does not claim preservation of ACLs or xattrs, which
the original `rsync -aH` command did not request.

## Bounds, outcomes and retained evidence

The default VM bound is **7,200 seconds** (`--audit-seconds`, allowed 60–14,400).
Each fsck has a 1,200-second local deadline and a 4 MiB output-size limit.
The existing helper memory gate still requires RAM plus 768 MiB available;
with the session's 2,048 MiB RAM this means **2,816 MiB available** before launch.
The default running bounds remain 512 MiB available memory, 1,536 MiB free
storage and 64 MiB host logs. This does not relax the later iOS boot's separate
3,840 MiB available-memory requirement.

A successful result is **`PARTITION_AUDIT_PASSED`** with `disk_unchanged: true`
and `preparation_records_unchanged: true`. Every missing, failed or interrupted
gate remains **`INCOMPLETE`** with exit status 2. There is no repair, automatic
retry, checkpoint fabrication, or write to the preparation session. A failed
guest comparison can still return its metadata through the helper's
success-only output channel; the host independently validates the audit
verdict, fresh attempt nonce, policy digest and unfiltered fsck results.

The fresh work directory contains `audit-session.json`, `result.json`, and
`a1/` with the owned launch/process records, serial/native logs, VM cleanup,
input and bounded output tar disks, the expected nonce/policy, and extracted
`files/audit/{result.json,fsck-system.txt,fsck-data.txt}`. A failure before either
fsck may have only `result.json`. Reports contain metadata, path names, counts,
digests and verdicts; fsck logs can contain filenames/catalog diagnostics but
no requested image/file-content dumps. Plist values, certificates, and Apple
image bytes are not exported. Original guest assets stay on the phone.

This gate establishes a read-only filesystem/copy audit of this exact prepared
disk. It does **not** establish that iOS has booted, that the real iOS GPU path
is complete, or that an APK is ready.

## Focused offline checks

```sh
python3 -B -m unittest -v test_audit_ios26_partition
```

The tests use authored files, sparse GPT sector maps and mocked helper
execution. They cover both GPT copies/CRCs, incomplete or misleading fsck
output, unchanged-time content changes, missing/extra files, symlink and
hard-link relationships, owner/mode errors, independently specified plist
transformations and strict types, source-derived optional outputs, source-hash
and owner-lock refusals, real returned-tar extraction, final disk-change
refusal and failed-VM evidence. They perform no QEMU/GPU execution, mount,
firmware download or phone operation.

Journal cases independently encode the formatter layout and cover source-name
collisions; missing or wrong file identities, owners, modes, link counts and
sizes; both volume headers; bitmap and metadata-extent overlap; pointer bounds
and alignment; all JIB padding regions; zero/nonzero raw and mounted journal
data; initialized-journal refusal; block-map gaps, relocation, EOF and unit
handling; unsupported ioctls; raw catalog identity, extra data allocation,
nonempty resource forks, unsupported overflow/node formats, damaged record
bounds, duplicate/missing names and leaf cycles; and preservation of ordinary-copy/extra-entry
refusals when journal classification succeeds. Linux block-map calls are
mocked in these host tests; their physical execution remains part of the
required phone audit.

An independent host rehearsal also built `newfs_hfs` from the verified
upstream and Debian source archives, applied all six Debian patches, and
formatted a sparse authored 16 GiB Data image with the exact command above.
The new raw header, catalog-fork, full-JIB and all-zero-journal checks passed
against that real formatter output. The host build used an explicitly recorded
empty `uuid/uuid.h` include because this target uses no declarations from it;
the unchanged `missing.h` supplies `uuid_string_t`. This is source-level layout
evidence, not execution of the released arm64 utility. There was no mount,
FIBMAP, fsck, VM or phone execution in that rehearsal. The source identities,
byte-matched utility comparison, host test result, independent review and
rehearsal receipts are retained in
[`host-checks/partition-journal.json`](host-checks/partition-journal.json).
