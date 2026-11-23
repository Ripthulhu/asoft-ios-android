# Physical native iOS 26 GPU boot on Pixel 10

The [accepted system-app audit and GPU inputs](APP-AUDIT.md) fed a native
iOS 26.6 build 23G90 wallpaper-stage boot on a disposable QCOW2 child.
The Pixel used system Vulkan and CPU-shadow GPU memory with native EL0
required. QEMU and reims reported eight host-presented frames. A captured
1179 × 2556 frame was stable and nonuniform, and visual inspection of an
earlier capture showed the iOS startup logo. Native initialization,
execution, sampling and final syscall witnesses all passed.

The Android host fell below the 512 MiB running-memory floor after about
17 minutes, before the DataMigration milestone or a guest sync answer.
The supervisor stopped QEMU, read block statistics and block inventory,
and quit. All 17 checked block-stat nodes reported zero failed writes and
flushes. Shutdown returned exit zero, with natural process cleanup. The
boot remains incomplete and the original GPU preparation is verified
unchanged.

| Physical evidence retained on the phone | SHA-256 |
| --- | --- |
| Launch | `9bb950d1fe617b68b04d53ab08bf85b3062058236f4e4d12133611d6b26c177a` |
| VM result | `ee4ef7e5496010841602618841c01eb407b9d649a8e4e49fd4562e1fdeeb093e` |
| Guard result | `cfd96af5bc9f4b59d5c479dc900222c8ac54a5b896df8ba21c30eb73937e9358` |
| Final frame | `e5fdb505771c5a82d09f256b4fce22c8b8352db4d73a1d09d906da0d6ac0bbbc` |
| Interrupted boot disk | `163c2124429aee5e0ea74175158772d67f69a7a0c2d17cb579cb078c0028b7cc` |

Read-only raw checks found byte-identical iOSRoot primary and alternate
headers and an empty iOSRoot journal. Data had a pending journal
(`1073152..4076032`) and an unclean primary volume flag. Recovery runs on
a detached Data copy and writes a new QCOW2 child only after independent
read-only fsck. The retry waits for this recovery and a whole-image
inspection, then requires 5 GiB available at launch and limits the native
worker pool to 12. The original and interrupted images are retained.

This observation establishes physical rendering during the native boot.
DataMigration, the interactive iOS home screen, and APK verification
remain open.

## Recovery and resumed launch

The portable tool replayed 17 transactions on the detached copy. The native,
forced read-only Data check passed. The initial publisher used the wrong
version of the QCOW2 verification helper and stopped before writing the
new child. The corrected publisher reused the checked detached copy,
injected one 1 MiB window, and verified all 16 GiB of virtual Data bytes.
The child allocated no sectors outside Data.

A second native read-only inspection of the whole recovered image confirmed
matching GPT, unchanged journal metadata during inspection, empty journals
and passing forced fsck on both partitions. The native helper exited
naturally. The resumed wallpaper-stage boot launched from a fresh child
with 5,765 MiB available on Android and a pool limit of 12 native stubs.

| Accepted phone evidence | SHA-256 |
| --- | --- |
| Detached Data read-only fsck result | `e5bb4818f7334afbc905e08d305263f874b9ed88e21e43cf28399b9bb2686c68` |
| Recovery manifest | `819a7f2cdd817cc606a09bb15320fe637c408e0e3a268b935a6155f4310271b0` |
| Recovered QCOW2 child | `d587766a186e6d1315718750b550f5136751df49a585e803eabdf957eafa9f02` |
| Whole recovered image inspection | `4e3eae992ec88d4e9b2b7267d984562646e10bf338afd244abdaf6f50a888148` |
| Resumed launch | `768869edf69fbfff57000667b20d0a9e34bf9bc80db2286081305cdfcfd449cc` |

## Second memory stop and recovered checkpoint

The resumed 3× run reached eight host-presented frames. Native EL0
remained active for 1,406 seconds before Android again crossed the
512 MiB memory floor. QEMU acknowledged stop and quit, exited zero,
and reaped the native children without force. Post-stop block statistics
reported zero failed writes or flushes across 21 nodes. DataMigration
had not yet reported `LastSystemVersion`.

The two physical runs recorded recurring frame-drain timeouts before their
memory stops. FIFO 1 wait stamps advanced across both traces. The captured
startup logo and the eight presents confirm rendering, and further testing
is needed to explain the frame-completion delays.

The second interrupted layer kept the exact iOSRoot headers and empty
iOSRoot journal. Recovery replayed 17 Data transactions across the
journal wrap. The forced detached Data fsck passed. The publisher
verified all 16 GiB of virtual Data and limited the new allocations
to one 1 MiB range within Data. Both volumes then passed an independent
forced read-only check on the whole recovered image.

| Phone evidence | SHA-256 |
| --- | --- |
| Resumed VM result | `a8f16201e0d95ccb68340ceeca29c4e83ab0a34136afc78228268d692a9e877a` |
| Resumed guard result | `c26ee12e90b36e0dce14777980636ce15e8f24f46f28411efb8c97103bde890c` |
| Second interrupted QCOW2 | `344e7fb9b1e2dc140d3bcbb7e481de99a0211fe3830b794bccfc6c9d26e3b44d` |
| Second recovery manifest | `4dfc1c423ecd524278e64acb34198900ed69980c48148d2250d3512827dba9b9` |
| Second recovered QCOW2 | `2ec0f74844e537e68f41b08d60bf3f6de161171265137f88ede319e5e6dc5241` |
| Whole-image inspection | `e013fb4b5c47392aaaed66acdfea9de7e6e6a96db5494eb96796d8def070e346` |

