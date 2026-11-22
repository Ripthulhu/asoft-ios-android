# Portable HFSX recovery on the Pixel

The portable path recovers an unmounted raw volume into a new image. It uses
the pinned [go-apfs-v3 recovery engine](https://github.com/deploymenttheory/go-apfs-v3/tree/c378f4780357eb5fd80e5f39b0c3742b28c9910c).
It validates committed records, applies the updates to private scratch,
checks the recovered allocation and metadata graph, and sets the primary
unmounted flag. The wrapper flushes and publishes a new file without overwrite.

## Disposable qualification

On macOS, the recovered fixture matched Apple's replay-only result byte for
byte after setting the single validated unmounted bit on the reference. The
portable image then passed an independent read-only `fsck_hfs -fn` with its
hash intact. [macOS comparison](https://github.com/Ripthulhu/asoft-ios-android/actions/runs/45082166905).

The pinned ARM64 Linux build ran on the Pixel as the shell UID. The synthetic
journal moved from `512..12800` to `12800..12800`, the catalog FinderInfo
value was restored, and the unmounted bit was set. A separate native Linux VM
opened the result read-only and ran `fsck.hfsplus -f -n`. It exited zero and
reverified the raw image hash.

| Disposable evidence | SHA-256 |
| --- | --- |
| ARM64 recovery executable | `5fcdc7e9370a9613e96a9d7aea4ebfc21b4d16413d9a8ec4d1d63b4af3ef564e` |
| Pending fixture, preserved | `4f3c23d42d26fd0de77da4271a2e3f1b50d869793d2876594e772411fea53456` |
| Recovered fixture | `15cb36d3745e0278dc424d9c065ba84f66c9f6ed35d20215269dd02accbc202f` |
| Pixel read-only checker receipt | `d4d33381195d248174922b285a74769b2eb02f0f5d70426ed15d3aff1907c363` |

The Pixel's pinned `qemu-img` was also tested on a small QCOW2 descendant
with a patterned raw backing image. A scoped partition replacement preserved
the backing image and both neighboring ranges. Full subrange extraction and
comparison matched, including the replacement of existing data with zeros.

The ARM64 build and synthetic inputs came from
[the disposable transport run](https://github.com/Ripthulhu/asoft-ios-android/actions/runs/45082307499).
All saved Data reads and recovery work are local to the phone.
