# Pixel 10 Pro XL: ordinary-app test, 2026-11-21

The frozen app probe installed and launched successfully through Android's
Activity Manager. The native tests then ran as children of the ordinary Android
app. This note records the actual phone results reported by the coordinating
device session, which owns the original report inspection and screenshots in
the main [device-results directory](../results/2026-11-21/).

## Artifact and execution identity

| Field | Observed value |
|---|---|
| Phone | Pixel 10 Pro XL |
| Run timestamp | `2026-11-21T14:16:51Z` |
| Probe sequence duration | Approximately 0.3 seconds |
| App package | `com.ripthulhu.pixelpowervr.probe` |
| Target SDK | 35 |
| Application UID | 10441 |
| Application SELinux domain | `u:r:untrusted_app_34:s0:c185,c257,c512,c768` |
| Native query UID/EUID | 10441 / 10441 |
| Native opaque v2 UID/EUID | 10441 / 10441 |
| APK bytes | 53,923 |
| Installed APK SHA-256 | `2da38f13b10998a7fd394f265c1e2b0824c40a6f88e9f7461e005ea85b548093` |
| Opaque v2 payload SHA-256 | `f5fb47f842632a196aad9441ce1cc25d313dea2dd5b274d57b43662e0d97c59a` |

The phone-side APK checksum matched the frozen build. The manifest requests no
permissions and the app is not debuggable. Java launches the unchanged native
PIE binaries directly from Android's installed `nativeLibraryDir`; no root
shell executes the probes. ADB/root provides the control and report-reading
channel; the observed app and native UIDs establish the execution context of
the tests themselves.

## Phase results

| Stage | Result | Evidence |
|---|---|---|
| Vulkan capability query, API 1.3 | Exit 0 | Query completed under native UID/EUID 10441. |
| Tile ordering: same draw | PASS | 1,024 pixels checked; zero wrong pixels. |
| Tile ordering: across draws | PASS | 1,024 pixels checked; zero wrong pixels. |
| Tile probe overall | Exit 0 | Both ordering checks passed. |
| Opaque FD Vulkan phase | PASS | Producer-owned export/import and Vulkan round-trip checks passed. |
| Full native FD mapping | PASS | Full offset-zero mapping and its round-trip checks passed. |
| First CPU scatter offset check | Unsupported | A mapping requesting source page 5 returned page 0's test value at word 0. |
| Opaque v2 overall | Exit 4 | `VULKAN_FD_MMAP_PASS_CPU_SCATTER_UNSUPPORTED`. |
| App overall | COMPLETE, unsupported capability | The harness retained the earlier successful phases and did not label the run all-PASS. |

The offset-content mismatch was:

```text
requested source page: 5
word:                  0
observed value:        0x7b620000
expected value:        0x7b620005
```

The probe stopped before scatter writes. It did not proceed to the later CPU
scatter-write, repeated-page remap, or associated GPU-readback phases after this
content check rejected the mapping. Exit 4 therefore does not invalidate the
earlier successful Vulkan or full offset-zero native-mapping checks.

## What this establishes

The tested ordinary app context supports the capability query, both tile-image
ordering cases, and this producer-owned opaque-FD Vulkan/full-native-mapping
baseline. Moving those tests from the root shell to an ordinary app UID did not
introduce a new failure in the observed successful phases.

The first CPU offset-content check reproduced the earlier root-run limitation:
requesting page 5 exposed page 0's test pattern. This run does not establish a
working CPU scatter/remap path. It also does not test full iOS GPU integration,
arbitrary existing guest-page import, or sparse GPU aliasing. These conclusions
apply to the exact recorded APK, native probes, phone and driver state.

## Reports and build provenance

The Activity writes the latest compact result to private `files/summary.txt`
and appends complete native output to private `files/report.txt`:

```text
/data/user/0/com.ripthulhu.pixelpowervr.probe/files/summary.txt
/data/user/0/com.ripthulhu.pixelpowervr.probe/files/report.txt
```

This device-test note is separate from [dist/build-info.json](dist/build-info.json).
That file records the build-time state, including that hardware execution was
not performed by the build. It remains unchanged, as do the APK, Java source,
manifest, payloads, signature verification record and `dist/SHA256SUMS`.
