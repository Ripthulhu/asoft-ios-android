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
