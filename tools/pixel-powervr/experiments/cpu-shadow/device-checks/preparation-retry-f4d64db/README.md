# Active native rootfs retry snapshot

**This is startup evidence for the fresh `05-0002` rootfs attempt, captured
while its owner was active. It is not a completed rootfs or partition result.**
The original `05-0001` timeout remains preserved in the
[previous evidence](../preparation-disks-f4d64db/README.md).

## Recorded boundary

| Event | UTC on 2026-11-22 |
| --- | --- |
| Read-only preflight started | 06:40:12.101156 |
| Preflight finished, exit 0 | 06:40:41.862134 |
| Retry owner started | 06:43:51.411279 |
| Native Linux helper started | 06:44:50.213024 |
| Export snapshot captured | 06:47:44.182661 |

[`preflight.json`](raw/preflight.json) reports `PREFLIGHT_READY`, the same five
completed stages through `ios26-decrypt`, and only `ios26-rootfs` and
`ios26-partition` remaining. Its network and guest-boot stage lists are empty;
`execution_verified` remains false because this is the planning result.
The exit receipt binds the exact preflight output hash and an empty stderr.

The retry command adds only **`--helper-seconds 21600`** to the previous
execution command, extending the helper deadline from two hours to six.
It still selects through `ios26-partition`, with no `--allow-guest-boots`.
The preserved owner wrapper matches `/tmp/pixel-run-disks-retry-f4d64db.py`
byte for byte, SHA256
`6ed877eba0114375409dce5146c0e7187fca06af6ab587cddbd2aab836b9d38a`.
The wrapper is historical execution evidence, not authorization to rerun it.

The [new launch record](raw/attempts/05-0002/launch.json) is byte-identical to
the first attempt after substituting only the attempt directory and
`deadline_seconds: 7200` with `21600`. Helper memory remains **2,048 MiB**,
with four vCPUs and eight required native stubs. The OS, SystemOS and AppOS
input drives remain read-only and point to the same successful predecessors.
The input tar is read-only; the output raw file and fresh `root26.qcow2`
belong to `05-0002`. All other launch arguments and environment entries are
unchanged.

## Active snapshot, with no completion credit

[`vm-result-snapshot.json`](raw/attempts/05-0002/vm-result-snapshot.json)
reports `INCOMPLETE`, `natural_exit=false`, and native initialization,
execution and sampler witnesses. Its final native-SVC witness, GPU execution
and frame capture are false. There is no error field, finished timestamp,
cleanup record, or completion protocol field. The sole QMP exchange is the
successful capabilities handshake. Absence of an error at startup is not
proof that the job completed.

The raw polling elapsed value is 170.90625744799763 seconds. It predates the
export timestamp and is retained unchanged. All boot, GPU-path and app-gate
completion flags remain false.

| Recorded process | PID | Start ticks |
| --- | ---: | ---: |
| Outer owner wrapper | 27799 | 5485624 |
| Preparation runner | 27801 | 5485639 |
| QEMU helper child | 28210 | 5491577 |

These identities describe the captured attempt. The export reports
`owner_active=true`; this host preservation performed no live phone or PID
check and makes no claim about the owner's later state.

## Integrity and retained predecessors

[`verification.json`](verification.json) records every block and file check.
The eight-block compressed transfer is **30,767 bytes**, SHA256
`af17b15ce8b20120e6c65250b9abc15b847f7f0d55e2687441833170ee2fcc91`.
All **11 exported files, totaling 76,327 bytes**, are preserved exactly under
`raw/`; local Git attributes prevent line-ending conversion.

Against repository base `e886625049c20e62fd19ef56111dff4c96c8938d`, the
preflight session object exactly matches the prior session, and the reported
session-file, five checkpoint-file and failed `05-0001` VM-result hashes
match the committed records. The predecessor chain verifies with canonical
session digest
`9ce5f5b8e4953ac54fddd854c5b4a606c2b9866814af6b1d520c2b590e987a6b`.
The preflight's 36 artifact records exactly match the checkpoint union, and
the retry stage-input file is byte-identical to the first attempt's file.
The included setup manifest also matches the pinned local tooling source.
These are metadata comparisons; the host did not reopen phone image files.

