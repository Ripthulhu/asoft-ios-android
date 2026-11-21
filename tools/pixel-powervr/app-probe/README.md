# Pixel PowerVR ordinary-app probe

This small test app runs the existing Vulkan capability reporter, tile-image
ordering probe, and reviewed opaque-FD **v2** experiment under an ordinary Android
application UID and SELinux domain. It is a standalone diagnostic harness for
the rooted Pixel 10 Pro XL investigation; it does not modify or replace the
`com.asoft.ios` app, a driver, a kernel, or a system setting.

## Pixel device result — 2026-11-21

The frozen APK was installed and executed successfully on the Pixel 10 Pro XL.
The app ran as UID **10441** in SELinux domain
`u:r:untrusted_app_34:s0:c185,c257,c512,c768`, with target SDK 35. The native
query and opaque probe also reported UID/EUID 10441.

The Vulkan query and both tile-ordering checks passed. Opaque v2 passed its
Vulkan and full offset-zero native-mapping phases, then returned **exit 4**:
the first CPU mapping requesting source page 5 exposed page 0's test value.
The probe stopped before scatter writes. The app correctly reported a completed
run with an unsupported capability rather than an overall PASS. This reproduces
the root probe's CPU scatter limitation in an ordinary app context.

See [DEVICE-TEST.md](DEVICE-TEST.md) for the exact artifact identity, phase
results, observed mismatch, and limits of this validation. The APK, source,
manifest and build-time provenance remain unchanged after the device test.

## Package and execution

- Package: `com.ripthulhu.pixelpowervr.probe`.
- ABI: ARM64; native executables target Android API 35 with 16 KiB ELF alignment.
- Minimum/target API: 35; compile SDK: 36. The target matches the existing ASOFT
  app, so it does not obtain an older app's compatibility treatment.
- No requested Android permissions, shared UID, network functionality,
  analytics, services, receivers, or content providers. The app is not debuggable.
- `extractNativeLibs=true`; the three unchanged native PIE files are packaged as
  compressed `lib/arm64-v8a/lib*.so` entries. Android installs these in
  `nativeLibraryDir`, and Java executes them directly with `ProcessBuilder`.
  Only non-executable SPIR-V assets are copied to the app's own files directory.
- The app records its UID, PID, SELinux domain, optional SELinux enforcing
  readout, APK hash, and native/shader payload hashes. It refuses to start probes
  unless an ordinary app UID and an `untrusted_app` domain are observed.

Opening the Activity automatically starts one run per app process. **Run again**
starts another run after the current one finishes; Activity recreation does not
duplicate a run. All output is appended to private `files/report.txt` and shown
in selectable text. Private `files/summary.txt` contains the latest run's compact
context, hashes, stage results and important unsupported/failure messages.
**Copy report** copies only the full report to Android's
clipboard; Tango's documented **Sync from device** can subsequently transfer
that clipboard text to the connected computer.

## Probe sequence and bounds

1. `libvulkan_caps.so --api 1.3`: query only; 45-second outer timeout. If this
   query fails or is unsupported, the execution probes are skipped.
2. `libtile_image_probe.so --shader-dir <app files>/shaders`: same-draw and
   across-draw ordering checks; 45-second outer timeout. Exit 2 (unsupported)
   still permits the independent opaque-memory probe; all other nonzero exits
   stop the sequence.
3. `libopaque_fd_probe.so`: reviewed v2, including Vulkan export/import,
   POSIX FD mapping, CPU scatter mapping, repeated aliases, and canonical GPU
   readback; 60-second outer timeout. Exit 0 passes all requested phases; exits
   2, 3, and 4 describe unsupported capabilities as documented by the probe.

Native GPU fence waits are five seconds. Java drains output concurrently, waits
with a deadline, and forcibly terminates only its own child on timeout. It never
starts a later probe after an unexpected failure, incomplete output, or timeout.
The run button remains disabled after an unexpected failure or timeout, including
when a killed child cannot yet be reaped; no automatic retry is attempted.
The app reports a complete PASS only when all three stages exit zero. This is
not a test of complete iOS rendering, arbitrary existing guest-page import, or
sparse GPU aliasing.

## Build

`build.py` uses the existing Java 21 compiler module and official Android SDK
Build Tools 36.0.0 plus Android SDK Platform 36 revision 2. No Gradle or external
Java dependencies are required. The script does not download anything.

The default tool paths match Google's official SDK archives extracted under
`toolchain/sdk`. The download URLs and verified archive hashes are recorded in
`provenance/sdk-downloads.json`; Google's repository metadata provides the
expected SHA-1 checksums. SDK archives and extracted tools are excluded from
this repository. Point at existing SDK components:

```sh
python build.py \
  --build-tools /path/to/android-sdk/build-tools/36.0.0 \
  --android-jar /path/to/android-sdk/platforms/android-36/android.jar
```

Prepared, unchanged probe binaries and shaders are under `payload/`. Their
sources live in the main Pixel PowerVR diagnostic kit and the separate opaque
producer v2 experiment. The build pins the reviewed opaque v2 binary SHA-256
`f5fb47f842632a196aad9441ce1cc25d313dea2dd5b274d57b43662e0d97c59a`.

The build generates a local test certificate under `build/signing`, signs with
APK v2/v3 schemes, verifies the signature and binary manifest, checks permissions
and 16 KiB native ELF alignment, and verifies the final packaged payload hashes.
The test key is not an ASOFT release key and must not be committed or reused as a
production key. Outputs appear in `dist/`:

- `pixel-powervr-app-probe-v2.apk`
- `build-info.json`
- `verification.txt`
- `SHA256SUMS`

The checked-in APK is the frozen build with SHA-256
`2da38f13b10998a7fd394f265c1e2b0824c40a6f88e9f7461e005ea85b548093`
(53,923 bytes). Its APK v3 signature verifies for the supported Android versions;
the certificate SHA-256 is
`1be8112cbcd1eb86ff6085b63f07dd0ca68e9f4d354079b0076e9c3ea2134256`.
The exact original build script, manifest, Java source and small payload snapshot
are retained so the `dist/build-info.json` source and payload hashes remain
inspectable. The payload duplicates the kit's binaries intentionally for that
frozen provenance. Native build records and the Java version are under
`provenance/`; the compiled SDK, signing key, class files and build directories
are excluded. Rebuilding creates a fresh local test signer unless the same local
key is retained, so a rebuilt APK need not have the same APK or certificate hash.

## Device test handoff

The build does not install or launch the APK. After installation through the
existing authorized phone connection, launch:

```sh
am start -W -n com.ripthulhu.pixelpowervr.probe/.MainActivity
```

This starts an Android Activity through Activity Manager. The native probes
are then launched by the app itself; do not run the packaged native files from
the ADB/root shell when evaluating the app-context boundary. Keep the Activity
foreground until its result is displayed, then inspect the UID/domain and each
stage exit code before interpreting a PASS.

All harness source is MIT-licensed; diagnostic payloads retain their source
projects' licenses. Source SPDX identifiers are included in the Java and native
diagnostic sources.
