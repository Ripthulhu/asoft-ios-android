# Ordinary guest RAM and canonical GPU storage

These authored diagnostics qualify the CPU-authoritative GPU integration. They
do not build an app or an APK. CPU code, stacks, page tables, atomics and data
remain in ordinary size-sealed writable memfd RAM. Only the GPU runtime copies
between that RAM and its canonical Vulkan storage at submission boundaries.

An individual passing test is deliberately reported with
`gpu_path_complete=false`. Contiguous display output does not establish
fragmented shader, texture, index, indirect-command, alias, or rebinding coverage.
Host Vulkan results also do not qualify the Pixel's PowerVR driver.

## Current physical checkpoint

For recovery after a chat limit, start with [CONTINUE-PIXEL.md](CONTINUE-PIXEL.md).
It records the frozen phone session, active owner, exact source identities and
next gates. Its observation timestamp must be checked against the live phone.

**The expanded seventeen-case Pixel suite passed** on experimental reims
`e9cc754`, including the real C API/MMIO resource-capability cases with argument
buffers configured on and off. [`device-checks/core-run-e9cc754`](device-checks/core-run-e9cc754/README.md)
preserves all 53 exported files byte for byte, verified hashes and a terminal
screenshot. Every case exited zero, stayed within its deadline and reaped its
children without forced cleanup. Installation verified all 36 files and the
runner rechecked its complete package checksum list after execution. The
8.990135-second interval is diagnostic time, not a boot benchmark.

The actual private-flag buffer, shared heap, discard and fragmented rebind paths
passed with exact old/new/gap byte checks and completed GPU epochs. All binaries
were checked against the same runtime archive/header. The system PowerVR
D-Series DXT-48-1536 MC1 probe again passed all seven checks. Both native modes
passed; the iOS swap case retained its two changed pointers, CPU-hint rewrite,
saved registers, two native entries/SVC returns and two exact 64 by 64 frames.
Its final QEMU counters include a third presentation before shutdown, while
the supervisor pixel-checks two frames. The prior
[`fifteen-case run`](device-checks/swap-run-2a04355/README.md) remains unchanged.

The buffer/heap/detach capability trio is enabled only for the explicitly opted-in
CpuShadow candidate. Its source remains experimental and separate from the
original integration branch. Actual iOS cold boot, app-UID execution, a larger
native worker pool, PAC instruction coverage and required full integration
checks remain open. Initial recovery checks found no prepared guest assets,
installed ASoft app or resumable setup in the checked locations. The
qualification asset is absent and no final APK was built. **Resume here** in
the latest evidence README records exact paths, identities and remaining work.

**The standalone native Linux helper now also passes on the Pixel.**
[`device-checks/preparation-tools-1528a782`](device-checks/preparation-tools-1528a782/README.md)
preserves the verified 121-file tooling reconstruction, Android image-tool/JNI
checks, exact nonce/hash/16-KiB helper result, 8,080 native entries, 3,373 SVCs
and natural exit with complete child reaping. The 28 raw exported files retain
the unsupported/fault counters and timing qualification. The
[standalone preparation procedure](IOS26-PREPARATION.md) uses the same qualified
runtime to prepare a coherent guest asset set without an APK installation.
The first selected preparation boundary is shared fetch, unpack and build;
its live checkpoints must be checked before advancing to the iPhone stages.

**Shared fetch, unpack and build have now passed on the Pixel.**
[`device-checks/preparation-shared-f4d64db`](device-checks/preparation-shared-f4d64db/README.md)
records the authenticated input stage, 488 MiB shell ramdisk, matched trees,
patched kernel, retained GPU bundle and 555,827,200-byte verified return tar.
The helper recorded 864,281 native entries, 622,571 SVCs and natural exit with
complete reaping. Only metadata and selected counters are exported. The next
boundary constructs the iPhone disks, followed by a separate read-only disk
audit before actual iOS boot.

