# Combined native EL0 and cached PowerVR checkpoint

**The fixed one-region proof passed on the phone.** The ordinary-memfd control,
GPU-backed run and subsequent two-CPU TPIDRRO regression all passed under the
existing root shell. [Device results](../../results/2026-11-21/native-gpu-one-region-root.json)
and the unchanged [terminal capture](../../results/2026-11-21/native-gpu-one-region-root.jpg)
record the observed result. The [experiment sources](../../experiments/native-gpu-one-region/README.md)
contain the owner, protocol, guest, fixtures, runner and packaging tools.

## What passed

| Check | Observed result |
| --- | --- |
| Ordinary memfd control | Six native phases, clean QEMU exit, three processes reaped to `ECHILD`, all 8,192 words correct |
| Producer | Memory type 2, flags `0xb`, cached/noncoherent, exactly 32,768 bytes |
| Native data view | 16,384 bytes at backing offset 16,384, guest VA `0x100004000`, GPA `0x80000000`, NX |
| Native payload | Input `0x6a1b2c346a1b2c34`, output `0x615c5026615c515d` |
| Native witnesses | READY → ENTRY → CODE_MAP → DATA_FAULT → DATA_MAP → COMPLETE; per-message credentials and durable owner ACKs |
| Native execution counters | One entry, one SVC, two successful fills; zero injected faults, kicks or unsupported operations |
| Lifetime before GPU handoff | Clean QEMU exit 0; one private-group termination signal; leader, factory and stub reaped to `ECHILD` |
| Independent GPU readback | All 8,192 words correct; only eight bytes at allocation offset 16,392 changed |
| Register regression | Both CPUs' T7 values correct, two native TPIDRRO reads each ending at `0x100000768`; runner and QEMU exit 0 |

The GPU run's context timestamp is 2026-11-21 18:44:51 UTC. It ran as UID 0,
`u:r:ksu:s0`, with SELinux Enforcing on PowerVR D-Series DXT-48-1536 MC1.
The tested code is a fixed scalar payload; this is not an iOS boot or general
GPU-backed guest-RAM qualification. The product GPU gate remains unchanged.

## Exact artifacts

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Android QEMU | 58,529,200 | `a815e121d487c15cd9c1cec75ca6f43a48b2edf1ab42675bb9cde988b9679145` |
| Android owner | 38,024 | `347d00a3190f3395ad1496a9bec46f6edd1e6af5276b78396703d40445a80be7` |
| Fixed guest ELF | 50,680 | `1f30382df569a6e1562d60c846503d7e9d886aecc352ce023b589f7b6da65d36` |
| Complete phone ZIP | 20,190,759 | `c3c9108f42333637053e407f75de95f2e96348d9669eb0e50af095145ca5cc4f` |
| Local update ZIP | 2,597,426 | `9b948d465f9f88cf01ac1cd90ee8ab88ce1727717d8165517af4685efa4d50fb` |

The full ZIP is `qemu26-native-gpu-one-region-a815e121.zip`. Large executables
and runtime libraries are retained in that separate deliverable, not committed
here. [package-SHA256SUMS](package-SHA256SUMS) identifies all frozen payloads.
Its immutable manifest says device testing was pending at package freeze; the
linked later device record supplies the completed qualification.

## Engine changes and reconstruction

Source base is `alpersamur3/qemu-sptm` commit
`7a900afb62ddf94713e38ac5a4aafe1d42c9efa8`. Apply
[qemu-native-gpu-combined.patch](qemu-native-gpu-combined.patch) to that clean
base. It includes the Android Meson adjustment, required-native checks,
generic TPIDRRO trap implementation and this new fixed provider. Do not stack
the earlier required-native/TPIDRRO implementation patches on top. The header
is included. A forward application reproduced the exact five changed source
files, and the reverse apply check passed.

