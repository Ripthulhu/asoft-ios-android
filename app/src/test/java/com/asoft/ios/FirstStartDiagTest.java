package com.asoft.ios;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import java.io.File;
import java.io.IOException;
import java.io.StringReader;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;

import org.junit.Test;

/**
 * What the first start's console diagnostics make of console text. The healthy excerpts are real lines of a good
 * iOS 16 boot on a phone (notes/logs/phone-perf-2026-11-10/save-relram16/R1/serial.txt, lines 1172, 1284-1287,
 * 2266-2281; apk-2026-11-04/quick1 for the crash lines); the respawn noise is the real tail of issue #59.
 */
public class FirstStartDiagTest {
    private static final long MIN = SetupLimits.MIN;

    private static final String[] BEFORE_OFF = {
            "SWEET FB: display on",
            "exec misagent",
            "SWEET AKS: securityd sel 10 arg0 0 in 2/32 out 1/40 -> 0xe00002c7",
            "SWEET FB: display off ignored (sweetfb_keepon)",
            "SWEET AKS: securityd sel 10 arg0 0 in 2/32 out 1/40 -> 0xe00002c7"};

    private static final String[] SPRINGBOARD = {
            "SWEET AKS: SpringBoard sel 26 arg0 2 in 3/0 out 0/0 -> 0x0",
            "|SpringBoard| 2026-11-10 23:30:28.857 SpringBoard[26:238] ",
            "|SpringBoard| Unbalanced calls to begin/end appearance transitions for <SBCoverSheetPrimarySlidingViewController: 0x10486d000>.",
            "|SpringBoard| ",
            "SWEET AKS: SpringBoard sel 32 arg0 0 in 1/0 out 0/0 -> 0xe00002c7",
            "SWEET FB: display on",
            "SWEET FB: backboardd sel 79 in 2/0 out 0/40 -> 0x0"};

    private static final String[] RESPAWN_NOISE = {
            "exec xpcproxy", "exec fairplayd.H2",
            "SWEET AKS: securityd sel 10 arg0 0 in 2/32 out 1/40 -> 0xe00002c7",
            "exec xpcproxy", "exec fairplayd.H2"};

    private static String join(String[]... parts) {
        List<String> l = new ArrayList<>();
        for (String[] p : parts) {
            l.addAll(Arrays.asList(p));
        }
        return String.join("\n", l) + "\n";
    }

    private static FirstStartDiag.Marks feedAll(FirstStartDiag.Marks m, String[] lines, long atMs) {
        for (String l : lines) {
            m.feed(l, atMs);
        }
        return m;
    }

    @Test
    public void aHealthyStartGivesOnThenIgnoredOffThenOn() {
        FirstStartDiag.Marks m = new FirstStartDiag.Marks(1000);
        assertEquals("display on at min 2 (line 1)", m.feed(BEFORE_OFF[0], 1000 + 2 * MIN));
        for (int i = 1; i < 3; i++) {
            assertNull(m.feed(BEFORE_OFF[i], 1000 + 2 * MIN));
        }
        assertEquals("display off ignored at min 3 (line 4)", m.feed(BEFORE_OFF[3], 1000 + 3 * MIN));
        m.feed(BEFORE_OFF[4], 1000 + 3 * MIN);
        for (int i = 0; i < 5; i++) {
            assertNull(m.feed(SPRINGBOARD[i], 1000 + 38 * MIN));
        }
        assertEquals("display on at min 38 (line 11)", m.feed(SPRINGBOARD[5], 1000 + 38 * MIN));
        m.feed(SPRINGBOARD[6], 1000 + 38 * MIN);
        assertEquals("display on at min 2 (line 1); display off ignored at min 3 (line 4); display on at min 38 (line 11)", m.events(1000 + 39 * MIN));
        assertTrue(m.summary(), m.summary().startsWith("12 lines; SBCoverSheetPrimarySlidingViewController lines 1; SWEET AKS: SpringBoard lines 2;"));
    }

