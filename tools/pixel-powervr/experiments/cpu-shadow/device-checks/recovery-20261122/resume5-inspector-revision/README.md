# Resume5: classify an exact authored root-journal initialization

The canonical host and guest sources are frozen after 60 focused tests passed.
This directory contains exact source/test snapshots, the complete patch against
the preserved resume3 revision, and the captured test report. Independent source
review and a fresh physical inspection are separate steps. No resume5 inspection
result, journal-emptiness verdict, or filesystem verdict is claimed here.

## Observed reason for the change

The actual resume4 inspector stopped at `root_baseline_jib_changed`, before
either filesystem check. Its native helper completed cleanly and preserved the
backing chain. A separate, reviewed diagnostic then read both complete 4,096-byte
root Journal Information Blocks through sixteen bounded 512-byte reads.

The independently reviewed [bound metadata selection](../resume4-saved-inspection/jib-diagnostic/physical-observations/metadata-selected.json)
records the summary at 2026-11-22T20:21:20.762494+00:00 and its only difference
range at 20:21:32.934758+00:00. The actual diagnostic result is 14,246 bytes,
SHA-256 `5d39c9a0fb16c794577abaf4ab7155ee5f352d46cb7027e03b571055f10d5061`.

| Property | Authored baseline | Saved firstboot |
| --- | --- | --- |
| JIB flags | `5` (`0x00000005`) | `1` (`0x00000001`) |
| Complete JIB SHA-256 | `65f57e6fad390f4a87dafbc97c23ded9a66a416d6600350dd5eeb34ebc2632eb` | `e50b1697e64b81794bc984642dc652d40bd7041818f7299f71a118300f8289a9` |
| JIB allocation block | 257 | 257 |
| JIB absolute virtual offset | 2,101,248 | 2,101,248 |
| Journal volume-relative offset | 1,056,768 | 1,056,768 |
| Journal size | 8,388,608 | 8,388,608 |

Exactly one JIB byte differs: the half-open interval `[3, 4)`. Both complete
hashes also match the deterministic formatter layout, with only the flags word
changed from 5 to 1. The diagnostic did not follow the journal pointer or assess
journal state. Its preservation checks and clean owned-child completion do not
replace those remaining checks.

## Primary-source rationale

