# Signed helper ran in the diskless Darwin guest

The fifth physical run booted the accepted ramdisk copy from the second
Linux embedding run. The signed helper passed its guest-side SHA-256
check, dynamically linked against Darwin's libSystem and returned
`ASOFT_ROOT_MOUNT root_device hfs` from `statfs("/")`. The shell mount
table and the kernel's `md0` marker agreed with that observation.

QMP reported no block devices or named block nodes before boot, after guest
observation and after helper execution. The run returned
`RAMDISK_HELPER_INSPECTED` at **22:26:10.105354 UTC** on November 22,
2026. Native initialization, execution and final SVC passed, and QEMU
stopped and quit with exit zero and unforced cleanup. The helper was
exercised in read-only mode. This run did not exercise unmount.

The retained result is `/data/local/tmp/asoft-rd-probe-05/run/result.json`,
4,774 bytes, SHA-256
`493254a47740cfc0fd54cbf5fff18e0d7f17b6a2fbd9d7c54b0ccf7f0e421af6`.
Its source SHA-256 is `c582344791de535167ca063b01302c2346e8862fbcc13095a1f0efd970592856`.
The next experiment must use a disposable HFS+ volume.
