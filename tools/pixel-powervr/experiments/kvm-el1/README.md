# Pixel 10 Pro XL KVM EL1 probes

These synthetic guests exercise the KVM operations relevant to an iOS 26 EL1 port. On the Pixel 10 Pro XL, with SELinux enforcing and the 4 KiB Android `6.12.81-android16-6` kernel, both guests passed under root with KVM API 12.

| Probe | Device result |
| --- | --- |
| EL1 hypercall | A filtered HVC exited to userspace, which read the guest registers and returned the checked value. |
| Read-only IPA mapping | A guest store to the read-only slot exited as MMIO. Userspace verified the address, value, access size and original bytes, applied the store and resumed the guest. |
| Apple instruction compatibility | A GXF sysreg read and `GENTER` each caused a guest undefined-instruction exception. |
| 16 KiB stage-1 permission switch | Userspace switched `TTBR0_EL1` between two 16 KiB tables. The guest invalidated its TLB and verified read-only, writable and restored read-only permissions for the same address. The store during the writable phase survived the return. |

The permission test uses prebuilt tables, one vCPU and guest-directed TLB invalidation. The full SPRR/GXF model needs coherent shadow table maintenance, guarded CPU state, exception delivery, and invalidation across vCPUs. The iOS boot still uses its existing accelerator. [Asahi's m1n1 implementation](https://github.com/AsahiLinux/m1n1/pull/643) provides a worked example of shadow tables and stage-2 write traps.

## Run

Use Android NDK LLVM to build the two guest images.

```sh
for probe in el1-exits el1-shadow; do
    clang --target=aarch64-linux-android35 -c "$probe.s" -o "$probe.o"
    llvm-objcopy -O binary --only-section=.text "$probe.o" "$probe.bin"
done
```

On the Pixel, run the harness with ARM64 Python, access to `/dev/kvm`, and the compiled images in the working directory.

```sh
python3 -I -B run-probes.py el1-exits.bin el1-shadow.bin
```

```text
KVM_EL1_HVC_AND_READONLY_WRITE_PASS
KVM_EL1_UNDEF_AND_PERMISSION_SWITCH_PASS
```
