# Prepared saved-firstboot inspection owner

This package prepares the inspection after the genuinely accepted `07-0004`
under the `resume1` firstboot owner. The firstboot was observed accepted at
14:45:21 UTC on 2026-11-22. Its nine input bindings were observed at 14:46:27 UTC,
and independently checked against all 288 decimal digest bytes in the saved
screenshot. `accepted-firstboot-inputs-observation.json` preserves that selected
screen transcription; it is not a raw phone receipt export.

`run_saved_inspection_owner_UNRELEASED.py` remains unchanged and deliberately
refuses every mode while `FIRSTBOOT_SUCCESS_PINS` is `None`. The finalized
`run_saved_inspection_owner.py` changes only that assignment. Its other Python
AST nodes match the independently reviewed draft. Source finalization alone
does not establish that this inspection was installed, launched or passed.

The installed counter1 inspector remains unchanged:

| Source | SHA-256 |
| --- | --- |
| `inspect_ios26_firstboot.py` | `2b127ecda390b199287358cdad7e6e7774f5b787148aea524e7b0247a2640cf3` |
| `inspect_ios26_firstboot_guest.py` | `ada26de8ababb11bb4af20e558708545eb64fd516481359fd5d0ccf6a7cbae2b` |
| Required firstboot guard | `ea40638312d6ac41607806ecb03c148fbd0677df6ab01480e13fd40536869674` |

The Linux helper does not need the Python memfd adapter. Its launch requires
2,816 MiB available RAM for the unchanged 2,048 MiB helper; running memory floor
is 512 MiB and free-storage floor is 1,536 MiB. The helper's own native execution,
ownership, journal, filesystem and complete disk/backing-hash checks remain in
the existing inspector.

## Bind the successful firstboot before staging

After the firstboot outer owner has accepted and exited cleanly, use the
read-only `observe_success_inputs.py` (or its bounded command) to observe these
nine exact files. The observation includes both ordinary SHA-256 text and all
32 decimal bytes. It does not print guest logs or write receipts.

- The new firstboot outer owner and memfd adapter source files.
- The new outer owner's `owner.json`, `command.json` and `exit.json`.
- The new guard's `guard-session.json`, `guard-observations.json` and `result.json`.
- The accepted preparation `checkpoints/ios26-firstboot.json`.

Cross-check source hashes against the reviewed firstboot release, preserve the
observation, and set `FIRSTBOOT_SUCCESS_PINS` to exactly those nine
`{path: {bytes, sha256}}` entries. Do not include the display-only `digest_bytes`
field in the owner mapping. Review the finalized source and create a separately
hash-bound installation/launch transport. The finalized source package contains
six bounded source-transfer commands, a separate read-only preflight launcher,
and a compact preflight receipt observer. `firstboot-binding-finalization.json`
records their exact hashes and the state at finalization. Independent review is
required before phone staging; actual successful preflight bindings are still
required before constructing the execution launcher.

The paths used by the draft are:

