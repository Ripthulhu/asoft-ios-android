# Standalone preparation tools, without installing an APK

`package_prep_tools.py` produces a small extraction plan and payload. The phone
extracts the remaining tools from one exact, already downloaded release APK.
Neither command installs that APK, starts QEMU, downloads Apple inputs, or
modifies the verified CPU-shadow qualification package. The preparation runner
supplies the independently qualified QEMU and enforces its 17-case result gate.

## The three sources in the bundle

| Source | Files | Integrity boundary |
| --- | --- | --- |
| Existing release APK | `qemu-img`, its 24 non-system libraries, the 16 KiB Linux helper kernel/initrd, and authored iOS 26 setup scripts/steps/tools | Whole APK byte count and SHA256, fixed 99-file whitelist with individual hashes, exact ELF metadata and dependency closure |
| Current committed app source | `setup/asoft-setup.json`, the 17 iOS/shared phone files, and the original Java/JNI source inputs | Git blob identity and source hashes checked before and after each operation; setup files copied byte-for-byte |
| Standalone adapter and build tools | `PrepareInputs.java`, rebuilt current `libunpack.so`, and `classes.dex` | Adapter commit and source hash, pinned Google R8/platform hashes, build commands and output hashes |

The resulting tool bundle has 121 inventoried files plus
`tooling-manifest.json`. It contains no iOS image, old QEMU, Vulkan ICD, app UI,
or APK. Source script templates remain unchanged, including `{TIMEBASE}` in
`shared-build.sh`; the preparation runner supplies the phone's 38,400,000 Hz
value when it authors a job.

The release APK is:

- URL: <https://github.com/alpersamur3/asoft-ios-android/releases/download/v0.1.6/ASoftware-iOS-Android-0.1.6.apk>
- Bytes: `109357759`
- SHA256: `befbcc1b31d83f166870010300a2a302e3570a7d3622d8de9c02fd896eeaa0cf`
- Release tag commit: `869a82690c1a4d846683319d9d15e75bfcbc50c2`
- Previously verified APK signing certificate SHA256:
  `d412a33bde757a6b36524e09c215b1e2a2a21285b0fd38e8e30a8c5f23672ef2`

These are byte identities, not a claim that the released native binaries have
been reproduced from that tag. `prep_tools_release.json` records every selected
member and the reviewed ELF metadata. The extractor pins that inventory's own
SHA256 and refuses a changed whitelist.

## Complete Android dependency closure

The released executable identifies itself in its embedded version text as
`qemu-img version 11.1.0 (ASoftware-android)`. Its exact member is
`lib/arm64-v8a/libqemuimg.so` (2,356,032 bytes, SHA256
`1bd2fd6b968c492d0263436c260af2a8c2ee807cf4afd4fd2abb3300446e2440`).
It is an AArch64 PIE using `/system/bin/linker64`, with congruent 16 KiB LOAD
segments. Every bundled dependency has the same required alignment.

The 24 non-system libraries total 18,712,056 bytes:

```text
libandroid-support.so  libbz2.so.1.0         libcrypto.so.3
libcurl.so            libffi.so             libglib-2.0.so.0
libgmp.so             libgnutls.so           libhogweed.so.6
libiconv.so           libidn2.so             libnettle.so.8
libnghttp2.so         libnghttp3.so          libngtcp2.so
libngtcp2_crypto_ossl.so                      libp11-kit.so
libpcre2-8.so         libssh2.so             libssl.so.3
libtasn1.so           libunistring.so        libz.so.1
libzstd.so.1
```

The extractor traverses actual `DT_NEEDED` entries from `qemu-img` and the new
JNI library. Missing, extra, renamed, or nonmatching SONAME libraries fail. It
allows only the explicit Android system-library set from
`prep_tools_common.py`. The original ELF RUNPATH names Termux directories, so
execution must set `LD_LIBRARY_PATH` to this bundle's `lib` directory. No APK
installation or private app directory is required.

## Linux helper and unpacking requirements

The helper inputs are byte-identical renamed APK assets:

| Output | Bytes | SHA256 |
| --- | ---: | --- |
| `helper/Image16k.gz` | 14,699,489 | `f18bca1a0cc68d8c2bce7809d76523a61c367392c81a986c81ede9db578f8dcf` |
| `helper/initrd.gz` | 28,853,976 | `7dff81e88f5e6261ae206c6c481f53748374d76ebd433be7b263f34c571a4a24` |

Static inspection of the initrd's 2,402 CPIO members found its `/init`,
`/asoft/job-run.sh`, Python 3.12, Bash, `apfs-fuse`, `rsync`, `tar`,
`mkfs.hfsplus`, `losetup`, mount utilities, and ext4 tools. The job runner reads
disks by virtio serial (`in`, `out`, and the `.job/disks` map), executes the
authored `.job/run`, and reports bounded exported bytes as `ASOFT: out N` and
the helper completion as `ASOFT: done RC`. This is a static inventory, not a
claim of a successful Linux or iOS boot on the phone.

There is no separate `img4` or `dmg` executable requirement in this path.
Current `Unpack.java` handles IM4P extraction and authenticated AEA decryption,
using its JNI LZFSE decoder. The existing helper uses `apfs-fuse` for the
decrypted image. `IpswFetch` retains the established range/ZIP logic, with
`CdnEdges` and `Io` included unchanged. The adapter adds strict request/result
boundaries and reports exact file identities; it preserves encrypted AEA input.

