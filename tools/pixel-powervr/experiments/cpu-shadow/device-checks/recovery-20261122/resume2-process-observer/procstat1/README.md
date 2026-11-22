# Resume2 process observer: numeric stat discovery

## Checkpoint

This revision is a separate diagnostic observer for the fresh, unchanged saved
inspection at `/data/local/tmp/pixel-saved-audit-e9cc754-resume2`. Its detached
launch was observed at **2026-11-22 15:56:49.922589 UTC**, and live readiness was
independently verified at **15:57:24.246217 UTC**. The observer identity was
`11031/8803490`; its parent was PID 1 and its process group/session were both
11031. The actual ready receipt is 3,839 bytes, SHA-256
`4c3abfebaeee33ce4c1c59f5195292116b016bc869d27ff5f0e38a5047981a3d`.
Its discovery probe read 895 numeric records in 48.492579 ms with zero failed
reads; the heartbeat age at verification was about 0.254 seconds. This is
readiness evidence, not an inspection result. See
[the selected ready observation](physical-observations/monitor-ready-155724.json)
and [independent ready review](independent-ready-evidence-review.json).

The seven source installation commands had previously been observed to succeed
at the checkpoint recorded **15:55:18.201121 UTC**. The installation receipt says
`execution_started=false` and `inspection_started=false`. See
[the selected installation observation](physical-observations/sources-installed.json)
and its [screenshot](physical-observations/sources-installed.jpg).

The accepted firstboot `07-0004`, the failed resume1 saved inspection, all prior
failure evidence, the immutable counter1 inspector, and its acceptance rules
remain intact. This observer does not change guest execution, native worker
shutdown, cleanup, reaping, checkpoint state, or disk policy. The earlier forced
PID 13344 remains unclassified by the retained stderr evidence. A new observed
process must be identified from its own receipts and genealogy.

The original task-children observer one directory above was reviewed but never
installed or launched. Android did not expose its required
`/proc/PID/task/TID/children` interface. The separate procstat1 revision uses a
bounded numeric `/proc` scan. The physical compatibility query read 894 `stat`
records in 53.212 ms with zero vanished, denied, or malformed reads. It printed
only aggregate counts and the query's own identity. See
[the compatibility record](../DEVICE-COMPATIBILITY.md) and
[the selected scan observation](../physical-observations/proc-stat-surface-ready-154917.json).

## Frozen source and prerequisite bindings

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `observe_processes.py` | 37,878 | `a49ec9b11ba0fefda03e2a688e86422df53851c9ec146f21591961da20104bd2` |
| `launch_observer.py` | 6,252 | `c21d61a218240b63a32c6f8f08bf98d6ca5e06d8a1d740706fe58c7cbaa593f3` |
| Source transfer manifest | see file | `a560443a8d372545001df2c12a66f6c67e779bfe9965f7b500a13ff151c085a4` |
| Resume2 inspection owner | 35,799 | `445f16736ff3f0c4aca2f9d825f4b71b9264bc24b177fe3a8281ca9c6e0f1e0b` |
| Actual new resume2 preflight stdout | 9,070 | `84b31f4f08744f6adeb20ab5af308b1d10c839803c051d4bba577201a4ad3760` |

The actual preflight was observed at 15:38:40.651056 UTC. Its stdout happens to
repeat the prior successful preflight's digest, so the observer also binds the
new preflight command, startup and exit receipts, exact owner source, accepted
clean reap, and absence of the old preflight PID/start identities. The new work
and execution receipts must still be absent before the observer starts.

The independent source/install/launch/readiness review is retained in
[independent-source-release-review.json](independent-source-release-review.json),
11,912 bytes, SHA-256
`09eb2ae73bafd9cf5fbf15fc6ca556388aec0cc20fbf5fb39c821ec1aa544110`.
It does not assert a physical observer or inspection outcome.

## Ownership and observation

`BASE` is `/data/local/tmp/pixel-gpu-transfer-sxtv33sh`.

| Purpose | Phone path |
| --- | --- |
| Observer source | `BASE/run-ios26-saved-inspection-resume2-observer-procstat1.py` |
| Detached observer launcher | `BASE/launch-ios26-saved-inspection-resume2-observer-procstat1.py` |
| Observer's fresh output directory | `BASE/ios26-saved-inspection-resume2-observer-procstat1` |
| Observer launch receipt | `BASE/ios26-saved-inspection-resume2-observer-procstat1-launch.json` |
| Observer wrapper log | `BASE/ios26-saved-inspection-resume2-observer-procstat1-wrapper.log` |
| Observed inspection owner | `BASE/ios26-saved-inspection-resume2-owner` |
| Observed inspection work | `/data/local/tmp/pixel-saved-audit-e9cc754-resume2` |

The observer is launched into its own session before the separately detached
inspection owner. It is outside the inspector's descendant subtree. Its ready
receipt records its PID/start ticks, parent, group, session, source identity,
preflight identity, output path, exact observation scope, and finite bounds.
It verifies its own numeric stat record through the actual discovery interface
before creating `READY`.

The observer obtains the inspection wrapper and inspector identities from the
canonical `owner.json` and `command.json`. It obtains QEMU's identity from
`a1/vm.child.json`, bound to `a1/launch.json` and the exact native QEMU executable.
For a live QEMU anchor, `/proc/PID/exe` must match. An unavailable zombie exe is
explicitly recorded as unverified.

Numeric discovery retains only transient PID/start-ticks/parent tuples for
unrelated processes. It does not read unrelated command lines, executable
links, status, environment, or app inventories. Before adding a process to the
owned graph, it rechecks the cached child start ticks, current parent PID, and
the tracked parent's unchanged identity. It reads selected status and exe
metadata only for the anchored inspection subtree. Unrelated tuples are never
written to the observer's files or terminal output.

