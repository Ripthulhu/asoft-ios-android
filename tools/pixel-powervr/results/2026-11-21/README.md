# Pixel 10 Pro XL: first physical GPU test

Date: 2026-11-21. **Ordered tile-image rendering passed. The proposed DMA-BUF
buffer import route did not pass its capability query.** No patched Android
application, integrated Metal runtime, or iOS boot was tested.

The two execution probes and their shaders were taken from app-fork commit
`046882039212433b562f662cd666611c24bd85f1`. Their hashes were checked on the phone
before execution. All four matched `SHA256SUMS`.

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

The terminal was already running as root through ADB/KernelSU. These results
are not evidence of ordinary ADB-shell or Android application-domain access.
SELinux, device-node permissions, kernel parameters, modules, and application
settings were not changed for the tests. Files were staged in one fresh
temporary directory under `/data/local/tmp`.

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

Captured terminal evidence: [tile-root.png](tile-root.png).

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

Captured terminal evidence: [dma-root.png](dma-root.png).

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

The next diagnostic is the [query-only reporter](../../VULKAN-CAPS.md), starting
with `--api 1.3` to match the candidate backend. It distinguishes smaller usage
combinations from the runtime's exact `0x1ff` / optional `0x201ff` masks, and
checks DMA-BUF separately from opaque-FD and Android hardware-buffer handles.
It never allocates GPU resources or submits work. **It has been built and
reviewed, but has not been transferred to or run on this phone.**

Browser control was lost during an attempted log export, after the two original
probes had completed. The existing terminal logs remain on the phone. The PNG
files here are unmodified screenshots captured through the browser tool; the
tables and excerpts above were transcribed from the observed output, not
represented as downloaded raw logs. The temporary probe directory was retained
because remote cleanup was unavailable. No user files were removed.

The app's GPU support check remains unchanged. A successful tile test alone is
insufficient to enable the candidate while its memory-import contract is
unqualified.

## References

- [Khronos: external-buffer query](https://docs.vulkan.org/refpages/latest/refpages/source/vkGetPhysicalDeviceExternalBufferProperties.html)
- [Khronos: external-buffer input contract](https://docs.vulkan.org/refpages/latest/refpages/source/VkPhysicalDeviceExternalBufferInfo.html)
- [Khronos: external-memory properties](https://docs.vulkan.org/refpages/latest/refpages/source/VkExternalMemoryProperties.html)
