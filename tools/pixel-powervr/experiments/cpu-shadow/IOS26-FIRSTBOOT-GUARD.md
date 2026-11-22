# Guarded first iOS26 setup boot

`guard_ios26_firstboot.py` adds two explicit execution checks around the exact
frozen preparation runner. It changes no frozen file or session configuration.
Its default is **read-only preflight**; `--execute` runs only the first iOS setup
boot from a completed, passed partition audit.

The additional source is recorded transparently: the guard compiles the four
runner files only after verifying their preparation-session hashes, installs
two temporary hooks in those loaded modules, and invokes the original
`prepare.execute()` in the same process. The original runner remains the sole
writer of preparation attempts and checkpoints. The guard's receipt identifies
both the frozen source hashes and this additional execution source.

## Why this separate guard is needed

In qualified QEMU commit `755b88fad8a2771a8e3e207133a54898b740cd7f`,
`monitor/qmp-cmds.c:qmp_stop()` ignores the return value of `vm_stop()`, while
`system/cpus.c:do_vm_stop()` includes the result of `bdrv_flush_all()`. An
acknowledged QMP `stop` therefore does not independently report that flush
return value. The original app's `PhoneSetup26.saveBoot()` checks the recorded
failed guest-write and guest-flush counters after stopping. The frozen
standalone runner omitted that check and could also accept a boot without a
shell-sync response.

The two hooks are deliberately limited:

1. **`Qmp.call("stop")`:** call the original stop, then the original
   `query-blockstats` with a five-second response deadline. Require one `root`
   backend and validate every returned parent/backing statistics object. Both
   `failed_wr_operations` and `failed_flush_operations` must be present,
   nonnegative integers and exactly zero; booleans, missing values, malformed
   structures, nonzero values and query errors are refusals. The original QMP
   method records both full request/response pairs in the original VM trace.
2. **`supervise_vm("ios26-firstboot")`:** delegate the existing supervision,
   then require its **`guest_sync_answered is True`** witness, one successful
   counter check and unchanged bound inputs before returning to `guest_stage`.
   The original memory, native, console, settling, deadline and cleanup gates
   remain in force.

A counter-check exception occurs inside the original shutdown's stop handling:
the original stop flag stays false and the cleanup error prevents VM acceptance.
Quit, wait, bounded owned termination if necessary, and descendant reaping still
run. A missing shell-sync witness is rejected after that cleanup, before the
stage can return to the checkpoint-writing branch. A hook receipt-write failure
also prevents that return. Both hooks are restored in `finally`.

### Exact evidence limit

**Zero counters describe recorded guest I/O failures. They do not expose the
return value of stop's internal `bdrv_flush_all()`.** That direct QEMU path does
not update the BlockBackend guest-I/O failure counters. The frozen field named
`stop_flushed` retains its historical meaning here: the stop call returned
successfully under the added counter guard; it is not direct proof of the
internal flush return.

The pinned QEMU exposes no suitable `blockdev-flush` QMP command, and HMP
`qemu-io` also discards its command return status. This guard adds neither
workaround. It records `failed_io_counters_zero` and
`stop_internal_flush_return_observed: false` explicitly.

The pinned Linux HFS checker also cannot be treated as a journal-replay proof:
its Linux replay routine is a no-op, and its journal-empty check does not
strictly validate all raw-header failure cases. Therefore **a separate saved
filesystem/raw-journal check remains mandatory after this firstboot, before
any subsequent Linux disk mutation**. A shell-sync response strengthens the
shutdown evidence but does not replace that check. This guard does not
implement the later journal inspection or continue into persona/activation.

## Inputs and invocation

Stage this single Python source outside the four-file frozen runner, audit
output, and verified runtime/tooling directories. Provide the actual source
directory of the auditor whose physical run passed; newer reviewed auditor
revisions are supported by matching their hashes to the passed audit receipt.
No older auditor revision is silently substituted.