The new mode is explicitly `ASOFT_NATIVE_GPU_ONE_REGION=1`. The owner supplies
the required native/copied-code flags, a single CPU/worker, the producer and
credentialed event descriptors, expected parent and fresh run generation in a
clean environment. The provider remains outside `RAMBlock.fd`. Ordinary RAM
is acknowledged at factory index 0 and the producer at index 1 before any
worker is forked. The worker maps the entire allocation at FD offset zero,
moves the selected interval into its owned native reservation and retains the
unmoved prefix until process death. Code is copied into ordinary memfd storage.

The fixed EL0 hook and trap branch fail on unsupported execution, unexpected
signals or mapping changes. The worker pauses after each map until the owner
has saved and acknowledged that exact event. The owner uses a subreaper,
captured parent identities and a private group; it retains the leader until
the one group signal, then requires `ECHILD`. Any protocol, timeout, exit or
reap failure prevents post-native GPU work. These are experiment constraints,
not a generalized process or memory-provider API.

[engine-build.json](engine-build.json) records actual compiler/link commands,
source hashes and frozen baseline object provenance. The two changed translation
units (`native-el0.c` and `virt.c`) were compiled and the full executable relinked
against the unchanged baseline objects and real reims library. Native compilation
reported 11 warnings; virt compilation and linking reported none. The build
script preserves its original workspace-relative layout; copy it into a sibling
build directory and adapt the explicit source/baseline/tool paths for another
checkout. Owner/guest build commands are in the experiment README.

## Host checks and review

The Android owner compiled with `-Wall -Wextra -Werror`; Clang static analysis
reported zero diagnostics. Its payload page was extracted and compared against
all ten instruction words and the full zero-padded 16 KiB hash. Linker section
GC removed the unrelated legacy entry point and producer-atomic experiments.

The actual owner validation rejected 8,192 single-bit packet corruptions and
six replays. Twelve real-process cases covered a valid tree with an orphan,
wrong sender, surplus/truncated records, unexpected rights, wrong PC/result,
early exit, engine deadline, nonregular logs and an unreaped descendant. Every
failure denied GPU permission. An ordinary memfd fixture checked the selected
move, retained prefix, surrounding guards and shared write. Extracted engine
guards accepted only the two allowed fault shapes across 45,000 tuples and
rejected corrupted code, fill and completion requests. These host checks did
not execute AArch64 or a GPU; the phone results establish that part.

Root reviewed the resulting source and failure paths directly. The parallel
workers hit a model authentication block, so there is no completed independent
worker sign-off. See [source-review.json](source-review.json) and the retained
build/fixture logs. Host checks and review were followed by the three successful
phone qualifications above.

## Transfer and evidence

The update reused the exact previous QEMU binary
`78e6174366fa3522fdcef0e1eca3f606ea3601823148bb69a31e4ecd18c42a35`
as its delta base. The phone checked 24 parts, the complete update ZIP and the
installer, then reconstructed and verified all 25 frozen package files in a
fresh private directory. It rechecked the old binary unchanged before enabling
execution. The full ZIP container was not transferred; its exact file contents
were reconstructed. [update.json](update.json), [install-update.py](install-update.py),
[package.json](package.json) and [transfer.json](transfer.json) preserve the details.

An initial local reconstruction rejected zstd's propagation of executable mode
bits to the delta. Packaging now marks transfer data `0600`; the unchanged
fail-closed installer then passed. This happened before phone execution.

Complete raw device logs and the generated device record remain on the phone
and in its recorded shared-download directory. The repository result explicitly
labels console-transcribed fields/hashes and does not claim downloaded raw
logs. The JPEG screenshot is preserved byte-for-byte.

## Remaining integration work

The actual native/GPU scalar data path is demonstrated. A runtime provider still
needs allocation identity, mapping lifetime and noncoherent ownership tracking
across the real reims/QEMU bridge, broader workload qualification and ordinary-app
validation. This result does not establish producer atomics, concurrent access,
general guest RAM, arbitrary offsets, dynamic invalidation, JIT behavior or an
iOS 26 boot. Keep those boundaries separate from this completed proof.
