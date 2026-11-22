package com.asoft.ios;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

import org.junit.Test;

/**
 * The first start's "idle or busy" and "what CPU does QEMU really get" facts: the engine's sampler lines in
 * qemu-stderr.txt, QEMU's ticks in /proc/PID/stat, and the arithmetic between two notes. The t=30s sample is a real
 * pair of lines (notes/logs/phone-perf-2026-11-10/run2/L0-off/who.txt); the t=1650s "all:" line is the one from a
 * phone's first start; its "who" line is modelled on the real one.
 */
public class FirstStartLoadTest {
    private static final String ALL_30 = "el-sample t=30s all: halted 51.7% el1 24.3% el0-tcg  8.6% el0-nat 15.4% | native 19984 ms handler 786 ms"
            + " entry 0 ms enters 38675 fills 175988 mrs 60955 evictions 1979";
    private static final String WHO_30 = "el-sample t=30s who (asid:el0/el1): 4:4008/6115 3:3134/4843 0:4/5187 2:1742/2071 57:846/581 38:588/428"
            + " 18:621/338 5:603/353 37:529/355 29:449/415";
    private static final String ALL_1650 = "el-sample t=1650s all: halted  0.0% el1 45.7% el0-tcg  4.8% el0-nat 49.4% | native 57036 ms handler 1644 ms"
            + " entry 0 ms enters 131907 fills 327323 mrs 47830 evictions 2215";
    private static final String WHO_1650 = "el-sample t=1650s who (asid:el0/el1): 4:3980/6001 3:3010/4700 0:5/5100 2:1700/2000";
    private static final String NOISE = "exec xpcproxy\nexec fairplayd.H2\nSWEET AKS: securityd sel 10 arg0 0 in 2/32 out 1/40 -> 0xe00002c7\n";

    // ---- the engine's sampler -------------------------------------------------------------------------------

    @Test
    public void theNewestAllLineIsTakenAndCutTo140Characters() {
        String text = ALL_30 + "\n" + WHO_30 + "\n" + NOISE + ALL_1650 + "\n" + WHO_1650 + "\n";
        String l = FirstStartDiag.lastElSample(text);
        assertEquals(140, l.length());
        assertEquals(ALL_1650.substring(0, 140), l);
        assertTrue(l, l.startsWith("el-sample t=1650s all: halted  0.0% el1 45.7% el0-tcg  4.8% el0-nat 49.4% | native 57036 ms handler 1644 ms"));
        // a shorter line is kept whole
        assertEquals("el-sample t=30s all: halted 51.7%", FirstStartDiag.lastElSample("el-sample t=30s all: halted 51.7%\n" + WHO_30 + "\n"));
    }

    @Test
    public void aTailThatStartsInTheMiddleOfALineStillWorks() {
        // the file's last 32 KB begin inside the older "all:" line: only the lines after it count
        String cut = ALL_30.substring(60);
        assertFalse(cut.contains("el-sample"));
        assertEquals(ALL_1650.substring(0, 140), FirstStartDiag.lastElSample(cut + "\n" + WHO_30 + "\n" + ALL_1650 + "\n" + WHO_1650 + "\n"));
        // and when that cut line is all there is, there is no sample
        assertNull(FirstStartDiag.lastElSample(cut + "\n" + WHO_30 + "\n" + NOISE));
    }

    @Test
    public void anUnfinishedLastLineIsNotTaken() {
        assertEquals(ALL_30.substring(0, 140), FirstStartDiag.lastElSample(ALL_30 + "\n" + WHO_30 + "\nel-sample t=60s all: halted 49.9% el1 2"));
        assertNull(FirstStartDiag.lastElSample(ALL_30));             // (no newline at all: it may still be written)
    }

    @Test
    public void noSampleGivesNull() {
        assertNull(FirstStartDiag.lastElSample(null));
        assertNull(FirstStartDiag.lastElSample(""));
        assertNull(FirstStartDiag.lastElSample(NOISE));
        assertNull(FirstStartDiag.lastElSample(WHO_30 + "\n" + WHO_1650 + "\n"));
    }

