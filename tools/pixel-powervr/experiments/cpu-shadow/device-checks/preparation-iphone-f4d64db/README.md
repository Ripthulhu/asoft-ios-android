# Physical iPhone input checkpoint

**The six selected iPhone inputs and both authenticated AEA decode stages have
passed on the Pixel.** These extend the same preserved preparation session
after [the completed shared build](../preparation-shared-f4d64db/README.md).

| Checkpoint | Verified output |
|---|---|
| `ios26-fetch` | Six files, 10,215,316,143 bytes; finished 2026-11-22 04:31:22 UTC |
| `ios26-decrypt` | Two images, 14,776,532,992 bytes; finished 2026-11-22 04:32:39 UTC |

The SystemOS plaintext is 5,253,365,760 bytes and OS is 9,523,167,232 bytes.
The phone retains both encrypted inputs and authenticated outputs. Exact
artifact paths and hashes are in the two exported checkpoint JSON files.
No image or key-database contents are stored here.

The three-file metadata export is 3,680 bytes uncompressed, 1,504 bytes
compressed, SHA256
`144b731ae9af9827e0d29e8b164088bd680eeb5518ddcaec962178651e265d08`.
Every exported file was checked against its recorded length/hash. The first
iPhone checkpoint links to the completed shared-build checkpoint, and the
second links to the first. Both bind session digest
`9ce5f5b8e4953ac54fddd854c5b4a606c2b9866814af6b1d520c2b590e987a6b`.
`input-export.json` preserves the export manifest and checkpoint identities.

## Active disk-construction boundary

The owner recorded in `raw/owner.json` selects through `ios26-partition` using
the frozen four-file `f4d64db` runner. At this input checkpoint, rootfs
construction is active in `/data/local/tmp/pixel-prep-e9cc754/attempts/05-0001`.
Rootfs and partition completion must be read from the live checkpoint chain;
these two input checkpoints alone do not establish either disk result.

The owner wrapper is `run_disks.py`. On the phone, its command, owner, stdout,
wrapper log and exit receipt use `ios26-disk-*-f4d64db` under
`/data/local/tmp/pixel-gpu-transfer-sxtv33sh`. Inspect the recorded PID **and
process start time**, the owner exit receipt and live checkpoints before any
resume. A running owner keeps the existing preparation lock.

Keep the complete session, successful predecessors and failed attempts.
Before first iOS boot, run the separate read-only GPT/HFS/Data-copy audit and
remeasure the required 3,840 MiB MemAvailable. The original scripts suppress
some partition copy/check failures, so the audit is an additional concrete
gate. Actual iOS boot/UI, app-UID operation and full integration checks remain
open; `boot_complete` and `gpu_path_complete` remain false.
