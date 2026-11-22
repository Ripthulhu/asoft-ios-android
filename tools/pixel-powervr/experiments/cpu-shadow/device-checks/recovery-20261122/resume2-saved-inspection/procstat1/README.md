# Execution integration for the bounded proc-stat observer

This separate revision preserves the unused task-children observer integration
and its source-transfer package in the parent directory. The Android self-only
probe found the task-children file absent. The replacement diagnostic observer
uses a bounded numeric `/proc` stat scan, while the saved inspection owner,
inspector, runtime, cleanup, acceptance and memory thresholds remain unchanged.

The accepted fresh preflight remains the independently reviewed 9,070-byte
resume2 observation with SHA-256
`84b31f4f08744f6adeb20ab5af308b1d10c839803c051d4bba577201a4ad3760`.
Its fresh source, command, detached launch, prerequisite and exit bindings are
checked again before inspection execution. The nine accepted firstboot pins
and nineteen prior failed-inspection pins remain enforced by the unchanged
35,799-byte owner.

## Separate observer and execution paths

The observer source, output and launch receipt have the `observer-procstat1`
name. The execution launcher source is staged separately as
`launch-ios26-saved-inspection-resume2-execute-procstat1.py` under the existing
transfer base. The target inspection owner/work and its final execute-launch
receipt remain the fresh resume2 paths; neither is reused from resume1.

The new monitor bounds include at most 4,096 `/proc` directory entries, 2,048
numeric entries, 4 MiB of discovery reads and 1,000 ms per discovery scan, with
1,000 ms between discovery scans. Existing owned-process sampling and finite
observer/runtime/output bounds remain explicit. Unrelated process metadata
is not exported. The ready proof must identify this discovery method, confirm
that the observer found its own identity, and report positive readable/numeric
counts and read bytes within all discovery bounds.

Execution still requires the actual ready file's observed length, all 32 digest
bytes and live PID/start identity. The launcher validates the ready source,
preflight, scope and bounds, independent session, exact live command and fresh
waiting heartbeat before creating execution artifacts and again immediately
before its single `Popen`. Stopped, traced, reused or finished observer identities
are refused. Both readiness checks are recorded. The observer and inspection
owner retain separate process ownership; no observer wait, signal or reap is
introduced into the inspection launcher.

The local `build_execution_command.py`, once finalized, reads only the selected
and independently reviewed actual-ready JSON to create the bounded command.
It does not execute the command. Source staging must finish before starting the
monitor so its 600-second owner-wait window is reserved for readiness review
and launch.

Read-only inspection status remains available through the parent's
`observe-inspection.command.txt`. If the unchanged inspector actually accepts,
the parent's `observe-success-pins-0.command.txt` through
`observe-success-pins-2.command.txt` collect fourteen newly observed resume2
bindings in pages of five, five and four. These commands still validate the
actual accepted result and every bound input; they cannot promote a failed
inspection or supply guessed result pins.

## Finalized source, actual readiness still pending

The procstat1 execution launcher is 22,286 bytes, SHA-256
`8b78cad291697db0987f101ec44e68c5de7b4ed7e5143ff5e9444bb714a91a2b`.
Its retained unreleased draft differs only in the final observer source pin.
Five separate exclusive source-transfer commands are at most 5,118 bytes each.
The final launcher has passed fourteen focused offline tests, with source and
log pins in `execution-offline-validation.json`. The local actual-ready command
builder is finalized; no actual monitor-ready input or launch command has yet
been produced. Final source staging awaits the independent integration review.
