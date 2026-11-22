# Bounded iOS26 native/GPU cold-boot observation

`cold_boot_ios26.py` prepares and observes the actual `vresearch` guest after the
authored qualification suite. **Its default is read-only preflight.** Only
`--boot`, complete existing guest inputs, and a matching completed physical
qualification including `native-swap`, `core`, and `core-no-argument-buffers`
permit execution. It does not build an
APK, download or prepare Apple images, modify the app support gate, or change
device security settings.

## Established blocker at recovery

On 2026-11-22, read-only phone inspection found no guest in any expected root:

- `/data/local/tmp/asoft/ios26`
- `/data/user/0/com.asoft.ios/files/ios26`
- `/data/user/0/com.asoft.ios.dev/files/ios26`

Both app package queries returned no installation, both private
`files/setup/a26` progress directories were absent, and searches under
`/sdcard/Download` and `/data/local/tmp` to depth three found no matching guest
assets or user qcow2. No Apple guest inputs were found in the recovered local
scratch/cache workspaces either. These are the search scopes, not a claim to
have searched every filesystem. An old `ios26-inventory.txt` was an inventory,
not an installed guest. **No actual iOS26 cold boot has been performed.**

Both the old fourteen-case `afdbdd0` suite and the later fifteen-case swap suite
deliberately fail this harness's preflight. The final runtime needs all fifteen
existing cases plus **`core`** and **`core-no-argument-buffers`**, for seventeen
required cases. Both core cases must pass; a passing default core case does not
substitute for the argument-buffer-disabled mode. Complete and review this
capability-enabled runtime's physical suite before using the harness. Its
package checksum list, every case's original log,
and `qualification.json` must remain together and unchanged. The harness checks
the matching completed cases and seven-check probe, then rechecks the full
runtime and evidence immediately before launch and after shutdown. Source and
runtime archive provenance still require review: verify that the C core fixture
and QEMU were linked from the **same final runtime archive** and corresponding
source revisions. Passing a separate C fixture's logs does not establish which
runtime was linked into QEMU. This harness binds its selected binaries to the
completed physical report; it does not infer archive identity or source
capability settings from those logs.

## Required inputs

Use a single coherent installed image set:

| Variant | Base disk | Trustcache | Device tree |
|---|---|---|---|
| Manual | `root26r.qcow2` | `root26m.tc` | `dtree-root26v-smp4-19m2` |
| Phone installer/AOD | `root26s-aod.qcow2` | `root26s-aod.tc` | `dtree-root26v-smp4-19m2-aod` |

Both need `bootkc`, `sptm`, `txm`, and `rd-shell.hfs` in the assets directory and
all original backing-chain files. The AOD installer normally also supplies both
trees and `install.json`. `--variant` resolves ambiguity when both bases exist.
Use `--disk` for an existing user overlay; its chain must contain the selected
variant's base. Supply that user's `*.apps.tc` through `--trustcache` when one
exists. `--dtree` selects an already prepared matching tree.

The default is **3 GiB RAM, four vCPUs, and 1179×2556 at 3x**. The Pixel's
architectural counter was measured at **38,400,000 Hz** in
[`experiments/counter-frequency`](../counter-frequency/README.md). Each boot
patches only a copied tree's timebase and RAM fields. For an existing prepared
2x disk, use `--scale 2` and its matching 2x tree. The harness refuses a mismatched
tree; it does not alter the guest's MobileGestalt cache. Arbitrarily resizing a
3x guest to 2x gives the wrong cached UI geometry (see `Guest.fitScreen26` and
`Screen26` in the app).

An Android qemu-img executable is required separately. The app packages it as
`libqemuimg.so`; supply its dependency directory with `--qemu-img-lib` if it
differs from the qualification package's `lib`. Original APK dependency names
`lib_<soname>.so` need ordinary SONAME links, as `Emu.links()` implements. The
harness records the executable hash and runs `info` and `create` only during
explicit boot preparation, never during default preflight.

## Invocation

Keep `cold_boot_ios26.py` and `cold_boot_dt.py` together **outside** the verified
qualification package. Adding files inside that package invalidates its exact
checksum inventory. Use a new, short run directory outside the source assets,
backing-disk directories, and package. Its parent must already exist.

Example with paths replaced by verified existing inputs:

```sh
/data/data/com.termux/files/usr/bin/python -B cold_boot_ios26.py \
  --assets /data/local/tmp/asoft/ios26 \
  --package /absolute/verified/cpu-shadow-qualification \
  --qualification /absolute/completed-run/qualification.json \
  --qemu-img /absolute/libqemuimg.so \
  --qemu-img-lib /absolute/dependency-links \
  --run-dir /data/local/tmp/ios26-cold-001
```

Read the emitted plan. Missing assets, an older suite, a changed package/log, an
existing run directory, a wrong tree, or insufficient free space returns JSON
`INCOMPLETE` with exit 2 and launches nothing. `PREFLIGHT_READY` with exit 0 is
only a file/command preparation result. It does not execute qemu-img, QEMU, or a
GPU probe; it does not create a directory. No-argument invocation also returns
an explicit incomplete preflight.

