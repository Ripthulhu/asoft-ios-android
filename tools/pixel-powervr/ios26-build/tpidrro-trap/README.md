# Generic TPIDRRO trap candidate

**Root-shell phone qualification PASSED on 2026-11-21.**
This separate opt-in candidate fixes the pinned benchmark's T7 mismatch under
the tested identity. The [device record](../../results/2026-11-21/qemu-tpidrro-trap-root.json)
and [terminal capture](../../results/2026-11-21/native-tpidrro-trap-root.png)
preserve both CPUs' exact T7 values, native T7 witnesses, FP/copy checks and
successful completion. Ordinary-app and GPU-provider execution remain separate.
The previous executable ran native guest code but returned the host's zero
`TPIDRRO_EL0` value on both CPUs. Its result remains correctness **FAILED**;
see [phone evidence](../../results/2026-11-21/qemu-native-root.json).

The new mode leaves the guest and its expectations unchanged. It rewrites
only exact reads of `TPIDRRO_EL0` in copied code to an undefined instruction,
then uses the existing original-instruction emulator to return the guest CPU's
read-only thread pointer. The writable guest `TPIDR_EL0` continues to execute
natively and is preserved across state transfers. The existing iOS swap mode
and default behavior remain unchanged when the new flag is absent.

## Explicit mode and scope

Set `ASOFT_NATIVE_EL0_TPIDRRO_TRAP=1` together with native enabled, required
native mode, and 1–32 stub slots. The new flag is mutually exclusive with
`ASOFT_NATIVE_EL0_TPIDRRO=1`. It rejects in-process execution, disabled code
cache and the `PATCH_XO` option.

Executable mappings must be read-only and copied through aligned 16 KiB
code-cache pages from RAM fd index 0. Even clean executable pages are copied.
Writable executable mappings, direct executable RAM aliases, private-copy
substitutes and uncacheable executable pages are rejected. Neighbour prefill
is disabled, worker fill descriptors are checked, and worker fill failures
terminate this qualification instead of selecting a TCG substitute.

This is a focused ordinary-memfd test. It adds no PowerVR memory provider,
GPU allocation, app integration or new process/fd lifetime mechanism. Existing
kernel and unsupported-instruction TCG paths remain part of the hybrid engine.
Outside-window and guest-translation decisions retain their existing behavior;
the strict pinned benchmark witness is what excludes a TCG-only qualification.
Concurrent writable aliases, self-modifying code and instruction-byte data
inspection are not qualified. See the full [mode contract](native-el0-tpidrro-trap.rst).

## Exact artifacts

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Incremental TPIDRRO patch | 63,270 | `1738fb1fe0b7dcf50e3fc6a39e71ec10430c9d7204b39588f6a84d56f5c553e6` |
| Full required-native + TPIDRRO source patch | 99,636 | `baa62fc7ee6191dc9b6befa8226e0c5c74c291b642283a98a4ad2722cb9603bd` |
| Android executable | 58,516,208 | `78e6174366fa3522fdcef0e1eca3f606ea3601823148bb69a31e4ecd18c42a35` |
| Separate phone ZIP | 20,184,858 | `2ca2bc06c689126d37ea1fc1e8836ab21862c8b98f0186330ea65e96b8dc17d1` |

The standalone archive is `qemu26-tpidrro-trap-smoke.zip`; large executables
and runtime libraries are omitted from this repository checkpoint. The ZIP's
[manifest](package-manifest.json) and [payload hash list](package-SHA256SUMS)
are included here. Every earlier ZIP and executable remains unchanged.

## Applying and reconstructing

Source base: `alpersamur3/qemu-sptm` commit
`7a900afb62ddf94713e38ac5a4aafe1d42c9efa8`.

For a clean base, apply [the Android configuration patch](base-qemu-android-build.patch)
and [the full source patch](native-el0-required-plus-tpidrro-trap.patch).
They touch disjoint files. The full source patch includes the required-native
implementation and this new mode, source tests, documentation and runners.

The [incremental patch](native-el0-tpidrro-trap.patch) applies **only after**
the [required-native prerequisite](base-native-el0-required.patch), SHA-256
`f8894bf7f907301b4c18fd708fa162e50a1a4b337a55ce9072a4fdbf547cbef3`.
Do not stack the incremental patch on top of the full source patch. Neither
source patch embeds the separate Android Meson change.

