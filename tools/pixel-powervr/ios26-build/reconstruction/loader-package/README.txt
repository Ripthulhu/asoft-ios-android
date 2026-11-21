Android QEMU loader smoke package

This is the source-built QEMU 11.1.0 fork with native EL0 and the actual reims
C API linked. It is an isolated diagnostic executable, not an app-engine update.
The PowerVR producer/adoption memory backend has not been integrated into it.

Copy or extract the directory to a NEW location below /data/local/tmp, then run:

  sh /data/local/tmp/<new-directory>/loader-smoke.sh

The wrapper verifies every payload hash and runs only -version, -machine help
and -accel help, with a 10 second timeout for each command. It records output
under its own results directory. A clean environment prevents inherited ASOFT
options from starting native stub processes. It does not start a guest, create
disks, allocate GPU-shared memory, change device policy or replace an installed
engine. These checks establish loader/registration behavior only; they do not
qualify native guest execution, GPU integration or an iOS boot.

Keep all bundled libraries together. They are the exact closure of this binary,
from the previously signature/hash-verified Termux package set. The wrapper sets
LD_LIBRARY_PATH to this private lib directory; the original build/Termux RUNPATHs
are retained as recorded in manifest.json. No system or Vulkan driver library is
bundled or replaced. All bundled ELF LOAD segments are 16 KiB aligned.

Sources and build provenance:
  QEMU: alpersamur3/qemu-sptm @ 7a900afb62ddf94713e38ac5a4aafe1d42c9efa8
  qemu26-build-reconstruction/README.md and provenance/qemu-build.json
  qemu26-build-reconstruction/provenance/qemu-android-build.patch
  qemu26-build-reconstruction/provenance/reims-build.json
  qemu26-build-reconstruction/termux-lock.json
