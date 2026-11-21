# Native EL0 access to one cached GPU region

**Passed on the Pixel 10 Pro XL under root, with SELinux enforcing, on 2026-11-21.**
The [device record](../../results/2026-11-21/native-gpu-one-region-root.json)
identifies the exact binaries, memory type, six native events, native counters,
complete descendant reap, independent GPU readback and register regression.
See the [build checkpoint](../../ios26-build/native-gpu-one-region/README.md)
for the QEMU patch and frozen artifact identities.

This experiment connects the actual QEMU native worker to a 16 KiB view of a
32 KiB cached PowerVR allocation. Vulkan fills all eight host pages with known
values. A fixed native EL0 payload reads an aligned 64-bit input, rotates and
XORs it, adds a constant, and writes one aligned 64-bit result. After QEMU exits
and the owner reaps every descendant, an independent GPU copy/readback verifies
all 8,192 words, including the unchanged surrounding data.

Code, stack, page tables, trap frames, counters and process-control state stay
in ordinary memfd or anonymous memory. The code page contains nine instructions
through its completion SVC, followed by an unexecuted BRK guard and explicit
zero padding. Its complete 16 KiB hash is pinned. The guest's EL1 setup and
shutdown use TCG; the target EL0 payload must use the actual native worker.

## Components

| File | Purpose |
| --- | --- |
| `owner.c` | Cached Vulkan owner, explicit memfd control, clean QEMU environment, fork/exec, serialized GPU handoffs |
| `owner_control.h` | Exact event validation, per-message credentials, durable ACKs, private-group shutdown and subreaper closure |
| `native_gpu_protocol.h` | Shared 256-byte wire format, geometry, fixed instructions and expected scalar transform |
| `guest.S`, `guest.ld` | One-CPU EL1 setup and the fixed native EL0 payload |
| `owner_fixture.c` | Actual host sockets, forks, corrupt/replayed records, deadline/reap failures and owned memfd mapping checks |
| `engine_host_checks.py` | Extracts actual engine guard functions and checks accepted/rejected code, fill, trap and completion shapes |
| `build.py` | Android owner/guest builds, static analysis, payload hash/disassembly and host fixtures |
| `package.py` | Frozen full package and delta against the previously qualified TPIDRRO package |
| `run-one-region.sh` | Package verification and retained one-shot phone run |
| `collect-device-evidence.py` | Copies completed logs into the phone's existing project evidence directory; launches no test |

The owner includes the frozen cached diagnostic's Vulkan implementation under
a renamed legacy entry point. It calls only its allocation, cache-maintenance,
fill, readback and successful-cleanup functions. The old entry point, copied-code
experiment and producer-atomic paths are removed by linker section GC; the
build checks their absence. The frozen diagnostic itself is unchanged.

## Build

Use Android NDK r29 and the reconstructed QEMU baseline described in the build
checkpoint. Build the owner and guest into a separate output directory:

```sh
python3 build.py --ndk /path/to/android-ndk-r29 --out /path/to/owner-build
python3 engine_host_checks.py --source /path/to/patched-qemu --out /path/to/owner-build
```

`package.py --help` lists the required frozen baseline package, QEMU source,
QEMU build, owner build and fresh output-directory inputs. Packaging verifies
the source/build identities and reconstructs every target file locally before
producing a transferable update. It never executes QEMU. The `.zst` delta is
explicitly non-executable: zstd otherwise propagates input modes to its output.
The installer's rejection of executable unverified decoder output remains active.

## Phone invocation

The verified package is isolated under `/data/local/tmp`; it does not replace
the installed app or engine. Run the ordinary-memory control first:

```sh
/system/bin/sh /path/to/package/run-one-region.sh --memfd-control
```

Only after that exact control passes, run the GPU proof:

```sh
/system/bin/sh /path/to/package/run-one-region.sh --gpu
```

The runner verifies every frozen file, creates a fresh result directory and
redirects the owner to a retained regular log with `/dev/null` stdin. It checks
the owner's exit, all six events, the guest's completion marker, complete
descendant reap and the exact final result. The owner has a 45-second process
budget, a 15-second engine budget, a 3-second reap budget and 5-second GPU fence
waits. Kernel/interconnect failures cannot be contained by userspace deadlines.

The ordinary memfd control passed, followed by
`RESULT=NATIVE_GPU_ONE_REGION_SCALAR_PASS`. The new engine then passed the
existing two-CPU TPIDRRO runner, invoked with its required package argument.

## Evidence boundary

This is a scalar, one-region, serialized root-shell result. Producer atomics,
concurrent CPU/GPU access, general guest RAM, arbitrary offsets, dynamic
invalidation, ordinary-app execution of this bridge and iOS 26 boot remain
unqualified. The producer stays NX. There is no uncached fallback and no
`--cpu-atomics` entry point. Product GPU gates and device security settings are
unchanged.