| Role | Phone path |
| --- | --- |
| Accepted firstboot guard | `/data/local/tmp/pixel-firstboot-guard-e9cc754-resume1` |
| Inspector sources | `/data/local/tmp/pixel-saved-checks-counter1` |
| Fresh inspection output | `/data/local/tmp/pixel-saved-audit-e9cc754-resume1` |
| Fresh two-phase owner receipts | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume1-owner` |

## Two phases

The finalized owner's `--preflight` mode captures the immutable inspector's
default read-only preflight. It checks the actual accepted firstboot and exact
eight-checkpoint boundary, requires all earlier owned children absent, and
creates only fresh owner receipts. The inspection output must remain absent.
The inspector itself validates the complete saved/predecessor disk chain,
earlier partition audit, source provenance and ordered guarded QMP witnesses.

After that phase has exited and been reviewed, execution needs both
`--preflight-sha256` and `--preflight-bytes` matching the actually observed raw
preflight stdout. The same owner source and bound successful firstboot inputs
must remain unchanged. It launches the identical command plus `--execute`.
The fresh output is never reused after either a success or an incomplete run.

The wrapper's receipt, direct-child handling and signal cleanup follow the
committed partition-audit owner. Preflight has a 1,800-second outer deadline;
inspection has a 7,800-second outer deadline around the existing 7,200-second
helper deadline. Cleanup signals only the wrapper's own unreaped direct child;
the inspector retains its own QEMU ownership and cleanup behavior. A forced
child cleanup cannot be accepted as success.

The inspector is solely responsible for VM and disk logic. The outer wrapper
also verifies the accepted output inventory, returned file hashes, native
completion, clean reap, unchanged successful-firstboot inputs, and absence of
the saved-inspection VM. Neither phase advances preparation or declares the
GPU path or final app complete.

## Offline checks

`python -B -m unittest -v test_owner` passes 14 synthetic tests. They check
unfinalized refusal, missing/changed source pins, nonaccepted firstboot,
wrong attempt, live predecessor, default read-only preflight, clean child reap,
failed preflight retention, observed preflight pins, one-shot execution and
post-inspection output/cleanup/input validation. Tiny local Python children and
synthetic metadata are used; no phone, QEMU, guest, GPU or disk image is run.

`independent-draft-review.json` records the static review of the preserved draft.
Final source/transport review and actual physical preflight are separate gates.
This source package provides no physical saved-firstboot inspection success
evidence by itself.

## Physical installation and preflight launch

The six source-transfer steps succeeded on the Pixel. The on-screen installation
receipt confirmed the exact 25,168-byte owner and 5,926-byte preflight launcher.
The preflight launcher then reported `PREFLIGHT_OWNER_LAUNCHED` at
2026-11-22T14:51:17.055082Z with wrapper PID 9859, start ticks 8410203. This is a
launch observation, not saved-disk inspection success. The parent's physical screenshots are
`physical-observations/sources-installed.jpg` and
`physical-observations/preflight-launched.jpg`.

The read-only preflight was then observed accepted at
2026-11-22T14:53:17.147449Z: child and owner exit codes zero, child cleanly reaped,
wrapper and child absent, inputs unchanged, and inspection output still absent.
Its raw captured stdout was 9,070 bytes with SHA-256
`84b31f4f08744f6adeb20ab5af308b1d10c839803c051d4bba577201a4ad3760`.
The selected transcription and screenshot are
`physical-observations/preflight-passed-145317.json` and `.jpg`; all 32 decimal
digest bytes were independently checked. `accepted-preflight-inputs-observation.json`
preserves the input used to finalize the execution launcher and read-only
inspection observer.

`launch-execution.command.txt` carries the reviewed launcher as a bounded,
hash-checked inline command. It launches the existing installed owner with the
actual preflight hash and length, after fresh prerequisite, receipt, absence and
resource checks. It does not require another source installation.
`observe-inspection.command.txt` reports selected execution metadata;
`observe-success-pins.command.txt` will emit the fourteen next-stage bindings
only after accepted results, clean reaping, absent recorded processes and
unchanged prior inputs are verified. `independent-execution-release-review.json`
records the passed exact-byte review of the launcher, both observer modes, and
all three bounded commands. That release does not establish physical inspection
success; subsequent execution observations must supply that evidence.

## Physical inspection execution

At 2026-11-22T14:54:58.850272Z the Pixel's execution launcher reported
`SAVED_INSPECTION_EXECUTION_OWNER_LAUNCHED`, with accepted preflight and inspection
execution requested. The detached owner was PID 12027, start ticks 8432383,
with its process group and session both 12027. The launcher was PID 12005,
start ticks 8432359. The installed owner source remained unchanged. The earlier
preflight owner and inspector were absent after their recorded clean finish at
14:52:41.607902Z.

At 2026-11-22T14:58:55.245032Z the final observation showed `INCOMPLETE`, with
inspector and outer owner exit codes 2, `accepted: false`, a cleanly reaped
inspector, and no forced outer-runner cleanup. The owner reported
`ValueError: inspector exited 2`. Wrapper PID 12027/start 8432383, inspector PID
12044/start 8432415, and QEMU PID 13326/start 8442942 were absent. The QEMU start
ticks were corrected from an earlier selected transcription after a direct read
of `a1/vm.child.json`; see the erratum below.

The VM receipt showed natural QEMU exit code 0 and native initialization,
execution and final-service witnesses, but recorded forced cleanup of descendant
PID 13344. That PID's role and start ticks were not captured in the selected
observation. The unchanged native cleanup gate rejects a nonempty
`forced_descendants` list. The final inspector reported the full backing chain
and preparation/guard inputs unchanged, with no identity error, before returning
`RuntimeError: VM stage incomplete`.

The failed work and owner directories are preserved. This attempt did not reach
`SAVED_FIRSTBOOT_INSPECTION_PASSED`; persona, activation, apps, GPU, wallpaper,
locale, packaging and final cold boot remain blocked. No retry or relaxed gate
is released. A separate read-only failure observer inventories the exact raw
metadata receipts and log filenames, sizes and hashes without exporting log
contents or extracting the guest output archive.

`independent-failure-collector-review.json` records the passed review of
`observe_failure.py` and its five bounded commands. Use
`observe-failure-summary.command.txt` for selected failure fields and inventory,
then `observe-failure-pins-0.command.txt` through
`observe-failure-pins-3.command.txt` for nineteen exact source and receipt pins.
Each pin includes all 32 decimal digest bytes. Readiness refers only to failure
evidence collection, never to a passed inspection. The collector does not
recompute disk hashes; it preserves the completed immutable inspector's
unchanged-chain and unchanged-input report and rechecks the bound metadata.

### VM identity transcription correction

The first failure collector safely refused `recorded VM identity differs` before
emitting evidence. A direct read of the preserved raw `a1/vm.child.json` showed
`{"pid":13326,"start_ticks":8442942}`. The earlier selected transcription had
incorrectly recorded 8442923. No phone receipt, source or runtime state was
changed. `vm-identity-transcription-erratum.json` records this correction and
references `physical-observations/vm-identity-correction.jpg`.

The original collector, its commands and review remain preserved.
`observe_failure_pin1.py` changes only `EXPECTED_VM.start_ticks` to the raw
receipt's value; its other AST nodes are identical. Its distinct commands are
`observe-failure-summary-pin1.command.txt` and
`observe-failure-pins-0-pin1.command.txt` through
`observe-failure-pins-3-pin1.command.txt`.
`independent-failure-pin1-review.json` records the passed raw-image, exact-delta
and five-command review. This correction neither changes the failed inspection
result nor releases an inspection retry.

## Completed failure evidence collection

The corrected read-only observer returned failure evidence readiness at
2026-11-22T15:10:07.388267Z. Four subsequent pin pages, ending at
15:11:42.723814Z, captured nineteen exact source and metadata-receipt bindings.
`physical-observations/failure-bindings-selected.json` contains all 608 decimal
digest bytes, the SHA-256 values independently derived from those bytes, and
the separately transcribed displayed hexadecimal values. Every value matches.
`independent-completion-review.json` records the independent comparison against
the original screenshots and pins the final selected JSON files.

`physical-observations/failure-summary-selected.json` records the final selected
metadata, process identities and log filename/size inventory. The helper
reported `done_codes: [0]` and `out_sizes: [10240]`; its VM receipt spans
14:56:44.148520 to 14:57:13.923618 UTC, or 29.775098 seconds. The stored
`elapsed_seconds: 20.03636254199955` is the last periodic sample retained by the
frozen runner, not its final record span. The inspector ran from
14:56:44.138307 to 14:57:33.556702 UTC and the outer owner finished at
14:57:33.620032 UTC. These timestamp differences describe receipt intervals,
not independently measured process lifetimes.

The run remains incomplete because clean descendant cleanup failed. The
selected records establish natural leader exit and native execution, preserved
firstboot inputs and disks, and absence of the recorded wrapper, inspector and
QEMU identities. They do not establish an accepted saved inspection. No guest
log contents were exported, no guest output archive was extracted, and no
inspection retry was released. The selected JSON files explicitly identify
their screenshot-transcription provenance and are not raw phone receipt exports.
