# Second physical diskless Darwin probe

The revised probe ran once on 2026-11-22 from **22:17:21.735133 UTC** to
**22:18:00.894541 UTC**. It captured one structured guest record within the
console nonce markers. QMP reported no block devices and no named block
nodes both before `cont` and after guest observation.

| Observation | Value |
| --- | --- |
| Real and effective UID | 0 and 0 |
| Root mount row | `root_device on / (hfs)`, one root row |
| Kernel root-device witness | `md0` |
| Paths that passed the executable-file test | `/sbin/mount`, `/sbin/mount_hfs`, `/bin/stat`, `/bin/sync` |
| Unmount paths that failed the executable-file test | `/sbin/umount`, `/bin/umount`, `/usr/sbin/umount`, `/usr/bin/umount` |
| Native witnesses | Initialization, execution, final SVC, no fatal markers |
| QEMU completion | Acknowledged QMP stop and quit, exit 0, unforced owned reaping |
| Probe status | `INCOMPLETE`, no checked unmount utility was executable |

The kernel calls the root device `md0` and the guest mount table uses
`root_device` for the HFS filesystem mounted at `/`. The record preserves
both observations. The probe executed the read-only mount listing. The
utility checks verified the applicable file predicates.

The staged source SHA-256 is
`3fbccdf79df80ca8bd2acb445554c369c4ebcf8fd95cb8419b9872cf56c25a71`. Its
Bash fixtures exercised a normal root row, the `root_device` form, duplicate
and absent root rows and redaction of an unrelated path. Host fixtures
covered asynchronous output, duplicate or malformed records, nonroot UID and
missing unmount refusal.

The retained phone result at `/data/local/tmp/asoft-rd-probe-02/run/result.json`
is 3,589 bytes, SHA-256
`3935bcf3a3e7b2f746b9aa1c35f7e4b0059cc0d64ce9f1878f147c2e57b57afb`.
The first physical result remained hash-identical. The second owner and QEMU
identities were absent at the final check. No original iOS disk was attached.

The next dependency is a non-forced guest unmount, first demonstrated on a
disposable HFS filesystem. See [helper source and build notes](helper/README.md).
