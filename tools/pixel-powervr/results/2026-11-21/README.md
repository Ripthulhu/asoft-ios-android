# Pixel 10 Pro XL: physical GPU tests

Date: 2026-11-21. **Ordered tile-image rendering and a Vulkan-owned, coherent
CPU/GPU allocation passed. Importing existing pages through DMA-BUF remains
unsupported. A CPU page-offset alias of the exported opaque FD did not expose
the requested page; a later one-page move from a full mapping passed.** The
successful rendering, sharing and one-page move were reproduced under an
ordinary Android app UID. A later real Metal compiler/runtime probe passed
producer-backed compute and floating-point framebuffer fetch under root and the
ordinary app UID, alongside passing ordinary-memory CPU execution controls.
A native execution probe then passed two 16 KiB data aliases but failed to
return from direct code execution. No integrated ASoftware or iOS boot has
been tested. A later combined CPU-memory/copied-code command lost its Tango
connection before any result was collected. Later recovery established an
asynchronous SError kernel panic; the interrupted parent/child phase remains
unresolved because the expected test log was not found.
These different execution contexts and limits remain explicit.

The original two execution probes and their shaders were taken from app-fork commit
`046882039212433b562f662cd666611c24bd85f1`. Their hashes were checked on the phone
before execution. All four matched `SHA256SUMS`. The query reporter came from
`c79b7d974f3f16cdddf8a02f305ed4bd561fe83a`; the newer producer probe hashes and
their phase-specific results are recorded below.

## Device and context

| Observation | Value |
|---|---|
| Phone | Google Pixel 10 Pro XL, `mustang`, Tensor G5 |
| Android | 17, SDK 37 |
| Build | `CP4A.261105.040.A1` |
| Security patch | 2026-11-05 |
| Kernel | `6.12.81-android16-6-g4a1a020d156e-ab16388316-4k` |
| Architecture / page size | AArch64 / 4,096 bytes |
| Execution identity | UID 0, EUID 0; `u:r:ksu:s0` |
| SELinux | Enforcing |
| GPU | PowerVR D-Series DXT-48-1536 MC1 |
| Vulkan loader / device API | 1.4.0 / 1.4.344 |
| Vendor / device ID | `0x1010` / `0x71061212` |
| Driver version | `0x006a5136` |
| Driver name / info | PowerVR D-Series Vulkan Driver / `26.1@6967606` |
| Reported conformance | 1.4.5.0 |

The terminal was already running as root through ADB/KernelSU. Root-shell
results are labeled separately from the ordinary-app run recorded below;
there was no ordinary ADB-shell comparison.
SELinux, device-node permissions, kernel parameters, modules, and application
settings were not changed for the tests. Files were staged in fresh
temporary directories under `/data/local/tmp`. The ordinary-app run used its
own package, native-library installation and private report directory.

## Tile-image execution: PASS

The driver reported:

```text
VK_EXT_shader_tile_image: 1
dynamicRendering: 1
shaderTileImageColorReadAccess: 1
shaderTileImageDepthReadAccess: 1
shaderTileImageStencilReadAccess: 1
shaderTileImageCoherentReadAccelerated: 1
shaderTileImageReadSampleFromPixelRateInvocation: 0
shaderTileImageReadFromHelperInvocation: 0
```

The program ran with a 60-second process limit and its built-in five-second
fence limits. Both cases completed successfully:

| Case | Draws | Primitives | Checked pixels | Wrong pixels | Expected RGBA |
|---|---:|---:|---:|---:|---|
| Same draw | 1 | 32 | 1,024 | 0 | `[32, 208, 208, 255]` |
| Across draws | 2 | 64 | 1,024 | 0 | `[64, 160, 160, 255]` |

Final output was `result: PASS`, with `tile_exit_code: 0`. The across-draw case
uses no intervening barrier inside that rendering instance.

This establishes the two authored, single-sample integer-color recurrence
tests on the reported driver under root. It does not test the patched Metal
compiler, the candidate runtime, floating-point formats, MSAA, general raster
order groups, application access, or iOS rendering. The depth/stencil feature
bits are advertised capabilities; shader depth/stencil reads were not exercised.
The accelerated property is not a performance measurement. The reported lack
of helper-invocation tile reads supports retaining the compiler's existing
dataflow restrictions.

No validation layer was requested or enabled on the phone. The output line
`validation_errors: 0` is an unused counter in this run, not evidence of an
active Vulkan validation layer.

Captured terminal evidence: [tile-root.jpg](tile-root.jpg).

## DMA-BUF capability: UNSUPPORTED

The probe reported these extensions:

```text
VK_KHR_external_memory_fd=yes
VK_EXT_external_memory_dma_buf=yes
VK_EXT_queue_family_foreign=yes
VK_EXT_external_memory_host=no
```

Its external-buffer query returned:

```text
usage=0x23
features=0x0
compatible_handles=0x200
export_from_imported=0x200
RESULT=UNSUPPORTED: DMA-BUF not importable for a storage/transfer buffer
dma_exit_code: 3
```

