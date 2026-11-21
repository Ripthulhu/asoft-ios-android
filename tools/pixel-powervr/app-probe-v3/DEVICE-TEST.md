# Pixel 10 Pro XL: v3 ordinary-app PASS

The coordinating device session installed the frozen v3 APK as an update to
the known diagnostic package, launched its Activity, and inspected the app's
private report. This note records that actual result; the coordinating session
owns the original report and screenshots in the main
[device-results directory](../results/2026-11-21/).

| Observation | Value |
|---|---|
| Run timestamp | `2026-11-21T14:30:43Z` |
| Package / version | `com.ripthulhu.pixelpowervr.probe`, code 2 / `1.1-v3` |
| Application UID / PID | 10441 / 17804 |
| SELinux domain | `u:r:untrusted_app_34:s0:c185,c257,c512,c768` |
| Target SDK | 35 |
| Native query and v3 UID/EUID | 10441 / 10441 |
| Verified APK SHA-256 | `16c4343fcd733c4df2a9ee024001554edebf140749866e60dab650d9ae5025f4` |
| Opaque v3 payload SHA-256 | `987d6950f1654753dab838c41b02d5072872bd8a5ab7f4b6681b1427f83eeb30` |
| Opaque invocation | `libopaque_fd_probe.so --move-page` |

The native executables ran directly from the app's installed native-library
directory. The test execution had the ordinary app UID above, even though
ADB/root was used to control the installation and read its private report.

| Stage | Result | Exit | Whole-process elapsed time |
|---|---|---:|---:|
| Vulkan query, requested API 1.3 | Completed | 0 | 101 ms |
| Tile-image ordering | Both cases PASS | 0 | 102 ms |
| Opaque v3, `--move-page` | All requested phases PASS | 0 | 105 ms |

These elapsed values are diagnostic process durations, not GPU benchmarks.
The app reported an overall PASS for this exact sequence.

The earlier Vulkan and full offset-zero native-mapping phases passed. All
one-page-move checks also passed: verification of the disposable full mapping,
the page-5 move syscall, initial moved-page contents, writes through the moved
CPU view, all eight canonical pages including seven unchanged guards,
independent GPU readback, GPU fills visible through the moved CPU page, and
cleanup of precisely the remaining owned mapping intervals.

## Scope and retained limitation

This validates the tested single CPU-page movement and CPU/GPU visibility in
an ordinary Android app context. The GPU buffer remained canonical and
contiguous. It does not qualify repeated CPU aliases, forced page refault,
GPU scatter/gather, arbitrary existing guest-page import, guest-sized memory,
the candidate Metal runtime or iOS rendering.

V2's direct nonzero-FD-offset mapping still has its recorded page-5/page-0
counterexample. V3 uses a different operation: move one page out of a separately
verified full offset-zero mapping. This result neither repairs nor retests
the failed direct-offset route.

The latest compact result is in private `files/summary.txt`; complete output
is appended to `files/report.txt`, which can also retain the earlier v2 run.
The `1.1-v3` header and `opaque_v3_move` stage label distinguish this run.

The APK, source, manifest, payloads, build-info and checksum artifacts remain
unchanged. Their build-time record correctly says hardware execution was not
performed by the build; this separate note records the subsequent phone test.
