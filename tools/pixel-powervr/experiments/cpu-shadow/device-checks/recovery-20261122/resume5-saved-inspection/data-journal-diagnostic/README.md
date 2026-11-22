# Read-only Data journal structure diagnostic

## Status

**Completed once on the phone at 2026-11-22 21:35:42.308919 UTC.** All supported
structure checks passed for six transaction-start lists and 49 live payload
entries. The actual-bound summary and two record pages independently reproduce
the retained analysis. Read [the actual result](RESULT.md) and
[current status bindings](source-status-current.json). **Do not relaunch.**

The saved inspection remains unaccepted at its nonempty-journal refusal.
Neither forced read-only filesystem check has run. No replay, repair, mount or
recovery write is part of this diagnostic. The original prepared source and
transport checkpoint is preserved at `caf8e1757ac75a272a5577ae578d7a9918c7c560`.

The completed inspection and its physical evidence are published at
[`2630efc33bebd65a0a61eb9166da4eb0ecca2483`](https://github.com/Ripthulhu/asoft-ios-android/commit/2630efc33bebd65a0a61eb9166da4eb0ecca2483).
Read [the actual inspection result](../RESULT.md) before using this package.
Do not relaunch a completed firstboot, inspection, observer or diagnostic.

## Observed boundary

The checksum-bound guest projection at **2026-11-22T21:11:04.460470+00:00**
reports a passing raw root-journal classification and a Data refusal at
`nonempty_journal`. Data has a valid 512-byte little-endian journal header,
start 512, end 614400 and total journal size 8,388,608 bytes. Its active
interval is 613,888 bytes without wraparound. The stored and computed header
checksums are both 195,764,962; the exact complete header SHA-256 is
`f9bd83c96acbaba80a2d24b09731ef6f39ae78cc922cbca9d65c774716c2a66f`.

Those header facts alone did not validate the transactions inside the active
interval. The completed diagnostic subsequently checked their supported record
structure, checksums, lengths and target bounds while retaining the original
saved image. Its result does not establish filesystem consistency or replay
safety.

The pinned Linux hfsprogs build does not implement journal replay; see
[the existing partition audit rationale](../../../../IOS26-PARTITION-AUDIT.md).
Repeating the same no-replay inspection cannot empty this journal. Any later
recovery would need a distinct fresh copy-on-write descendant and its own
review and acceptance evidence.

## Fixed native read scope

| Read | Maximum bytes |
| --- | ---: |
| Current Data primary volume header | 512 |
| Current Data alternate volume header | 512 |
| Current Data Journal Information Block | 4,096 |
| Current Data journal, including its header | 8,388,608 |

The host uses the exact reviewed native `qemu-img` and fresh task-owned output
paths. Geometry, source images, receipt bindings and recorded process absence
must be checked before reads. Every owned image-tool child must complete
cleanly and be reaped; every original bound receipt, source and backing-file
identity must remain unchanged afterward.

The host rechecks chain identities and metadata records carrying the preceding
full hashes. It does not recompute the complete image files' hashes for this
bounded diagnostic, and must explicitly report that limit. Only the four
listed virtual regions are extracted. Raw extracted bytes remain on the phone;
public output contains bounded selected metadata, counts, verdicts and hashes.

## Narrow parser profile

The pure parser is restricted to the exact observed header and a supported
modern little-endian, nonwrapped active interval. It follows record lengths
inside that interval, validates block-list and available payload checksums,
checks descriptor counts and aggregate byte accounting, and validates that
live target ranges fit within Data. Killed entries have no write destination
but still occupy their recorded payload length. No target blocks are read.

The parser must not follow or export an opaque entry-zero pointer. It must not
export payload bytes, raw target-sector inventories, file names or directory
contents. Unknown flags, absent checksum evidence, inconsistent sequence
relationships and unsupported layouts remain diagnostic `INCOMPLETE` cases.
They must not be silently accepted or presented as proven corruption.

Current layout interpretation is based on the definitions and matching producer
and consumer in Apple's pinned
[`hfs-715.100.10` source](https://github.com/apple-oss-distributions/hfs/commit/d1bac2f062e6e9c0dfcce302d9aacb10173d0eea).
[The independent format review](independent-format-semantics-review.json)
records the exact file identities and resolves the older format note's
contradictory count and obsolete field descriptions. This establishes the
reviewed parser profile, not the exact source revision of the running kernel.

## Meaning of the completed result

A completed supported structural diagnosis can establish which checks passed
for the retained active records. It does not establish filesystem consistency,
the correctness of any recovery implementation, safe replay, a clean root/Data
filesystem result, boot completion, GPU completion or APK readiness. The
canonical inspector and all native, cleanup, resource and application gates
remain unchanged.

## Released source identities

| Source | Bytes | SHA-256 |
| --- | ---: | --- |
| `parse_data_journal.py` | 14,617 | `4036055b490f5fd93a74e6d12de12f511de45e8e0f62dfa81419151fc2dcc852` |
| `host/inspect_data_journal.py` | 51,923 | `85194af9e14f68e16d1990e79603060644a892c772adafc51dc52777055c77c9` |

The author and independent reviewer passed all **29 parser tests** and
**31 host tests** on these exact sources. The synthetic cases cover checksum,
format, count, payload and target-bound failures; fixed extraction scopes;
changed receipts, sources or headers; output allowlisting; owned-child timeout
and reaping; preservation failures; and lock release. Two checksum vectors were
also checked with an independent compiled C implementation. The canonical
inspector was not changed. Source fixtures contain no actual journal payloads.

See [the independent parser release](independent-parser-source-review.json)
and [the independent host release](host/independent-host-source-review.json).
## Reviewed staging and execution

The exact ordered source-only commands are in
[`host/transport-steps.json`](host/transport-steps.json): `00-begin`, seven
numbered chunks, then `08-assemble-install`. The longest command is 5,218 bytes.
The [manifest](host/transfer-manifest.json) binds the exact two installed files.
Installation reconstructs and verifies both source files without running the
diagnostic. Repeating a completed staging step is not an execution procedure;
preserve its existing output and first establish what completed.

The separately reviewed
[`host/run-data-journal-diagnostic.command.txt`](host/run-data-journal-diagnostic.command.txt)
is 1,961 bytes, SHA-256
`49844f2967f3e90da6c15d002374a961ee6e5d364404f2f2dc55e2d71d69143e`.
It verifies the installed sources and executes the diagnostic in the same
owned Python process. It creates no separate launch log or receipt. The host
checks the unchanged 2,816 MiB MemAvailable and 1,536 MiB free-storage floors
before creating its fresh output, and again before each native read. It has no
automatic retry. Any started attempt and its partial outputs remain preserved.

Read-only result projections are preserved separately under `observations/`.
The actual result pin, summary and list pages 0 and 1 were executed and
independently reviewed. Pages 2 and 3 were not needed and were not executed.
See [the result](RESULT.md) for physical evidence and limits; source and
synthetic-test releases alone do not imply a device result. The historical
`host/preparation-status.json` remains unchanged as a preparation record.
