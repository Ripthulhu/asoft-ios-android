# Saved-inspection revision: preexisting iOSRoot alternate marker

## Observed cause

The bounded read-only diagnostic completed at `2026-11-22T16:39:46.597544+00:00`.
All eight primary/alternate headers are journaled. The original nonjournaled-root
hypothesis is ruled out. The actual rejected field is **bit 11 in the iOSRoot
alternate header**, already present in the accepted partition predecessor.

| Volume/copy | Saved attributes | Baseline attributes | Bit 11 | Bit 14 |
| --- | --- | --- | --- | --- |
| iOSRoot primary | `0x80002100` | `0x80002100` | Clear | Clear |
| iOSRoot alternate | `0x80002800` | `0x80002800` | Set | Clear |
| Data primary | `0x80002000` | `0x80002100` | Clear | Clear |
| Data alternate | `0x80002100` | `0x80002100` | Clear | Clear |

Corresponding saved/baseline iOSRoot header SHA-256 values were visually
confirmed equal by the independent reviewer. This is header evidence, not a
filesystem-health verdict or equality of the entire root partition. The raw
phone diagnostic result is 14,542 bytes, SHA-256
`d768516e7cc9846e35aefa5f7583797b4cc0c129402a16994965501c69882ba6`.
The retained selected observation and its independent review are
`../resume2-saved-inspection/header-diagnostic/physical-observations/headers-observed-163946.json`
and `../resume2-saved-inspection/header-diagnostic/independent-header-result-evidence-review.json`.
Raw phone receipts and raw volume-header bytes were not downloaded.

## Source-supported distinction

[Apple TN1150, Volume Header](https://developer.apple.com/library/archive/technotes/tn/tn1150.html)
describes alternate-header updates when special-file locations or lengths
change. It does not require every primary attribute update to be copied to the
alternate. Bit 11 is the legacy boot-consistency marker; current public Apple
source defines bit 14 separately as runtime inconsistency.

At Apple HFS commit `d1bac2f062e6e9c0dfcce302d9aacb10173d0eea`:

- [`core/hfs_vfsops.c`](https://github.com/apple-oss-distributions/hfs/blob/d1bac2f062e6e9c0dfcce302d9aacb10173d0eea/core/hfs_vfsops.c),
  Git blob `c7ff05f8dfc94610b3b490f37ca7cd705982e75d`, updates primary
  attributes and copies the header to the alternate only when `altflush` is
  requested. Its ordinary unmount clean-bit path calls the volume-header flush
  with `HFS_FVH_WAIT`; special-file modifications can independently request
  alternate flushing.
- [`lib_fsck_hfs/dfalib/SVerify1.c`](https://github.com/apple-oss-distributions/hfs/blob/d1bac2f062e6e9c0dfcce302d9aacb10173d0eea/lib_fsck_hfs/dfalib/SVerify1.c),
  Git blob `12940258bf1a5dc94a52ed7db4eeba7ec4983824`, uses the primary
  volume header's attributes in its HFS Plus volume-information path. That
  path explicitly records removal of an HFS Plus volume-attribute comparison.

These are public format/implementation evidence, not proof of the exact code
in the running iOS kernel. The repository's already-passed partition auditor
also requires journal bit 13 in both Data headers while applying clean bit 8
and boot bit 11 only to the primary. Its earlier accepted audit recorded both
independent filesystem checks passing; see
`../audit-owner/execution-observation-113842.json`.

## Narrow revised classifier

The canonical host and guest now distinguish strict journaled headers from
`BASELINE_IDENTICAL_ROOT_ALTERNATE_BOOT_MARKER`. The latter requires all of:

1. Exact iOSRoot name and fixed partition extent: offset 1,048,576 bytes,
   size 34,359,738,368 bytes. Data cannot enter this path.
2. The complete saved primary and alternate 512-byte headers equal their
   corresponding baseline bytes, not just attribute masks. Both copies retain
   the existing signature, geometry, volume-ID and valid JIB-location checks.
3. A clean, journaled primary with bits 11 and 14 clear; a journaled alternate
   with the preexisting bit 11 and no bit 14. Newly added, removed or otherwise
   changed markers do not qualify.
4. Exact current/baseline JIB bytes. For initialized journals, both headers are
   independently parsed with the existing checksum, endian, range and empty
   cursor rules, then the full 512-byte journal headers must be identical.
   For NeedInit journals, the exact authored JIB and complete all-zero 8 MiB
   journal regions in both images remain mandatory.
5. Both existing forced read-only filesystem checks pass, with complete logs
   revalidated by the host. GPT and the complete raw classification are checked
   again afterward. Existing full backing-chain preservation, native execution,
   clean process cleanup, no-mount/no-replay/no-repair and success-receipt gates
   remain required.

The host validates the exact new proof schema, scalar types, masks, geometry,
header/JIB digests and independently validated matching journal metadata. A
success label, a false equality boolean, missing fields, or relabeling the
special case as strict does not suffice.

**Additional tightening:** bit 14 now explicitly refuses every header in both
volumes, including the strict path. Data otherwise retains its prior journal
and bit-11 rules, including classification of an initialized empty journal
when its primary clean-unmount bit is clear. No automatic 32 GiB root scan is
added: it is unnecessary to resolve the narrowly evidenced alternate-update
assumption, and would not replace raw-journal or independent filesystem checks.

The two existing journal states are unchanged. In particular, this revision
does not introduce a nonjournaled state, reset flags, repair headers or accept
any earlier failed inspection. Any new inspection must observe and satisfy
all current gates afresh.

## Validation and preservation

`validation.json` records exact canonical source hashes, frozen-original hashes,
the source snapshot/diff and the focused offline test result. Tests exercise
new/changed markers, primary inconsistency/unclean state, all eight runtime-bit
locations, altered header/JIB/journal bytes, independent baseline parser
failures, Data misuse, incomplete host proof, both required fscks and the
post-fsck recheck. They use synthetic sparse byte ranges and no Apple disk data.

The original executed counter1 inspector and tests under
`../firstboot-counter/guard-revision/` remain unchanged. This source revision
does not itself stage files on the phone, start a VM or publish a commit. New
runtime bindings and independent review are owned by the separate resume3
saved-inspection package.
