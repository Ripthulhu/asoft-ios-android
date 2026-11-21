# Adopted Vulkan buffer placement and backing lifetime

This optional metal2vulkan increment adds the ownership and address-placement
boundary needed by a future producer-backed reims path. It is not part of the
frozen series used by the existing Pixel runtime probes or QEMU reconstruction.
Neither series manifest in the parent directory has been changed.

## Exact source

| Item | Value |
| --- | --- |
| Repository | `https://github.com/alpersamur3/metal2vulkan` |
| Required base commit | `ffda2ffd9485b6796ad8ca49bc024bf97401342c` |
| Required base tree | `9fe786a921829ccdb51b2d977c0dbf30f7173962` |
| Prepared commit | `7aaf60f105544b70b4cf25f9eb44ace4b00a61fd` |
| Prepared tree | `1ee7add340efbe6da12d9e16e29dfe60ed5daff9` |
| Mail patch SHA-256 | `8f1e6e0500a104200b237f351c9a835dbf8929aa9f85543479d1ecdf49a3b898` |

The patch is `0011-Retain-adopted-Vulkan-backing-with-explicit-address-placement.patch`.
Its name identifies an optional increment, not a replacement for the existing
series. `provenance.json` records the source hashes, dependency resolution,
toolchain versions, validation details, and a successful reconstruction of the
prepared tree using a temporary Git index. The repository and working index were
not changed by that reconstruction check. The upstream dual license continues to
apply; copies are in the parent directory's `licenses/`.

Apply in a clean, isolated checkout at the exact base above:

```sh
git apply --check /path/to/0011-Retain-adopted-Vulkan-backing-with-explicit-address-placement.patch
git am /path/to/0011-Retain-adopted-Vulkan-backing-with-explicit-address-placement.patch
git rev-parse 'HEAD^{tree}'
```

The resulting tree must equal the prepared tree. `git am` can produce a different
commit ID because the committer metadata is local. Check this directory's contents
with `sha256sum -c SHA256SUMS` before applying it.

## API and lifetime contract

`VkBufferDescriptor` and the unsafe
`Device::new_buffer_with_vk_buffer_descriptor` add three independent inputs:

- `AddressPlacement`, including an explicit guest-visible address;
- an optional `RangeToken`, released with the Metal address range;
- an optional caller-owned `KeepAlive`, retained through the actual backing's
  final memory and command references.

The old `new_buffer_with_vk_buffer` wrapper retains its `Any` placement, no-token,
no-owner behavior and its existing diagnostic call names. Both entry points use
the same validation and wrapping implementation.

The owner is installed before the buffer becomes visible and is held by
`FixedPages`. Live address tables and `MemoryHold` can therefore retain it after
the Metal address range is released. `ProgramObject` also accounts for its caller
destructor, so it does not run on the queue-waiter completion path. Destruction is
scheduled only after the runtime's memory lock and exit section have ended.
Process exit retains the backing alongside the runtime's existing retained
Vulkan objects. The runtime does not itself destroy the adopted raw Vulkan
objects; a caller-supplied owner can do so.

This remains an unsafe adoption API. The caller must supply live objects from the
actual same logical device, accurate creation and binding information, required
usage and device-address allocation flags, coherent host-visible memory, a valid
mapping, and external synchronization. The API cannot validate opaque handle
provenance or infer whether different CPU mappings refer to the same bytes.

**Overlapping adopted buffers still have separate hazard identities.** A shared
allocation or owner does not register physical aliases. The caller must supply
dependencies between conflicting uses, including uses submitted through this
runtime. Physical alias registration is a separate bridge requirement.

## Executed validation

| Check | Observed result |
| --- | --- |
| New requested-address, conflict, preflight and once-only ownership test | PASS |
| New pending named-command and discarded-command ownership test | PASS |
| New argument-only compute, range release/reuse and backing retention test | PASS |
| Existing private-buffer wrapper test | PASS |
| Existing shared-buffer wrapper test | FAIL during unrelated owned AIR fixture assembly; details below |
| Existing compiler and AIR public-surface table checks | 2/2 PASS |
| Runtime Clippy with warnings denied | PASS |
| Runtime rustdoc with warnings denied | PASS |
| Refusal-surface regeneration and `git diff --check` | PASS |

