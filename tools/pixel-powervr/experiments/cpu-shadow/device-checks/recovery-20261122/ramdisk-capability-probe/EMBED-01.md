# First Linux ramdisk embedding experiment

The qualified native Linux helper attached a fresh writable 488 MiB ramdisk
copy, a read-only job tar and its own return buffer. It copied the signed
helper to `/bin/asoft-unmount` in the copy, verified its SHA-256, unmounted
the copy and ran `fsck.hfsplus -f -n`. The guest reported that the volume
appeared to be OK. Its retained selected receipt records `copied`,
`unmounted` and `readonly_fsck` as true, with helper SHA-256
`00e39e335386e61ee4c208d186a910b9daad40531b3d81d6feb5a2827f859b55`.

QEMU completed naturally with exit 0 and all native witnesses. The frozen
supervisor recorded six force-reaped descendants. The host therefore marked
the run `INCOMPLETE` and did not release the candidate image for Darwin.
A later check found all recorded processes absent. The original ramdisk and
bound receipts were reverified. The saved iOS Data image was outside this
job's attachment list.

| Retained item | SHA-256 |
| --- | --- |
| Embedding source | `bac6cf3811eb14b782505ac3144944eae2d72578783f91fdfc76c9676e71179e` |
| Host result | `8c9d735830dcd0af07c46df922af165ba85c0ae1899468cc04630f5f1bf9fcec` |
| VM result | `d4813fb32ae8b37cd78459ac881f17a168c3e889269212ad675b5a5a6b5eb06d` |
| Unaccepted 511,705,088-byte candidate | `ba5f01732889ae119c5d9f9dd0aa4fcea667af3ad3cceb73d4e469f439001a0e` |

Files are retained under `/data/local/tmp/asoft-rd-embed-01`. Preserve this
experiment. A fresh build still needs natural, unforced descendant
reaping before the modified ramdisk can be used for a diskless Darwin
`--inspect-root` test.
