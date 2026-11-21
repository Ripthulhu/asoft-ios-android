# Vulkan-owned opaque-FD experiment

`bin/opaque_fd_probe` tests whether new Vulkan-owned memory can provide coherent
CPU views, GPU access, and native CPU aliases. It is a separate allocation
strategy from importing existing guest pages through UDMABUF. A pass does not
implement that allocation strategy in ASoftware or establish an iOS boot.

The current executable identifies itself as **version 2**. It adds bounded CPU
scatter/remapping checks to the original export/import and full-map experiment.
Device observations belong in the [results record](results/); build metadata
records the exact executable and source hashes. `run.py` still runs only its
original tile-image and DMA-BUF probes; this is a manual follow-up.

**Observed Pixel result:** v2 passed its Vulkan and full native-map phases in
root and ordinary-app contexts, then returned exit 4 when the first direct
page-offset alias exposed page 0 instead of page 5. The separate
[v3 move experiment](experiments/opaque-move-v3/README.md) successfully moved
one verified page from a disposable full mapping, including CPU/GPU visibility
and exact cleanup, in both contexts. It does not replace or change this v2
executable's direct-offset test.

## Run manually

Close any running iOS session. Use an existing authorized ADB connection and
select the intended phone with `-s` if necessary. From this package directory,
verify the local payloads before transfer:

```sh
sha256sum -c SHA256SUMS
adb shell mktemp -d /data/local/tmp/pixel-opaque-fd.XXXXXX
```

Replace `RUN_DIR` below with that exact newly created directory. Compare the
phone's checksum with the `bin/opaque_fd_probe` entry in `SHA256SUMS` before
executing:

```sh
adb push bin/opaque_fd_probe RUN_DIR/opaque_fd_probe
adb shell sha256sum RUN_DIR/opaque_fd_probe
adb shell chmod 0755 RUN_DIR/opaque_fd_probe
adb shell 'id; timeout 30 RUN_DIR/opaque_fd_probe; result=$?; echo opaque_exit_code=$result; exit $result'
```

Record `id` and the complete output. A root-context test through an already
authorized `su -c` session must be labelled as root. It does not establish that
the same operations work inside an ordinary Android application. Save the
report before removing only this run's temporary directory.

The default runs every phase that its preceding checks permit. `--no-fd-mmap`
runs only the Vulkan baseline and skips both native-mapping phases.

| Exit | Meaning |
|---|---|
| 0 | All requested phases passed. Check whether native phases were explicitly skipped. |
| 1 | API, data, or GPU submission/fence failure. Stop further GPU tests and inspect the output. |
| 2 | A required Vulkan or memory-class capability is unavailable. |
| 3 | Vulkan baseline passed; the tested full native FD mapping is unavailable. |
| 4 | Vulkan and full native mapping passed; CPU offset mapping or remapping is unavailable. |

## What the Vulkan phase checks

The probe requests Vulkan 1.3 and checks OPAQUE_FD import/export support for the
runtime's ordinary-buffer usage `0x1ff`. If buffer device address is advertised,
it enables the feature and allocation flag and uses `0x201ff`. It creates two
identical non-sparse buffers, checks both actual memory requirements, and
selects compatible `HOST_VISIBLE | HOST_COHERENT` memory. A dedicated-only
contract or required dedicated allocation returns unsupported for this
generic-backing experiment.

It allocates new producer memory, exports that actual Vulkan allocation as an
OPAQUE_FD, and imports a duplicate using the original allocation size and memory
type. It never reinterprets a generic memfd or DMA-BUF as an opaque Vulkan
handle. It does not call `vkGetMemoryFdPropertiesKHR` for OPAQUE_FD. Vulkan owns
the duplicate only after a successful import; the original descriptor is kept
for native mappings, and the original allocation survives all dependent uses.

Both Vulkan memory objects are mapped. CPU writes through the original view
must appear through the imported view and in GPU readback. GPU fills through
the imported buffer must appear through both CPU views. Every word across
eight host pages is checked. Readback uses a third independent allocation,
avoiding a copy between overlapping aliases.

All objects belong to one Vulkan device and queue. Only the imported buffer is
accessed by GPU commands. Global HOST/TRANSFER dependencies cover the aliased
views; CPU mappings are not external queues. No artificial external ownership
transfer is used. Each submission has a five-second fence limit, with process
exit instead of unsafe cleanup if submission or waiting fails. The outer
timeout also bounds driver calls outside those waits.

