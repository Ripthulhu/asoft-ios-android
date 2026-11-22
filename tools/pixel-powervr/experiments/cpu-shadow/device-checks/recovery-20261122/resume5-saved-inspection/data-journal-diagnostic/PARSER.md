# Data journal structure parser

This pure parser answers a bounded structural question about the active Data
journal retained after resume5. It changes no canonical inspector or acceptance
predicate. It does not read a device or file, launch a process, replay a journal,
mount a filesystem, run fsck, repair anything, or recommend that replay is safe.
The separate host wrapper owns all actual extraction and preservation checks.

## Actual boundary and exact scope

The independently reviewed guest projection reports `nonempty_journal` after
the current Data journal header passed the existing endian, magic, checksum,
geometry and cursor checks. The saved host result is 7,269 bytes with SHA-256
`08ab06ea5b0e1d46a168935df1dbaabeda0daa7ab569b1e001f61e17d7cfc828`.
The selected evidence and its independent review are in
`../physical-observations/guest-boundary-selected.json` and
`../physical-observations/independent-guest-boundary-evidence-review.json`.
Neither fsck ran. This observation establishes a nonempty Data journal, not a
corruption diagnosis or a filesystem verdict.

The supported parser profile is deliberately limited to the actual dimensions:

| Property | Required value |
| --- | --- |
| Input | Immutable `bytes`, exactly 8,388,608 bytes |
| Data volume | 17,179,869,184 bytes |
| Journal type | Modern JNLx, little endian |
| Journal header | 512 bytes; checksum over original 44 bytes |
| Active interval | Nonwrapped `[512, 614400)`, 613,888 bytes |
| Block-list header | 49,152 bytes |
| Descriptor capacity | At most 3,071 including reserved entry0 |
| Secondary work limits | 16 list headers and 4,096 ordinary entries |
| Actual header SHA-256 | `f9bd83c96acbaba80a2d24b09731ef6f39ae78cc922cbca9d65c774716c2a66f` |

The active interval can contain at most twelve complete list headers of this
size. The explicit caps remain a second bound. No scan continues beyond the
declared active end, and no byte in the inactive region is interpreted.

## Primary implementation basis

The public Apple HFS repository is pinned to commit
`d1bac2f062e6e9c0dfcce302d9aacb10173d0eea`. These files were fetched by exact
commit, and the returned Git blob identities were independently cross-checked:

