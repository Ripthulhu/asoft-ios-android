# Host header check for e9cc754

The recorded `cargo +1.98.1 run --offline --locked --package xtask -- header
--check` completed with **exit 0 in 1.267819 seconds**, ending with
`header: ok`. It ran on 2026-11-22 at 06:42:43–06:42:44 UTC against reims
`e9cc7541e4edee4896d9564b3056bb2799595d3f`, using the restored host target.

The source at `xtask/src/header.rs` requires **cbindgen 0.29.4** and refuses
the check when the generator version differs. The successful check therefore
confirms that the pinned generator's output matched the committed header.
Its recorded before/after SHA-256 remained:

```text
da1dc6eb2b616fb17ccac2a9a5ddfac14c5c735b0965beb0478e376f80e5aad7
```

The recorded local Cargo manifest hash also remained unchanged. `launch.json`
preserves the exact command, source revision, working directory, environment,
and initial resource observation. `result.json` adds the exit code, elapsed
time, final observation, and log hash; `check.log` is the exact output.
`verification.json` binds these three byte-identical copies to their original
paths and hashes and records the source-level generator contract.
`SHA256SUMS` covers the files preserved here.

No command was rerun for this evidence copy. This result qualifies only the
header comparison. The full `cargo xtask check`, the required behavior suite,
and independent guest cold-boot/integration qualification remain pending.
