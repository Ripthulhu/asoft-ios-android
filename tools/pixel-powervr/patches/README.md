# Candidate DMA-BUF-only importer backport

`0001-Allow-dma-buf-imports-without-host-pointer-extension.patch` adapts the
capability separation from upstream commit
[`12a8a907bcdd3c7ae5683ee436e83e42fd6397a4`](https://github.com/steelbrain/metal2vulkan/commit/12a8a907bcdd3c7ae5683ee436e83e42fd6397a4)
to the older Android fork.

Target: `alpersamur3/metal2vulkan`, branch `asoft-android`, base
`5951098336923a231a011578d8722449a3981034`.

The candidate commit is `629f6e09598313b9ebf22032ae8ecc6493d30f1a` in the
development checkout used to produce this patch. It is not an upstream commit
or an application release.

## Contract

An importer can exist when the device has a DMA-BUF route but lacks
`VK_EXT_external_memory_host`. Host-pointer functions and alignment belong to
a separate `PointerImport`; pointer-only operations still refuse unsupported
inputs. The older `GatherSource` path is guarded rather than made to pretend it
can import host pointers.

This covers the importer and related buffer, heap and rebind paths. It does not
change guest capability advertising or the Android application's GPU check.
In particular, `SupportsResourceDetachBacking` still keys off the host-memory
extension in this pinned runtime. That conservative underreporting remains an
integration issue to resolve with actual guest evidence.

The runtime still requires compatible `HOST_VISIBLE | HOST_COHERENT` memory.
It needs a source for the original pages; anonymous allocations in reims are
not converted to memfds by this patch. There is no framebuffer-ordering backend
change in this patch.

## Apply for development

Use a separate working branch of the dependency at the exact base above. From
that dependency checkout, with `PATCH` set to the included patch's path:

```sh
git switch -c pixel10-dmabuf-candidate 5951098336923a231a011578d8722449a3981034
git apply --check "$PATCH"
git am "$PATCH"
```

The Android repository uses separately built native libraries. Storing this
patch here does not rebuild or replace those libraries and does not produce a
PowerVR-capable APK.

## Verification and limits

- `cargo test -p metal2vulkan-runtime --lib tests::host_memory --all-features`:
  **17 passed**, including an eight-combination mock-dispatch regression for
  extension presence, pointer importability and DMA-BUF availability.
- `cargo clippy -p metal2vulkan-runtime --lib --tests --all-features -- -D warnings`:
  passed.
- `RUSTDOCFLAGS='-D warnings' cargo doc -p metal2vulkan-runtime --all-features --no-deps`:
  passed.
- Refusal reference regenerated and checked; patch whitespace checked.

These checks do not execute a GPU. No Android runtime build, Pixel DMA-BUF
import, complete upstream gate, or iOS boot is claimed for this candidate.

The patch retains `metal2vulkan`'s
`GPL-2.0-or-later OR LGPL-3.0-or-later` licensing. Its original notice and license
texts are included in `licenses/`.
