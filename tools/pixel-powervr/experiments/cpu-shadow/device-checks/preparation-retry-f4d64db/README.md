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
