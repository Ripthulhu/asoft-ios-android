# Recovered iOS 26 whole-image inspection

The native Pixel helper inspected the recovered QCOW2 layer and the immutable
partition predecessor as read-only devices. The GPT matched. Both partitions
passed raw journal validation and forced read-only fsck. The helper completed
naturally, passed the native initialization, execution, and final SVC
witnesses, and was reaped cleanly with exit zero.

| Partition | Empty journal position | Read-only fsck diagnostic SHA-256 |
| --- | --- | --- |
| iOSRoot | 512 | `aefb23a7afb89699deacef1c756373a8a01ebb9882d3905be560a51bc314bd5a` |
| Data | 614400 | `b70d937af5426f0a864c291745310fe99594e63ea59c9941da5531b2a2b482f5` |

The iOSRoot check verified the exact authored NeedInit-to-initialized
transition. Data passed the strict initialized journal gate. No partition was
mounted, replayed, or repaired during this inspection. The original and
recovered chains retained their pinned identities and hashes.

The inspection is retained at `/data/local/tmp/asoft-recovered-audit-01`.
Host result SHA-256 is
`f306d1f1ec29b583e3b9d35338f5cccb50264a69e6c4f81aba51860433bb5a7d`.
Guest result SHA-256 is `602582f62e86c021bfb72473c8d3e88c49762f11cef40d5cb28acc664561f96a`.
The [recovery layer and Data manifest](DATA-COPY.md) remain the source for
subsequent fresh writable descendants.
