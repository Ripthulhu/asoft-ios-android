package com.asoft.ios;

/**
 * Who pressed iOS's side button to wake its display: a tap on the "Screen off" cover, the automatic wake after
 * a load, and the wake at the phone's unlock are the app's own presses; the bar's side button is the user's.
 * Issue #122: iOS 16's side button toggles the display, so a press sent while the guest is still waking up (it is
 * slow right after a load) puts the display to sleep again, and a tap on the cover looked like the user's own
 * press and ended the automatic wake. A pure state machine (CoverWakeTest): the caller reads the LED byte and
 * Guest.lastPowerMs, does the pressing (wake()) and passes the clock (uptime ms).
 *   - One wake press is in flight at a time: after the app sent one, no other goes out until the display was
 *     seen on, or SETTLE_MS passed. A tap is only sent while the display is off.
 *   - The automatic wake (after a load, 60 s): first press FIRST_MS after it starts, then EVERY_MS apart, at
 *     most MAX_PRESSES (taps do not count), and it ends at once after a side button press of the user's within
 *     USER_PRESS_MS (Guest.lastPowerMs moved by something other than the app's own presses). Its press waits
 *     while a tap's press is in flight and goes at the first tick after, if the display is still off.
 */
final class CoverWake {
    static final long FIRST_MS = 5_000, EVERY_MS = 6_000, WINDOW_MS = 60_000, USER_PRESS_MS = 10_000, SETTLE_MS = 5_000;
    static final int MAX_PRESSES = 6;

    /** What a tap on the cover should do. */
    enum Tap { SEND, PENDING, NOT_OFF }

    /** What the automatic wake wants at this tick. */
    enum Step { WAIT, PRESS, END }

    private boolean auto, started;
    private long wakeAt, wakeUntil;
    private int tries;
    /** Guest.lastPowerMs right after the app's own last press (or when the automatic wake started). */
    private long ownPowerMs;
    private boolean pending;
    private long pendingAt;

    /** A new QEMU (or none yet): forgets everything; @afterLoad it was started from a save, so the automatic wake is on. */
    void reset(boolean afterLoad) {
        auto = afterLoad;
        started = false;
        wakeAt = wakeUntil = ownPowerMs = pendingAt = 0;
        tries = 0;
        pending = false;
    }

    /** The automatic wake has not ended yet (it runs from reset(true) to its END). */
    boolean autoWake() {
        return auto;
    }

    /** How many presses the automatic wake sent (taps are not counted). */
    int tries() {
        return tries;
    }

    /** A wake press went out less than SETTLE_MS ago and the display has not been seen on since. */
    boolean pending(long up) {
        return pending && up - pendingAt < SETTLE_MS;
    }

    /** Every read of the display's LED: a display seen on ends the pending press. */
    void observe(boolean displayOff) {
        if (!displayOff) {
            pending = false;
        }
    }

    /** A tap on the cover. SEND: press (wake()), which then calls pressed(). */
    Tap tap(long up, boolean displayOff) {
        if (!displayOff) {
            return Tap.NOT_OFF;
        }
        return pending(up) ? Tap.PENDING : Tap.SEND;
    }

    /**
     * The app sent a wake press (the tap's, the automatic one, the unlock's): @lastPowerMs is Guest.lastPowerMs
     * after it (iOS 16's wake is the side button, which sets it: ours, not the user's).
     */
    void pressed(long up, long lastPowerMs) {
        pending = true;
        pendingAt = up;
        ownPowerMs = lastPowerMs;
    }

    /**
     * The automatic wake, at every tick while iOS runs: PRESS means press now (wake(), which calls pressed());
     * END means it is over (the caller notes it). @lastPowerMs is Guest.lastPowerMs.
     */
    Step auto(long up, boolean displayOff, long lastPowerMs) {
        if (!auto) {
            return Step.WAIT;
        }
        if (!started) {
            started = true;
            wakeAt = up + FIRST_MS;
            wakeUntil = up + WINDOW_MS;
            ownPowerMs = lastPowerMs;
            return Step.WAIT;
        }
        if (up >= wakeUntil || tries >= MAX_PRESSES || lastPowerMs != ownPowerMs && up - lastPowerMs < USER_PRESS_MS) {
            auto = false;
            return Step.END;
        }
        if (displayOff && up >= wakeAt && !pending(up)) {
            tries++;
            wakeAt = up + EVERY_MS;
            return Step.PRESS;
        }
        return Step.WAIT;
    }
}
