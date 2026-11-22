# Restored host check and source fixes

The previous chat's host directories were absent in the new session. The
source was reconstructed from the committed patch sequences, checking each
intermediate Git tree. Reims exactly matched the saved `bda933b` tree
`c603324e4e499668f5ae4133cfe14b39f4491275`; metal2vulkan exactly matched the
saved runtime tree `1b8c0eff2356c3a05cc372b6ea25e74cbdeff8d0`.

The [ten source increments](../../../../patches/cpu-shadow-host-checks/README.md)
correct the source issues reached by the full check:

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
7. Reject invalid gamma and cursor-glyph task-copy ranges before allocating,
   reusing the existing exact range check and preserving the later copy behavior.
8. Correct the two new regression assertions to wrap the local task error in
   its existing parent enum before comparing its exact raise identifier.
9. Give the shared data helper an internal owned-copy path so the local task
   reader can validate its range before allocation, retaining the public
   slice callback API and the existing global-limit/error ordering.
10. Hold the paging-discard test queue explicitly during its lifetime observation,
    preserving the preceding writer overlap and the original retention/byte assertions.

The clock remains `CLOCK_MONOTONIC`; its arithmetic and suspend behavior are
unchanged. The heap helper receives the same borrowed values and phase
numbers. The first six increments retain GPU commands, comparison values and
C API behavior, while exposing existing Rust clock and submission-gate services.
The seventh changes invalid-input allocation ordering in production display
code: an invalid task range now raises its existing error before attempting a
large allocation. It preserves global-limit guard priority, nil-task zero
behavior, valid copies and subsequent comparisons.

The current candidate source tree is
`4a87638743e4cb6a7e004c20e68ac8c66440d5d2`, local source commit
`d93a48896c11f26a341794e2675e417ec47f3bd2`. These are source-only increments;
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
| 07 | `8fa45892` | All-feature Clippy found the two new test assertions needed the existing parent-enum conversion. |
| 08 | `8ee08bfd` | Gamma/glyph regressions passed; a separate shared-task boundary fixture attempted a 32 GiB allocation before its copy callback could reject it. |
| 09 | `d15416c1` | Allocation regressions passed; a Vulkan paging lifetime fixture lost its timing assumption because the preceding command had already completed. |
| 10 | `4a876387` | Both gated lifetime fixtures and earlier regressions passed; the host denied self `process_vm_readv`, blocking the anonymous-page import death test. |

The first four attempts passed testkit, header and formatting checks. Each
stopped after its first observed failure, preserved the log and returned an
`INCOMPLETE` result. Owned processes were reaped with no remaining process or
cleanup error. The task runner sometimes starts its next command before the
external owner observes the previous failure; that command is stopped and no
pass is inferred from its appearance in the log.

The exact stopped-attempt logs, launch records and results are under `check-01`
through `check-10`. Attempt 05 passed testkit, generated header, formatting and
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
allocation. The seventh increment factors that sequence for gamma and the
source-confirmed matching cursor-glyph defect. The gamma test now requires the
exact `CopyRange` error, and a new glyph regression also checks untouched output. Nextest recorded 816 passing
tests before owned cleanup finished. A later active test received the owner's
SIGTERM and is not an independently established defect. Source and prerequisite
identities were unchanged. Its owner additionally records process names/start
identities and CPU counters for progress observation; failure handling and
cleanup were unchanged. The complete check, runtime integration and macOS
behavior-suite gates stay open.

Attempt 07 stopped during all-feature Clippy because the two new regression
assertions directly converted a local-task error instead of wrapping it in the
existing parent enum. The eighth increment corrects those two assertions and
leaves the reviewed production change intact.

Attempt 08 passed both Clippy configurations, the C harness and the gamma/glyph
regressions, then stopped on the separate shared-task boundary fixture
`a_length_past_any_task_raises`. Its generic slice callback could only reject
the read after a 32 GiB destination had been allocated. The run recorded 2,256
passing tests before the owner stopped after that allocation abort; a later
SIGTERM was cleanup fallout. Source/prerequisite identities remained unchanged
and cleanup completed without survivors or errors.

The ninth increment adds an internal owned-copy path behind the same global
length guard, and routes the actual local-task reader through its checked copy.
The existing public slice callback API remains a wrapper. Legacy small, zero,
raising and above-limit tests remain. The exact-MAX test now checks forwarded
offset/length and its callback error on the production owned path; a real-task
regression also verifies MAX gives `CopyRange` and greater values give
`BufferLength`. This intentionally replaces the former test's requirement that
the host successfully reserve a 32 GiB legacy destination. No smaller limit,
synthetic slice or host memory-policy change is introduced.

Attempt 09 passed both Clippy configurations and all allocation regressions,
then stopped after 2,653 passing tests at the multisampled paging-discard
lifetime fixture. Its preceding command had already completed when the test
expected it to remain in flight; the paging completion callback had not yet
arrived. The fixed 8,000-round busy shader did not guarantee the intended
observation interval. The later private-buffer fixture received the owner
cleanup SIGTERM. Raw runtime warnings, complete stopped log and clean owned
reap are retained. This result does not establish a production lifetime fault.

The tenth increment uses the existing timeline gate on the exact queue,
armed before the preceding writer commits. It retains writer/paging overlap,
strictly empty completion channel, mappings/import counts, next-import
isolation, final release and exact writeback bytes. A separate controller opens
on request, disconnect or a 30-second timeout. A timeout permits cleanup but
cannot pass the test. Only the test fixture and test visibility of the existing
gate change; no production paging/runtime change is made.

Attempt 10 passed both Clippy configurations, the C harness, all allocation
regressions and both gated paging lifetime fixtures. It recorded **2,805 passing
tests** before stopping at the anonymous-page import death test. That test
requires readable memory without file backing to reach the existing fatal
remap refusal. Here the preceding readability probe returned false, so the
code correctly rejected the request earlier and the expected death was absent.

The [one-byte host diagnostic](../../../../patches/cpu-shadow-host-checks/readability-host-probe.json)
confirmed `process_vm_readv` on the process's own initialized writable memory
returned `-1/EPERM`. The host reports an active seccomp filter, but the precise
enforcing rule has not been identified. The full check is therefore recorded
as **BLOCKED_ENVIRONMENT**, with its raw owner result still `INCOMPLETE`. No
production fallback, test skip, assertion weakening or host-policy change was
made. The complete gate must be rerun in a suitable existing environment.

The later active surface-hold test received the owner cleanup SIGTERM; it is
not a second independent defect. Two existing entries were skipped, 213 selected
tests were not run, and doctests were not reached. Source and tool identities
stayed unchanged; cleanup completed, the owner lock was released and no build
or test process remains. The [coverage record](../../../../patches/cpu-shadow-host-checks/coverage-and-limitations.json)
separates the existing manual/child fixtures and conditional device coverage.

All ten exported patches independently reapply to every expected intermediate
tree, as recorded in `series-reconstruction.json` beside the patches. The full
Linux result and other integration gates remain open.

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
