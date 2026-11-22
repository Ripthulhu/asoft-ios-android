package com.asoft.ios;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class RunStatsTest {
    private static final String STDERR =
            "reims[info] reims_vgpu_vulkan::os: reims-vgpu: views census: held 682 of budget 49146 (vm.max_map_count 65530); aliases 0\n"
            + "el-sample t=11603s all: halted  3.0% el1 60.0% el0-tcg  7.0% el0-nat 30.0% | native 1 ms\n"
            + "el-sample t=11633s cpu0: halted  0.0% el1 65.9% el0-tcg  5.2% el0-nat 28.9%\n"
            + "el-sample t=11633s all: halted  0.0% el1 65.4% el0-tcg  5.0% el0-nat 29.7% | native 15141 ms handler 897 ms\n"
            + "el-sample t=11633s tlbi-scope: all 966669 self 21744949 none 8006119\n"
            + "reims[info] reims_vgpu_vulkan::os: reims-vgpu: views census: held 1444 of budget 49146 (vm.max_map_count 65530)\n";

    @Test
    public void peakIsTheBusiestWholeSecond() {
        RunStats.Peak p = new RunStats.Peak();
        assertEquals(0, p.peak());
        p.add(5_000);
        p.add(5_400);
        p.add(5_999);                       // one second: 3 frames
        assertEquals(3, p.peak());
        p.add(6_000);                       // a new second closes the old one; the open one counts too
        assertEquals(3, p.peak());
        p.add(6_100);
        p.add(6_200);
        p.add(6_300);
        p.add(6_400);
        assertEquals(5, p.peak());
        p.add(9_000);                       // an idle stretch: the maximum stays
        assertEquals(5, p.peak());
        p.reset();
        assertEquals(0, p.peak());
        p.add(1_000);
        assertEquals(1, p.peak());
    }

    @Test
    public void takesTheLastSamplerLine() {
        RunStats.El e = RunStats.lastEl(STDERR);
        assertNotNull(e);
        assertEquals(11633, e.t);
        assertEquals(0.0, e.halted, 0.01);
        assertEquals(65.4, e.el1, 0.01);
        assertEquals(5.0, e.el0tcg, 0.01);
        assertEquals(29.7, e.el0nat, 0.01);
    }

    @Test
    public void aSamplerLineWithoutTheNativeSplitStillGivesHalted() {
        RunStats.El e = RunStats.lastEl("el-sample t=30s all: halted 91.5% | something\n");
        assertNotNull(e);
        assertEquals(91.5, e.halted, 0.01);
        assertEquals(-1, e.el1, 0.01);
    }

    @Test
    public void noSamplerNoCensus() {
        assertNull(RunStats.lastEl("reims[info] nothing here\n"));
        assertNull(RunStats.lastCensus("reims[info] nothing here\n"));
    }

    @Test
    public void takesTheLastCensus() {
        assertEquals("1444/49146", RunStats.lastCensus(STDERR));
    }

    @Test
    public void lineIsOneCompactLine() {
        String l = RunStats.line(600, RunStats.lastEl(STDERR), "1444/49146", 12.34, 120, 2431, "1 (light)", "0-7");
        assertFalse(l.contains("\n"));
        assertTrue(l, l.startsWith("run: 10 min: vCPUs halted 0% el1 65% el0-tcg 5% el0-native 30% (sampled at 11633 s)"));
        assertTrue(l, l.contains("; views 1444/49146; live view 12.3 fps over 120 s; MemAvailable 2431 MB; thermal 1 (light); cpuset 0-7"));
    }

    @Test
    public void lineWithNothingKnown() {
        String l = RunStats.line(300, null, null, -1, 0, -1, "unknown", "-");
        assertEquals("run: 5 min: engine -; live view not drawing; MemAvailable -; thermal unknown; cpuset -", l);
    }

    @Test
    public void linesComeEveryFiveMinutesThenEveryHalfHour() {
        assertFalse(RunStats.due(299, 0));
        assertTrue(RunStats.due(300, 0));
        assertFalse(RunStats.due(590, 300));
        assertFalse(RunStats.due(3700, 3400));      // after the first hour the gap is 30 min
        assertTrue(RunStats.due(5200, 3400));
    }

    @Test
    public void startLineRamIsTheGuestsOwn() {
        // iOS 16: the memory XNU manages (maxmem), not the 7 GiB QEMU maps
        assertEquals(2048, RunStats.startRam(Guest.IOS16, 0, 2048));
        assertEquals(4096, RunStats.startRam(Guest.IOS16, 4096, 2048));
        // iOS 26 and the watch: what they booted or loaded with, else their chosen size
        assertEquals(4096, RunStats.startRam(Guest.IOS26, 4096, 6144));
        assertEquals(3072, RunStats.startRam(Guest.WATCH, 0, 3072));
    }
}