[Apple TN1150, Journal Info Block and Journal Header](https://developer.apple.com/library/archive/technotes/tn/tn1150.html)
defines `0x1` as an in-volume journal and `0x4` as NeedInit. It describes clearing
NeedInit during initial journal-header initialization and separately defines an
empty initialized journal by equal start/end cursors. These are separate facts:
the observed flags alone cannot establish a valid empty current journal.

Pinned Apple source corroborates the transition:

- [HFS `hfs_format.h`, lines 802–817](https://github.com/apple-oss-distributions/hfs/blob/d1bac2f062e6e9c0dfcce302d9aacb10173d0eea/core/hfs_format.h#L802-L817)
  defines the structure and masks. Git blob: `cda1efe48bd157f389368b78f6d5313113687547`.
- [HFS `hfs_vfsutils.c`, lines 2599–2618](https://github.com/apple-oss-distributions/hfs/blob/d1bac2f062e6e9c0dfcce302d9aacb10173d0eea/core/hfs_vfsutils.c#L2599-L2618)
  invokes journal creation and clears NeedInit in the stored JIB. Git blob:
  `bac1a8034bfe7d1100cbdd7ab48e65f284d0e637`.
- [HFS `hfs_journal.c`, lines 1825–1855](https://github.com/apple-oss-distributions/hfs/blob/d1bac2f062e6e9c0dfcce302d9aacb10173d0eea/core/hfs_journal.c#L1825-L1855)
  initializes the journal header's magic, endian marker, equal cursors and size,
  then writes the header. Git blob: `fefbf640f97030be63048e471916bff00a4a024f`.
- [XNU `hfs_vfsutils.c`, lines 2697–2716](https://github.com/apple-oss-distributions/xnu/blob/0f3703ac1dbc5486bdb2da031e69dcafe463e2f0/bsd/hfs/hfs_vfsutils.c#L2697-L2716)
  contains the same create-and-clear sequence. The official tag
  `xnu-3247.1.106` resolves to that commit; the file blob is
  `1015fbd914685864c446bc2e900dc860890e05d3`.

These sources establish format and implementation semantics. They do not
identify the exact running guest kernel or establish the outcome of a future
inspection.

## Separate, strict proof

The existing `BASELINE_IDENTICAL_ROOT_ALTERNATE_BOOT_MARKER` path remains intact.
The new `ROOT_AUTHORED_NEEDINIT_TO_INITIALIZED_EMPTY` classification is available
only for the exact iOSRoot partition with the preexisting alternate boot marker.
It requires all of the following in the same read-only inspection:

1. Identical corresponding complete saved/baseline volume headers and geometry;
   a clean root primary; journaled headers; no runtime-inconsistent bit; and all
   existing discovery, range and metadata-overlap checks.
2. A baseline JIB identical to the complete expected formatter-authored block,
   including every reserved and padding byte, and flags exactly 5.
3. A current JIB identical to that complete expected block with only the
   big-endian flags word changed to 1. Relocation, resizing, extra bits, reverse
   transitions and every other JIB byte change are refused.
4. Every byte of the complete baseline 8 MiB journal region is zero, using the
   unchanged bounded `zero_region()` implementation.
5. The current journal passes the unchanged `initialized_header()` parser:
   endian and magic, size, checksum, supported header/block-list sizes, bounded
   aligned cursors, and `start == end`. Existing inactive-payload semantics are
   unchanged; current inactive bytes are not misrepresented as examined.

The proof explicitly reports `baseline_jib_identical=false` and
`baseline_journal_metadata_identical=false`. It carries separate
`AUTHORED_NEEDINIT_ZERO` baseline evidence, `INITIALIZED_EMPTY` current evidence,
and the exact flag-clear description. The host independently reconstructs both
expected complete JIB hashes and requires exact proof keys, value types,
partition scope, flags, offsets, sizes and the complete zero-journal digest.

Both raw volume checks still precede both forced read-only `fsck.hfsplus -f -n`
checks. Both logs and verdicts remain mandatory. The full raw classification is
repeated after the filesystem checks; host log revalidation, native execution,
clean process ownership, resource floors and whole-chain preservation remain
unchanged. No mount, replay, repair, boot-completion or GPU-completion claim was
added. Data retains its existing classification and checks.

## Focused verification and release boundary

The suite contains the 45 existing tests plus 15 new tests, with subcases for
both endians, exact observed JIB hashes, other-byte/flag/direction/location
mutations, baseline bytes throughout the 8 MiB region, invalid/nonempty current
headers, root scope, missing or forged host proof fields, each filesystem check,
cleanup, missing logs and changes after filesystem checks. One existing refusal
test now expects the more precise zero-baseline rejection when a NeedInit flag
is forged over an initialized baseline journal; the case remains refused.

Run from `tools/pixel-powervr/experiments/cpu-shadow`:

```sh
python -B -m unittest test_inspect_ios26_firstboot -v
```

[validation.json](validation.json) binds the exact canonical snapshots,
[focused-tests.log](focused-tests.log), reviewed actual diagnostic evidence and
source references. Production AST comparison changes only guest
`inspect_volume()` and one class-name constant, plus host dispatch to the new
`root_initialization_proof()` validator. Other production functions are
unchanged. Tests use synthetic sparse data and mocked filesystem utilities;
they execute no VM, mount, repair or real filesystem check.

Fresh installation is intended for `/data/local/tmp/pixel-saved-checks-resume5`.
Historical installed sources and receipts are preserved. A new physical
preflight and inspection must supply their own actual evidence before any
success claim or downstream continuation.
