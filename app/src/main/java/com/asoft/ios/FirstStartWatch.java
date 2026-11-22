package com.asoft.ios;

import java.util.Locale;

/**
 * Decides how long the iOS 16 first start is waited for (PhoneSetup.firstStart). It keeps waiting while the
 * console shows something new, gives up when it has shown nothing new for SetupLimits.FIRST_START_QUIET_MS (or
 * nothing at all for FIRST_START_NO_CONSOLE_MS), and never waits past FIRST_START_CEILING_MS. No Android here.
 *
 * Signs of life: a console line not seen before (ConsoleLife), and a milestone the caller names (the display
 * going off and on). The phone's iOS 16 has no readable screen, so the screen is not a sign here.
 */
final class FirstStartWatch {
    enum Verdict { WAIT, NO_CONSOLE, QUIET, CEILING }

    private final long start;
    private final ConsoleLife life = new ConsoleLife();
    private long lastSign, lastNovel;
    private boolean anyConsole;

    FirstStartWatch(long nowMs) {
        start = nowMs;
        lastSign = nowMs;
        lastNovel = nowMs;
    }

    /** New console text since the last call ("" when none) and whether a milestone was just seen. */
    void observe(long nowMs, String newText, boolean milestone) {
        int novel = life.feed(newText);
        if (!newText.isEmpty()) {
            anyConsole = true;
        }
        if (novel > 0) {
            lastNovel = nowMs;
        }
        if (novel > 0 || milestone) {
            lastSign = nowMs;
        }
    }

    Verdict verdict(long nowMs) {
        long since = nowMs - start;
        if (since >= SetupLimits.FIRST_START_CEILING_MS) {
            return Verdict.CEILING;
        }
        if (!anyConsole && since >= SetupLimits.FIRST_START_NO_CONSOLE_MS) {
            return Verdict.NO_CONSOLE;
        }
        if (anyConsole && nowMs - lastSign >= SetupLimits.FIRST_START_QUIET_MS) {
            return Verdict.QUIET;
        }
        return Verdict.WAIT;
    }

    long sinceSignMin(long nowMs) {
        return (nowMs - lastSign) / SetupLimits.MIN;
    }

    /** How many different console lines (ConsoleLife.key) it has seen, and when the last new one came (diagnostics only). */
    int distinctKinds() {
        return life.distinct();
    }

    long sinceNovelMin(long nowMs) {
        return (nowMs - lastNovel) / SetupLimits.MIN;
    }

    /** The line the setup screen shows while it waits. */
    String status(long nowMs) {
        long min = (nowMs - start) / SetupLimits.MIN;
        if (!anyConsole) {
            return String.format(Locale.ROOT, "Waiting for iOS to start (%d min). Nothing from it yet.", min);
        }
        long ago = sinceSignMin(nowMs);
        return String.format(Locale.ROOT, "iOS is setting itself up (%d min; a fast phone needs about 25). Still working: last sign of life %s.",
                min, ago < 1 ? "just now" : ago + " min ago");
    }

    /** Why it gave up, in plain words, for the error the user reads. */
    String giveUpText(Verdict v, long nowMs) {
        long min = (nowMs - start) / SetupLimits.MIN;
        switch (v) {
            case NO_CONSOLE:
                return "iOS printed nothing in " + min + " min, so it is not starting. Tap Resume to try again; if it happens again, send the log.";
            case QUIET:
                return "iOS has done nothing new for " + sinceSignMin(nowMs) + " min (" + min
                        + " min into its first start). Tap Resume to carry on from where it was.";
            case CEILING:
                return "iOS has been setting itself up for " + min + " min and is still not done. Tap Resume to carry on from where it was.";
            default:
                return "";
        }
    }
}
