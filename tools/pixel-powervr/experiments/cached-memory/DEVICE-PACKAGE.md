# Pixel cached-memory diagnostic: manual-upload package

This package contains the **unchanged frozen cached-memory diagnostic** and a
runner restricted to its default mode. Preparing this archive does not mean
that the program has run on the phone or that cached producer memory has
passed. No download, trust-store change, device installation or settings change
is performed by the package.

## Exact executable

| Item | Value |
| --- | --- |
| Filename | `cached_memory_diagnostic` |
| Bytes | 61,280 |
| SHA-256 | `f69664840ba2e7588e196849ea4ce9ff598a8c0081c22e8ac249830fb43f2b9c` |
| Target | Android API 35, AArch64; 16 KiB ELF LOAD alignment |
| Required host page size | 4,096 bytes |
| Selected alias/code span | 16,384 bytes |
| Producer allocation | 32,768 bytes |
| Command used by the runner | `cached_memory_diagnostic --cached-memory` |

The package's `SHA256SUMS` covers its four payload files. It is a separate
package manifest; the original experiment's larger `SHA256SUMS` is unchanged.
`PROVENANCE.json` identifies the frozen experiment and the packaging inputs.

## User step: upload only

Upload `pixel-cached-memory-device.zip` through Tango's Files interface into
the existing phone folder:

```text
/sdcard/Download/pixel-native-resume-mdPitH/
```

Leave the ZIP intact and report that the upload is complete. No test command
is needed from you. The operator will verify the transferred hash before
extracting or executing the diagnostic in the next session.

## Operator step: verify and extract after upload

The prepared archive's exact SHA-256 and size are recorded in
`device-package.json` beside `package_device.py` in the source checkout and
in the delivery message. Check that archive hash on the phone first:

```sh
sha256sum /sdcard/Download/pixel-native-resume-mdPitH/pixel-cached-memory-device.zip
```

Continue only after it matches the recorded archive hash. Use a directory on
`/data/local/tmp` for extraction and execution; the shared-storage upload folder
is only the transfer destination.

Use the current shell identity; the runner does not invoke `su`. Extraction
must be into a **new directory** so older logs and binaries are preserved:

```sh
device_dir="/data/local/tmp/pixel-cached-manual-$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir "$device_dir" && unzip /sdcard/Download/pixel-native-resume-mdPitH/pixel-cached-memory-device.zip -d "$device_dir"
```

The archive has one top-level directory, `pixel-cached-memory-device`. If the
file-transfer interface presents an extract action, retain the original ZIP
and perform the verified extraction above. No network request is needed.

Verify before running:

```sh
cd "$device_dir/pixel-cached-memory-device" && sha256sum -c SHA256SUMS
```

After both archive and payload hashes have been verified, the operator can run
the default-only wrapper:

```sh
sh ./run-cached-memory.sh
```

The wrapper accepts **no arguments** and never forwards options to the
diagnostic. It verifies the package and the hard-coded frozen binary hash,
records the current UID and SELinux context, and makes the local executable
owner-only executable. It then runs precisely the command shown above.

## Retained output and time limit

Each invocation creates a new directory:

```text
pixel-cached-memory-device/results/cached-YYYYMMDDTHHMMSSZ-PID/
    checksums.txt
    environment.txt
    diagnostic.txt
    status.txt
```

The wrapper prints the absolute `RESULTS=` path before starting. Diagnostic
stdout and stderr go directly to `diagnostic.txt`, a regular file. They do not
pass through `tee` or another pipe. The frozen program flushes and `fsync`s
regular-file phase checkpoints, including role, PID and the final result.

The diagnostic already has a 60-second parent watchdog, a 25-second child
watchdog and shorter per-operation bounds. The wrapper adds Android Toybox
`timeout -s KILL 65`, requesting a kill at 65 seconds without a further grace
period. This is a userspace time limit; it cannot contain a kernel panic or
guarantee prompt termination of uninterruptible kernel work. Toybox's documented
signal option is recorded in its
[Android source](https://android.googlesource.com/platform/external/toybox/+/ee37aaec/toys/other/timeout.c).

On completion, the wrapper displays the last 40 diagnostic lines, its status,
and the results path. The full output remains in `diagnostic.txt`. A passing
run must have exit zero, the default result marker below and a final regular-file
parent checkpoint with producer atomics disabled:

```text
RESULT=CACHED_MEMORY_BASIC_PASS_ATOMICS_NOT_TESTED
RUNNER_RESULT=CACHED_MEMORY_BASIC_PASS_ATOMICS_NOT_TESTED
```

Any other result, missing completion, timeout or interrupted connection needs
log review. Preserve the entire results directory before another test. After
a disconnect or reboot, recover the existing `diagnostic.txt` and `status.txt`
instead of automatically rerunning the binary.

## What this default mode does

It requires a compatible Vulkan allocation advertising `HOST_VISIBLE` and
`HOST_CACHED`; it has no uncached producer fallback. It performs ordinary
aligned and within-granule unaligned 64-bit accesses on the producer allocation,
explicit Vulkan flush/invalidate handoffs, GPU readback, moved CPU aliases and
the same checks in a fresh exec child. Verified instruction bytes execute from
separate ordinary memfd code snapshots, returning 42, 43 and 42.

**No LSE operation targets the GPU producer allocation in this mode.** The
separately labelled ordinary-memfd control does exercise LSE before any Vulkan
allocation exists. This distinction matters when reading the log.

The earlier uncached producer diagnostic was associated with a recovered
asynchronous SError kernel panic. The current package does not repeat that
allocation policy or its producer-atomic mode. A passing basic result would
still not establish producer atomics, Normal write-back PTEs, concurrent
CPU/GPU coherence, the reims memory contract, integrated QEMU native EL0,
general guest RAM or an iOS 26 boot. `HOST_CACHED` and `smaps` alone do not prove
those properties. Native-FD cache-maintenance coverage remains driver-specific
behavior under test.

## Rebuild this archive without changing the frozen experiment

From a checkout containing the packaging additions, run:

```sh
python3 tools/pixel-powervr/experiments/cached-memory/package_device.py \
    --output /absolute/path/pixel-cached-memory-device.zip
```

The packager prints a JSON package report to stdout; retain it as
`device-package.json` alongside this document. The packager first verifies
every entry in the original experiment manifest,
then checks the exact executable hash and size. It copies the frozen executable
without recompiling it. This document becomes the archive's `README.md`; the
original experiment `README.md` is untouched. ZIP entry times, order and modes
are fixed. With the same Python/zlib implementation and input bytes, repeated
packaging produces identical archive bytes. The script checks the resulting
ZIP CRCs and every packaged SHA-256 before reporting success.