    @Test
    public void aStartThatNeverGetsPastTheIgnoredOffSaysSo() {
        FirstStartDiag.Marks m = new FirstStartDiag.Marks(0);
        feedAll(m, BEFORE_OFF, 3 * MIN);
        feedAll(m, RESPAWN_NOISE, 200 * MIN);
        assertEquals("display on at min 3 (line 1); display off ignored at min 3 (line 4); no second display on after 310 min",
                m.events(310 * MIN));
        assertTrue(m.summary(), m.summary().contains("exec fairplayd lines 2;"));
        assertTrue(m.summary(), m.summary().contains("SBCoverSheetPrimarySlidingViewController lines 0;"));
        // without a "now" the closing clause has no minutes
        assertEquals("display on at min 3 (line 1); display off ignored at min 3 (line 4); no second display on", m.events());
    }

    @Test
    public void whatNeverHappenedIsSaid() {
        assertEquals("no display on or off in the console after 45 min", feedAll(new FirstStartDiag.Marks(0), RESPAWN_NOISE, MIN).events(45 * MIN));
        FirstStartDiag.Marks onOnly = new FirstStartDiag.Marks(0);
        onOnly.feed("SWEET FB: display on", MIN);
        assertEquals("display on at min 1 (line 1); no display off after 45 min", onOnly.events(45 * MIN));
        FirstStartDiag.Marks offOnly = new FirstStartDiag.Marks(0);
        offOnly.feed("SWEET FB: display off", 2 * MIN);
        assertEquals("display off at min 2 (line 1); no display on after 45 min", offOnly.events(45 * MIN));
    }

    @Test
    public void aLineGluedToTheOneBeforeStillCounts() {
        FirstStartDiag.Marks m = new FirstStartDiag.Marks(0);
        assertNull(m.feed("skip attaching fsw to en0 using legacy TX modelSWEET NET: configd en0 delete address 10.0.2.15", 0));
        assertEquals("display on at min 0 (line 2)", m.feed("ifnet_attach: Waiting for all kernel threads created for interface stf0SWEET FB: display on", 0));
        assertEquals("display off at min 0 (line 3)", m.feed("exec misagentSWEET FB: display off", 0));
    }

    @Test
    public void crashesAreCountedAndTheirProcessesNamed() {
        FirstStartDiag.Marks m = new FirstStartDiag.Marks(0);
        feedAll(m, new String[] {
                "CRASH assetsd[245] sig 6 code 0x0 sub 0x0 slide 0x180bc000 mh 0x102c20000",
                "CRASH assetsd pc 0x1da6d3198 lr 0x1e9c625f8 sp 0x16d40acd0 fp 0x16d40acf0 far 0x1f6f2ee28",
                "CRASH assetsd bt 0x1a5d184b8 0x1e9b9af54 0x1e9b8ba4c",
                "CRASH assetsd reason ns 2 code 0x6: (none)",
                "CRASH searchd[223] sig 6 code 0x0 sub 0x0 slide 0x1e3e4000 mh 0x100c0c000",
                "CRASH assetsd[247] sig 6 code 0x0 sub 0x0 slide 0x180bc000 mh 0x1006f0000",
                "panic(cpu 0 caller 0xfffffff00a1b2c3c): something",
                "no crash in this line"}, 0);
        assertTrue(m.summary(), m.summary().contains("CRASH lines 6 (processes: assetsd, searchd); panic( lines 1"));
        FirstStartDiag.Marks many = new FirstStartDiag.Marks(0);
        for (int i = 0; i < 12; i++) {
            many.feed("CRASH proc" + (char) ('a' + i) + "[" + (100 + i) + "] sig 6 code 0x0", 0);
        }
        assertTrue(many.summary(), many.summary().contains("CRASH lines 12 (processes: proca, procb, procc, procd, proce, procf, procg, proch)"));
    }

    @Test
    public void aFlappingDisplayDoesNotFloodTheLogOrTheSentence() {
        FirstStartDiag.Marks m = new FirstStartDiag.Marks(0);
        int noted = 0;
        for (int i = 0; i < 100; i++) {
            if (m.feed(i % 2 == 0 ? "SWEET FB: display on" : "SWEET FB: display off", i * MIN) != null) {
                noted++;
            }
        }
        assertEquals(40, noted);
        String e = m.events(100 * MIN);
        assertTrue(e, e.contains("; 88 more"));
        assertFalse(e, e.contains("no second display on"));
    }

