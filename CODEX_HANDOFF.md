# Codex handoff — native Pixel iOS26 work

**Current continuation** · The [diskless ramdisk probe](tools/pixel-powervr/experiments/cpu-shadow/device-checks/recovery-20261122/ramdisk-capability-probe/RESULT.md)
ran once after available memory cleared the original floor. It reached a
root Darwin shell with clean native witnesses and teardown. Root-source
identification and unmount capability remain open. Preserve that completed
run. The original handoff below records the preceding checkpoint.

**Paused at the user's request on 2026-11-22 after completing the read-only
Data journal diagnostic. Commit and push this checkpoint; continue development
in Codex. No new maintenance probe has been implemented, installed or run.**

Repository: `Ripthulhu/asoft-ios-android`

Branch: `pixel10-gpu-integration`

## Read first

1. [Current continuation guide](tools/pixel-powervr/experiments/cpu-shadow/CONTINUE-PIXEL.md).
2. [Current recovery state](tools/pixel-powervr/experiments/cpu-shadow/device-checks/recovery-20261122/CURRENT_STATE.md).
3. [Completed Data journal diagnostic](tools/pixel-powervr/experiments/cpu-shadow/device-checks/recovery-20261122/resume5-saved-inspection/data-journal-diagnostic/RESULT.md)
   and [exact current result/source bindings](tools/pixel-powervr/experiments/cpu-shadow/device-checks/recovery-20261122/resume5-saved-inspection/data-journal-diagnostic/source-status-current.json).
4. [Rejected resume5 saved inspection](tools/pixel-powervr/experiments/cpu-shadow/device-checks/recovery-20261122/resume5-saved-inspection/RESULT.md).

The earlier prepared/not-executed documents are historical snapshots. Prefer
the current status and actual observation files above. Never infer that an old
work path is unused from a historical preflight.

## Exact completed boundary

- The accepted guarded firstboot `07-0004` remains preserved. Do not repeat it.
- Resume5's native VM completed normally, with all three native witnesses and
  clean unforced cleanup. Its saved inspection remained `INCOMPLETE`.
- The strict raw iOSRoot initialization classification passed. Data was refused
  as `nonempty_journal`: journal start **512**, end **614400**. Neither forced
  read-only filesystem check ran.
- The separate Data diagnostic completed once at **21:35:42.308919 UTC**. Four
  fixed native image-tool reads were cleanly reaped. Supported structure checks
  passed for **six transaction-start lists and 49 live payload entries**, with
  all 49 payload checksums and target bounds verified.
- Six list headers plus **318,976 payload bytes** account for all **613,888
  active interval bytes**. The independently transcribed actual-bound summary
  and both record pages reproduce that result from the retained bytes.
- Actual diagnostic result: **13,026 bytes**, SHA-256
  `6d1829c3a1a4982e4cdcf11a6854fb862f93a12d5025a783331d4a578de28efc`.
- Diagnostic owner/child PIDs and prior inspection identities were absent at
  the bound observations. Bound metadata/tooling and disk identities were
  unchanged. The diagnostic did **not** recompute whole-image hashes.
- No journal replay, mount, repair, fsck or new guest VM occurred in the
  diagnostic. Filesystem consistency and replay safety are not established.

The reviewed diagnostic sources and transport were published at
`caf8e1757ac75a272a5577ae578d7a9918c7c560`, parent
`2630efc33bebd65a0a61eb9166da4eb0ecca2483` (the completed rejected inspection).
This checkpoint adds actual installation/result evidence, the independently
reviewed result readers and updated continuation documents.

## Next proposed work — design only

Investigate a **new diskless Darwin shell-ramdisk capability probe**, using
`rd=md0`, the existing pinned research kernel, shell ramdisk, trust cache and
qualified hybrid runtime. Attach **no iOS image, COW overlay or backing disk**
to this first probe. Use fresh task-owned paths and the existing native,
counter, memfd, resource, bounded-output, ownership and cleanup gates.

Its narrow purpose would be to establish actual root UID/EUID, fixed utility
presence/executability and the observed root mount identity. A requested
`rd=md0` boot argument or `/dev/md0` presence does not prove which filesystem
is mounted at `/`. The proposed guest protocol would use nonce-bound output,
fixed paths and selected scalars; no private inventory should be exported.
How to obtain an exact bounded root-mount observation remains to be designed
and independently reviewed.

**No resume6 source, parser, builder, tests, transport or runtime package exists
at this handoff.** The proposed host and guest API was discussed only; no
unfinished executable implementation needs to be resumed or trusted.

If that entry point is qualified, a later distinct recovery attempt could use
a **fresh COW descendant** of the saved firstboot image, let Darwin's HFS
implementation mount/replay Data, and verify one clean non-forced unmount.
This is a candidate workflow, not a released procedure or an assertion that
the needed utilities or unmount capability are available. Preserve failures;
do not force unmount, kill guessed guest daemons or retry automatically.

Do not turn the current active-interval parser into an offline replay writer.
Its explicit limitations include unexamined inactive journal contents,
unevaluated replay/coalescing semantics and no binding between the header
sequence and the first or last transaction. The pinned Linux hfsprogs path
does not implement journal replay. The existing normal iOS26 shutdown uses
guest `sync` followed by QMP stop/quit and does not establish a clean Data
unmount. See the diagnostic result, [partition audit](tools/pixel-powervr/experiments/cpu-shadow/IOS26-PARTITION-AUDIT.md),
and [current guest shutdown implementation](app/src/main/java/com/asoft/ios/Guest.java).

## Non-negotiable continuation constraints

- Native EL0 plus kernel TCG; **no TCG-only fallback**.
- **No APK until the GPU path is complete.** App, GPU and APK gates remain closed.
- Do not weaken filesystem acceptance, native witnesses, cleanup, resource or
  preservation gates. A structural journal result does not satisfy fsck.
- Never relaunch completed firstboots, inspections, preflights, observers or
  diagnostics. Retain all original chains, attempts, receipts and installed
  sources, including explicitly unreleased historical precursors.
- No unrelated process termination, manual app thaw or persistent policy or
  security changes.
- Public repository scope: reviewed source, selected metadata, hashes and task
  screenshots. Keep raw Apple images, headers/JIB/journal payloads, raw guest
  logs and private file inventories off the repository.

## Phone and source locations

Phone diagnostic output:
`/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-data-journal-diagnostic-resume5`.

Installed diagnostic host:
`/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-data-journal-diagnostic-resume5.py`.

Installed pure parser:
`/data/local/tmp/pixel-gpu-transfer-sxtv33sh/parse-ios26-data-journal-resume5.py`.

Preparation root: `/data/local/tmp/pixel-prep-e9cc754`.
Completed resume5 inspection work:
`/data/local/tmp/pixel-saved-audit-e9cc754-resume5`.

The actual phone work used the user's connected Tango terminal browser tab.
Do not assume a new Codex session inherits that connection or shell state.
Verify available access and the exact current receipts before any new device
action. The saved files and source checks establish the prior checkpoint;
they are not fresh process or resource observations.

All collaborating work was stopped before publication. There are no running
agent tasks or pending guest operations from this handoff.
