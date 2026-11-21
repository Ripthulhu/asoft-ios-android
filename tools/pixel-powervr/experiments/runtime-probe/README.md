# Real Metal runtime probe — transfer checkpoint

**The Android binary in this checkpoint has not yet been run on the phone.**
Its source has been reviewed and its real adopted-buffer compute path passes
on software Vulkan with validation enabled. The Pixel must still qualify the
moved-page compute and compiled tile-render paths. This directory packages that
exact candidate for a pinned-commit download and subsequent device testing.

The original kit runner, its four original payloads, the v2/v3 native probes and
their APKs remain separate. This experiment adds no product capability override
and changes no QEMU or native EL0 behavior.

## Exact payload

| Item | Size | SHA-256 |
|---|---:|---|
| Reconstructed `pixel_runtime_probe` | 18,720,160 bytes | `0291f97791c1b6f84c12a31a6213573f35d45c308ce306cca1505a06932b89f4` |
| Reconstructed `pixel_runtime_probe.gz` | 8,284,596 bytes | `0d2a58e80e7204206eb617001e44f2505990f97b49c3db83e1dbb5f5ea8a27ee` |

The gzip stream is split into **16 ordered parts**, numbered `000` through
`015`. Each is at most 524,288 bytes (512 KiB); the last is 420,276 bytes.
[payload-manifest.json](payload-manifest.json) records the order, size and
SHA-256 of every part, as well as both reconstructed outputs. The local
`.gitattributes` keeps part bytes unchanged by text normalization.

Compression used gzip level 9, timestamp 0 and an empty filename with zlib
1.3.2. The raw binary and complete gzip are retained in the build workspace;
only the split stream is checked in here.

## Reconstruct and run on the phone

Download `assemble.sh`, `PARTS-SHA256SUMS`, `OUTPUT-SHA256SUMS` and all sixteen
`payload/` files from the same reviewed, pinned fork commit, preserving their
relative paths. `payload-manifest.json` supplies the exact ordered file list.
From the destination directory:

```sh
sh assemble.sh
mkdir -p runtime-cache
timeout 60 ./pixel_runtime_probe --producer --cache-root "$PWD/runtime-cache"
```

The assembly script verifies every part, reconstructs into a fresh temporary
directory, verifies both output hashes, and makes the executable runnable. It
does not execute the probe. An existing reconstructed pair is verified and
retained; a partial or mismatched existing pair is refused.

Run the tile mode after the producer mode returns `RESULT=PASS` and exit 0:

```sh
timeout 60 ./pixel_runtime_probe --tile --cache-root "$PWD/runtime-cache"
```

The binary needs an existing writable cache root. It creates a unique empty
child shader-cache directory for each invocation and removes it after successful
teardown. No separate shader assets or phone-side shader compiler are required.
The actual AIR-to-SPIR-V compiler is part of this executable and runs on the
phone. The normal Vulkan loader is opened by the runtime.

| Exit | Meaning |
|---|---|
| 0 | Requested test passed; the optional compute-only mode explicitly reports `COMPUTE_ONLY_PASS` |
| 1 | Runtime, translation, execution, data, evidence or cleanup failure |
| 2 | Invalid command-line use |
| 3 | Required producer, native-map or tile capability unsupported |
| 5 | Producer baseline passed but this CPU move is unsupported |
| 6 | Bounded GPU completion wait failed or timed out; no teardown attempted |

Each GPU wait has a five-second bound. Exit 6 retains the binary label
`GPU_TIMEOUT`, but the runtime can also return a failed bounded wait for refusal
or process exit; the label alone does not establish a driver hang. The outer
60-second timeout also bounds device and pipeline creation. Errors terminate
without destructors so pending GPU work or an uncertain fixed-move destination
cannot trigger guessed cleanup.

## What the modes exercise

**Producer:** a producer-owned, host-visible coherent Vulkan buffer uses the
runtime's exact buffer usage, including BDA where enabled. It exports its actual
allocation as OPAQUE_FD, then enters the existing public
`new_buffer_with_vk_buffer` API. Repository-owned `scale_and_offset` AIR is
translated and dispatched through a Metal compute encoder. Sixty-four input
values in page 5 produce outputs in the disjoint page 6; a separate GPU readback
checks all eight pages, including six untouched guard pages and both data-page
tails. The execution record identifies the actual compiled compute pipeline.