No compressed/base64 transfer, Apple image or binary, key database, or full
guest log is included. No phone operation, build or test suite was run for
this preservation. This snapshot grants no rootfs, partition, iOS boot, UI,
app-UID or GPU pass.

## Read-only status after reconnecting

`status_retry.py` is a separate, standalone observer for this recorded retry.
Its reviewed bytes were staged at 07:20:02 UTC and first run at 07:20:58 UTC.
Run this one command from the same privileged phone shell used for preparation:

```sh
/data/data/com.termux/files/usr/bin/python -I -B /data/local/tmp/pixel-status-retry-f4d64db.py
```

Append `--json` for the selected metadata as JSON on standard output, suitable
for copy-back. The observer itself creates no output file. The exact
[installation receipt](observer-install.json) binds the 7,495-byte archive and
24,367-byte source, SHA256
`899331a986db310d04af2ee076792d00c3ed64e8403f73b6e02efa897427c462`,
installed as a root-owned mode-0644 regular file at
`/data/local/tmp/pixel-status-retry-f4d64db.py`. Its `observer_executed=false`
describes the earlier installation boundary, before the separate invocation.

The [first terminal observation](observer-072058-terminal.txt) is the exact
browser clipboard selection, including terminal CRLF and the shell prompt;
it is not an exported phone file. [Evidence identities](observer-evidence.json)
distinguish these two sources. The observed wrapper, runner and QEMU PIDs/start
ticks matched this retry, and no exit receipt was present. The metadata prefix
remained five stages through decrypt. Attempt `05-0002` still reported native
execution, no error field and no cleanup; its periodic sample was from
07:20:50 UTC. The container file was 6,824,198,144 bytes with 6,830,845,952
allocated bytes, MemAvailable was 2,272,305,152 bytes and free work-directory
space was 103,987,073,024 bytes. These are an active snapshot, not rootfs,
partition, iOS boot or GPU completion evidence.

The paths to the work directory and this retry's owner directory are fixed
in the script. It checks the pinned owner record, reads its wrapper and runner
PIDs dynamically, and compares each `/proc/PID/stat` start time before calling
that recorded identity live. Absent, reused, zombie and unreadable identities
are distinguished. A missing exit receipt is reported independently of
process liveness; a present receipt is checked against the recorded command
and owner start time. Neither elapsed time nor an old result grants a pass.

The output includes the contiguous checkpoint metadata prefix, latest new
`05-*` and `06-*` attempt directories, actual launch deadline/`-m`/`-smp`,
QEMU child identity, periodic VM file mtime and sample, native witnesses,
error field, current MemAvailable and work-directory free space. Disk sizes
are **container file bytes and allocated filesystem bytes**, obtained by
stat; they are not the guest filesystem's used space or the virtual disk's
capacity. The top-level result is labeled as possibly belonging to an older
boundary.

Each JSON read is limited to 256 KiB and each directory listing to 128
entries. Path components and final metadata files reject symlinks. Only small
metadata is hashed; no image contents or full serial/stderr logs are read.
The observer invokes no other process, acquires no lock, sends no signal,
and performs no write, mount, VM, GPU or guest operation. It disables Python
bytecode writes as well as using `-B` in the invocation above; `-I` isolates
standard-library imports from caller Python path overrides and the script's
directory.

The reads are independent snapshots while the owner may be writing atomic
JSON replacements. They are not one transaction or a new completion audit.
Unreadable, malformed, changed or out-of-scope metadata produces explicit
findings. Exit code 0 means only that a status snapshot was printed; inspect
its findings and recorded state before deciding what work is appropriate.
The observer passed syntax and source review before the recorded phone
invocation. No new test suite was run for this low-impact status utility.
