# Final cold observation: memory and preparation provenance

`guard_ios26_coldboot.py` is a separate wrapper for the existing
[`cold_boot_ios26.py`](cold_boot_ios26.py) owner. Its default is a read-only
preflight. `--boot` explicitly starts one bounded cold observation after the
complete `ios26-pack` boundary and every required earlier proof have been
validated. This source and its authored host tests do **not** record a physical
iOS boot, a usable UI, or complete GPU/product qualification.

The wrapper retains the original command, process ownership, supervision loop,
frame memfd, QMP stop/quit ordering, timeout behavior and descendant reaping.
It neither executes preparation stages nor modifies a frozen runner, completed
checkpoint, qualified package, earlier evidence directory or prepared input.
All writable cold state belongs to a fresh output directory.

## Mandatory preparation and evidence

The entry input is `--wallpaper-inspection-work`, naming the actual successful
saved-wallpaper inspection. Its receipts identify the preparation session,
frozen runner, qualified runtime, tooling and earlier proofs. Callers cannot
substitute another disk, trustcache, device tree, runtime or guest RAM setting.

The current preparation must have exactly all 15 completed checkpoints through
`ios26-pack`, with the unchanged session digest and previous-checkpoint hash
links. The frozen preparation preflight verifies its artifacts and qualified
17-case package, including native TPIDRRO swap and both capability cases. The
wrapper then reconstructs each earlier prefix rather than calling an earlier
tool's intentionally exact-current-boundary preflight.

| Proof | Prefix retained by its receipt | What is revalidated |
| --- | --- | --- |
| Partition audit | Through `ios26-partition` | Original audit, actual source pair, output/policy identities and immutable partition predecessor |
| Guarded first boot and saved-firstboot inspection | Through `ios26-firstboot` | Original guard acceptance, native completion, cleanup, saved journal/fsck outputs and original two-disk ancestry |
| App-copy audit | Through `ios26-apps` | The reviewed app verifier's original prefix, source pair, launch, VM result, raw comparison outputs, policy and full relevant inputs |
| Wallpaper execution guard | Through `ios26-wallpaper`, with its original through-GPU input prefix | Exact accepted checkpoint and attempt, shell-sync witness, ordered post-stop failed-I/O check, original native/GPU/frame/settling conditions and immutable inputs |
| Saved-wallpaper inspection | Through `ios26-wallpaper` | The actual seven-member disk chain, GPU predecessor, read-only native helper launch, natural completion/reap, exact source pair/dependencies, nonce/policy, raw journal metadata and both forced read-only fsck outputs |
| Final pack | Through `ios26-pack` | Exact nine packed files, prepared copy sources, standalone packed qcow2, locale overlay and every actual retained backing member |

The first four proof implementations remain the reviewed sources described in
[`IOS26-APPS-AUDIT.md`](IOS26-APPS-AUDIT.md),
[`IOS26-WALLPAPER-GUARD.md`](IOS26-WALLPAPER-GUARD.md) and
[`IOS26-WALLPAPER-INSPECTION.md`](IOS26-WALLPAPER-INSPECTION.md). A successful
historical proof is never relabelled as having inspected locale or final-pack
writes. The app-copy result does not supply an application-launch or migration
milestone. The wallpaper guard retains the original marker/settling rules and
their documented limitations.

### Exact final asset and backing contract

The packed directory is the original `14-NNNN/files/ios26` output and contains
exactly these nine ordinary files, each with one host link:

| Packed name | Prepared source or identity |
| --- | --- |
| `root26s-aod.qcow2` | Standalone compressed pack output; no backing file |
| `root26s-aod.tc` | Byte-identical `root.tc` |
| `bootkc` | Byte-identical `fw/bootkc` |
| `sptm` | Byte-identical `fw/sptm` |
| `txm` | Byte-identical `fw/txm` |
| `rd-shell.hfs` | Byte-identical `rd-shell.hfs` |
| `dtree-root26v-smp4-19m2` | Byte-identical `dtree-phone` |
| `dtree-root26v-smp4-19m2-aod` | Byte-identical `dtree-phone-aod` |
| `install.json` | Original standalone preparation identity, build `23G90`, exact session digest and false completion flags |

The actual locale chain must be eight distinct owned files, newest first:
locale, wallpaper, GPU, apps, activation, persona, first boot and partition.
Every member's qcow2 header must name the exact remaining suffix of that chain.
Both the standalone pack and retained disks must have virtual size
51,541,704,704 bytes. The original OS input required by the app proof is also
fully hashed. The copied firmware/tree/trustcache source records and their
packed counterparts must match in size and SHA-256.

