# Pixel PowerVR framebuffer fetch

The 2× iOS boot aborted at a framebuffer-fetch pipeline for color attachment 0,
Metal format 550 (`RGB10A8_2P_XR10`). The descriptor enabled all four color
channels without blending on attachment 0. The other two color attachments
disabled writes, and the descriptor included a combined depth/stencil
attachment. [Boot evidence](../device-checks/recovery-20261122/macos-hfs-replay/GPU-BOOT.md)

## Tested Vulkan path

The fixture uses coherent reads from an FP16 working attachment through
`VK_EXT_shader_tile_image`. It performs four overlapping read-modify-write
operations per pixel in a single dynamic rendering pass. Both primitives
in a final draw fail the depth test. The other two color attachments keep
their original values. The host checks every channel of every pixel as
exact FP16 bits. [Vulkan extension](https://docs.vulkan.org/features/latest/features/proposals/VK_EXT_shader_tile_image.html)

| Pixel 10 Pro XL test | Process exit | Mismatching pixels |
| --- | ---: | ---: |
| Coherent tile fetch with depth/stencil | 0 | 0 |
| Replace tile read with the original clear value | 1 | 256 |
| Let both depth-rejected primitives pass | 1 | 256 |

The system PowerVR D-Series driver reported color tile reads, accelerated
coherent tile reads and independent blend state. The passing run checked
256 pixels on all three color attachments.

| Passing binary or shader | SHA-256 |
| --- | --- |
| `tile_fetch` | `34ea7d748b94d089805d9333590b7654f8143568fa0320e1f4bac56b92a178af` |
| `feedback.vert.spv` | `f03bddb629d7e7e8d420c398ea0b5e7e9f335b29d13c7b0768ff3bf557ccc835` |
| `feedback.frag.spv` | `5b09026dc894c902f5f361af00397c654baf3f40101d8c8cc26bfa740df804f2` |

## Build and run

Build the fixture with an installed Android NDK and Python 3. The phone run
used NDK 30.0.14904198 and a 16 KiB-aligned arm64 executable. The build
accepts the NDK's older SPIR-V assembler by checking the temporary
instruction encoding before replacing it with the tile-read opcode.

```sh
python3 build_fixture.py /path/to/android-ndk /path/to/output
adb push /path/to/output/tile_fetch /path/to/output/*.spv /data/local/tmp/
adb shell 'cd /data/local/tmp && chmod 700 tile_fetch && ./tile_fetch feedback.vert.spv feedback.frag.spv'
```

The two negative controls are `negative.frag.spv` in place of
`feedback.frag.spv`, and `negative-depth.vert.spv` in place of
`feedback.vert.spv`. Each should produce 256 mismatches.

## Renderer integration

The fixture verifies the ordered FP16 read and write path on this GPU.
Integration still needs the renderer to choose it for the supported
pipeline shape, hold the FP16 attachment across the pass and use the
existing XR decode and quantization code at load and store. The upstream
runtime already models FP16 tile values through a different ordering path.
The fixture contains no iOS shader, firmware or disk image.
[Upstream shadow implementation](https://github.com/alpersamur3/metal2vulkan/blob/asoft-android/crates/metal2vulkan-runtime/src/render/extended_shadow.rs)

The phone build pins metal2vulkan `51c322d883ea723d290c931b3b2013c50f5e4934`.
The pinned checkout was unavailable during this test. The installed
renderer and iOS boot still need integration and verification.
