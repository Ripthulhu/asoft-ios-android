# Host alias and workspace-check follow-up

The supported host alias route **passes**. The original formatting, lint,
missing-CMake and stale-fixture blockers are repaired. The complete workspace
gate now builds and runs, but **is not green**: the final run reports
**3,007 tests run, 3,001 passed, six failed and two skipped**. This checkpoint
preserves the six failures, including an unresolved paging-test precondition.

This follows the [reims-owned Pixel proof](../reims-producer-native/README.md).
It is a host source/validation increment, with no new Android binary, phone
test, native-memory qualification or iOS boot. The earlier Pixel package and
its exact qualified source remain separately identified in that checkpoint.

## Supported CPU alias

The example's default and `--vulkan-alias` modes duplicate the producer's
opaque FD, import it on the exact same logical Vulkan device, and map the
imported allocation through `vkMapMemory`. The allocation size, memory type
and device-address flags match the producer. This creates another CPU mapping
of the same allocation; no second runtime buffer or copy supplies its bytes.

The [Vulkan opaque-handle contract](https://docs.vulkan.org/refpages/latest/refpages/source/VkExternalMemoryHandleTypeFlagBits.html)
does not promise a generic POSIX byte layout. The
[FD import contract](https://docs.vulkan.org/refpages/latest/refpages/source/VkImportMemoryFdInfoKHR.html)
allows the driver to interpret that handle and transfers the duplicated FD
only after successful import. Failed imports close the duplicate locally.
The mapping owner retains the device and unmaps/frees its import before the
CPU/native ownership leases can retire.

This host diagnostic deliberately requires host-visible, coherent memory.
The Pixel's cached, noncoherent native mapping provider remains a separate
qualification. A passing Vulkan import does not qualify raw POSIX mapping,
arbitrary offsets, arbitrary guest pages, producer atomics or executable data.

The final run used lavapipe/llvmpipe LLVM 19.1.7, memory type 0, flags `0xf`,
32,768 allocation bytes and cache atom 64. It checked:

| Check | Observed result |
| --- | --- |
| Initial alias contents | All 8,192 words match; alias address differs from canonical address |
| Registered view | Selected 16 KiB half of the allocation |
| Physical-span resolution | Contiguous spans resolve; repeated physical pages are refused |
| Alias store | Exact scalar value is visible through the canonical mapping |
| Alias retirement | Mapping drops; lookup of its stale address is refused |
| Ownership | Live export blocks CPU end; CPU epoch blocks GPU work |
| Runtime compute and independent readback | All 8,192 words match; same runtime object |
| Cache/submission accounting | Four flushes, four invalidations, four completed submissions |
| Abandoned epoch | Later CPU and GPU access refused |
| Public owner release | CPU/native leases retain the allocation until their release |
| Validation | Khronos instance/device layers loaded; synchronization validation enabled; zero `VUID-` or `SYNC-HAZARD` messages |
| Final status | `REIMS_PRODUCER_RUNTIME_PASS`, exit 0, `producer_atomics=0` |

See [alias-vulkan-final.log](alias-vulkan-final.log) and its
[execution record](alias-vulkan-final.json). Its SHA-256 is
`eb7c818dc9eef0b3727ddb64bfe3d91c86f77585c1ac04bb1880899f128e255c`.

The explicit `--posix-alias` negative control still exits 1 before alias
registration or writes: word 0 is `0x9028`, expected `0x6a1b2c30`, with
`OPAQUE_FD_POSIX_ALIAS_UNQUALIFIED`. See
[alias-posix-final.log](alias-posix-final.log). The refused raw interpretation
is retained as evidence; it is not counted as the working alias path.

## Workspace repairs

The six [optional source patches](../../patches/reims-host-validation/README.md)
make the following changes:

- Repair baseline Rust formatting, a nonzero log denominator, a mutex API
  mismatch and collection lookup lint. Route Linux cache timers through the
  OS clock interface while retaining `CLOCK_MONOTONIC` awake-time behavior;
  the guest's `CLOCK_BOOTTIME` clock is unchanged.
- Complete the sleep callback fixtures and check true, false and absent
  callbacks. Extend the C harness to exercise all 50 declared functions,
  including the producer API's refusals, retained identity, CPU/export/GPU
  transitions and full-range readback.
- Classify two runtime-reported, unmeasured format semantics in strict audits.
  Strict mode refuses them on both device classes; default mode retains its
  existing logged relay. This optional strict-policy change has no new cold
  guest boot qualification and is not claimed ready for upstream integration.
- Check SIMD flags against all of the actual host's audited rows, each present
  exactly once, retaining the separately measured Mac pin. The product's
  capability calculation is unchanged. Keep idle defaults asserted at compile
  time.
- Fix the surface-lifetime test's address-reuse ambiguity. A retained file
  descriptor prevents inode reuse while device/inode/offset identify the
  original mapping; it does not retain the mapping or surface. A regression
  replaces this test's own mapping at the same address and proves the witness
  distinguishes it. The resource/import lifetime assertions remain enforced.
- Add the Vulkan import/map alias provider described above.

CMake 3.31.6, Ninja 1.11.1 and a private X11 development SDK allowed the real
SDL window backend to compile. This is not an SDL no-link substitute. The
SDK's 28 Debian packages were downloaded over verified HTTPS and checked
against the package index's sizes and SHA-256 values; the index matched its
InRelease digest. **The release signature was not verified** because no
verifier was available. No system package database or package maintainer
script was used. [sdl-sdk.json](sdl-sdk.json) records the exact packages and
relocated pkg-config metadata; [prepare_sdl_sdk.py](prepare_sdl_sdk.py) records
the extraction procedure. [host-tools.json](host-tools.json) records tool
versions and invoked binary hashes.

## Full gate and remaining failures

[workspace-check-final.log](workspace-check-final.log), SHA-256
`b27a62272ee1ba603c3ca0b99b42454f251828dc2522acb59cca1128e1c590e1`,
records the complete `cargo +1.98.1 xtask check` run. Its total wall time was
391.95 seconds and its exit status was 1.

| Stage | Result |
| --- | --- |
| Testkit and generated-header checks | Passed |
| `cargo fmt --all --check` | Passed |
| Workspace/all-target/all-feature Clippy, warnings denied | Passed |
| Workspace/all-target Vulkan Clippy without default features, warnings denied | Passed |
| Workspace compilation and nextest | 3,007 run: 3,001 passed, six failed, two skipped |
| Doctest stage | Passed; two existing documentation examples ignored |
| Overall gate | **Failed** |

No failing case was disabled or converted to success. The two nextest skips
were also present in the earlier workspace runs. No ignore attribute or
expected-output file was added or changed by this increment.

The remaining cases are listed in [remaining-failures.json](remaining-failures.json):

| Cases | Evidence and boundary |
| --- | --- |
| Two core oversized-length tests | Both abort because allocation of 34,359,738,368 bytes fails. This establishes an allocation failure in this host, not a requirement for 32 GiB of resident physical RAM. Address-space and data rlimits report unlimited. |
| Three Linux memory-readability/remap tests | A direct one-byte self-`process_vm_readv` preflight returns `EPERM`. The affected readability path therefore cannot establish readable anonymous memory in this environment. No security policy or production memory checks were changed. |
| Multisampled texture paging-discard test | The command buffer intended to hold work in flight is already completed when the test inspects it. The test fails its precondition before qualifying retention/readback. The cause remains unresolved. |

The paging case also failed when run in isolation. Increasing its busy-kernel
round count from 8,000 to 80,000 still failed; that experiment is preserved in
[focused-lifetime-repairs.log](focused-lifetime-repairs.log) and **was reverted**.
The final patch leaves `paging_discard.rs` unchanged. The surface-lifetime
case, its new address-reuse regression and private-buffer paging pass in the
final full run.

The remaining full-gate work needs a host on which the required memory probes
and large allocation can run, plus a resolved and measured way to hold the
multisampled paging case in flight. A larger spin count is not established as
a fix. These findings do not qualify an iOS workload or permit merging this
branch as green.

## Reproducing the host run

Apply the source series to the exact prepared producer base and retain the
prepared metal2vulkan dependency described in the patch README. The local
absolute Cargo overrides are separately recorded in
[reims-path-override.patch](reims-path-override.patch); adapt their paths to the
local prepared checkout. Use [reims-Cargo.lock](reims-Cargo.lock) for the
recorded dependency resolution. The portable source patches exclude these
machine-specific overrides.

Use Rust/Cargo 1.98.1, cargo-nextest 0.9.152, cbindgen 0.29.4 and the recorded
host build dependencies. [run_check.py](run_check.py) is the exact runner used
here; its `ROOT`, `LVP`, cache and tool paths name this workspace and need
relocation elsewhere. It records the command, environment, exit, timeout,
source snapshot and log hash. It uses one compiler job and one test thread.
Do not run GPU suites or full checks concurrently.

The three final commands were:

```sh
cargo +1.98.1 xtask check
cargo +1.98.1 build -p reims-vgpu-vulkan --example producer_memory
/path/to/producer_memory /path/to/runtime_examples.air --vulkan-alias
```

The negative control substitutes `--posix-alias`. Both alias executions used
separate fresh runtime caches with the Khronos validation layer. The AIR is
assembled from the prepared metal2vulkan repository's own
`crates/metal2vulkan-validation/fixtures/public/examples/runtime_examples.ll`;
its SHA-256 is
`0318b8e0230fec78c86d01e78e2e7dd0b98c4cb139d3006d1c5dc3e3203b0bdf`.
No guest-derived shader or Apple binary is supplied by this checkpoint.

[validation.json](validation.json) summarizes the final results and retains
earlier failed runs as history. [host-artifacts.json](host-artifacts.json)
identifies the exact executable and authored AIR used. The patch provenance
verifies that the final gate, example build and both alias executions used the
same source content, and that all 30 changed source files match their committed
blobs. Applying the six patches in a temporary Git index reconstructs the
exact final source tree. `checkpoint-index.json` hashes this fork increment's
files, excluding the index itself.

The latest actual device proof remains the earlier serialized reims/native
EL0 handoff. General shared-device ownership, guest-memory mapping hooks,
concurrent vCPUs, producer atomics, app-UID execution of the combined bridge,
suspend/resume and iOS 26 boot remain outside this host checkpoint.
