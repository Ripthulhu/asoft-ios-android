# Pixel PowerVR app probe v3: one CPU page move

This is a separate build of the permission-free ordinary-app diagnostic harness.
It upgrades the known test package `com.ripthulhu.pixelpowervr.probe` from version
code 1 / `1.0-v2` to version code **2 / `1.1-v3`**, using the same local test
signing certificate. It does not replace `com.asoft.ios`. All frozen v2 source,
payloads, APK and provenance remain in the separate `app-probe` directory.

The v3 native experiment passed in the coordinating session's root test before
this APK was built. The frozen APK subsequently **passed in the ordinary app
context on the Pixel 10 Pro XL**, at `2026-11-21T14:30:43Z`, as UID 10441 in
`u:r:untrusted_app_34:s0:c185,c257,c512,c768`. Query, tile and opaque move-mode
stage exits were all zero. The move, visibility, seven-guard-page and cleanup
checks passed. See [DEVICE-TEST.md](DEVICE-TEST.md) for the measured result and
its scope; build-time provenance remains unchanged.

## Change from v2

The Vulkan capability query, tile-image executable and both SPIR-V shaders are
byte-for-byte identical to v2. The opaque executable is the reviewed v3 payload,
SHA-256 `987d6950f1654753dab838c41b02d5072872bd8a5ab7f4b6681b1427f83eeb30`,
and the Activity invokes it with **`--move-page`**.

That option retains the Vulkan export/import and full offset-zero native-map
baseline. It then verifies an additional disposable full mapping, moves one
already-verified CPU page (source page 5) into an owned destination with
`mremap`, and checks its initial contents before writing. Subsequent checks
compare the changed page and all seven guard pages through canonical CPU and
GPU views, then verify a GPU fill through the moved CPU page. Successful
cleanup covers only the mapping intervals still owned by the probe.

This mode does **not** repair or rerun v2's failed direct nonzero-FD-offset mapping.
It does not test repeated CPU aliases, forced refault, GPU scatter/gather,
arbitrary existing guest-page import, guest-sized allocations or iOS rendering.
The GPU buffer remains canonical and contiguous. The native source and design
are tracked separately in the kit's
[opaque-move-v3 experiment](../experiments/opaque-move-v3/README.md).

## Context, sequencing and results

The manifest still requests no permissions, uses no shared UID, and is not
debuggable. Native executables are installed with `extractNativeLibs=true` and
run directly from `nativeLibraryDir`; the app does not invoke a root command or
shell. The existing ordinary-UID/`untrusted_app` context guard, payload hash
verification, output bounds and stop policy are unchanged.

Opening the Activity starts one sequence per app process:

1. `libvulkan_caps.so --api 1.3`, outer timeout 45 seconds.
2. `libtile_image_probe.so --shader-dir <app files>/shaders`, outer timeout
   45 seconds.
3. `libopaque_fd_probe.so --move-page`, outer timeout 60 seconds.

Native GPU fence waits remain five seconds. A failed query prevents later
tests. Tile exit 2 may continue to the independent opaque test; unexpected
failures, incomplete output and timeouts stop the sequence and disable retries
in that app process.

In this explicit move mode, opaque exit **0** passes all requested phases;
**2** means Vulkan support is unavailable; **3** preserves a Vulkan pass while
reporting unavailable full native FD mapping; **5** preserves the earlier
baseline while reporting an unavailable disposable mapping, move or initial
moved-page view. A mismatch after moved-page writes begin is failure **1**.
Exit 4 belongs to the separate direct-offset path and is unexpected for this
APK's fixed `--move-page` invocation. The app reports an overall PASS only when
query, tile and move-mode opaque stages all exit zero.

The updated UI/header, native argument log and `opaque_v3_move` stage name
identify the new mode. `files/summary.txt` is replaced with the latest compact
result and includes `CPU_MOVE_*` and GPU-to-moved-page markers. Full output
continues to append to `files/report.txt`, which may retain the preceding v2
run after an in-place test-app upgrade. **Copy report** copies that full history
to Android's clipboard.

## Build and provenance

Use the same official Android SDK Build Tools 36.0.0, platform 36 revision 2
and installed Java 21 compiler module as the v2 harness. No Gradle or external
Java dependency is required. The script downloads nothing, verifies the reviewed
opaque payload hash, and refuses an absent or different signing key.

```sh
python build.py \
  --build-tools /path/to/android-sdk/build-tools/36.0.0 \
  --android-jar /path/to/android-sdk/platforms/android-36/android.jar \
  --signing-keystore /private/path/to/v2/probe-test.p12
```

The expected signing certificate SHA-256 is
`1be8112cbcd1eb86ff6085b63f07dd0ca68e9f4d354079b0076e9c3ea2134256`.
The private key is retained locally and excluded from the repository. A public
checkout cannot reproduce the original signature or build a same-signer upgrade
without that private test key; it is not an unrestricted signed-APK rebuild.
The repository also excludes SDK tools, class files, transfer intermediates and
temporary build directories. Exact source, payload, APK and signer identities
are recorded in `dist/build-info.json`; `dist/verification.txt` retains signature
and binary-manifest inspection. Official SDK downloads, native build metadata
and Java version are under `provenance/`.

The target SDK remains 35, minimum SDK 35, and ABI ARM64 with 16 KiB ELF segment
alignment. These settings, permissions and executable locations are unchanged
from the app context already tested with v2.

## Frozen APK

| Field | Value |
|---|---|
| APK | `dist/pixel-powervr-app-probe-v3.apk` |
| Bytes | 58,019 |
| SHA-256 | `16c4343fcd733c4df2a9ee024001554edebf140749866e60dab650d9ae5025f4` |
| Package / version | `com.ripthulhu.pixelpowervr.probe`, code 2, `1.1-v3` |
| Certificate SHA-256 | `1be8112cbcd1eb86ff6085b63f07dd0ca68e9f4d354079b0076e9c3ea2134256` |

The APK v3 signature verifies, and the signer matches the installed v2 test
package's certificate. The binary manifest, embedded payload hashes and 16 KiB
ELF alignment were checked. Exact source and payload snapshots are retained
with this frozen artifact; the SDK and private signing key are excluded.
Any later phone result belongs in a separate device-test record,
without rewriting build-time provenance.

## Device handoff

The build does not install, upgrade or launch the APK. The coordinating device
session may update only the known test package after verifying the APK and
same signer, then launch its Activity:

```sh
am start -W -n com.ripthulhu.pixelpowervr.probe/.MainActivity
```

Private report paths are unchanged:

```text
/data/user/0/com.ripthulhu.pixelpowervr.probe/files/summary.txt
/data/user/0/com.ripthulhu.pixelpowervr.probe/files/report.txt
```

An actual app test should record its UID/domain, exact mode and each native
exit code. A root native pass alone does not establish that app result.
