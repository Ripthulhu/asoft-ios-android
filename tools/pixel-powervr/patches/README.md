# Candidate native backend patches

These two ordered series implement an initial PowerVR color-fetch path and the
memory integration needed to investigate it in the Android fork. Apply each
series to its own dependency repository at the exact base below. The app uses
separately built native libraries; these files do not replace them automatically.

The full implementation boundary is in [BACKEND.md](../BACKEND.md), and observed
results and limits are in [VALIDATION.md](../VALIDATION.md).

## Source identities

| Dependency | Exact base | Prepared source revision |
|---|---|---|
| [metal2vulkan](https://github.com/alpersamur3/metal2vulkan) | `5951098336923a231a011578d8722449a3981034` | `ffda2ffd9485b6796ad8ca49bc024bf97401342c` |
| [reims-vgpu](https://github.com/alpersamur3/reims-vgpu) | `3e0467e64b4c21b6087ae3589388fec5154fb0cb` | `2e568fba381bca9470e2df14c7029c3a402797b0` |

Prepared revision IDs identify the development commits that produced these
patches. They are not claimed to be published commits in the dependency
repositories. `git am` can produce different commit IDs because committer
metadata changes; the final source-tree hashes in the manifests are the
reproducibility check.

## Ordered series

### metal2vulkan

| Order | Patch | Source commit |
|---:|---|---|
| 1 | [0001-Allow-dma-buf-imports-without-host-pointer-extension.patch](0001-Allow-dma-buf-imports-without-host-pointer-extension.patch) | `629f6e095983` |
| 2 | [0003-Expose-coherent-tile-image-framebuffer-fetch-contracts.patch](0003-Expose-coherent-tile-image-framebuffer-fetch-contracts.patch) | `0a7360d4a4f4` |
| 3 | [0004-Lower-coherent-color-fetches-to-shader-tile-images.patch](0004-Lower-coherent-color-fetches-to-shader-tile-images.patch) | `629df0d091a4` |
| 4 | [0005-Record-tile-image-draws-through-dynamic-rendering.patch](0005-Record-tile-image-draws-through-dynamic-rendering.patch) | `9d824ae890b7` |
| 5 | [0006-Compose-deferred-host-gathering-with-same-page-DMA-BUF-import.patch](0006-Compose-deferred-host-gathering-with-same-page-DMA-BUF-import.patch) | `864b0a038ef1` |
| 6 | [0007-Clarify-materialized-gather-answers-and-contract-tests.patch](0007-Clarify-materialized-gather-answers-and-contract-tests.patch) | `8dacca27d07f` |
| 7 | [0008-Version-combined-tile-rendering-and-deferred-import-runtime.patch](0008-Version-combined-tile-rendering-and-deferred-import-runtime.patch) | `ffda2ffd9485` |

Expected final tree: `9fe786a921829ccdb51b2d977c0dbf30f7173962`.

### reims-vgpu

| Order | Patch | Source commit |
|---:|---|---|
| 1 | [0002-Use-aliasable-backing-for-detached-buffer-temporaries.patch](0002-Use-aliasable-backing-for-detached-buffer-temporaries.patch) | `689674ad60c5` |
| 2 | [0009-Import-deferred-memory-without-host-pointers.patch](0009-Import-deferred-memory-without-host-pointers.patch) | `7c14daa7a924` |
| 3 | [0010-Negotiate-Vulkan-1.3-with-the-selected-loader.patch](0010-Negotiate-Vulkan-1.3-with-the-selected-loader.patch) | `2e568fba381b` |

Expected final tree: `f94e8a04f9e1c461e5db1aaa4c4935135edc4cbe`.

The initial importer change is a backport of the capability separation in
[upstream metal2vulkan commit 12a8a907](https://github.com/steelbrain/metal2vulkan/commit/12a8a907bcdd3c7ae5683ee436e83e42fd6397a4).
The remaining patches adapt the pinned Android sources. The existing initial
importer and detached-buffer patch files were preserved byte for byte.

## Apply in dependency checkouts

The commands below use a POSIX shell on the development host. Point the variable
at this directory in your app-fork checkout, then work in clean checkouts of
the respective dependencies.

```sh
export POWERVR_PATCH_DIR="/absolute/path/to/asoft-ios-android/tools/pixel-powervr/patches"
```

Inside the `metal2vulkan` checkout:

```sh
git switch -c pixel10-powervr-candidate 5951098336923a231a011578d8722449a3981034
git am "$POWERVR_PATCH_DIR/0001-Allow-dma-buf-imports-without-host-pointer-extension.patch" \
  "$POWERVR_PATCH_DIR/0003-Expose-coherent-tile-image-framebuffer-fetch-contracts.patch" \
  "$POWERVR_PATCH_DIR/0004-Lower-coherent-color-fetches-to-shader-tile-images.patch" \
  "$POWERVR_PATCH_DIR/0005-Record-tile-image-draws-through-dynamic-rendering.patch" \
  "$POWERVR_PATCH_DIR/0006-Compose-deferred-host-gathering-with-same-page-DMA-BUF-import.patch" \
  "$POWERVR_PATCH_DIR/0007-Clarify-materialized-gather-answers-and-contract-tests.patch" \
  "$POWERVR_PATCH_DIR/0008-Version-combined-tile-rendering-and-deferred-import-runtime.patch"
git rev-parse HEAD^{tree}
```

The last command should print `9fe786a921829ccdb51b2d977c0dbf30f7173962`.

Inside the `reims-vgpu` checkout:

```sh
git switch -c pixel10-powervr-candidate 3e0467e64b4c21b6087ae3589388fec5154fb0cb
git am "$POWERVR_PATCH_DIR/0002-Use-aliasable-backing-for-detached-buffer-temporaries.patch" \
  "$POWERVR_PATCH_DIR/0009-Import-deferred-memory-without-host-pointers.patch" \
  "$POWERVR_PATCH_DIR/0010-Negotiate-Vulkan-1.3-with-the-selected-loader.patch"
git rev-parse HEAD^{tree}
```

The last command should print `f94e8a04f9e1c461e5db1aaa4c4935135edc4cbe`.

## Select the patched dependency for reims

Reims must build against all three crates from the patched metal2vulkan tree.
The pinned Android workspace contains an existing local patch path; the checks
recorded here supplied explicit Cargo configuration without editing its pins.
For a local build, create a Cargo config file with the actual absolute paths:

```toml
[patch."https://github.com/steelbrain/metal2vulkan"]
metal2vulkan = { path = "/absolute/path/to/metal2vulkan/crates/metal2vulkan" }
metal2vulkan-runtime = { path = "/absolute/path/to/metal2vulkan/crates/metal2vulkan-runtime" }
metal2vulkan-air = { path = "/absolute/path/to/metal2vulkan/crates/metal2vulkan-air" }
```

Pass that file as `cargo --config /absolute/path/to/powervr-deps.toml ...`.
The Android metadata check used the C facade:

```sh
cargo --config /absolute/path/to/powervr-deps.toml check \
  -p reims-vgpu-c --no-default-features --features vulkan \
  --target aarch64-linux-android
```

It used Rust 1.98.1 and Android NDK r29 linker configuration. A metadata check
does not link the Android library. Rebuilding the QEMU/reims native bundle and
the APK is a further integration step; the app repository consumes those
libraries through its existing native-build workflow.

## Verification and remaining requirements

Both series were applied from their exact bases in isolated temporary Git
indexes. Every intermediate tree matched its source commit, and the final
trees matched the tested source. The source working indexes were unchanged.
Per-file SHA-256 values and the reconstruction record are in
[metal2vulkan-series.json](metal2vulkan-series.json) and
[reims-series.json](reims-series.json).

The runtime tests, compiler tests, native reims results, Android metadata
check, and unresolved environment limitations are recorded in
[VALIDATION.md](../VALIDATION.md). A full workspace gate and corpus qualification
are not claimed. The standalone tile-image probe has passed on the Pixel, and
the DMA-BUF probe has returned an unsupported buffer-capability declaration;
see the [device test record](../results/2026-11-21/README.md). The patched runtime,
linked candidate Android library, APK, and iOS boot remain unvalidated on the
phone.

The tested kernel has a built-in UDMABUF exporter. The device still needs
compatible Vulkan buffer imports, memory types, usages, synchronization and
integrated rendering semantics. The application support check and conservative
guest capability advertising remain unchanged.

## Licenses

The standalone probe kit has its own MIT license. These dependency patches
retain `GPL-2.0-or-later OR LGPL-3.0-or-later`, with their original notices:

- [metal2vulkan notice](licenses/LICENSE) and adjacent GPL/LGPL texts.
- [reims-vgpu notice](licenses/reims-vgpu/LICENSE) and its `LICENSES` directory.
