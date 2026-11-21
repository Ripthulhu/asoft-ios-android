# Native instruction-fetch diagnosis

This separate diagnostic preserves the failed original native-alias probe.
It adds phase timing, post-RX instruction verification and bounded SA_SIGINFO
reporting (signal, code, PC/LR and selected registers), without dereferencing
fault addresses in a signal handler. Its logger and CPU control were independently
reviewed. Android static analysis reported zero diagnostics; exact source and
binary identities are in `build-info.json` and `SHA256SUMS`.

## Ordinary CPU memory: PASS under root

`cpu_exec_control`, SHA-256
`d58320129c9a2092096a12cd4acdfb0345a8936208c54b9d64f1187d3be26ca9`,
is libc-only and performs no Vulkan initialization or calls. Both modes ran on
the Pixel after checksum verification:

```sh
timeout 10 ./cpu_exec_control --cpu-exec-anon
timeout 10 ./cpu_exec_control --cpu-exec-memfd
```

Each allocated 16 KiB, wrote `mov w0,#42; ret`, synchronized I-cache, changed
RW to RX, re-read the exact bytes, returned 42, restored RW and cleaned up.
Both exited 0. Its five-second watchdog was not reached. Recorded millisecond
values are phase diagnostics, not a CPU performance benchmark.

[CPU controls capture](../../results/2026-11-21/cpu-exec-controls-root.jpg).

## GPU-backed direct code: watchdog failure under root

`native_exec_diagnostic`, SHA-256
`cb23c82536c39e3928a42b66a824c6c67d3288b1d977b622765cb34cdab9e47f`,
retains the original producer and alias sequence:

```sh
timeout 60 ./native_exec_diagnostic --native-alias
```

The target alias, second alias and canonical view all returned the exact code
words `52800540,d65f03c0` **after** RW-to-RX protection. At 155 ms the probe called
the code. At 45,000 ms it received **SIGALRM (14), si_code 128**, with phase
`call_fixed_code` and phase duration 44,845 ms. The interrupted PC
`0x7802a38000` equaled the first instruction's target address; LR was
`0x5e68fa7c30`, and x0 was `0x2f`. It exited 1. No successful return or fresh
child occurred. No individual RWX VMA or policy change was requested.

These observations isolate failure to this direct executable mapping sequence.
They do not prove its kernel/driver mechanism or establish that every possible
GPU allocation is nonexecutable. In particular, a successful data read and
`mprotect` are insufficient proof of instruction fetch. Ordinary memfd execution
works in the control, supporting a separately qualified native code-cache route.
The code cache copies executable bytes; it must not be described as direct
execution from GPU-backed pages.

[Instrumented failure capture](../../results/2026-11-21/native-exec-diagnostic-root.jpg).

No actual QEMU/native EL0 factory, guest code invalidation or iOS boot is tested.
The build helper records NDK r29/API35 inputs and emits both executables. Its
`libraries` arrays describe explicit linker flags; ELF reports contain the
complete DT_NEEDED closure. The CPU control links Android libc and libdl only.
