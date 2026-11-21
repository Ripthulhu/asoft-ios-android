# Android QEMU26 build reconstruction

This checked-in directory preserves the working scripts, input pins and build
records. To replay their original layout, copy this directory to
`qemu26-build-reconstruction/` beside the pinned `qemu-pixel-android-build`,
`reims-pixel-android-link`, `metal2vulkan-tile-runtime` and `tooling` directories
described below. The records retain original absolute paths as evidence;
they are not instructions to modify an unrelated checkout at those paths.
The Rust scripts currently expect the recorded `/home/agent/.cargo/bin`
toolchain location. Adapt that location explicitly on a different host.

Compiled engines, extracted dependencies and large compiler caches are omitted
from this source checkpoint. `loader-package/` contains the smoke script and
hash/closure records only, not an independently runnable copy of the package.
The pinned signed Termux metadata is retained in `downloads/`; package archives
are fetched and hash-verified by `scripts/fetch_termux.py`.

This is an isolated source-build preparation for the Pixel work, created on
2026-11-21. It does not replace the app's engine, enable a GPU compatibility gate,
change the phone, or establish an iOS boot. Native EL0 remains a required runtime
route. QEMU's AArch64 TCG target contains `target/arm/tcg/native-el0.c`; retaining
that target is necessary but does not prove the native engine executes guest
instructions successfully.

## Exact sources

| Component | Pinned input |
| --- | --- |
| QEMU fork | `alpersamur3/qemu-sptm`, `7a900afb62ddf94713e38ac5a4aafe1d42c9efa8`, version 11.1.0 |
| reims C API | `alpersamur3/reims-vgpu`, `2e568fba381bca9470e2df14c7029c3a402797b0` |
| metal2vulkan tile candidate | `ffda2ffd9485b6796ad8ca49bc024bf97401342c` |
| Android NDK | r29, `29.0.14206865`, Linux x86-64 host |
| Rust | 1.98.1, `aarch64-linux-android` standard library |
| Target compiler | `aarch64-linux-android29-clang` |
| Meson | 1.11.1, wheel already committed in the pinned QEMU checkout |
| Ninja | 1.13.0, pinned wheel in the input manifest |
| keycodemapdb | `f5772a62ec52591ff6870b7e8ef32482371f22c6`, exactly QEMU's wrap revision |
| Termux recipes and keys | `78335abe27295e118127e373370e7cb92cf26331` |

The QEMU commit describes itself as a readback of the 0.1.6 phone engine. That
statement is recorded as upstream provenance, not treated as proof of the
release `libqemu26.so`'s source revision or byte-for-byte reproduction. The
verified v0.1.6 APK inventory remains a separate reference.

The prepared reims and metal2vulkan commit IDs are local development identities,
not assumed to be fetchable from the upstream repositories. Reconstruct them from
the public bases and ordered patch series already in the app kit. Their manifests
are copied into `provenance/`; expected final trees are
`f94e8a04f9e1c461e5db1aaa4c4935135edc4cbe` (reims) and
`9fe786a921829ccdb51b2d977c0dbf30f7173962` (metal2vulkan). The build source trees
were checked against those identities before the local path override.

The two build worktrees are `../qemu-pixel-android-build` and
`../reims-pixel-android-link`. The latter changes only the three workspace patch
paths in Cargo.toml to the frozen `../metal2vulkan-tile-runtime` checkout.
`provenance/reims-path-override.patch` preserves that exact change. The product
memory backend is unchanged; the producer allocation and adoption experiments
are not integrated here.

## Verified Android dependency set

`termux-lock.json` pins the package records, repository metadata hashes, sizes and
SHA-256 values. The `InRelease` snapshot dated 2026-11-21 15:02:05 UTC is signed by
fingerprint `CC72CF8BA7DBFA0182877D045A897D96E57CF20C`. Its signature is verified
against the exact Termux repository keys from the pinned recipe commit, using an
isolated GnuPG home. No owner-trust change is made.

The required development headers and matching libraries come from glib, zlib,
libpixman, dtc/libfdt, libslirp, libnettle, libgmp and zstd, with their selected
transitive packages. Packages are extracted with `dpkg-deb -x`; their maintainer
scripts and ARM64 executables are never run on the host. These are newly pinned
matched development/runtime inputs, not a claim that they are identical to the
APK's older bundled dependencies. A resulting binary must use the matching
qualified runtime closure rather than mixing library sets by name.

