## Latest diagnosis: iOSRoot alternate-header flag

The read-only eight-header follow-up completed at 16:39:46 UTC. All eight headers have the journal bit set; the saved and baseline iOSRoot alternate headers both contain legacy boot-inconsistent bit 11. Their corresponding saved/baseline 512-byte header hashes match. No header has modern runtime-inconsistent bit 14. The saved Data primary has its clean-unmount bit clear while baseline Data primary has it set.

This identifies the exact predicate that rejected the unchanged inspector; it does not establish filesystem health or an inspection pass. No JIB/journal payload or fsck result was obtained, and no acceptance code was changed. See [header diagnosis and exact evidence](header-diagnostic/README.md). All prior saved-inspection work and both failed help-gated capability attempts remain preserved.

# Fresh saved-firstboot inspection with independent process observation

This package prepares a fresh `resume2` inspection of the accepted firstboot
`07-0004`. The failed `resume1` inspection remains preserved. This source package
does not establish a new preflight or inspection success.

The counter1 host inspector, guest inspector, frozen preparation runner, native
runtime, cleanup rules, filesystem checks and success criteria remain unchanged.
The new outer owner uses fresh inspection paths and additionally verifies all
nineteen independently reviewed source/receipt pins from the failed predecessor.
It requires the prior wrapper, inspector and QEMU identities to be absent, checks
the old inspection lock without writing it, and carries all nineteen hashes into
its before/after input-preservation checks. Every existing owner function except
`prerequisites` is AST-identical to the accepted `resume1` source; that function
adds the predecessor-preservation call. The two new functions implement those
read-only checks.

## Bound paths

