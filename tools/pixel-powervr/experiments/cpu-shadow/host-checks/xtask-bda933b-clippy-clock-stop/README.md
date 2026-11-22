# Partial host check: disallowed direct clock calls

This third actual full-check attempt on 2026-11-22 **did not pass**. With the
verified LLVM assembler configured, the first all-feature Clippy phase
reported five uses of the disallowed method `std::time::Instant::now` in
`crates/reims-vgpu-vulkan/src/cpu_shadow_probe.rs`. The owner stopped its
owned process tree at that first concrete failure and recorded `INCOMPLETE`.
Cargo was terminated by SIGTERM (`cargo_exit_code: -15`).

```sh
cargo +1.98.1 run --offline --locked --package xtask -- check
```

The recorded interval is 07:14:14.822083 through 07:15:12.728972 UTC.
The source remains integrated revision
`bda933b9592262dd85d8723e5c47cfe6886b6c25`, with the approved local Cargo
dependency-path override and clean runtime
`51c322d883ea723d290c931b3b2013c50f5e4934`.

## Exact observed boundary

The retained raw log records `testkit: ok`, `header: ok`, the formatting-check
command without a formatting diff, and the first Clippy command:

```sh
cargo clippy --workspace --all-targets --all-features -- -D warnings
```

Clippy identifies direct clock calls at lines 272, 380, 385, 395 and 455,
with the repository guidance to use `Clock (7.5)`. The exact diagnostics are
preserved without edits in `check.log`. That log contains no subsequent
Clippy, nextest or doctest command or result. No complete-check pass,
later-phase pass or runtime-test outcome is inferred from this compilation
and lint failure.

The owner records complete owned cleanup, no remaining processes, no cleanup
errors and no SIGKILL. Source identities and all prerequisite pins were
unchanged. Its postcheck also revalidated the exact regular LLVM assembler,
mode 0755, size 4,105,480 bytes and SHA-256
`3c9a80d96a7c71624c0ce7cc2c36ef71032a8fb2e772dd0fde26ddda568b80cc`.
The 57 resource observations have a minimum recorded MemAvailable of
3,470,155,776 bytes; this was a lint stop, not a resource-floor stop.
Those samples do not establish a hard real-time resource guarantee.

## Exact preservation

`artifact-inventory.json` records every original artifact path, byte count
and SHA-256. Copied logs, source owner, launch/result/ownership records,
resources, formatting and assembler provenance, patches, preparation and
root-launch receipts are byte-identical to the originals. The four larger
source inventories remain at their original paths with exact size/hash
references; `result.json` retains their matching before/after identities,
commit IDs and diff hashes.

| Key retained artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `check.log` | 2,693 | `059d013165e4b17a44647c7923d003320da3b11940c08b2a43a98a1888b45692` |
| `owner.py` | 33,557 | `a7576872d5451e683e002a521762648823a3758d16f9683e3570e6392e475936` |
| `preparation.json` | 4,226 | `aea3a647c89d9bdb6b5b5222ac30aad93f07724fd09b9aa105cb306468603648` |
| `root-launch.json` | 1,453 | `78056bdcc11b134e655813c56432302c7b0b80b788912eedca0f9982d5bf4b7d` |

The preparation and launch receipts retain their historical pending-outcome
scope. The actual later result is in `result.json`. This preservation ran no
build, test, header check or assembler command and changed no reims source,
dependency, cache or earlier qualification export. All copied contents are
authored source, host logs or metadata; no Apple images, plist bodies,
certificates, guest payloads or assembler binaries are included. This
evidence grants no physical GPU, guest-boot, UI or product qualification.
