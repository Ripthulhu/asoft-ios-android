# HFS header failure: conditional interpretation

> **Post-diagnostic update:** the actual eight-header result at 16:39:46 UTC
> showed bit 13 set in every copy. The nonjournaled-root hypothesis below is
> ruled out. iOSRoot's alternate bit 11 is preexisting, with corresponding
> saved/baseline header hashes equal. The source-supported narrow classifier,
> explicit bit-14 tightening and required journal/fsck checks are documented in
> [the resume3 inspector revision](resume3-inspector-revision/README.md).
> The remaining text preserves the earlier conditional analysis as history.

## Established boundary

The resume2 guest inspection returned
`volume_not_journaled_or_inconsistent` for `iOSRoot`. The observed attachments
were read-only; GPT checks passed, and no mount, replay, repair or fsck ran.
**The eight raw current/baseline volume headers have not yet been observed in
this analysis. No filesystem diagnosis or acceptance change is established.**

The exact frozen guest source is
`firstboot-counter/guard-revision/inspect_ios26_firstboot_guest.py`, SHA-256
`ada26de8ababb11bb4af20e558708545eb64fd516481359fd5d0ccf6a7cbae2b`.
Its `volume_headers()` applies this predicate to each header:

```python
attributes & (1 << 13) and not attributes & (1 << 11)
```

The checks visit current primary, current alternate, baseline primary and
baseline alternate, stopping at the first failure. Each visited header first
requires HFSX signature/version and exact 4,096-byte allocation geometry. Its
attribute check precedes JIB bounds and the comparison between the two header
geometries. The generic error does not identify the failing copy or distinguish
an absent journal bit from a set boot-consistency bit. It does not establish
that the later comparisons or either journal parser ran. `Data` is after
`iOSRoot` in the inspection loop.

## Apple definitions and their limits

| Bit | Mask | Apple symbol | Relevant meaning |
| --- | --- | --- | --- |
| 8 | `0x00000100` | `kHFSVolumeUnmountedBit` | Clean-unmount marker |
| 11 | `0x00000800` | `kHFSBootVolumeInconsistentBit` | Legacy boot-volume consistency marker |
| 13 | `0x00002000` | `kHFSVolumeJournaledBit` | Journal present |
| 14 | `0x00004000` | `kHFSVolumeInconsistentBit` | Serious runtime inconsistency marker in current public source |

[Apple TN1150](https://developer.apple.com/library/archive/technotes/tn/tn1150.html),
sections **Volume Header**, **Volume Attributes** and **Journal**, describes
bit 11 as the inverted boot-volume counterpart to bit 8: its set state calls
for consistency checking. A dirty marker alone does not prove structural
damage. The archived 2004 note treats bit 14 as reserved; current
[Apple `hfs_format.h`](https://github.com/apple-oss-distributions/hfs/blob/main/core/hfs_format.h)
assigns the separate runtime-inconsistency definition above. The frozen
predicate checks bit 11, **not bit 14**.

TN1150 places the two headers at volume-relative offsets `1024` and
`volume_size - 1024`. It specifies alternate-header updates when a special
file's length or location changes. Thus a whole-header difference is not, by
itself, a corruption diagnosis. A JIB pointer is meaningful only when the
journal bit is set.

These sources were checked on 2026-11-22. The public header defines the
on-disk vocabulary; it is **not proof that this checkout is the exact HFS
implementation in the actual iOS kernel**. The current public source URL is
also a moving branch. No inference here establishes which kernel path changed
any observed field.

## Narrow read-only diagnosis

Read exactly one 512-byte sector for each combination of current/baseline,
`iOSRoot`/`Data`, and primary/alternate. Bind each extraction to the exact
read-only qcow2 input/backing chain, volume extent, logical sector, fresh
output path, length and SHA-256. The separately prepared native `qemu-img`
capability probe must establish exact skip/count behavior before these reads.

Decode big-endian fields without changing the bytes:

- Signature/version at offsets 0/2; attributes at 4, in hex and decimal.
- Last-mounted version at 8; JIB block at 12.
- Allocation block size/total/free blocks at 40/44/48; write count at 68.
- The volume-ID bytes at 104–111, which the frozen comparator hashes.
- Separate booleans for bits 8, 11, 13 and 14; retain the full attribute word.

Label every row explicitly. Compare journal presence, both inconsistency
markers, geometry, JIB location, volume ID and other changed fields separately.
The frozen primary/alternate comparator covers block size, total blocks, JIB
block and volume-ID digest; it does not require all 512 bytes to match.
Do not follow an unclassified/reserved JIB pointer merely because its numeric
value looks plausible.

## Decisions depend on the actual bytes

| Observed pattern | Interpretation and possible next step |
| --- | --- |
| Current and baseline both lack bit 13 | A nonjournaled layout may be outside the intentionally narrow inspector's supported scope. This alone would not show firstboot damaged the volume. A separately reviewed nonjournaled classification would need its own geometry/provenance and complete read-only filesystem checks. |
| Baseline has bit 13; current does not | Establish the actual state transition and provenance. A header-bit edit would not establish valid journal structures or explain why the state changed. |
| Bit 11 is set | Preserve the dirty-boot indication and investigate consistency. Do not relabel it as modern bit 14 or dismiss it merely because its protocol is old. |
| Bit 14 is set | Current public Apple semantics identify a distinct runtime inconsistency indication. The frozen bit-11 predicate would not catch it by itself. Keep the boundary refused pending appropriate diagnosis. |
| Only alternate attributes differ | Classify the differing fields against baseline and the alternate-update rules. Staleness is a possibility, not an established explanation or permission to ignore geometry/journal contradictions. |
| All relevant header predicates now pass | Reconcile the exact input chain, offsets, labels, raw bytes and frozen reader provenance with the recorded failure before proposing a source change. |

A proven unsupported-layout assumption may call for a new, separately reviewed
classifier with stronger diagnostic labels. Proven inconsistent metadata may
call for a separate repair experiment on a fresh derivative. Neither action
is selected or released here. Existing failed inspection evidence, original
headers, frozen sources and acceptance decisions remain unchanged.

One local provenance distinction matters before selecting such a route:
`audit_ios26_partition_guest.py` calls `classify_data_journal()` from
`compare_data()`. That Data-specific authored-journal classification does not
by itself establish that `iOSRoot` was journaled. If the actual current and
baseline root headers both prove a supported nonjournaled state, a possible
strict follow-up would require the **entire current iOSRoot partition** to be
byte-identical to its baseline and require a clean read-only fsck result,
while retaining the existing strict Data journal checks. Such a route would
need a new explicit classifier and independent review; it would neither
fabricate a journal header nor replay or alter the saved input. No such
implementation or release has been made.
