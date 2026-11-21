# Official Android 0.1.6 runtime inventory

Inspected on 2026-11-21. This work downloaded and statically inspected the official
release APK. It did not install the APK, run any bundled executable or helper
script, contact the phone, or alter the main application checkout.

## Release identity

- Repository: <https://github.com/alpersamur3/asoft-ios-android>
- Release: <https://github.com/alpersamur3/asoft-ios-android/releases/tag/v0.1.6>
- Release publication: `2026-11-15T17:10:57Z`.
- Annotated tag resolves to app commit `869a82690c1a4d846683319d9d15e75bfcbc50c2`.
- APK URL: <https://github.com/alpersamur3/asoft-ios-android/releases/download/v0.1.6/ASoftware-iOS-Android-0.1.6.apk>
- APK size: **109,357,759 bytes**.
- APK SHA-256: `befbcc1b31d83f166870010300a2a302e3570a7d3622d8de9c02fd896eeaa0cf`.
  The downloaded bytes match the digest and size supplied by GitHub's release API.
- `apksigner verify --verbose --print-certs` succeeded.
- Signer certificate SHA-256: `d412a33bde757a6b36524e09c215b1e2a2a21285b0fd38e8e30a8c5f23672ef2`.
- Manifest identity: `com.asoft.ios`, versionCode `8`, versionName `0.1.6`, minSdk
  `29`, targetSdk `35`, compileSdk `36`, ARM64 only.

The complete API responses, signature report, manifest badging and static ELF
reports are under `reports/`. `inventory.json` records each native/asset member's
size, compression mode and SHA-256, each extracted library's direct dependencies,
and comparisons against the current Android source files. The APK release/tag
does **not** establish an exact source commit or reproducible build recipe for
each native/helper binary. Those components are identified by their bytes here.

## Extracted material

The inspection extracted **157 files, 229,030,424 bytes** into scratch; those
payloads are not included in this source checkpoint:

| Group | Files | Reuse decision |
|---|---:|---|
| Three QEMU executables and 38 packaged dependency libraries | 41 | Keep the helper QEMU, qemu-img and dependency closure as candidates for unchanged reuse; replace QEMU26 after backend integration |
| Helper kernels and initramfs | 3 | Reuse exact assets; preserve stored `.bin` packaging |
| Setup manifest, phone jobs, installer scripts/steps and tools | 113 | Pin release files by hash; refresh the Android-owned manifest and phone jobs from the current source |

The extraction omits the app-built `librender.so`, `libgpucheck.so`, and
`libunpack.so`, which must come from the dev APK's source build. It also omits
`libconscrypt_jni.so`, which the Gradle dependency supplies. Their original APK
hashes remain in the inventory. The iOS 16 kernel and benchmark asset were not
extracted for this iOS 26 task. No application classes/resources were extracted.

Every extracted file was hashed again from disk after writing. The complete
list is `SHA256SUMS-extracted.txt`; it can be checked from the original inspection directory (which contains
`extracted/`) with `sha256sum -c SHA256SUMS-extracted.txt`.

### Principal native and helper identities

| APK member | Bytes | SHA-256 |
|---|---:|---|
| `lib/arm64-v8a/libqemu26.so` | 79,323,176 | `ce057a7ac0e30a074b737f10a0d89ee07e4f969874db2668f7d2256655fe5f56` |
| `lib/arm64-v8a/libqemu.so` | 36,432,520 | `929563c581b1a86a5b92516a1cbebb63cfd3a1889a8749d356ece13093c9d8c5` |
| `lib/arm64-v8a/libqemuimg.so` | 2,356,032 | `1bd2fd6b968c492d0263436c260af2a8c2ee807cf4afd4fd2abb3300446e2440` |
| `lib/arm64-v8a/lib_libvulkan.so.so` | 670,888 | `392f41013aaa53c1ad339a4b5206b5cdc2c5d3a3467a03a0dd37c86eb84c4ec8` |
| `lib/arm64-v8a/lib_libvulkan_freedreno.so.so` | 18,350,264 | `b721583659bbe9ee3606d15e7edce407aaf623f5c8806c72bb0f4e9ae42445f8` |
| `assets/helper/Image.gz.bin` | 14,735,226 | `fc01672d018705fa533757498fc58a8e5b572b64d9504128a912b05009e89a63` |
| `assets/helper/Image16k.gz.bin` | 14,699,489 | `f18bca1a0cc68d8c2bce7809d76523a61c367392c81a986c81ede9db578f8dcf` |
| `assets/helper/initrd.gz.bin` | 28,853,976 | `7dff81e88f5e6261ae206c6c481f53748374d76ebd433be7b263f34c571a4a24` |

