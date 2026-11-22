# Durable HFSX journal replay on disposable macOS media

Apple’s replay-only HFS operation committed a journal on a 96 MiB,
case-sensitive HFS+ (HFSX) image. The macOS test generated the whole image
locally, wrote a known FinderInfo attribute, and put its complete catalog
node into a synthetic pending transaction. The original metadata value was
visible again both on disk immediately after replay and later through the
mounted filesystem. The sentinel file contents also matched.

| Gate | Observation |
| --- | --- |
| Journal before replay | Start 512, end 12800 |
| Apple replay-only operation | Returned 0 on the unmounted disposable device |
| Journal after replay-only and detach | Start and end 12800 |
| Unmounted flag after replay-only | Clear |
| Journal after ordinary mount and non-forced unmount | Start and end 30208 |
| Forced read-only fsck | Passed on a read-only attachment, with the image hash unchanged |

[Source and successful macOS run](https://github.com/Ripthulhu/asoft-ios-android/actions/runs/45081588558).
The earlier [mount-based control](https://github.com/Ripthulhu/asoft-ios-android/actions/runs/45081505436)
also passed. Both used freshly generated disposable images on GitHub’s hosted
Mac. The Pixel, its saved Data image and its Apple firmware inputs were outside
those runs.

## Reproduce

On a supported macOS host with Python 3.11 or newer, Xcode command-line tools
and noninteractive administrator access, run
`python3 qualify_macos_hfs_replay.py`. It accepts no disk or image argument
and creates its fixture in a new temporary directory. The helper checks for an
HFSX raw device with the fixture’s exact 96 MiB geometry. The caller binds the
device to the disposable image returned by `hdiutil`.

The named Apple operation is defined in
[hfs_mount.h](https://github.com/apple-oss-distributions/hfs/blob/d1bac2f062e6e9c0dfcce302d9aacb10173d0eea/core/hfs_mount.h#L78)
and [hfs_vfsops.c](https://github.com/apple-oss-distributions/hfs/blob/d1bac2f062e6e9c0dfcce302d9aacb10173d0eea/core/hfs_vfsops.c#L4492).
It replays the journal and flushes the raw device. The separate mount/unmount
qualified the clean volume state.

## Pixel recovery gate

The signed Darwin ramdisk helper and disposable-data route still require a
fresh qualified Pixel test. On this macOS fixture, durable replay alone left
the unmounted flag clear. A Pixel run that reaches only that stage still lacks
the clean-unmount evidence required by the saved-image inspection. Keep the
saved Data detached until the end-to-end recovery route is qualified.

A supported Mac can provide both native operations on a local disposable
copy. A portable candidate is the
[go-apfs-v3 completed-copy recovery tool](https://github.com/deploymenttheory/go-apfs-v3/blob/c378f4780357eb5fd80e5f39b0c3742b28c9910c/docs/hfs-journal-recovery.md),
which documents an Apple-backed comparison and separate graph validation
before marking a recovered copy unmounted. It has yet to be qualified for
this Pixel project.
