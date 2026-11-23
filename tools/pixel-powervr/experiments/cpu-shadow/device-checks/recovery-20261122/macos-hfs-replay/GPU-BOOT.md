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
