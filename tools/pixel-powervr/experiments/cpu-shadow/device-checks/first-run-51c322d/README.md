# First physical Pixel GPU checkpoint

**Status: `DEVICE_PARTIAL_FAILED`.** This record contains authored diagnostics
on a Pixel 10 Pro XL with the system PowerVR D-Series DXT-48-1536 MC1 driver.
The full fourteen-case suite stopped at its first case. Follow-up diagnostic
runs establish eight passing cases, two failures and four cases not run; they
do not convert the stopped suite into a qualification pass.

[`summary.json`](summary.json) maps every case to its original result and log,
with exact hashes, device properties, source revisions and executable hashes.
The tested sources are reims `3d046429`, metal2vulkan `51c322d` (runtime 1505),
and QEMU `755b88fa`.

| Cases | Result | Observed scope |
|---|---|---|
| fixed, rebind, heap, arguments, dynamic-rebind | PASS | Exact GPU/ordinary-file comparisons; dynamic rebind includes all seven authored subcases. |
| efi, efi-fragmented | PASS | Three exact display frames per case, including CPU refresh and remap; padding preserved. |
| native | PASS | Two exact 64×64 frames, two native entries and SVC returns, two TPIDRRO witnesses, completed GPU epochs and `ECHILD`. |
| probe | FAILED | Runtime status 15: the CPU edit was not witnessed between upload and scatter. No successful probe identity report was emitted. |
| tile | FAILED | Execution-record count was 0 instead of 2. Pixel comparisons were not reached. |
| alias, fragmented, chunk-boundary, lifetime | NOT_RUN | The full runner stopped at probe; follow-up diagnostics omitted these timing-witness cases pending its fix. |

The probe used a submission callback to record its timing witness. Source
inspection found that completion/scatter can overtake this callback. The tile
fixture read execution records without enabling the runtime's opt-in recording.
Both exact checks must remain in place when the witnesses are corrected. These
findings explain failures of the test evidence; they do not establish the
untested GPU results.

All ten executed cases stayed within their process deadlines and reaped their
children without forced descendant cleanup. The successful native fixture used
ordinary memfd RAM and the generic authored-guest TPIDRRO trap mode. It does not
test iOS TPIDRRO swap mode or an Apple guest. The physical run did not explicitly
enable Vulkan validation layers; host validation evidence is recorded separately.

## Exact evidence

The `raw/` directory preserves all 29 exported UTF-8 files byte for byte,
including original temporary paths and newline endings. The original
[`evidence-manifest.json`](raw/evidence-manifest.json) lists 28 files; the
additional file is the manifest itself.
[`raw-sha256.json`](raw-sha256.json) covers all 29. Every original manifest hash,
case-log hash, grouped case record and package hash was rechecked, as was the
15,464-byte compressed export. The raw files contain only authored diagnostics,
synthetic display identities, diagnostic paths and VM addresses; no Apple guest
artifacts or personal content were found.

The two scripts under `raw/` are exact records of the separate diagnostic runs.
Their `all_cases_passed` and `gpu_path_complete` flags remain false even when
their selected cases pass. The installation reports retain their earlier
`VERIFIED_NOT_EXECUTED` status because they record the installation stage; the
subsequent execution results are in the case reports and summary.

The capability trio remains disabled and the app qualification asset remains
absent. No APK was built. A corrected package must pass the complete physical
suite; the final capability-enabled binaries then require their own exact
qualification before an APK build.
