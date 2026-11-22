# Staged native boot inspection sources

The Pixel received and hash-verified the reviewed partition auditor, firstboot
guard and saved-firstboot inspector on 2026-11-22. The two original install
receipts below were copied back byte for byte through the visible terminal;
their lengths and complete SHA256 hashes were checked before saving.

**This is source-transfer evidence. No physical partition audit, iOS firstboot
or saved-firstboot inspection is claimed.** The existing native rootfs copy was
still running. None of the four frozen preparation files was replaced.

| Receipt | Bytes | SHA256 |
|---|---:|---|
| `boot-install.json` | 734 | `eedc2b9ae4ec28e305f2cc40fcff320ce1214511d1c128fe8be528f5bf947064` |
| `saved-inspector-install.json` | 592 | `e15eff3d5609808e702e75b18c3c1852874ddcc1512713e8814663a8443570be` |

The first receipt binds local source commit `ebbc9c0e54006e59d1634fbb32893a9f5f10a98a`
and the 26,231-byte ZIP with SHA256
`2879d4a89a652b37418edfb1c3e09d52d78605e98bc8933b84235f8dbb1cf938`.
Its three files are under `/data/local/tmp/pixel-boot-checks-ebbc9c0`, in the
separate `auditor` and `firstboot` source directories.

The second binds local source commit `d4e0ac061e02a21d9139fa31ef853350c0cc176c`
and the 13,324-byte ZIP with SHA256
`1e50e0aaccc6cb0c02797d433823a11f05a5d39f88220677b372b8d5f7d76bd3`.
Its two files are under `/data/local/tmp/pixel-saved-checks-d4e0ac0`.
Each receipt records every individual source hash and the actual install time.
The archives were verified before extraction into fresh directories; every
extracted source was rehashed and set to mode 0644.

The [recovery index](../../CONTINUE-PIXEL.md) gives the exact staged commands,
unchanged preparation session and required order. Host test/review evidence is
documented in the [partition auditor](../../IOS26-PARTITION-AUDIT.md),
[firstboot guard](../../IOS26-FIRSTBOOT-GUARD.md), and
[saved-firstboot inspector](../../IOS26-SAVED-FIRSTBOOT-INSPECTION.md).
