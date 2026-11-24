# Guarded framebuffer-fetch boot on the Pixel

The original iOS 26 native boot aborted at about 83 minutes when the XR10 framebuffer-fetch shader reached a discard condition based on a tile read. The guarded renderer bypasses that discard when the fragment is already a helper invocation. Both recovered variants of `ffea2ba11gcoha4` compiled on the Pixel with the guard. The XR smoke test read back all 256 pixels exactly in each of its two passes. [Renderer change](https://github.com/Ripthulhu/asoft-ios-android/commit/c0b7c77df8df14dfe1f0c264f198469bd5c72950)

The engine carrying the guard and refusal capture is from build 45292713675. Its QEMU SHA-256 is `4935a63011f2e4f7cb0639cd4e4f520fffba1ded6e157e53a7389b22c964a3ae`. It passed the loader check and both native EFI GPU fixtures on the Pixel 10 Pro XL. The fixtures each verified two 64 × 64 frames and clean process reaping. [Engine build](https://github.com/Ripthulhu/asoft-ios-android/actions/runs/45292713675)

## Live run

- Started a fresh overlay at approximately 01:32 Amsterdam time on November 24, 2026. Native EL0 and the iOS TPIDRRO mode were required.
- First GPU frame arrived after 231 seconds of active runtime.
- At 02:36 Amsterdam time the owner reported 3,347 seconds of active runtime. Serial output was advancing, native execution and GPU execution were witnessed, and no framebuffer-fetch refusal or guest fatal marker was visible. The final boot result could not be retrieved after the session lost ADB access.

| Device record | Path |
| --- | --- |
| Owner log and PID | `/data/local/tmp/asoft-ff-resume-1124/boot-owner.log` and `boot-owner.pid` in the same directory |
| Run directory | `/data/local/tmp/asoft-recovered-gpu-boot-10-tile-capture` |
| Final status | `result.json` under the run directory |
| Guest output and current stage | `qemu-stderr.txt`, `serial.txt`, and `vm-result.json` |
| Last observed frame | `frame-latest.png` |
| Any new tile-fetch refusal | `tile-fetch/tile-fetch.air` and `tile-fetch/tile-fetch.spv` |

The block-scan optimization and instrumented engine passed their own native fixture tests. The opt-in cached-shadow engine at commit `228cfcabb359033f1ed61f6ed15e9aef0a5f00a4` built successfully and still needs its device test. The guarded live boot uses the original guarded engine so its result remains attributable to the shader change. [CPU-shadow measurements](../../cpu-shadow-profile/README.md) · [Cached-shadow build](https://github.com/Ripthulhu/asoft-ios-android/actions/runs/45305727723)