    @Test
    public void theProgressLineSaysIdleOrBusy() {
        assertEquals("engine 1650s: halted 0.0% el1 45.7% el0-tcg 4.8% el0-nat 49.4%", FirstStartDiag.engineText(FirstStartDiag.lastElSample(ALL_1650 + "\n")));
        assertEquals("engine 30s: halted 51.7% el1 24.3% el0-tcg 8.6% el0-nat 15.4%", FirstStartDiag.engineText(FirstStartDiag.lastElSample(ALL_30 + "\n")));
        assertEquals("engine 30s: halted 51.7%", FirstStartDiag.engineText("el-sample t=30s all: halted 51.7%"));       // (an older engine's shorter line)
        assertEquals("engine sample: none", FirstStartDiag.engineText(null));
        assertEquals("engine sample: unreadable", FirstStartDiag.engineText("something else"));
    }

    @Test
    public void onlyTheLast32KbOfStderrAreRead() throws IOException {
        File f = File.createTempFile("qemu-stderr", ".txt");
        try {
            StringBuilder b = new StringBuilder(ALL_30 + "\n");
            while (b.length() < 40_000) {
                b.append(NOISE);
            }
            Files.write(f.toPath(), b.toString().getBytes(StandardCharsets.ISO_8859_1));
            String t = FirstStartDiag.stderrTail(f);
            assertEquals(FirstStartDiag.STDERR_TAIL, t.length());
            assertNull("the old sample is beyond the tail", FirstStartDiag.lastElSample(t));
            Files.write(f.toPath(), (b + ALL_1650 + "\n" + WHO_1650 + "\n").getBytes(StandardCharsets.ISO_8859_1));
            assertEquals(ALL_1650.substring(0, 140), FirstStartDiag.lastElSample(FirstStartDiag.stderrTail(f)));
        } finally {
            f.delete();
        }
        assertEquals("", FirstStartDiag.stderrTail(new File(f.getPath() + ".missing")));
    }

    // ---- QEMU's CPU ticks -------------------------------------------------------------------------------------

    /** 4242 (libqemu so): fields 14 and 15 are 700 and 300. */
    private static final String STAT = "4242 (libqemu so) S 1 4242 4242 0 -1 4194560 13 0 5 0 700 300 0 0 20 0 8 0 55 100 20 18446744073709551615 0 0 0";

    @Test
    public void ticksAreUtimePlusStime() {
        assertEquals(1000, FirstStartDiag.cpuTicks(STAT));
        assertEquals(1000, FirstStartDiag.cpuTicks(STAT + "\n"));
    }

    @Test
    public void aCommandNameWithSpacesOrParenthesesDoesNotShiftTheFields() {
        // comm is "a) S 1 (b) x": a first ")" would put the fields of the name where the numbers are
        assertEquals(12345 + 678, FirstStartDiag.cpuTicks("4242 (a) S 1 (b) x) S 1 4242 4242 0 -1 4194560 13 0 5 0 12345 678 0 0 20 0 8 0 55"));
        assertEquals(7, FirstStartDiag.cpuTicks("1 (qemu-system-aarch64) R 0 1 1 0 -1 0 0 0 0 0 3 4 0 0 20 0 1 0 1"));
        assertEquals(0, FirstStartDiag.cpuTicks("1 () R 0 1 1 0 -1 0 0 0 0 0 0 0 0 0 20 0 1 0 1"));
    }

    @Test
    public void whatIsNoStatLineGivesMinusOne() {
        assertEquals(-1, FirstStartDiag.cpuTicks(null));
        assertEquals(-1, FirstStartDiag.cpuTicks(""));
        assertEquals(-1, FirstStartDiag.cpuTicks("garbage"));
        assertEquals(-1, FirstStartDiag.cpuTicks("1 (x) S 1 2 3"));                                                // too few fields
        assertEquals(-1, FirstStartDiag.cpuTicks("1 (x) S 1 2 3 4 5 6 7 8 9 10 11 abc def 0 0 20"));              // not numbers
        assertEquals(-1, FirstStartDiag.cpuTicks("1 (x) S 1 2 3 4 5 6 7 8 9 10 11 -5 7 0 0 20"));
    }

