package com.asoft.ios;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class RamReleaseTest {
    @Test
    public void theStoppedQemusRamIsReleasedOnceItIsGone() {
        assertTrue(RamRelease.shouldRelease(7, 7, false));
    }

    @Test
    public void aNewMemfdInTheMeantimeIsNeverWiped() {
        // a new iOS 16 start made its own RAM (or a close moved the generation) while the thread waited
        assertFalse(RamRelease.shouldRelease(7, 8, false));
        assertFalse(RamRelease.shouldRelease(7, 8, true));
    }

    @Test
    public void aRunningQemuKeepsItsRam() {
        assertFalse(RamRelease.shouldRelease(7, 7, true));
    }
}
