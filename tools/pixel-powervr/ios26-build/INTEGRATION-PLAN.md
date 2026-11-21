# Pixel iOS 26 application and build integration plan

This is a proposed route based on inspected source and recorded device probes.
It does not claim that the application or an iOS guest has booted on this Pixel.
No main app source changes or device actions were performed for this plan.

## Current boundary

The phone's ordinary test app has passed the standalone tile-read and
producer-allocation/full-map/one-page-move probes. Direct nonzero FD offsets
still return the wrong page. That distinction is essential: a one-page move
does not implement arbitrary reims gathers, shared writable view lifetimes,
guest RAM allocation, or native EL0's cross-process mappings.

Later root and ordinary-app tests passed actual Metal AIR translation,
producer-backed compute and two floating-point tile-fetch cases. Ordinary
anonymous and memfd code controls also passed under both identities. Direct
execution from moved GPU-backed
pages failed: an instrumented run retained correct code bytes after RX but was
interrupted by its watchdog at the first instruction. Ordinary anonymous and
memfd execution controls passed. A copied-code candidate's combined memory/code
test was issued, but Tango lost its device connection before a phase log or
exit status was observed. The outcome is unknown and requires log recovery
before further phone tests. Data sharing, CPU memory semantics and the engine's
actual invalidation behavior still require qualification. See the
[device evidence](../results/2026-11-21/README.md) and
[memory architecture audit](MEMORY-ARCHITECTURE.md).

The root agent independently found no `com.asoft.ios` or `com.asoft.ios.dev`
installation and about 134 GiB free on `/data`, with SELinux Enforcing. No
existing guest or setup was found. Those are the root agent's phone observations;
this investigation did not inspect the phone.

## Producer-memory policy: native EL0 is required

The user's latest instruction makes the fast native EL0 route a hard requirement.
Do not prepare a TCG-only iOS boot, silently disable native acceleration, or
present an automatic slow fallback as completion. The producer-memory alias
provider must qualify native EL0's actual mapping requirements before the iOS 26
route is enabled. Root availability and CPU instruction support do not satisfy
that memory contract.

| Launch path | Current code | Required initial policy |
|---|---|---|
| Normal iOS 26 boot/resume | `Guest.start26()` sets `ASOFT_NATIVE_EL0=1` when CPU features pass | Require a qualified native-EL0 producer alias provider; keep acceleration enabled and verify it becomes active |
| Setup iOS 26 boots, including firstboot/persona/wallpaper | Same `Guest.start26()` with `sb != null`; debug `ios26.txt` overrides are ignored | Enforce the same native-provider requirement for these starts; use a fresh setup/guest for initial qualification |
| QEMU manual/native entry | External configuration could select incompatible RAM or fail to initialize the factory | Report and stop if the required provider/factory cannot initialize; do not silently continue an intended native run in TCG-only mode |
| Linux setup helper VM | `Helper.run()` uses separate `libqemu.so`, `memory-backend-memfd`, and the `helper-native` setting | Keep this ordinary memfd path separate; preserve and verify its native mode rather than applying Vulkan-provider assumptions |
| iOS 16 | Separate `libqemu.so` and the app's guest-RAM memfd | Keep outside the producer iOS 26 experiment |

Relevant inspected code:

- `Guest.java`: `start26()`, `nativeMissing()`, `overrides26()`; the launch uses
  `-accel tcg,thread=multi,tb-size=768` and then adds native-EL0 environment when
  CPU features pass.
- `Guest.java`: `Map<String, String> ov = watch || sb != null ? ... : overrides26(...)`.
  Therefore the provider/acceleration policy belongs in the common launch path,
  not only in a debug override file.
- QEMU `target/arm/tcg/native-el0.c`, `native_el0_setup()`: native mode prepares
  its address window and forks a factory before the main process has threads.
  Startup already has fallback cases, so setting the environment alone does
  not prove that native execution is active.
- `Helper.java`: `useNative()`, `run(... allowNative ...)`, `cpuArg()`.

The alias provider must be integrated in the actual native stub/factory path,
not just QEMU's canonical RAM mapping. The inspected engine forwards RAM FDs to
the factory, then the stubs use `mmap(... MAP_SHARED | MAP_FIXED, fd, off)` for
arbitrary guest pages. That exact offset operation is incompatible with the
recorded PowerVR direct-offset result. The path must route producer-backed
pages through a qualified mapping provider while retaining existing memfd
behavior for ordinary files. The single-page move experiment supplies one
building block, not this provider.

Qualification needs to cover all of the following in an ordinary app context:

1. Transfer the correct producer allocation identity and lifetime through the
   factory/FD-registration protocol, including already-created and later stubs.
2. Materialize arbitrary nonzero-offset pages and discontiguous views without
   changing canonical addresses or mapping a different page. Test repeated
   independent aliases and parent/child shared write visibility, including the
   CPU/GPU coherence contract.