## Static linkage and rebuild boundary

`libqemu26.so` is an ARM64 Android executable using `/system/bin/linker64`.
Its `DT_NEEDED` list contains the usual Termux dependency libraries and Android
`libc`, `libdl`, and `libm`; it has no dynamically linked reims or metal2vulkan
library. QEMU's inspected `meson.build` explicitly finds `reims-vgpu` through
pkg-config with `static: true`, and `Emu.java`/`pull-libs26.sh` describe that same
linked-in engine. Updating a separate Rust shared library cannot update this
release executable: patched reims/metal2vulkan must be linked into a rebuilt
QEMU26 that also implements the required guest-memory provider.

All extracted native `DT_NEEDED` references resolve either to the app's
`lib_*.so` aliases or Android system `libc.so`, `libdl.so`, `libm.so`, and
`libz.so`. This is a static closure check, not an Android load/run test. The
executables retain Termux runpaths; `Emu.linkLibraries*()` supplies their actual
app-private library path at launch. Preserve its filename-to-soname mapping.

The bundled Vulkan loader and Turnip library are the existing Adreno route.
They may remain packaged for that route, but a qualified Pixel backend must use
Android's system Vulkan loader and PowerVR driver. `Emu.linkLibrariesSystem()`
already excludes both aliases and the normal launch path removes custom Vulkan
driver-file variables. The current backend gate and old host-pointer memory
mode still prevent this from being a working PowerVR app.

The APK provides runtime `.so` dependencies, **not** their development headers,
pkg-config files, a complete Android QEMU sysroot, or the WSL `13-qemu.sh`
referenced by `pull-libs26.sh`. Those build inputs remain to be reconstructed or
obtained from matching primary sources. No full patched QEMU build has been
completed by this inventory.

## Current-source versus release setup drift

Comparisons use app checkout HEAD `c79b7d974f3f16cdddf8a02f305ed4bd561fe83a`;
`inventory.json` records the exact current file hashes, so the comparison does
not rely on a branch name alone.

- `setup/phone/jobs/shared-build.sh` changes the guest tree's hardcoded
  `19200000` timebase to `{TIMEBASE}`. Current `PhoneSetup26` supplies
  `CounterFreq.hz()` for this variable. Use the current job.
- `setup/phone/jobs/watch-prep.sh` has the equivalent timebase change; retain
  the current file when packaging the standard app's full setup assets.
- `setup/phone/adhoc.py`, `ipa-hashes.py`, and `jobs/ios26-apps.sh` differ only
  in line endings; nevertheless stage the current source versions consistently.
- `setup/asoft-setup.json` differs in shared GPU-driver step metadata. The
  selected Apple URLs/builds do not change in that diff. Use the current
  manifest alongside current `PhoneSetup26`.
- The other current phone files compared are byte-identical to the release.
- The extracted `root26-staged.py` already contains
  `skip_system_app_migrator`, satisfying `pull-setup.sh`'s explicit source-age
  check. Its SHA-256 is
  `57bf2f60cf192b9331791562da30a563818b2d5a683c38dc6e118285c42b4886`.

Suggested staged mixture: verified release helper assets, dependency libraries,
and installer scripts/steps/tools; exact current Android `setup/phone` and
`setup/asoft-setup.json`; rebuilt JNI libraries and the new QEMU26 engine.
The build record must list both source sets and hashes rather than calling the
whole result an unchanged 0.1.6 release.

## Files produced by this inspection

- `inventory.json`: complete machine-readable provenance, hashes and linkage.
- `SHA256SUMS-extracted.txt`: all extracted payload hashes.
- `inspect_release.py`: the static inspection/extraction program.
- `reports/github-*.json`: official release/tag API snapshots.
- `reports/apk-signature.txt`, `apk-badging.txt`, `*.readelf.txt`: verification.
- `reports/diff-*.patch`: normalized text differences against current app setup.
- `INTEGRATION-PLAN.md`: the proposed build and initial-launch policy.

The 109 MB upstream APK and extracted payloads remain in scratch. This source
checkpoint preserves only the inventory, inspection program, build plan and
verification reports; it does not vendor those release payloads.