**The iPhone fetch and authenticated decrypt have passed.**
[`device-checks/preparation-iphone-f4d64db`](device-checks/preparation-iphone-f4d64db/README.md)
records both completed checkpoints. The native rootfs/partition build is the
next physical boundary. The [separate partition auditor](IOS26-PARTITION-AUDIT.md)
has passed 27 offline tests and independent review; its physical result remains
pending and does not follow from the source checks.

## Recovered candidate build

[`recovery-afdbdd0.json`](recovery-afdbdd0.json) records the completed replacement
package at reims `afdbdd0`, metal2vulkan `51c322d` and QEMU `755b88fa`.
The native runtime, qualifier, QEMU and EFI diagnostic built successfully. Its
5,444,509-byte v2 update archive passed actual delta reconstruction against the
first package. Recovery rechecked its archive, all 31 package files, host evidence
hashes and all three complete source reconstructions without rebuilding.

The two changes correct authored diagnostic witnesses: tile execution recording
is now enabled, and a same-queue timeline gate keeps the CPU edit ahead of GPU
completion. [`host-checks/ordering-witness-fix.json`](host-checks/ordering-witness-fix.json)
records the four affected host cases and the later real C API probe. All seven
probe checks passed; the host runs loaded instance and device validation layers,
requested synchronization validation and reported no validation errors.

The recovery record now points to the later complete physical run and retains
the original recovery state. It provides exact archive and manifest hashes,
local artifact locations and the earlier phone baseline path. The earlier
physical evidence and `android-build-checkpoint.json` remain unchanged historical
records; their eight passes, two failures and four unrun cases describe the
earlier package.

## Recorded host checkpoint

[`host-checks/gpu-suite.json`](host-checks/gpu-suite.json) consolidates nine
passing llvmpipe host cases at reims `3d046429378d6a3fd0866a24935b3f59868f7dff`
and metal2vulkan `51c322d883ea723d290c931b3b2013c50f5e4934` (runtime 1505).
It records the qualifier and authored AIR hashes, verified original report/log
hashes, and observed comparisons. Instance and device validation layers were
loaded, synchronization validation was requested, each case used a separate
shader-cache directory, and the reports contain no validation errors. The
previous checkpoint is preserved byte for byte in
[`gpu-suite-ebe9ce3.json`](host-checks/gpu-suite-ebe9ce3.json).

Coverage includes aliasing and fragmented/chunk-crossing shader addresses,
fixed-function copies and indexed draws, buffer and heap replacement, lifetimes,
and argument texture/sampler handles. Dynamic rebind now has seven subcases:
resident-only and named buffer replacement, exact mutable-indirect-input refusal,
and four texture/texel-view replacement or detach-only controls. Those four bind
only textures, report cold pending recording and zero buffer-table uploads, and
compare complete output texels, padding and ordinary files. Detached refusal
still permits batch synchronization; actual queue/epoch work is reported
separately from texture readback.

The pending-binding lifetime changes are source-reviewed hardening. The same
view-only fixture **also passed on the older runtime**; the record includes that
baseline and makes no failing-old/passing-new reproduction claim. These software
Vulkan checks do not test the Pixel, native EL0, or an Apple guest, and create no
APK.

## Earlier Android build and physical checkpoint

[`android-build-checkpoint.json`](android-build-checkpoint.json) records the
completed Android AArch64 runtime 1505, qualifier, EFI diagnostic and QEMU
`755b88fad8a2771a8e3e207133a54898b740cd7f` candidate. It preserves exact source,
artifact and report hashes. The native package passed 16 KiB ELF load-alignment
and dependency-closure checks; the actual three binary deltas reconstructed all
31 package files with matching hashes while preserving the baseline. The
checkpoint also records the complete diagnostic bundle by filename and hash.

