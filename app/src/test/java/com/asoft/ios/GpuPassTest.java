package com.asoft.ios;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

/**
 * The GPU check's pass after an app update: Set up checks again (thisBuild false), but a start keeps the mode the
 * build before found. Before, a Mali that had passed on its own driver started on Turnip after an update (A#296,
 * Vulkan -3) and an Adreno 750 lost the compatibility mode.
 */
public class GpuPassTest {
    private static final String OLD = "8/2969416", NEW = "9/2969416";

    @Test
    public void aPassOfThisBuildCountsEverywhere() {
        GpuPass p = new GpuPass(NEW, NEW, "", "", false);
        assertTrue(p.thisBuild);
        assertTrue(p.any);
        assertFalse(p.noSparse);
        assertFalse(p.system);
        assertEquals("the full mode", p.mode());
    }

    @Test
    public void afterAnUpdateTheSystemDriverPassKeepsItsMode() {
        GpuPass p = new GpuPass(NEW, OLD, OLD, OLD, false);
        assertFalse(p.thisBuild);           // Set up checks again before it downloads
        assertTrue(p.any);                  // an installed iOS 26 starts, a begun setup goes on
        assertTrue(p.system);               // on the phone's own driver, not on Turnip
        assertTrue(p.noSparse);
        assertEquals("the phone's own driver", p.mode());
    }

    @Test
    public void afterAnUpdateTheCompatibilityPassKeepsItsMode() {
        GpuPass p = new GpuPass(NEW, OLD, OLD, "", false);
        assertFalse(p.thisBuild);
        assertTrue(p.any);
        assertTrue(p.noSparse);
        assertFalse(p.system);
        assertEquals("the compatibility mode", p.mode());
    }

    @Test
    public void afterAnUpdateAFullPassStaysFull() {
        GpuPass p = new GpuPass(NEW, OLD, "", "", false);
        assertTrue(p.any);
        assertFalse(p.noSparse);
        assertFalse(p.system);
    }

    @Test
    public void modesOfAnotherPassDoNotCount() {
        // a check of this build passed in the full mode: the build before's compatibility key is stale
        GpuPass p = new GpuPass(NEW, NEW, OLD, OLD, false);
        assertTrue(p.thisBuild);
        assertFalse(p.noSparse);
        assertFalse(p.system);
    }

    @Test
    public void aFailedCheckOfThisBuildReplacesThePass() {
        // GpuCheck.run writes "" for all three keys when the check fails
        GpuPass p = new GpuPass(NEW, "", "", "", false);
        assertFalse(p.any);
        assertFalse(p.thisBuild);
        assertFalse(p.noSparse);
        assertFalse(p.system);
        assertEquals("no pass", p.mode());
        assertFalse(new GpuPass(NEW, null, null, null, true).system);   // no prefs at all; the debug flag needs a pass
    }

    @Test
    public void theDebugFlagForcesTheSystemDriverWithAPass() {
        assertTrue(new GpuPass(NEW, OLD, "", "", true).system);
        assertTrue(new GpuPass(NEW, NEW, "", "", true).system);
    }

    @Test
    public void cpuShadowRequiresTheCurrentBuildAndTheInstalledQualification() {
        for (GpuPass p : new GpuPass[] {
                GpuPass.forRuntime(NEW, OLD, OLD, OLD, OLD, true, false, false),
                GpuPass.forRuntime(NEW, NEW, NEW, NEW, NEW, false, false, true)}) {
            assertTrue(p.shadowBlocked);
            assertFalse(p.any);
            assertFalse(p.system);
            assertFalse(p.cpuShadow);
        }
    }

    @Test
    public void qualifiedCpuShadowUsesTheSystemDriverWithDeferredViews() {
        GpuPass p = GpuPass.forRuntime(NEW, NEW, NEW, NEW, NEW, true, true, false);
        assertTrue(p.any);
        assertTrue(p.cpuShadow);
        assertTrue(p.system);
        assertFalse(p.noSparse);
        assertFalse(p.shadowBlocked);
    }
}