```sh
/data/data/com.termux/files/usr/bin/python -B guard_ios26_firstboot.py \
  --audit-work /data/local/tmp/pixel-audit-e9cc754 \
  --auditor-dir /absolute/path/to/the/actual/passed/auditor-source \
  --runner-dir /data/local/tmp/pixel-prep-runner-f4d64db \
  --work /data/local/tmp/pixel-firstboot-guard-e9cc754
```

Replace the auditor source path with the actual staged revision. The command
first verifies the passed audit's source hashes, session, exact checkpoint
chain, partition disk record/identity, clean native completion and reaping,
returned metadata files, and unfiltered fsck diagnostic hashes. It also runs
the original preparer's complete preflight, including the 17-case physical
qualification, runtime correspondence, tooling receipt and artifact rehashes.

After reviewing the resulting plan, add **`--execute`**. The original runner
arguments are reconstructed from the immutable preparation session, including
Europe/Amsterdam, the empty region, 24-hour clock, helper RAM/vCPU settings and
the existing runtime/tooling paths. The only stage selected is
`--through ios26-firstboot --execute --allow-guest-boots`; no further network
flag or asset/version/display choice is needed.

The completed prefix must end **exactly at `ios26-partition`**, and remaining
work must be exactly `ios26-firstboot`. A pre-existing firstboot checkpoint,
another selected stage, an incomplete audit, changed evidence/source, or a
changed original disk is a refusal. An execution that became a no-op because
another owner finished firstboot cannot be accepted: the guard requires one
guarded supervision, one counter event, and one new launched attempt.

The original firstboot uses a fresh overlay, 3 GiB RAM, four vCPUs, 1179×2556 at
3×, a copied 38.4-MHz device tree, required native EL0 with TPIDRRO swap and 24
stubs, and the stock research kernel/plain tree. It requires both persona and
user-session keybag files, then 30 seconds settling, under a 3,600-second bound.
Fresh available memory must still be at least **3,840 MiB** before launch, and
the existing default **512 MiB** running low-memory bound remains unchanged.
The original additional-free-space gate is **4.5 billion bytes**. Physical
thermal/charging conditions remain a separate prelaunch check.

## Evidence and acceptance

The fresh guard directory holds `guard-session.json`,
`guard-observations.json`, and `result.json`. They bind:

- guard source SHA256 and exact frozen source hashes;
- the passed audit's actual source revision and result/output identities;
- the preparation session, prior checkpoint hashes and original input identities;
- equivalent original-runner argv and the explicit in-process execution method;
- actual new attempt, original QEMU `launch.json` and VM-result identities;
- post-stop statistics, mandatory sync verdict and the resulting checkpoint SHA.

All source/audit/input identities are checked before and after guarded
supervision and again after execution. The guard result is
**`GUARDED_FIRSTBOOT_COMPLETE`** only when the original firstboot checkpoint
belongs to its fresh launched attempt and every added guard has passed. It
still records `boot_complete=false` and `gpu_path_complete=false`: this is an
initial setup boot, not final native GPU/UI qualification.

Counter/sync guard refusals prevent this execution from writing a firstboot
checkpoint. A **later** evidence-collection, identity or receipt-write failure
can occur after the frozen runner has written its checkpoint. Such a run is
`INCOMPLETE`, with `checkpoint_accepted_by_guard: false`; the original checkpoint
is retained, not deleted, rewritten, fabricated or silently adopted. **Later
orchestration must require the successful guard receipt bound to the current
checkpoint**, then the separate saved-journal check. The mere presence of
`ios26-firstboot.json` is insufficient.

Every failed attempt and its evidence stay separate. This tool does not adopt a
failed boot disk, change the application support gate, build an APK, modify
the final cold-boot harness, or relax any memory threshold.

## Focused offline tests

```sh
python3 -B -m unittest -v test_guard_ios26_firstboot
```

The tests run the original frozen checkpoint-writing, shutdown and success
predicates with authored metadata/qcow headers and mocked VM/QMP I/O. They
cover malformed/nonzero/nested counters, query timeout, missing sync, bound
source mutation, audit/source mismatch, receipt-write failure, no-op/adoption
refusal, hook restoration, actual launch binding, post-commit refusal, and
quit/reap preservation. They perform no phone, guest, GPU or mount operation.
