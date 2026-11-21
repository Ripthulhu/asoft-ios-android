# Explicit reims producer ownership

This optional increment adds cached producer allocation, one retained runtime
buffer identity, CPU-address range registration, and serialized native/GPU
ownership to the actual reims library. Its additive `rvg_producer_*` C API is
used by the [native owner](../../experiments/reims-native-gpu/README.md).
The [Pixel checkpoint](../../ios26-build/reims-producer-native/README.md)
passed under root with SELinux enforcing. This does not wire the guest's general
RAM, gather/remap table, MMIO graphics calls, or ordinary-app path.

## Exact source

| Item | Value |
| --- | --- |
| Repository | `https://github.com/alpersamur3/reims-vgpu` |
| Required prepared base | `2e568fba381bca9470e2df14c7029c3a402797b0` |
| Base tree | `f94e8a04f9e1c461e5db1aaa4c4935135edc4cbe` |
| Prepared producer commit | `7bbcb042a71b57dba286d33638848c188e5d4799` |
| Prepared producer tree | `7ec29658bf455090d881b8ef055fdf00394e61b3` |
| Required metal2vulkan prepared commit | `7aaf60f105544b70b4cf25f9eb44ace4b00a61fd` |
| Required metal2vulkan tree | `1ee7add340efbe6da12d9e16e29dfe60ed5daff9` |

First reproduce the original reims and metal2vulkan series in the
[parent directory](../README.md). Apply the separate
[metal2vulkan retained-backing patch](../producer-adoption/README.md), then
apply this reims patch to its exact prepared base:

```sh
sha256sum -c SHA256SUMS
git apply --check /path/to/0012-Add-explicit-cached-producer-memory-ownership.patch
git am /path/to/0012-Add-explicit-cached-producer-memory-ownership.patch
git rev-parse 'HEAD^{tree}'
```

The resulting tree must be `7ec29658bf455090d881b8ef055fdf00394e61b3`.
The local committer metadata may produce a different commit ID. A temporary
Git index reproduced the complete tree, and reverse application also checked.
`provenance.json` matches every changed source file in the tested build to its
committed blob. The local absolute Cargo path override is excluded from the
patch and retained separately in the build checkpoint.

Select all three crates from the exact prepared metal2vulkan checkout in the
local manifest before using `build_reims.py`. The build verifies Cargo's resolved
package paths and records stable source/dependency hashes around compilation.
Use the checkpoint's `reims-Cargo.lock` for the recorded resolution. The frozen
original series manifests remain unchanged. Existing dual licenses and notices
in the parent's `licenses/` directory continue to apply.

## Contract

`Producer::new` uses the supplied exact logical runtime device. The C constructor
selects and owns a device; it does not attach to an existing `RvgDevice`.
Physical adapter IDs are not logical-device identity. Each allocation keeps one
runtime buffer, exposed as Private storage without a coherent CPU-pointer claim.

The registry resolves complete contiguous physical spans across verified CPU
aliases and retains allocation identity through address reuse. Fragmented
resources, repeated pages and holes are refused. CPU/native leases retain their
owner independently of the public producer handle. A live export prevents CPU
completion and GPU submission. Retirement requires permanently quiescent
recipients and mappings; closing an FD is insufficient.

GPU epochs flush the complete mapping, submit through the runtime, wait for
successful completion, then invalidate before permitting CPU access. Failed,
timed-out or abandoned handoffs poison the allocation. Uncertain resources are
retained to process teardown. Control state and counters use ordinary memory;
the producer path issues no atomics against the GPU-backed pages.

## Validation boundary

The focused ownership/registry tests, C export checks, new-source lint, C API
lint, runtime upload/compute/readback, and lease-release test pass. The Pixel
native owner passes all six native phases and independent GPU readback after
complete descendant reap. See the checkpoint for exact logs and source hashes.

The broader workspace check failed on unchanged formatting/lint findings and
an unavailable CMake dependency. Lavapipe's opaque FD did not have the diagnostic's
POSIX byte layout; its alias preflight correctly refused it. Neither result is
presented as a passing full gate or portable alias qualification. General guest
integration, concurrent vCPUs, producer atomics, app UID, suspend/resume and an
iOS boot remain unqualified.
