# Read-only audit of the iOS 26 apps-copy step

`audit_ios26_apps.py` checks the exact completed `ios26-apps` boundary before
GPU installation or the wallpaper boot. It compares the original OS image's
staged system apps with the new apps disk and its immutable activation
predecessor. The result is **`APP_COPY_AUDIT_PASSED`** only after the source,
copy, journal, filesystem, native-execution, cleanup and final-identity gates
all pass.

This is a separate audit. It does not execute another preparation stage or
modify the frozen runner, setup scripts, checkpoints or input disks. Default
invocation performs read-only preflight; `--execute` starts its one owned,
bounded native Linux helper on the phone. It is not an application launch,
migration, UI, GPU, or final cold-boot qualification.

## Why the copy needs a separate check

The pinned `apply-apps.sh` loops over non-dot `*.app` entries in the original
OS image's `private/var/staged_system_apps`. It skips exactly
`AppleVisionProApp.app` and `Image Playground.app`, and then skips any
destination for which `[ -e ]` succeeds. Every remaining bundle gets a separate
`cp -a` invocation. The script then applies recursive owner `0:0`, top-level
bundle owner `0:80`, and `chmod 775` on that top-level directory.

Copy errors are suppressed or sent through `grep | head`. The surrounding
`m2-peek.sh` runs its command without `-e` and does not preserve that command's
exit status through its cleanup. A successful preparation checkpoint alone
therefore does not prove that every bundle copied completely.

The other apps-step operations patch dyld caches, restore launchd entries,
move SystemAppMigrator, rename LaunchServices caches, and adjust Data
preferences. They do not explicitly write under `/Applications`. The initial
root builder also makes cryptex/root hardlinks, so the auditor still compares
every preexisting Applications entry against the activation predecessor to
detect unexpected changes through aliases.

The scope does not validate these other modifications. In particular,
`APP_COPY_AUDIT_PASSED` does not establish that `LastSystemVersion` was removed,
that the migration marker is fresh, or that the later wallpaper milestone
means the UI is ready.

## Exact three-view comparison

The guest reads:

1. Original `os/094-97246-090.dmg`, from the immutable decrypt checkpoint.
2. `/Applications` on `root26-activation.qcow2`.
3. `/Applications` on `root26-apps.qcow2`.

Each root must expose a regular no-follow system-version plist declaring
build `23G90` and version `26.6.2`. The selected plist path, length and complete
SHA-256 must match across all three views. Its values or contents are not
returned; only the fixed required identity and digest are reported.

The expected destination is the complete predecessor tree plus every eligible
source bundle whose exact name was absent from that predecessor. Existing
bundles are checked against the predecessor, not credited as newly copied or
as matching the staged source.

| Entry class | Required identity |
|---|---|
| New bundle root | Real directory, UID:GID `0:80`, mode `0775` |
| New descendant directory or file | Exact source type and mode, UID:GID `0:0` |
| New regular file | Exact logical length and complete streamed SHA-256 |
| New symbolic link | Exact link text and expected owner/mode; never follow its target |
| Preexisting entry | Exact path, type, owner/mode and content or symlink text, against the activation predecessor |
| Explicitly skipped source bundle | No addition; preserve it if it already existed |
| Applications parent | Same type/owner/mode, with exactly the expected resulting child tree |

Every missing or unexplained destination entry fails. Staged-root entries must
be ordinary directories with supported, non-dot `.app` names; a leading `-`,
unexpected root entry, top-level symlink, dangling destination, special file,
unsupported path or excessive traversal fails for classification. Nested
symlink text may be absolute or contain `..`; it is compared as data and is
never used to traverse or hash a referent. Every parent component is opened
with a directory descriptor and `O_NOFOLLOW`.

### Link relationships and unsupported states

`cp -a` runs separately for each bundle. Expected regular-file hardlink groups
therefore have an invocation tag: one tag for the complete preexisting
Applications tree, and one distinct tag for each new bundle. The auditor
compares those combined expected groups with the complete destination
relationship set. This preserves required links within a bundle while also
rejecting accidental aliases between independently copied bundles or between
new and preexisting files. Equal bytes do not excuse a broken or extra link.

Global `st_nlink` values are not compared across views: source or predecessor
files can have links outside the compared tree, and separate copy invocations
split source links that span bundles. All three inventories explicitly refuse
hardlinked symlinks and repeated directory `(device, inode)` identities. Those
states are unsupported rather than silently omitted from a relationship
claim. Ordinary directory/global link counts are not treated as copy identity.

New source entries with set-ID bits are also refused. Recursive `chown` can
clear regular-file set-ID bits, while a numeric directory `chmod 775` can
preserve its set-ID bits; the audit does not guess a normalization. It checks
ordinary modes exactly after the two specified bundle-root transformations.