The next native boot diagnostic uses the app's 2× frame size
(786 × 1704). The original 3× launch tree passed the original tree check
before the adapter changed the one display-scale byte in its disposable
copy. The normalized 2× tree digest is
`aa171086d4e6e6b0830e5550c99327c27d6e7f297d66f3d09bfcdebef1c80202`.
The diagnostic preserves the 3 GiB guest, the 12-stub limit and the
native EL0 and Vulkan requirements. Its launcher waits for 5 GiB
of Android headroom. The 2× guest and the APK remain unverified.

## Physical 2× startup observation

The 5 GiB prelaunch target held the first diagnostic before any guest
started. Its owner ended with preservation verified. A fresh attempt used
the frozen 3,840 MiB launch minimum and the existing 512 MiB running
floor. It launched with 4,688 MiB available and required native EL0,
12 native stubs, a 3 GiB guest and the PowerVR system Vulkan backend.

The physical 786 × 1704 capture showed the iOS startup logo. The first
positive CPU-shadow record reported 46,268,416 uploaded bytes. The first
record from the earlier 3× run reported 100,319,232 bytes. By 784 seconds
the 2× run had eight host-presented frames and zero frame-drain timeout
reports. At that point DataMigration had yet to report completion.
This is a startup observation on a later recovered Data checkpoint, with
different Android memory headroom from the earlier runs.

| Phone evidence | SHA-256 |
| --- | --- |
| Physical 2× launch | `5edb64153dc35a338558ae4be8c8435f58ec4e4ad6ee334076894191fe091c7f` |
| Physical 2× launch tree | `aa171086d4e6e6b0830e5550c99327c27d6e7f297d66f3d09bfcdebef1c80202` |
| Sampled 2× frame | `16787dbccd27ff19bf42e14651b9244ecb4210875be53f9c9e470ac1f46c0e82` |

The saved-disk checker and locale/pack owner are bound to this attempt.
They require a complete native boot, guest sync and independent read-only
disk inspection. The interactive home screen and APK are still pending.

## Later physical 2× progress

After 26 minutes, the 2× run had logged at least 512 host-presented
frames. The framebuffer showed the Apple logo and a visible progress bar.
Across two samples the bright portion grew from 249 to 314 of 482 pixels.
At the later sample, about 31 minutes after launch, the guest was still
writing to its disposable QCOW2 child. Android reported 1,120,068 KiB
available at the preceding sample. Reims had reported three frame-drain
timeouts at that point.

The later 786 × 1704 capture is retained on the phone with SHA-256
`321803cc477cbace59e1c58e94d714b194e0f3f002a4726cd39b027cddc7610e`.
DataMigration had yet to report `LastSystemVersion` when the monitoring
connection became unavailable. The launch, saved-disk audit, and pack were
queued under the phone-side owners. The final boot, disk and pack outcomes
have yet to be read.

## Final 2× result

The phone-side test ran for 5,575 seconds and logged at least 2,048
host-presented frames and seven frame-drain timeouts. QEMU aborted
with SIGABRT while reims was creating a render pipeline. The
metal2vulkan runtime returned `FramebufferFetch / NotImplemented`
for color attachment 0, Metal pixel format 550
(`MTLPixelFormatRGB10A8_2P_XR10`). Attachments 1 and 2 were present
with color writes disabled. The earlier half-output precision warning
was relayed and was separate from the abort.

DataMigration never reported completion. The guard retained the
disposable boot disk and verified the preserved inputs. The VM record
contains neither a QMP stop/flush acknowledgment nor the guest sync
witness. The saved-disk audit and pack correctly refused to continue.

| Phone evidence | SHA-256 |
| --- | --- |
| VM result | `af11d7d884226da256d13b575aa972446e6eb1505263a5f1f0a7384ee5b0cca9` |
| Guard result | `0cb6e4279f907ac3bb357b01fe05a331e13b334ce0541a83eca8621995582ec3` |
| Interrupted 2× QCOW2 | `aa1afc4fbd00229dd5057a63635f391d8dc9f2f8a82b4eaafd002e2088d5b5ab` |
| Final 2× frame | `2b66590cfa7f6f8f9a999f8b07f41060b74460b099d4939e71a713cc7a4e82a9` |

The upstream [metal2vulkan refusal inventory](https://github.com/steelbrain/metal2vulkan/blob/master/docs/REFUSALS.md)
describes unsupported computed framebuffer-fetch writes and records
RGB10A8_2P_XR10 fetches in macOS compositor pipelines. The Pixel record
identifies the feature and attachment format. It does not identify the
exact shader operation that led to the refusal. The interactive home
screen and APK remain unverified.

The [PowerVR tile-fetch fixture](../../../framebuffer-fetch/README.md) verifies coherent FP16 color reads and writes on this Pixel. It retains packed XR conversion and renderer integration as open requirements.
