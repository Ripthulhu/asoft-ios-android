# Saved-wallpaper inspection before locale

`inspect_ios26_wallpaper.py` is a separate read-only gate after the guarded
wallpaper boot and before `ios26-locale`. It writes only a fresh inspection
directory. It does not modify the frozen preparation runner, original session,
guard, earlier audit sources, checkpoints, or input disks.

The current preparation boundary must be exactly completed wallpaper, with a
successful `GUARDED_WALLPAPER_COMPLETE` receipt from the approved wallpaper
guard. The inspector revalidates the earlier app, firstboot, and partition
proofs at their original prefixes. A failed guard cannot be replaced by an
otherwise successful original wallpaper checkpoint.

## Invocation

Install the new host and guest source pair in a separate directory. Keep the
successful wallpaper guard and all its bound source/evidence paths available.
Default planning is read-only:

```sh
python3 -B /data/local/tmp/pixel-wallpaper-inspector/inspect_ios26_wallpaper.py \
  --guard-work /data/local/tmp/pixel-wallpaper-guard-e9cc754 \
  --work /data/local/tmp/pixel-wallpaper-check-e9cc754
```

After a reviewed `PREFLIGHT_READY`, repeat with `--execute`. The fresh output
path must have an existing parent, be at most 55 characters, and sit outside
every preparation/input/source/evidence tree.

The original preparation owner lock is acquired without rewriting its contents.
The verified frozen helper launcher and supervisor are reused, with the
session's 16 KiB Linux kernel, helper RAM/CPU settings, required native
execution, and no TCG retry. A 2048 MiB helper still requires at least 2816 MiB
of fresh available memory; its running floor remains 512 MiB. Default audit
deadline is 7200 seconds, with bounded logs and a 16 MiB output disk. The only
writable VM disk is this audit's owned output disk; both saved
wallpaper and immediate GPU predecessor are attached `readonly=on`.

## Fresh raw inspection, fixed implementation

The new guest adapter runs the existing reviewed raw inspection implementation
against these two current input disks. It hashes both dependencies before
execution:

| Dependency | SHA-256 |
| --- | --- |
| `inspect_ios26_firstboot_guest.py` | `ada26de8ababb11bb4af20e558708545eb64fd516481359fd5d0ccf6a7cbae2b` |
| `audit_ios26_partition_guest.py` | `6874b9b6b68c7fb50c3f9cf05c1b6a86a53f8fed75863c00a6ad9254b1640593` |

This is a new inspection, not reuse of an old disk result. The adapter records
both the raw implementation's original kind/status and the fresh wallpaper
context in `raw_implementation`; errors and numeric classification metadata
are retained. No earlier source or result is rewritten.

The raw implementation verifies:

- Exact 51,541,704,704-byte GPT geometry, both headers and entry-array CRCs,
  reciprocal header locations, and the fixed 32 GiB System / 16 GiB Data layout.
- Primary and alternate HFS volume headers, allocation geometry, and direct
  volume-header-to-JIB discovery for both volumes. Journal discovery does not
  depend on mounting or filenames.
- For initialized journals: consistent magic/endianness, the supported 512-byte
  header, header checksum, representable/aligned block-header size, and bounded
  empty cursors (`start == end`). Inactive old journal payload is not required
  to be zero.
- For an untouched `NeedInit=5` journal: the exact authored layout, JIB bytes
  and padding, zero journal region, and unchanged raw volume headers/JIB/journal
  against the separately attached immutable GPU predecessor. A zero header
  alone never grants an exemption.
- Both raw journal gates before either unmounted read-only loop view runs
  unfiltered `fsck.hfsplus -f -n`. Both checks must exit zero, include all
  required phases and the positive clean summary, and contain no skipped,
  incomplete, repair/replay, corruption, or journal-read diagnostic.

No mount, replay, repair, or input write is permitted. Detachment is attempted
for every recorded loop view; cleanup failures prevent acceptance. The complete raw checks
are repeated after filesystem checking.

The supported cursor range is strictly below journal size. A cursor equal to
the size is classified as an unsupported state, not asserted to be corrupt.
Nonempty, unknown, and unsupported journals remain `INCOMPLETE` with numeric
metadata. The accepted rules and checksum derive from the existing reviewed
implementation and Apple's [TN1150 journal description](https://developer.apple.com/library/archive/technotes/tn/tn1150.html).
The Linux helper's permissive journal-replay stub is not used as evidence.

## Acceptance and records

The host independently checks the guest's nonce, policy digest, dependency
identities, raw journal verdicts, and both complete filesystem logs. It requires
natural native helper completion, exact clean owned reaping
(`forced_descendants=[]`), and exactly the expected metadata files. Before and
after the run, all seven actual disk/backing files are fully hashed, together
with the original decoded OS and every bound prerequisite proof.

Success is `SAVED_WALLPAPER_INSPECTION_PASSED`. Records include
`inspection-session.json`, `result.json`, `a1/inspection-result.json`, exact
launch/VM/policy metadata, and `a1/files/inspection/` containing the guest result
and two full filesystem diagnostics. Only metadata and diagnostics are exported;
there are no mounted guest file contents, plists, certificates, or image bytes.

Any identity change, native/cleanup failure, missing output, or unsupported
filesystem state leaves the outcome `INCOMPLETE`. Locale must not proceed on
that result. A passing inspection makes the saved filesystem boundary
reviewable; it is not final cold-boot, GPU-path, UI, or application qualification.

## Offline verification

```sh
python3 -B -m unittest -v test_inspect_ios26_wallpaper
```

Focused tests cover source pinning and adapter context, preservation of
incomplete classifications, actual bounded tar collection, both read-only
attachments, native cleanup shape, changed input and missing evidence refusal,
and exclusive ownership. The reused journal/fsck algorithm retains its earlier
source-derived tests. These tests perform no guest, mount, or phone operation.