The wrapper hashes complete files before execution, repeats the full hashes
after the original owner has shut down, and checks the prior proof/source files
again. These checks establish exact provenance and preserved inputs. They are
not an independent virtual-sector comparison of the compressed packed disk
against the locale predecessor, or an audit of every locale modification.

## Guest RAM comes from the verified launch tree

The wrapper fixes `ram_gib=3`, display scale 3, four vCPUs and the existing
38,400,000 Hz tree-patching contract. Immediately before the qualified QEMU
`Popen`, it reads all three tree files and requires:

1. The copied input tree is byte-identical to the bound packed AOD tree.
2. The actual launch tree is exactly `expected_tree(original, 3, 3)`.
3. Applying the same reviewed transformation again leaves those launch bytes
   unchanged.

The frozen command is unchanged. It does not contain a generic `-m` argument,
and this wrapper does not add one. That omission does not demonstrate missing
guest-RAM configuration for the qualified custom machine: at QEMU source
`755b88fad8a2771a8e3e207133a54898b740cd7f`, `hw/arm/vresearch.c` reads
`/chosen/dram-size` into `info->dram_size`; `hw/arm/xnuboot_sptm.c` calls
`alloc_ram(OBJECT(cpu), info->dram_base, info->dram_size)` and uses that size in
guest boot arguments. The existing preparation `guest_stage` also verifies its
patched tree with `expected_tree(..., 3, 3)` before supervision.