`provenance/termux-elf-closure.json` records the ELF closure of the selected entry
libraries and hashes each file. There are no unresolved non-system dependencies
in that inventory. Package manager dependencies used only by package CLI tools
are not executed or inferred to be QEMU runtime dependencies.

`prepare_qemu.py` writes relocated copies of target `.pc` files and a wrapper
whose `PKG_CONFIG_LIBDIR` includes only those copies and the actual reims dist
directory. It clears host `PKG_CONFIG_PATH` and `PKG_CONFIG_SYSROOT_DIR`, avoiding
host GLib detection and accidental double-prefixing of reims paths.

## Android coroutine dependency

The pinned Termux QEMU recipe builds a private ARM64 setjmp/longjmp archive to
support QEMU's coroutine switching on Android. The four exact source files and
their original licenses are retained under `provenance/termux-setjmp/`; their
URLs, Git blob identities and SHA-256 values are in `termux-setjmp.json`.
`prepare_qemu.py` copies them without source edits, builds the archive with the
same NDK, and records its commands and hash.

This implementation intentionally avoids Bionic's private setjmp cookie checks,
as described by the Termux compatibility workaround. It affects only this linked
executable, not system libc or phone policy. The verified release engine does
not import setjmp/longjmp symbols, which is consistent with private linkage but
does not prove identical shim bytes. Its compatibility with the eventual native
stub workload still needs bounded device qualification.

Primary references:

- https://github.com/termux/termux-packages/issues/12261
- https://github.com/termux/termux-packages/blob/78335abe27295e118127e373370e7cb92cf26331/packages/qemu-system-x86-64-headless/build.sh
- https://github.com/termux/termux-packages/tree/78335abe27295e118127e373370e7cb92cf26331/packages/qemu-system-x86-64-headless/setjmp-aarch64

## Build sequence

Restore the pinned checkouts, NDK and Rust target at the paths above. Run `scripts/setup_host_tools.py` to create the
`host-tools` Python virtual environment and install the recorded, hash-checked
Meson, pycotap, qemu-qmp and Ninja wheels. Restore the pinned keycodemapdb revision under QEMU's
`subprojects/keycodemapdb`. The preparation scripts expect that layout; all paths
and commands they use are written to provenance records.

```sh
python3 scripts/setup_host_tools.py
python3 scripts/fetch_termux.py
python3 scripts/prepare_qemu.py
python3 scripts/build_reims.py
python3 scripts/configure_qemu.py
python3 scripts/build_qemu.py
```

Restore `provenance/reims-Cargo.lock` as the reims checkout's `Cargo.lock`; fetch
its locked dependencies on a connected development host before the offline
build if they are not already cached. The final recipe passes both `--offline`
and `--locked`.

The reims build uses two Cargo jobs and a dedicated target directory outside the
source tree. It uses the normal Vulkan feature and embeds no fake device
capabilities or software-ICD configuration. Its actual `--print native-static-libs`
output supplies the pkg-config static link dependencies. The configure script
refuses to proceed without a successful real archive and a matching archive
hash; there is no placeholder reims library.

QEMU retains default devices and explicitly enables AArch64 system emulation,
TCG, KVM build support, reims, nettle, pixman, libfdt, slirp and zstd. KVM being
compiled is not a claim about device access or usability. Nettle is necessary
because the vresearch Apple AES path must have a real AES backend; disabling
crypto would produce a superficially buildable but unsuitable iOS26 engine.
Desktop frontends and unnecessary optional services are disabled for this
initial source-build reconstruction. `-fno-emulated-tls` retains the fork's
intended native TLS path, whose source supplies the required 64-byte ELF TLS
alignment. Both ELF page-size link arguments request 16 KiB alignment.

## CPU and warning requirements

The reims raw ARM64 access module emits `ldsetal` and `ldapr`, so the build
explicitly enables stable Rust `+lse,+rcpc` code generation. The module also
assumes FEAT_LSE2 within-granule atomicity and ARM Normal-memory access semantics.
No compiler flag alone qualifies a CPU or memory provider. The eventual Pixel
runtime evidence should include HWCAP_ATOMICS, HWCAP_LRCPC and HWCAP_USCAT, and
actual guest RAM access tests. GPU coherent memory is not thereby proven suitable
as fast native RAM.