    // ---- the whole file ----------------------------------------------------------------------------------

    private static String numbered(int n, int offAt) {
        StringBuilder b = new StringBuilder();
        for (int i = 1; i <= n; i++) {
            b.append(i == offAt ? "SWEET FB: display off ignored (sweetfb_keepon)" : "hfs: set hardlink bit on vol=iOSRoot cnid=" + (450000 + i) + " line " + i).append('\n');
        }
        return b.toString();
    }

    @Test
    public void theHeadIsTheFirst120Lines() {
        FirstStartDiag.Scan s = new FirstStartDiag.Scan().read(new StringReader(numbered(300, 0)), 1 << 20);
        assertEquals(300, s.lines);
        assertEquals(120, s.head.size());
        assertEquals("hfs: set hardlink bit on vol=iOSRoot cnid=450001 line 1", s.head.get(0));
        assertTrue(s.head.get(119).endsWith("line 120"));
    }

    @Test
    public void theWindowIs30LinesBeforeAndAfter100AfterTheFirstDisplayOff() {
        FirstStartDiag.Scan s = new FirstStartDiag.Scan().read(new StringReader(numbered(400, 200) + "SWEET FB: display off\n"), 1 << 20);
        List<String> w = s.window();
        assertEquals(1 + 30 + 1 + 100, w.size());
        assertEquals("(lines 170 to 300; the first display off is line 200)", w.get(0));
        assertTrue(w.get(1).endsWith("line 170"));
        assertEquals("SWEET FB: display off ignored (sweetfb_keepon)", w.get(31));
        assertTrue(w.get(w.size() - 1).endsWith("line 300"));
    }

    @Test
    public void aWindowNearTheEdgesIsShorterAndSaysWhichLines() {
        FirstStartDiag.Scan early = new FirstStartDiag.Scan().read(new StringReader(numbered(400, 10)), 1 << 20);
        assertEquals("(lines 1 to 110; the first display off is line 10)", early.window().get(0));
        assertEquals(1 + 9 + 1 + 100, early.window().size());
        FirstStartDiag.Scan late = new FirstStartDiag.Scan().read(new StringReader(numbered(250, 240)), 1 << 20);
        assertEquals("(lines 210 to 250; the first display off is line 240)", late.window().get(0));
    }

    @Test
    public void noDisplayOffGivesNoWindow() {
        FirstStartDiag.Scan s = new FirstStartDiag.Scan().read(new StringReader(join(RESPAWN_NOISE)), 1 << 20);
        assertTrue(s.window().isEmpty());
        LinkedHashMap<String, String> h = new LinkedHashMap<>();
        LinkedHashMap<String, List<String>> sec = new LinkedHashMap<>();
        FirstStartDiag.addRecordParts(h, sec, s, null);
        assertEquals("(the console has no display off line)", sec.get(FirstStartDiag.S_AROUND).get(0));
        assertFalse(h.containsKey("display LED at give-up"));
        assertFalse(h.containsKey("engine at give-up"));
        assertFalse(sec.containsKey(FirstStartDiag.S_SCREEN));
    }

