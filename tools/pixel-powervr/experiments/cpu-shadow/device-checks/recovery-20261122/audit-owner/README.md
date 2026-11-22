# Completed native partition audit

Latest physical observation: **2026-11-22 11:38:42 UTC**. The physical audit is
**`PARTITION_AUDIT_COMPLETE_ACCEPTED`**. Both full HFS checks passed, the disk
and preparation records remained unchanged, all native witnesses and natural
completion were accepted, and the owner exited cleanly with all recorded
process identities absent. No firstboot or final GPU-path result is claimed.

## Reviewed source and purpose

The fresh outer owner is [run_partition_audit.py](run_partition_audit.py),
18,144 bytes, SHA-256
`af4b1478e37b52cf223bc86bf41df2c23f83d31dd5de287cfaabe64d0983bfe7`.
It invokes the unchanged staged auditor, preserves exact commands, owns its
one direct child and retains exclusive per-phase command, process and exit
receipts. It never launches QEMU or the preparation runner directly. The frozen
auditor continues to own VM supervision, preparation locking, native witnesses,
resource gates and clean child reaping.

The owner passed 12 focused synthetic tests. Its installer, preflight launcher
and status helpers passed five focused synthetic checks, with no real VM or
auditor used by those checks. Independent source review found no remaining
blocker. The original authoring manifests and procedures in this directory
are historical predeployment records; their statements that no phone action
had occurred describe that authoring boundary. The physical observations below
supersede those staging-only statements.

## Physical installation and preflight

Selected screenshot evidence is in [preflight-observation.json](preflight-observation.json).
It is deliberately labelled as a transcription, not an exact-byte export of
the phone's receipt files. Full phone records remain under the paths below.

| Step | Observed result |
|---|---|
| Source installation, 11:29:24 UTC | Exclusive source and receipt created; exact 18,144 bytes and reviewed SHA-256 read back; mode 0644. |
| Detached preflight, 11:29:46 UTC | Wrapper PID 5805/start 7201146; independent session/group 5805; stdin disconnected and output retained. |
| Completed preflight, 11:30:18 UTC | `PREFLIGHT_READY`; child and owner exit zero; accepted and reaped; no force, wrapper error or cleanup errors. |
| Process identities | Wrapper 5805/7201146 and auditor 5869/7201174 absent. |
| Boundary | Exactly seven checkpoints through `ios26-partition`; read-only/native required; TCG retry false. |
| Resource observation | 3,770,880,000 bytes MemAvailable; 74,048,487,424 free bytes; the 2,816 MiB fresh-helper floor was met. |

The accepted preflight output was 3,927 bytes, SHA-256
`9a3a798965dac353fec36405b31706b8da1d982fd732566b39f09fcf5c4d34a1`,
and matched the exit receipt. All four checked commands matched their expected
outer/auditor argument lists. The audit work directory remained absent;
`execution_verified`, `boot_complete`, `gpu_path_complete` and `app_gate_changed`
were false. Preflight validates the final disk identity and recorded inputs;
it does not establish a physical filesystem-audit or iOS boot result.

## Physical audit launch

The reviewed execution launcher finished at **11:35:34 UTC** after rechecking
the accepted preflight, source installation, unchanged preparation metadata,
available preparation lock and absent prior identities. It started the same
owner source with `--execute` in a fresh session; no frozen auditor argument,
helper limit, memory floor or source was changed.

The [first execution observation](execution-observation-113612.json) found:

| Process | Recorded identity | State at 11:36:12 UTC |
|---|---|---|
| Outer wrapper | PID 8032/start 7235994 | Matching, alive |
| Auditor | PID 8034/start 7236028 | Matching, alive |
| Audit QEMU | PID 8247/start 7238076 | Matching, alive |

The VM record was `INCOMPLETE` at 10.06 seconds, with initialization true,
execution/final witnesses false, no completion protocol or cleanup yet. The
audit work directory existed; no final audit or owner exit receipt was
available. MemAvailable was 3,072,147,456 bytes and free work space was
74,047,299,584 bytes. The first sample does not establish a native execution
or filesystem-audit pass. [The terminal screenshot](audit-running-113612.jpg)
retains this observed state.

Use [status_audit_execution.py](status_audit_execution.py) for the current
bounded observation. Its compact default selects receipts, process identities,
native witnesses and verdict fields. `--json` emits the same selected metadata.
Its existence does not authorize a duplicate execution launch.

## Accepted physical audit

The [11:38:42 UTC observation](execution-observation-113842.json) and
[terminal screenshot](audit-passed-113842.jpg) record the completed outcome:

| Gate | Observed result |
|---|---|
| Owner and auditor exits | Zero/zero; accepted, reaped; no forced runner, wrapper error or cleanup errors. |
| VM | `VM_OBSERVATION_COMPLETE`, native initialization/execution/final witnesses all true. |
| Natural completion | Done code zero, natural exit, QEMU exit zero and complete reap without forced processes. |
| iOSRoot filesystem | Full audit verdict `PASSED`, fsck exit zero. |
| Data filesystem | Full audit verdict `PASSED`, fsck exit zero. |
| Input preservation | Disk and preparation records unchanged. |
| Receipt binding | Final result hash matches owner exit; audit session matches accepted preflight. |
| Recorded processes | Wrapper 8032/7235994, auditor 8034/7236028 and QEMU 8247/7238076 absent. |

The accepted final result SHA-256 is
`542dcf281cbcfb0016d74eda8dbb7a84db799e390e857321f519de4e0f1a7146`.
The pinned auditor accepts only complete unfiltered fsck reports plus its exact
copy, GPT and journal classification checks. The result remains bound to that
unchanged source and session. The VM's final elapsed field was 110.68 seconds;
the observation does not claim that as total outer-owner wall time.

Available memory was 3,641,196,544 bytes and free work space 74,046,492,672 bytes.
That meets the helper's 2,816 MiB fresh-launch floor, but is **below the
firstboot requirement of 3,840 MiB (4,026,531,840 bytes)**. The next step is the
separate firstboot guard's read-only preflight and a fresh resource check.
Do not lower the existing threshold or start a firstboot from this observation.

## Phone locations

| Item | Phone path |
|---|---|
| Installed owner | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-partition-audit-ebbc9c0.py` |
| Source installation receipt | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-partition-audit-ebbc9c0-install.json` |
| Detached preflight receipt | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-partition-audit-ebbc9c0-preflight-launch.json` |
| Phase owner and result receipts | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-partition-audit-ebbc9c0-owner` |
| Detached execution receipt | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-partition-audit-ebbc9c0-execute-launch.json` |
| Separate audit work | `/data/local/tmp/pixel-audit-e9cc754` |

Do not rerun the installer, preflight launcher or execution launcher: their
exclusive artifacts already exist. Read the current owner/exit records and
VM identity first. The original preparation and separate audit are complete, with no recorded
owner left running. The auditor created and retained its own audit work directory.

The [compact status reader](status_audit_preflight_compact.py) contains the exact
bounded [full reader](status_audit_preflight.py). Both read only selected metadata,
process identities and resources, with no guest/serial/VM log export or process
control. [executed-invocations.json](executed-invocations.json) identifies the
exact transport commands used by the root agent. The helper author's numbered
command files are equivalent source transports with different compile labels;
they are preserved as authored, not represented as the commands that were run.

Accept a later audit only with the existing `PARTITION_AUDIT_PASSED` rules,
unchanged disk/preparation identities, both complete unfiltered HFS checks,
exact copy and journal agreement, natural native completion and clean owned
reap. Actual firstboot and GPU-path completion remain later gates.
