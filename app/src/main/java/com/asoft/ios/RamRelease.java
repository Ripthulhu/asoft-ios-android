package com.asoft.ios;

/**
 * When a stopped iOS 16's guest RAM goes back to the phone (RamReleaseTest). Guest.stop() only sends the terminate: the
 * QEMU is gone a moment later, and its RAM is this app's memfd, which kept 3.6 GB of shared memory until the next start
 * (measured after the adb test action "off"). A thread waits for the pid and then releases. A new iOS 16 start in the
 * meantime makes a new memfd, and a late release would wipe that guest's memory: so the release happens only while the
 * generation of the RAM (moved by every create and close of it) is the one the stopped QEMU had, and no QEMU runs. Pure,
 * so it is tested without Android.
 */
final class RamRelease {
    private RamRelease() {}

    /** True when the memfd is still the stopped QEMU's (@genAtStop equals @genNow) and no QEMU runs now. */
    static boolean shouldRelease(int genAtStop, int genNow, boolean qemuRunning) {
        return genAtStop == genNow && !qemuRunning;
    }
}
