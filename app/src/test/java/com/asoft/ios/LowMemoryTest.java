package com.asoft.ios;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class LowMemoryTest {
    @Test
    public void ios26DefaultByPhoneSize() {
        // 8 GB (7.5 reported), 12 GB (11.7, the S25 Ultra of A#8) and 16 GB (15.5) phones
        assertEquals(3072, LowMemory.defaultGuestMiB(7_500_000_000L, Guest.IOS26));
        // 10-14 GB: 4 GiB as in 0.1.5 while IOS26_3G_UP_TO is left at 10 GB
        assertEquals(LowMemory.IOS26_3G_UP_TO > 11_700_000_000L ? 3072 : 4096, LowMemory.defaultGuestMiB(11_700_000_000L, Guest.IOS26));
        assertEquals(4096, LowMemory.defaultGuestMiB(15_500_000_000L, Guest.IOS26));
    }

    @Test
    public void ios16DefaultIsSmallBelowTenGb() {
        assertEquals(2048, LowMemory.defaultGuestMiB(5_600_000_000L, Guest.IOS16));
        assertEquals(2048, LowMemory.defaultGuestMiB(7_600_000_000L, Guest.IOS16));
        assertEquals(4096, LowMemory.defaultGuestMiB(11_400_000_000L, Guest.IOS16));
    }

    @Test
    public void watchDefaultKeepsItsOldSplit() {
        assertEquals(2048, LowMemory.defaultGuestMiB(7_500_000_000L, Guest.WATCH));
        assertEquals(3072, LowMemory.defaultGuestMiB(11_700_000_000L, Guest.WATCH));
    }

    /** The offers of Guest.RAM_CHOICES_26 / _WATCH, copied so the test does not load Guest. */
    @Test
    public void defaultIsOneOfTheOffers() {
        for (long total : new long[]{3_500_000_000L, 5_800_000_000L, 7_500_000_000L, 11_700_000_000L, 15_500_000_000L}) {
            assertTrue(contains(new int[]{3072, 4096, 6144}, LowMemory.defaultGuestMiB(total, Guest.IOS26)));
            assertTrue(contains(new int[]{2048, 3072}, LowMemory.defaultGuestMiB(total, Guest.WATCH)));
        }
    }

    @Test
    public void guestNeed() {
        assertEquals(2048L << 20, LowMemory.guestNeedBytes(Guest.IOS16, 2048));
        assertEquals(3584L << 20, LowMemory.guestNeedBytes(Guest.IOS16, 4096));
        assertEquals((3072L * 3 / 4 + 512) << 20, LowMemory.guestNeedBytes(Guest.IOS26, 3072));
        assertTrue(LowMemory.guestNeedBytes(Guest.IOS26, 6144) > LowMemory.guestNeedBytes(Guest.IOS26, 4096));
    }

    @Test
    public void shortOnlyWhenReadAndUnderNeed() {
        long need = LowMemory.guestNeedBytes(Guest.IOS26, 3072);
        assertTrue(LowMemory.isShort(850L << 20, need));       // the 7.5 GB phones of issues 12 and 20
        assertFalse(LowMemory.isShort(need, need));
        assertFalse(LowMemory.isShort(6L << 30, need));
        assertFalse(LowMemory.isShort(0, need));               // not read: no question
        assertFalse(LowMemory.isShort(-1, need));
    }

    @Test
    public void messageSaysWhatToDo() {
        String m = LowMemory.message("iOS 26", 850L << 20, 2800L << 20);
        assertTrue(m.contains("Close other apps"));
        assertTrue(m.contains("on the screen"));
        assertTrue(m.contains("iOS 26 takes about"));
    }

    private static boolean contains(int[] a, int v) {
        for (int x : a) {
            if (x == v) {
                return true;
            }
        }
        return false;
    }
}