    @Test
    public void aProcessThatIsGoneHasNoTicks() {
        assertEquals(-1, FirstStartDiag.readTicks(Integer.MAX_VALUE));
    }

    // ---- the arithmetic and the line ---------------------------------------------------------------------------

    @Test
    public void coresAreCpuSecondsPerSecond() {
        // 240000 ticks at 100 Hz = 2400 CPU seconds in 600 s = 4 cores
        assertEquals("QEMU used 4.0 cores on average in the last 10 min", FirstStartDiag.coresText(1000, 241_000, 600_000, 100));
        // the same ticks at 1000 Hz are a tenth of that
        assertEquals("QEMU used 0.4 cores on average in the last 10 min", FirstStartDiag.coresText(1000, 241_000, 600_000, 1000));
        // 100 Hz when the rate is not known
        assertEquals("QEMU used 4.0 cores on average in the last 10 min", FirstStartDiag.coresText(1000, 241_000, 600_000, 0));
        assertEquals("QEMU used 4.0 cores on average in the last 10 min", FirstStartDiag.coresText(1000, 241_000, 600_000, -1));
        assertEquals("QEMU used 0.0 cores on average in the last 10 min", FirstStartDiag.coresText(5, 5, 600_000, 100));
        assertEquals("QEMU used 1.5 cores on average in the last 7 min", FirstStartDiag.coresText(0, 63_000, 420_000, 100));
    }

    @Test
    public void theIntervalIsNamedInWholeMinutes() {
        assertEquals("QEMU used 1.0 cores on average in the last 10 min", FirstStartDiag.coresText(0, 59_900, 599_000, 100));      // 9 min 59 s
        assertEquals("QEMU used 1.0 cores on average in the last 1 min", FirstStartDiag.coresText(0, 1000, 10_000, 100));
    }

    @Test
    public void coresNeedTicksAtBothEndsAndTime() {
        String none = "QEMU's CPU use not readable";
        assertEquals(none, FirstStartDiag.coresText(-1, 500, 600_000, 100));
        assertEquals(none, FirstStartDiag.coresText(500, -1, 600_000, 100));
        assertEquals(none, FirstStartDiag.coresText(500, 400, 600_000, 100));        // (another process under the same number)
        assertEquals(none, FirstStartDiag.coresText(0, 500, 0, 100));
        assertEquals(none, FirstStartDiag.coresText(0, 500, -5, 100));
    }

    // ---- which cores, and how fast ----------------------------------------------------------------------------

    /** A phone with four slow cores (0-3) and four fast ones (4-7), as capacities by core number. */
    private static java.util.function.IntUnaryOperator caps(int... c) {
        return i -> i < c.length ? c[i] : -1;
    }

    @Test
    public void fourSlowCoresOnAPhoneWhoseBestIs1024AreNotFast() {
        assertEquals("allowed cores 0-3: capacity 512,512,512,512 (0 of 4 fast, best on this phone 1024)",
                FirstStartDiag.coresDescribe("0-3", caps(512, 512, 512, 512, 1024, 1024, 1024, 1024), 1024));
    }

    @Test
    public void aListWithTwoRangesIsReadInOrder() {
        assertEquals("allowed cores 0-1,4-5: capacity 1024,1024,1024,1024 (4 of 4 fast, best on this phone 1024)",
                FirstStartDiag.coresDescribe("0-1,4-5", caps(1024, 1024, 1024, 1024, 1024, 1024), 1024));
        assertEquals("allowed cores 0-1,4-5: capacity 512,512,1024,1024 (2 of 4 fast, best on this phone 1024)",
                FirstStartDiag.coresDescribe("0-1,4-5", caps(512, 512, 512, 512, 1024, 1024, 1024, 1024), 1024));
        assertEquals("allowed cores 5: capacity 1024 (1 of 1 fast, best on this phone 1024)",
                FirstStartDiag.coresDescribe("5", caps(512, 512, 512, 512, 1024, 1024, 1024, 1024), 1024));
    }

