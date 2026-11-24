# Guarded framebuffer-fetch boot on the Pixel

The original iOS 26 native boot aborted at about 83 minutes when the XR10 framebuffer-fetch shader reached a discard condition based on a tile read. The guarded renderer bypasses that discard when the fragment is already a helper invocation. Both recovered variants of `ffea2ba11gcoha4` compiled on the Pixel with the guard. The XR smoke test read back all 256 pixels exactly in each of its two passes. [Renderer change](https://github.com/Ripthulhu/asoft-ios-android/commit/c0b7c77df8df14dfe1f0c264f198469bd5c72950)

The engine carrying the guard and refusal capture is from build 45292713675. Its QEMU SHA-256 is `4935a63011f2e4f7cb0639cd4e4f520fffba1ded6e157e53a7389b22c964a3ae`. It passed the loader check and both native EFI GPU fixtures on the Pixel 10 Pro XL. The fixtures each verified two 64 × 64 frames and clean process reaping. [Engine build](https://github.com/Ripthulhu/asoft-ios-android/actions/runs/45292713675)

## Live run

- Started a fresh overlay at approximately 01:32 Amsterdam time on November 24, 2026. Native EL0 and the iOS TPIDRRO mode were required.
- First GPU frame arrived after 231 seconds of active runtime.
- At 02:36 Amsterdam time the owner reported 3,347 seconds of active runtime. Serial output was advancing, native execution and GPU execution were witnessed, and no framebuffer-fetch refusal or guest fatal marker was visible.
- The recovered result records a QEMU `SIGABRT` after 5,015 seconds of active runtime, at 03:04 Amsterdam time. The final frame matched the last sampled frame. Native EL0 and PowerVR execution were both witnessed. The wallpaper filesystem checks and APK gate remained incomplete.
- QEMU's final error was a render-pipeline format refusal on color attachment 0 for `ffgea5cia6gcoha4` (Metal format 550, `RGB10A8_2P_XR10`). The tile-fetch capture directory was empty. Two AIR variants recovered from the preserved run overlay both declare a `half4` color output at 0 and a `half2` coverage output at 1. Neither declares a framebuffer-fetch input. The descriptor state is still missing. The renderer's opt-in `METAL2VULKAN_XR_LINK_DIAGNOSTICS=1` logs the write mask, blending, alpha-to-coverage and raster sample count when this type of graphics link fails.

| Device record | Path |
| --- | --- |
| Owner log and PID | `/data/local/tmp/asoft-ff-resume-1124/boot-owner.log` and `boot-owner.pid` in the same directory |
| Run directory | `/data/local/tmp/asoft-recovered-gpu-boot-10-tile-capture` |
| Final status | `result.json` under the run directory |
| Guest output and current stage | `qemu-stderr.txt`, `serial.txt`, and `vm-result.json` |
| Last observed frame | `frame-latest.png` |
| Any new tile-fetch refusal | `tile-fetch/tile-fetch.air` and `tile-fetch/tile-fetch.spv` |

## Cached CPU-shadow device check

Build 45305727723 produced QEMU SHA-256 `6eebd917e64ae95080c2436b13e8efaff77fc4f49cbbc96c0fb47cbdd5570917`. The Pixel passed the loader check and both native EFI GPU fixtures with caching enabled and disabled. Each fixture verified two 64 × 64 frames and clean process reaping in both modes. The wrapper exports the cache and timing flags in the QEMU process because the fixture owner supplies an explicit environment.

With caching enabled, the completed 16 KiB epochs recorded 23–51 µs for cache flush, 23–37 µs for invalidation and 5.8–6.8 µs for scanning and setup. The coherent control's scan took 25–39 µs. These fixtures had zero scattered bytes. They exercise upload visibility and clean readback with real GPU work. The separate 8 MiB Vulkan scan fixture covers GPU-written bytes. End-to-end boot time with cached shadows is still unmeasured. [CPU-shadow measurements](../../cpu-shadow-profile/README.md) · [Cached-shadow build](https://github.com/Ripthulhu/asoft-ios-android/actions/runs/45305727723)
