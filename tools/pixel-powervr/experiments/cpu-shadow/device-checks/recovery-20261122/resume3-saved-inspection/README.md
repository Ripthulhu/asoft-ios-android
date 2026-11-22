# Preserved resume3 saved-firstboot inspection package

## Actual outcome: prerequisite refusal before inspector launch

All sixteen source staging steps completed, and the installed inspector pair,
owner and preflight launcher matched their exact reviewed hashes. The separate
observer's seven source-only staging steps also completed. The preflight owner
launched at **2026-11-22 17:01:52.504058 UTC** as **6603 / 9193748**.

At **17:06:29.127032 UTC**, a bounded read-only query found `OWNER_REFUSED`:
the pinned resume2 observer `exit.json` digest did not match. The wrapper was
absent, the new owner directory did not exist and all preflight receipt paths
were absent. The reviewed owner performs this check before starting the
inspector. Consequently, no new inspector child, VM or filesystem check ran.
The first two `PENDING` projections tested only for a missing final receipt;
they did not prove a live preflight.

The original 16:04:28 screenshot and a fresh **17:07:17.404781 UTC** read identify
one historical hash transcription error. The actual **478-byte** observer exit
receipt is `4af8f8a2feeb3e8103bfaf61c8393aa58f94c9ea01e32f06e51bbaee3cdbb920`;
the earlier selected record and this installed owner used `6` instead of `0`
at zero-based hex offset 40. The fresh query displayed every decimal digest
byte, and the other three observer receipts match their historical bindings.

See the [selected refusal](physical-observations/preflight-refused-170629.json),
[fresh receipt identities](physical-observations/prior-observer-pins-170717.json)
and [installation evidence review](independent-installation-evidence-review.json).
This entire package and every installed source remain preserved. A separate
resume4 owner/preflight/observer package will correct the binding and use fresh
paths while reusing the already installed inspector pair. This package must
not be relaunched or retroactively labelled accepted.

## Original package scope

This package continues the actual accepted native firstboot attempt `07-0004` with a fresh inspector source directory, owner, output directory and process observer. All prior inspection work, source bytes and diagnostic evidence remain preserved.

The previous resume2 native VM exited cleanly with no forced descendants. Its guest inspection rejected iOSRoot's alternate volume header before journal classification or fsck. The subsequent bounded read-only diagnostic proved that all eight headers are journaled, and the same legacy boot-inconsistent bit 11 is present in the saved and baseline iOSRoot alternate headers. Their corresponding 512-byte header hashes match. That observation did not establish filesystem health or an inspection pass.

The separately reviewed [canonical inspector revision](../resume3-inspector-revision/) classifies only the strict preexisting iOSRoot alternate-header case. Primary clean/journal/inconsistency rules, exact saved/baseline header and JIB relationships, independently valid matching empty journal metadata, read-only attachments, fsck verdicts, native execution and unchanged backing-chain requirements remain enforced. No prior failure is relabelled as a pass.

## Frozen source bindings

| Component | Bytes | SHA-256 |
| --- | ---: | --- |
| Inspector host | 32,576 | `245393bf59b9e731fa9f511b9368e5676f86a8ad0d6b8e03859e73239bf8559c` |
| Inspector guest | 18,979 | `f52e4d4ec78c08bf73ec37efac8aa6ecb99a5ab2baf174481fda8b286fb49d97` |
| Outer owner | 48,469 | `91ac3ba2ba8c3e40b2a99dfffdc4a53ae49b8e441245755f33ef761846d61e14` |
| Detached preflight launcher | 5,926 | `85e0f7bdb7b5fb1bb95e2e93f784dafe050c5063784d0c22f2445dc6b71277d8` |

The owner binds the revised pair through `INSPECTOR_SOURCE_PINS`. Its preserved draft has that value unset. Finalization changes only that assignment. Native runtime, owner child cleanup, resource and outer result-acceptance functions are unchanged from the prior owner.

The owner preserves the nine accepted firstboot bindings and all nineteen resume1 failure bindings. Sixteen additional exact pins preserve the five actual resume2 failure receipts, its installed owner, the completed header source/result, all three capability outcomes, and the finished independent observer's source/ready/exit/summary/events. It also checks and carries the eight retained header-file digests and the old attempt's linked metadata. The old header diagnostic's exact verified source bytes provide its existing read-only metadata validator; its main and native-command functions are never run during this validation.

## Fresh phone paths

| Purpose | Path |
| --- | --- |
| Revised inspector pair | `/data/local/tmp/pixel-saved-checks-resume3` |
| New inspection output | `/data/local/tmp/pixel-saved-audit-e9cc754-resume3` |
| New owner source | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/run-ios26-saved-inspection-resume3.py` |
| New owner receipts | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/ios26-saved-inspection-resume3-owner` |
| Preflight launcher | `/data/local/tmp/pixel-gpu-transfer-sxtv33sh/launch-ios26-saved-inspection-resume3-preflight.py` |

The existing counter1 inspector and both old inspection outputs are untouched. Existing old ownership locks are opened read-only for nonblocking exclusion checks. Recorded old owners, inspectors, QEMU instances, capability/header owners and process observer must be absent.

## Released source staging and read-only preflight

The [independent staging review](independent-source-staging-review.json) checked the complete source bundles, all sixteen compressed commands and the bounded preflight loader.

`staging-order.json` gives the exact order: eight `inspector-source-transfer/` commands create the fresh inspector directory and install its two source files; eight `source-transfer/` commands install only the owner and preflight launcher. Every command is at most 5,240 bytes. Each step preserves existing targets; bundle assembly verifies all bytes before exclusive installation. Installation receipts explicitly state that execution has not started.

`launch-preflight.command.txt` then starts only the detached read-only preflight owner. `observe-preflight.command.txt` checks accepted exit/clean reaping, source and prerequisite preservation, absent output/execution artifacts, and reports the actual new preflight stdout length, hash and all 32 digest bytes.

The actual prerequisite refusal and subsequent historical receipt reread are
recorded above. This package produced no accepted preflight and cannot bind
execution.

## Execution remains separately bound

`launch_saved_inspection_execution_UNRELEASED.py` retains the reviewed independent-process-observer readiness contract. The fresh preflight hash/length and observer source pin remain unset in this draft. A separate [resume3 process observer](../resume3-process-observer/procstat1/) uses fresh paths and the same bounded procstat algorithm; it must report an actually observed READY receipt, matching live process identity/argv, independent session, scope and fresh heartbeat before the execution owner is launched.

The execution launcher will retain the existing 2,816 MiB available-memory and 1,536 MiB storage floors through the owner's resource check. The inspector uses the same native helper, bounded cleanup and read-only/fsck policy. Successful observation or preflight does not establish saved-inspection success.

## Focused validation

The inspector author and independent reviewer each ran the focused 45-test source suite successfully. Three additional package tests exercise the real generated source-only transfers in fresh scratch directories, verify exact installed bytes and refusal to overwrite existing targets, and verify that the unfinalized owner refuses absent inspector bindings. These local transport tests substitute only scratch paths and the effective owner UID for phone paths/root UID; they never run the installed source payloads. `focused-verification.json` records their scope and result.
