# Recoverable firstboot execution owner

The reviewed outer owner was installed at 12:06:06 UTC and launched at
12:06:51 UTC on November 22. It exited cleanly at 12:09:06 UTC with an
incomplete firstboot: Python lacked os.memfd_create, so no QEMU VM was
launched. The failed 07-0001 attempt and all receipts remain preserved.
The source-authoring/review agents performed no phone operations. The staged
firstboot guard and four frozen preparation files remain unchanged.

## Final files

| Purpose | Source | Clipboard transport |
|---|---|---|
| Install only the new outer source | `install_firstboot_owner.py` | `01-install-firstboot-owner.command.txt` |
| Start one detached execution owner | `launch_firstboot_owner.py` | `02-launch-firstboot-owner.command.txt` |
| Read compact selected status | `status_firstboot_owner.py` | `03-status-firstboot-compact.command.txt` |
| Read selected status as JSON | `status_firstboot_owner.py` | `04-status-firstboot-json.command.txt` |

The outer source is `run_firstboot_owner.py`, 18,957 bytes, SHA256
`605f194f89cc59dd4025e587a0fc2239920b0850e089943bca9e9ea0656eee57`.
`manifest.json` records all helper and transport hashes. `review-complete.json`
records the final review clearance separately from the packaging snapshot.

The installer reserves the source and installation receipt exclusively,
verifies the exact embedded and read-back bytes, and starts no process. Its
phone source target is:

```
/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-firstboot-owner-ebbc9c0.py
```

The launcher verifies those bytes and the installation receipt before loading
the owner's definitions with a non-main module name. It runs only read-only
prerequisite checks in that caller, then detaches:

```sh
/data/data/com.termux/files/usr/bin/python -I -B \
  /data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-firstboot-owner-ebbc9c0.py \
  --execute
```

The launcher returns after writing its exclusive launch receipt. It does not
wait, signal, or become a subreaper. The outer owner remains the parent of the
unchanged guard. The guard receives its documented `python -B` argv with only
`--execute` appended, and owns the frozen in-process preparation execution.

## Preconditions

The owner consumes the already accepted 21,952-byte firstboot preflight with
SHA256 `eda974e4e726b0164f8c5bbcda232c972db53622e22b1736f1091717b2e4713b`.
It verifies its command/startup/exit receipts, absent process identities,
unchanged source and input metadata, the accepted partition audit and its clean
outer-owner exit, the exact seven-checkpoint boundary, an available preparation
lock, and absence of previous native children.

It checks **3,840 MiB / 4,026,531,840 bytes MemAvailable** and **4,500,000,000
free bytes** before reserving its owner directory, and again immediately before
spawning the guard. The guard performs its own unchanged full preflight and
fresh VM resource checks. No cache reclamation, app termination, VM RAM change,
threshold reduction or kernel-setting change is performed by these helpers.

The outer owner directory, guard work and phase-specific launcher artifacts
must be fresh. Unknown or incomplete artifacts are preserved; no retry or
artifact adoption occurs automatically. The owner directory is
`/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-firstboot-owner-ebbc9c0`.
The guard alone creates `/data/local/tmp/pixel-firstboot-guard-e9cc754`.

## Ownership, limits and completion

The original VM deadline remains **3,600 seconds**. A **5,400-second outer
owner bound** allows guard preflight, checkpoint checking and final evidence
work. On interruption or timeout, the outer owner sends SIGTERM only to its own
unreaped guard child and grants 180 seconds for the original native cleanup.
If necessary it kills only that direct child and allows 30 seconds to reap it.
No name-based or blanket group kill is used. The guard retains QEMU's original
separate process group, PDEATHSIG and subreaper behavior.

Any forced guard cleanup is incomplete and requires an explicit owned-process
recheck. The outer owner never infers clean QEMU cleanup from its guard child's
exit alone.

A complete result requires the guard's accepted firstboot checkpoint, unchanged
bound inputs, the actual new attempt, all four attempt metadata files, matching
guard session and observations, the original native controlled-stop predicate,
the shell-sync witness and the unique verified zero-failure counter event. It
also requires current predecessor/checkpoint hashes, QEMU absence, an available
preparation lock and no remaining native child.

Firstboot is a controlled QMP stop/quit. Natural helper exit and `ASOFT: done 0`
are not imposed on this guest boot. Zero reported guest I/O failures still do
not expose QMP stop's internal flush return. The separate saved-firstboot
filesystem/journal inspection remains the next required gate.

