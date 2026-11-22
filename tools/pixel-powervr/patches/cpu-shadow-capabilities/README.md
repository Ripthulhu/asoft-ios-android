# Experimental CPU-shadow resource capability candidate

This incremental patch captures reims candidate
`e9cc7541e4edee4896d9564b3056bb2799595d3f`, based on the physically tested
`afdbdd0c3c13710bf0565ef9365f0a9d890b207d` source. Its complete source tree is
`c191491d2ca8a1224d0f55bd14ecec4fcdf170da`. The original integration branch and
the earlier CPU-shadow source exports remain at their qualified checkpoint.

The candidate enables buffer address ranges, heap address ranges and resource
backing detach for the explicitly selected CPU-shadow backend. CPU-shadow is
still opt-in. Host-import and absent-backend answers retain their prior values.
The change also adds authored C API/MMIO traffic and a non-GPU backend truth-table
unit so the capability answers are exercised through real core resource paths.

[`reims/source.json`](reims/source.json) records the patch hash, changed files,
excluded machine-local Cargo paths and exact full-tree reconstruction. In a
separate checkout prepared through the existing
[`CPU-shadow reims export`](../cpu-shadow/reims/source.json), apply
[`reims/0001-enable-cpu-shadow-resource-capabilities.patch`](reims/0001-enable-cpu-shadow-resource-capabilities.patch)
with `git apply --index`, then require `git write-tree` to equal the source tree
above. These are raw Git diffs, not `git am` mail patches.

The two real C API/MMIO host cases passed with synchronization validation and
zero validation errors. Exact evidence is under
[`host-checks/core-capabilities-e9cc754`](../../experiments/cpu-shadow/host-checks/core-capabilities-e9cc754/README.md).
It covers private-flag buffers, shared heaps, fragmented discard/rebind, byte
preservation and task deletion with argument buffers configured on and off.
This fixture does not dispatch a guest-framework argument-buffer shader.

At this source checkpoint, Android artifacts and physical candidate execution
are being prepared. Exact PowerVR qualification, affected full checks, cold
Apple-guest boots and the app-UID path remain separate gates. Keep this source
candidate experimental until the required integration gates are satisfied.
The app proof asset remains absent and no final APK has been built.

Build and package commands are documented in
[`CORE-CAPABILITIES.md`](../../experiments/cpu-shadow/CORE-CAPABILITIES.md).
[`IOS26-COLD-BOOT.md`](../../experiments/cpu-shadow/IOS26-COLD-BOOT.md) describes
the bounded overlay-based boot harness. Its preflight now requires all seventeen
authored cases, including both core configurations, plus review that the C
fixture and QEMU use the same exact runtime archive and generated C header.
