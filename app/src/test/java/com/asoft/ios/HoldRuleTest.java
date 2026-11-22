package com.asoft.ios;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class HoldRuleTest {
    private static final long MIN = 60_000L;

    @Test
    public void moderateNeverHolds() {
        HoldRule r = new HoldRule(true);
        for (long t = 0; t < 120 * MIN; t += 500) {
            assertFalse(r.decide(2, false, t).holding);
        }
    }

    @Test
    public void severeHoldsAndModerateReleases() {
        // A#63: before 0.1.6 a hold at severe lasted until "light"; a phone that settles at moderate never went on
        HoldRule r = new HoldRule(true);
        assertTrue(r.decide(3, false, 0).holding);
        assertTrue(r.decide(3, false, 5 * MIN).holding);
        assertTrue(r.decide(3, false, 6 * MIN).holding);
        assertFalse(r.decide(2, false, 6 * MIN + 500).holding);
        assertFalse(r.decide(2, false, 60 * MIN).holding);
    }

    @Test
    public void boundedSevereHoldRunsForTwoMinutesThenHoldsAgain() {
        HoldRule r = new HoldRule(true);
        assertTrue(r.decide(3, false, 0).holding);
        assertTrue(r.decide(3, false, HoldRule.SEVERE_HOLD_MS - 1).holding);
        assertFalse(r.decide(3, false, HoldRule.SEVERE_HOLD_MS).holding);
        long t = HoldRule.SEVERE_HOLD_MS;
        assertFalse(r.decide(3, false, t + HoldRule.SEVERE_RUN_MS - 1).holding);
        assertTrue(r.decide(3, false, t + HoldRule.SEVERE_RUN_MS).holding);
        // and again 10 minutes later
        assertTrue(r.decide(3, false, t + HoldRule.SEVERE_RUN_MS + HoldRule.SEVERE_HOLD_MS - 1).holding);
        assertFalse(r.decide(3, false, t + HoldRule.SEVERE_RUN_MS + HoldRule.SEVERE_HOLD_MS).holding);
    }

    @Test
    public void unboundedGateHoldsAtSevereUntilModerate() {
        HoldRule r = new HoldRule(false);
        assertTrue(r.decide(3, false, 0).holding);
        assertTrue(r.decide(3, false, 3 * 60 * MIN).holding);
        assertFalse(r.decide(2, false, 3 * 60 * MIN + 500).holding);
    }

    @Test
    public void criticalHoldsWithoutLimit() {
        HoldRule r = new HoldRule(true);
        assertTrue(r.decide(4, false, 0).holding);
        assertTrue(r.decide(4, false, 60 * MIN).holding);
        assertTrue(r.decide(5, false, 61 * MIN).holding);
        assertTrue(r.decide(6, false, 62 * MIN).holding);
        assertFalse(r.decide(2, false, 63 * MIN).holding);
    }

    @Test
    public void criticalDuringARunWindowHoldsAtOnce() {
        HoldRule r = new HoldRule(true);
        r.decide(3, false, 0);
        assertFalse(r.decide(3, false, HoldRule.SEVERE_HOLD_MS).holding);
        assertTrue(r.decide(4, false, HoldRule.SEVERE_HOLD_MS + 1000).holding);
    }

    @Test
    public void aFlickerAroundSevereDoesNotStopAndStartTwiceASecond() {
        HoldRule r = new HoldRule(true);
        assertTrue(r.decide(3, false, 0).holding);
        assertFalse(r.decide(2, false, 1000).holding);
        // back at severe 1 s later: not held again until the release is 30 s old
        assertFalse(r.decide(3, false, 2000).holding);
        assertFalse(r.decide(3, false, 1000 + HoldRule.MIN_RUN_MS - 1).holding);
        assertTrue(r.decide(3, false, 1000 + HoldRule.MIN_RUN_MS).holding);
    }

    @Test
    public void lowBatteryHoldsUntilTheCharger() {
        HoldRule r = new HoldRule(true);
        HoldRule.Hold h = r.decide(1, true, 0);
        assertTrue(h.holding);
        assertEquals(HoldRule.Why.BATTERY, h.why);
        assertTrue(h.note().contains("charger"));
        assertFalse(r.decide(1, false, 500).holding);
    }

    @Test
    public void heatIsTheReasonWhenBothApply() {
        HoldRule r = new HoldRule(true);
        assertEquals(HoldRule.Why.HOT, r.decide(3, true, 0).why);
    }

    @Test
    public void theNoteNamesTheStatusAndIsNullWhenNotHeld() {
        HoldRule r = new HoldRule(true);
        HoldRule.Hold h = r.decide(3, false, 0);
        assertNotNull(h.note());
        assertTrue(h.note().contains("severe"));
        assertTrue(h.log().contains("thermal 3"));
        assertNull(r.decide(1, false, 1000).note());
    }

    /** What a decrypt's wait told, in order. */
    private static final class Told implements HoldRule.Listener {
        final java.util.List<String> events = new java.util.ArrayList<>();

        @Override
        public void held(HoldRule.Hold h) {
            events.add("held: " + h.note());
        }

        @Override
        public void over(long heldMs) {
            events.add("over after " + heldMs);
        }
    }

    @Test
    public void aDecryptOnAPhoneThatStaysAtSevereGoesOnAfterTenMinutes() {
        // A#261: a Sony whose sensor says severe while barely warm waited at every decrypt cluster for ever (the
        // decrypt's rule had no limit); since 0.1.7 it is bounded like the helper VM's
        HoldRule r = new HoldRule(true);
        long[] clock = {0};
        Told told = new Told();
        HoldRule.waitOut(() -> r.decide(3, false, clock[0]), () -> clock[0] > 60 * MIN, ms -> clock[0] += ms,
                () -> clock[0], told);
        assertEquals(HoldRule.SEVERE_HOLD_MS, clock[0]);
        assertEquals("over after " + HoldRule.SEVERE_HOLD_MS, told.events.get(told.events.size() - 1));
        // the next clusters run through the 2 minute window, then the decrypt waits again
        assertFalse(r.decide(3, false, clock[0] + MIN).holding);
        assertTrue(r.decide(3, false, clock[0] + HoldRule.SEVERE_RUN_MS).holding);
    }

    @Test
    public void theBootGateStartsABootOnAPhoneThatStaysAtSevere() {
        // startCool asks every 15 s; a boot starts in the first run window and is not held after
        HoldRule r = new HoldRule(true);
        long t = 0;
        while (r.decide(3, false, t).holding && t < 60 * MIN) {
            t += 15_000;
        }
        assertEquals(HoldRule.SEVERE_HOLD_MS, t);
        assertTrue(new HoldRule(true).decide(4, false, 0).holding);    // critical still holds
    }

    @Test
    public void aDecryptHoldTellsWhyAtOnceAndWhenItIsOver() {
        // A#258: a decrypt on a phone at severe heat showed "Decrypting ...: 0.3 GB" and nothing else
        HoldRule r = new HoldRule(false);
        int[] thermal = {3, 3, 3, 2};
        int[] at = {0};
        long[] clock = {1000};
        java.util.List<Long> slept = new java.util.ArrayList<>();
        Told told = new Told();
        HoldRule.waitOut(() -> r.decide(thermal[at[0]++], false, clock[0]), () -> false, ms -> {
            slept.add(ms);
            clock[0] += ms;
        }, () -> clock[0], told);
        assertEquals(3, slept.size());
        assertEquals(HoldRule.WAIT_STEP_MS, (long) slept.get(0));
        assertEquals(2, told.events.size());
        assertTrue(told.events.get(0).startsWith("held: Paused: the phone is hot"));
        assertTrue(told.events.get(0).contains("severe"));
        assertEquals("over after 15000", told.events.get(1));
    }

    @Test
    public void aDecryptHoldSaysTheChargerForALowBatteryAndTheNewReasonWhenItChanges() {
        HoldRule r = new HoldRule(false);
        // the battery first; then heat joins in (heat is the reason when both apply); then both are over at the last look
        int[] thermal = {1, 3, 2};
        boolean[] low = {true, true, false};
        int[] at = {0};
        Told told = new Told();
        HoldRule.waitOut(() -> {
            int i = at[0]++;
            return r.decide(thermal[i], low[i], i * 1000L);
        }, () -> false, ms -> {
        }, () -> 0, told);
        assertEquals(3, told.events.size());
        assertTrue(told.events.get(0).contains("charger"));
        assertTrue(told.events.get(1).contains("hot"));
        assertTrue(told.events.get(2).startsWith("over"));
    }

    @Test
    public void aPhoneThatIsNotHeldTellsNothingAndDoesNotSleep() {
        HoldRule r = new HoldRule(false);
        Told told = new Told();
        int[] slept = {0};
        HoldRule.waitOut(() -> r.decide(2, false, 0), () -> false, ms -> slept[0]++, () -> 0, told);
        assertEquals(0, slept[0]);
        assertTrue(told.events.isEmpty());
    }

    @Test
    public void aStopEndsTheWaitAndStillClearsWhatItSaid() {
        HoldRule r = new HoldRule(false);
        Told told = new Told();
        int[] looks = {0};
        HoldRule.waitOut(() -> r.decide(4, false, 0), () -> looks[0]++ >= 1, ms -> {
        }, () -> 0, told);
        assertEquals(2, told.events.size());
        assertTrue(told.events.get(0).startsWith("held: "));
        assertTrue(told.events.get(1).startsWith("over"));
    }

    @Test
    public void theSetupScreensShowTheDecryptHoldAndTheStepsOwnTextAfter() {
        SetupService.State s = new SetupService.State();
        s.text = "Decrypting 90.ipsw.aea: 0.3 GB";
        s.pct = 4;
        String note = new HoldRule(false).decide(3, false, 0).note();
        assertEquals(note, SetupService.holdText(s, note));
        assertTrue(s.held);
        assertEquals(note, s.holdNote);
        assertEquals("Decrypting 90.ipsw.aea: 0.3 GB (4%)", SetupService.holdText(s, null));
        assertFalse(s.held);
        assertNull(s.holdNote);
        s.pct = -1;
        assertEquals("Decrypting 90.ipsw.aea: 0.3 GB", SetupService.holdText(s, null));
    }

    @Test
    public void thermalNames() {
        assertEquals("moderate", HoldRule.thermalName(2));
        assertEquals("shutdown", HoldRule.thermalName(6));
        assertEquals("unknown", HoldRule.thermalName(-1));
    }
}
