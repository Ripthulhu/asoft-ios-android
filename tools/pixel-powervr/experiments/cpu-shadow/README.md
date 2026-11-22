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

`build_qemu_candidate.py` reuses the preserved Android baseline's unchanged
objects, recompiles all four changed translation units, and links a separate
candidate against the new Android reims archive. The changed units are
`xnuboot_sptm.c`, `virt.c`, `vresearch_pvg_reims.c`, and `native-el0.c`. The iOS
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
