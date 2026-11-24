# VResearch EL1 on Pixel KVM

The same iOS 26 boot kernelcache, SPTM, TXM, device tree and trust cache used by the guarded XR test were used in a disposable one-vCPU VResearch guest. The probe used a placeholder ramdisk and disabled the virtual GPU. It attached no boot disk. This isolates entry into SPTM.

| Configuration | Pixel result |
| --- | --- |
| `ASOFT_PAGE_BITS=14`, `-accel tcg -cpu max`, paused | Reached QMP prelaunch. |
| `ASOFT_PAGE_BITS=14`, `-accel kvm -cpu host`, paused | QEMU asserted that its internal page size cannot exceed the host kernel page size. |
| `ASOFT_PAGE_BITS=12`, `-accel kvm -cpu host`, paused | Reached QMP prelaunch with KVM enabled. |
| `ASOFT_PAGE_BITS=12`, `-accel kvm -cpu host`, running | First `KVM_RUN` returned `EINVAL` at the initial PC. |
| `ASOFT_PAGE_BITS=12`, `-accel kvm -cpu host,pmu=off`, running | Executed SPTM at EL1 and reached its exception handler. |

The KVM run started at `PC=0x870a4388`. After 200 ms, QMP reported `PC=0x870a5070`, in the exception path. QEMU's local GDB stub reported `ESR_EL1=0x02000000`, `ELR_EL1=0x870a74ec`, and `VBAR_EL1=0x870a5000`. The word at `ELR_EL1` was `0xd51ef100`, `msr S3_6_C15_C1_0, x0`, a write to `SPRR_CONFIG_EL1`. The syndrome reports an undefined instruction. [Asahi register reference](https://asahilinux.org/docs/hw/cpu/sprr-gxf/)

`ASOFT_PAGE_BITS` sets QEMU's internal granule. The synthetic guest independently verified 16 KiB EL1 translation on the 4 KiB Android host. Disabling the PMU lets this QEMU build enter the guest. The synthetic HVC and permission tests establish mechanisms for a compatibility layer. Guarded register state, exception semantics and synchronized shadow tables are required for real iOS execution beyond this point. [VResearch initialization](https://github.com/alpersamur3/qemu-sptm/blob/asoft-android/hw/arm/vresearch.c) � [Asahi shadow-table implementation](https://github.com/AsahiLinux/m1n1/pull/643)

The Pixel's normal KVM VM reported `ID_AA64MMFR3_EL1=0x0` through `KVM_GET_ONE_REG`. Neither architectural stage-1 permission indirection (`S1PIE`) nor overlay (`S1POE`) is exposed to this guest. The shadow table probe uses ordinary stage-1 permissions.