The proof covers visible paths, types, logical bytes, owner/mode and regular
hardlink relationships. It does not establish timestamps, ACLs, xattrs,
resource-fork attributes, code-signing acceptance or application launchability.
If all eligible names already existed, a pass reports `new_copy_exercised:
false`; it proves predecessor preservation without granting new-copy credit.

## Earlier evidence remains bound to its own boundary

The host requires exactly the checkpoint prefix through `ios26-apps` and no
GPU, wallpaper, locale or pack checkpoint. It validates the earlier successful
guard and saved-firstboot inspection against their original prefixes:

- The partition audit remains bound to the partition disk and prefix.
- The firstboot guard remains bound to its actual firstboot attempt, shell
  sync, ordered QMP observations and accepted firstboot checkpoint.
- The saved-firstboot inspection remains bound to that immutable firstboot
  disk, its partition predecessor, its raw journal findings and complete
  read-only fsck diagnostics.
- Persona, activation and apps must extend that same unchanged prefix.

The later audit does not call the earlier inspector's whole preflight, which
correctly requires the earlier exact boundary. It reconstructs the earlier
prefix explicitly and uses the reviewed pure acceptance functions. The older
auditor host/guest pair, guard, inspector pair, policy, launch, supervision,
raw outputs and receipt files are all included in the before/after binding.
An earlier failed result cannot acquire credit merely because its checkpoint
exists. The firstboot proof is not represented as an audit of later writes.

The actual apps backing chain must be exactly:

`apps -> activation -> persona -> guarded firstboot -> audited partition`

Every disk path must be distinct and inside the owned preparation session.
The actual header-derived chain must match each original full artifact record.
Every member and the original OS image are fully hashed before and after the
audit. Earlier versions of the logical `root26g.qcow2` name are recovered from
their own stage records; the persona result cannot stand in for firstboot.

## Read-only helper and journal checks

All three input drives are attached with `readonly=on`. The guest independently
checks their block-device identities, sizes and read-only flags. Only the
bounded metadata output disk is writable. Both partitioned inputs must have
the exact checked GPT geometry and unchanged primary/backup GPT data.

Before either HFS mount, each P1 journal is discovered from its actual volume
headers and JIB, checked for bounds/metadata overlap, and compared with the
approved saved-firstboot P1 journal identity:

- An initialized journal must still have the exact approved empty header,
  valid endian/magic/checksum and normalized equal cursors.
- Flags `5` require the exact authored JIB and the complete zero journal,
  still matching the earlier approved journal. The result is named
  `AUTHORED_UNINITIALIZED_JOURNAL_PRESERVED`. Later Linux volume-header
  allocation/counter updates are allowed; no unchanged-whole-volume claim is
  made.

The primary volume header must indicate clean unmount. Both P1 views then
receive full, unmounted `fsck.hfsplus -f -n` checks. Each unfiltered diagnostic
must satisfy the existing strict clean verdict. There is no repair or replay.

HFS mounts use `ro,nosuid,nodev,noexec`. The original OS is presented through
an owned `.dmg` link to its read-only input device, following the proven
`m2-peek.sh`/`mk-root26.sh` input shape. APFS-FUSE receives exactly:

```text
apfs-fuse -o ro,nosuid,nodev,noexec,allow_other OWNED/source.dmg OWNED/os
```

The pinned tool's `-f` selects a secondary Fusion-drive device; it is not a
foreground option. Its `-l` permits potentially corrupt fallback data. Neither
option is enabled, and there are no UID/GID, snapshot, transaction or volume
overrides. The mount witness must show the requested read-only restrictions
and the expected `fuse[.apfs-fuse]` / `apfs-fuse` identity. An unsupported
observed mount shape fails closed for review; host tests do not claim physical
APFS mount validation.

Mount directories and the temporary `.dmg` link exist only inside this owned
helper. Cleanup attempts every created mount and loop, including after a
failure; any cleanup failure prevents a pass. The original native helper
launcher/supervisor supplies the native-required contract, fresh memory gate,
timeout, logs, natural exit and descendant reaping. No TCG retry is introduced.

## Invocation and bounds

Use the actual passed inspection directory and a fresh short output path.
Illustrative phone paths:

```sh
python3 -B /data/local/tmp/apps-audit-src/audit_ios26_apps.py \
  --inspection-work /data/local/tmp/firstboot-inspection \
  --work /data/local/tmp/apps-audit-01
```

Add `--execute` only for the separately authorized physical audit. Preflight
starts no helper and creates no output directory. Execution holds the original
nonwriting owner lock, refuses live preparation children, and creates only
the fresh audit directory. Later stages must wait for the audit result.

