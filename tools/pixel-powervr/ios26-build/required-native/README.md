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
| Source patch | 36,673 bytes | `b525b5431ecbddf8156f6791b03570d383d6d11766e7c24ef3dc9b3748b15ad9` |
| Stripped Android QEMU | 58,513,456 bytes | `02fd3b92e1f7747596df8688326af2802a261bf59fdf09222b2a4d7dbb94be74` |
| Native benchmark ZIP | 20,145,138 bytes | `314be50ecafdcc7e9dcffd552a0c7e5e0da1f51a1337024ac66586ca3e264cd0` |

The [patch](native-el0-required.patch) applies to QEMU source commit
`7a900afb62ddf94713e38ac5a4aafe1d42c9efa8`. It does not modify `meson.build`.
The separate [Android Meson patch](../reconstruction/provenance/qemu-android-build.patch)
remains required for the reconstructed Android configuration. The two patches
touch different files and can be applied together in either order. The candidate
build reused the frozen Android baseline's unchanged objects and replaced only
the compiled native-EL0 translation unit before a complete relink.
The exact commands and source hashes are in [build.json](build.json).

The checked-in source checkpoint omits the large executables and matched
runtime libraries. The complete ZIP is a separate deliverable. The scripts
retain the original workspace layout as a build record; adapt their paths
explicitly when reconstructing elsewhere.

## Verification

- Forty-three bounded host cases passed. They compile the production
  unsupported-host constructor and production option/stub-start functions
  with simulated factory/clock dependencies. Cases include delayed readiness,
  worker failure, invalid options, and an exit-handler lock that a fatal path
  must bypass. See [constructor-tests.json](constructor-tests.json).
- Eight additional log-checker fixtures passed. They execute the phone
  script's actual checker with synthetic logs: lowercase T10 `check=ok`
  passes; `check=BAD`, a BAD line alongside an OK result, uppercase T10 `OK`,
  missing completion, zero native SVC/time, and a floating-point mismatch fail.
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
- **Phone loading, native guest execution and iOS boot remain untested.**

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
stop grace period. Results go into a new package-local directory.

A pass requires exit zero, requested stub-mode initialization, positive native
entry and SVC counts, positive native time, a spawned stub, guest `EXIT 0`, and
successful floating-point and copy checks. The existing guest reports T10
success as lowercase `check=ok` and failure as `check=BAD`; the checker uses
those verified strings. This correction changes the script, tests and package,
while the compiled executable remains byte-for-byte unchanged.
A ready message, positive entry
attempts alone or a timeout cannot pass. Read the complete
[startup contract and benchmark limits](native-el0-required.rst) before use.

A shell pass would qualify only that process identity. An ordinary-app test and
the actual GPU-backed native-memory integration remain separate requirements.

[checkpoint-index.json](checkpoint-index.json) records the current source, validation and package identities.