    @Test
    public void theMapCountsKindsWithDigitsCollapsed() {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < 7; i++) {
            b.append("hfs: set hardlink bit on vol=iOSRoot cnid=").append(450710 + i).append(" inoid=").append(561978490 + i).append('\n');
        }
        for (int i = 0; i < 3; i++) {
            b.append("exec fairplayd.H2\n");
        }
        b.append("exec misd\n\n");          // (an empty line has no kind)
        FirstStartDiag.Scan s = new FirstStartDiag.Scan().read(new StringReader(b.toString()), 1 << 20);
        List<String> m = s.map();
        assertEquals("3 distinct line kinds (digits collapsed) in 12 lines; the 15 commonest:", m.get(0));
        assertEquals("7 x hfs: set hardlink bit on vol=iOSRoot cnid=# inoid=#", m.get(1));
        assertEquals("3 x exec fairplayd.H#", m.get(2));
        assertEquals("1 x exec misd", m.get(3));
        assertEquals(4, m.size());
    }

    @Test
    public void theMapKeepsTheTop15AndCutsLongKinds() {
        StringBuilder b = new StringBuilder();
        for (int k = 0; k < 20; k++) {
            for (int n = 0; n <= k; n++) {
                b.append("kind").append((char) ('a' + k)).append(" ").append(n).append('\n');
            }
        }
        for (int n = 0; n < 25; n++) {
            b.append("x".repeat(110)).append('\n');
        }
        FirstStartDiag.Scan s = new FirstStartDiag.Scan().read(new StringReader(b.toString()), 1 << 20);
        List<String> m = s.map();
        assertEquals(1 + 15, m.size());
        assertEquals("21 distinct line kinds (digits collapsed) in 235 lines; the 15 commonest:", m.get(0));
        assertEquals("25 x " + "x".repeat(100), m.get(1));
        assertEquals("20 x kindt #", m.get(2));
        assertEquals("7 x kindg #", m.get(15));
    }

    @Test
    public void linesEndAtNewlineOnlyAndAPartialLastLineCounts() {
        FirstStartDiag.Scan s = new FirstStartDiag.Scan().read(new StringReader("a\r\nb\rc\n\nlast without newline"), 1 << 20);
        assertEquals(4, s.lines);
        assertEquals("b\rc".replace('\r', '.'), s.head.get(1));        // a lone \r stays inside the line (kept as a dot)
        assertEquals("last without newline", s.head.get(3));
        assertFalse(s.truncated);
    }

    @Test
    public void aFileOverTheCapIsReadOnlyToTheCap() {
        FirstStartDiag.Scan s = new FirstStartDiag.Scan().read(new StringReader(numbered(100, 0)), 500);
        assertTrue(s.truncated);
        assertTrue(s.lines < 100);
        assertTrue(s.map().get(0).contains("only the first 64 MB were read"));
        LinkedHashMap<String, String> h = new LinkedHashMap<>();
        FirstStartDiag.addRecordParts(h, new LinkedHashMap<String, List<String>>(), s, null);
        assertTrue(h.get("first start console"), h.get("first start console").contains("(the first 64 MB)"));
    }

    @Test
    public void aFileIsReadAsLatin1WithControlCharactersOut() throws IOException {
        File f = File.createTempFile("serial", ".txt");
        try {
            Files.write(f.toPath(), new byte[] {'a', (byte) 0xe9, 0x1b, '[', 'm', '\n', 0, 'x', '\n'});
            FirstStartDiag.Scan s = FirstStartDiag.scan(f);
            assertEquals(2, s.lines);
            assertEquals("aé.[m", s.head.get(0));
            assertEquals(".x", s.head.get(1));
            assertEquals("", s.error);
        } finally {
            f.delete();
        }
        FirstStartDiag.Scan none = FirstStartDiag.scan(new File(f.getPath() + ".missing"));
        assertEquals(0, none.lines);
        assertFalse(none.error.isEmpty());
    }

    @Test
    public void theRecordGetsItsFactsAndSectionsInOrder() {
        FirstStartDiag.Scan s = new FirstStartDiag.Scan().read(new StringReader(join(BEFORE_OFF, RESPAWN_NOISE)), 1 << 20);
        LinkedHashMap<String, String> h = new LinkedHashMap<>();
        LinkedHashMap<String, List<String>> sec = new LinkedHashMap<>();
        List<String> screen = Arrays.asList("screen 1179x2556, 0.0 % not black, 1 colours in a 4-bit sample");
        FirstStartDiag.addRecordParts(h, sec, s, new FirstStartDiag.GiveUp(5, "display on at min 2 (line 1); no display off after 310 min", "off", screen,
                "el-sample t=1650s all: halted  0.0% el1 45.7% el0-tcg  4.8% el0-nat 49.4% | native 57036 ms"));
        assertEquals("display on at min 2 (line 1); no display off after 310 min | " + s.marks.summary(), h.get("first start console"));
        assertEquals("off", h.get("display LED at give-up"));
        assertEquals("el-sample t=1650s all: halted  0.0% el1 45.7% el0-tcg  4.8% el0-nat 49.4% | native 57036 ms", h.get("engine at give-up"));
        assertTrue(!FirstStartDiag.S_MAP.contains("console") && !FirstStartDiag.S_HEAD.contains("console") && !FirstStartDiag.S_AROUND.contains("console"));
        assertEquals(Arrays.asList(FirstStartDiag.S_SCREEN, FirstStartDiag.S_MAP, FirstStartDiag.S_HEAD, FirstStartDiag.S_AROUND),
                new ArrayList<>(sec.keySet()));
        assertEquals("first start, the first 120 lines of serial.txt", FirstStartDiag.S_HEAD);
        assertEquals("first start, the commonest line kinds of serial.txt (top 15)", FirstStartDiag.S_MAP);
        assertEquals("first start, around the first display off in serial.txt (30 before, 100 after)", FirstStartDiag.S_AROUND);
        assertEquals("the screen when the first start gave up", FirstStartDiag.S_SCREEN);
        // the file's own events when nothing was seen live: no minutes
        LinkedHashMap<String, String> h2 = new LinkedHashMap<>();
        FirstStartDiag.addRecordParts(h2, new LinkedHashMap<String, List<String>>(), s, null);
        assertTrue(h2.get("first start console"), h2.get("first start console").startsWith("display on (line 1); display off ignored (line 4); no second display on | 10 lines;"));
    }

    // ---- the LED and the lines of the app log ------------------------------------------------------------

    @Test
    public void ledTextSaysOffWhenScrollLockIsLit() {
        assertEquals("not readable", FirstStartDiag.ledText(-1));
        assertEquals("on", FirstStartDiag.ledText(0));
        assertEquals("off", FirstStartDiag.ledText(1));
        assertEquals("on", FirstStartDiag.ledText(2));       // another LED only
        assertEquals("off", FirstStartDiag.ledText(3));
    }

    @Test
    public void theLedByteIsReadFromItsFile() throws IOException {
        File f = File.createTempFile("leds", "");
        try {
            assertEquals(-1, FirstStartDiag.readLed(f));       // empty: not written yet
            Files.write(f.toPath(), new byte[] {1});
            assertEquals(1, FirstStartDiag.readLed(f));
            Files.write(f.toPath(), new byte[] {0});
            assertEquals(0, FirstStartDiag.readLed(f));
        } finally {
            f.delete();
        }
        assertEquals(-1, FirstStartDiag.readLed(new File(f.getPath() + ".missing")));
    }

    @Test
    public void theTenMinuteLine() {
        assertEquals("first start 40 min: console 1500 lines (+120 in the last 10 min), new line kinds 410, last new kind 3 min ago, LED off",
                FirstStartDiag.progressLine(40, 1500, 120, 410, 3, "off"));
        assertEquals("first start 10 min: console 900 lines (+900 in the last 10 min), new line kinds 90, last new kind just now, LED not readable",
                FirstStartDiag.progressLine(10, 900, 900, 90, 0, "not readable"));
    }

    @Test
    public void theLocaleLineSaysWhatWasWritten() {
        assertEquals("boot-args locale: tz=Europe/Istanbul region=TR clock=24", FirstStartDiag.localeLine("Europe/Istanbul", "TR", true));
        assertEquals("boot-args locale: tz=America/New_York region=(empty, not written) clock=12", FirstStartDiag.localeLine("America/New_York", "", false));
        assertEquals("boot-args locale: tz=GMT+05:30 (not accepted, not written) region=419 clock=24", FirstStartDiag.localeLine("GMT+05:30", "419", true));
    }

    @Test
    public void aWholeHealthyExcerptReadsTheSameAsTheLiveFeed() {
        String text = join(BEFORE_OFF, SPRINGBOARD);
        FirstStartDiag.Scan s = new FirstStartDiag.Scan().read(new StringReader(text), 1 << 20);
        assertEquals(12, s.lines);
        assertEquals("(lines 1 to 12; the first display off is line 4)", s.window().get(0));
        assertEquals("display on (line 1); display off ignored (line 4); display on (line 11)", s.marks.events());
    }
}