| Role | Phone path |
| --- | --- |
| Accepted firstboot guard, unchanged | `/data/local/tmp/pixel-firstboot-guard-e9cc754-resume1` |
| Counter1 inspector sources, unchanged | `/data/local/tmp/pixel-saved-checks-counter1` |
| Preserved failed inspection | `/data/local/tmp/pixel-saved-audit-e9cc754-resume1` |
| New inspection output | `/data/local/tmp/pixel-saved-audit-e9cc754-resume2` |
| New owner source | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-saved-inspection-resume2.py` |
| New owner receipts | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume2-owner` |
| New source-transfer directory | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/saved-inspection-resume2-transfer` |

The nine accepted-firstboot pins stay exactly as observed for `07-0004`; their
paths intentionally retain `resume1`. The nineteen failed-inspection bindings
come from `../resume1-saved-inspection/physical-observations/failure-bindings-selected.json`,
SHA-256 `3f17a220fbb6a52c886a1eaa85833cd76d7d6b782d8537a2f698bb7a97e7019a`.
Those bindings were independently compared with all 608 decimal digest bytes in
the original screenshots. They describe a rejected inspection, not success.

## Source staging and read-only preflight

After independent package review, run the seven commands in `source-transfer/`,
from `00-begin.command.txt` through `06-assemble-install.command.txt`, in order.
They exclusively install only the new outer owner and detached preflight
launcher. Each bounded step validates its input and readback; an existing target
is preserved and causes refusal. No source-transfer command starts a process
under inspection or launches a guest.

`launch-preflight.command.txt` starts the fresh owner in `--preflight` mode.
`observe-preflight.command.txt` then checks actual accepted receipts, clean reap,
absent preflight identities, unchanged bound inputs, fresh output paths, and the
raw captured stdout's length and SHA-256, including all 32 decimal digest bytes.

The inspector's public preflight session omits the requested output directory.
Its newly observed stdout can therefore legitimately equal the earlier
9,070-byte preflight. A matching digest alone does not establish fresh execution:
the new source, launch, command, prerequisite, owner and exit receipts must bind
the actual `resume2` invocation.

## Execution remains unreleased

`execution-state.json` deliberately has no actual new preflight or monitor-ready
binding. The execution launcher will be constructed only after the fresh
preflight is observed and the independently owned process observer has supplied
an actual ready receipt and matching live process identity.

The observer is a separate detached process outside the inspection's ownership
tree. It does not signal, reap, trace or launch observed processes. Its readiness
must identify the exact new inspection source, preflight, owner directory, work
directory, QEMU child record and qualified executable. A fresh running heartbeat
and finite observation bounds are required before the execution launcher starts
the inspection owner. The inspection owner does not wait for monitor completion;
its result and cleanup criteria remain independent. The monitor may finish after
the recorded owner exit and its bounded residual-identity observation.

Execution retains the original 2,816 MiB available-memory launch floor,
2,048 MiB helper RAM, 512 MiB running floor and 1,536 MiB free-storage floor.
Forced cleanup still fails. There is no PID exemption, rewritten cleanup
receipt, cleanup-delay change, disk repair, TCG fallback or downstream release.

## Focused offline validation

`offline-validation.json` pins the current owner, tests and exact test log.
Twenty-two focused tests pass. Existing tests cover accepted-firstboot binding,
read-only preflight, actual stdout pins, one-shot execution, owned-child reap and
strict returned-output acceptance. Added cases cover missing or changed prior
failure pins, repinned inconsistent failure, still-live prior identities, an
occupied prior lock, changed prior evidence after execution, and nonempty forced
descendants. The tests use synthetic metadata and tiny local Python children;
they do not run the phone, native guest, QEMU, images or GPU.

`owner-preparation.json` records the AST comparison and exact predecessor input
bindings. `preflight-package-status.json` and `transport-steps.json` record source
and command hashes. Physical observations and any later release reviews are
separate evidence and do not replace these preserved source records.

## Observed fresh preflight

All seven source-transfer steps succeeded on the Pixel with both installed
source hashes matching the reviewed package. The new preflight owner launched
at 2026-11-22T15:37:09.352352Z as PID 32296/start 8685433. At
15:38:40.651056Z the read-only observer reported accepted preflight, both exit
codes zero, clean unforced reap, absent wrapper/inspector/work, unchanged prior
inputs and no inspection execution.

The actually captured stdout is 9,070 bytes, SHA-256
`84b31f4f08744f6adeb20ab5af308b1d10c839803c051d4bba577201a4ad3760`.
`independent-preflight-evidence-review.json` verifies all 32 decimal digest bytes
and the fresh source/path/phase predicates against the new screenshot. The
matching earlier stdout digest does not replace that new physical evidence.
Execution remains pending the reviewed independent observer and its actual
ready receipt/live identity. Installed owner, preflight and transfer bytes are
frozen; any execution transport is a separate artifact.

## Preserved execution candidate and Android capability boundary

The first execution-only source is finalized at 21,154 bytes, SHA-256
`6ab62a4b57bd99615fd8e4abbd7ace37a682854e23bee1abf5f2a767f24ed982`.
Its five separate source-transfer commands, monitor-pinned draft, thirteen
passing focused readiness tests and read-only result observer are retained.
Neither this execution candidate nor its monitor was installed or launched.

A physical self-only Android probe then found
`/proc/4573/task/4573/children` absent. The monitor bound by this candidate
requires that surface in its initial self-probe and would refuse before READY.
This is a diagnostic-observer capability boundary; the accepted fresh preflight
and unchanged inspection owner/runtime remain intact. A separately named
bounded `/proc` stat fallback candidate and matching execution source/transport
are required before staging. The original candidate bytes are preserved.

## Current continuation: procstat1 and the actual guest boundary

The separately reviewed procstat1 observer and execution integration are in
`procstat1/`. That fresh inspection has actually run. Its native VM exited
cleanly with no forced descendants, while the saved-filesystem inspection
returned `INCOMPLETE` at its classified guest-result boundary. The retained
source/input/backing-chain checks passed and all recorded inspection processes
were absent. `procstat1/README.md` and `procstat1/revision-status.json` record
the launch, exact rejected result and independent evidence reviews. No
inspection success or downstream release is claimed.

`observe-guest-boundary.command.txt` is the independently reviewed, compact
read-only next query. It binds the actual failed owner and clean native VM, then
reports only classified guest error codes and allowlisted journal/fsck metadata.
It preserves absent metadata as unavailable. It exports no raw guest logs or
private file inventories and performs no runtime, disk or acceptance change.
