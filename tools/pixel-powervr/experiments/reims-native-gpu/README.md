# Reims-owned cached bytes through native EL0

This increment moves the one-region proof's allocation, runtime buffer,
ownership state, cache maintenance, upload and independent GPU readback into
the real reims/metal2vulkan runtime. The C owner calls the additive
`rvg_producer_*` API. Its native supervisor is byte-for-byte the verified
supervisor from `native-gpu-one-region/owner.c`; the build refuses drift.

**This complete handoff passed on the Pixel under root with SELinux enforcing.**
See the [build checkpoint](../../ios26-build/reims-producer-native/README.md)
and [device record](../../results/2026-11-21/reims-native-gpu-root.json) for the
exact tested source, package, six native phases, full-range readback and limits.

The existing QEMU binary and fixed guest are reused without changes. The
runner requires QEMU SHA-256
`a815e121d487c15cd9c1cec75ca6f43a48b2edf1ab42675bb9cde988b9679145`
and verifies every file in that existing package before launch.

## What the owner verifies

1. Reims creates a 32 KiB cached, host-visible allocation and one runtime buffer.
   The owner checks the actual memory flags, cache atom and allocation size.
2. A real runtime GPU blit uploads the full page-dependent pattern. An exclusive
   CPU epoch checks all 8,192 words through the canonical mapping.
3. A native export retains the producer. CPU-end and GPU-upload attempts are
   refused while that export/epoch remains live, without advancing cache counts.
4. The unchanged strict QEMU native protocol proves the fixed native EL0 load,
   transform and store through the qualified selected 16 KiB producer view.
   Six credentialed events, exact payload/geometry, native counters, a clean
   engine exit and complete owned-descendant reap to `ECHILD` are required.
5. Only then does the owner retire the export and end its CPU epoch. Replayed
   retirement and end calls must be refused.
6. Reims flushes, submits an independent runtime GPU readback, waits and
   invalidates. All 8,192 words must match, with exactly the expected eight-byte
   change at allocation offset 16,392. A new CPU epoch checks the complete
   canonical mapping after invalidation. Allocation and runtime-object IDs
   must remain the same, with exactly two completed handoffs.

The owner has no raw Vulkan allocation/command path and invokes no producer
atomics. Code, stack, trap/control state and native counters remain in ordinary
memory. The engine uses TCG for EL1 setup and requires real native EL0 for the
target payload. This is an explicit serialized interop path; it does not wire
the guest's general reims gather/remap or MMIO graphics calls to these bytes.

## Source and build

Use the pinned reims producer patch and its metal2vulkan retained-backing
dependency described in `../../patches/reims-producer/README.md`. The local
reims manifest's three metal2vulkan path overrides must select the exact
prepared dependency. `build_reims.py` checks Cargo's resolved paths and records
the source hashes before and after compilation; it refuses changing inputs.

```sh
python3 build_reims.py \
  --source /path/to/reims-producer \
  --metal2vulkan /path/to/metal2vulkan-producer-adoption \
  --ndk /path/to/android-ndk-r29 \
  --target-dir /path/to/isolated-reims-target \
  --out /path/to/reims-producer-build

python3 build.py \
  --ndk /path/to/android-ndk-r29 \
  --reims-dist /path/to/reims-producer-build/reims-dist \
  --out /path/to/reims-owner-build
```

The library build uses one Rust compiler job, the pinned lockfile, and the
previously recorded Android desktop-window `dead_code` exception. Other Rust
warnings remain errors. The owner links the real localized reims archive,
checks its required producer symbols, and passes Clang static analysis and
16 KiB ELF alignment checks. Build outputs go into separate supplied paths.

## Device run

After reconstructing and hash-verifying the package in a fresh directory:

```sh
/system/bin/sh /path/to/reims-package/run.sh \
  /path/to/verified/qemu26-native-gpu-one-region-a815e121
```

The runner creates a new private result directory, records device context,
verifies both packages and retains the complete log. It requires
`RESULT=REIMS_NATIVE_GPU_ONE_REGION_PASS`, all six events, the guest's completion
marker, and complete descendant reap. The inherited 45-second owner watchdog,
15-second engine budget and 3-second reap budget remain in force. Reims uses
five-second GPU completion waits. These userspace budgets cannot contain a
kernel or interconnect failure.

Each invocation creates an empty `runtime-cache` inside its private result
directory. Only the owner's child environment has `HOME` removed and
`XDG_CACHE_HOME` set to that directory. This uses the existing runtime fallback
and leaves the caller's home and environment intact. The initial phone attempt
aborted before producer creation because the root shell selected the read-only
`/.cache/reims-vgpu-vulkan`; that failure is retained in the device record.

The related Rust `producer_memory` example tests the same runtime allocation
with a repository-authored AIR compute fixture. Its `--canonical-only` mode
does not qualify POSIX mapping of opaque FDs. The observed lavapipe alias
failure remains a failure; Pixel native aliases need the separately qualified
PowerVR mapping provider used by the strict engine.

`package.py` freezes the seven-file owner package and a checked delta against
the existing QEMU binary. `prepare_transfer.py` creates terminal-safe base64
parts and a pinned assembler. Its optional `--reuse-update` accepts an earlier
update directory only when its complete owner delta is byte-identical; the
phone re-hashes the reused delta before installing. This lets runner-only
corrections transfer their small metadata payload while retaining every check.
`collect-device-evidence.py` copies completed logs and produces a device record;
it launches no diagnostic.

## Integration boundary

The C constructor owns a selected runtime device. It is not attached to an
existing `RvgDevice`; equal physical adapter IDs do not establish that identity.
Rust `Producer::new` accepts the exact embedding runtime device. One allocation
keeps one runtime buffer identity, and the CPU registry validates contiguous
physical offsets across verified aliases. Fragmented resources are refused.

Remaining work includes the product's shared-device and region ownership,
guest gather/remap hooks, mid-command CPU events, dynamic mappings, concurrent
vCPUs, app-UID qualification, suspend/resume and actual iOS execution. This
diagnostic does not change product GPU gates or qualify producer atomics.