Here `0x23` is storage-buffer plus transfer-source and transfer-destination
usage. `0x200` is the DMA-BUF handle type. The returned feature mask lacks
`IMPORTABLE`. A compatible-handle bit is a separate property, and is not
permission to import a buffer whose feature query refused that contract.

The probe correctly stopped **before** opening `/dev/udmabuf`, exporting memfd
pages, creating a logical device, or attempting memory import or transfer.
The printed backing/export sizes and page ordering describe the planned test;
they are not proof that those operations happened. No CPU-to-GPU or GPU-to-CPU
round trip was executed.

Captured terminal evidence: [dma-root.jpg](dma-root.jpg).

## Complete external-buffer matrix

The [query-only reporter](../../VULKAN-CAPS.md) completed all **51 queries** under
requested Vulkan API 1.3 and exited 0. Its transferred executable SHA-256 was
`07dfa8e6622060e17e7375593f303a0e12568bfcf8859a3b7d5cd657922784fe`, checked
on the phone before execution. It allocated no GPU buffers and submitted no
GPU work.

| Handle type | Tested usage combinations | External feature mask | Importable | Exportable | Dedicated only |
|---|---:|---:|---|---|---|
| `DMA_BUF_EXT` | 17 | `0x0` | No | No | No |
| `OPAQUE_FD` | 17 | `0x6` | Yes | Yes | No |
| `ANDROID_HARDWARE_BUFFER_ANDROID` | 17 | `0x6` | Yes | Yes | No |

The rows include the runtime's exact `0x1ff` and `0x201ff` usage masks. The
opaque-FD and Android hardware-buffer rows describe their respective handle
contracts; they do not make an arbitrary DMA-BUF importable as another type.
No Android hardware buffer was allocated or executed in this test.

Additional reported properties relevant to the candidate:

- `bufferDeviceAddress=1`, `bufferDeviceAddressCaptureReplay=1`.
- `sparseBinding=1`, `sparseResidencyBuffer=1`, but
  **`sparseResidencyAliased=0`**.
- Memory type 1 has flags `0x7`: device-local, host-visible and host-coherent.
  Type 2 has flags `0xb`: device-local, host-visible and host-cached, without
  host coherence.
- `minMemoryMapAlignment=4096`, `nonCoherentAtomSize=1`,
  `bufferImageGranularity=1`.
- `maxBufferSize=4294967295`, `maxMemoryAllocationSize=8589934592`, and
  `maxStorageBufferRange=134217728`. These are declarations, not tested
  allocation sizes.
- Queue family 0 has two queues, flags `0x1f`, including transfer and sparse
  binding. No sparse resource was created or bound.

Captured evidence: [matrix summary](caps-summary.jpg),
[memory and feature properties](caps-memory.jpg), and
[exact runtime usage rows](caps-runtime.jpg).

## Vulkan-owned shared allocation: PASS

The [opaque-FD producer experiment](../../OPAQUE-FD.md) starts with a **new
Vulkan allocation**. It does not attempt to import pre-existing guest memory.
Version 1, SHA-256
`0daa83ea361129d70cc586cbca58401b2614e907f55383fbdf64ee7258a183d7`, was checked
on the phone and completed with `RESULT=PASS`, exit 0.

The allocation and both buffers used the runtime's complete `0x201ff` usage
mask, with non-sparse create flags 0. The observed allocation was **32,768
bytes: eight 4,096-byte pages**, using coherent memory type 1. Both buffer
requirements were size 32,768, alignment 4,096, memory-type bits `0x7`, with
neither dedicated allocation required nor preferred.

The probe legally exported an `OPAQUE_FD` from the Vulkan allocation, duplicated
that FD, and imported the duplicate using the original allocation size and
memory type on the same device. The imported duplicate was consumed by Vulkan;
the original exported FD remained owned by the probe.

All of these checks passed, comparing **8,192 words** per full-buffer check:

- CPU writes through one Vulkan map were visible through the second map and
  through an independent GPU copy/readback buffer.
- GPU page-distinct fills were visible through both Vulkan CPU mappings.
- Native `mmap(MAP_SHARED)` of the exported FD at offset zero exposed the
  expected GPU-filled contents before any native-view write.
- Native-map writes reached both Vulkan maps and independent GPU readback.
- Further GPU fills reached all three CPU mappings.

The mappings were page-aligned. The FD reported an extent of 32,768 bytes.
Nonzero buffer device addresses were obtained, but no shader dereferenced
them. Work used fenced transfer commands, global host/transfer barriers and
host-coherent memory; there were no explicit flush/invalidate or DMA-BUF cache
ioctls. The program used a 30-second process limit and five-second fence limits.

This establishes a small, canonical contiguous allocation on this driver.
Native mapping of an opaque FD is a driver-specific POSIX observation, not a
portable Vulkan guarantee. It does not establish arbitrary guest-page import,
sparse GPU aliases, large guest RAM, shader memory access or runtime integration.

Captured evidence: [opaque-producer-v1.jpg](opaque-producer-v1.jpg).
The exact [v1 source, executable and build metadata](opaque-v1/README.md) are
preserved alongside the result.

## Direct CPU page-offset aliases: UNSUPPORTED

