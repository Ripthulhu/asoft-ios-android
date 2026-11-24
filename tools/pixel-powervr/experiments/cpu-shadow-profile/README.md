# Pixel CPU-shadow scan measurements

Two eight-second userspace profiles of the guarded iOS boot had zero lost samples. The sampled addresses in the QEMU binary with SHA-256 `4935a63011f2e4f7cb0639cd4e4f520fffba1ded6e157e53a7389b22c964a3ae` disassembled to the byte-by-byte scan that detects changes in the coherent Vulkan mapping after GPU completion.

| Profile | Samples | Share in the scan |
| --- | ---: | ---: |
| Early boot | 1,225 | 28.65% across the two hottest instructions |
| After 16.9 GB of cumulative CPU-shadow uploads | 2,020 | 32.92% across the three hottest instructions |

`scan-vulkan.c` isolates that loop on the Pixel's PowerVR DXT-48-1536 MC1 using 8 MiB of host-visible, host-coherent memory without host caching (`memory_flags=0x7`). It uses the 1 MiB canonical chunk size and changes eight bytes per 16 KiB. Each trial matches the scalar and block scan signatures. The equivalent Rust software test matches every changed range directly.

| Phase | Median of five trials |
| --- | ---: |
| Read from the ordinary file | 2.69 ms |
| Copy into the Vulkan mapping | 0.55 ms |
| Scalar scan | 453.68 ms |
| 64-byte block scan | 12.96 ms |

The fixture submits no GPU work and measures no fence wait or guest boot time. The renderer's `METAL2VULKAN_CPU_SHADOW_TIMING=1` option records file reads, upload copies, the elapsed interval from upload readiness to the start of scatter, and the scan and writeback in the actual runtime. The readiness interval includes queueing and completion handling.

Build the fixture with NDK LLVM and run it on the Pixel.

```sh
clang --target=aarch64-linux-android35 -O3 -Wall -Wextra -Werror scan-vulkan.c -lvulkan -o scan-vulkan
adb push scan-vulkan /data/local/tmp/scan-vulkan
adb shell 'chmod 700 /data/local/tmp/scan-vulkan && su -c /data/local/tmp/scan-vulkan'
```

## Relinked engine check

[Android build 45301079959](https://github.com/Ripthulhu/asoft-ios-android/actions/runs/45301079959) produced QEMU SHA-256 `af520234007161c8ba2c40bfd4e2bf10e1c45044ba29effe8772be243de54216`. The Pixel passed the loader check and both native EFI GPU fixtures, including the iOS TPIDRRO mode. Each fixture verified two 64 × 64 frames and reaped its process tree.

Timing enabled on the same runs produced four completed 16 KiB epochs. File reads ranged from 8.9 to 12.8 µs, upload copies from 0.78 to 1.22 µs, and upload readiness to scatter from 1.98 to 3.93 ms. These small fixtures exercise the reporting and rendering path. The complete iOS boot is the workload for measuring the end-to-end change.
