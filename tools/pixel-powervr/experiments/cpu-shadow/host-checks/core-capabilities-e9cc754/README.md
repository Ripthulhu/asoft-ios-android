# Host C API/MMIO capability qualification

**Both argument-buffer configurations passed** on candidate
`e9cc7541e4edee4896d9564b3056bb2799595d3f` with metal2vulkan
`51c322d883ea723d290c931b3b2013c50f5e4934`.
[`host-validation.json`](host-validation.json) pins source/tree, compiler,
generated input, test/library hashes and the exact validation environment.
[`SHA256.json`](SHA256.json) covers all three exact retained records.

The authored C program uses the installed C API, MMIO/FIFO, isolated-task
handshake and core resource constructors. It creates a private-flag buffer and
shared heap placement, performs GPU copies and fills, discards and rebinds the
same resource objects to newly fragmented guest pages, checks all output and
old/new/gap bytes, and completes task deletion. It requires completed shadow
epochs as well as CPU-visible byte comparisons.

| Result | Argument buffers enabled | Argument buffers disabled |
|---|---|---|
| Device-info key 33 | `0xabf` | `0xa9f` |
| Device-info key 42 | `3` | `0` |
| Shadow chunks / views | `4 / 8` | `4 / 8` |
| Prepared / finished epochs | `2 / 2` | `2 / 2` |
| Bytes uploaded / scattered | `294912 / 98400` | `294912 / 98400` |

The exact [`host-validation.log`](host-validation.log) includes six instance
validation-layer insertions and two device-layer insertions. Synchronization
validation was enabled; no validation error was reported. The combined test
exited zero in 0.665724 seconds. This is a host diagnostic duration, not a Pixel
or guest performance result. Each child used a new shader cache, removed
`LD_PRELOAD`, and searched this candidate's C library before inherited loader
paths. A separate [`backend truth-table unit`](backend-truth-table.log) passed
with one selected test and 432 filtered tests.

Two earlier fresh builds were killed during memory pressure. A proposed cached
dependency was rejected after prerequisite byte comparison found a mismatch;
the passing build reused no archived compiled dependency. Releasing archived
old build outputs and restoring the documented CMake/SDL environment allowed a
fresh build to complete. The exact build-attempt history remains in the record.

This validates the two core resource paths and device-info configuration gates.
It does not claim guest-framework argument-buffer shader dispatch, physical
PowerVR execution, full `cargo xtask check`, a cold Apple boot, app-UID execution
or product qualification. The candidate remains experimental and no APK was
built. Later device evidence, when available, must identify its own exact
Android runtime and package hashes.
