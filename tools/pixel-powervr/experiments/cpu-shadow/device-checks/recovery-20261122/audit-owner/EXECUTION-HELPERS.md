# Separate execution phase

These files are ready for root review. This agent has not used them on the
phone. The installed 18,144-byte outer owner remains byte-identical at SHA256
`af4b1478e37b52cf223bc86bf41df2c23f83d31dd5de287cfaabe64d0983bfe7`.

## Launcher

Review `launch_audit_execution.py`, then use its shell-safe clipboard form
`05-launch-execution.command.txt` only after inspecting the actual completed
preflight. The launcher verifies the source and the physical installation
receipt whose SHA256 is
`c4fb254cc076faa54e3409cc4a32b4440cb1b2624edc323fc8681961d4228ec2`.

Before creating launch artifacts or spawning a child, it loads only definitions
from the exact byte-verified outer wrapper with a non-main module name. It
reuses that wrapper's read-only preparation prerequisites and public-preflight
validator. It then requires unchanged preflight input metadata, the successful
and clean accepted exit, exact command and startup/exit identities, matching
preflight output hash, and absence of the recorded preflight wrapper and
auditor identities. It also binds them to the original detached preflight
launcher and installation receipt.

It refuses an existing audit work path or any execution phase artifact under
the owner directory. It does not create either the owner or audit work root.
Its only subprocess command is:

```sh
/data/data/com.termux/files/usr/bin/python -I -B \
  /data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-partition-audit-ebbc9c0.py \
  --execute
```

The detached launch uses `start_new_session=True`, stdin `DEVNULL`, and an
exclusive wrapper log. It returns immediately after writing its exclusive
launch receipt, including wrapper PID/start time/group/session and hashes of
the accepted preflight metadata. There is no wait, poll, signal, subreaper or
direct VM launch in this short caller. The unchanged wrapper owns its auditor
child, and the unchanged auditor owns native VM supervision.

New phone artifacts are limited to:

```
/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-partition-audit-ebbc9c0-execute-launch.json
/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-partition-audit-ebbc9c0-execute-wrapper.log
```

The wrapper itself writes its exclusive execution receipts under the existing
owner directory. The auditor creates its fresh audit work only after its own
checks and lock acquisition. If any launch or receipt step fails, preserve the
artifacts and inspect the recorded owner before attempting recovery.

## Read-only observation

`status_audit_execution.py` embeds the exact previously reviewed bounded
metadata reader. Its default output is 19 lines, plus one line only for a
structured outer-wrapper refusal. It reports the detached wrapper, recorded
owner, auditor and QEMU PID/start identities; exact command checks; exit and
cleanup fields; native VM witnesses and elapsed time; final audit status and
unchanged identities; result/session hash agreement; filesystem check status;
and resources.

- `06-status-execution-compact.command.txt`: compact terminal view.
- `07-status-execution-json.command.txt`: full selected JSON metadata.

The reader accesses bounded source/receipt/VM-result/audit-result JSON, process
stat fields, memory information and free-space metadata. It reads no guest,
serial or VM run logs. A small wrapper log is parsed only for a structured
`OWNER_REFUSED` error. It performs no process action and writes no file.

`PARTITION_AUDIT_COMPLETE_ACCEPTED` requires matching accepted owner/result/
session receipts and absence of the recorded wrapper, auditor and helper
identities. Running/finalizing remains distinct. Inspect the actual audit
result and required filesystem evidence as well; the status command is an
observer. Boot, GPU and app qualification do not become complete here.

## Verification

`repo_recovery` reviewed both helper sources and found no blocking issue.
`execution-helper-validation.json` records six narrow synthetic checks of the
new receipt-consumption gate, failed input/identity cases, and the compact
missing-evidence observation. They started zero real subprocesses and performed
no phone action. Clipboard argument lists and compressed source round trips
were checked byte for byte. Exact hashes are in
`execution-helpers-manifest.json`.
