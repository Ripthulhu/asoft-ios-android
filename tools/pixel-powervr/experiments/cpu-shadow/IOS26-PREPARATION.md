# Standalone iOS26 preparation without installing an APK

`prepare_ios26.py` ports the **phone** schedule in `PhoneSetup26.java` into an
owned command-line session. Its default is a **read-only plan**. It uses the
exact seventeen-case qualified QEMU, a separately verified tooling bundle, the
existing phone helper jobs and imported step bodies, and the existing Java
input decoders. It never installs an APK or changes the app's support gate.

The [physical authored helper checkpoint](device-checks/preparation-tools-1528a782/README.md)
passed on the Pixel with the seventeen-case qualified runtime, exact returned
nonce/hash/16-KiB-page result, positive native execution and natural exit.
Repeat that small check for a changed runtime/tooling combination before large
image downloads. Both actual iOS setup boots remain explicit steps, and even
a completed asset set is not the final cold-boot/UI qualification.

## Inputs and provenance

Keep these four Python files together outside the immutable qualification and
tooling directories:

- `prepare_ios26.py`
- `prepare_ios26_stages.py`
- `cold_boot_ios26.py`
- `cold_boot_dt.py`

Provide the exact qualification package and its completed `qualification.json`
with all original case logs. The runner uses the cold-boot gate: all seventeen
cases, both core modes, all seven probe checks, exact package inventory/hashes,
and matching case-log hashes. It additionally compares the core fixture's
archive/header hashes to QEMU's corresponding build record. Execution must be
on the Android ARM64 build identified by that qualification.

The tooling packager/stager supplies a separate `tooling-manifest.json`. Pin its
SHA256 from the reviewed staging receipt with `--tooling-sha256`; the runner
checks every member's path, length, SHA256 and mode, and refuses extra files and
symlinks. Its entrypoints are:

| Entry | Bundle path |
|---|---|
| Android qemu-img | `tools/qemu-img` |
| Standalone decoder | `java/classes.dex` |
| Matching JNI decoder | `lib/libunpack.so` |
| Native Linux helper kernel | `helper/Image16k.gz` |
| Helper initrd | `helper/initrd.gz` |
| Original setup manifest | `setup/asoft-setup.json` |

The bundle also contains qemu-img's complete SONAME dependency closure,
`setup/phone`, `setup/scripts/ios26`, and `setup/steps/ios26`. The imported bodies
remain byte-identical; the runner performs the same manifest placeholder
substitution that `PhoneSetup26` performs. It does not use the PC schedule in
the manifest. The prepared target remains **iOS26.6.2, build23G90**.

`standalone/PrepareInputs.java` is compiled alongside the unchanged current
`Unpack`, `IpswFetch`, `CdnEdges`, and `Io` sources. A matching JNI build is
required: the old release's `libunpack.so` lacks the current directory-fsync
entrypoint and cannot substitute. The adapter preserves encrypted input, checks
all available ZIP-entry pins, rechecks completed member CRCs, and retains the
existing authenticated AEA decoder. CloudOS entries without a pinned CRC still
use the archive's CRC; this is recorded verification, not an invented pinned
source hash.

The app_process environment inherits only known Android runtime variables,
including `BOOTCLASSPATH`, before setting its own classpath/library path.
Android RuntimeInit can redirect standard streams; the adapter restores its
owned descriptors and writes a fresh explicit JSON result file. Exit zero with
no complete result file is a failure. Normal verified Android TLS remains
enabled. The optional adapter `tls-probe` operation performs only HTTPS HEAD
requests and reports redirects; it does not install a custom trust manager.

## First: authored native helper check

Use a short, separate work root. The qualification paths below identify the
physical `e9cc754` checkpoint; the tooling receipt identifies the reviewed
121-file `1528a782` reconstruction on the same phone.

```sh
/data/data/com.termux/files/usr/bin/python -B prepare_ios26.py \
  --package /data/local/tmp/pixel-gpu-transfer-sxtv33sh/pixel-cpu-shadow-ksceynt6/cpu-shadow-qualification \
  --qualification /data/local/tmp/pixel-gpu-transfer-sxtv33sh/qualification-e9cc754/qualification.json \
  --tooling /data/local/tmp/pixel-tools-1528a782 \
  --tooling-sha256 a5461ecf2e41d4966f783dfca620d3d700f9aa1bc76dd5fa745ec54666e764b2 \
  --work /data/local/tmp/pixel-smoke-e9cc754 \
  --helper-smoke
```