The status reader selects bounded metadata and process/resource observations.
It reads no guest serial or VM run logs. It verifies current attempt metadata
against the accepted result and requires the recorded wrapper, guard and QEMU
identities to be absent before displaying completed acceptance. Running or
finalizing remains distinct. Final boot, GPU and app qualification flags remain
false at this initial setup boundary.

## Review and validation

`host_clock_fix` cleared the core owner, including native firstboot semantics,
receipt bindings and cleanup envelope. `repo_recovery` cleared the transfer,
detachment and status helpers; both reviewers cleared the final status checks.
Final sources parse, the installer payload equals the reviewed owner exactly,
the launcher pins and argv match, and every clipboard command round-trips to
its reviewed source. No existing guard suite was rerun and no real child or
device job was launched by this authoring agent.

## Physical installation and launch

The root agent installed the exact outer source at **2026-11-22 12:06:06 UTC**.
The selected [installation record](install-observation-120606.json) and original
[screenshot](owner-install-120606.jpg) record 18,957 bytes and the reviewed SHA.
The unchanged helper transports were executed with only their final newline
removed for clipboard submission. Existing source, receipt and work names must
not be overwritten or relaunched.

A [fresh conditions check](launch-conditions-120630.json) at **12:06:30 UTC**
reported 4,340,904 KiB MemAvailable, 74,343,567,360 free bytes, battery capacity
74, raw battery temperature 282, health Good, USB online and thermal status 0.
All displayed 10/60/300-second memory-pressure averages were zero. No RAM
reclamation or application termination was needed or performed.

The [launch receipt observation](launch-observation-120651.json) records
**12:06:51 UTC**, wrapper **26052/start 7423681**, in its own matching process
group/session. The launcher's memory check read **4,196,081,664 bytes**, above
the unchanged 4,026,531,840-byte floor; free space was 74,869,415,936 bytes.
The installed-source receipt SHA was
`c6d5b42e82dc773e26d0424b855c86de478432f39c48aedd039f50d1436f913a`.
The launcher returned to the root prompt; the owner continued independently.

The first [12:07:17 UTC observation](status-observation-120717.json) found that
wrapper and guard **26054/start 7423704** live with matching source and commands.
The [12:08:38 UTC observation](status-observation-120838.json) still found both
live and now found the guard session equal to the accepted preflight. No VM
attempt had yet been observed. These are input-validation observations, not
firstboot success or failure. Missing final hashes/receipts are pending.

All physical JSON files here are selected screenshot transcriptions, clearly
labelled as such. They are not exact-byte exports of the phone's receipts.
The complete original owner/guard/attempt files remain on the phone; only
bounded selected metadata is displayed. No guest serial logs or Apple binaries
are exported.

## Recovery of this completed, incomplete owner

Use `03-status-firstboot-compact.command.txt` for the reviewed read-only status
(or `04-status-firstboot-json.command.txt` for the selected structured view).
Do not rerun the installer or launcher. The owner receipt directory is
`/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-firstboot-owner-ebbc9c0`.
Its `command.json`, `inputs.json`, `owner.json` and eventual `exit.json`
identify the one guard child and accepted inputs. The separate launch receipt
and wrapper log are beside that directory. Read PID plus start time before any
owned-process action. A live owner would exclude another phone VM/GPU job; this owner and guard
were confirmed absent at 12:10:21 UTC.

After completion, require the fully consistent accepted status and all recorded
identities absent. Then the saved-firstboot inspector is mandatory before any
later Linux disk mutation. Initial setup completion still leaves
`gpu_path_complete=false` and the final APK gate open.

## Preserved pre-VM failure

The [12:10:21 UTC observation](completion-observation-121021.json) found the
wrapper and guard absent, exit 2, guard reaped, no forced cleanup or cleanup
errors. The guard result is `INCOMPLETE`, with unchanged bound inputs and no
firstboot checkpoint. Its error is `AttributeError: module 'os' has no
attribute 'memfd_create'`. Only `stage-inputs.json` appears in the guard
result's attempt metadata inventory; no VM was launched. The frozen
`guest_stage` calls this API after creating a fresh overlay and copying boot
inputs but before allocating the fd or calling `supervise_vm`. Those new
07-0001 files and the old guard/owner work are retained.

The [read-only capability check](failure-details-121307.json) found Python
3.14.8 missing `os.memfd_create` and both `MFD_*` constants, while the required
fcntl seal constants and Bionic libc symbol are present. It made no memfd
call. The subsequent bounded smoke/adapter recovery is recorded separately.
No memory reclamation or threshold change was needed. Do not reuse the failed
work directory or its attempt; a compatible retry needs explicit adapter
provenance, a new preflight and fresh owner/guard paths.
