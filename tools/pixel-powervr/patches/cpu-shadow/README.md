# CPU-authoritative GPU source exports

These binary-capable Git patches reproduce the committed QEMU, metal2vulkan and
reims source trees below. Reconstruction is verified. The exact Android
diagnostic candidate built from these sources **passed all fourteen authored
cases on the Pixel 10 Pro XL**; the complete evidence is in
[`full-run-afdbdd0`](../../experiments/cpu-shadow/device-checks/full-run-afdbdd0/README.md).
The capability-enabled product path, iOS TPIDRRO swap mode and Apple guest boot
remain unqualified. No APK was built. Component manifests retain their earlier
export-time status; the linked execution record describes the later physical run.

| Component | Required base commit | Exported source commit | Complete source tree |
| --- | --- | --- | --- |
| qemu | `7a900afb62ddf94713e38ac5a4aafe1d42c9efa8` | `755b88fad8a2771a8e3e207133a54898b740cd7f` | `d1def5a49eaec302e46d8fa28aeaf5a227d02ecb` |
| metal2vulkan | `7aaf60f105544b70b4cf25f9eb44ace4b00a61fd` | `51c322d883ea723d290c931b3b2013c50f5e4934` | `1b8c0eff2356c3a05cc372b6ea25e74cbdeff8d0` |
| reims | `c3551c742dfa826ea8e4aecf5affc22bf508822b` | `afdbdd0c3c13710bf0565ef9365f0a9d890b207d` | `67f1860dc72f8cffff6bc6a79a9f5919be3bcc88` |

Each component's `source.json` preserves its patch name, size, SHA-256, changed
paths and exact reconstruction result. The metal2vulkan base is prepared by
`../producer-adoption`; the reims base by `../reims-host-validation`. These
increments do not replace or alter those earlier patch series or their licenses.

## Verify and apply

Run `sha256sum -c SHA256SUMS` in this directory. In a separate clean checkout at
the component's recorded base, apply its patch with `git apply --index` and check
`git write-tree` against `source_tree` in its manifest. These are raw Git diffs,
not mail patches; `git am` is not the application method. The resulting commit
ID may differ, but the complete Git tree must match exactly.

## Repeat the export

The helper takes explicit source and output paths and captures all three HEADs
before generating any patch. Optional expected heads make a pinned rerun fail
if a checkout has advanced. Omit or update those checks intentionally when
exporting a later committed capability change. Base commits also have explicit
`--qemu-base`, `--metal2vulkan-base` and `--reims-base` overrides; their defaults
are the required bases above.

```sh
python3 ../../experiments/cpu-shadow/export_sources.py \
  --qemu-source /absolute/qemu-cpu-shadow \
  --metal2vulkan-source /absolute/metal2vulkan-paged-shadow \
  --reims-source /absolute/reims-pixel-apk-runtime \
  --out /absolute/asoft-ios-android/tools/pixel-powervr/patches/cpu-shadow \
  --expect-qemu-head 755b88fad8a2771a8e3e207133a54898b740cd7f \
  --expect-metal2vulkan-head 51c322d883ea723d290c931b3b2013c50f5e4934 \
  --expect-reims-head afdbdd0c3c13710bf0565ef9365f0a9d890b207d
```

Only committed differences enter the patches. Local reims `Cargo.toml` path
overrides, staged/uncommitted edits and untracked files are excluded and their
paths recorded. Configure the three local metal2vulkan Cargo paths separately
for a build, as described by `../../experiments/cpu-shadow/README.md`.

The helper reconstructs each full tree in a temporary bare repository with its
own index and object directory. Source objects are read through Git alternates;
the original checkouts, indexes and remote refs are not written. It checks HEAD,
main-index bytes, tracked working differences, untracked contents and remote
refs again before publishing. Ignored build outputs are not part of that check.
All reconstruction and stability checks must pass before existing export files
are replaced. `SHA256SUMS` is written last, so an interrupted update cannot pass
the checksum check with mismatched files. Unrelated output files are left alone.
