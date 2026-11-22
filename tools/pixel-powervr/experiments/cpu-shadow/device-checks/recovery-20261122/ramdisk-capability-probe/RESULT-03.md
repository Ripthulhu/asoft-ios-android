# Third physical probe: read-only ramdisk blocked helper transfer

The third diskless guest ran from **22:20:06.582892 UTC** to
**22:20:47.173871 UTC** on November 22, 2026. It reproduced the root HFS mount
and UID and EUID zero. Both QMP block queries returned empty inventories
before boot and after guest observation. Native initialization, execution
and final SVC passed. QEMU stopped and quit cleanly with exit zero, no
forced cleanup and no remaining owned processes.

The helper's arm64 Mach-O was signed on the phone and its Code Directory hash
matched the one new entry in the prepared trust cache. A sparse binary
reconstruction check reproduced the full signed helper byte for byte.

| Artifact | Value |
| --- | --- |
| Launch source SHA-256 | `f83447648d477614fd6bf97021cd15f87c985bf84718d8a8cf281540e32aeb35` |
| Signed helper SHA-256 | `00e39e335386e61ee4c208d186a910b9daad40531b3d81d6feb5a2827f859b55` |
| Helper CDHash | `46bc61e091ae39b748b8c91516ceafcca9109274` |
| Trust cache SHA-256 | `c3aeacc6132a14afe6318f15041cc9eb15d461073953b0dd5b03c19f4f2954fd` |
| Result SHA-256 | `8b9a619c792bdc2a3b9f87606d8f65188ffb84915858c81ce58ecb8bf96cd7f0` |
| Result path | `/data/local/tmp/asoft-rd-probe-03/run/result.json`, 4,284 bytes |

The guest refused creation of a staging directory on the read-only HFS root.
There were zero helper chunks transferred and no helper execution. The
attempt is preserved as `INCOMPLETE`. The signed output, adjusted trust
cache and serial logs remain on the phone.

A separate RAM-only guest can test a non-forced read-write remount after
confirming the exact HFS root, Darwin's `md0` boot marker and empty QMP block
inventories. If remount is unavailable, package the helper into a separate
ramdisk image using the existing build flow before retrying. Data remains
detached until unmount behavior is demonstrated on a disposable volume.