The default helper deadline is 7,200 seconds, configurable from 60 to 14,400.
Each filesystem check has a 1,200-second deadline and 4 MiB diagnostic limit;
APFS diagnostics have the same size limit. Host logs are capped at 64 MiB.
The usual 2,048 MiB helper requires fresh `MemAvailable >= 2,816 MiB`, with
the frozen running floor of 512 MiB and at least 1,536 MiB free storage.
No firstboot or final cold-boot memory gate is relaxed.

The implementation retains all three bounded inventories. They share a
**500,000-entry and 128 MiB encoded-path budget**; this is not a claim of
per-bundle streaming inventories or a measured Python heap peak. Each tree
also has a 32 GiB unique regular-file logical-byte limit, depth limit 128,
4,096-byte path limit and 1,024-byte component limit. Source roots are limited
to 512 bundle names. File contents are streamed in 1 MiB chunks and hashes are
cached per inode/view. At most 128 comparison errors are returned. The helper
RAM and execution bounds still apply if filesystem caches or Python metadata
exceed expectations.

## Receipt and downstream consumption

The host writes `apps-audit-session.json`, `result.json`, and an owned `a1/`
attempt with launch, supervision, expected policy and collection records.
The exact regular output set is:

```text
apps-audit/result.json
apps-audit/fsck-activation.txt
apps-audit/fsck-apps.txt
apps-audit/apfs-mount.txt
```

The APFS diagnostic has a fixed authored header even if the mount emits no
messages. Reports contain names, numeric metadata, digests, counts and
verdicts. They export no application content, plist values, certificates or
image bytes. Diagnostics may contain filesystem paths or structural errors.

A successful top-level result has `status: APP_COPY_AUDIT_PASSED`,
`apps_audit_session_sha256`, exact `outputs`, `guest_result`, positive native
witnesses, `natural_exit: true`, clean/reaped cleanup, and both
`full_input_chains_unchanged` and `preparation_and_prior_evidence_unchanged`.
The guest result must independently match its fresh nonce/policy hash, all
three system-version identities, both filesystem/journal verdicts, read-only
mount witnesses and the complete application comparison. Every failure is
`INCOMPLETE` with host exit status 2; preflight readiness is not an audit pass.

Later wallpaper/final-boot tools must verify the committed auditor source
hashes, session/result copies, actual launch/supervision, fresh expected policy
and exact raw output records before consuming this result. They must rebuild
the original through-apps prefix from the later checkpoint chain, not call
this tool's whole exact-boundary preflight or pretend this audit covered GPU
or later writes. The pure helpers `prefix_inventory`, `saved_inspection`,
`full_inputs`, `require_native` and `guest_pass` support that source-bound
validation; they do not replace the caller's own later-boundary checks.

## Pinned source and utility provenance

The reviewed helper initrd is SHA-256
`7dff81e88f5e6261ae206c6c481f53748374d76ebd433be7b263f34c571a4a24`.
Offline inspection of its exact members establishes:

| Member | Bytes | SHA-256 |
|---|---:|---|
| `usr/local/bin/apfs-fuse` | 738,768 | `ad16c03296347d4556a3f50874da226a9069b256fd0c70347d855f99737a94a7` |
| `usr/bin/cp` | 133,496 | `1b9b90064637c58fda2b6bb3940ae67d6eac6bea94c21a694f341feca8f24f49` |
| `usr/bin/chown` | 67,944 | `9f2b9d580c8bfe80a3e3eb5bc621161d555067e2610b917b99219c33b3eb613b` |

The byte-identical setup script members come from the pinned released tooling
APK documented in [preparation-tools.json](host-checks/preparation-tools.json).
The app-audit host pins the nine exact relevant job/step/script hashes in
`SCRIPT_SHA256`, including `apply-apps.sh` and `m2-peek.sh`; the existing full
tooling manifest check remains mandatory. Earlier source dependencies are
also pinned in `APPROVED`. HFS utility/source provenance and journal rules are
documented in [IOS26-PARTITION-AUDIT.md](IOS26-PARTITION-AUDIT.md) and
[IOS26-SAVED-FIRSTBOOT-INSPECTION.md](IOS26-SAVED-FIRSTBOOT-INSPECTION.md).

## Focused host validation

```sh
python3 -B -m unittest test_audit_ios26_apps
```

Authored fixtures exercise full byte comparison despite unchanged size/time,
new/preexisting ownership and modes, exact skipped-name handling, no-follow
paths, set-ID/special-file refusals, regular hardlink preservation and
invocation splitting, accidental cross-bundle/preexisting aliases, linked
symlinks and directory aliases, system-version types/digests, journal changes,
read-only mount and cleanup failure paths, exact checkpoint prefixes, full
backing-file mutation beyond the fast witness, earlier evidence/source
changes, actual cleanup list shape, native/VM failures, and real safe-tar
collection. Filesystem utility and VM calls are mocked. These tests perform
no mount, VM, phone operation, network access or Apple-image processing.
