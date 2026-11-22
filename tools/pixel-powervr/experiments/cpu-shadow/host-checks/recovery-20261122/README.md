# Restored host check and diagnostic fixes

The previous chat's host directories were absent in the new session. The
source was reconstructed from the committed patch sequences, checking each
intermediate Git tree. Reims exactly matched the saved `bda933b` tree
`c603324e4e499668f5ae4133cfe14b39f4491275`; metal2vulkan exactly matched the
saved runtime tree `1b8c0eff2356c3a05cc372b6ea25e74cbdeff8d0`.

The [six source increments](../../../../patches/cpu-shadow-host-checks/README.md)
correct the diagnostic code reached by the full check:

1. Use the existing awake-time clock for the installed CPU-shadow probe's
   cumulative command wait budgets.
2. Make that existing clock service available to the separate diagnostic
   example crates and replace their four direct clock calls.
3. Use fixed-size four-byte chunks for the authored tile comparison.
4. Group the heap diagnostic's related backing inputs and document the heap
   and rebind entry points.
5. Compile the existing submission gate once as a shared Linux/Android module;
   derive its device from the existing queue and retain its operations and waits.
6. Extend the C harness to exercise both new CPU-shadow exports, retaining exact
   function-count and per-function completeness checks and output-boundary assertions.

The clock remains `CLOCK_MONOTONIC`; its arithmetic and suspend behavior are
unchanged. The heap helper receives the same borrowed values and phase
numbers. GPU operations, comparison values and C API behavior are unchanged.
The Rust API gains public access to the existing awake-time service and
submission gate.

The current candidate source tree is
`7aab93b65472f72ee12756a016b94c26465d80bb`, local source commit
`e473c264954c5c4db2e9a4d53671b41a25b131d1`. These are source-only increments;
the qualified phone runtime remains the original e9 package.

## Required check

Each attempt runs the original full command on its recorded source:

```sh
cargo +1.98.1 run --offline --locked --package xtask -- check
```

There is one host check owner, one build job and serial tests, with the prior
resource floors and owned-process cleanup. The restored host is independent
of the Pixel running the preparation helper.

| Attempt | Source tree prefix | Recorded stopping point |
|---|---|---|
| 01 | `963542a2` | All-feature Clippy found two direct clock calls in the alias example. |
| 02 | `6bfcb3a4` | All-feature Clippy rejected the tile diagnostic's constant `chunks_exact(4)`. |
| 03 | `330f7365` | All-feature Clippy rejected the heap helper's eight parameters and undocumented public entry point. |
| 04 | `bc5c6838` | All-feature Clippy found duplicate inclusion of the shared submission gate in the combined qualifier. |
| 05 | `794660bc` | Both Clippy configurations passed; nextest found the C harness covered 50 of 52 exported functions. |
| 06 | `7aab93b6` | The repaired C harness passed; gamma mapped-length boundary test attempted a 32 GiB allocation before its expected task-range fault. |

The first four attempts passed testkit, header and formatting checks. Each
stopped after its first observed failure, preserved the log and returned an
`INCOMPLETE` result. Owned processes were reaped with no remaining process or
cleanup error. The task runner sometimes starts its next command before the
external owner observes the previous failure; that command is stopped and no
pass is inferred from its appearance in the log.

The exact stopped-attempt logs, launch records and results are under `check-01`
through `check-06`. Attempt 05 passed testkit, generated header, formatting and
both required Clippy configurations. Nextest passed 93 tests before the
`c_harness_calls_every_function` failure. A later test received the owner's
cleanup SIGTERM; it is not counted as a second independent defect. Cleanup
completed with no survivors or errors, and source/prerequisite identities
stayed unchanged. The sixth source increment adds the missing executable harness
coverage: counter snapshots and output boundaries on the live test device, and
invalid-only probe calls that cannot start competing GPU work.

Attempt 06 passed both Clippy configurations and the repaired C harness, then
stopped on `gamma_mapped_length_past_any_task_faults`. The process aborted when
reserving 34,359,738,368 bytes before reaching the expected local-task range
fault. The existing cursor snapshot path already checks the range before its
allocation; a source correction is being prepared to give gamma the same
ordering without weakening its fault assertions. Nextest recorded 816 passing
tests before owned cleanup finished. A later active test received the owner's
SIGTERM and is not an independently established defect. Source and prerequisite
identities were unchanged. Its owner additionally records process names/start
identities and CPU counters for progress observation; failure handling and
cleanup were unchanged. The complete check, runtime integration and macOS
behavior-suite gates stay open.

## Coverage boundaries

The Linux check selects testkit and Vulkan features. Its all-feature Clippy
configuration compiles the authored `guest-arm64` integration, but its nextest
feature list does not run that ARM64-specific integration test. The earlier
physical 17-case package qualification remains separate evidence.

This host has no `/dev/udmabuf`. The existing tests
`a_dma_buf_shows_the_pages_of_its_range` and
`a_view_past_the_limits_is_made_of_chunks` return early when that device is
unavailable; a successful test process would not establish hardware DMA-BUF
coverage. macOS C API/Metal behavior, real window presentation, and physical
iOS boot/UI also remain outside this Linux run.

## Restored tools and local paths

[provenance.json](provenance.json) records actual versions, hashes and
official acquisition sources. Rust/Cargo 1.98.1, LLVM assembler 21.0.0,
nextest 0.9.152 and CMake 3.31.6 match the earlier pinned identities. Cbindgen
0.29.4 was built from its locked release; Ninja has the same reported
version but a different executable hash, recorded explicitly.

The local dependency prefix supplies SDL build prerequisites, lavapipe and
Khronos validation layers. The Vulkan enumeration succeeded with the layer
inserted; it is not a GPU test or window-system qualification.

```text
/workspace/scratch/abcabc3f01ae/host-clock-fix/clock-worktree
/workspace/scratch/abcabc3f01ae/host-clock-fix/metal2vulkan-full
/workspace/scratch/abcabc3f01ae/host-clock-fix/runs
/workspace/scratch/abcabc3f01ae/host-tooling
```

`env.sh` and `environment.json` capture this session's absolute build paths;
they must be adapted when reconstructing in another workspace. The local
Cargo dependency override is retained separately from the source patches.
The check target's logical cache path was moved to the workspace disk while
the owner was stopped, preserving its 949-entry inventory. This prevents the
new build from exhausting the small memory-backed home filesystem.

No APK, Android runtime replacement or new physical GPU qualification is
claimed by these host fixes.
