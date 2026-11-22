# Native header reader: input-open evidence

Checked on 2026-11-22. No phone action, runtime source change, or header read was
performed by this analysis.

## Exact released binary versus native source

The tool is the release APK's `lib/arm64-v8a/libqemuimg.so`, installed as
`/data/local/tmp/pixel-tools-1528a782/tools/qemu-img`: 2,356,032 bytes, SHA-256
`1bd2fd6b968c492d0263436c260af2a8c2ee807cf4afd4fd2abb3300446e2440`.
Its reported version is `11.1.0 (ASoftware-android)`. The app release tag resolves
to `869a82690c1a4d846683319d9d15e75bfcbc50c2`.

The committed `tools/pixel-powervr/ios26-build/PROVENANCE.md` and
`tools/pixel-powervr/experiments/cpu-shadow/PREPARATION-TOOLS.md` explicitly
distinguish those byte identities from an exact native source commit or a
reproducible native build from the app tag. No such exact qemu-img source
binding was found. **No writable-input defect has been observed.** The missing
source binding is an evidence limit, not evidence that `dd` opens its input
writable.

## Primary upstream evidence

Read through the GitHub read API, then re-read at the exact commit:

- Repository: `qemu/qemu`.
- Commit: `aa0d2a4006353c12dfd702e7d9f609259be2b086`.
- `qemu-img.c` Git blob: `edf75e43abad11d32cd04f8cafb5fefb74c7569c`.
- [Pinned source](https://github.com/qemu/qemu/blob/aa0d2a4006353c12dfd702e7d9f609259be2b086/qemu-img.c).

In `img_dd`, line 5550 opens the input through `img_open` with flags `0`.
Line 5623 opens the output with `BDRV_O_RDWR`. This supports the ordinary
read-only input contract; applying that implementation to the custom release
remains an inference because its native source identity is not established.

There is a separate, concrete skip/count compatibility question. This source
limits `size` to `count * block_size` **before** subtracting the skipped input
offset (lines 5595–5607). In that implementation, `count=1,skip=2,bs=512`
produces no data, whereas `count=3,skip=2,bs=512` selects one sector. Its
command-specific help omits `skip` despite the parser supporting it. These are
upstream source findings, not yet observations of the pinned Android binary.

## Smallest supported diagnostic contract

Retain the fixed-format `dd` input and fresh owned output, without adding an
extra parser requirement solely because native source provenance is missing.
The bounded synthetic test should establish the actual binary's skip/count
semantics and exact output length/content before using any saved disk. Keep
the exact tool pin, existing input/backing-chain validation and exclusivity,
bounded child/log/output handling, and unchanged-input checks. Use no repair,
snapshot, commit or force-share option.

The [official qemu-img manual](https://www.qemu.org/docs/master/tools/qemu-img.html)
documents `--image-opts` as an alternative to `-f`; the
[block-node reference](https://www.qemu.org/docs/master/system/invocation.html)
documents explicit `read-only` node options. These provide an optional
alternative contract if specifically selected and tested. They are not a
newly required gate, and do not resolve the separate skip/count behavior.
