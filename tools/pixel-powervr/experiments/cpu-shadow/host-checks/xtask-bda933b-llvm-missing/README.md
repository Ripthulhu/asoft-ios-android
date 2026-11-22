# Partial host check: missing authored-probe assembler

This actual full-check attempt on 2026-11-22 **did not pass**. The all-feature
Clippy phase reached the Vulkan crate's custom build and failed because the
sanitized host environment did not provide `RVG_CPU_SHADOW_LLVM_AS`, and
`llvm-as` was absent from its effective command search path. The owner
reported `INCOMPLETE` and terminated its owned Cargo process with SIGTERM
(`cargo_exit_code: -15`). The failing custom build itself reported exit 1.

```sh
cargo +1.98.1 run --offline --locked --package xtask -- check
```

The recorded interval is 07:05:09.186743 through 07:06:27.009380 UTC. The
source is integrated formatting revision
`bda933b9592262dd85d8723e5c47cfe6886b6c25`, with the approved local Cargo
dependency-path override and clean runtime
`51c322d883ea723d290c931b3b2013c50f5e4934`.

## Exact observations

The complete raw `check.log` records:

- `testkit: ok` and `header: ok`.
- The formatting-check command, with no remaining formatting diff or error,
  followed by the first all-feature Clippy command.
- The custom-build error identifying the missing CPU-shadow probe assembler.
- The second Clippy command, using the tested features without defaults,
  already starting before the owner observed the first failure.

The original `xtask check` accumulates failed phases with `ok &= ...`; it does
not stop itself at the first failure. The owner detects failures from the raw
log, so phase advancement before detection is possible and occurred here.
There is **no passing second-Clippy, nextest, doctest or complete-check
result** from this run. No separate per-phase exit receipt is invented for
the formatter or the second Clippy command.

The owner records complete cleanup, no remaining owned processes, no cleanup
errors, no SIGKILL, unchanged source identities and unchanged prerequisite
receipts. It collected 77 resource observations; the minimum recorded
MemAvailable was 2,430,529,536 bytes, above the sampled stop threshold. This
was a missing build-tool setting, not a resource-floor stop. Sampled readings
do not establish a hard real-time resource guarantee.

## Preservation and scope

`artifact-inventory.json` records the original path, size and SHA-256 of every
artifact. Copied logs, owner source, launch/result/ownership records, resource
observations, formatting provenance, patches and preparation receipt are
byte-identical to their originals. Four larger source inventories remain at
their recorded external paths and are referenced by exact size/hash; their
before/after identities and source commits are also in `result.json`.

| Key retained artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `check.log` | 2,214 | `fcc37701db6c80f93f113d9ba0fb8cf763b17b32611a52487efaea286e612add` |
| `owner.py` | 31,633 | `905b2d7409d0978c8b75b094420ff8594d2d95c2fbc33d92edf890370b55ebb7` |
| `preparation.json` | 4,489 | `8e59371cfa93b25cf766708c625597f5254da01c1beaeabe9543002c8b4e1a4d` |

The preparation receipt retains its earlier pending-outcome scope without
alteration. The later actual failure is in `result.json`. No build, test,
header check or assembler invocation was rerun while preserving this
evidence. No e9 qualification export was replaced. These authored host logs
and metadata contain no Apple images, plist bodies, certificates or guest
payloads and grant no physical GPU, guest-boot, UI or product qualification.

The planned follow-up adds only the explicit, hash-verified LLVM assembler
path already used by the earlier successful native-runtime build. Its owner
and result are separate artifacts with a fresh output directory; this failed
attempt remains unchanged.

`next-owner-preparation.json` records the narrow independent source review
of owner SHA-256
`a7576872d5451e683e002a521762648823a3758d16f9683e3570e6392e475936`.
It adds only `RVG_CPU_SHADOW_LLVM_AS` and the corresponding file/provenance
checks. `llvm-as-runtime-build.json` is a byte-identical copy of the earlier
successful build metadata that records this assembler path, source e9,
runtime 51c and stable sources. It retains its original
`BUILT_NOT_DEVICE_QUALIFIED` scope. `llvm-followup-inventory.json` binds both
copies to their originals. No assembler binary is committed, and neither
the preparation agent nor its reviewer executed the assembler or any check.
