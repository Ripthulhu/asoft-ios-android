# Partial host check: stopped at the first rustfmt failure

The actual full-check invocation on 2026-11-22 **did not pass**. Its owner
observed the first formatting failure and terminated only its owned process
tree. The retained result is `INCOMPLETE`, with Cargo terminated by SIGTERM
(`cargo_exit_code: -15`). There is no later clippy, nextest or doctest result
from this attempt.

```sh
cargo +1.98.1 run --offline --locked --package xtask -- check
```

The command ran in the candidate worktree named by `launch.json`, at reims
`e9cc7541e4edee4896d9564b3056bb2799595d3f`, using the existing approved local
dependency-path override and clean metal2vulkan
`51c322d883ea723d290c931b3b2013c50f5e4934`. The recorded interval was
06:59:34.827790 through 06:59:37.620676 UTC.

## Observations and limits

- `testkit: ok` and `header: ok` appear in the complete retained raw log.
- `cargo fmt --all --check` reports a diff in
  `crates/reims-vgpu-c/tests/cpu_shadow_core.rs:52`: rustfmt wraps the existing
  iterator chain differently. The log contains the exact proposed change.
- `xtask check` accumulates failed phases with `ok &= ...`. The owner watches
  its original log because `xtask` would otherwise continue. This attempt's
  log contains no subsequent phase command or result.
- The owner records `first_concrete_log_failure`, no forced SIGKILL,
  complete owned cleanup with no remaining processes or cleanup errors,
  unchanged source identities, and unchanged prerequisite receipts.
- Both sampled memory observations were above the resource floor; the minimum
  recorded MemAvailable was 4,596,113,408 bytes. Sampling does not establish
  a continuous or hard real-time memory guarantee.

These facts establish an early formatting-gate failure and clean owner
termination. They grant no complete host-check pass, later-suite pass,
physical GPU, guest-boot, UI or product qualification. A formatting-only
revision and a new full-check attempt are separate work.

## Exact evidence preservation

The 16 copied artifacts total 47,884 bytes and are byte-identical to the
recorded originals. `artifact-inventory.json` gives every original path,
size and SHA-256, including the copied owner, preparation receipt, launch,
raw log, process ownership/result, resource observations and before/after
patches. No build, test or header check was rerun while preserving them.

The four full source inventories total 3,715,342 bytes. They remain at the
absolute original paths listed in `artifact-inventory.json`; this small
evidence directory references their exact sizes and hashes. The committed
`result.json` also preserves their identical before/after identities, source
commit IDs, file counts and exact diff hashes. The source changes themselves
are retained as the original patches.

| Key retained artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `check.log` | 851 | `9736d9f0d704a67893fb12fcb0125fd85c8aebff3d02249ebc9a913085a1011a` |
| `owner.py` | 28,956 | `14c8a2b80ba686e171af970e803279e181f060d3f2edd0caf204a537c9ffa25c` |
| `preparation.json` | 5,721 | `ca0156099d6be87f496ac67df947a01f1a60fea3e473bca9274d9ae43cfff29f` |

`preparation.json` is preserved without alteration. It was written before
the result was known and therefore correctly labels the outcome as pending
at that earlier time. The actual later outcome is in `result.json`.

The owner received independent source-only review from `boot_readiness` and
`harness_review`. That review and AST syntax parsing are recorded in the
preparation receipt; neither is described as an execution test of the owner.
All copied contents are authored code, host logs and provenance metadata.
They contain no Apple images, plist bodies, certificates or guest payloads.

## Subsequent source correction

The exact formatter patch and original formatting receipt are retained as
`formatting.patch` and `formatting-receipt.json`; `formatting-followup.json`
binds their bytes and the integrated revision. Author commit
`a42a1e68dbf255103b9589162014ff2fbee0784a` and integrated commit
`bda933b9592262dd85d8723e5c47cfe6886b6c25` have the same tree,
`c603324e4e499668f5ae4133cfe14b39f4491275`, and both directly descend from
the failed attempt's e9 revision. The only source change is the recorded
test-expression line wrapping and optional trailing call-argument comma.
The current header and approved Cargo override retain their earlier hashes.

This follow-up preserves the first attempt unchanged and records no passing
rerun. A new owner binds the exact correction and uses a fresh output
directory. Its full check will repeat the header gate itself; no additional
standalone header check was run while preparing the correction or evidence.

`next-owner-preparation.json` preserves the narrow independent review of that
new owner, SHA-256
`905b2d7409d0978c8b75b094420ff8594d2d95c2fbc33d92edf890370b55ebb7`.
Its command, environment and supervision are unchanged; its added checks
bind the exact formatting correction and its output directory is new.
The receipt records the root agent's separate 07:05:09 UTC launch report
with the outcome still pending. It grants no result for that later check.