The first physical Pixel 10 Pro XL run is preserved in
[`device-checks/first-run-51c322d`](device-checks/first-run-51c322d/README.md):
**eight cases passed, two failed, and four were not run**. The full runner stopped
at the installed-runtime probe's missing CPU-edit ordering witness. Separate
bounded diagnostics passed fixed-function rendering, buffer and heap rebinds,
argument handles, all seven dynamic-rebind subcases, contiguous and fragmented
EFI frames, and the authored native-EL0/GPU integration. The tile test failed its
execution-record count before reaching its pixel comparisons. All executed cases
reaped their children without timeout or forced descendant cleanup.

The native fixture checked two exact frames, two native entries/SVC returns,
both TPIDRRO witnesses and `ECHILD`. It used the generic authored-guest trap mode;
this does not establish an iOS swap-mode or Apple guest boot result. Exact raw
logs and reports are retained with verified hashes. The two witness fixes and
subsequent complete physical run are recorded above. The CPU-shadow capability
trio stays disabled, `cpu-shadow-qualified.properties` remains absent, and no APK
was built.

## Real-device C API test

`efi_memfd_integration.c` creates an actual `RvgDevice` and EFI display. It
registers two guest-physical ranges over distinct CPU mappings of the same memfd,
including a nonzero file offset, and closes the original descriptor after device
creation. The library must retain the backing itself.

Three independently checked 64 by 64 BGRA frames cover the initial resource, a
CPU update to that live resource, and a display remap through the other alias.
Every output pixel and readback row-padding byte is checked. Unrelated ordinary
RAM must stay unchanged. The additive `rvg_device_cpu_shadow_counts` API must
report real views, completed epochs and uploaded bytes on that device.

`--fragmented` uses a 64 by 128 framebuffer whose two logical 16 KiB guest pages
name file offsets 16 KiB and 48 KiB. Both guest-physical views use that layout,
while the intervening physical page is a sentinel. The two frame pages contain
different patterns, so neither a contiguous read nor a repeated first page can
pass. This reaches the product's task mapping, no-copy texture and fixed-function
gather path as well as the C API.

Link against an already built runtime with its matching generated header:

```sh
python3 build_fixture.py \
  --include /absolute/reims/crates/reims-vgpu-c/include \
  --library /absolute/build/libreims_vgpu_c.so \
  --out /absolute/results/efi-host
REIMS_VGPU_CPU_SHADOW=1 /absolute/results/efi-host/efi-memfd-integration
```

The runtime must select the `vulkan,guest-arm64` features so its guest page size
is 16 KiB. `--ndk /absolute/android-ndk-r29` instead links an Android AArch64
command-line diagnostic against an already built Android library. The script
records source, header, library and executable hashes, the complete compiler
command, and ELF details. Android LOAD segments must retain 16 KiB alignment.

For host validation, select the intended ICD and the installed Khronos layer,
enable synchronization validation, and use a new shader-cache directory for
each qualification run. Verify that the loader actually inserted the layer;
requesting it through environment variables alone is insufficient evidence.

## Native EL0 plus QEMU's actual GPU device

`native_efi_guest.S` is a bare-metal authored guest. Its EL1 setup creates 16 KiB
translation tables in ordinary RAM. Two native EL0 phases independently draw
different tile patterns into the same ordinary guest framebuffer. Each phase
reads TPIDRRO_EL0 at the fixed witness PC `0x10000007c` and returns through an SVC;
EL1 checks the exact return PC, phase, tag and TPIDRRO value. EL1 programs the
real reims EFI registers. It advances only after the supervisor acknowledges a
byte-exact GPU output frame through ordinary RAM.

`native_efi_owner.c` owns the RAM and output memfds, forks QEMU in a separate
process group, and subreaps its children. It has a bounded deadline, checks both
frames, requires a successful QEMU exit, and verifies native-entry statistics,
both exact TPIDRRO witnesses, guest completion and actual runtime GPU counters.
It kills only its own child group when necessary and requires an `ECHILD`
result before accepting completion. The generic TPIDRRO trap mode is selected
only for this authored guest; the separate iOS TPIDRRO swap mode is unchanged.

