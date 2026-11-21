# Backend integration boundaries

These notes describe the source inspected and what the probes can justify.
They do not declare Pixel GPU support.

| Repository | Branch inspected | Commit |
|---|---|---|
| `alpersamur3/asoft-ios-android` and `Ripthulhu/asoft-ios-android` | `main` | `b9b930d6d4771daa0c5e2df6104ff45e2567da2d` |
| `alpersamur3/metal2vulkan` | `asoft-android` | `5951098336923a231a011578d8722449a3981034` |
| `alpersamur3/reims-vgpu` | `asoft-android` | `3e0467e64b4c21b6087ae3589388fec5154fb0cb` |

## Framebuffer ordering

The reported Pixel PowerVR driver lists `VK_EXT_shader_tile_image`. That offers
a third candidate for color framebuffer reads alongside the renderer's existing
rasterization-order attachment access and fragment-interlock paths. It is not
an alias for either extension. Khronos specifies ordered coherent reads and
requires dynamic rendering for tile-image access.

At the pinned source, `FragmentCaps` knows ROAA and pixel interlock, the color
lowering uses input attachments or storage images, and the runtime uses legacy
render passes. Supporting tile images requires coordinated changes:

- Add the real feature to device requirements, query chains, logical-device
  enablement, and capability derivation. An advertised extension is not enough.
- Add a third lowering in `lower/fragment/color.rs`. It uses `TileImageEXT`
  storage, `TileImageDataEXT`, attachment `Location`, and
  `OpColorAttachmentReadEXT`. It needs neither an input-attachment descriptor
  nor a noncoherent execution mode.
- Represent the operation in the typed IR, builder, serializer and requirement
  checks. Carry tile-read requirements in pipeline metadata and cache identity.
- Create compatible pipelines with `VkPipelineRenderingCreateInfo` and execute
  them with dynamic rendering. Audit attachment transitions, split passes,
  secondary command buffers and any graphics pipeline library path.
- Preserve existing precision conversions, sample semantics and established
  renderer paths. Qualify further formats and MSAA before claiming them.

A color tile read does not implement Metal raster-order groups for arbitrary
storage images or buffers. Passing the authored single-sample probe therefore
supports this specific integration, not blanket ordering support.

## Shared memory

The upstream change
[`12a8a907`](https://github.com/steelbrain/metal2vulkan/commit/12a8a907bcdd3c7ae5683ee436e83e42fd6397a4)
fixes a relevant early rejection: the importer used to require the host-pointer
extension before considering DMA-BUF. The included backport adapts that
separation to the older Android fork and its `GatherSource` implementation.

The candidate can reach the existing DMA-BUF route when a source is supplied.
It does not fabricate support for importing a bare CPU pointer. Its pointer
functions are held separately so the absence of the host extension cannot
silently lead to a host-pointer Vulkan call.

Guest capability advertising is unchanged. In particular,
`SupportsResourceDetachBacking` still keys off the host-memory extension at this
revision; DMA-BUF-only support remains conservatively underreported there.

The current reims exporter resolves memfd-backed memory. However,
`LinuxVm::allocate_anywhere` and `allocate_fixed_overwrite` also create anonymous
mappings. Making the importer accept DMA-BUF-only devices does not turn those
anonymous pages into exportable memory. The guest allocation and remapping
contracts still need an audit and an appropriate memfd-backed design or another
coherent implementation.

Other remaining conditions include a compatible host-visible/coherent Vulkan
memory type, storage and shader/device-address usages, page alignment, exporter
size/list limits, cache ownership, resource lifetime, aliasing, and app-context
access. The standalone probe intentionally tests only a small part of this
contract. Its output identifies a useful first boundary; it is not an iOS boot
qualification.

Root can expose whether access restrictions are the obstacle. It cannot add a
missing kernel exporter or missing Vulkan semantics. Hardware buffers and DMA
heaps can be useful for new allocations, but importing new storage is a
different contract from sharing the pages that the guest already uses.

## Evidence required to change the application gate

Use results from the actual Pixel build to select the implementation. The
graphics and memory backends must then pass their own authored execution tests,
followed by a real iOS boot and rendering exercise. A standalone probe pass, a
successful cross-build, and unit tests each establish narrower facts. None is a
reason by itself to label this phone supported.
