# Prepared native helpers through apps

This is a **source-only package** for the three native Linux preparation
helpers after the accepted saved-firstboot inspection. It records no physical
helper run, app-copy audit or GPU result. Existing executed `resume1` sources
and evidence are unchanged.

The [owner draft](run_apps_prep_owner_UNRELEASED.py) deliberately has
`INSPECTION_SUCCESS_PINS = None`. Both `--preflight` and `--execute` refuse
before prerequisite reads, locks, directories or child processes until the
fourteen actual accepted inspection identities are bound. No owner installer,
detached launcher or execution command is released in this package.

## Exact scope and preserved contract

The only runner is the unchanged phone source
`/data/local/tmp/pixel-prep-runner-f4d64db/prepare_ios26.py`. The four frozen
source identities and preparation session digest remain the existing ones.
The newer checkout runner is not copied to the phone.

| Property | Required boundary |
| --- | --- |
| Accepted starting prefix | Eight checkpoints through `ios26-firstboot`, from `07-0004` |
| Remaining stages | `ios26-persona`, `ios26-activation`, `ios26-apps`, in that order |
| Fresh attempt names | `08-0001`, `09-0001`, `10-0001`; each must be absent initially |
| Final prefix | Exactly eleven linked checkpoints, ending at `ios26-apps` |
| Guest boots and network stages | Empty lists; neither permission is enabled |
| Native helper RAM and vCPUs | 2,048 MiB and four |
| Fresh helper memory floor | 2,816 MiB |
| Running memory floor | 512 MiB |
| Helper deadline | Existing supported 21,600 seconds per stage |
| Runner child deadline | 68,400 seconds for all three helpers; full prerequisite/result validation is separate |
| Preflight child deadline | 1,800 seconds |
| Running storage floor | Existing 1,536 MiB |
| Runner output bound | 64 MiB execution log; 4 MiB preflight output |

The new wrapper also requires 6,000,000,000 free bytes before starting the
execution child. The frozen runner retains its own fresh per-stage storage
checks: 2,500,000,000 bytes for persona, the same for activation, and
6,000,000,000 bytes for apps. Each VM retains its own fresh memory check and
running resource supervision.

The three jobs write fresh attempt-owned overlays. The apps helper also owns
its scratch disk. The Python framebuffer memfd adapter is unnecessary for
these Linux helpers and is not invoked. The unchanged helper QEMU launch still
uses its native-required contract and its existing memory backend.

## Existing proof validators remain authoritative

The exact counter1 app-auditor host supplies `saved_inspection()`. The wrapper
calls that existing read-only validator with the inspector's eight-checkpoint
inventory before preparation, and with the app auditor's eleven-checkpoint
inventory after preparation. The validator reconstructs the original
firstboot/partition prefixes in both cases. It revalidates guard acceptance,
the actual saved-disk chain, journals, complete fsck diagnostics, native
supervision, output files and source provenance.

The wrapper does not rerun either whole inspector or app-audit preflight into
an occupied or premature output directory. It adds no guest filesystem logic.
The original firstboot disk remains identified by its own checkpoint; persona
is allowed to produce a new overlay under the same logical `root26g.qcow2`
name. The mutable preparation `result.json` is expected to change.

Final acceptance requires all three helper checkpoint/result pairs, exact
stage-owned output inventories, original predecessor identities in each
`stage-inputs.json`, natural native completion, clean reap and the unchanged
helper launch contract. The existing app auditor's `full_inputs()` then checks
the full backing ancestry:

`apps -> activation -> persona -> accepted firstboot -> audited partition`

It fully verifies those five distinct members plus the original OS image.
The wrapper holds the existing nonwriting preparation lock during this final
verification and rechecks the exact checkpoint boundary under that lock.
All earlier bound metadata and old attempt names remain unchanged.

The wrapper owns only its direct frozen-runner child. Its exclusive command
receipt reserves each phase. Cleanup signals only that unreaped direct child;
the frozen runner retains its own QMP, descendant, subreaping and parent-death
handling. A timeout, forced cleanup, changed input or incomplete proof cannot
be accepted. Failed paths and receipts remain preserved for inspection.

## Fourteen observed success bindings still required

`INSPECTION_SUCCESS_PINS` must contain exactly `{path: {bytes, sha256}}` for:

- The finalized saved-inspection owner source.
- Its execution `command.json`, `owner.json` and `exit.json`.
- The saved work's `inspection-session.json` and `result.json`.
- Its `a1/inspection-result.json`, `expected-policy.json`, `launch.json`,
  `vm-result.json` and `vm.child.json`.