Version 2, SHA-256
`f5fb47f842632a196aad9441ce1cc25d313dea2dd5b274d57b43662e0d97c59a`, was also
verified before execution. All Vulkan and full offset-zero native-map phases
passed again. It then reserved four fresh CPU pages and attempted to map FD
pages `{5,0,7,2}` into those owned slots. No sparse or scattered GPU resource
was involved.

The first read check returned:

```text
FAIL: CPU_SCATTER_INITIAL_CONTENTS slot=0 source_page=5 word=0
got=0x7b620000 expected=0x7b620005
CPU_SCATTER=UNSUPPORTED initial offset mappings do not expose expected pages;
no scatter writes attempted
RESULT=VULKAN_FD_MMAP_PASS_CPU_SCATTER_UNSUPPORTED
opaque_v2_exit_code: 4
```

The requested page-5 mapping contained page 0's first value. This is one
measured counterexample; it does not establish how every offset behaves or
identify the driver's exporter implementation. The probe stopped before
scatter writes, repeated-page remapping or subsequent scatter-related GPU
checks, and completed cleanup.

The existing reims file-offset alias contract cannot use this FD as an ordinary
page-addressable backing without another qualified mapping path. See
[MEMORY-PATHS.md](../../MEMORY-PATHS.md) for the runtime boundary.

Captured evidence: [opaque-producer-v2.jpg](opaque-producer-v2.jpg).

## Moving an already verified CPU page: PASS

The [v3 follow-up](../../experiments/opaque-move-v3/README.md) tested an
alternative to requesting a nonzero FD mapping offset. It used the exact
executable SHA-256
`987d6950f1654753dab838c41b02d5072872bd8a5ab7f4b6681b1427f83eeb30`, verified
on the phone, with `--move-page` and a 30-second process limit.

After the existing Vulkan and native-map phases passed, it created a separate
full offset-zero mapping of the same allocation and verified all 8,192 words.
It then moved page 5 from that disposable mapping into a fresh one-page
reservation using equal old/new sizes and `MREMAP_MAYMOVE | MREMAP_FIXED`.
Both Vulkan maps and the earlier full native map remained intact.

All new phases passed:

| Check | Actual root result |
|---|---|
| Full disposable source mapping | All 8,192 words matched before the move |
| Equal-size page move | Returned the requested destination |
| Moved page's initial contents | All 1,024 words matched page 5 before any writes |
| CPU writes through moved page | Visible in all three canonical CPU views and independent GPU readback |
| Unselected guard pages | All seven preserved; every canonical check covered all eight pages |
| GPU writes through the canonical buffer | Visible through the moved page and all canonical CPU views |
| Cleanup | Released the five-page source prefix, two-page suffix and moved destination; left the vacated hole untouched |

The final output was `CPU_MOVE_PAGE_ROUNDTRIP=PASS`, `RESULT=PASS`, and
`opaque_v3_move_exit_code: 0`. No timeout or crash occurred. The host fixture
had separately checked that cleanup preserves an independent mapping placed
in the vacated source hole and refuses cleanup after a failed fixed move.

This provides a working alternative for **one moved CPU page** on the retained
32 KiB allocation. It does not make direct FD offsets work. Repeated or
scattered moved CPU views, forced refault behavior, arbitrary scattered GPU
resources, large allocations and runtime integration remain untested. The GPU
continued to access the same canonical contiguous buffer throughout.

Captured evidence: [opaque-move-v3-root.jpg](opaque-move-v3-root.jpg).

## Ordinary Android app: same working paths and same offset limit

The separately built [diagnostic APK](../../app-probe/README.md) was installed
into the previously absent package `com.ripthulhu.pixelpowervr.probe` and
launched through Android Activity Manager. Installation and launch both exited
0. Its SHA-256 was checked before installation and by the running app:

```text
2da38f13b10998a7fd394f265c1e2b0824c40a6f88e9f7461e005ea85b548093
```

The manifest requests no Android permissions, uses no shared UID, and is not
debuggable. Java launched the exact packaged native executables directly from
`nativeLibraryDir`; the probes were not executed from the root shell. All
three native and both shader hashes matched the frozen payload manifest.

| Context observation | Value |
|---|---|
| Run start / finish | 2026-11-21 14:16:51 UTC |
| Application UID / PID | 10441 / 3061 |
| App SELinux domain | `u:r:untrusted_app_34:s0:c185,c257,c512,c768` |
| Native query / opaque UID and EUID | 10441 / 10441 |
| Target SDK | 35 |
| Global SELinux state after run | Enforcing, checked from the root shell |

The app could not read `/sys/fs/selinux/enforce`; its report honestly records
that read as unavailable. The global enforcing state is the separate shell
observation, not a claimed app read.

| Stage | Actual app result | Exit |
|---|---|---:|
| Query reporter, requested API 1.3 | All 51 rows completed; 17 DMA-BUF rows features 0, 17 opaque-FD and 17 AHB rows features 6 | 0 |
| Tile-image ordering | Both cases passed; 1,024 pixels and zero wrong pixels per case | 0 |
| Opaque v2 Vulkan/full native-map phases | Passed the same 32 KiB allocation and CPU/GPU visibility checks | — |
| Opaque v2 direct page-offset alias | The same page-5/page-0 counterexample; stopped before scatter writes | 4 |