These source facts were checked from the qualified local Git objects, without
a network request or guest run. The upstream repository is
[alpersamur3/qemu-sptm](https://github.com/alpersamur3/qemu-sptm); the exact local
qualified revision and file identities are:

| Source at qualified QEMU revision | Bytes | SHA-256 |
| --- | ---: | --- |
| `hw/arm/vresearch.c` | 40,142 | `9fa5da4d5c9a51697b18ffefba81afa34693a2633b952f8f504aef05c24f2b9b` |
| `hw/arm/xnuboot_sptm.c` | 19,557 | `9042c3da5e6cbaa701c615cadee5ab2c4227e571c0dde20eeefa878890be6d6c` |

## Host-memory hooks and cleanup

Only the frozen cold module's `subprocess` reference is replaced with a proxy.
The shared Python `subprocess` module is untouched. Other tool invocations pass
through; the exact qualified QEMU invocation must match the frozen command,
environment, inherited frame descriptor and owner options.

After input/tree validation and immediately before delegating that `Popen`, a
fresh `/proc/meminfo` read must have exactly one valid `MemAvailable` line in
kernel `kB` units and at least **3,840 MiB** available. The threshold is compared
in KiB without rounding a subthreshold value upward. Missing, duplicate,
malformed, excessive or unreadable values fail. There is no configurable
exception or retry onto TCG. The real `Popen` call is the proxy's final return
expression; no fallible action occurs after it succeeds and before the frozen
caller receives the child handle.

The existing `storage_report` hook adds a **512 MiB** running floor and combines
it with the original free-space/log verdict. A memory failure is permanent for
that observation even if later samples recover. Missing/malformed/read-error
samples fail the same way as a low value. Storage-report exceptions become an
explicit failed bound, including in the original final-report call, which is
outside its main exception handler.

Sampling uses the owner's existing approximately ten-second reports, plus a
nonraising pre-shutdown sample and the final report. It is not a hard realtime
monitor: intervals can lengthen during other owner operations, and the wrapper
cannot rule out a shorter unsampled memory dip. Samples are bounded to 256;
exceeding that bound fails. The original owner calls the wrapped storage report
and therefore exits its loop normally on a latched failure.

The optional pre-shutdown sample always delegates the original shutdown,
including when the sampler itself fails. No `poll`, sleep, clock or signal
function is replaced. No supervision/cleanup loop is copied. The original
stop/frame/quit, child wait, forced fallback and descendant reap remain in
charge; forced cleanup cannot earn the original success verdict.

The original preparation owner lock is held exclusively from the full
execution recheck through the final full-input comparison and evidence writes.
A conflicting owner or live preparation child stops execution before creating
the new work directory. Full disk hashing occurs before launch or after the
original owner returns, rather than in the running sampling loop.

## Invocation and results

Use a fresh short output path outside preparation, runtime, tooling, sources
and all prior evidence trees. Preflight is read-only and can be reviewed first:

```sh
python3 -B /data/local/tmp/final-cold-src/guard_ios26_coldboot.py \
  --wallpaper-inspection-work /data/local/tmp/wallpaper-inspection \
  --work /data/local/tmp/final-cold-01
```

Execution requires adding `--boot`. Supply the actual operator-selected serial
literal through repeatable `--expect-serial` options before asking for a passing
observation. This wrapper supplies no invented guest/UI marker. As in the
original harness, an empty expected-marker list may produce a bounded
diagnostic observation but cannot produce `WITNESSES_OBSERVED`.

Default duration is 900 seconds; the allowed range remains 30–1,800 seconds.
The wrapper requires at least 1,024 MiB free-space bound and a log bound of
1–64 MiB. It fixes the guest RAM/display settings and both memory floors.

The wrapper preflight uses the fresh outer work path when asking the original
read-only preflight to validate an existing parent, then derives the equally
fresh `work/cold` path and exact unchanged command. It creates neither directory
at preflight. The nested run's socket path length is checked independently.

The new output is:

| Path under fresh work | Meaning |
| --- | --- |
| `guard-session.json` | Exact sources, checkpoint/proof prefixes, full input bindings, packed contract, original cold preflight and fixed memory policy |
| `memory-observations.json` | Ordered bounded samples, permanent failure latch, exact guarded launch/tree witness and memory verdict |
| `result.json` | Wrapper verdict plus original result/launch and memory-file hashes, completion flags and final input-recheck outcome |
| `cold/` | Original owner's overlay, copied/patched tree, logs, frame captures, launch and result, unchanged in format |

The wrapper returns `WITNESSES_OBSERVED` only when the original owner returns
that exact status, its unchanged witness function independently still accepts
the explicit markers, a guest was started, the original result/launch were
retained, memory passed and every bound input remains unchanged. Otherwise the
wrapper returns `INCOMPLETE`. The original result is preserved even when the
additional wrapper verdict fails; downstream readers must use the wrapper
result for this gate.

`boot_complete`, `gpu_path_complete` and `app_gate_changed` remain false in all
wrapper results. A frame still requires human review. The `cold/` outputs can
contain Apple-derived state or image content and are not automatically suitable
for repository export. Source files, authored tests and reviewed metadata
receipts can be retained separately without copying guest images or plist data.

## Immutable code dependencies and host validation

| Dependency | SHA-256 |
| --- | --- |
| Frozen `cold_boot_ios26.py` | `6a57ed164864eef20aeffd34b14b675a8ac597c20583c9f179414a36b4ccbdeb` |
| Frozen `cold_boot_dt.py` | `6931310e1318a6397ee2d7eead966bd0fcdeaae9c10038ca2f2aa01de1a45f7e` |
| Wallpaper guard, authored commit `079a9da` | `a92e26604ec76d2280528ad396a961a8cda901e29177f87887d5b7ce8b495c44` |
| Wallpaper inspector host, authored commit `ba93f48` | `6519303a9094510ecef88399d815f2079c871dbb8d49b1494c95950c1f937f5a` |
| Wallpaper inspector guest, authored commit `ba93f48` | `0b3f83d3dd7fd74b0c1ee9008c90b874b237b0a8e818fca70e71ab67a19f1b1b` |

The app and earlier guard/inspector/partition source pins are inherited from the
already reviewed wallpaper and app proof validators and rehashed before use.
Unverified prerequisite Python source is never imported.

From this directory, the lightweight authored validation command is:

```sh
python3 -B -m unittest -v test_guard_ios26_coldboot
```

The host tests exercise strict floor boundaries, read failures and recovery
latches; exact original command/tree matching; no post-spawn child inspection;
original-owner cleanup after a low-memory stop; historical proof prefixes;
complete retained chains; standalone pack/copy/geometry constraints; bytes
beyond the fast identity prefix; old source changes; lock conflicts; exact
read-only saved-inspection launch; source/nonce/native/fsck receipt requirements;
read-only preflight; and conjunction of original witnesses, memory and final
hashes. Owner, helper and native observations are mocked where needed. The
original owner-loop test uses a real small host memfd with a fake child and
mocked sealing because this host Python lacks the seal constants. No test
executes QEMU, mounts a filesystem, starts a guest or accesses a GPU/phone.