| File | Git blob | Relevant source locations |
| --- | --- | --- |
| [core/hfs_journal.h](https://github.com/apple-oss-distributions/hfs/blob/d1bac2f062e6e9c0dfcce302d9aacb10173d0eea/core/hfs_journal.h) | `594f574e883c4b9249643f347c150db13d5c737a` | Packed structures, flag definitions and journal checksum boundary |
| [core/hfs_journal.c](https://github.com/apple-oss-distributions/hfs/blob/d1bac2f062e6e9c0dfcce302d9aacb10173d0eea/core/hfs_journal.c) | `fefbf640f97030be63048e471916bff00a4a024f` | 130; 228–238; 545–547; 1225–1287; 1302–1405; 1442–1445; 2550–2559; 2897–2911; 2970–2973; 4140–4143; 4230–4237 |
| [lib_fsck_hfs/fsck_journal.c](https://github.com/apple-oss-distributions/hfs/blob/d1bac2f062e6e9c0dfcce302d9aacb10173d0eea/lib_fsck_hfs/fsck_journal.c) | `3189cd33da18230e7c655b6bf8170c4a8584ddcb` | 270–334 corroborate ordinary-entry iteration, payload bounds and killed entries |

[Apple TN1150](https://developer.apple.com/library/archive/technotes/tn/tn1150.html)
provides the historical format context. Its older block-list terminology and
inconsistent inclusive-count prose are not used to override the pinned modern
producer and reader. The public source does not establish the exact source
identity of the running guest kernel. Unknown or unsupported cases remain
classified `INCOMPLETE`.

## Record interpretation

The modern prefix is sixteen bytes: unsigned16 `max_blocks`, unsigned16
`num_blocks`, signed32 `bytes_used`, unsigned32 checksum and signed32 flags.
Each descriptor is sixteen bytes. `num_blocks` includes reserved entry0;
ordinary entries occupy indices1 through `num_blocks - 1`. The producer starts
the count at one and adds one per payload. Physical table capacity and the
declared maximum both constrain the count.

The block-list checksum covers the first32 bytes with its four-byte field at
offset8 cleared. This covers the prefix and reserved entry0, not the ordinary
descriptor table. Entry0's first eight bytes can contain a serialized in-memory
pointer. The parser never unpacks, follows or exports it. Its signed size must
be zero for this supported producer profile; its final uint32 is a transaction
sequence. The journal header's separate sequence at offset44 is outside the
original44-byte checksum and is not tied to a first or last transaction.

Only the known modern checksum and first-header bits are supported. Checksums
must be enabled. The first list must carry the first-header bit and a nonzero
sequence. Continuations keep that sequence; a new first-header list increments
it by one. This is a strict producer-pattern profile. The upstream reader's
broader compatibility behavior does not turn zero or unsupported cases into
successful diagnoses here. Sequence values are not exported.

Each ordinary descriptor contains a signed64 destination sector, a signed32
payload size and an unsigned32 payload checksum. Payload sizes must be positive,
512-byte aligned and contained in the current record and active interval.
`bytes_used` must equal the list-header size plus exactly all its payload sizes.
The next list starts at that end; no descriptor pointer controls traversal.

A destination of `-1` is a killed entry: its payload still consumes space, but
no destination or payload-checksum verdict is assigned. Other negative targets
are unsupported. Each live destination uses512-byte sector units, and its full
payload range must fit inside the exact Data volume. Every live recorded
checksum is recomputed from the retained payload. A zero stored checksum is
explicitly unavailable in upstream behavior; this diagnostic stops as
`INCOMPLETE` instead of counting it as verified. A mismatch also stops.

The checksum is a noncryptographic 32-bit byte recurrence. Payload checksums
do not independently authenticate the ordinary descriptor table or its target
numbers. No coalescing, destination overlap resolution, filesystem semantics,
transaction replay or recoverability decision is implemented.

## API and output contract

```python
result = analyze_journal(
    immutable_journal_bytes,
    volume_bytes=17179869184,
    expected_header_sha256="f9bd83c96acbaba80a2d24b09731ef6f39ae78cc922cbca9d65c774716c2a66f",
)
```

Both keyword arguments are required. Production must pass the independently
bound actual digest explicitly. Synthetic tests pass their fixture-header
digest while preserving the supported geometry. Inputs must be immutable
`bytes`; mutable buffers are refused before any parsing.

The result contains fixed schema/kind/format fields, the scope, aggregate counts,
at most sixteen list rows, and a fixed-code failure with bounded positions.
Rows expose only journal-relative offsets, counts, sizes, known/raw flag values
and check booleans. No destination block numbers, pointers, exact sequences,
payload bytes, filenames or private inventories are returned. Exception text
does not contain input values. Partial traversal is visibly `INCOMPLETE`, with
whole-interval checks left unknown or false and only completed-list coverage
credited. Complete traversal is `STRUCTURE_DIAGNOSIS_COMPLETE`; all replay,
filesystem-acceptance and inspection-acceptance fields remain false.

## Focused validation

The synthetic suite covers exact count semantics, a multi-list transaction and
new-transaction boundary, killed entries, immutable/size/digest binding,
unknown header profiles, journal and list checksums, every size/count/range
boundary, missing/corrupt payload checksums, negative/overflow-sized targets,
sequence and first-header disagreements, incomplete active tails, work caps,
inactive-region isolation and metadata-only output. Header sequence changes
cannot create an invented transaction binding. Two checksum vectors were also
computed independently using a standalone C uint32 program and then frozen in
the Python tests. No actual journal payload or device content is in the tests.

See `source-validation.json` and the focused test log for exact frozen bytes and
results. Source preparation and synthetic tests do not establish a physical
diagnostic result; the actual output binding remains separate and unfilled
until the new host diagnostic has genuinely run and been independently reviewed.
