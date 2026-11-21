# Pixel 10 Pro XL: physical GPU tests

Date: 2026-11-21. **Ordered tile-image rendering and a Vulkan-owned, coherent
CPU/GPU allocation passed. Importing existing pages through DMA-BUF remains
unsupported. A CPU page-offset alias of the exported opaque FD did not expose
the requested page; a later one-page move from a full mapping passed.** The
successful rendering, sharing and one-page move were reproduced under an
ordinary Android app UID. No integrated Metal runtime or iOS boot was tested
in this diagnostic checkpoint.

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
settings were not changed for the tests. Files were staged in one fresh
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
