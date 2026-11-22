# Prepared root JIB diagnostic

## Current state

This directory contains a new diagnostic and its local validation, source-only staging, and separate launch package. **It has not been installed or run on the phone. Browser access is unavailable in this chat context. There is no actual JIB result or result digest to bind.** The detailed projection template retains `SOURCE_PIN = None` and `RESULT_PIN = None`; no detailed projection command is released at this checkpoint.

The unchanged diagnostic source has passed [independent source review](independent-diagnostic-source-review.json). The source-only transfer, separate launch, future receipt collector, and unbound projection/finalizer have passed [independent transport and projection review](independent-transport-projection-review.json). These code reviews are complete. Reconnecting the browser does not by itself require another source review or new user permission; the remaining steps are to observe and verify the actual installation, execute the separately guarded diagnostic, and bind its actual result.

The completed resume4 saved inspection stopped at `root_baseline_jib_changed`, before journal-header/empty-journal validation or either filesystem check. That predicate compares the complete current and baseline 4,096-byte root Journal Information Blocks. The existing eight-header diagnostic contains only volume headers, so its retained payloads cannot identify the JIB difference. This package preserves those files and the failed inspection.

## Diagnostic scope

The diagnostic binds the actual resume4 failure receipts, the frozen owner/runtime and image-tool sources, the prior passed capability probe, retained root headers, image identities, and ownership locks. It derives the root JIB range from the bound header evidence and verifies the expected virtual offset `2048 * 512 + 257 * 4096 = 2101248`.

It reads exactly two 4,096-byte blocks through sixteen instances of the already demonstrated 512-byte extraction primitive. Each invocation uses the frozen tool's observed `count = skip + 1` semantics. The native child timeout, output limits, direct ownership, and clean reap requirements remain in force.

Raw sectors and assembled JIBs remain in the fresh phone output directory. Public output consists of block lengths and hashes, big-endian flags/journal offset/journal size, the total differing-byte count, and up to 128 differing-byte ranges. Ranges are JIB-relative half-open intervals `[start, end)`; omitted ranges and truncation are explicit. No arbitrary byte values, device signatures, UUID values, or file/process inventories are exported.

The diagnostic does not follow the journal pointer, start a guest or filesystem checker, mount, replay, repair, or change the saved-inspection predicate. A difference is not classified as safe. Preservation checks cover the bound metadata, tooling and file identities; this package does not claim a new full-disk hash.

## Exact phone paths

All new files use `/data/local/tmp/pixel-gpu-transfer-sxtv33sh` as their base.

| Purpose | Fresh path below the base |
|---|---|
| Installed diagnostic source | `run-ios26-root-jib-diagnostic-resume4.py` |
| Exclusive source transfer directory | `root-jib-diagnostic-resume4-transfer/` |
| Source installation receipt | `root-jib-diagnostic-resume4-install.json` |
| Diagnostic evidence directory | `ios26-root-jib-diagnostic-resume4/` |
| Completed diagnostic receipt | `ios26-root-jib-diagnostic-resume4/result.json` |
| Phone-only assembled payloads | `ios26-root-jib-diagnostic-resume4/saved-jib.bin` and `baseline-jib.bin` |

The source and output paths match the author's `DIAGNOSTIC_SOURCE` and `OUT` constants. Existing targets, occupied output directories, and previous transfer records are preserved by refusal. A partially completed installation must be inspected; it must not be overwritten or silently restarted.

## Future staging and execution sequence

The exact source and command hashes are recorded in `transport-build.json`, `transfer-manifest.json`, `transport-steps.json`, and the validation records. The final reviews above cover these unchanged prepared commands. `preparation-status.json` and `staging-order.json` bind those reviews and distinguish the completed code review from the physical work that remains.

1. Execute the numbered `source-transfer/*.command.txt` files in their recorded order. These commands create a fresh exclusive transfer, verify every chunk and the complete source bundle, and install one exact source file. They do not import or execute the diagnostic. Installation prints its exact byte length and SHA-256 and writes an installation receipt with `execution_started: false`.
2. Observe and verify the actual installation evidence, then use the already reviewed separate `run-jib-diagnostic.command.txt`. Its loader verifies the exact manifest, installation receipt, source length and hash, and absence of the fresh diagnostic output, then runs the diagnostic in the foreground. The diagnostic performs the actual metadata/resource/ownership checks again before extracting anything.
3. Preserve the actual result and its screenshot evidence. The prepared `observe-jib-result-pin.command.txt` is a future read-only receipt collector. It requires a completed diagnostic, all sixteen native commands cleanly reaped, all preservation and scope flags explicit, and the diagnostic owner identity absent. It emits the result byte length, SHA-256, all 32 digest bytes, and fixed status fields. It does not release the detailed projection.
4. Independently review a selected observation with kind `selected_physical_root_jib_diagnostic_observation`, the collector's `ROOT_JIB_RESULT_BINDING_READY` status and fields, `independently_reviewed: true`, and a relative `independent_review` file reference. Preserve the actual source and result pins and the 32 decimal digest bytes. Do not manufacture this record before the physical diagnostic completes.
5. Only then run the local `finalize_jib_projection.py ACTUAL_REVIEWED_RESULT_OBSERVATION_JSON`. It validates the actual evidence, source pin and decimal digest, changes only the detailed reader's two pin assignments, and writes a fresh `result-binding/` directory. Independently review those newly generated commands before using them. The original unbound template remains unchanged.

Every generated terminal command is capped at 6,000 bytes. Detailed output has a compact summary and four optional pages of at most 32 difference ranges. The final reader verifies the actual result digest, source, owner absence, fixed read plan, all sixteen retained sectors, the two assembled blocks, and the recomputed scalar comparison. It exports only an explicit scalar/range allowlist.

## Local validation and its limits

The author owns the diagnostic's extraction, parser, boundary and lifecycle tests. Separate transport tests exercise source-only installation, existing-target preservation, corrupted chunks, duplicate commands, symlink inputs, and changed launch inputs in temporary local directories. Those tests remap only the phone base and expected UID to the local test environment; generated phone code still requires root and ordinary root-owned files.

The frozen diagnostic passed 28 focused tests. The separate packet passed 12 transport tests and 16 projection/finalizer tests. Both groups were independently rerun successfully. The validation logs and their hashes are retained in `focused-validation.json` and `transport-projection-validation.json`; `packet-roundtrip-verification.json` records the exact generated command and source reconstruction.

Projection tests use synthetic evidence held in memory. They cover missing actual-result bindings, changed hashes and commands, incomplete results, missing or wrong preservation/scope flags, forced cleanup, live diagnostic ownership, sector/assembled-block disagreement, scalar mismatch, and output allowlists. They do not claim a physical JIB observation. Packet verification independently reconstructs the compressed shell commands, every chunk, the complete bundle, exact source bytes, and the source-bound receipt collector.

Prepared/tested status does not establish phone compatibility, installation, a completed diagnostic, a safe JIB transition, saved-inspection acceptance, or downstream application readiness. The saved-inspection gate remains closed until a separately supported policy and successful actual inspection justify opening it.
