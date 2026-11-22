# Resume5 saved-inspection preparation

The revised inspector pair, preservation owner, source-only staging commands and separate preflight launcher have passed independent review. This preparation checkpoint is ready for physical staging and a fresh preflight. It records no resume5 installation, preflight, observer readiness or inspection result. Earlier preparation records with pending-review labels are preserved; `preparation-status.json` links their completed reviews.

The prior resume4 saved inspection remains rejected at `root_baseline_jib_changed`. Its native helper exited cleanly, and the subsequent read-only JIB diagnostic observed an exact flag difference (saved 1, baseline 5; one differing byte at the half-open range `[3,4)`). That diagnostic did not read the journal or establish saved-inspection success. The new inspector independently verifies the narrowly authored NeedInit-to-initialized-empty case, including the full authored baseline journal and current empty journal, before either read-only filesystem check can qualify the saved state.

## Review and source bindings

The revised host and guest sources are preserved in `../resume5-inspector-revision/sources/`. Their source review and 60 focused tests are recorded in [the independent inspector review](../resume5-inspector-revision/independent-inspector-review.json). The owner and its preservation helper passed [independent source review](independent-owner-source-review.json) and 12 focused preservation/refusal tests. All 17 installation commands, both complete bundles, the preflight launcher command and the read-only preflight query passed [independent transport review](independent-source-staging-review.json).

| Source | Bytes | SHA-256 |
| --- | ---: | --- |
| `inspect_ios26_firstboot.py` | 37,444 | `30eaaffc42aa73bf95488f3ca504d7c56344fbada0aaed746904ed1f4f78fd3e` |
| `inspect_ios26_firstboot_guest.py` | 20,929 | `96c559bac19a3c36a4e26c2cf57b75cbafdfd5879de6e4fceb582b2c07a9b51a` |
| `run_saved_inspection_owner.py` | 60,564 | `dbb570dc9b3354a5d7c4eb218883ab22f25afe24757c429e46cc7c04de1baa63` |
| `launch_saved_inspection_preflight.py` | 6,233 | `8908256ab34f49dba1e1fa17b56fd8563dad73af594b0028b62b27b74446e034` |
| `observe_preflight.py` | 8,539 | `a9253f9378945d1f34dab9f613abecd8483e387079ca320577271bd7d90c5a65` |

The owner binds the nine actual resume4 receipt hashes, completed sibling observer, actual 14,246-byte JIB diagnostic result and exact diagnostic source. Its added read-only preservation helper validates the retained sector commands, clean exits, output hashes and both reconstructed JIB blocks under the old inspection lock. It starts no native tool or VM and follows no journal pointer. Preserved evidence hashes enter the same unchanged final input checks as earlier evidence. Previous firstboot, failure, native ownership, cleanup, resource and acceptance gates remain in force.

## Fresh phone scope

`BASE` below is `/data/local/tmp/pixel-gpu-transfer-sxtv33sh`.

| Item | Fresh phone path |
| --- | --- |
| Inspector pair | `/data/local/tmp/pixel-saved-checks-resume5/` |
| Owner source | `BASE/run-ios26-saved-inspection-resume5.py` |
| Preflight launcher source | `BASE/launch-ios26-saved-inspection-resume5-preflight.py` |
| Owner receipts | `BASE/ios26-saved-inspection-resume5-owner/` |
| Inspection work | `/data/local/tmp/pixel-saved-audit-e9cc754-resume5/` |
| Preflight launch receipt | `BASE/ios26-saved-inspection-resume5-preflight-launch.json` |
| Preflight launcher log | `BASE/ios26-saved-inspection-resume5-preflight-wrapper.log` |
| Fresh sibling observer | `BASE/ios26-saved-inspection-resume5-observer-procstat1/` |

The accepted firstboot guard remains `/data/local/tmp/pixel-firstboot-guard-e9cc754-resume1`. Earlier inspector sources, work directories, output receipts and observer readiness files are preserved.

## Physical sequence

1. Follow `staging-order.json`: eight commands in `inspector-source-transfer/`, then nine in `source-transfer/`. These exclusively install the exact sources and report their hashes. They do not launch the inspector. The maximum command is 5,236 bytes.
2. Observe and verify the installed source bytes and receipts. Run the separate `launch-preflight.command.txt`, then `observe-preflight.command.txt` to collect the actual fresh result. Acceptance requires exact inputs, clean reap, no execution work and all ordinary preflight checks.
3. Install the separately reviewed fresh sibling-observer packet in `../resume5-process-observer/procstat1/`. This can occur while preflight is pending; source staging does not start its finite readiness window.
4. Only after actual accepted resume5 preflight evidence is independently verified, create additive runtime bindings for the execution launcher and observer. Preserve the unbound templates. Stage the execution launcher before starting the observer so staging does not consume its owner-wait deadline.
5. Start the fresh observer through its separately bound launcher, collect its actual live READY receipt and verify source, PID/start ticks, scope, heartbeat and deadline. Bind that fresh readiness to the separate inspection execution command. Inspection execution and final result acceptance remain later gates.

The preserved `launch_saved_inspection_execution_UNRELEASED.py` has unbound source, installation, preflight and monitor constants and refuses before action. It is not an execution command. No earlier public preflight digest or READY receipt is treated as a new observation, even if a later public preflight digest repeats.

## Prepared evidence and remaining uncertainty

`source-binding.json` records the source-only assignment finalization. `owner-draft-preparation.json` and the `*_UNRELEASED.py` files retain the original unbound drafts. `preparation-status.json` binds all completed reviews, command manifests and the still-missing physical inputs. The frozen source and command reviews remain applicable when browser access is available; the next required evidence is actual installation followed by the fresh physical preflight and observer readiness.

The new route has not yet been exercised on the saved phone disks. It may still refuse on journal contents, filesystem checks, postcheck equality, resources or any preserved-input/ownership condition. A clean native helper or a diagnostic observer exit does not establish saved-inspection acceptance. Downstream preparation remains blocked until an actual accepted inspection result exists.