    @Test
    public void fastIsSixtyPercentOfTheBestLikeCpuPlan() {
        assertEquals("allowed cores 0-1: capacity 615,614 (1 of 2 fast, best on this phone 1024)", FirstStartDiag.coresDescribe("0-1", caps(615, 614), 1024));
        assertEquals("allowed cores 0-1: capacity 492,1024 (1 of 2 fast, best on this phone 1024)", FirstStartDiag.coresDescribe("0-1", caps(492, 1024), 1024));
    }

    @Test
    public void anUnreadableCapacityIsSaid() {
        assertEquals("allowed cores 0-1,4-5: capacity not readable", FirstStartDiag.coresDescribe("0-1,4-5", i -> -1, 1024));
        assertEquals("allowed cores 0-1: capacity not readable", FirstStartDiag.coresDescribe("0-1", caps(512, 512), -1));
        assertEquals("allowed cores 0-3: capacity 1024,1024,?,? (2 of 4 fast, 2 not readable, best on this phone 1024)",
                FirstStartDiag.coresDescribe("0-3", caps(1024, 1024), 1024));
    }

    @Test
    public void aListThatIsNoListIsSaid() {
        for (String l : new String[] {null, "", "-", "abc", "3-1", "1-2-3", "0-1,", "0-1000", "-1"}) {
            assertEquals("for " + l, "allowed cores not readable", FirstStartDiag.coresDescribe(l, caps(1024, 1024), 1024));
        }
    }

    @Test
    public void theBestCapacityIsTheHighestOfThePhone() {
        assertEquals(1024, FirstStartDiag.bestCapacity(caps(300, 300, 300, 300, 1024, 1024, 1024, 1024)));
        assertEquals(492, FirstStartDiag.bestCapacity(caps(492, 492)));
        assertEquals(-1, FirstStartDiag.bestCapacity(i -> -1));
    }

    @Test
    public void theCpusetIsNamedByItsFirstLine() {
        assertEquals("cpuset /moderate", FirstStartDiag.cpusetText("/moderate"));
        assertEquals("cpuset /top-app", FirstStartDiag.cpusetText("/top-app\n"));
        assertEquals("cpuset not readable", FirstStartDiag.cpusetText(""));
        assertEquals("cpuset not readable", FirstStartDiag.cpusetText(null));
        assertEquals("", FirstStartDiag.readCpuset(Integer.MAX_VALUE));          // (no such process)
        assertEquals(-1, FirstStartDiag.readCapacity(9999));                      // (no such core)
    }

    @Test
    public void theCoresFollowTheAllowedListInTheLine() {
        assertEquals("x, engine sample: none, QEMU's CPU use not readable, QEMU may run on cores 0-3, cpuset /moderate,"
                        + " allowed cores 0-3: capacity 512,512,512,512 (0 of 4 fast, best on this phone 1024), screen off",
                FirstStartDiag.withHost("x", "engine sample: none", "QEMU's CPU use not readable", "0-3", "cpuset /moderate",
                        "allowed cores 0-3: capacity 512,512,512,512 (0 of 4 fast, best on this phone 1024)", "screen off"));
    }

    @Test
    public void theProgressLineGetsTheEngineTheCoresAndTheHostAfterIt() {
        String base = FirstStartDiag.progressLine(40, 1500, 120, 410, 3, "off");
        assertEquals(base + ", engine 1650s: halted 0.0% el1 45.7% el0-tcg 4.8% el0-nat 49.4%, QEMU used 4.0 cores on average in the last 10 min,"
                        + " QEMU may run on cores 0-7, loop late max 0 s, screen off, idle no, power-save no, battery whitelist yes, charging yes, thermal 0 (none)",
                FirstStartDiag.withHost(base, "engine 1650s: halted 0.0% el1 45.7% el0-tcg 4.8% el0-nat 49.4%",
                        "QEMU used 4.0 cores on average in the last 10 min", "0-7",
                        SetupTick.hostText(0, 0, 0, 0, 1, 1, 0)));
        assertEquals("x, engine sample: none, QEMU's CPU use not readable, QEMU may run on cores -",
                FirstStartDiag.withHost("x", "engine sample: none", "QEMU's CPU use not readable", "-", ""));
    }
}
