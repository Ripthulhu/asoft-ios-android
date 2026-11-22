# Physical shared image preparation checkpoint

**Shared fetch, authenticated unpacking and native Linux construction passed
on the Pixel on 2026-11-22.** The same `e9cc754` runtime and frozen `f4d64db`
preparation runner used in the authored helper check produced this checkpoint.

| Stage | Verified completion |
|---|---|
| `shared-fetch` | 11 output files, 1,007,990,083 bytes; pinned shared downloads and selected cloudOS ZIP members |
| `shared-unpack` | Seven outputs, 1,651,513,152 bytes; firmware, research kernel, device tree, ramdisk image and authenticated GPU image |
| `shared-build` | Ten output files; shell ramdisk, its trustcache, three matched trees, patched boot kernel and retained GPU bundle |

The returned tar is **555,827,200 bytes**. The runner validated its complete
bounded archive, expected outputs and hashes before recording `STAGE_COMPLETE`.
The shell ramdisk is 511,705,088 bytes (488 MiB). Every output path, byte count
and SHA256 is in `raw/checkpoints/shared-build.json`; the image bytes remain on
the phone.

The build helper records **864,281 native entries and 622,571 SVCs**, one
`ASOFT: done 0`, natural exit 0, `ECHILD`, no forced termination and no cleanup
errors. Its VM start/finish timestamps span 817.513153 seconds. This is image
preparation time. The original polling-only elapsed field is retained as
recorded; the later source telemetry fix does not alter this frozen run.

Hybrid execution qualifications remain visible: 81,922 failed fills/injected
faults, 77,917 unsupported native events and one stub eviction. No invalidation
wait timeout was reported. The selected final native counters and all helper
protocol lines are in `raw/observation.json`, together with the full logs'
original byte counts and hashes. This preparation job does not add an iOS
boot, app-UID or GPU rendering qualification.

## Integrity and export scope

The nine-file completed export contains 27,896 bytes of JSON metadata and
selected protocol/counter lines. The 8,802-byte compressed export has SHA256
`1ee3ed29a84516b8cd72b56c2d4dbb90d5dfb150b1ae7c3160409105d552a3cd`.
`completed-export.json` records each exact exported file identity. The earlier
three-file input snapshot is also retained in `input-export.json`; its copies
of the session and first two checkpoints match the completed export exactly.

The checkpoint chain was independently reconstructed from the exact metadata:
each stage points to its predecessor's SHA256 and the same session digest,
`9ce5f5b8e4953ac54fddd854c5b4a606c2b9866814af6b1d520c2b590e987a6b`.
The phone runner verified actual artifacts and preserved predecessors; the
host rechecked the exported metadata bytes and hash chain. This repository
contains no downloaded image, firmware, Apple binary, key database or full
guest-preparation serial log.

## Resume

The owned phone session is `/data/local/tmp/pixel-prep-e9cc754`. Its immutable
shared build attempt is `attempts/02-0001`; the matched artifacts are under
that attempt's `files/`. The earlier download/decode attempts and encrypted
inputs remain preserved. Keep the complete session and its backing files.

The frozen four-file runner remains at
`/data/local/tmp/pixel-prep-runner-f4d64db`, and the verified tools remain at
`/data/local/tmp/pixel-tools-1528a782`. Use the same qualified package and
seventeen-case report recorded in `raw/session.json`.

The subsequent owner selects `ios26-fetch` through `ios26-partition`. Its
command, owner identity, stdout and exit receipt use
`ios26-disk-*-f4d64db` under
`/data/local/tmp/pixel-gpu-transfer-sxtv33sh`; the owner wrapper is preserved in
`../preparation-iphone-f4d64db/run_disks.py`. Inspect that owner and the live
checkpoint chain before resuming. The top-level result can still describe a
previous completed boundary while the next owner runs.

Before first boot, verify the partitioned disk through the separate read-only
audit. The inherited partition script suppresses some copy and filesystem
check statuses, so a successful qcow2 container check alone is insufficient.
Retain the fresh 3,840 MiB MemAvailable gate for the 3 GiB iOS boot. All result
records keep `boot_complete=false`, `gpu_path_complete=false` and
`app_gate_changed=false`. No final APK has been built.