```sh
python3 build_native_fixture.py \
  --ndk /absolute/android-ndk-r29 \
  --out /absolute/results/native-fixture
```

The fixture needs a QEMU candidate containing the explicitly selected test
device on `virt`: `ASOFT_VIRT_REIMS_TEST=1`. This instantiates the same
`vresearch-pvg-reims` device used by the product, at test-only MMIO apertures
`0x0b000000` and `0x0b010000`. The supervisor supplies this switch and requires
native EL0 and CPU-shadow mode. It supplies an explicit child environment and a
new cache directory; ambient switches cannot accidentally change the test.

Place the candidate `qemu-system-aarch64`, `native-efi-guest.elf`, supervisor,
and the candidate's verified dependency closure under a fresh package directory,
with shared libraries in `lib/`. The result directory must not already exist:

```sh
/absolute/package/native-efi-owner \
  /absolute/package /absolute/new-result-directory
```

This fixture uses no Apple image, firmware, shader or binary, and performs no
CPU atomic operation on a Vulkan allocation. It does not execute the frozen
uncached-producer diagnostic.

### Separate iOS TPIDRRO swap witness

`build_native_fixture.py` also builds `native-efi-swap-guest.elf` and
`native-efi-swap-owner` from the shared sources with `NEF_IOS_SWAP=1`. The
existing `native` case still uses its generic trap mode and verifier. Both
original binaries remain byte-for-byte identical to the first qualified package.

The new `native-swap` case selects `ASOFT_NATIVE_EL0_TPIDRRO=1` and supplies no
generic-trap switch. Its two native entries read different ordinary-RAM thread
data pointers, `0x100008100` and `0x100008140`, and load distinct 64-bit values
through those pointers. Each native TPIDR read must return the zero CPU hint,
while EL1 must retain the distinct nonzero guest TPIDR value it set before that
entry. Generic trap mode or TCG returns that nonzero value and fails the check.
EL1 also compares the exact register-read PC, SVC return PC, phase and tag before
publishing its measured register record or advancing to the next GPU frame.

The swap supervisor requires two ordered exact register records, successful
native/SVC statistics, settled GPU epochs, both complete pixel patterns and
`ECHILD`. Its separate parser rejects generic-trap evidence, stale thread data,
missing records, wrong PCs, incomplete GPU work and guest failures. The same
bounded process ownership and cleanup logic serves both supervisors. The build
checks actual AArch64 register-read/load/SVC instructions and witness addresses,
16 KiB ELF alignment, and the mode strings embedded in each supervisor.

```sh
/absolute/package/native-efi-swap-owner \
  /absolute/package /absolute/new-swap-result-directory
python3 test_native_swap_fixture.py
```

[`host-checks/native-swap-fixture.json`](host-checks/native-swap-fixture.json)
records the build, generic-binary comparison, host parser checks and v1/v2 update
roundtrip. Host parser inputs are synthetic; they establish no device result.
The package runner now requires this case after the original native case, for
15 total cases. The new swap case uses one native worker and two entries; it
does not establish an app-UID run, the app's larger worker pool, PAC instruction
behavior, or an Apple guest boot. Those claims require their own execution.

## Separate QEMU candidate build

`build_runtime.py` first builds the opt-in Android library, matching C header,
single qualifier executable and six authored AIR files. It requires NDK r29,
Rust 1.98.1, cbindgen 0.29.4, and an offline Cargo dependency cache. Compilation uses
normal release optimization, one job, no debug information or LTO, native
AArch64 LSE/RCpc instructions and 16 KiB ELF alignment. Warnings are errors.
The source trees must contain committed inputs; tracked local changes are
captured as exact binary patches, and untracked files are refused.

Before running it, point the three existing entries under
`[patch.'https://github.com/steelbrain/metal2vulkan']` in reims' root `Cargo.toml`
at the matching patched checkout:

