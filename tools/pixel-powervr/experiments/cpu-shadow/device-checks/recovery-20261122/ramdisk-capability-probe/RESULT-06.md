# Disposable HFS+ mount refused by Darwin System Policy

The native Linux preparation job produced a fresh ramdisk with the signed
helper and fixed mountpoint plus a blank 96 MiB journaled HFS+ volume.
The read-only HFS checks passed on both outputs. The preparation result is
`/data/local/tmp/asoft-rd-fixture-01/result.json`, SHA-256
`d8e292bd31acbb459f071bed52c7f5867d8c985079bde2d434a7f9574eb5bd3c`.

The Darwin guest booted from `md0`, reached UID and EUID 0, and ran the
signed helper's read-only root inspection. Four QMP inventory checks showed
only the fresh writable disposable copy, with one raw block device and two
block nodes. Darwin System Policy denied `mount_hfs` the `file-mount`
operation at `/mnt/asoft-recovery`. The nonce-bound command returned exit 1
and reported `Operation not permitted`. The project probe returned
`INCOMPLETE`. The native witnesses passed and QEMU stopped and reaped
cleanly. No mount, unmount, journal replay, or saved Data attachment occurred.

The disposable original and its attempted writable copy both retained SHA-256
`d0e6bc14344cb1908e30a353840365141caea8bdecbb2b9625282aac730168d0`.
A read-only observer verified both hashes, the QMP inventories, process
cleanup and the nonce-bound denial on the Pixel. It exported selected
evidence only and launched no VM.

| Retained evidence | SHA-256 |
| --- | --- |
| Fixture builder | `fc9560b91287aafeceac5dfec6916ee978eb3144a718ae62108b3ed21ab7fb39` |
| Darwin probe source | `35151a69c21bef98e9fe99a6f32de7b76b715d106680d14954062b68f73569ae` |
| `/data/local/tmp/asoft-rd-probe-06/run/result.json` | `61a48cb59e15ae7068f4dd3a78583f2189b1818af84b6bd234aed3c1a65ea475` |
| Retained serial log | `b1086e177b319fc6fd88fa4c80363459ce7cf4ef392474755d7b689d52939b12` |
| Read-only observer | `8d66e304276fb14a0302d3381166a8025d2ac134c16fe316fe0872721f6267fd` |

Preserve this attempt. Candidate recovery routes include a normal authorized
HFS maintenance tool or a supported Darwin host that can attach a fresh
copy. Apple's public HFS checker includes an in-memory verification branch
that simulates journal replay. A successful check of that kind alone does
not establish that replay was committed to disk. Keep any future journal
replay qualification on disposable media first.