A native factory or worker role requires observed ancestry under the exact
receipt-bound QEMU, its executable identity, and `asoft-stubfac` or
`asoft-stubN`. A process first observed before its native name is set can be
promoted later when these conditions hold. Known identities stay tracked after
adoption by another parent. Reuse of a numeric PID does not transfer ownership.

The observer sends no signals to targets, does not wait for or reap targets,
and does not use ptrace, stop targets, or write their files. It handles only its
own termination signals to attempt final diagnostic receipts. The inspection
owner and immutable inspector finish independently of the observer.

## Bounds and limitations

| Bound | Value |
| --- | ---: |
| Total observer lifetime | 9,000 seconds |
| Wait for execution owner | 600 seconds |
| Residual observation after bound outer exit | 5 seconds |
| Root stat discovery interval | 1,000 ms |
| Owned process sampling | 200 ms; 20 ms for a 2-second burst after changes |
| Numeric entries per root scan | 2,048 |
| All directory entries per root scan | 4,096 |
| Total stat bytes per root scan | 4 MiB |
| Time check per root scan | 1,000 ms |
| Tracked process identities | 128 |
| Event records / bytes | 10,000 / 8 MiB |
| Total own output component caps, including atomic status temporary | below 9 MiB |

The 1-second discovery interval avoids rescanning every tracked parent or on
each 20-ms owned sample. At the single measured compatibility sample, full
discovery's 53.212-ms elapsed time occupied about 5.3% of the selected 1-second
cadence. This wall-clock ratio is not a CPU utilization measurement. Runtime
overhead can differ; status and summary record scan durations, intervals, bytes, and lost
reads. No complete-scan event is emitted on each interval, avoiding event
volume from unchanged root inventories.

The graph records parent/name changes, significant process states, pending
SIGKILL changes, disappearance and reuse. Ordinary runnable/sleeping transitions
are counted rather than individually logged. Samples separated by more than
`max(500 ms, 3 × intended owned interval)` produce explicit sampling-gap events.
Shorter delays and scan latency can still miss transitions. Discovery itself
may miss a process created and gone between scans. The retained monotonic event
times describe observations, not exact kernel transition times.

Missing or unstable initial receipt publication is retried for at most two
seconds with gap/recovery evidence. Stable malformed receipts and later changes
to bound receipts are rejected. A cap or timeout produces
`OBSERVER_INCOMPLETE`; compact final status/summary handling preserves a final
receipt even when the full status or summary exceeds its own capacity. Output
or disk errors can still prevent a final write.

`OBSERVATION_FINISHED` and observer exit zero mean only that the diagnostic
window finished. They do not mean the inspection passed. A process disappearing
from `/proc` supplies no exit status. A pending SIGKILL mask does not identify
the sender or prove which kill request caused termination. The unchanged
inspection acceptance continues to reject forced descendants.

## Commands and reviewable evidence

The source-only packet is [transport-steps.json](transport-steps.json): seven
commands under `source-transfer/`, maximum 5,435 bytes. It installs exactly the
observer and detached launcher, with exclusive fresh paths and exact readback.
It never launches either process or the inspection. The matching inspection
execution launcher must be staged before starting the observer so the
600-second owner-wait budget is available for actual launch.

`launch-observer.command.txt` is 1,711 bytes. It binds the installed launcher
and actual preflight. `observe-ready.command.txt` is 3,209 bytes; it verifies
the live observer's PID/start/session/argv, exact ready/source/scope/probe,
accepted new preflight, and heartbeat. It prints the actual ready receipt's
byte count, SHA-256 and all 32 decimal digest bytes. The separate inspection
execution launcher must bind those observed values and recheck live readiness.

The current separate read-only queries are under `projection-pin1/`; the
earlier reader candidate is preserved in this directory. The correction keeps
an unavailable cleanup forced-descendant field distinct from an observed empty
list. These readers do not change the installed observer.
The [independent reader review](projection-pin1/independent-projection-review.json)
passed for the corrected sources and all three exact compressed commands.
`projection-pin1/observe-status.command.txt` and
`projection-pin1/observe-final.command.txt` produce
at most 69 logical terminal lines. The final query verifies source, ready,
exit, summary, event bytes/count/hash, bound owner and QEMU identity. It maps
each cleanup PID to every matching observed identity and native role, with
parent/state/pending/timestamp evidence. Unmatched PIDs remain unclassified;
multiple observed start identities for the same number remain ambiguous.
`projection-pin1/observe-final-json.command.txt` provides the fuller bounded selected metadata
projection. None reads native stderr, guest serial, or raw guest output.

The compact view can omit additional rows explicitly. The full projection
limits forced PID numbers to 16 and retains at most 12 selected event points
per matching identity, with omission counts. Complete bounded event evidence
remains in the hash-bound `events.jsonl`. Final output is at most 128 KiB.

Validation records:

- [offline-validation.json](offline-validation.json) and
  [offline-tests.log](offline-tests.log): 35 focused checks, including stat
  parsing, PID reuse, ownership/adoption, native name promotion, scan privacy
  and caps, readiness refusal, output-bound finalization, exact transport
  reconstruction, full source installation replay, and repeat-install refusal.
- [projection-pin1/projection-validation.json](projection-pin1/projection-validation.json): twelve focused
  reader/command checks, including unmatched/ambiguous identities, terminal
  line bounds, event omission counts, read-only calls, exact command decoding,
  unavailable versus empty cleanup evidence, and AST-equivalent formatting
  used to keep each query under 6,000 bytes. The earlier nine-check reader
  record remains preserved separately.

Physical observations are separate from these offline checks. Do not infer a
saved-inspection pass or a cleanup explanation from source review or source
installation alone.