After reviewing the read-only plan, append **`--execute`** to run the authored
helper. No network or Apple
guest inputs are needed. Do not run other VM/GPU diagnostics concurrently.

This check uses the same native Linux kernel, QEMU, eight-stub native mode,
memfd RAM, virtio input/output tar disks, process owner and cleanup path as the
preparation jobs. Its Python job hashes a nonce-specific known payload and
returns that nonce, byte count, hash, machine and **16 KiB page size** through
the helper output protocol. The owner requires the exact returned JSON,
positive native execution, exactly one `ASOFT: done 0`, natural QEMU exit, and
complete reap without forced cleanup. It has a **180-second default bound**;
`--smoke-seconds` accepts 30–600.

`HELPER_SMOKE_PASSED` confirms that authored helper workload only. Its workdir
has `session.json`, `result.json`, and immutable attempts, **no setup-stage
checkpoints**. A preparation session cannot adopt the smoke workdir.

## Preparation stages

Use a different root such as `/data/local/tmp/pixel-prep-e9cc754`. Select a
reviewable boundary with `--through`. The default stops at `ios26-partition`,
before the first real iOS boot.

| Stages | Work performed |
|---|---|
| `shared-fetch`, `shared-unpack` | Fetch pinned shared inputs; unwrap firmware/tree/kernel; authenticate and decrypt the GPU source image. |
| `shared-build` | Native Linux helper builds the shell ramdisk, matched trees at 38.4 MHz, patched kernel and retained GPU bundle. |
| `ios26-fetch`, `ios26-decrypt` | Fetch the exact iPhone members and authenticate/decrypt SystemOS and OS. |
| `ios26-rootfs`, `ios26-partition` | Native helper creates the 32 GiB filesystem disk, then the partitioned disk with 16 GiB Data space. |
| **`ios26-firstboot`** | Real native-required iOS boot with the stock research kernel/plain tree; waits for persona and user-session keybags, then 30 seconds and saved shutdown. |
| `ios26-persona`, `ios26-activation`, `ios26-apps`, `ios26-gpu` | Native helper modifies new overlays, applies the existing patches and installs the retained GPU bundle. |
| **`ios26-wallpaper`** | Real iOS boot with patched kernel/AOD tree; requires migration `LastSystemVersion`, a six-minute PosterBoard interval, positive native/GPU/frame evidence and saved shutdown. |
| `ios26-locale`, `ios26-pack` | Native helper applies the explicit locale; qemu-img creates a flattened compressed AOD disk and matched asset directory. |

Pass **`--allow-network`** together with `--execute` for network stages. AEA key
lookup may fetch the header's FCS key or the pinned key database, so unpack and
decrypt count as network stages too. Both real iOS boots require
**`--allow-guest-boots`**. Flags are execution selectors; they do not authorize a
caller to bypass another party's approval or access policy.

For example, after replacing the same verified input paths and receipt, use
`--work /data/local/tmp/pixel-prep-e9cc754 --through shared-build --execute
--allow-network` for the first preparation checkpoint. Later runs use the same
work root and immutable session configuration, increasing `--through` only as
far as intended. Select the locale before the first run, for example
`--timezone Europe/Amsterdam --clock 24`; an empty region remains empty. The
generic default is `Etc/UTC`, not an inferred phone location.

The final directory is printed as `assets` in `result.json`, under the successful
pack attempt. It contains `root26s-aod.qcow2`, `root26s-aod.tc`, both matched
device trees, `bootkc`, `sptm`, `txm`, `rd-shell.hfs`, and `install.json`. The
compressed disk has no backing file. Use that complete directory with the
separate [cold-boot harness](IOS26-COLD-BOOT.md); do not rename or combine pieces
from intermediate stages.

## Resume, storage and ownership

`session.json` binds the qualified runtime/evidence, tooling receipt, manifest,
runner sources, locale, RAM and CPU configuration. Completed checkpoints form a
hash-linked ordered chain and retain full output hashes. Resume revalidates the
complete artifacts, including qcow2 backing paths. A changed configuration or
input requires a new work directory; timestamp-only app `.done` files are not
imported.