3. Honor native page permissions and executable mappings. Test the engine's
   direct `PROT_EXEC` mappings, instruction-cache maintenance, and its existing
   rewritten-code/cache paths where applicable. A readable/writable data-view
   pass does not establish executable support. Preserve the existing semantics
   of code rewriting rather than substituting copied writable guest data.
4. Preserve invalidation/remap behavior when guest page tables change, writable
   aliases are replaced, mappings are protected, stubs are recycled or a child
   exits. Check ownership and cleanup after partial failure.
5. Exercise representative range sizes and alias churn under the actual
   multi-stub factory path. Record native-execution counters and stub activity,
   so a successful TCG fallback cannot be mislabeled as a native pass.

Concrete source hooks are in `target/arm/tcg/native-el0.c`: `stub_shm_init()`,
`factory_main()`, RAM-FD registration around `ram_fd_index()`, the stub mapping
path around the `f.va/f.len/f.prot/f.off` request, fill-around mappings, and the
in-process mirror mapping. The code-cache memfd is a separate mechanism and
must remain coherent with any provider-specific direct code mapping. QEMU RAM
allocation and reims gather/view ownership also need the same allocation
identity; fixing the stub alone is insufficient.

The exact backend-selection API remains to be designed with the memory bridge;
this plan does not invent a working producer-memory environment variable. Log
the selected RAM provider and verified active native mode on both setup and
ordinary launches. Guest kernel work can still use TCG as the upstream design
requires; the hard requirement is that the supported native EL0 acceleration
actually runs, not that every CPU instruction is native.

## GPU support gate

Do not write a saved GPU-check pass, force the system-driver preference, or
classify the standalone diagnostic as an integrated capability pass.

The current `GpuCheck.java`/`gpucheck.c` tests still require the old memory path
and ROAA/interlock options. The current system-driver launch also sets
`REIMS_VGPU_DEFERRED_VIEWS=0`, selecting views that import host pointers. PowerVR
lacks that host-pointer extension. Selecting system Vulkan alone cannot bridge
this mismatch.

Once the actual producer/gather/runtime implementation exists, extend the gate
to execute the same backend contract that the guest engine will use. It must
test the required Vulkan allocation/usage and coherent CPU mapping, correct
views and lifetime, actual translated tile-fetch shader behavior, and ordinary
app execution. Unsupported forms must remain a refusal. Only that new pass may
select the corresponding system-loader/memory-policy path. Existing Adreno
selection should retain its current behavior.

## Build inputs and proposed staging

The official v0.1.6 APK was downloaded and verified. See `PROVENANCE.md` and
`inventory.json` for exact hashes. Reuse is source-specific:

| Input | Source | Action |
|---|---|---|
| `libqemu.so`, `libqemuimg.so`, ordinary `lib_*.so` dependencies | Verified release APK | Candidate unchanged reuse; retain original filename/soname mapping |
| `libqemu26.so` | Release provides a reference engine only | Rebuild QEMU with the producer-RAM bridge and statically linked patched reims/metal2vulkan |
| Packaged Vulkan loader and Turnip | Verified release APK | Preserve for the existing route if desired; exclude from the Pixel process library path |
| Helper `.gz.bin` assets | Verified release APK | Reuse all three; preserve no-compression packaging |
| Installer `setup/scripts`, `steps`, `tools` | Verified release APK | Pin every file by release asset hash; the required migrator fix is present |
| `setup/phone/**`, `setup/asoft-setup.json` | Current Android checkout, exact file hashes in inventory | Copy current sources, including dynamic `{TIMEBASE}` jobs, over the corresponding staged release files |
| `librender.so`, `libgpucheck.so`, `libunpack.so` | Current Android C/JNI source | Rebuild with the app; do not copy duplicate prebuilts |
| Conscrypt JNI | Declared Maven dependency | Let Gradle supply it; do not stage an APK copy |
| `el0bench.elf` | Already tracked in current Android source | Existing benchmark is byte-identical to the release |

`app/build.gradle` has two native source folders: `jniLibs` and `jniLibs26`.
`pull-libs.sh` normally populates the first and `pull-libs26.sh` the second.
Recreate that partition when staging and avoid duplicate native basenames.
For example, put QEMU26 plus the two optional bundled Vulkan libraries in
`jniLibs26/arm64-v8a`, and helper QEMU/qemu-img/other dependencies in
`jniLibs/arm64-v8a`. Do this in an isolated build checkout after memory-bridge
feasibility is settled, without overwriting the known release reference.

The upstream pull scripts assume the author's Windows/WSL/Termux environment.
The referenced Android cross-build recipe `13-qemu.sh`, development headers and
dependency `.pc` files are not in the APK. Runtime libraries alone are not a
complete QEMU build sysroot. The inspected QEMU Meson dependency is
`dependency('reims-vgpu', method: 'pkg-config', static: true, ...)`; build the
selected reims C static library for `aarch64-linux-android` with its actual
patched metal2vulkan sources, publish matching headers/pkg-config metadata,
then link the matching QEMU source and producer changes. Record exact commits,
patch hashes, compiler/toolchain, build arguments, and the final ELF closure.

