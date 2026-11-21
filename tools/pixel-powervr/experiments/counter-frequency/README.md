# Read-only ARM64 counter-frequency probe

`counter_freq` reads `CNTFRQ_EL0` exactly once and prints the value in Hz plus
UID/EUID. It does not measure elapsed time, sleep, create timers, access the GPU,
open device files, or write configuration. Output goes only to standard output.

This is the standalone equivalent of the main app's
`Render.counterHz()` register read. It catches SIGILL as unsupported. A value
outside the app's accepted 1 MHz to unsigned-32-bit range is reported as unusable;
the probe does not guess or substitute 19.2 MHz.

| Item | Value |
|---|---|
| Target | ARM64 Android API 35, PIE, 16 KiB ELF maximum page size |
| NDK | r29, revision `29.0.14206865` |
| Native bytes | 5,688 |
| Native SHA-256 | `09541f87a6bab04e50218badff3b21d92bf77ce44d3c11ae1c5f4c4ad7fd9016` |
| Source SHA-256 | `7698ed86c0fd338f4f42660144538b888437233c27def86acce913a00504662f` |
| Gzip bytes | 2,125 |
| Gzip SHA-256 | `01d8b11244ba38b72d494ab38ac2832d189323b9bca050cf13d89192080b8e06` |

The only linked dependencies are Android `libc.so` and `libdl.so`.
`build-info.json` records the exact compile command and toolchain version;
`readelf.txt` and `disassembly.txt` record static inspection. Disassembly contains
one `MRS CNTFRQ_EL0` instruction. No phone execution was performed by this build.

After the coordinating session transfers and verifies the binary, the command
is simply the executable's path, with no arguments. Root is not required to read
the register. Exit 0 means a usable register value; exit 2 means unreadable or
unusable; exit 1 means signal-handler setup failed. A successful register read
does not establish GPU-memory aliasing or native-EL0 compatibility.

## Pixel observation, 2026-11-21

The coordinating session verified the raw binary hash on the Pixel 10 Pro XL
and ran it with a 10-second process limit from the KernelSU root terminal. The
observed output was:

```text
COUNTER_FREQ_PROBE=1 UID=0 EUID=0
CNTFRQ_EL0_HZ=38400000
RESULT=PASS
counter_exit_code: 0
```

The [terminal capture](../../results/2026-11-21/counter-frequency.jpg) records
that observation. The phone reports **38.4 MHz** for its architectural timer.
Use the current application code's measured `{TIMEBASE}` setup path. The release
0.1.6 setup script's fixed 19.2 MHz must not be carried into this Pixel build.
This register value is not a CPU or GPU clock-speed measurement.
