# Physical rootfs preparation timeout

**The original `f4d64db` disk-preparation owner stopped at `ios26-rootfs`
with `INCOMPLETE`; neither rootfs nor partition completion is established.**
This is the completed outcome of the owner described as active in the
[iPhone input checkpoint](../preparation-iphone-f4d64db/README.md).
The five successful checkpoints through `ios26-decrypt` remain unchanged.

## Recorded outcome

The native Linux helper in `attempts/05-0001` started at
2026-11-22 04:32:39.442043 UTC and finished at 06:32:41.559144 UTC after its
7,200-second deadline. The owner exited with code **2**. Its command selected
through `ios26-partition`, without `--allow-guest-boots`; the recorded VM is
the 2,048 MiB, four-vCPU Linux preparation helper.

[`vm-result.json`](raw/attempts/05-0001/vm-result.json) records
`TimeoutError: VM stage deadline`, `natural_exit=false`, and empty
`done_codes` and `out_sizes`. QMP `stop` and `quit` returned matching replies.
Cleanup records QEMU exit 0, `ECHILD`, no forced QEMU or descendants, and no
cleanup errors. These are owner-ordered timeout cleanup records. The
`stop_flushed` field records the successful QMP stop response; it is not an
independent filesystem, journal or completed-copy check.

Native initialization, execution, sampler and final-SVC witnesses are present.
The selected final counters record **8,345,091 native entries and 7,306,120
SVCs**, alongside 311,112 failed fills/injected faults, 1,799 unsupported
events, 13 stub evictions and zero invalidation-wait timeouts. GPU execution
and frame capture are false. All completion flags remain false.

[`observation.json`](raw/observation.json) preserves only the selected authored
protocol, copy-phase and native counter lines. Its last four progress lines
report `50 copying iOS onto its disk (9.3 GB so far)`; no completion protocol
was observed. This identifies the last exported progress, not the cause of
the timeout or the completeness of the output filesystem.

The VM timestamps span 7,202.117101 seconds including cleanup. The raw
`elapsed_seconds=7195.547600282` and storage counters are the frozen runner's
last periodic sample. They are retained unchanged; the observation records
the final log sizes and hashes separately.

## Integrity and evidence scope

[`verification.json`](verification.json) records strict decoding and all
five block length/hash checks, followed by the complete compressed-stream
and individual file checks. The compressed transfer was **18,017 bytes**,
SHA256 `eb959bcb0b446a45d912f84b53ac3de33496db9d7bd58484e1bad4335afceda1`.
Its envelope contained **14 exact files totaling 40,544 bytes**, preserved
under `raw/`. The compressed and base64 transfer payloads are not included.
Local Git attributes preserve the raw files and UI transcript without
line-ending conversion.

Against repository base `af86ab68bc039a4a520107b9757768413c6ea2b3`, the
session and all five checkpoint files match the earlier committed evidence
byte for byte. Their predecessor hashes and common canonical session digest
`9ce5f5b8e4953ac54fddd854c5b4a606c2b9866814af6b1d520c2b590e987a6b`
verify. The four frozen runner source hashes match commit
`f4d64dbccea6cffd30b3bc906b50c80f2ecb9b1a`. Rootfs stage-input metadata matches
the 36 prior artifact paths and sizes; short-file hashes also agree. This
host verification did not reopen or rehash the phone's image artifacts.

[`owner-reap-ui-transcript.txt`](owner-reap-ui-transcript.txt) preserves the
transfer's `owner_reap_observation` text and line endings. **It is a UI
transcript, not a raw phone file.** At 06:34:26.280997 UTC it reports the
recorded wrapper, runner and QEMU PIDs absent and `RELEVANT OWNERS []`.
The PID identities match the exported owner and child metadata. No new phone
check was performed while preserving this evidence.

No image, Apple binary, key database, full guest log or compressed transfer
is published here. No phone operation, build or test suite was run for this
host preservation. Keep the failed attempt and successful predecessors;
this record grants no rootfs, partition, iOS boot, UI, app-UID or GPU pass.
