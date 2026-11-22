# Partition audit outer owner — staged review only

This directory contains a fresh two-phase receipt owner for the already staged
partition auditor. Nothing in this directory has been run on the phone. The
frozen preparation runner, staged auditor, preparation data, main repository,
host check environment, and app gate were not changed.

## Files and ownership

`run_partition_audit.py` adapts the historical retry wrapper's direct-child
ownership and exclusive JSON receipts. It never invokes the old retry wrapper,
preparation runner, QEMU, a package installer, or a policy command. Its only
subprocess is the documented auditor command. It imports only standard-library
modules; it does not import or mutate the frozen runner or auditor.

`test_owner.py` uses synthetic metadata and a small local Python stub. It does
not execute the auditor, firmware, a VM, or a GPU job. Twelve focused cases
cover accepted two-phase receipts, refusal while an old owner/child/lock is
present, partial checkpoints, native failure, forced prior cleanup, changed
source, changed preflight bytes, exclusive artifacts, failed preflight, and
bounded direct-child interruption cleanup.

Suggested fresh phone source path:

```
/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-partition-audit-ebbc9c0.py
```

The wrapper has fixed paths. Its receipt directory is:

```
/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-partition-audit-ebbc9c0-owner
```

The auditor's separate fresh work root remains:

```
/data/local/tmp/pixel-audit-e9cc754
```

Do not create the audit work root manually. The unmodified auditor creates it
after its own preflight, preparation lock, live-child checks and ownership setup.

## Prerequisites checked by both phases

The wrapper requires the byte-pinned retry `owner.json` and `command.json`, a
matching clean zero exit receipt, and absence of the recorded wrapper and
runner PID/start-time identities. PID reuse with a different start time is
recognized without signalling that process.

It validates the canonical preparation session digest, exactly seven
hash-linked checkpoints through `ios26-partition`, the final preparation
result, and the native/natural/clean helper results for the checkpointed
rootfs and partition attempts. It verifies the staged auditor's two source
hashes, frozen runner's four source hashes and historical wrapper hash.

It probes the existing preparation lock through a read-only descriptor and
checks recorded child identities plus the original preparation attempt marker
scan. The probe releases the lock. The auditor remains the authoritative
execution owner and reacquires that lock itself; a competing owner in the gap
causes the auditor to refuse rather than starting another helper.

The auditor's read-only preflight performs the full final-disk, checkpoint,
package, qualification, tooling and policy validation. The wrapper's metadata
checks are additional ownership gates, not a substitute for that validation.

The canonical session digest used by checkpoints and the raw session-file
SHA256 used by the auditor are checked separately. The wrapper compares the
auditor's `prep_session_sha256` with the actual raw session bytes.

## Launch sequence after the previous owner finishes

1. Observe the original owner and partition attempt finish cleanly, and retain
   their metadata. Do not run another VM or GPU job alongside them.
2. Transfer only the reviewed wrapper source into the fresh suggested path
   using exclusive creation; verify its full SHA256 against `manifest.json`.
   Keep an installation receipt. Do not overwrite a prior staged source.
3. Run the wrapper's **preflight phase** and let that wrapper finish. Its exact
   child argv is:

   ```sh
   /data/data/com.termux/files/usr/bin/python -B \
     /data/local/tmp/pixel-boot-checks-ebbc9c0/auditor/audit_ios26_partition.py \
     --prep-work /data/local/tmp/pixel-prep-e9cc754 \
     --runner-dir /data/local/tmp/pixel-prep-runner-f4d64db \
     --work /data/local/tmp/pixel-audit-e9cc754
   ```

   Outer wrapper invocation:

   ```sh
   /data/data/com.termux/files/usr/bin/python -I -B \
     /data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-partition-audit-ebbc9c0.py \
     --preflight
   ```

4. Review `preflight.json`, `preflight-owner.json`, `preflight-command.json` and
   `preflight-exit.json` under the receipt directory. Require child exit zero,
   owner exit zero, `accepted=true`, successful reap, no wrapper/cleanup error,
   no force, and the output SHA256 matching the exit receipt. Require
   `PREFLIGHT_READY`, exact unchanged checkpoint/source/session identities, and
   an absent audit work root. Check that the preflight wrapper and auditor
   recorded identities are now absent. The fresh helper memory gate remains
   the auditor's unchanged requirement; a ready preflight does not waive it.
5. Run the **execution phase** separately, after accepting the preflight:

   ```sh
   /data/data/com.termux/files/usr/bin/python -I -B \
     /data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-partition-audit-ebbc9c0.py \
     --execute
   ```

   The child command is exactly the command above with `--execute` appended.
   No other Python flag, helper deadline, memory bound, environment override,
   network permission or guest-boot option is added. The outer wrapper's `-I`
   affects only its standard-library receipt process; the auditor keeps its
   documented `-B` invocation.

For a disconnected terminal, detach each outer wrapper phase with a short
root Python caller using `subprocess.Popen(..., stdin=DEVNULL, stdout=<fresh
exclusive wrapper log>, stderr=STDOUT, start_new_session=True)`. Record that
outer PID and `/proc/PID/stat` start time in an exclusive launcher receipt.
Use different launcher receipts and wrapper logs for the two phases; wait for
and inspect the preflight receipts before detaching execution. The detached
outer wrapper itself records its actual identity, auditor identity and command
in its startup receipt. Do not detach QEMU or invoke the auditor a second time
outside this owner.

The wrapper uses exclusive creation for the owner directory and every receipt
or output file. A duplicate phase cannot overwrite an existing command receipt
or start another child. A failed or interrupted attempt is preserved. A later
attempt requires a separately reviewed fresh owner/work choice; never delete
the prior evidence or change a receipt to make this wrapper accept it.

## Completion and interruption

During execution use `owner.json`, `command.json`, `run.log` and the auditor's
`a1/vm-result.json` together. The final `exit.json` records child and outer exit
codes, both process identities, force/error flags, accepted status, and a hash
of the accepted auditor result. A missing exit receipt means no completed
outer-owner verdict is available.

Accept completion only when the wrapper has exited cleanly with
`owner_exit_code=0`, `exit_code=0`, `accepted=true`, `runner_reaped=true`, no
force/error, and the recorded identities are absent. The wrapper also requires
`PARTITION_AUDIT_PASSED`, unchanged disk and preparation records, matching
accepted preflight/audit sessions, positive native execution, natural helper
exit and clean owned reap. Inspect the actual audit result and required full
HFS check results. This remains a partition-audit gate; boot, GPU and app gate
flags remain false.

On SIGINT/SIGTERM or a wrapper exception, the wrapper sends SIGTERM only to its
own unreaped `Popen` child, waits 60 seconds, then records a forced child kill
if a further 30-second reap is needed. These are the historical outer-wrapper
cleanup bounds. The child auditor retains native QMP cleanup, PDEATHSIG and
subreaping. No process-name kill or group kill is used. A forced or incomplete
cleanup never becomes an accepted result; perform the recorded owned-process
recheck before considering any subsequent job.

Export selected JSON/protocol metadata only. Preserve full guest logs,
firmware, disk contents and generated binaries on the phone.