Device addresses are checked for nonzero values, but no shader dereferences
them. These are ordinary bound resources, not sparse resources.

## Native CPU views

After the Vulkan baseline passes, the probe attempts a full `MAP_SHARED` view
of the retained opaque descriptor at offset zero. This is a driver-specific
observation, not a portable guarantee of the Vulkan opaque-handle contract.
The descriptor may refuse mapping or expose metadata instead of payload.

The probe compares every expected word before writing through that view. A
mapping refusal, wrong initial contents, or guarded SIGBUS reports the native
contract unavailable. It does not infer private payload offsets. If the full
comparison succeeds, it verifies native CPU writes through both Vulkan views
and GPU readback, then verifies GPU fills through all three CPU views. It does
not apply DMA-BUF ioctls to this opaque descriptor.

Version 2 then reserves four fresh CPU pages with `PROT_NONE` and maps source
pages `{5, 0, 7, 2}` into them. Every `MAP_FIXED` target is restricted to that
owned reservation, and source offsets are checked against the known canonical
buffer size. Distinct slot/page/word patterns must appear in both Vulkan CPU
views, the full native view, and an independent GPU readback of all eight
canonical pages. The four unselected pages retain their expected guard values.
GPU fills of the canonical buffer must then appear in the reordered CPU slots.

Finally, after the GPU fence completes, slot 3 is replaced: it changes from
source page 2 to source page 5. Slots 0 and 3 now share page 5. Writes through
slot 3 must appear through slot 0 and all canonical views, while old page 2
remains unchanged. GPU readback again checks all eight pages. Partial mapping
failures release only the owned reservation.

**The GPU buffer stays contiguous and canonical throughout.** A pass proves
these bounded CPU offset/repeated-alias cases around that buffer. It does not
prove a GPU buffer containing a scattered sequence of guest pages, sparse
aliasing, arbitrary guest-memory import, shader BDA access, large-window limits,
or complete backend integration. See [BACKEND.md](BACKEND.md) for integration
status and remaining requirements.

## Build and host verification

With an existing Android NDK r29 installation:

```sh
python3 build_opaque.py --ndk /path/to/android-ndk-r29
```

This builds only the opaque-FD probe, updates its checksum entry, and writes
`build-info-opaque-fd.json`. Other payloads remain untouched. When rebuilding
the whole kit, run `build.py` first, followed by `build_caps.py` and
`build_opaque.py`, so the manifest retains all manual diagnostics too.

The supplied executable targets ARM64 Android API 35 with Clang 21,
`-std=c11 -O2 -Wall -Wextra -Werror`, PIE, and 16 KiB load-segment alignment.
Clang static analysis returned no diagnostics. The memory requirements,
descriptor ownership, synchronization, cleanup, mapping bounds, and remap
expectations were independently reviewed.

The same source's Vulkan baseline passed on lavapipe with the Khronos
validation layer explicitly loaded and synchronization validation requested;
no validation errors or synchronization hazards were reported. That driver's
opaque-FD offset-zero map exposed a header, so the native-write and CPU-scatter
phases were not reached there.

The Linux host fixture uses the **same `src/cpu_alias.h` helpers** with an
ordinary memfd. It passed reordered CPU mappings, full-page guard checks,
canonical CPU writes reflected in those views, repeated-page remapping, source
and destination bounds refusals, and cleanup of a partially mapped reservation.
It verifies that the released reservation is unmapped. It tests neither Vulkan
opaque-handle semantics nor GPU execution. To reproduce that focused fixture:

```sh
cc -std=c11 -O2 -Wall -Wextra -Werror -Isrc tests/cpu_alias_fixture.c -o /tmp/pixel-cpu-alias-fixture
/tmp/pixel-cpu-alias-fixture
```

## Primary references

- [Allocation/import contracts](https://docs.vulkan.org/refpages/latest/refpages/source/VkMemoryAllocateInfo.html)
- [Opaque-FD ownership](https://docs.vulkan.org/refpages/latest/refpages/source/VkImportMemoryFdInfoKHR.html)
- [Exporting a Vulkan memory FD](https://docs.vulkan.org/refpages/latest/refpages/source/vkGetMemoryFdKHR.html)
- [Memory aliasing](https://docs.vulkan.org/spec/latest/chapters/resources.html#resources-memory-aliasing)
- [Queue-family ownership](https://docs.vulkan.org/spec/latest/chapters/synchronization.html#synchronization-queue-transfers)

The original probe and fixture code are MIT licensed.