The released `libunpack.so` must **not** be paired with current `Unpack.java`:
the release exports LZFSE and hole punching but lacks `syncDirectory`, which
the current code uses for durable AEA checkpoints. The builder therefore
compiles the current committed `unpack.c` and the four committed LZFSE decoder
C files into a small API-29/16-KiB `libunpack.so`. It checks all three JNI export
names and records the complete C/header/license source inventory.

## Build and package on the host

Obtain the official tools with their normal publisher integrity checks:

- R8 `8.7.18`: <https://dl.google.com/dl/android/maven2/com/android/tools/r8/8.7.18/r8-8.7.18.jar>
  (SHA256 `58366f77067207c39a17d469de7b05701d2877212a9c55201bcb0af43e59e903`).
- Android platform `35_r02`: <https://dl.google.com/android/repository/platform-35_r02.zip>
  (SHA256 `0988cacad01b38a18a47bac14a0695f246bc76c1b06c0eeb8eb0dc825ab0c8e0`).
  Extract only `android-35/android.jar` and
  `android-35/core-for-system-modules.jar` for this build. Their hashes are
  pinned by the builder.

The available Java 21 runtime includes the javac module. Invoke it through
`java com.sun.tools.javac.Main`; no new JDK or Android SDK installation is
needed. The unchanged sources are Java-8-compatible and compile against the
Android core/framework boot API, followed by D8 with min-api 29. The compiler
metadata explains the obsolete-source/target option and existing serial UID
lint exclusions; remaining diagnostics are fatal and emitted warning text is
rejected. This avoids resolving app code against the host Java 21 API.

```sh
python3 -B build_prep_inputs.py \
  --source APP_CHECKOUT \
  --adapter ADAPTER_CHECKOUT/tools/pixel-powervr/experiments/cpu-shadow/standalone/PrepareInputs.java \
  --ndk ANDROID_NDK_R29 \
  --r8 R8_JAR --android-jar ANDROID_JAR --core-jar CORE_FOR_SYSTEM_MODULES_JAR \
  --out NEW_INPUTS_DIRECTORY

python3 -B package_prep_tools.py \
  --source APP_CHECKOUT --apk EXACT_RELEASE_APK \
  --inputs-build NEW_INPUTS_DIRECTORY --out NEW_PACKAGE_DIRECTORY
```

The input JNI/Java and setup source commits must agree; the separately
committed adapter is recorded independently. All source bytes and tool hashes
are checked again before a successful build/package receipt is written.
The small ZIP contains the extractor, common integrity code, pinned release
inventory, extraction plan, and current payload. The full 65 MB bundle stays
outside the qualification package.

## Extract and verify on the phone

The caller first downloads the exact existing release APK over normal
authenticated HTTPS and verifies the whole-file identity. Keep that APK as an
input file; it is never installed. Transfer the small stager ZIP and verify
its receipt SHA256 before unpacking it into a new directory.

```sh
python3 -B extract_prep_tools.py \
  --apk EXACT_RELEASE_APK \
  --plan tooling-plan.json --plan-sha EXPECTED_PLAN_SHA256 \
  --out NEW_TOOL_BUNDLE
```

Only the fixed APK member whitelist and exact plan-pinned payload files may be
read. Duplicate JSON/ZIP names, symlinks, unsafe paths, changes in any hash or
length, unexpected files, and existing outputs are refused. The extractor
writes non-executable files into an owned temporary directory, checks actual
ELF dependency closure and matching JNI/DEX build records, then rechecks the
entire APK and payload before setting final modes and publishing the bundle.
The DEX is pinned to mode `0444` (read-only) before Android loads it; ordinary
source/metadata files use `0644`, and native executables/libraries use `0755`.
Failure removes only its own temporary directory. It never changes the APK,
payload, existing qualification package, or neighboring directories.

The receipt prints the exact `tooling-manifest.json` SHA256. Supply that value
to the preparation runner's `--tooling-sha256`; the runner validates the
complete relative-path inventory, bytes, hashes, and integer POSIX modes.

The Java entry point is `com.asoft.ios.PrepareInputs`. Execution uses the
Android runtime environment (including `BOOTCLASSPATH`), the verified bundle
library path, and `CLASSPATH=BUNDLE/java/classes.dex`:

```sh
CLASSPATH=BUNDLE/java/classes.dex LD_LIBRARY_PATH=BUNDLE/lib \
  /system/bin/app_process -Djava.library.path=BUNDLE/lib /system/bin \
  com.asoft.ios.PrepareInputs REQUEST_JSON
```

The request's explicit `result_file` inside its owned `output_root` is the
authoritative completion record. A process exit code or empty output alone
does not indicate a successful fetch/decrypt. All network operations retain
normal certificate verification. Neither this builder nor extractor exercises
phone networking, native execution, Linux helper boot, or iOS boot.

## Host verification

`python3 -B test_prep_tools.py` covers the exact whitelist, rejection of old
QEMU/old JNI/Apple-image members, immutable released-member identities,
payload source selection, unsafe paths/modes, duplicate JSON, symlinks,
streamed size/hash checks, publication modes, existing-output preservation,
precreation refusal, and malformed ELF input. A separate actual-APK rehearsal
checks every installed byte and mode against the plan and preserves its input
files. The host receipt records the real artifacts and bounded scope.
