# Execution readiness contract

The execution launcher remains unreleased until actual new preflight and
observer readiness records are available. This document specifies the intended
checks; it is not an executable command or a physical observation.

## Fresh preflight

Reuse the reviewed `resume1` execution launcher's source, installation,
prerequisite, detached-launch and accepted-preflight checks, adapted only to the
fresh inspection paths and exact installed owner hash. Supply the actually
observed `resume2` preflight stdout hash and length. Verify its new owner and
inspector identities are absent and its new phase receipts are consistent.
The new `prerequisites()` independently checks the accepted firstboot and the
preserved failed inspection before every phase. Reusing an equal stdout digest
is insufficient without these fresh phase/source/command bindings.

## Independent observer

The observer package owns these separate paths under
`/data/local/tmp/pixel-gpu-transfer-sxtv33sh`:

- Source: `run-ios26-saved-inspection-resume2-observer.py`
- Detached launcher: `launch-ios26-saved-inspection-resume2-observer.py`
- Output: `ios26-saved-inspection-resume2-observer/`
- Detached launch receipt: `ios26-saved-inspection-resume2-observer-launch.json`

The observer's ready record must bind its exact reviewed source, live
`{pid,start_ticks}` identity, detached process group/session, accepted new
preflight, exact inspection-owner source, and target scope. The scope includes
the fresh owner directory, inspection work directory, unchanged inspector
command plus `--execute`, `a1/vm.child.json`, and qualified QEMU executable.
The QEMU path is derived from the already validated preparation session's
package, not guessed from a process name.

The readiness source contract also requires an atomic `RUNNING` heartbeat with
the same observer identity/source/scope and a current monotonic timestamp.
The launcher must validate the finite observation and owner-wait bounds, refuse
an observer that has exited or exhausted its bounds, and repeat the live
identity/heartbeat check immediately before starting the fresh inspection owner.
The actual ready bytes, hash and identity will be pinned from phone observation;
the changing heartbeat is validated for identity, scope and freshness rather
than assigned a static hash.

The proposed observer limits are 9,000 seconds total, 600 seconds waiting for the
inspection owner, 128 process identities, 10,000 events and 8 MiB of event data.
The final execution source must use the exact reviewed observer contract and
source hashes once that package is frozen; proposed values here confer no
runtime release.

## Ownership and evidence

The observer and inspection owner are separate detached siblings. The observer
has no inspection child to reap and cannot signal, trace, stop or launch observed
processes. The execution launcher does not adopt the observer. It starts only
the inspection owner after readiness validation. The inspection owner retains
its original direct-child supervision and writes its exit receipt without
waiting for the observer, avoiding a cycle with the observer's terminal-state
collection. The observer can then finish its bounded residual observation and
write its own exit records.

The execution-launch receipt should preserve the observed ready record hash,
observer source and identity, selected current heartbeat timing, exact scope and
bounds, and the independently validated preflight metadata hashes. These extra
diagnostic records cannot replace the unchanged inspector's native, disk,
filesystem and cleanup acceptance. A repeated forced-descendant result remains
a failed inspection even if the observer diagnoses the process successfully.
