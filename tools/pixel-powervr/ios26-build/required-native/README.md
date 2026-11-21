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
| Source patch | 32 KiB approximately | `13a61cc214b6f5de96b2844830da65dfbb18183ea52f238da73b3995c1d7c15d` |
| Stripped Android QEMU | 58,513,456 bytes | `02fd3b92e1f7747596df8688326af2802a261bf59fdf09222b2a4d7dbb94be74` |
| Native benchmark ZIP | 20,143,604 bytes | `04e356a587a9667f715965c7ed529053e3361bbc82d0feaba6d221fd1cc22f94` |

The [patch](native-el0-required.patch) is the full delta against clean QEMU
`7a900afb62ddf94713e38ac5a4aafe1d42c9efa8`. It includes the Android Meson
compatibility changes also recorded in the earlier reconstruction. Do not
blindly apply both complete patch files to the same checkout. The candidate
build reused the frozen compatible baseline's unchanged objects and replaced
only the compiled native-EL0 translation unit before a complete relink.
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

It then runs the existing `EngineService.java` configuration on `virt` with
512 MiB of ordinary memfd RAM, two vCPUs and two native stub slots. It configures
no GPU, disk or network. The 30-second outer bound has a three-second forced
stop grace period. Results go into a new package-local directory.

A pass requires exit zero, requested stub-mode initialization, positive native
entry and SVC counts, positive native time, a spawned stub, guest `EXIT 0`, and
successful floating-point and copy checks. A ready message, positive entry
attempts alone or a timeout cannot pass. Read the complete
[startup contract and benchmark limits](native-el0-required.rst) before use.

A shell pass would qualify only that process identity. An ordinary-app test and
the actual GPU-backed native-memory integration remain separate requirements.
