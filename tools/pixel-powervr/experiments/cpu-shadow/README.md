# Ordinary guest RAM and canonical GPU storage

These authored diagnostics qualify the CPU-authoritative GPU integration. They
do not build an app or an APK. CPU code, stacks, page tables, atomics and data
remain in ordinary size-sealed writable memfd RAM. Only the GPU runtime copies
between that RAM and its canonical Vulkan storage at submission boundaries.

An individual passing test is deliberately reported with
`gpu_path_complete=false`. Contiguous display output does not establish
fragmented shader, texture, index, indirect-command, alias, or rebinding coverage.
Host Vulkan results also do not qualify the Pixel's PowerVR driver.

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
