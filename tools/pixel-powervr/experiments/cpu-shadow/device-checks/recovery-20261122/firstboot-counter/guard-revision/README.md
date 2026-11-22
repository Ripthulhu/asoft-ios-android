# Firstboot counter protocol correction — counter1

This source-only export corrects the concrete `07-0002` backend-inventory rejection. It does not accept that attempt or provide a physical firstboot result. The new guard and saved-firstboot inspector must be staged under new source paths, and a new exact-source physical preflight and owned execution must supply all original evidence plus the new `query-block` witness.

## Scope

The guard requires matching unique inventories containing `root` or `root` plus the qualified default empty `floppy0`. It binds the writable inserted root node and attached-device identity across both QMP responses. The optional floppy must have exactly `device` and `stats` in `query-blockstats`, and exactly `device=floppy0`, `type=unknown`, `removable=true`, and `locked=false` in `query-block`. Every returned top-level, parent and backing write/flush failure counter remains type-checked and must be zero. No generic extra-backend allowance is added.

The successful stop sequence is now `stop` → `query-blockstats` → `query-block` → `quit`. The new query retains a bounded five-second call. Failure preserves the event and follows the existing stop cleanup. The inspector pins the new guard, reevaluates the two-response predicate, and validates both raw replies and the exact ordered trace. Native witnesses, guest sync, input/source identity, cleanup, checkpoint, filesystem and application gates are unchanged.

`SOURCE-BASIS.md` contains the exact qualified QEMU source excerpts and the reason the empty backend is removable. `source-basis.json` provides immutable source URLs, byte lengths, hashes, and retained scratch locations. `account_failed=false` does not disable failure-counter increments; the field controls particular timing/last-access statistics. Nested returned node summaries are not independent backend failure accounts.

## Final source pins

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `guard_ios26_firstboot.py` | 25686 | `ea40638312d6ac41607806ecb03c148fbd0677df6ab01480e13fd40536869674` |
| `inspect_ios26_firstboot.py` | 26030 | `2b127ecda390b199287358cdad7e6e7774f5b787148aea524e7b0247a2640cf3` |
| `inspect_ios26_firstboot_guest.py` (unchanged) | 16829 | `ada26de8ababb11bb4af20e558708545eb64fd516481359fd5d0ccf6a7cbae2b` |

Proposed new phone locations are `/data/local/tmp/pixel-boot-checks-counter1/firstboot/guard_ios26_firstboot.py` and the inspector pair under `/data/local/tmp/pixel-saved-checks-counter1`. The frozen preparation runner and old source paths remain separate. Outer ownership, memfd compatibility and preservation receipts are authored and reviewed separately.

## Validation and provenance

The final corrected source passed **57 focused offline tests** in the guard and saved-firstboot inspector suites. See `focused-tests-reviewed.json` and `focused-tests-reviewed.log` for the command, all imported local source hashes, unchanged-source check, exit code and log hash. Tests use authored metadata and mocked I/O. No VM, GPU, phone, mount, package or network execution was performed by these suites.

The copied local preparation support source differs from the frozen phone runner only as recorded in `baseline.json`; the offline receipt is not a physical validation of the phone environment. Existing on-phone `07-0001` and `07-0002` failures must remain intact. The latter has no `query-block` witness and cannot satisfy this new protocol retrospectively.

The earlier uninstalled guard candidate `617ac1b347b4d5139fdee01ad9f8cc60120720b16cc3862b7e1959dfcf5977fc` incorrectly required `removable=false`. Its two test receipts remain in the isolated work directory as historical evidence. Neither is a validation receipt for this export. The final guard corrected that predicate and the dependent inspector pin after independent qualified-source review.

`0001-validate-root-and-qualified-empty-floppy.patch` is a four-file unified diff against the byte-recorded baseline. `manifest.json` records each before/after identity, the unchanged guest, and final validation hashes. No main repository files or phone files were edited by this export task. Downstream app, wallpaper and final cold-boot compatibility is a separate candidate and may not be inferred from this firstboot correction.
