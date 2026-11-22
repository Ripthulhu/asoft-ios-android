# Darwin unmount helper

`guest_unmount.c` uses the iPhoneOS arm64 `statfs` layout and calls Darwin's
`unmount` with flags zero. Its read-only mode reports the root mount source and
filesystem type. Its unmount mode requires UID 0, an explicit Darwin disk
device, and an HFS mount matching that device at `/mnt/asoft-recovery`.
After unmount it checks that the path is back on the guest root mount.

The authored helper compiled with the Pixel project's available Android NDK
clang and Mach-O LLD 21. The resulting 49,944-byte arm64 iOS Mach-O declared
iOS 26.0 and the `/usr/lib/libSystem.B.dylib` dependency. The local unsigned
build SHA-256 was
`e077546177739191e2cdd0b3f40cf6f2997980120bc7f55d8ab269a48926a4e3`.

Run the build from this directory with LLVM's bin directory on PATH:

```sh
clang --target=arm64-apple-ios26.0 -Os -ffreestanding -fstack-protector-strong \
  -Wall -Wextra -Werror -c guest_unmount.c -o guest_unmount.o
ld.lld -flavor darwin -arch arm64 -platform_version ios 26.0 26.0 \
  -headerpad 0x80 -no_adhoc_codesign -o asoft-unmount guest_unmount.o libSystem.tbd
```

The text stub declares the iPhoneOS libSystem imports for linking. The guest
provides the implementation. To use the binary, sign it with the project's
existing ramdisk signing tool and add its CDHash to a fresh guest trust cache.
The helper must first run in a diskless guest using `--inspect-root`, then
demonstrate a clean unmount on a separately prepared disposable HFS fixture.
These tests precede a Data recovery experiment.

- [Darwin iPhoneOS statfs ABI](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/mount.h)
- [Darwin mount and unmount API](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/mount.2.html)
