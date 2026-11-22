# Prepared saved-firstboot inspection owner

This package is preparation for the inspection after a genuinely accepted
`07-0004` under the `resume1` firstboot owner. It has not been installed or run
on the phone. The owner draft deliberately refuses every mode while
`FIRSTBOOT_SUCCESS_PINS` is `None`.

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
hash-bound installation/launch transport. No such transport is released here.

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

The draft still needs independent review and actual success/preflight bindings
before use. It provides no physical saved-firstboot inspection evidence.
