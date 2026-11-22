# Saved-inspection descendant cleanup analysis

This is read-only source analysis and a narrow diagnostic query for the
preserved incomplete saved-firstboot inspection. It changes no phone source,
process state, disk, checkpoint or acceptance rule. It does not release the
blocked downstream apps-preparation owner.

The preserved apps-preparation draft names this now-failed inspection's work
and owner paths. Those files cannot become an accepted input in place. Any
later successful fresh inspection will require a separately reviewed draft
revision binding its actual new work, owner/source paths and success hashes.
Keep the current draft and its `None` success-pin mapping unchanged; do not
fill it from the failed result or overwrite the failed work.

## Established physical boundary

The parent agent's **2026-11-22 14:58:55.245032 UTC** observation reports an
inspection/outer-owner exit of 2, `accepted=false`, and clean, unforced outer
reaping. The inspector result is `INCOMPLETE` with
`RuntimeError: VM stage incomplete`. It reports
`full_backing_chain_unchanged=true`,
`preparation_and_guard_unchanged=true`, and no identity error.

The VM record reports natural QEMU leader exit with exit code 0 and native
initialization/execution, but **`forced_descendants=[13344]`**. This is decisive
under the unchanged acceptance rules. It is not an accepted saved filesystem
inspection and cannot supply downstream success pins.

The frozen runner's `elapsed_seconds` is a periodic sample. Its final value
must not be treated as the complete VM lifetime; use the raw `started_utc` and
`finished_utc` timestamps for that duration. The actual phone observations and
failure file identities are owned by the separate saved-inspection evidence
record, not reconstructed from this analysis.

A later raw `vm.child.json` projection identifies the failed inspection's QEMU
as **PID 13326 / start ticks 8442942**. The previously selected value 8442923
was a transcription error. A read-only failure collector refused that stale
expected identity; the parent is preserving the correction in a separate
reader. The correction does not change the failed cleanup result or identify
descendant PID 13344.

## Exact source recovery

The recovered frozen [preparation runner](source/prepare_ios26.py) is 61,412
bytes, SHA-256
`c77bc990e56dcb47d651f9c054c41313a6671498a5b2494e96bb522ae868fb1a`.
It was recovered from the current checkout by reversing exactly three later
telemetry lines: the `started = None` initialization and the conditional final
elapsed-time update. The complete hash matches the established phone source.
The [exact reverse diff](source/reverse-runner-telemetry.diff) is retained.

The full [qualified native source](source/native-el0.c) is 198,762 bytes,
SHA-256
`a6c9a6110f6a34ddfdab5a4ce29bd1ecf176692de9f1d4f7546078734b0ca598`,
Git blob `180bf260f60d878b0b579819de5115cfd5fc6085`. Both identities match the
retained source patch and qualified QEMU build record.

The exact public base file was obtained with a read-only GitHub request at
commit `7a900afb62ddf94713e38ac5a4aafe1d42c9efa8`. Its Git blob was verified as
`0d15b862ccd0aaaba13a745430960d2df801e74b`. Applying only the existing retained
`native-el0.c` patch reconstructed the final qualified source. The
[base](source/native-el0-base.c), [scoped patch](source/native-el0.patch) and
[provenance](source-provenance.json) are preserved. No build or device execution
was performed for this recovery.

The unchanged `cold_boot_ios26.py` remains SHA-256
`6a57ed164864eef20aeffd34b14b675a8ac597c20583c9f179414a36b4ccbdeb`.
Its `subreaper()`, `shutdown()` and `reap_owned()` are the cleanup source basis.

## What the source proves

`stub_shm_init()` forks a factory before QEMU has threads. `factory_main()`
names that process `asoft-stubfac` and forks workers for `FAC_SPAWN` requests.
`stub_main()` names each worker `asoft-stubN`, creates its native vCPU threads
and then waits indefinitely.

Both the factory and each worker request `PR_SET_PDEATHSIG=SIGKILL`. Their
parent checks test only whether `getppid() == 1`. The factory command set is
`FAC_NONE`, `FAC_RECV_FD`, `FAC_SPAWN`; it has no shutdown command. Its loop
reaps already-finished worker children with nonblocking `waitpid`. The native
source's QEMU-side exit registration is `stats_report()`, not an explicit
factory/worker shutdown-and-wait routine. Normal parent exit therefore relies
on the configured parent-death signal cascade for these native descendants.

The frozen Python `shutdown()` skips QMP stop/quit if the QEMU leader already
exited. It reaps that leader, closes QMP, records its return code, then calls
`reap_owned()`. The latter performs a nonblocking `waitpid(-1, WNOHANG)`. If
that returns zero, it immediately scans for its current direct children and
requests `SIGKILL` for each one. Its five-second deadline is a cleanup/reap
deadline, **not a five-second passive grace period**.

`forced_descendants` records PIDs after those `os.kill(..., SIGKILL)` calls
return successfully. It proves that the supervisor requested the signal. It
does not by itself establish which process role the PID had, whether that
signal caused its exit, or how long it would otherwise have remained present.
The function discards reaped descendant wait statuses. `vm_success()` requires
the forced-descendant list to be empty, so the reported VM cannot pass. The
supervisor raises before the inspector can extract and validate the returned
guest inspection results.

## Narrow existing-log query