- Its three `a1/files/inspection/` outputs: `result.json`, `fsck-system.txt`
  and `fsck-data.txt`.

The corresponding read-only collector is prepared separately in
[`resume1-saved-inspection`](../resume1-saved-inspection/README.md). A file hash
alone is insufficient: the new wrapper also requires the bound accepted outer
receipt, matching command/result/identity fields, clean reap, no current matching
inspection/preparation child, and the existing saved-proof validator's pass.

| Role | Phone path |
| --- | --- |
| Saved-inspection owner source | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-saved-inspection-resume1.py` |
| Saved-inspection owner receipts | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume1-owner` |
| Accepted saved-inspection work | `/data/local/tmp/pixel-saved-audit-e9cc754-resume1` |
| New helper owner receipts | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-apps-prep-resume1-owner` |
| Fresh app-auditor sources | `/data/local/tmp/pixel-app-checks-counter1-resume1` |
| Later app-audit work, required absent here | `/data/local/tmp/pixel-app-audit-e9cc754-resume1` |

The currently reviewed finalized saved-inspection owner source is 25,168 bytes,
SHA-256 `87526ee42417108f46a8ca03b3fece1cd154f2c439a9c6492f20c97fd6981bb9`.
The fourteen observed successful files are not yet filled into this draft.
Any necessary source change requires a new reviewed identity; no old receipt
or executed file is overwritten to satisfy a pin.

After those identities are actually bound, a new reviewed owner installation
can run its preflight phase. Execution additionally requires the observed raw
preflight stdout byte count/hash, the matching clean preflight receipts,
unchanged prerequisites and fresh resources. It is a one-shot execution.

## Install-only app-auditor transport

The old app-auditor installation has incompatible firstboot prerequisite
pins. The new bundle contains exactly these two reviewed sources:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `audit_ios26_apps.py` | 34,103 | `6096521f41a8f2caf1c166495d09df28923135dde02295872b98c97a96378291` |
| `audit_ios26_apps_guest.py` | 24,987 | `aee8d203cc10fdc2a75d93bed9293d66588190e103cddb50720924c46a43c8c5` |

The host exactly matches the retained reviewed
[`downstream-counter/revision`](../downstream-counter/revision/README.md)
export. The guest remains unchanged. Exact copies are retained in
[`package/app-auditor`](package/app-auditor/).

[`build_source_staging.py`](build_source_staging.py) reproducibly creates the
install-only package locally. The [transport manifest](package/app-auditor-transfer-manifest.json)
is 2,896 bytes, SHA-256
`6f8fa424f05e409e0e349885b0390684744ddd45fbf0b08f9347a8cff8f00eba`.

There are **nine commands**, each at most **5,186 bytes**: a fresh transfer
reservation, seven exact chunks, and assembly/installation. They are listed in
[transport order](package/app-auditor-transport-steps.json). Each command has
its exact decoded Python source beside it. The manifest binds every chunk,
the complete encoded payload, the bounded decompressed bundle and both sources.

Installation checks all eight earlier source dependencies before/after writes,
requires fresh source and receipt paths, uses exclusive file creation, checks
installed readback, and writes root-owned source files and an install-only
receipt. It imports no preparation owner and starts no process, VM, guest,
filesystem check or app audit. A partial installation is preserved rather than
overwritten. No physical installation is claimed by the source package.

## Focused offline verification

The package has **25 passing focused tests**: 22 owner tests and three transport
tests. The tests cover the unreleased refusal, fourteen-file schema, changed
bindings, rejected/reused/live predecessor evidence, exact initial/final
prefixes, native helper input/launch/completion checks and final-lock behavior.
The lifecycle tests run a tiny Python runner under a real separate wrapper
process, exercising clean reaping, failed output, wrong preflight pins, resource
refusal, one-shot execution, nonzero exit and timeout cleanup.

The proof-delegation fixtures substitute synthetic metadata and validator
results. They prove that the wrapper calls the existing validator at the correct
boundaries; they are not new physical filesystem or native-execution evidence.
Transport tests decode all nine commands and reconstruct exactly the two-file
bundle without executing phone commands. Existing broader validator suites
were not repeated for this wrapper-only change.

The final validation record and exact unfiltered test output are retained in
[`offline-validation.json`](offline-validation.json) and
[`offline-tests.log`](offline-tests.log).

Preparation success still grants no app-copy, application-launch, GUI or GPU
completion. The next independent physical gate remains `APP_COPY_AUDIT_PASSED`
before the GPU helper may run.