An exclusive workdir lock prevents overlapping owners. Existing child records
bind PID and start time; a still-live matching child or process naming the
private attempt tree blocks resume. The runner does not kill an unrelated PID.
Attempt trees must contain ordinary unlinked files/directories, with no
symlinks, hard links or special-file download sidecars.

Incomplete **downloads** can resume in their owned attempt using the existing
chunk markers, followed by complete CRC/hash checks. Every failed decrypt gets
a **fresh output attempt**: the decoder's original progress marker does not
authenticate an already written plaintext prefix. Encrypted input and the
failed plaintext remain preserved. Every VM attempt likewise starts a fresh
disk or overlay from its last verified predecessor; failed VM disks are never
silently adopted.

This preservation uses more storage than the app installer, which reclaims
encrypted images and intermediate disks. The app's approximately 46 GB peak is
**not** a bound for this runner. Per-stage additional-space estimates and a
1.5 GB margin appear in the plan; disk growth is monitored while processes run.
The runner never automatically deletes a predecessor, failed attempt, user
disk, encrypted image, or backing file. Review the actual remaining space
before a large stage and retain all backing-chain members.

Default helper RAM is **2048 MiB**, matching the established in-RAM work floor.
Before a VM, fresh `MemAvailable` must be at least guest RAM plus **768 MiB**;
the helper therefore needs 2816 MiB available. The iOS setup boots use a copied
tree patched to 3 GiB and require at least 3840 MiB available. No memory failure
triggers a TCG retry. While a VM runs, the default low-available-memory bound is
512 MiB. All sizes and outcomes are recorded; the runner does not free other
apps' memory or change Android security settings.

Linux helper TLS uses ordinary `TPIDR_EL0`; both TPIDRRO swap and trap modes are
absent. Actual iOS boots retain the qualified TPIDRRO swap configuration. Both
require native initialization **and positive execution**; flags alone cannot
satisfy a checkpoint. XNU/Linux kernel execution still uses TCG as part of the
established hybrid native-EL0 route.

Input tools default to two-hour bounds; helper jobs likewise default to two
hours. The first iOS boot is bounded at one hour, and migration at five hours.
The owner checks 64 MiB log and free-space bounds, drains serial in bounded
chunks, and never pauses the guest's host-counter clock. Keep the phone awake,
powered and cool; this shell runner does not reproduce Android's app wake-lock
or thermal UI.

The verified helper initrd syncs, prints completion, and powers itself off.
Successful helpers must exit naturally. On interruption/failure the owner asks
QMP stop/flush and quit, then bounded wait and owned cleanup; a forced end stays
incomplete. Guest setup boots request shell sync when responsive and always
require acknowledged QMP stop/flush, clean exit and full reap. A disk check
follows before checkpointing. Source/backing identities are checked before
and after each successful stage; completed artifacts also carry full hashes.

Returned tar data is bounded by the reported output length and device capacity.
Headers are prevalidated before the tar parser can allocate extension bodies;
links, sparse/PAX entries, oversized names, traversal, missing outputs and
incomplete terminal records are refused. A helper's `done 0` marker alone is
insufficient, because the original output-tar pipeline can fail after the job
script succeeds.

## Status and retained evidence

`PREFLIGHT_READY` is a file/plan result only. `PREPARATION_CHECKPOINT` means the
selected stages completed; `PREPARED_ASSETS` means the flattened matched set was
created. Every status keeps `boot_complete=false`, `gpu_path_complete=false`
and `app_gate_changed=false`: actual cold-boot/UI and app-UID qualification
remain separate gates. Errors and bounds return `INCOMPLETE` and exit 2.

Attempts retain launch/environment records, child identities, input requests,
adapter results, console/QEMU logs, QMP transcript, bounded frame captures,
native/GPU witnesses, cleanup records, and stage outputs. Logs/frame captures
from a real Apple guest require review before exporting. Never commit guest
images, Apple binaries, decrypted files, generated guest shaders, or the tool
bundle's binary contents into the source repository.

Focused host-only verification:

```sh
python -B -m unittest -v test_prepare_ios26.py
```

The tests use authored files and mocked operations. They cover qualification
refusals, archive/runtime identity, side-effect-free planning, exclusive
checkpoints, partial-download containment, fresh decrypt/VM attempts, overlay
preservation, Android environment/result handling, helper mode and native
witness gates, bounded tar/console parsing, nonce/page-size smoke results, and
unconditional descendant cleanup. They do not execute Android, QEMU, a GPU, or
an Apple guest.
