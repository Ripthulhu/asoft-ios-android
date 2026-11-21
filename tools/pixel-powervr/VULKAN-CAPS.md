# Query-only Vulkan report

`bin/vulkan_caps` is a manual follow-up diagnostic for a DMA-BUF probe that
reports an unsupported external-buffer contract. It queries the driver to
distinguish a restriction on particular buffer usages from a restriction on the
handle type. It creates a Vulkan instance and performs physical-device queries.
It creates no logical device, GPU memory allocation, resource, queue, or
submission.

**Status:** built and checked on the development host; this reporter has not
been transferred to or executed on the Pixel. It is separate from the two
execution probes. The ordinary `run.py` still transfers and checks its original
four payloads and does not run this diagnostic.

## Manual use

Use an existing authorized ADB connection, selecting the intended phone with
ADB's `-s` option when necessary. From this package directory:

```sh
sha256sum -c SHA256SUMS
adb shell mktemp -d /data/local/tmp/pixel-vulkan-caps.XXXXXX
```

Use the exact directory printed by `mktemp` in place of `RUN_DIR` below. Transfer
only after the local checksum check passes, and compare the phone's checksum
with the `bin/vulkan_caps` entry in `SHA256SUMS` before executing:

```sh
adb push bin/vulkan_caps RUN_DIR/vulkan_caps
adb shell sha256sum RUN_DIR/vulkan_caps
adb shell chmod 0755 RUN_DIR/vulkan_caps
adb shell 'id; timeout 30 RUN_DIR/vulkan_caps --api 1.3; result=$?; echo caps_exit_code=$result; exit $result'
```

For a root-context comparison, wrap the same command with `su -c` through the
existing KernelSU authorization. Record `id` with the report and label whether
the command ran as root, an ADB shell, or inside the application. Redirect output
to a file if needed; retain its exit status. Remove only the exact temporary
directory created for this run when the report is saved.

`--api 1.3` matches the candidate backend's requested version. `--api 1.4` is
accepted when the loader reports support. With neither argument, the program
requests the highest reported loader version up to 1.4. Device index defaults
to zero; choose another enumerated index with `--device INDEX`.

The focused reporter requires a Vulkan 1.3 or later physical device. Exit zero
means the queries completed, not that any import or rendering worked. Exit two
means the requested API or selected device is unavailable. Exit one reports an
error. Keep the full output, including requested API, driver, and execution UID.

## External-buffer matrix

For each advertised DMA-BUF, opaque-FD, and Android hardware-buffer handle type,
the matrix queries 17 non-sparse usage combinations. These include separate
transfer directions; storage alone and with each transfer direction; uniform,
texel, vertex, index, and indirect usages; the runtime's exact `0x1ff` usage; and
buffer-address variants including `0x201ff`. Address rows are queried only when
`bufferDeviceAddress` is advertised. Physical-device queries have no enabled
logical-device feature set; this program does not create one.

The output separates `importable`, `exportable`, and `dedicated_only` from the
compatibility and export-from-imported masks. A compatible-handle bit alone does
not establish importability. The candidate runtime requires importability
without the dedicated-only restriction. Even a qualifying row does not prove
that an actual FD can be imported with the required memory type or that CPU/GPU
sharing is coherent. A positive Android hardware-buffer or opaque-FD row does
not qualify the UDMABUF exporter's original-page DMA-BUF route.

Other output includes relevant extensions, core and tile/ROAA/interlock
features, driver information, memory types/heaps, limits, and queue families.
It does not print UUIDs.

## Rebuild and verification

No shader compiler is needed. With an existing Android NDK r29 installation:

```sh
python3 build_caps.py --ndk /path/to/android-ndk-r29
```

This builds only the reporter, refreshes its checksum entry in `SHA256SUMS`, and
writes `build-info-vulkan-caps.json`. It preserves the four existing execution
payloads. If rebuilding the complete kit, run the existing `build.py` first and
`build_caps.py` second: the former regenerates the manifest for its four files.

The supplied executable targets ARM64 Android API 35, built with NDK r29
(29.0.14206865), Clang 21, `-std=c11 -O2 -Wall -Wextra -Werror`, PIE, and 16 KiB
ELF load-segment alignment. The metadata records source and executable hashes.
NDK r29 has Vulkan 1.3 headers; API 1.4 negotiation uses the standard version
encoding, while every command called is core 1.1 or earlier.

Clang static analysis returned no diagnostics. A native host build of the same
source completed all 51 matrix queries under requested API versions 1.3 and 1.4
using lavapipe with the Khronos validation layer explicitly loaded; no
validation error was emitted. That host advertised neither the tile-image
extension nor fragment shader interlock, so those feature-query branches have
source review and compilation coverage rather than host execution coverage.
Host results are not Android or PowerVR capability evidence.

The binary's imported Vulkan symbols were checked against the instance and
physical-device query allowlist. Existing probe binaries and shaders were kept
byte-for-byte unchanged.

## Specification references

- [External-buffer query inputs](https://docs.vulkan.org/refpages/latest/refpages/source/VkPhysicalDeviceExternalBufferInfo.html)
- [External-memory feature and compatibility masks](https://docs.vulkan.org/refpages/latest/refpages/source/VkExternalMemoryProperties.html)
- [External-buffer query command](https://docs.vulkan.org/refpages/latest/refpages/source/vkGetPhysicalDeviceExternalBufferProperties.html)

The original reporter source is MIT licensed, as are the other probes.