[`observe_native_pid.py`](observe_native_pid.py) reads only the preserved
`/data/local/tmp/pixel-saved-audit-e9cc754-resume1/a1/qemu-stderr.txt`. It refuses
noncanonical/nonordinary input, caps the file at 64 MiB and each parsed line at
4,097 bytes, verifies the file's identity before/after reading, and hashes the
exact bytes. It reads no guest serial log and prints no raw stderr or guest
line.

The exact native source includes these PID-bearing message families:

- Worker reaped by factory: `stub N (pid P) killed by signal S` or
  `stub N (pid P) exited with E`.
- Slot-owner mismatch: slot/vCPU numbers, owner PID and stub PID.
- Worker `tgkill` error: stub index, PID and TID.
- Ten-second native wait diagnostic: vCPU, stub index, PID and TID.

The observer projects only numeric fields for **PID 13344**, counts recognized
formats, and includes the last parsed pool-count summary. Ordinary successful
startup statistics do not print a factory/worker PID map. In particular, the
source has no factory-startup PID diagnostic. A result with no matches leaves
the process unclassified.

The [single compressed query](observe-native-pid.command.txt) is 3,153 bytes.
Its decoded source is 5,257 bytes, SHA-256
`3895c9239b77740a96894be984a08dd2a03bad5abab1ddbce55d097ad5639ca3`.
The source-provenance record describes the earlier preparation boundary. The
parent subsequently ran the independently reviewed query and reported the
following selected projection at **2026-11-22 15:05:18.608037 UTC**:

| Observed field | Value |
| --- | --- |
| Native stderr bytes | 1,770 |
| Native stderr SHA-256 | `025b5c6f8b2cb1e534b39588adc76d776fb263489f47597ced8a60e4a94cbc6c` |
| Recognized PID-format lines | 0 |
| Numeric fields matching PID 13344 | `[]` |
| Native lines mentioning PID 13344 | 0 |
| Overlong lines | 0 |
| Native stub pool configured / spawned / bound | 8 / 6 / 1 |
| Evictions / invalidation waits / slow waits / timeouts | 0 / 0 / 0 / 0 |

**PID 13344 remains unclassified.** The pool counts describe native activity,
not a mapping between the forced PID and a factory or worker. This is the
parent's selected diagnostic projection, not a copy of raw guest or stderr
logs. No new helper or process signal was requested by the query.

## Hypotheses, without accepting the failure

Several distinct explanations remain compatible with the available record:

1. The QEMU-parent/factory/worker death cascade was still completing when the
   supervisor immediately scanned adopted children.
2. A child became waitable between the nonblocking `waitpid` and `SIGKILL`
   request. The resulting forced-list entry alone cannot establish signal
   causality.
3. A child lost its original parent before it installed `PDEATHSIG`. Under a
   subreaper, its new parent need not be PID 1, so the source's parent check
   does not necessarily detect that race. Such a child could persist and
   require actual cleanup.
4. The recorded PID had another owned process role, not yet identified.

The third point is a source-level possibility, not a finding that it occurred
on this phone. A normal QEMU leader exit and unchanged read-only disks do not
distinguish these cases or remove the failed cleanup gate.

## Preferred next diagnostic: unchanged inspection plus owned observation

A fresh inspection with the same immutable code and gates, accompanied by an
independently owned read-only process sidecar, provides the clearest next
observation. It needs fresh inspection/owner/monitor paths and a fresh bound
preflight. The original failed work remains preserved.

The sidecar must run outside the inspector's descendant subtree, for example
as an independently owned sibling. It must not be a child of the inspector:
the unchanged reaper intentionally targets all current direct children.
The monitor must never signal, reap, ptrace, stop or alter the observed
processes.

Anchor it to the actual inspector and QEMU `(pid, start_ticks)` records. Record
the native factory/worker birth and parent relationships before shutdown, then
adoption and disappearance afterward. Useful bounded fields are the monotonic
timestamp, PID/start ticks, PPid, process group, session, name, state, and
selected pending-signal fields. The verified native names distinguish
`asoft-stubfac` and `asoft-stubN`; the qualified QEMU executable identity can
be checked without reading guest memory or raw logs. Limit process count,
event count, output bytes and observation duration, and record any gaps.

An unchanged retry can establish whether its own result passes and can
classify a newly recorded forced PID. It cannot prove that waiting would have
saved the prior PID. Sampling itself may alter scheduling; neither a repeated
pass nor a repeated failure should be presented as proof of the prior race.

## Alternative: a separately reviewed passive-reap adapter

A process-local passive-reap grace is a possible later experiment, not an
implemented or released fix here. It would intentionally change cleanup
timing and needs its own exact source, command, original-source and receipt
bindings. Unchanged file hashes must not conceal the changed runtime behavior.

The narrow form is a bounded no-signal `waitpid(..., WNOHANG)` phase for the
actual owned native helper after a natural leader exit, followed on expiry by
the original forced-cleanup path. Preserve descendant wait statuses and
ownership observations, every actual signal request, the original
`forced_descendants` result, `ECHILD`, and all existing native, filesystem,
input, resource and acceptance checks. Restore every temporary function
binding in `finally`. Other cleanup calls should retain their original
behavior.

There must be no PID-specific exemption, filtering of forced entries, or
retroactive acceptance of this failure. A surviving child at grace expiry must
still lead to the original cleanup and refusal. The bound and intended native
process roles should be chosen and reviewed using actual observations, not
assumed from the leader's exit code.

An explicit QEMU factory shutdown protocol would be a broader native-source
and binary change requiring new qualification. It is outside this read-only
diagnostic and is not necessary to obtain the next ownership observation.
