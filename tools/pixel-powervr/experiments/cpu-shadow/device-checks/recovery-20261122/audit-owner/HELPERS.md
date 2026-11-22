# Reviewed staging and preflight helpers

These helpers are standalone source files. Their companion `.command.txt`
files are shell-safe, single-command clipboard forms for the root phone
terminal. Each clipboard form invokes the Termux Python with `-I -B`, verifies
the decompressed helper's exact byte length and SHA256, then executes that
reviewed helper. No source helper depends on being installed beside another
helper. Full source, command lengths and hashes are in `helpers-manifest.json`.

## Use in order

1. `01-install-owner.command.txt` runs `install_audit_owner.py`. It installs
   only the reviewed 18,144-byte outer wrapper with SHA256
   `af4b1478e37b52cf223bc86bf41df2c23f83d31dd5de287cfaabe64d0983bfe7`
   at the fresh phone source path and writes an exclusive installation receipt.
   It verifies the embedded bytes, installed bytes, root ownership and `0644`
   mode. It creates no process and never runs the wrapper or auditor. Preserve
   any existing or partially created source/receipt; a duplicate call refuses.
2. Inspect the installation receipt. Then
   `02-launch-preflight.command.txt` runs `launch_audit_preflight.py`. It
   verifies the installed source and receipt, reserves an exclusive launch
   receipt and wrapper log, and launches exactly:

   ```sh
   /data/data/com.termux/files/usr/bin/python -I -B \
     /data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-partition-audit-ebbc9c0.py \
     --preflight
   ```

   The detached wrapper receives `start_new_session=True`, stdin `DEVNULL`,
   stdout the exclusive wrapper log and stderr the same log. The launcher
   records PID, start time, process group and session, then returns immediately.
   It does not wait, poll, signal, or become a subreaper. The wrapper remains
   the auditor's parent and performs its wait/cleanup. The wrapper runs the
   unchanged documented auditor command with `-B`, without `--execute`.
3. `03-status-compact.command.txt` runs the read-only compact status projection.
   It embeds the exact reviewed full reader and emits 15 lines, plus one line
   only if a structured outer-wrapper refusal exists. Repeating this command
   reads bounded metadata and process/resource information only.
4. `04-status-json.command.txt` runs the same reader as full JSON when exact
   selected metadata needs to be retained. It reads no guest, serial or VM
   logs. Its only log input is the small outer-wrapper log, from which it may
   select an `OWNER_REFUSED` JSON error.

The launcher receipt and log are outside the wrapper's owner directory:

```
/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-partition-audit-ebbc9c0-install.json
/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-partition-audit-ebbc9c0-preflight-launch.json
/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-partition-audit-ebbc9c0-preflight-wrapper.log
```

The status reader checks PID plus start time and reports reused PIDs without
acting on them. A zero status-reader exit is observation only. Its completed
preflight label means the retained preflight receipts agree and recorded
process identities are absent; it is not a partition audit pass or a fresh
execution-prerequisite check. The execution wrapper must still perform its
own checks before a separately authorized execution launch.

The synthetic example file is explicitly local test output, not phone evidence.
Five focused helper validations passed using temporary local fixtures, a
simulated root identity and a mocked child. No real subprocess was started by
those validations. The compact projection was checked only for exact embedded
source and its 15-line output; no additional device/test job was run.

This agent performed no phone operation. The parent operator owns staging,
preflight launch, inspection and any later execution decision.
