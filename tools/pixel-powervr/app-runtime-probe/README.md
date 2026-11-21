# Ordinary-app real Metal runtime probe

This permission-free diagnostic runs the exact real compiler/runtime binary
that passed the root producer and tile tests. VersionCode **3**, versionName
**1.2-runtime**, upgrades `com.ripthulhu.pixelpowervr.probe` with the same local
test signer. It preserves the append-only `files/report.txt`; `summary.txt`
contains the latest run. It is not the ASoftware application.

The native executables are `libpixel_runtime_probe.so` and the libc-only
`libcpu_exec_control.so`, installed in `nativeLibraryDir`. The app verifies both
SHA-256 hashes before direct `ProcessBuilder` execution and checks its ordinary
UID/SELinux domain. It first executes the same fixed AArch64 code from a fresh
anonymous mapping and from an ordinary memfd, with 10-second parent limits and
five-second native alarms. Each control must return 42 and exit 0. It then runs
`--producer`, followed by `--tile` only after exit 0 and complete output. Both
runtime processes have 60-second parent limits and five-second GPU waits. On timeout,
the app stops/reaps its own process and starts no later test. Output is bounded.

The runtime creates a new empty shader cache for each invocation under the
app's private `files/runtime-caches`. AIR translation and pipeline creation
occur on the phone. The app requests no permissions, shell, root or network
access, and contains no custom Vulkan driver. The failed GPU-backed executable-alias probe
is deliberately absent. The ordinary-memory controls do not test or claim
execution by the actual native EL0 engine.

## Reconstruct and inspect

Run `sh assemble.sh` in this directory. It verifies every ordered payload part
and the complete APK before publishing the reconstructed file. The parts hold
one signed APK, not independent installable packages. The complete APK identity
is in `payload-manifest.json` and `APK-SHA256SUMS`. The builder's signature,
binary manifest, payload and alignment verification is in `dist/verification.txt`.

- APK SHA-256: `c6f3a33e3f00b071e0ab2e6116d596519311a4bff85fbd889b84fad275e33c1c`.
- APK size: **8,315,322 bytes**.
- Runtime SHA-256: `0291f97791c1b6f84c12a31a6213573f35d45c308ce306cca1505a06932b89f4`.
- Signer SHA-256: `1be8112cbcd1eb86ff6085b63f07dd0ca68e9f4d354079b0076e9c3ea2134256`.
- minSdk/targetSdk: 35; compileSdk: 36; debuggable: false.

After review, an existing authorized device connection can install the test
upgrade with `adb install -r pixel-powervr-runtime-probe.apk`. Open the app to
run. All four stages must exit 0 for its PASS; unsupported/error/timeout stops
the sequence visibly. No saved ASoftware GPU capability result is written.

## Rebuild

`build.py` uses the Android SDK tools pinned in `provenance`, an existing test
signing keystore, and `--runtime-probe /path/to/pixel_runtime_probe` plus
`--cpu-exec-control /path/to/cpu_exec_control`. The CPU control source and
frozen binary are in [the execution diagnostic](../experiments/native-exec-diagnostic/README.md). Reconstruct
that executable from [the runtime kit](../experiments/runtime-probe/README.md).
The private signing key is not included. Supply `--build-tools`, `--android-jar`
and `--signing-keystore` for your local installation. A different signer cannot
upgrade this existing diagnostic package without a separate installation choice.

Root reviewed the new source and another agent independently reviewed the
producer-before-tile order, UID/domain check, report preservation, private caches,
payload verification and bounded child lifetime. Compilation, signing,
manifest/no-permission inspection, exact payload checks and ELF/APK alignment
checks passed. The phone run completed at `2026-11-21T15:21:33Z`, with all four
stages exiting 0 under ordinary UID 10441 and `untrusted_app_34`. Root independently
observed global SELinux Enforcing; the app could not read the enforcement node.
The [machine-readable record](../results/2026-11-21/runtime-app.json) and
[terminal evidence](../results/2026-11-21/runtime-app.jpg) preserve the result.
Recorded process durations are diagnostic timings, not performance benchmarks.

A PASS is limited to ordinary-memory fixed-code execution, small contiguous
producer memory, one moved CPU page, actual compute and two tile-fetch cases. It does not qualify GPU scatter,
overlapping resources, native executable aliases, QEMU integration or iOS boot.