```toml
[patch.'https://github.com/steelbrain/metal2vulkan']
metal2vulkan-runtime = { path = "/absolute/metal2vulkan/crates/metal2vulkan-runtime" }
metal2vulkan = { path = "/absolute/metal2vulkan/crates/metal2vulkan" }
metal2vulkan-air = { path = "/absolute/metal2vulkan/crates/metal2vulkan-air" }
```

These machine-local paths are build configuration and do not belong in the
portable source patch. `--runtime` verifies all three resolved packages; it
does not rewrite the manifest. The build records the local manifest diff,
lockfiles, exact source revisions, commands and artifact hashes, and refuses
source changes during compilation.

```sh
python3 build_runtime.py \
  --source /absolute/reims \
  --runtime /absolute/metal2vulkan \
  --ndk /absolute/android-ndk-r29 \
  --target /absolute/task-cache \
  --out /absolute/results/runtime
```

`build_qemu_candidate.py` reuses the preserved Android baseline's unchanged
objects, recompiles all five changed translation units, and links a separate
candidate against the new Android reims archive. The changed units are
`xnuboot_sptm.c`, `virt.c`, `vresearch_pvg_reims.c`, `native-el0.c`, and
`system/main.c`. The iOS
RAM allocation also needs grow/shrink/size seals; it remains ordinary writable
RAM. The native EL0 implementation is retained from the qualified baseline.

```sh
python3 build_qemu_candidate.py \
  --source /absolute/qemu-cpu-shadow \
  --baseline /absolute/qemu26-build-reconstruction \
  --library /absolute/new-runtime/libreims_vgpu.a \
  --include /absolute/new-runtime/include \
  --ndk /absolute/android-ndk-r29 \
  --out /absolute/results/qemu-candidate
```

The baseline executable must match its saved provenance. The script checks that
it remains unchanged, verifies the new dependency list and 16 KiB ELF alignment,
and records the exact source hashes and compile/link commands. A successful
build is reported as `BUILT_NOT_EXECUTED`; device execution is separate evidence.

## Installed-runtime probe and device qualification

The candidate's `--asoft-gpu-probe` entry point creates no guest VM. With
`REIMS_VGPU_CPU_SHADOW=1`, it calls the additive `rvg_cpu_shadow_probe_v1` API
inside its linked runtime. The build must explicitly enable the
`cpu-shadow-probe` feature; a library without that feature returns unsupported.
The authored shader is assembled from source when that feature is built.

The probe runs actual aliasing GPU atomics, ordinary-file scatter, an independent
CPU write, event visibility and fragmented fixed-function copies. It reports a
pass only after exact comparisons and completed epochs. The caller supplies a
fresh 64-character lowercase hexadecimal challenge, checks the single
`ASOFT_GPU_PROBE` JSON line and successful exit, and enforces an external process
deadline. The runtime's internal waits cannot bound a driver/compiler hang.
The returned physical-device IDs and UUIDs come from that same runtime device.

This quick probe is distinct from the full authored qualification suite. The
suite also covers dynamic shader pointers, cross-chunk pages, indexed drawing,
tile-image framebuffer fetch, detached rebinding, pending/in-flight lifetimes,
shared no-copy heaps and placed textures, texture/sampler handles loaded from
fragmented argument buffers, dynamic roots refreshed after an event-blocked
backing replacement, the real-device EFI C API and native EL0 execution.
Passing it does not establish that an Apple guest has booted successfully.

`package_device_tests.py` combines already built diagnostics, their source/build
records and the preserved dependency closure. It creates a new full package and
a smaller incremental transfer archive. Large executables use a zstd patch
against the separately verified older QEMU; libraries are copied from that
unchanged baseline. The full archive SHA-256 must be checked before extraction.
`install_device_update.py` then checks the separately supplied update-manifest
SHA-256, every input and every reconstructed output before applying executable
permissions. It writes only to its newly created directory and executes nothing.

