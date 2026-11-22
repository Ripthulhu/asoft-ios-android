# Resume3 process observer: reviewed algorithm, fresh scope

## Source-only checkpoint

This package ports the independently reviewed resume2 `procstat1` observer to
the fresh resume3 saved inspection. It changes only the observation paths,
inspector command path, receipt-kind labels and exact source bindings.
`test_port.py` compares complete Python syntax trees with the prior reviewed
sources after normalizing only those bindings. The observer algorithm,
detached-launch lifecycle, readiness gates, sampling bounds, native-role
classification, and corrected final-reader semantics are unchanged.

At this source checkpoint there is **no observed resume3 preflight or observer
execution**. Preflight pins remain `None`, and the builder does not produce
launch/readiness commands until the actual new preflight is supplied. The
source-install packet can be reviewed and staged independently. No old
preflight output or observer readiness receipt is adopted.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Observer | 37,877 | `4064333cabad9120c03716da9e95b358f05fc30365885b05501857f432a92af1` |
| Detached launcher | 6,252 | `304f13f16f1ba6f146348aa6fe73d9d531bde8b346e2df91e856cb7c50119a32` |
| Resume3 inspection owner | 48,469 | `91ac3ba2ba8c3e40b2a99dfffdc4a53ae49b8e441245755f33ef761846d61e14` |
| Source transfer manifest | See file | `affe3f299edc825a462e69d21f88771fc8c24971eea62b610f6bee6b6e10fc02` |

The owner is separately packaged under `../../resume3-saved-inspection/`.
It binds the reviewed resume3 inspector pair. Observer diagnostics do not
alter that inspector's acceptance or filesystem policy.

## Exact fresh paths

`BASE` is `/data/local/tmp/pixel-gpu-transfer-sxtv33sh`.

| Purpose | Phone path |
| --- | --- |
| Observer source | `BASE/run-ios26-saved-inspection-resume3-observer-procstat1.py` |
| Detached launcher | `BASE/launch-ios26-saved-inspection-resume3-observer-procstat1.py` |
| Observer output | `BASE/ios26-saved-inspection-resume3-observer-procstat1` |
| Observer launch receipt | `BASE/ios26-saved-inspection-resume3-observer-procstat1-launch.json` |
| Observer wrapper log | `BASE/ios26-saved-inspection-resume3-observer-procstat1-wrapper.log` |
| Target owner | `BASE/ios26-saved-inspection-resume3-owner` |
| Target work | `/data/local/tmp/pixel-saved-audit-e9cc754-resume3` |
| Inspector source directory | `/data/local/tmp/pixel-saved-checks-resume3` |

The accepted firstboot guard remains
`/data/local/tmp/pixel-firstboot-guard-e9cc754-resume1`. That existing input path
is intentional. No resume1/resume2 observer, inspector, failure or diagnostic
file is overwritten by this port.

## Preserved behavior and limits

The observer runs in its own detached session before the separately detached
inspection owner. It binds owner/inspector identities from their ordinary
receipts and the QEMU identity from the actual new child/launch receipts.
Numeric PID reuse never transfers ownership. Native factory/worker roles
require receipt-anchored ancestry, the expected executable, and the observed
native process name. Known identities remain tracked through adoption.

Discovery scans numeric `/proc` stat records once per second, discarding
unrelated rows without exporting names, executable paths, command lines or
inventories. Owned snapshots use a 200 ms cadence and a 20 ms burst after
changes. The observer sends no target signals, reaps no target, uses no ptrace,
and never writes target-process files.

The unchanged bounds include 9,000 seconds total, 600 seconds waiting for the
execution owner, 5 seconds after outer exit, 128 process identities, 2,048
numeric entries per discovery scan, 10,000 event records, 8 MiB event bytes,
and less than 9 MiB total own output component caps. Read gaps, sampling gaps,
caps, ambiguous PID reuse and unobserved transitions remain explicit.

Observer completion is diagnostic completion, not inspection success.
Disappearance is not an exit status; pending SIGKILL does not identify its
sender. This run cannot retrospectively classify old forced PID 13344 or
establish a cleanup/grace fix.

## Transport, readiness and result queries

`transport-steps.json` lists seven exclusive install-only commands in
`source-transfer/`, maximum 5,435 bytes. They install exactly two sources,
verify the new owner source, and read back exact bytes. They create neither an
observer output directory nor an inspection process.

The matching inspection execution launcher should be installed before starting
the observer. Once an actual fresh preflight is observed, its byte count and
digest must be bound in both `build_transport.py` and `observe_ready.py`.
`preflight-binding.json` will retain that actual observation. Only then may the
builder generate `launch-observer.command.txt` and `observe-ready.command.txt`.
The latter retains exact source/ready/launch identity, detached session, live
argv, heartbeat freshness and remaining owner-wait checks. The separate
inspection launcher must bind the actual new readiness receipt and identity.

The corrected read-only status/final queries are already generated under
`projection-pin1/`. They retain a missing cleanup field as unavailable, distinct
from an observed empty forced-descendant list. Compact output is capped at 69
logical lines; the full selected JSON projection is capped at 128 KiB. Each
command is under 6,000 bytes. They inspect selected process/receipt metadata,
not guest logs.

## Offline validation

`offline-validation.json` and the retained logs record:

- 41 observer, installation-replay, bounded-command and port-equivalence tests.
- 12 corrected projection tests, including unavailable/empty cleanup evidence,
  PID reuse, classification limits, exact compressed command reconstruction
  and bounded terminal output.

`port-provenance.json` records the original reviewed source hashes and owner
binding. Independent release and physical observations are separate records;
offline results do not claim a phone outcome.