The Activity reported `COMPLETE: one or more capabilities unsupported`, not an
overall PASS. There was no timeout or crash. Its per-stage elapsed times were
102 ms, 102 ms and 104 ms; these are whole-process diagnostic times, not GPU
performance measurements.

This demonstrates that the successful tile and contiguous-sharing cases do
not require root in the tested app context. The equal root/app offset failure
points to the mapping contract rather than a root-versus-app access boundary.
It does not qualify the separately rebuilt ASoftware APK or solve reims' CPU
aliasing and GPU gather requirements.

The complete report remains in the diagnostic app's private `files/report.txt`
and is available through its **Copy report** button; `files/summary.txt` contains
the compact latest run. The v2 report was retained; the package was subsequently
upgraded to the v3 diagnostic described below.
Captured evidence: [full app summary](app-v2-summary.jpg) and
[compact result with matrix counts](app-v2-confirmed.jpg).

## Ordinary Android app v3: page-move PASS

The diagnostic package was upgraded from its verified v2 APK to version code
2, version name `1.1-v3`, using the same test signer. The v2 source, APK and
report evidence remain archived. The updated APK SHA-256 was checked before
installation and by the running app:

```text
16c4343fcd733c4df2a9ee024001554edebf140749866e60dab650d9ae5025f4
```

At **2026-11-21 14:30:43 UTC**, the updated app observed UID **10441**, PID
17804, and the same `u:r:untrusted_app_34:s0:c185,c257,c512,c768` domain with
target SDK 35. The query and opaque v3 child processes independently printed
UID/EUID 10441. The app verified the exact three native and two shader hashes.
The root shell separately confirmed global SELinux remained enforcing.

It ran query → tile → `opaque_fd_probe --move-page`. All three stages exited
**0**, in 101 ms, 102 ms and 105 ms respectively. Both tile cases again checked
1,024 pixels with zero mismatches. All v3 page-move phases passed, including
the 8,192-word disposable-map check, page-5 identity, seven guard pages,
independent GPU readback, GPU fill visible through the moved page, and exact
cleanup. No timeout or crash occurred.

The final app output was:

```text
stage_exit_codes query=0 tile=0 opaque_v3_move=0
PASS: query, tile ordering, and opaque FD v3 one-page move passed in ordinary app context
```

This qualifies the **one-page move mode**, not v2's different direct-offset
mapping. It still uses the canonical contiguous GPU buffer and does not test
repeated moved aliases, forced refaults, shader BDA dereferences, GPU gather,
guest-sized RAM, the real Metal runtime or an iOS boot. The reported process
times are not GPU performance benchmarks.

The installed diagnostic app and its append-only report remain available for
review. Its latest compact summary describes v3; the saved v2 summary and full
report preserve the earlier negative result. Exact source, minimal upgrade
diff, signer and payload provenance are under
[app-probe-v3/](../../app-probe-v3/README.md).

Captured evidence: [full v3 app summary](app-v3-summary.jpg) and
[compact v3 result](app-v3-confirmed.jpg).

## Kernel exporter: present

Read-only diagnostics found all of the following:

- `/dev/udmabuf` exists and is registered as device `10:258`.
- The running configuration contains `CONFIG_UDMABUF=y`,
  `CONFIG_DMA_SHARED_BUFFER=y`, `CONFIG_MEMFD_CREATE=y`, and `CONFIG_SHMEM=y`.
- UDMABUF's limits are 1,024 list entries and 64 MiB per export.
- The device node was owned by root with mode `0444` and the
  `u:object_r:udmabuf_device:s0` label.

The initial blocker is therefore the Vulkan buffer declaration, not a missing
kernel exporter. Access from other execution contexts has not been tested.
The probe's `O_RDWR` open would also need examination before assuming a
non-root process could open this read-only node, but the current run never
reached that open.

## Other observations and remaining work

`cmd gpu vkjson` exited 2 and returned:

```text
cmd: Failure calling service gpu: Failed transaction (2147483646)
```

This is a failure of Android's reporting path. The standalone Vulkan probe
subsequently queried and rendered successfully. Neither known installed-app
GPU-check log location contained a file.

Browser control was restored after the original session's export interruption.
The existing terminal logs remain on the phone. The JPEG files here are
unmodified screenshots captured through the browser tool; tables and excerpts
were transcribed from observed output, not represented as downloaded raw logs.
Diagnostic files were retained in their dedicated temporary directories. No
user files were removed.

The app's GPU support check remains unchanged. The successful tile and
contiguous-memory tests are prerequisites. The runtime still needs a qualified
memory path, compiler/runtime device execution and integration before these
results can be treated as iOS GPU support.

## References