Before execution, hold all other diagnostic GPU tests and VM work. Then use the
same command with **`--boot`** appended. Execution requires Android ARM64 and a
build fingerprint matching the physical qualification. It uses a minimal
environment, the system Vulkan loader, `REIMS_VGPU_CPU_SHADOW=1`, native required
mode, **TPIDRRO swap** mode, 24 stubs, and the existing 20-second native delay.
The QEMU accelerator remains `tcg,thread=multi,tb-size=768`: XNU/EL1 uses TCG,
while positive native EL0 execution is measured separately. Initialization
flags alone never count as native activity.

The default observation bound is 900 seconds; `--seconds` accepts 30–1800.
Initial qemu-img operations each have a 30-second bound and the existing tree
tool has 10 seconds. Ten-second progress reports retain sampled native/GPU
evidence. One GiB free-space and 64 MiB log bounds (including `qemu.log`) stop the
observation before further workload; configure them with `--min-free-mib` and
`--max-log-mib`. Final sizes are checked again after shutdown, and any truncated
evidence or exceeded bound keeps the result incomplete.

`--expect-serial 'literal guest milestone'` may be repeated. With explicit
milestones, the harness may stop early when every marker, positive native
execution, real GPU frame/copy counters, and a stable nonuniform captured frame
have appeared. A marker is a chosen observation milestone, not automatic proof
of a usable lock screen. Without markers it observes to the deadline and
reports `INCOMPLETE`, retaining all activity evidence for review.

## Ownership, evidence, and outcome

The original disk is opened through a **new qcow2 overlay with an absolute
backing path**. The original tree is copied and patched with the existing
tool, then independently checked byte for byte against just the intended
timebase/RAM changes. Source/backing identities (device/inode, size, times, and
first 64 KiB hash) are checked before and after. This is a change witness, not a
full multigigabyte disk-content checksum. No repair, commit, rebase, save-state
load, or backing-disk modification is performed.

The dedicated owner keeps a size-sealed frame memfd alive and passes only that
descriptor. The actual iOS26 QEMU allocates its own ordinary guest RAM. The
owner starts a separate process group, acts as a child subreaper, and requests
that QEMU die if the owner disappears. Normal SIGINT/SIGTERM requests follow
the ordered shutdown; abrupt owner SIGKILL cannot guarantee a disk flush.

Results stay in the new run directory:

- `launch.json`, `result.json`, and `backing-chain.json` record exact inputs,
  arguments/environment, package identities, progress, and cleanup.
- `serial.txt`, `qemu-stderr.txt`, and `qemu.log` retain actual guest/engine
  output. These require content review before exporting or committing.
- Frame PNGs retain the first eight minute-spaced snapshots, a latest snapshot
  thereafter, and a final stable frame when available. Frame hashes and
  stability/nonuniformity in visible RGB channels are recorded separately; the
  unused fourth pixel byte cannot turn a black image into a positive witness.
- `coldboot-overlay.qcow2`, `input-device-tree`, and `device-tree` are **local
  guest artifacts**, never repository inputs. Do not commit/push them, Apple
  guest binaries, generated guest shaders, or serialized guest descriptors.

Shutdown asks QMP **stop** (15 seconds, flushing disks), captures the final
frame, asks **quit** (3 seconds), and waits 5 seconds before killing an owned
still-live QEMU process group. It then reaps adopted descendants to `ECHILD`,
killing only its own direct children if necessary. Capture failure still takes
the quit/cleanup path. Never replace this with an unrelated `pkill` or a bare
SIGKILL of a disk-owning VM.

`WITNESSES_OBSERVED` (exit 0) requires all requested witnesses, no detected fatal
marker or changed original, acknowledged disk stop, clean QEMU exit, and full
reap without forced cleanup. Any timeout, missing witness, exception, or forced
cleanup remains `INCOMPLETE` (exit 2). **Both outcomes retain
`boot_complete=false` and `gpu_path_complete=false`.** Review the actual frame,
serial progress, native usage, and behavior before separately recording a
successful guest/UI qualification. This tool never unlocks the product gate.

## Helper provenance and focused checks

`cold_boot_dt.py` is the byte-identical existing `dt-phone.py` from the recovered
v0.1.6 APK's `assets/setup/scripts/ios26/`, already described in
[`ios26-build/PROVENANCE.md`](../../ios26-build/PROVENANCE.md). Its SHA256 is
`6931310e1318a6397ee2d7eead966bd0fcdeaae9c10038ca2f2aa01de1a45f7e`.
The launcher pins this source hash; it contains Python tree-editing logic, not
Apple binary data. Source parameters come from app `Guest.start26`,
`Guest.end26Now`, `CounterFreq`, and QEMU `native-el0.c`/`vresearch_pvg_reims.c`.

```sh
python -B tools/pixel-powervr/experiments/cpu-shadow/test_cold_boot_ios26.py
```

The focused tests use newly authored tiny ADTs, qcow2 headers, logs, and host
child processes. All twenty-two checks passed on 2026-11-22. They verify no-action
preflight/missing-input behavior, refusal of the old fifteen-case report or
either missing core case, acceptance of matching seventeen-case evidence,
checksum/swap/screen refusal, command construction, source-preserving overlay
planning, the actual existing tree helper, evidence parsing, frame encoding,
QMP message framing, runtime changes during preparation, final log overflow,
and ordered/forced owned-process cleanup despite frame-encoding errors. They never
execute QEMU, read Apple inputs, or access a GPU. The executor refused live
AF_UNIX creation with EPERM, so QMP transport is tested with an in-memory byte
stream; an actual phone QMP connection remains part of the first guest run.
