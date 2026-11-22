# Physical diskless Darwin ramdisk result

The first diskless Darwin VM ran once from **22:15:04.543585 UTC** to
**22:15:44.415659 UTC** on November 22, 2026. It reached a root Bash shell.
The probe owner exited 2 with status `INCOMPLETE`. QEMU exited 0 with
acknowledged QMP stop and quit, no forced cleanup, and no remaining owned
children. Both recorded owner and QEMU identities were subsequently absent.

## Memory and launch

| Observation | MemAvailable (MiB, rounded down) |
| --- | ---: |
| Before one clean-cache reclaim | 3,277 |
| After the reclaim settled | 3,407 |
| Before closing one user-approved cached Android app | 3,371 |
| First sample after that process had exited and its memory was released | 3,963 |
| Detached launch precheck | 3,960 |
| Required floor | 3,840 |

The clean-cache reclaim ran once. The Android app was confirmed cached and
frozen with zero active service records before closure. The first sample
after its memory was released showed about 469 MiB less zram physical usage
and 591 MiB more system-wide MemAvailable than the pre-closure sample.
The kernel OOM-kill counter stayed at zero through the last observation.

## Guest and QMP observations

- The VM was paused in QMP `prelaunch`. Both `query-block` and
  `query-named-block-nodes` returned empty lists before `cont`.
- The pinned runtime recorded native initialization, execution and final
  SVC witnesses with no fatal markers.
- The guest's boot log contained the `md0` root marker. Within the one
  complete nonce-delimited console exchange, the guest reported `uid=0`,
  `euid=0` and selected the HFS mount at `/`. Its source was redacted to
  `other` because it did not match the expected `md0` or `/dev/md0`
  spellings. The exact mount source is unresolved.
- `/sbin/mount` and `/sbin/mount_hfs` met the executable-file test.
  `/sbin/umount` and the checked HFS bundle utility path did not.
- The strict parser refused a 54-byte asynchronous line within the console
  markers. A later local projection of the retained log recovered the
  selected guest fields. The refusal occurred before the second QMP block
  queries in the probe.
- Bound runtime assets and receipts were reverified. This run attached no
  saved iOS image, performed no filesystem repair and claimed no GPU or APK
  milestone.

The retained phone result is `/data/local/tmp/asoft-rd-probe-01/run/result.json`,
2,562 bytes, SHA-256
`fff33fa9cf74d2c72963fcf3cf26112d1513030177707605c9ceac6696f60613`.
The raw console and QEMU logs remain on the phone.

## Next probe

Use a fresh diskless attempt with a single bounded structured console record
so that asynchronous guest messages cannot be mistaken for fields. Identify
the actual root mount source with a fixed observation and verify the
availability of a guest unmount entry point. Keep the original run and all
saved disks preserved. A later Data recovery on a fresh copy-on-write
descendant still requires a verified clean unmount and fresh filesystem checks.