`run_device_tests.py` accepts that verified package and a new output directory.
Every case runs in a separate bounded process with an explicit environment and a
new runtime shader-cache directory. It stops at the first failed case and writes
per-case logs, exact commands, artifact hashes and `qualification.json`. Process
success, required output markers, the probe challenge and child cleanup are all
required. `gpu_path_complete` remains false in this diagnostic evidence; product
qualification and the app's selection of the tested backend are separate steps.

## Checkpointed terminal transfer

`receive_device_update.py` receives the verified `device-update.zip` through an
existing terminal session. It needs a Python interpreter with TTY stdin/stdout;
it uses no network transport and never extracts or executes the archive. Transfer
and verify the receiver source first. Read `ARCHIVE_BYTES` and `ARCHIVE_SHA256`
from the local `package-build.json`, and choose a new child directory under an
owned transfer directory. The baseline package is not an output location.

```sh
"$TERMUX_PYTHON" receive_device_update.py \
  --out "$TRANSFER_ROOT/payload" \
  --bytes "$ARCHIVE_BYTES" \
  --sha256 "$ARCHIVE_SHA256"
```

The output directory must not exist on the first invocation. The receiver turns
off terminal echo and prints its durable next sequence and byte count. Send one
frame at a time, starting at sequence zero:

```text
PART <sequence> <decoded-byte-count> <64-character-lowercase-sha256>
<base64 lines>
END <sequence>
```

The SHA-256 covers that part's decoded bytes. Base64 lines must contain a multiple
of four characters, at most 1024 per line; padding belongs only on the last line.
Parts may vary in size from one byte through 1 MiB. A 196,608-byte part produces
256 lines of 1024 base64 characters and stays below the terminal's canonical
line-length limit. Wait for the matching `ACK` before sending another frame:

```text
ACK 0 bytes=196608
TOTAL 196608
SHA256 1/2 <first 32 digest characters>
SHA256 2/2 <last 32 digest characters>
CHECKPOINT saved
READY next=1
BYTES 196608/<archive byte count>
```

Acknowledgements repaint the screen and split the digest to fit a narrow terminal.
Check the sequence, part length, cumulative length and both digest halves. Each
acknowledged part has been written and fsynced before its checkpoint is published.
A repeated identical part is acknowledged without increasing the byte count;
wrong checksums receive `NACK` and do not advance the checkpoint.

After the last part, send `FINISH` on its own line. The receiver checks the complete
archive length and SHA-256, exclusively copies it to `device-update.zip`, fsyncs
and checks that copy, then publishes completion. Existing files are never
overwritten. The copy avoids `os.link`, which was absent from the phone's Termux
Python 3.14.8. Receiving bytes is separate from the update installer's manifest,
delta-reconstruction and executable-permission checks.

`STATUS` repeats the current checkpoint. `QUIT` exits and restores terminal
settings while retaining received parts. After a disconnect or interruption,
restart with the same arguments plus `--resume`. Resume verifies every retained
part and rebuilds only its private `incoming.zip`. If final copying was
interrupted, it checks every existing destination byte against the verified input
before appending the remainder; an inconsistent prefix is refused unchanged.
Completed transfers can also be reopened with `--resume` to verify the final ZIP.

The default input timeout is 180 seconds; `--timeout` accepts a positive value up
to 600 seconds. Each part has a 600-second deadline and a session lasts at most
one hour. Normal exits, handled signals, input errors and timeouts restore the
saved terminal settings. These bounds and checkpoints let the next invocation
continue from durable data.

The focused host regression is reproducible without Android tools:

```sh
python3 test_receive_device_update.py
```

It sends 224,708 synthetic bytes through a real host PTY, including a full
196,608-byte frame. Every child runs with `os.link` removed. Coverage includes
part and whole-archive checksum refusal, exact acknowledgements, duplicate parts,
interrupted reception, interrupted final copying, mismatched-prefix refusal,
resume, bounds, timeouts and terminal restoration. The sanitized recorded result
is `host-checks/receiver-pty.json`; it makes no device or GPU qualification claim.
