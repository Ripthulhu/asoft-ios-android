package com.asoft.ios;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class CoverWakeTest {
    /**
     * The activity's side: the clock, the LED read, Guest.lastPowerMs, and wake(), which presses and then tells
     * CoverWake (iOS 16's wake is the side button and sets lastPowerMs; iOS 26's is Home and does not).
     */
    private static final class Rig {
        final CoverWake w = new CoverWake();
        final boolean ios26;
        boolean off = true;
        long now;
        long lastPower = -100_000;
        int presses;
        final java.util.List<Long> pressTimes = new java.util.ArrayList<>();

        Rig(boolean afterLoad, boolean ios26) {
            this.ios26 = ios26;
            w.reset(afterLoad);
        }

        /** An LED read at @t (readLeds). */
        void led(long t, boolean displayOff) {
            now = t;
            off = displayOff;
            w.observe(off);
        }

        /** One frame tick at @t with the display as it is: the LED read, then the automatic wake. */
        CoverWake.Step tick(long t) {
            led(t, off);
            CoverWake.Step s = w.auto(t, off, lastPower);
            if (s == CoverWake.Step.PRESS) {
                wake();
            }
            return s;
        }

        /** A tap on the cover at @t (the click listener reads the LED first). */
        CoverWake.Tap tap(long t) {
            led(t, off);
            CoverWake.Tap r = w.tap(t, off);
            if (r == CoverWake.Tap.SEND) {
                wake();
            }
            return r;
        }

        void wake() {
            presses++;
            pressTimes.add(now);
            if (!ios26) {
                lastPower = now;
            }
            w.pressed(now, lastPower);
        }

        /** The user's own press of the bar's side button (Guest.button("power") changes lastPowerMs, CoverWake is not told). */
        void userPower(long t) {
            now = t;
            lastPower = t;
        }
    }

    @Test
    public void aTapOnTheCoverDoesNotCancelTheAutomaticWake() {
        // issue #122: load, the guest is slow to wake, the user taps the cover at +1 s and again
        Rig r = new Rig(true, false);
        assertEquals(CoverWake.Step.WAIT, r.tick(0));            // "running": the wake starts, first press due at 5 s
        for (long t = 100; t < 6_000; t += 100) {
            if (t == 1_000) {
                assertEquals(CoverWake.Tap.SEND, r.tap(t));
            } else if (t == 2_000 || t == 3_000) {
                assertEquals(CoverWake.Tap.PENDING, r.tap(t));
            }
            // the tap's press is in flight until 6 s: the automatic press (due at 5 s) waits, the wake is not cancelled
            assertEquals("t=" + t, CoverWake.Step.WAIT, r.tick(t));
            assertTrue(r.w.autoWake());
        }
        assertEquals(1, r.presses);
        assertEquals(0, r.w.tries());
        assertEquals(CoverWake.Step.PRESS, r.tick(6_000));       // the first automatic press, still the first of six
        assertEquals(1, r.w.tries());
    }

    @Test
    public void theAutomaticPressHeldBackByATapGoesAtTheFirstTickAfter() {
        Rig r = new Rig(true, false);
        r.tick(0);
        assertEquals(CoverWake.Tap.SEND, r.tap(4_000));          // in flight until 9 s
        assertEquals(CoverWake.Step.WAIT, r.tick(5_000));
        assertEquals(CoverWake.Step.WAIT, r.tick(8_900));
        assertEquals(CoverWake.Step.PRESS, r.tick(9_000));       // the tick after the settle time, display still off
        assertEquals(2, r.presses);
        assertEquals(1, r.w.tries());
        assertEquals(CoverWake.Step.WAIT, r.tick(14_900));       // and the next one 6 s after that
        assertEquals(CoverWake.Step.PRESS, r.tick(15_000));
        assertEquals(2, r.w.tries());
    }

    @Test
    public void aHeldBackAutomaticPressIsNotSentToADisplayThatIsOnByThen() {
        Rig r = new Rig(true, false);
        r.tick(0);
        r.tap(4_000);
        r.led(6_000, false);                                      // the tap woke iOS
        assertEquals(CoverWake.Step.WAIT, r.tick(6_100));
        assertEquals(CoverWake.Step.WAIT, r.tick(9_000));
        assertEquals(1, r.presses);
        assertTrue(r.w.autoWake());                               // it keeps watching for the rest of the minute
    }

    @Test
    public void aSecondTapWithinTheSettleTimeIsIgnored() {
        Rig r = new Rig(false, false);
        assertEquals(CoverWake.Tap.SEND, r.tap(0));
        assertEquals(CoverWake.Tap.PENDING, r.tap(1));
        assertEquals(CoverWake.Tap.PENDING, r.tap(CoverWake.SETTLE_MS - 1));
        assertEquals(1, r.presses);
        assertTrue(r.w.pending(CoverWake.SETTLE_MS - 1));
    }

    @Test
    public void aDisplayOnClearsThePendingPress() {
        Rig r = new Rig(false, false);
        assertEquals(CoverWake.Tap.SEND, r.tap(0));
        r.led(1_000, false);                                      // iOS woke
        assertFalse(r.w.pending(1_000));
        r.led(2_000, true);                                       // and slept again (its Auto-Lock) a second later
        assertEquals(CoverWake.Tap.SEND, r.tap(2_000));
        assertEquals(2, r.presses);
    }

    @Test
    public void afterTheSettleTimeWithTheDisplayStillOffATapIsSentAgain() {
        Rig r = new Rig(false, false);
        assertEquals(CoverWake.Tap.SEND, r.tap(0));
        assertEquals(CoverWake.Tap.PENDING, r.tap(CoverWake.SETTLE_MS - 1));
        assertEquals(CoverWake.Tap.SEND, r.tap(CoverWake.SETTLE_MS));
        assertEquals(CoverWake.Tap.PENDING, r.tap(CoverWake.SETTLE_MS + 1));
        assertEquals(2, r.presses);
    }

    @Test
    public void aTapWhileTheDisplayIsOnIsNotSent() {
        Rig r = new Rig(false, false);
        r.off = false;
        assertEquals(CoverWake.Tap.NOT_OFF, r.tap(0));
        assertEquals(0, r.presses);
        assertFalse(r.w.pending(0));
        r.off = true;
        assertEquals(CoverWake.Tap.SEND, r.tap(10));             // the refused tap did not start a settle time
    }

    @Test
    public void tapsNeverUseUpTheSixTries() {
        Rig r = new Rig(true, false);
        r.tick(0);
        for (int i = 0; i < 10; i++) {
            assertEquals(CoverWake.Tap.SEND, r.tap(1_000 + i * CoverWake.SETTLE_MS));
        }
        assertEquals(10, r.presses);
        assertEquals(0, r.w.tries());
        assertTrue(r.w.autoWake());
        assertEquals(CoverWake.Step.WAIT, r.tick(46_100));       // the last tap (46 s) is in flight
        assertEquals(CoverWake.Step.PRESS, r.tick(51_000));
        assertEquals(1, r.w.tries());
    }

    @Test
    public void sixAutomaticPressesSixSecondsApartThenItEnds() {
        Rig r = new Rig(true, false);
        r.tick(0);
        CoverWake.Step last = CoverWake.Step.WAIT;
        long endAt = -1;
        for (long t = 100; t <= 70_000 && last != CoverWake.Step.END; t += 100) {
            if (t == 1_000) {
                r.tap(t);                                         // a tap on the way changes nothing about the limit
            }
            last = r.tick(t);
            endAt = t;
        }
        assertEquals(CoverWake.Step.END, last);
        assertEquals(6, r.w.tries());
        assertFalse(r.w.autoWake());
        assertEquals(7, r.presses);                               // the tap and six automatic ones
        // the first automatic press waited for the tap's settle time (1 s + 5 s), the rest are 6 s apart
        assertEquals(6_000L, (long) r.pressTimes.get(1));
        for (int i = 2; i < r.pressTimes.size(); i++) {
            assertEquals(CoverWake.EVERY_MS, r.pressTimes.get(i) - r.pressTimes.get(i - 1));
        }
        assertEquals(r.pressTimes.get(6) + 100, endAt);           // the tick after the sixth press
    }

    @Test
    public void withoutTapsTheAutomaticPressesStartAtFiveSecondsAndAreSixApart() {
        Rig r = new Rig(true, false);
        r.tick(0);
        for (long t = 100; t < 5_000; t += 100) {
            assertEquals(CoverWake.Step.WAIT, r.tick(t));
        }
        assertEquals(CoverWake.Step.PRESS, r.tick(5_000));
        assertEquals(CoverWake.Step.WAIT, r.tick(10_900));
        assertEquals(CoverWake.Step.PRESS, r.tick(11_000));
        assertEquals(CoverWake.Step.WAIT, r.tick(16_900));
        assertEquals(CoverWake.Step.PRESS, r.tick(17_000));
        assertEquals(3, r.w.tries());
    }

    @Test
    public void aRealPowerPressOfTheUserEndsTheAutomaticWake() {
        Rig r = new Rig(true, false);
        r.tick(0);
        r.tap(1_000);                                             // ours: does not count as the user's
        assertEquals(CoverWake.Step.WAIT, r.tick(2_000));
        r.userPower(3_000);                                       // the bar's side button
        assertEquals(CoverWake.Step.END, r.tick(3_100));
        assertFalse(r.w.autoWake());
        assertEquals(0, r.w.tries());
        assertEquals(CoverWake.Step.WAIT, r.tick(20_000));       // over: no more presses, no second END
        assertEquals(1, r.presses);
    }

    @Test
    public void theUsersPressBeforeTheWakeStartedIsTakenAsTheBaselineAsToday() {
        Rig r = new Rig(true, false);
        r.userPower(500);
        assertEquals(CoverWake.Step.WAIT, r.tick(1_000));        // the start: the baseline is lastPowerMs as it is
        assertEquals(CoverWake.Step.WAIT, r.tick(1_100));
        assertTrue(r.w.autoWake());
    }

    @Test
    public void aUserPressOlderThanTenSecondsDoesNotEndIt() {
        Rig r = new Rig(true, false);
        r.tick(0);
        r.userPower(1_000);
        r.off = false;
        // no tick for a while (iOS not "running" or the screen in the background): the press is 10 s old by then
        assertEquals(CoverWake.Step.WAIT, r.tick(1_000 + CoverWake.USER_PRESS_MS));
        assertTrue(r.w.autoWake());

        Rig q = new Rig(true, false);
        q.tick(0);
        q.userPower(1_000);
        assertEquals(CoverWake.Step.END, q.tick(1_000 + CoverWake.USER_PRESS_MS - 1));
    }

    @Test
    public void theUnlocksWakePressIsOursToo() {
        Rig r = new Rig(true, false);
        r.tick(0);
        r.now = 2_000;
        r.wake();                                                 // onResume's wake()
        assertEquals(CoverWake.Step.WAIT, r.tick(2_100));
        assertTrue(r.w.autoWake());
        assertEquals(CoverWake.Tap.PENDING, r.tap(3_000));       // and it debounces a tap
        assertEquals(1, r.presses);
    }

    @Test
    public void iosTwentySixsHomePressLeavesLastPowerAlone() {
        Rig r = new Rig(true, true);
        r.userPower(-50_000);
        r.tick(0);
        assertEquals(CoverWake.Tap.SEND, r.tap(1_000));
        assertEquals(-50_000L, r.lastPower);
        assertEquals(CoverWake.Step.WAIT, r.tick(2_000));
        assertEquals(CoverWake.Tap.PENDING, r.tap(2_000));
        assertEquals(CoverWake.Step.PRESS, r.tick(6_000));
    }

    @Test
    public void theMinuteEndsTheAutomaticWake() {
        Rig r = new Rig(true, false);
        r.off = false;                                            // iOS is awake: nothing to press
        r.tick(10_000);
        assertEquals(CoverWake.Step.WAIT, r.tick(10_000 + CoverWake.WINDOW_MS - 1));
        assertEquals(CoverWake.Step.END, r.tick(10_000 + CoverWake.WINDOW_MS));
        assertEquals(0, r.presses);
        assertFalse(r.w.autoWake());
    }

    @Test
    public void withoutAnAutomaticWakeAutoNeverPresses() {
        Rig r = new Rig(false, false);
        assertFalse(r.w.autoWake());
        for (long t = 0; t < 70_000; t += 1_000) {
            assertEquals(CoverWake.Step.WAIT, r.tick(t));
        }
        assertEquals(0, r.presses);
    }

    @Test
    public void resetClearsEverything() {
        Rig r = new Rig(true, false);
        r.tick(0);
        r.tap(1_000);
        r.tick(6_000);
        assertEquals(1, r.w.tries());
        assertTrue(r.w.pending(6_000));

        r.w.reset(false);                                         // a new QEMU that was not loaded from a save
        assertFalse(r.w.autoWake());
        assertEquals(0, r.w.tries());
        assertFalse(r.w.pending(6_000));
        assertEquals(CoverWake.Tap.SEND, r.w.tap(6_000, true));
        assertEquals(CoverWake.Step.WAIT, r.w.auto(20_000, true, r.lastPower));

        r.w.reset(true);                                          // and one that was: it starts over
        assertTrue(r.w.autoWake());
        assertFalse(r.w.pending(6_000));
        assertEquals(CoverWake.Step.WAIT, r.w.auto(100_000, true, r.lastPower));      // the start, not an end
        assertEquals(CoverWake.Step.WAIT, r.w.auto(104_900, true, r.lastPower));
        assertEquals(CoverWake.Step.PRESS, r.w.auto(105_000, true, r.lastPower));
        assertEquals(1, r.w.tries());
    }
}
