# Opaque-FD one-page move experiment (v3)

**The frozen executable in this directory passed on the Pixel 10 Pro XL as
root and in an ordinary Android app on 2026-11-21, with exit status 0 and no
timeout.** See the
[device results](../../results/2026-11-21/README.md) and the machine-readable
[device-validation.json](device-validation.json).

This is a separate manual experiment. The kit's default v2 probe, automatic
runner and existing v2 APK retain their original payloads. The separate v3 APK
passed at `2026-11-21T14:30:43Z` with UID/EUID 10441 in the
`untrusted_app_34` SELinux domain (target SDK 35). Its query, tile and move
probes all exited 0; every move-phase check below passed in that app context too.

## Run the tested path

```sh
chmod 755 opaque_fd_probe
timeout 30 ./opaque_fd_probe --move-page
```

Use `--move-page` to select this experiment. With no option, the executable
follows v2's original offset-scatter sequence. `--no-fd-mmap` selects only the
Vulkan allocation/import and CPU/GPU baseline.

| Frozen executable | Value |
|---|---|
| File | `opaque_fd_probe` |
| SHA-256 | `987d6950f1654753dab838c41b02d5072872bd8a5ab7f4b6681b1427f83eeb30` |
| Size | 36,344 bytes |
| Target | Android ARM64, API 35, NDK r29 |
| ELF load alignment | 16 KiB |
| Shared libraries | `libvulkan.so`, `libdl.so`, `libc.so` |

## Observed root and ordinary-app results

The existing Vulkan producer/importer and full native offset-zero mapping
phases passed first. The new phase then completed all of these checks:

| Check | Observed result |
|---|---|
| Separate disposable full mapping | All 8,192 words verified before moving anything |
| Equal-size move of source page 5 | `mremap` returned the owned destination |
| Initial moved-page contents | All 1,024 words matched page 5 before writes |
| Moved-page CPU writes | Both Vulkan mappings and the retained full native mapping matched across all eight pages, including seven guards |
| Independent GPU readback | Passed |
| GPU fill back to the moved page | All 1,024 words matched |
| Cleanup | Retained source prefix, source suffix and destination released; vacated source hole excluded |
| Final outcome | `RESULT=PASS`, exit 0, no timeout |

The result establishes the tested **CPU page movement and visibility** path
over the retained contiguous Vulkan allocation. It does not establish arbitrary
CPU scatter, repeated moved aliases, forced page refaults, a scattered GPU
buffer, guest-sized memory, runtime integration or iOS boot.

If the native move path is unsupported, exit **5** reports
`RESULT=VULKAN_FD_MMAP_PASS_CPU_MOVE_UNSUPPORTED`. A failed fixed move may
already have unmapped its destination; the probe immediately exits without
attempting uncertain mapping cleanup. Mismatches after moved-page writes begin
are failures, exit 1. See [DESIGN.md](DESIGN.md) for the exact checks, ownership
rules and primary Linux/Vulkan references.

## Source, build and validation records

The executable, sources, helper, fixture, build script, design and original
host-validation files are copied byte-for-byte from the tested v3 build.
`SHA256SUMS` covers the executable and build inputs. `ARCHIVE-SHA256SUMS` covers
all sixteen frozen files. This README and `device-validation.json` record the
later phone result separately.

The frozen `build-info.json` and `validation.json` predate the phone run and
therefore retain their original pending-device text. The current device status
is in `device-validation.json` and the linked results page.

```sh
sha256sum -c SHA256SUMS
sha256sum -c ARCHIVE-SHA256SUMS
python3 build.py --ndk /path/to/android-ndk-r29
```

The build script targets Linux hosts and writes its outputs into this directory.
Use a separate copy if preserving the frozen metadata during a rebuild.

The exact shared helper passed its ordinary-memfd host fixture, including
seven guard pages, a reused source-hole sentinel that survived cleanup, and a
real failed-move child that refused uncertain cleanup. To run that CPU-only
fixture:

```sh
cc -std=c11 -O2 -Wall -Wextra -Werror cpu_move_fixture.c -o /tmp/pixel-cpu-move-fixture
/tmp/pixel-cpu-move-fixture
```

The NDK build used `-Wall -Wextra -Werror`; Clang static analysis produced no
diagnostics. An independent source review found no blocking issue. Software
Vulkan with the Khronos validation layer passed the Vulkan baseline, then
stopped at its opaque-FD metadata check with exit 3 before native writes or the
move. That software run did not qualify the moved-page GPU round trip; the
physical phone result above supplies that evidence.

Host executables, transfer encodings and toolchains are not included.