The candidate compiles only the changed native-EL0 translation unit and
relinks the full executable with the frozen baseline's other objects and
real reims library. [build.json](build.json), [source-base.json](source-base.json)
and the build/package scripts preserve exact commands and hashes. Their
workspace paths are a build record; adapt them explicitly for another
checkout. Run the source tests from their reconstructed QEMU `tests/unit/`
locations. The flat copies in this checkpoint are provided for review.

## Verification

- The Android translation unit compiled and the full executable linked.
  The same 11 pre-existing warning messages remain; no new warning message
  was added. See [warnings.json](warnings.json) and [compile.log](compile.log).
- All 13 runtime ELF files are AArch64, have at least 16 KiB LOAD alignment,
  and form a complete dependency closure with the recorded Android system
  libraries. The candidate's dependencies match the baseline.
- All 43 existing native-initialization cases passed.
- All 51 new option, mapping, worker-boundary and cache-policy cases passed,
  including copied clean pages, reuse/rewrite and cache failure decisions.
- Independent sanitized tests exercised all 32 destination registers and
  five read-only values, instruction-selection negatives, single PC advance,
  writable-pointer state preservation and unchanged iOS swap/state behavior.
- All 30 fixtures passed against the actual new shell checker, including
  wrong T7 values, T0-only native witnesses, mixed exits and secondary failure
  after T7. See [host-validation.json](host-validation.json) and [review.json](review.json).
- Both patch apply checks, shell syntax, ZIP CRC and all payload hashes passed.
  No target executable was run on the build host or by this checkpoint task.

These host models alone do not establish Android signal delivery or target
execution. The subsequent root-shell phone run supplied that evidence for the
pinned benchmark. Complete raw logs remain on the phone; the repository record
clearly labels selected output and hash transcriptions.

## Phone qualification

The verified delta transfer reconstructed all 22 frozen package files in a
fresh private directory and rechecked the unchanged original binary. The
runner exited 0 in seven seconds including wrapper work, and QEMU exited 0.
Both CPUs reported the expected T7 values and two native TPIDRRO emulations,
each ending at PC `0x100000768`. Native statistics recorded 415,536 entries
and 404,036 SVCs. These are execution witnesses, not a performance comparison.
See [transfer provenance](../tpidrro-transfer/README.md) and the device record
above. The frozen archive and its build-time metadata are unchanged.

Run [native-el0-tpidrro-trap-smoke.sh](native-el0-tpidrro-trap-smoke.sh) with a
new isolated package directory as its only argument. It verifies hashes and
negative configuration cases, then runs the unchanged guest with ordinary
512 MiB memfd RAM, two CPUs, two stub slots and `/dev/null` stdin. It uses the
original serial-stdio command and no sampler/debug additions. The stdin choice
matches EngineService and the successful stdin-only control; that control
does not conclusively locate the prior terminal-path stall.

The 30-second bound has a three-second forced-stop grace period. The code
cache reserves a sparse 1 GiB memfd; do not use a smaller process file-size
limit to constrain logs. Such limits affect the code/RAM memfds too.

`NATIVE_TPIDRRO_TRAP_BENCH_PASS=1` requires each CPU's own T6, T7, T10 and
`EXIT 0` result, positive native SVC/time evidence, and copied-code activity.
Each CPU must also report at least two native TPIDRRO traps with its last PC
at the exact T7 read, `0x100000768`; T0 alone cannot provide that witness.
T7 must retain writable pointer `0x1234` and read-only pointer `0xabcd0000`
for CPU0 / `0xabcd0001` for CPU1. CPU0 completion alone cannot prove secondary
success because the guest's secondary fatal-park path also increments its
done counter. Any `MISMATCH`, `check=BAD`, nonzero exit or native-policy
failure rejects the run.

Code-map counters count requests issued, not completed worker maps; the
native T7 witnesses establish execution. A shell pass qualifies only that
identity. Ordinary-app execution, iOS boot, GPU-backed native RAM and complete
process-tree quiescence remain separate requirements.