The initial unqualified ARMv8 build failed on `ldsetal`; its log and metadata are
preserved. The next attempt reached the desktop window crate and found seven
unused-code diagnostics in Android-disabled presentation paths. That failure is
also retained. The final recipe permits only `dead_code` warnings while keeping
other Rust warnings denied; this is a recorded cross-build exception, not a
claim that the unchanged upstream tree passed a universal warnings gate. The
unstable `lse2` compiler option is omitted; its hardware contract remains.

## Validation status

- Signed repository metadata and all selected package checksums: verified.
- Selected target ELF dependency closure: complete.
- Target-only pkg-config version checks: passed.
- QEMU's exact three reims ABI size assertions: passed with Android clang and
  `-Werror`; source, command and result are retained under `checks/` and
  `provenance/reims-abi.json`.
- Real reims Android release archive: built successfully. The initial full build
  took 8m09s; the final locked Cargo replay was cached. The upstream dist
  localization step was reproduced with target LLVM tools; only `rvg_*` C API
  symbols remain global. The staged archive is 836,007,138 bytes, SHA-256
  `73e4bfd29c962fea7f46ed34519309ff2de9cfbf7e8756a4efb6822a3bbf3138`.
  See `provenance/reims-build.json` and the preserved full compilation log.
- QEMU configure, compile and final link: passed. The build completed all 2,100
  Ninja steps, including `native-el0.c`, the vresearch machine and actual reims
  linkage. `provenance/qemu-build.json` records the enabled configurations,
  native symbols and ELF metadata. A subsequent incremental build completed
  successfully with no change to the linked binary; its separate record is
  `provenance/qemu-build-replay.json`.
- Stripped Android executable: 58,510,368 bytes, SHA-256
  `48914a38400c2f38ac127a3ba8f0db2ffa603f28bd0a17c65e59fc3b644447ce`.
  The interpreter is `/system/bin/linker64`, all `LOAD` segments are aligned to
  16 KiB, and TLS is aligned to 64 bytes. The unstripped link remains available
  for symbol inspection and debugging.
- The C build completed with 124 pre-existing-source diagnostics: 110 macro
  redefinitions, 11 format warnings, one missing prototype, one nonnull warning,
  and one format-truncation warning. The complete log is retained; this is not a
  warning-clean build.
- Device loading, native guest execution, combined GPU memory behavior and iOS
  boot: not established by this source build.

The source commit pins, manifest patch, original failed logs, final commands,
dependency signatures and byte hashes make each result reviewable. An eventual
successful build still leaves the producer memory bridge, fragmented GPU ranges,
native executable-page coherence and actual iOS26 boot as separate work.

## Isolated loader package

`python3 scripts/package_qemu_smoke.py` packages the exact stripped executable
and its 12 non-system shared libraries under `dist/qemu26-loader-smoke/`, with a
ZIP beside it. The script traverses `DT_NEEDED`, verifies each library against
the previously qualified dependency hashes, checks AArch64 and 16 KiB `LOAD`
alignment, and records each file's original SONAME and RUNPATH. It refuses to
overwrite an existing package directory.

The archive is 20,118,769 bytes with SHA-256
`0b51b6f0bd8d82abf5b2f764e76199db018f1cec7e37836512ae2421c99ec227`.
Its payload hashes and ZIP integrity were verified locally. No target binary
was executed on the build host.

The package's `loader-smoke.sh` verifies hashes and runs only `-version`,
`-machine help` and `-accel help`, with a 10-second bound on each. It uses a
clean environment and a private `LD_LIBRARY_PATH` containing the matched
libraries; inherited native-stub settings do not reach the executable. Results
go under the package's own `results/` directory. This is a loader and machine
registration check, not a guest boot or an installed engine replacement.

The original binary has a build-directory RUNPATH and the Termux libraries
have a Termux RUNPATH. These are retained and documented rather than silently
rewritten. The smoke wrapper selects the private bundled closure explicitly.
No system libc or Vulkan driver is bundled. A product APK integration still
needs its own packaging and runtime validation.