The selected wrapped-buffer run was **4 passed, 1 failed, exit 100**. All three
new adoption tests passed under the Khronos layer with synchronization validation
on lavapipe. They use real Vulkan buffers and commands. Shared-event gates hold
submitted work pending; timing or a large workload is not used as a substitute.
The argument-only case executes an existing owned AIR compute fixture without
explicitly naming the adopted buffer through `use_resource`.

The old shared-buffer test reaches a separate dynamic texture-array fixture that
NDK LLVM 21 rejects with `Attribute after last parameter!` on
`llvm.lifetime.start.i64` and `llvm.lifetime.end.i64`. The old test then panics
before its manual raw-handle teardown; the two subsequent
`VUID-vkDestroyDevice-device-05137` child-leak messages remain in the complete log.
No fixture was changed and validation was not suppressed. See
`nextest-wrapped-buffers.log` and `nextest-api-surface.log` for the full results.

There is no runtime public-surface catalog in this base. The existing catalogs
cover the compiler and AIR crates, and both were checked. The external validation
crate imports and uses the new public runtime descriptor in all three new tests.
`docs/REFUSALS.md` was regenerated. The final change after these GPU tests was an
explicit documentation note about overlapping adopted-buffer hazards; executable
Rust was unchanged.

## Reproducing the focused checks

The base workspace does not list `crates/metal2vulkan-validation` as a member.
For these checks only, add that exact path to the root `Cargo.toml` workspace
`members` array. No other manifest or dependency feature changes were made.
Restore that one registration after validation; it is excluded from this patch.

The executed environment was Linux x86-64, Rust 1.98.1 for builds and rustdoc,
Rust 1.98.0 for Clippy and formatting, nextest 0.9.152, NDK r29 LLVM 21.0.0,
lavapipe ICD JSON API 1.4.305, and Khronos validation layer API 1.4.309.
Paths below are the actual workspace layout; adjust `PIXEL_WORKSPACE` when
reconstructing the same tools elsewhere. Dependency versions are recorded in
`provenance.json`.

```sh
export PIXEL_WORKSPACE=/workspace/scratch/95f3cf369f81
export PATH="$PIXEL_WORKSPACE/tooling/nextest:/home/agent/.cargo/bin:$PATH"
export CARGO_TARGET_DIR="$PIXEL_WORKSPACE/target-producer-adoption"
export RUSTFLAGS='-Dwarnings --cfg m2v_cpu_icd'
export VK_DRIVER_FILES="$PIXEL_WORKSPACE/tooling/lavapipe/lvp-local.json"
export VK_LAYER_PATH="$PIXEL_WORKSPACE/tooling/lavapipe/layers"
export METAL2VULKAN_LANE_VALIDATION=sync
export METAL2VULKAN_LLVM_AS="$PIXEL_WORKSPACE/tooling/android-ndk-r29/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-as"
export METAL2VULKAN_SPIRV_VAL="$PIXEL_WORKSPACE/tooling/shader-tools/usr/bin/spirv-val"
export LP_NUM_THREADS=1

cargo +1.98.1 nextest run -p metal2vulkan-validation --all-features --lib \
  -E 'test(/^runtime_lane::wrapped_buffers::/)' \
  --success-output immediate-final --failure-output immediate-final

cargo +1.98.1 nextest run -p metal2vulkan -p metal2vulkan-air \
  --all-features --test api_surface -E 'test(the_table_matches_the_source)' \
  --success-output immediate-final --failure-output immediate-final

RUSTFLAGS=-Dwarnings cargo +1.98.0 clippy -p metal2vulkan-runtime \
  --all-features --lib -- -D warnings
RUSTFLAGS=-Dwarnings RUSTDOCFLAGS=-Dwarnings cargo +1.98.1 doc \
  -p metal2vulkan-runtime --all-features --no-deps
python3 scripts/refusal-surface/refusal_surface.py
git diff --check
```

## Remaining integration boundaries

This increment has not been used by the Pixel phone probes. Those executed the
existing `Any` wrapper at base `ffda2ffd`. No reims/QEMU integration, producer
session, physical alias registration, wrapped-buffer rebind, heap adoption, or
GPU scatter support is included here. There is no iOS boot claim.

Native EL0 remains required. A correct native memory provider, executable-code
storage and invalidation rules must be qualified before boot. The observed
PowerVR full-allocation FD mapping and single-page CPU move do not make its
arbitrary-offset FD mapping or direct GPU-backed code execution valid.