- [Khronos: external-buffer query](https://docs.vulkan.org/refpages/latest/refpages/source/vkGetPhysicalDeviceExternalBufferProperties.html)
- [Khronos: external-buffer input contract](https://docs.vulkan.org/refpages/latest/refpages/source/VkPhysicalDeviceExternalBufferInfo.html)
- [Khronos: external-memory properties](https://docs.vulkan.org/refpages/latest/refpages/source/VkExternalMemoryProperties.html)

## Real Metal compiler/runtime: PASS under root

The [runtime probe](../../experiments/runtime-probe/README.md), raw SHA-256
`0291f97791c1b6f84c12a31a6213573f35d45c308ce306cca1505a06932b89f4`,
was reconstructed from fork commit
`a06a07c861751a6c24d57d141e22c28ce166fe32`. Both the complete compressed
payload and raw executable were SHA-256 verified on the phone before execution.
The runtime source base is `ffda2ffd9485b6796ad8ca49bc024bf97401342c`;
the experiment adds a standalone executable, without altering its normal device
feature discovery or the application's support gate.

Each invocation created a new empty shader cache. Embedded input AIR bitcode
was parsed and translated into SPIR-V on the Pixel, followed by actual Vulkan
pipeline creation and execution through the runtime's public Metal APIs.
Requested Vulkan API was 1.3. The real enabled set reported buffer-device
addresses, dynamic rendering and tile-color reads; ROAA and pixel interlock
were false. No validation layer was enabled on the phone.

### Producer-backed Metal compute

`--producer` completed with `RESULT=PASS`, exit 0. It created a 32 KiB
coherent allocation using memory type 1, exact runtime usage `0x201ff`,
exported its actual OPAQUE_FD and adopted the bound buffer. Three real
`scale_and_offset` compute dispatches each processed 64 elements. Their execution
records contained the compiled 680-word SPIR-V program.

The canonical baseline, independent GPU readback, full native offset-zero view,
and moved page all agreed. CPU input through the moved page reached the shader;
a subsequent shader dispatch wrote back to that same moved page. Full-span
checks compared all **8,192 words**, including the untouched guards and tails;
the moved view check compared **1,024 words**. Cleanup completed before exit 0.

This is real compiler/runtime execution over a small contiguous GPU buffer.
The adopted buffer used `AddressPlacement::Any`; explicit reims placement,
shared backing ownership, overlapping GPU resources and full guest RAM remain
separate integration requirements.

Evidence: [runtime-producer-root.jpg](runtime-producer-root.jpg).

### Translated floating-point framebuffer fetch

`--tile` completed with `RESULT=PASS`, exit 0. The runtime translated the
owned 5,040-byte vertex AIR and 4,944-byte framebuffer-fetch fragment AIR.
Actual render execution records showed float tile attachment 0, and the
recorded dynamic-rendering begin/end counts matched the draw counts.

| Case | Clear value | Draws | Explicit barriers | Expected R32Float | Pixels checked | Wrong |
|---|---:|---:|---|---:|---:|---:|
| 0 | 1.0 | 2 | No | 0.25 | 1,024 | 0 |
| 1 | 0.75 | 3 | Yes | 0.09375 | 1,024 | 0 |

Both cases compared exact float bits. This establishes these two translated
shader cases and their runtime render path. It does not establish full Metal
coverage, MSAA, general raster order groups, a performance target or iOS frames.
The runtime also reported its existing native floating-point policy and
render-pass splitting notes; passing these exact cases does not remove those
limitations. Ordinary-app execution subsequently passed as recorded below.

Evidence: [runtime-tile-root.jpg](runtime-tile-root.jpg).

## Native executable aliases: direct execution FAILED

The [native-alias experiment](../../experiments/native-alias/README.md) used
frozen binary SHA-256
`83ec274ef8643f2a40e5e12978560b289659fbdee4dd3c4db5fb3439513d69fe`,
verified before execution. It selected host pages 4–7 as one 16 KiB interval
inside a 32 KiB producer allocation.

Two simultaneous moved aliases passed their initial identity checks. Writes in
both directions were visible through the other alias and all canonical pages,
with four untouched guard pages. Read-only/read-write transitions passed. The
eight fixed AArch64 code bytes were verified, instruction-cache synchronization
returned, and RW-to-RX permissions succeeded.

The call to that code did **not** produce `NATIVE_EXEC=PASS`. The bounded run
ended with exit 1 and the generic signal/deadline failure marker. Its original
handler did not print the signal number or interrupted PC, so a watchdog is
consistent with the observed delay but is not yet the diagnosed cause. No
fresh child was started, and the later parent/child GPU round trips were not
reached.

This is a failed direct execution contract, despite the earlier data-alias
passes. Root access and successful `mprotect(PROT_EXEC)` are not proof of
working instruction fetch from this driver allocation. A separate CPU-only
control and interruption diagnostic are recorded below. Upstream's existing
ordinary-memory code cache is a potential native-EL0 route that still requires
correct integration and invalidation; no TCG-only boot is being substituted.

Evidence: [native-alias-root.jpg](native-alias-root.jpg).

### Instrumented follow-up and ordinary-memory controls

The separate [execution diagnostic](../../experiments/native-exec-diagnostic/README.md)
made the next observation precise. Its target alias, second alias and canonical
view all showed `52800540,d65f03c0` after the RX transition. It then received
SIGALRM 14 at 45,000 ms while still in `call_fixed_code`; the interrupted PC
equaled the target's first instruction. It exited 1 without starting a child.
This identifies the watchdog and interrupted location, not the kernel/driver
mechanism. The original failed binary remains unchanged.

The libc-only control executed the same code from both a fresh anonymous
mapping and an ordinary memfd, with post-RX byte verification. Both returned 42
and exited 0 under root. That supports testing an explicit copied-code cache
while preserving GPU-backed data; it does not prove the real native EL0 engine.

Evidence: [instrumented GPU-backed failure](native-exec-diagnostic-root.jpg)
and [ordinary CPU controls](cpu-exec-controls-root.jpg).

## Ordinary-app native controls and real Metal runtime: PASS

The [runtime diagnostic app](../../app-runtime-probe/README.md), versionCode 3 /
`1.2-runtime`, was installed as an update with the existing test signer. Its
complete APK SHA-256 was verified as
`c6f3a33e3f00b071e0ab2e6116d596519311a4bff85fbd889b84fad275e33c1c`.
It ran as UID 10441, PID 12850, in
`u:r:untrusted_app_34:s0:c185,c257,c512,c768`. The app requested no permissions
and launched its verified native payloads directly. Global SELinux was Enforcing
when read from the root shell; the app itself could not read that node.

| Stage | Exit | Complete process duration |
|---|---:|---:|
| Fixed native code from anonymous memory | 0 | 108 ms |
| Fixed native code from ordinary memfd | 0 | 103 ms |
| Actual Metal producer compute | 0 | 607 ms |
| Actual Metal floating-point tile fetch | 0 | 311 ms |

The app reported overall PASS, finishing at `2026-11-21T15:21:33Z`. These
durations include diagnostic process startup and checks; they are not GPU
benchmarks or predictions of guest boot speed. Each runtime invocation used
a fresh shader cache. The CPU controls executed fixed AArch64 instructions;
they did not start QEMU's native EL0 engine. The Metal binary used the existing
Any-placement wrapper, not the newer optional adoption-descriptor patch.

Evidence: [runtime-app.jpg](runtime-app.jpg) and
[runtime-app.json](runtime-app.json). The original append-only report and a
copy of the completed summary remain in the diagnostic's own phone directories.

## Combined CPU-memory and copied-code attempt: recovered kernel panic

The separate [native code-cache diagnostic](../../experiments/native-code-cache/README.md)
was built and independently reviewed before transfer. Both its complete gzip
and raw executable hashes were verified on the Pixel; raw executable SHA-256:
`52857d6a36c24827dfbfdb75c9b849e85513d8b55b000050c9bbfd9140e968f8`.
Its `--native-code-cache` command was issued with a 65-second outer timeout,
a 60-second internal process limit, and five-second memory/call limits.

The first session lost Tango before an exit status or phase output was observed.
Its [original attempt record](native-code-cache-root-attempt.json) correctly
recorded an unknown outcome at that time. A later read-only recovery found
`sys.boot.reason=kernel_panic,asynchronous_serror_interrupt`. The retained
`/sys/fs/pstore/console-ramoops-0` records an SError on CPU 3, code
`0x00000000be000011`, UID 0, PID 17957, command `native_code_cac`, followed by
`Kernel panic - not syncing: Asynchronous SError Interrupt`.

The PC `0x5c60570728` and LR `0x5c60570714` uniquely match offsets `0xc728`
and `0xc714` in the frozen executable under a 16 KiB-aligned load bias
`0x5c60564000`. The call at `0xc710` enters `ldsetal` at `0xec44`; its return
address is `0xc714`. The interrupted instruction prepares the first view check,
before that check at `0xc740` and the restoring `ldclral` call at `0xc750`.
This places SError delivery immediately after this process's first aligned
atomic set call. Asynchronous SError does not prove a unique offending instruction or the
exact memory attribute. Load bias is inferred from the ELF, not recovered from
a process map.

The interrupted process had not reached its own copied-code or unaligned-access
phase. Both parent and child use the same routine, so these addresses alone do
not establish which process failed or whether earlier parent phases completed.
No combined-test pass is established. Do not repeat the coherent, uncached producer-memory
atomic test: neither its signal timer nor the outer timeout contained the
system-level error. A cached allocation is a separate candidate with explicit
CPU/GPU cache ownership requirements.

These selected pstore fields were transcribed from the live terminal screenshot;
the full raw pstore has not been exported. A subsequent continuation located
the original run directory and reverified its executable hash on the phone.
That directory contains only the binary and its two transfer files; the expected
test log was not found there or by the scoped basename search. A 3,000-byte
selected panic excerpt is now retained in a separate phone directory. Pstore
also reports PPID 17956, but the parent command was not recovered; parent/child
identity remains unknown. See the detailed
[recovery record](native-code-cache-panic-recovery.json),
[follow-up record](device-resume-followup.json), and reproducible
[ELF address check](symbolize-native-panic.py).

The reviewed experiment would keep producer data aliases GPU-backed, test
bounded CPU memory primitives, and copy each verified 16 KiB instruction image
into a new ordinary memfd before native execution. It would require 42→43→42
in both parent and fresh child plus fenced all-page GPU verification. These
are intended later phases, not observed phone results. No product backend or gate
was enabled from this attempt.

Evidence: [connection-loss screenshot](native-code-cache-unavailable.jpg) and
[attempt metadata](native-code-cache-root-attempt.json). The exact source,
build checks and host-only fixture are preserved in the separate experiment.

## Cached producer memory: basic root-shell PASS

The user uploaded both prepared ZIPs to the existing Tango folder. Their full
archive hashes and extracted payload hashes matched before execution in fresh
private directories. The default
[cached-memory diagnostic](../../experiments/cached-memory/README.md) completed
with `RESULT=CACHED_MEMORY_BASIC_PASS_ATOMICS_NOT_TESTED`, diagnostic exit 0
and runner exit 0. Its final regular-file checkpoint completed.

The observed producer allocation was 32,768 bytes, type 2, flags `0xb`:
host-visible and host-cached, without host coherence. The independent GPU
readback allocation was coherent type 1, flags `0x7`. Both parent and fresh
exec child passed ordinary aligned and unaligned 64-bit accesses with restored
bytes; producer atomic-call counts remained zero. The separate ordinary-memfd
control passed two aligned LSE calls before any Vulkan allocation existed.
The child was reaped before the final serialized GPU access, and independent
readback verified all 8,192 words of the producer allocation.

This qualifies the tested small allocation and serial handoffs under UID 0,
`u:r:ksu:s0`, SELinux enforcing. It does not qualify producer atomics, arbitrary
CPU aliases, concurrent CPU/GPU access, ordinary-app permissions, general guest
RAM, the actual QEMU provider or iOS boot. Executable snapshots were ordinary
memfd pages; the GPU allocation remained data.

The [structured result](cached-memory-root.json) identifies the frozen binary,
retained phone logs and transcribed SHA-256. The full raw log remains on the
phone and has not been retrieved or independently hashed in this checkout.

## Actual native QEMU: execution observed, TPIDRRO correctness FAILED

The original [required-native candidate](../../ios26-build/required-native/README.md)
passed its loader controls, a native-enabled `-version` control, and a paused
native-enabled QMP machine control with two vCPUs. Its first inherited-stdin
benchmark attempt ended with status 137 and no guest output under the bounded
runner. A subsequent early-execution control with file-backed serial output
and `/dev/null` stdin reached real native guest execution. A separate attempt
with `RLIMIT_FSIZE` was invalid because it also prevented creation of the
512 MiB RAM memfd; that attempt is excluded from engine diagnosis.

The final control ran the **unchanged uploaded v1 script with only stdin
redirected from `/dev/null`**. It completed in six seconds of wrapper elapsed
time, recorded 415,727 native entries and 404,036 native SVCs, and QEMU exited 0.
Both CPUs passed T6 floating-point and T10 copy checks and printed `EXIT 0`.
Both nevertheless printed:

```text
T7 tpidr=0x1234 tpidrro=0x0 MISMATCH
```

The runner correctly retained `NATIVE_MEMFD_BENCH_PASS=0` and exited 1.
Guest completion and positive native counters do not override this register
failure. Native time is aggregated over vCPUs; these counters and elapsed
values are execution evidence, not a speed comparison. The stdin-only success
narrows the earlier launch problem without identifying its exact cause.

Source and frozen-guest inspection explain the mismatch: the generic native
path can read the host's legal TPIDRRO value instead of trapping to the guest's
value. The expected values are `0xabcd0000` and `0xabcd0001`; writable TPIDR
must remain `0x1234`. The existing iOS-specific register-swap mode implements a
different ABI and is not the generic benchmark's fix. A separate opt-in
copied-code trap candidate was prepared and qualified in the subsequent run
below; this original binary's failure remains preserved.

The earlier v1 checker also had a separate completion-format defect: it expected
an unprefixed `EXIT 0` while the frozen guest emits `[cpu0] EXIT 0`. Checker v2
corrects that format and rejects nonzero exits without changing the executable.
The observed T7 mismatch remains a valid failure independently of that defect.
The later trap candidate has stricter per-CPU witnesses.

See the [structured native result](qemu-native-root.json) and the unmodified
[terminal capture](native-stdin-control-root.png). Full logs are retained in
the phone's private result directories and copied into the shared upload
folder. Those raw bytes have not been exported into this checkout; recorded
hashes are identified as phone-output transcriptions.

## Generic native TPIDRRO correction: root-shell PASS

The separately compiled [copied-code trap candidate](../../ios26-build/tpidrro-trap/README.md)
was reconstructed in a new private phone directory through an exact local
delta. All 18 transfer parts, the complete update archive and all 22 package
files verified before execution. The original binary was rechecked unchanged.
The frozen guest and its expected results were unchanged.

The strict runner and QEMU both exited 0. Both CPUs independently passed T6,
T7, T10 and completion. CPU0 read `TPIDRRO=0xabcd0000`, CPU1 read
`TPIDRRO=0xabcd0001`, and both retained writable `TPIDR=0x1234`. Each CPU
reported two native TPIDRRO emulations, with its last PC at the later T7 read,
`0x100000768`. Thus an early T0 read or a TCG-only result cannot satisfy this
qualification. The run recorded 415,536 native entries and 404,036 native SVCs,
one copied code page and two code-map requests.

The wrapper elapsed time was seven seconds. Native/wall times and counters
are retained as execution evidence, without a speed comparison. This result
belongs to UID 0 with SELinux enforcing. It does not qualify ordinary-app
QEMU, the actual producer provider, general GPU-backed guest RAM or iOS boot.
A later scoped process query found no row matching the private package path;
that is not proof of a completely reaped descendant tree.

See [qemu-tpidrro-trap-root.json](qemu-tpidrro-trap-root.json), the unmodified
[terminal capture](native-tpidrro-trap-root.png), and
[transfer provenance](../../ios26-build/tpidrro-transfer/README.md).
Complete raw logs remain on the phone. Selected output and the phone-computed
runner hash are explicitly recorded as transcriptions, not downloaded bytes.

## Combined native EL0 and cached GPU region: PASS

The [one-region native proof](../../ios26-build/native-gpu-one-region/README.md)
passed its ordinary-memfd control at 18:44:28 UTC and its GPU-backed run at
18:44:51 UTC (timestamps identify the result directories, not elapsed times).
The new QEMU executable is SHA-256
`a815e121d487c15cd9c1cec75ca6f43a48b2edf1ab42675bb9cde988b9679145`.

The GPU run used producer memory type 2, flags `0xb`, allocation 32,768 bytes,
and a 16,384-byte view at backing offset 16,384. The actual native worker read
`0x6a1b2c346a1b2c34` and produced `0x615c5026615c515d`. Six ordered, credentialed
events were saved and acknowledged. Native counters were one entry, one SVC,
two successful fills, zero injected faults, zero kicks and zero unsupported
operations. QEMU exited 0. The owner retained the leader until group shutdown
and reaped all three processes to `ECHILD` before permitting GPU readback.
The independent readback checked all 8,192 words, with only the intended
eight bytes at allocation offset 16,392 changed.

The same executable passed the existing two-CPU TPIDRRO benchmark afterward:
415,575 native entries, 404,036 native SVCs, correct T7 values, and two native
TPIDRRO emulations per CPU ending at `0x100000768`. An earlier invocation of
that runner omitted its required package argument and exited 2 at its usage
check; it launched no guest. The corrected invocation exited 0 and passed.

See [native-gpu-one-region-root.json](native-gpu-one-region-root.json) and the
unchanged [terminal capture](native-gpu-one-region-root.jpg). Complete raw
logs and a machine-readable device record remain in the recorded phone and
shared-download directories. Local result fields and phone-computed log hashes
are console transcriptions; the raw phone logs were not downloaded.

This is root UID 0 with SELinux enforcing. Producer atomics, simultaneous
CPU/GPU access, arbitrary guest workloads, app UID execution of the bridge,
and iOS 26 boot were not tested. No product GPU support gate changed.

## Reims-owned producer through native EL0: PASS

At 20:25:17 UTC, the real reims/metal2vulkan producer API passed the serialized
native/GPU handoff on this Pixel under root with SELinux enforcing. It allocated
32,768 cached, noncoherent bytes (type 2, flags `0xb`, atom 1), maintained one
runtime buffer identity, and checked all 8,192 words after upload, independent
GPU readback, and final CPU invalidation. The fixed native payload changed the
expected eight bytes at offset 16,392. All six credentialed native phases and
complete three-process reap to `ECHILD` preceded GPU reuse. Final flush,
invalidate and completed-submission counts were exactly two each.

Live native exports and CPU epochs correctly blocked conflicting handoffs;
replayed retirement and end calls returned status 17. Owner and runner exited
zero. The QEMU executable is unchanged from the earlier one-region result.
See [reims-native-gpu-root.json](reims-native-gpu-root.json), the preserved
[terminal capture](reims-native-gpu-root.jpg), and the
[source/build checkpoint](../../ios26-build/reims-producer-native/README.md).

The first attempt aborted during runtime startup when it selected a shader
cache on Android's read-only root. The corrected runner used a fresh writable
cache through the existing fallback, without changing the owner binary.
Complete raw logs for both attempts and a generated device record remain in
the phone's project download directory. Local device fields/hashes are console
transcriptions, not downloaded raw logs.

This qualifies the explicit fixed scalar handoff. General guest RAM and graphics
hooks, fragmented resources, producer atomics, concurrent native vCPUs, ordinary
app UID, suspend/resume and iOS 26 boot remain unqualified. No product GPU gate
or device security setting changed.

## Architectural counter: 38.4 MHz

The [read-only counter probe](../../experiments/counter-frequency/README.md)
read `CNTFRQ_EL0=38400000` and exited 0. The current application setup's measured
`{TIMEBASE}` path must be retained instead of the older release script's fixed
19.2 MHz. This is the architectural timer frequency, not a CPU/GPU clock speed.

Evidence: [counter-frequency.jpg](counter-frequency.jpg).
