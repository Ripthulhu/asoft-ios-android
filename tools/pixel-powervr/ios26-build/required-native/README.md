# Required-native QEMU candidate

This separate candidate adds `ASOFT_NATIVE_EL0_REQUIRED=1` to the source-built
QEMU26 engine. It exits on native initialization failure instead of silently
continuing without the requested engine. The original successful build and
loader-only package remain unchanged.

## What changed

Set both `ASOFT_NATIVE_EL0=1` and `ASOFT_NATIVE_EL0_REQUIRED=1`. Required mode
rejects an unavailable/disabled native engine, failed mirror/guard reservation,
failed context allocation, unavailable requested factory or code cache, failed
RAM-fd handoff, factory timeout, and workers that exit or fail to prepare their
selected vCPU signal frames. Invalid values of the required flag also fail.
Unset, empty or `0` preserves existing behavior.

The ready message explicitly says guest execution has not yet been observed.
Required mode enables existing exit statistics. Fatal setup failures flush
their message and use `_Exit(1)` because deferred failure can occur while the
stub-pool mutex is held; running ordinary exit handlers there could deadlock.

This is an initialization requirement. The hybrid engine still uses TCG for
guest kernel code and ordinary unsupported-instruction paths. The patch does
not add a general native-progress watchdog or a PowerVR memory provider.

## Exact artifacts

| Artifact | Size | SHA-256 |
| --- | ---: | --- |
| Source patch, checker revision 2 | 38,686 bytes | `f8894bf7f907301b4c18fd708fa162e50a1a4b337a55ce9072a4fdbf547cbef3` |
| Stripped Android QEMU | 58,513,456 bytes | `02fd3b92e1f7747596df8688326af2802a261bf59fdf09222b2a4d7dbb94be74` |
| Current checker-v2 ZIP | 20,146,323 bytes | `6d5da9e474172ab55cabaa0546b85b50c9fb3c52fd03c22ad7b611fe4bd5ac65` |
| Preserved phone-test ZIP, v1 | 20,145,138 bytes | `314be50ecafdcc7e9dcffd552a0c7e5e0da1f51a1337024ac66586ca3e264cd0` |

The [patch](native-el0-required.patch) applies to QEMU source commit
`7a900afb62ddf94713e38ac5a4aafe1d42c9efa8`. It does not modify `meson.build`.
The separate [Android Meson patch](../reconstruction/provenance/qemu-android-build.patch)
remains required for the reconstructed Android configuration. The two patches
touch different files and can be applied together in either order. The candidate
build reused the frozen Android baseline's unchanged objects and replaced only
the compiled native-EL0 translation unit before a complete relink.
The exact commands and source hashes are in [build.json](build.json).

The current separate archive is `qemu26-native-required-smoke-v2.zip`, recorded
in [package.json](package.json). The previously uploaded
`qemu26-native-required-smoke.zip` remains unchanged;
[package-v1.json](package-v1.json) preserves its original packaging record.
The checked-in source checkpoint omits the large executables and matched
runtime libraries. The scripts
retain the original workspace layout as a build record; adapt their paths
explicitly when reconstructing elsewhere.

## Verification

- Forty-three bounded host cases passed. They compile the production
  unsupported-host constructor and production option/stub-start functions
  with simulated factory/clock dependencies. Cases include delayed readiness,
  worker failure, invalid options, and an exit-handler lock that a fatal path
  must bypass. See [constructor-tests.json](constructor-tests.json).
- Fifteen log-checker fixtures passed. They execute the phone script's actual
  checker with CPU-prefixed guest lines. CPU0 completion and lowercase T10
  `check=ok` pass; a nonzero signed exit from any CPU fails, including mixed
  successful/failed lines. Unprefixed or secondary-only completion, `check=BAD`,
  uppercase T10 `OK`, zero native SVC/time and a floating-point mismatch fail.
  See [benchmark-log-tests.json](benchmark-log-tests.json). The
  [test source](test-native-el0-memfd-log.py) is also included in the patch and
  uses the reconstructed QEMU source-tree paths when run there.
- The supported native-EL0 translation unit compiled with the actual Android
  configuration and the complete executable linked successfully.
- The candidate retains the same 11 pre-existing native-source warnings; no
  new warning message was introduced. [warnings.json](warnings.json) and
  [compile.log](compile.log) preserve that distinction.
- The final ELF closure and 16 KiB LOAD alignment were verified. Package hashes
  and ZIP CRC passed. No target executable was run on the build host.
- The unchanged executable passed phone loader checks, native-enabled
  `-version`, and a paused native-enabled QMP machine control with two vCPUs.
  The v1 package's initial run with inherited stdin ended with status 137
  and no guest output. A subsequent control changed only stdin to `/dev/null`:
  QEMU exited zero and reported 415,727 native entries and 404,036 native SVCs.
  **Active native execution is established, but guest correctness FAILED.**
  Both CPUs reported T7 `TPIDRRO_EL0=0` with `MISMATCH`, despite both guest
  `EXIT 0` lines; the wrapper correctly exited 1. The control took 6 seconds
  including the wrapper (QEMU's reported wall time was 5,051 ms), without a
  performance claim. See the [phone evidence record](../../results/2026-11-21/qemu-native-root.json).
  The checker-v2 package has not run on the phone, and its completion-format
  correction does not fix the T7 register gap. A separate opt-in TPIDRRO trap
  candidate addresses that gap; iOS boot and GPU-backed native execution
  remain unqualified.

## Ordinary-memfd phone benchmark

The package includes the exact 12 matched libraries and the app's existing
`el0bench.elf`. The [smoke script](native-el0-memfd-smoke.sh) first verifies
payload hashes and checks that required-native plus disabled-native exits 1.
This rejects an older engine that would ignore the new requirement.
The same candidate supports bounded `-version`, `-machine help` and
`-accel help` checks before this benchmark; a second runtime package is unnecessary.

It then runs the existing `EngineService.java` configuration on `virt` with
512 MiB of ordinary memfd RAM, two vCPUs and two native stub slots. It configures
no GPU, disk or network. The 30-second outer bound has a three-second forced
stop grace period. This is a diagnostic bound, stricter than the app default
of 120 seconds. Results go into a new package-local directory.

A pass requires exit zero, requested stub-mode initialization, positive native
entry and SVC counts, positive native time, a spawned stub, guest
`[cpu0] EXIT 0 faults=...`, and successful floating-point and copy checks.
The existing guest prefixes its output with `[cpuN] `; CPU0 waits for the other
CPUs before completing. Any CPU's nonzero signed `EXIT` rejects the result,
even alongside a successful line. An unprefixed or secondary-only exit cannot
pass. The existing guest reports T10 success as lowercase `check=ok` and
failure as `check=BAD`; those exact strings remain required.

Revision 2 corrects the completion format that the earlier synthetic fixture
missed. It changes the script, tests and package while the compiled executable
remains byte-for-byte unchanged. It preserves the earlier phone-test archive
and its failure result. A ready message, positive entry attempts alone or a
timeout cannot pass. Read the complete
[startup contract and benchmark limits](native-el0-required.rst) before use.

A shell pass would qualify only that process identity. An ordinary-app test and
the actual GPU-backed native-memory integration remain separate requirements.

[checkpoint-index.json](checkpoint-index.json) records the current source, validation and package identities.