For the app itself, the existing command for an isolated identity is:

```sh
./gradlew assembleDebug -PasoftDev
```

That selects `com.asoft.ios.dev`. The source requests compileSdk 36, targetSdk
35, minSdk 29, CMake 3.22.1, NDK `29.0.13846066`, AGP 8.12.0 and Gradle 9.3.1.
The locally downloaded NDK is `29.0.14206865`; resolve that version difference
explicitly in the build record. SDK Build Tools 36 and platform 36 are present
as raw extracted archives for the small diagnostic APK, not yet a completed
standard Gradle SDK layout. A full application build has not been verified.

## Counter frequency

Current source already has a register read in `Render.counterHz()` and the
`CounterFreq.hz()` wrapper. `PhoneSetup26` substitutes that rate into the current
phone jobs; `Guest.fitCounter()` also adapts a boot tree. No standalone shell
command in the inspected kit exposes that JNI routine, and the app is not
installed.

The standalone [counter probe](../experiments/counter-frequency/README.md) has
now run on the Pixel after checksum verification. It read `CNTFRQ_EL0` once and
reported **38,400,000 Hz**, UID/EUID 0, exit 0. The terminal evidence is saved
with that experiment. Use this measured 38.4 MHz timebase through the current
`CounterFreq.hz()` / `{TIMEBASE}` plumbing; do not preserve the release setup
job's fixed 19.2 MHz. A register-read pass does not qualify the GPU memory
provider or prove native EL0 is active.

## Guest input and initial run sequence

The current installer pins **iOS 26.6.2, build 23G90, iPhone17,3**, combined with
the cloudOS 26.4b `vphone600` research components, for QEMU's `vresearch` machine.
This is a specific image combination; arbitrary iOS 26 IPSWs are not established
as compatible by the inspected code.

The pinned Apple iPhone IPSW and research archive both returned HTTP 200 with
byte-range support during this investigation. Sizes were 11,254,382,122 and
1,199,454,323 bytes respectively; the setup downloads selected members rather
than necessarily retaining the complete IPSW. No Apple image was downloaded by
this task. A user-supplied image is not inherently required: the built-in
installer can fetch its declared inputs once the application qualifies.

1. Finish the actual runtime shader and producer/gather/native-alias bridge
   qualification, including executable mappings and factory/stub behavior.
   Rebuild the static QEMU26 engine and verify its complete ordinary-app path.
2. Build the separate dev APK with pinned mixed-source inputs and the explicit
   native-EL0 requirement. Verify manifest identity, signature, packaged hashes,
   ELF dependencies, actual support-check refusal/pass behavior, and active
   native execution rather than environment settings alone.
3. Install only that reviewed dev package for a bounded helper/engine startup
   check. A successful helper boot validates its ordinary memfd path; it does
   not validate producer-backed iOS RAM or Metal rendering.
4. After the true GPU/backend gate passes, start the normal on-device iOS 26
   installer. Keep its resumable work in the dev app's private
   `files/setup/a26` directory. The documented peak is about 46 GB free space,
   roughly 12 GB retained; the first setup can take hours. Timing with the new
   native producer-memory path on this Pixel remains unmeasured.
5. Use the smaller supported initial guest settings, 3072 MiB and 2x rendering,
   subject to the actual engine's allocation test and available memory. Run a
   fresh cold boot. Observe serial progress, QMP responsiveness, rendered frames,
   correct draw results and memory pressure before expanding the workload.

The on-device final guest under private `files/ios26` consists of `bootkc`,
`sptm`, `txm`, both ordinary/AOD device trees, `root26s-aod.tc`, `rd-shell.hfs`,
`root26s-aod.qcow2` and `install.json`. The ordinary launch creates its writable
user overlay separately. The older/manual path instead uses `root26r.qcow2`
and `root26m.tc`. Do not mix files between these variants.

`dev/test-ios26.sh` is a useful logging template after qualification, but its
swipe coordinates are for the author's S25 display and need adapting to the
Pixel. Some other dev scripts delete or replace test disks and preferences;
they are unsuitable as an unreviewed first-run command. `GuestService`'s cold
start uses the currently selected OS; it does not implement an `os26` intent
extra. Select iOS 26 through the normal app flow.

## Verification limits

The available evidence proves the bounded standalone tests and the identity of
these source/build inputs. It does not prove a Pixel iOS 26 boot, full Metal
coverage, arbitrary memory gather/alias behavior, guest applications, native EL0
over Vulkan-produced RAM, or KVM. The inspected launch combines TCG with native
user-mode acceleration; the intended Pixel route must qualify and retain the
latter before it is treated as ready to boot.