After that baseline, a verified full native mapping and a second independently
verified full mapping precede moving the latter's page 5 into a fresh reservation.
CPU writes through the moved page feed the real compute shader; a second dispatch
writes back into that page. Canonical Vulkan, retained native and independent
GPU-readback views are checked throughout. The owner remains alive until every
adopted buffer and command has completed and been dropped. Cleanup excludes the
vacated source hole.

**Tile:** the normal runtime must actually enable coherent tile-color reads and
dynamic rendering. It translates the owned fullscreen vertex and
`fetch_scalar` AIR functions. Two 32×32 R32Float cases halve an initial value
of 1.0 twice, and 0.75 three times with explicit render-target barriers. Every
pixel must equal 0.25 or 0.09375 respectively. Actual executed pipeline records
must contain float tile attachment 0, the tile-read requirement, and no
input-attachment/ROAA path. Recorded dynamic-render begin/end counts must equal
the draw counts. No feature profile or SPIR-V is substituted to satisfy the test.

The Android build **did not set `m2v_cpu_icd` or `m2v_gpu`**. Its inputs are
preassembled AIR bitcode, not translated SPIR-V. All device selection, feature
queries and enables come from normal runtime configuration at Vulkan 1.3.

These modes qualify small runtime operations. They do not establish the reims
address-placement/owner bridge, GPU page scatter, 16 KiB guest-page behavior,
executable aliases, native EL0 stub remapping, RAM-scale allocation or iOS boot.
Native EL0 remains a required later gate. The Vulkan buffer stays contiguous
when one of its CPU pages is moved.

## Rebuild from the prepared candidate

[source.patch](source.patch) adds the complete standalone
`pixel-runtime-probes/` workspace to the prepared m2v candidate
`ffda2ffd9485b6796ad8ca49bc024bf97401342c`. It edits no product source.
[Cargo.lock](Cargo.lock) preserves the exact resolved dependencies for this
diagnostic; it is supplied here as a reproducibility input, outside the m2v
product repository's committed source.

Start with that candidate from the [kit's source preparation](../../README.md),
then create a separate checkout and apply this source patch:

```sh
git -C /path/to/prepared-metal2vulkan worktree add --detach \
  /path/to/runtime-rebuild ffda2ffd9485b6796ad8ca49bc024bf97401342c
git -C /path/to/runtime-rebuild apply /path/to/runtime-probe/source.patch
cp /path/to/runtime-probe/Cargo.lock \
  /path/to/runtime-rebuild/pixel-runtime-probes/Cargo.lock
python3 /path/to/runtime-rebuild/pixel-runtime-probes/build.py \
  --ndk /path/to/android-ndk-r29 --cargo /path/to/cargo \
  --output /path/to/build-output --target-dir /path/to/cargo-target
```

The helper uses Rust 1.98.1, the Android ARM64 target and NDK API 35; it builds
release code with warnings as errors, strips it and records input hashes and
ELF metadata. All four ELF load segments have 16 KiB alignment. Its only
`DT_NEEDED` libraries are Android's `libdl.so`, `libm.so` and `libc.so`.
[build-info.json](build-info.json) preserves the exact build command and input
hashes, including all three owned LLVM-text fixtures.

## Completed host validation

[validation.json](validation.json) and [host-validation/runs.json](host-validation/runs.json)
record the checks and their limits. The independent reviewer found no blocking
ownership, synchronization, cleanup or path-evidence issue. Rust compilation used
warnings as errors; Clippy and formatting passed. The exact Rust move helper
passed its ordinary-memfd fixture, including seven guard pages, both CPU
directions, and a reused source-hole sentinel that survived cleanup.

On software Vulkan, with the Khronos layer confirmed at both instance and
device and synchronization validation requested:

| Mode | Observed host result |
|---|---|
| `--producer-compute-only` | Exit 0: real AIR translation, adopted compute, 8,192-word canonical and independent GPU readback, then owner cleanup passed |
| `--producer` | The same baseline passed; exit 3 because its opaque fd has 36,904 bytes for a 32,768-byte allocation, before native mmap or move |
| `--tile` | Exit 3 because the actual software device lacks tile-image color reads; no tile execution is claimed |

Those runs reported no Vulkan validation or synchronization errors. Host
executables, Cargo targets, toolchains and temporary shader-cache directories
are excluded from this checkpoint.
