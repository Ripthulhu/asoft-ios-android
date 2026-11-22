package com.asoft.ios;

/**
 * Whose QEMU is running (SetupOwnerTest): a setup starts iOS itself (Guest.startSetup, or the iOS 16 first start) and
 * ends it itself, with its own save. The user's Save and close, Turn off, the notification's button and a swipe away from
 * Recents must leave that QEMU alone: one of them ended an iOS 26 setup's DataMigration boot after an hour (A#172).
 * The setup is remembered by the pid its start made, so it can never stick to a later QEMU of the user's. Pure, so it is
 * tested without Android.
 */
final class SetupOwner {
    /** What the screens say when a button that would end or save the setup's QEMU is pressed. */
    static final String BUSY = "iOS is being set up: the setup saves and closes it itself when it is done.";

    private SetupOwner() {}

    /**
     * Whether the running QEMU belongs to a setup: @setupPid is the pid the setup's start made (or -1), @runningPid the
     * pid Guest holds now, @alive whether that process is still there. A pid that is gone, or another one, owns nothing.
     */
    static boolean owns(int setupPid, int runningPid, boolean alive) {
        return setupPid > 0 && setupPid == runningPid && alive;
    }
}
