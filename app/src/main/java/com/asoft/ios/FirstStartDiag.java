package com.asoft.ios;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.Reader;
import java.io.RandomAccessFile;
import java.nio.charset.StandardCharsets;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.function.IntUnaryOperator;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * What the iOS 16 first start's console says, kept for the failure record (SetupRecord) and the app log. On some
 * phones the step sits at 95 % for hours and the record held only the console's last lines, launchd's respawn
 * noise: it could not say whether iOS never finished starting SpringBoard or reached its lock screen and the app
 * missed the lines. Nothing here changes what the setup does; it only records. No Android in here.
 *
 * Marks reads the console line by line as PhoneSetup.firstStart does (the display going on and off, SpringBoard's
 * cover sheet, crashes); Scan reads the whole serial.txt once, when the record is written. A console line is
 * sometimes glued to the one before it (no newline), so every match is a contains().
 */
final class FirstStartDiag {
    private FirstStartDiag() {}

    static final String DISPLAY_ON = "SWEET FB: display on", DISPLAY_OFF = "SWEET FB: display off";
    private static final String COVER = "SBCoverSheetPrimarySlidingViewController", AKS = "SWEET AKS: SpringBoard",
            FAIRPLAY = "exec fairplayd", CRASH = "CRASH ", PANIC = "panic(";

    /** A console file is read up to this many bytes; the head, the window and the map come from what was read. */
    static final long MAX_READ = 64L << 20;
    static final int HEAD = 120, BEFORE = 30, AFTER = 100, TOP_KINDS = 15, KIND_LEN = 100;
    /** The record's lines are cut here (a console line is rarely longer than 200). */
    private static final int KEEP_LINE = 300;
    private static final int KINDS_MAX = 20_000;

    // -- the display events and counters, as the lines come ------------------------------------------

    static final class Event {
        final boolean on, ignored;
        /** Minutes since the first start began, -1 when not known (a record made from the file). */
        final long min;
        /** 1-based console line number. */
        final long line;

        Event(boolean on, boolean ignored, long min, long line) {
            this.on = on;
            this.ignored = ignored;
            this.min = min;
            this.line = line;
        }

        String text() {
            return "display " + (on ? "on" : "off" + (ignored ? " ignored" : "")) + (min >= 0 ? " at min " + min : "")
                    + " (line " + line + ")";
        }
    }

    static final class Marks {
        private static final int KEPT_EVENTS = 12, NOTED_EVENTS = 40, KEPT_CRASHED = 8;

        private final long startMs;
        private final List<Event> events = new ArrayList<>();
        private final LinkedHashSet<String> crashed = new LinkedHashSet<>();
        private long lines, cover, aks, fairplay, crashLines, panics;
        private int total;
        private boolean offSeen, onBeforeOff, onAfterOff;

        /** @startMs: when the first start began; negative when the minutes are not known. */
        Marks(long startMs) {
            this.startMs = startMs;
        }

        /**
         * One console line (without its newline) seen at @nowMs.
         * @return a display event as a line for the app log, null when the line holds none (or the log has
         * had enough of them).
         */
        String feed(String line, long nowMs) {
            lines++;
            if (line.contains(COVER)) {
                cover++;
            }
            if (line.contains(AKS)) {
                aks++;
            }
            if (line.contains(FAIRPLAY)) {
                fairplay++;
            }
            if (line.contains(CRASH)) {
                crashLines++;
                String n = crashName(line);
                if (n != null && crashed.size() < KEPT_CRASHED) {
                    crashed.add(n);
                }
            }
            if (line.contains(PANIC)) {
                panics++;
            }
            boolean off = line.contains(DISPLAY_OFF);
            if (!off && !line.contains(DISPLAY_ON)) {
                return null;
            }
            // (the same order as PhoneSetup's own check: an "off" decides, then an "on")
            Event e = new Event(!off, off && line.contains("ignored"), startMs < 0 ? -1 : Math.max(0, (nowMs - startMs) / SetupLimits.MIN), lines);
            if (off) {
                offSeen = true;
            } else if (offSeen) {
                onAfterOff = true;
            } else {
                onBeforeOff = true;
            }
            total++;
            if (events.size() < KEPT_EVENTS) {
                events.add(e);
            }
            return total <= NOTED_EVENTS ? e.text() : null;
        }

        /** "CRASH assetsd[236] sig 6 ..." gives "assetsd"; null for the lines after it (pc, bt, reason). */
        private static String crashName(String line) {
            int at = line.indexOf(CRASH) + CRASH.length();
            int br = line.indexOf('[', at);
            if (br <= at || br - at > 40 || line.indexOf(" sig ", br) < 0) {
                return null;
            }
            String n = line.substring(at, br);
            return n.indexOf(' ') >= 0 ? null : n;
        }

        long lines() {
            return lines;
        }

        /** One sentence, without a time (a record made from the file). */
        String events() {
            return events(-1);
        }

        /**
         * "display on at min 2 (line 1281); display off ignored at min 3 (line 1397); no second display on after 310
         * min": what the display did, and what it never did. @nowMs: now (negative: no "after N min").
         */
        String events(long nowMs) {
            String after = nowMs >= 0 && startMs >= 0 ? " after " + Math.max(0, (nowMs - startMs) / SetupLimits.MIN) + " min" : "";
            if (total == 0) {
                return "no display on or off in the console" + after;
            }
            StringBuilder b = new StringBuilder();
            for (Event e : events) {
                b.append(b.length() > 0 ? "; " : "").append(e.text());
            }
            if (total > events.size()) {
                b.append("; ").append(total - events.size()).append(" more");
            }
            if (!offSeen) {
                b.append("; no display off").append(after);
            } else if (!onAfterOff) {
                b.append(onBeforeOff ? "; no second display on" : "; no display on").append(after);
            }
            return b.toString();
        }

        /** The counters: lines, SpringBoard's cover sheet, its AKS calls, fairplayd's respawns, crashes, panics. */
        String summary() {
            return lines + " lines; SBCoverSheetPrimarySlidingViewController lines " + cover + "; SWEET AKS: SpringBoard lines " + aks
                    + "; exec fairplayd lines " + fairplay + "; CRASH lines " + crashLines
                    + (crashed.isEmpty() ? "" : " (processes: " + String.join(", ", crashed) + ")") + "; panic( lines " + panics;
        }
    }

    // -- the whole file, once --------------------------------------------------------------------------

    /** What one read of serial.txt found: for the failure record. */
    static final class Scan {
        final Marks marks = new Marks(-1);
        /** The first HEAD lines. */
        final List<String> head = new ArrayList<>();
        /** BEFORE lines, the first "display off" line, AFTER lines; empty when there is no such line. */
        final List<String> around = new ArrayList<>();
        long lines;
        boolean truncated;
        String error = "";
        private final LinkedHashMap<String, int[]> kinds = new LinkedHashMap<>();
        private boolean kindsFull;
        private final ArrayDeque<String> ring = new ArrayDeque<>();
        private long offLine;
        private int before, afterLeft;

        private void line(String raw) {
            lines++;
            marks.feed(raw, 0);
            String k = ConsoleLife.key(raw);
            if (!k.isEmpty()) {
                int[] n = kinds.get(k);
                if (n != null) {
                    n[0]++;
                } else if (kinds.size() < KINDS_MAX) {
                    kinds.put(k, new int[] {1});
                } else {
                    kindsFull = true;
                }
            }
            String keep = null;
            if (lines <= HEAD || offLine == 0 || afterLeft > 0) {
                keep = keep(raw);
            }
            if (lines <= HEAD) {
                head.add(keep);
            }
            if (offLine == 0) {
                if (raw.contains(DISPLAY_OFF)) {
                    offLine = lines;
                    before = ring.size();
                    around.addAll(ring);
                    around.add(keep);
                    afterLeft = AFTER;
                } else {
                    ring.addLast(keep);
                    if (ring.size() > BEFORE) {
                        ring.removeFirst();
                    }
                }
            } else if (afterLeft > 0) {
                around.add(keep);
                afterLeft--;
            }
        }

        int distinct() {
            return kinds.size();
        }

        /** "412 distinct kinds in 1500 lines", then the TOP_KINDS commonest as "count x kind". */
        List<String> map() {
            List<Map.Entry<String, int[]>> all = new ArrayList<>(kinds.entrySet());
            Collections.sort(all, (a, b) -> Integer.compare(b.getValue()[0], a.getValue()[0]));      // (stable: ties keep their first-seen order)
            List<String> out = new ArrayList<>();
            out.add(kinds.size() + " distinct line kinds (digits collapsed) in " + lines + " lines"
                    + (kindsFull ? "; new kinds were no longer counted after " + KINDS_MAX : "")
                    + (truncated ? "; only the first " + (MAX_READ >> 20) + " MB were read" : "") + "; the " + TOP_KINDS + " commonest:");
            for (int i = 0; i < Math.min(TOP_KINDS, all.size()); i++) {
                String k = all.get(i).getKey();
                out.add(all.get(i).getValue()[0] + " x " + (k.length() > KIND_LEN ? k.substring(0, KIND_LEN) : k));
            }
            return out;
        }

        /** The window around the first display off, with a first line that says which lines it holds. */
        List<String> window() {
            if (around.isEmpty()) {
                return around;
            }
            List<String> out = new ArrayList<>(around.size() + 1);
            out.add("(lines " + (offLine - before) + " to " + (offLine + around.size() - 1 - before) + "; the first display off is line "
                    + offLine + ")");
            out.addAll(around);
            return out;
        }

        /** Reads @in as console text: lines end at "\n" only, as PhoneSetup's own reader splits them. */
        Scan read(Reader in, long maxChars) {
            StringBuilder b = new StringBuilder();
            char[] buf = new char[1 << 16];
            long seen = 0;
            try {
                int n;
                while (seen < maxChars && (n = in.read(buf, 0, (int) Math.min(buf.length, maxChars - seen))) > 0) {
                    seen += n;
                    for (int i = 0; i < n; i++) {
                        char c = buf[i];
                        if (c == '\n') {
                            line(b.length() > 0 && b.charAt(b.length() - 1) == '\r' ? b.substring(0, b.length() - 1) : b.toString());
                            b.setLength(0);
                        } else if (b.length() < 16_384) {     // a line that never ends is no line
                            b.append(c);
                        }
                    }
                }
                truncated = seen >= maxChars && in.read() >= 0;
            } catch (IOException e) {
                error = e.toString();
            }
            if (b.length() > 0) {
                line(b.toString());
            }
            return this;
        }
    }

    /** serial.txt read through once (up to MAX_READ); never throws, a failure is in Scan.error. */
    static Scan scan(File serial) {
        Scan s = new Scan();
        try (Reader in = new InputStreamReader(new FileInputStream(serial), StandardCharsets.ISO_8859_1)) {
            s.read(in, MAX_READ);
        } catch (IOException e) {
            s.error = e.toString();
        }
        return s;
    }

    /** A console line as the record keeps it: cut, control characters out. */
    private static String keep(String l) {
        String s = l.length() > KEEP_LINE ? l.substring(0, KEEP_LINE) + "…" : l;
        StringBuilder b = null;
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c < 32 && c != '\t') {
                if (b == null) {
                    b = new StringBuilder(s);
                }
                b.setCharAt(i, '.');
            }
        }
        return b == null ? s : b.toString();
    }

    // -- what the give-up saw (PhoneSetup.firstStart hands it to SetupRecord) ---------------------------

    static final class GiveUp {
        final long atMs;
        /** Marks.events() with the minutes. */
        final String events;
        /** ledText of the display LED at that moment. */
        final String led;
        /** The section "the screen when the first start gave up". */
        final List<String> screen;
        /** The engine's newest "el-sample ... all:" line (lastElSample), "none" without one. */
        final String engine;

        GiveUp(long atMs, String events, String led, List<String> screen, String engine) {
            this.atMs = atMs;
            this.events = events;
            this.led = led;
            this.screen = screen;
            this.engine = engine;
        }
    }

    /** The newest give-up of the first start in this process, null before one (or when a new first start began). */
    static volatile GiveUp lastGiveUp;

    // -- the display LED -------------------------------------------------------------------------------

    /** The guest's display power from QEMU's LED byte (Guest.ledsFile): -1 when the file cannot be read. */
    static int readLed(File f) {
        try (RandomAccessFile in = new RandomAccessFile(f, "r")) {
            return in.read();
        } catch (IOException e) {
            return -1;
        }
    }

    /** "off" while XNU lights Scroll Lock (iOS has its display off), "on" otherwise, "not readable" for -1. */
    static String ledText(int ledByteOrMinus1) {
        if (ledByteOrMinus1 < 0) {
            return "not readable";
        }
        return (ledByteOrMinus1 & Guest.SCROLL_LOCK_LED) != 0 ? "off" : "on";
    }

    // -- the lines of the app log ------------------------------------------------------------------------

    /** The every-10-minutes line: how busy the console is and when it last showed something new. */
    static String progressLine(long min, long lines, long newLines, int kinds, long lastNewKindMinAgo, String led) {
        return String.format(Locale.ROOT, "first start %d min: console %d lines (+%d in the last 10 min), new line kinds %d, "
                + "last new kind %s, LED %s", min, lines, newLines, kinds,
                lastNewKindMinAgo < 1 ? "just now" : lastNewKindMinAgo + " min ago", led);
    }

    /** The locale words Installer.prepareBoot puts into the boot-args, and whether each was accepted. */
    static String localeLine(String tz, String region, boolean clock24) {
        String w = " " + GuestImage.withLocale("", tz, region, clock24) + " ";
        return "boot-args locale: tz=" + shown(tz, w.contains(" asoft_tz=")) + " region=" + shown(region, w.contains(" asoft_region="))
                + " clock=" + (clock24 ? "24" : "12");
    }

    private static String shown(String v, boolean written) {
        if (written) {
            return v;
        }
        return v == null || v.isEmpty() ? "(empty, not written)" : v + " (not accepted, not written)";
    }

    // -- idle or busy, and what CPU QEMU really gets --------------------------------------------------------

    /** How much of qemu-stderr.txt's end is looked at for the engine's sampler lines. */
    static final int STDERR_TAIL = 32 << 10;
    private static final int EL_LINE = 140;
    private static final Pattern EL_ALL = Pattern.compile(
            "el-sample t=(\\d+)s all: halted +([\\d.]+)%(?: el1 +([\\d.]+)% el0-tcg +([\\d.]+)% el0-nat +([\\d.]+)%)?");

    /** The last STDERR_TAIL bytes of @f (QEMU's stderr), "" when it cannot be read. */
    static String stderrTail(File f) {
        try (RandomAccessFile r = new RandomAccessFile(f, "r")) {
            long from = Math.max(0, r.length() - STDERR_TAIL);
            byte[] b = new byte[(int) (r.length() - from)];
            r.seek(from);
            r.readFully(b);
            return new String(b, StandardCharsets.ISO_8859_1);
        } catch (IOException e) {
            return "";
        }
    }

    /**
     * The newest "el-sample t=Ns all: halted ..." line of @stderrTail (the engine's sampler prints one every 30 s: the
     * share of the time the vCPUs were halted, i.e. iOS had nothing to do, and in EL1, EL0 under TCG and native EL0),
     * cut to its first 140 characters; null when there is none. The text may start in the middle of a line, and its
     * last line may be unfinished (the engine is still writing it): neither is taken.
     */
    static String lastElSample(String stderrTail) {
        if (stderrTail == null) {
            return null;
        }
        String[] ls = stderrTail.split("\n", -1);
        for (int i = ls.length - 2; i >= 0; i--) {         // (the piece after the last newline is unfinished or empty)
            Matcher m = EL_ALL.matcher(ls[i]);
            if (m.find()) {
                String l = ls[i].substring(m.start()).replace("\r", "");
                return l.length() > EL_LINE ? l.substring(0, EL_LINE) : l;
            }
        }
        return null;
    }

    /** The progress line's part for a sampler line: "engine 1650s: halted 0.0% el1 45.7% el0-tcg 4.8% el0-nat 49.4%". */
    static String engineText(String elLine) {
        if (elLine == null) {
            return "engine sample: none";
        }
        Matcher m = EL_ALL.matcher(elLine);
        if (!m.find()) {
            return "engine sample: unreadable";
        }
        return "engine " + m.group(1) + "s: halted " + m.group(2) + "%"
                + (m.group(3) == null ? "" : " el1 " + m.group(3) + "% el0-tcg " + m.group(4) + "% el0-nat " + m.group(5) + "%");
    }

    /**
     * utime + stime, in clock ticks, from a /proc/PID/stat line (fields 14 and 15); -1 when it is not one. The
     * fields are counted after the last ")" because the command name between the parentheses may hold spaces and
     * parentheses itself.
     */
    static long cpuTicks(String procStatLine) {
        if (procStatLine == null) {
            return -1;
        }
        int close = procStatLine.lastIndexOf(')');
        if (close < 0) {
            return -1;
        }
        String[] f = procStatLine.substring(close + 1).trim().split("\\s+");      // f[0] is field 3, the state
        if (f.length < 13) {
            return -1;
        }
        try {
            long user = Long.parseLong(f[11]), system = Long.parseLong(f[12]);
            return user < 0 || system < 0 ? -1 : user + system;
        } catch (NumberFormatException e) {
            return -1;
        }
    }

    /** QEMU's CPU ticks from /proc/@pid/stat, -1 when unreadable (the process is gone). */
    static long readTicks(int pid) {
        try (RandomAccessFile r = new RandomAccessFile("/proc/" + pid + "/stat", "r")) {
            byte[] b = new byte[4096];
            int n = r.read(b);
            return n <= 0 ? -1 : cpuTicks(new String(b, 0, n, StandardCharsets.ISO_8859_1));
        } catch (IOException | RuntimeException e) {
            return -1;
        }
    }

    /**
     * "QEMU used 3.4 cores on average in the last 10 min" from the ticks at both ends of the interval, its length and
     * the kernel's tick rate (@clkTck; 100 when that is not known).
     */
    static String coresText(long ticksBefore, long ticksNow, long elapsedMs, long clkTck) {
        if (ticksBefore < 0 || ticksNow < ticksBefore || elapsedMs <= 0) {
            return "QEMU's CPU use not readable";
        }
        double cores = (ticksNow - ticksBefore) / (double) (clkTck > 0 ? clkTck : 100) / (elapsedMs / 1000.0);
        return String.format(Locale.ROOT, "QEMU used %.1f cores on average in the last %d min", cores, Math.max(1, (elapsedMs + 30_000) / 60_000));
    }

    /** @line with the engine's, QEMU's CPU and the phone's state after it (RunStats.cpus, PhoneSetup26.hostText). */
    static String withHost(String line, String engine, String cores, String allowed, String host) {
        return withHost(line, engine, cores, allowed, null, null, host);
    }

    /**
     * As above with which cores those are: @cpuset (cpusetText) and @capacities (coresDescribe) follow the list of
     * allowed cores; null leaves one out.
     */
    static String withHost(String line, String engine, String cores, String allowed, String cpuset, String capacities, String host) {
        return line + ", " + engine + ", " + cores + ", QEMU may run on cores " + allowed + (cpuset == null || cpuset.isEmpty() ? "" : ", " + cpuset)
                + (capacities == null || capacities.isEmpty() ? "" : ", " + capacities) + (host == null || host.isEmpty() ? "" : ", " + host);
    }

    // -- which cores, and how fast they are ---------------------------------------------------------------------

    /** The first line of /proc/@pid/cpuset ("/top-app": the group Android keeps QEMU in), "" when unreadable. */
    static String readCpuset(int pid) {
        try (BufferedReader r = new BufferedReader(new FileReader("/proc/" + pid + "/cpuset"))) {
            String l = r.readLine();
            return l == null ? "" : l.trim();
        } catch (IOException | RuntimeException e) {
            return "";
        }
    }

    /** "cpuset /moderate". */
    static String cpusetText(String firstLine) {
        return firstLine == null || firstLine.trim().isEmpty() ? "cpuset not readable" : "cpuset " + firstLine.trim();
    }

    /** The kernel's cpu_capacity of core @cpu (1024 = the fastest), -1 when it cannot be read (CpuPlan reads the same file). */
    static int readCapacity(int cpu) {
        try {
            return Integer.parseInt(new String(java.nio.file.Files.readAllBytes(new File("/sys/devices/system/cpu/cpu" + cpu + "/cpu_capacity").toPath())).trim());
        } catch (IOException | RuntimeException e) {
            return -1;
        }
    }

    /** The best capacity among the phone's cores (cpu0 to cpu63), -1 when none can be read. */
    static int bestCapacity(IntUnaryOperator capacityOf) {
        int best = -1;
        for (int i = 0; i < 64; i++) {
            best = Math.max(best, capacityOf.applyAsInt(i));
        }
        return best;
    }

    /** The cores of a cpuset list like "0-1,4-5" in order; null when it is none ("-" is RunStats.cpus' word for unreadable). */
    private static List<Integer> parseCores(String list) {
        if (list == null) {
            return null;
        }
        List<Integer> out = new ArrayList<>();
        for (String part : list.trim().split(",", -1)) {
            String[] r = part.trim().split("-", -1);
            try {
                int from = Integer.parseInt(r[0]), to = r.length == 2 ? Integer.parseInt(r[1]) : from;
                if (r.length > 2 || from < 0 || to < from || to > 255) {
                    return null;
                }
                for (int i = from; i <= to; i++) {
                    out.add(i);
                }
            } catch (NumberFormatException e) {
                return null;
            }
        }
        return out;
    }

    /**
     * Which cores QEMU may run on and how fast they are, as CpuPlan ranks them (@bestCapacity: the phone's highest
     * cpu_capacity; "fast" = 60 % of it or more): "allowed cores 0-1,4-5: capacity 1024,1024,1024,1024 (4 of 4 fast,
     * best on this phone 1024)". @capacityOf: a core's capacity, -1 when it cannot be read.
     */
    static String coresDescribe(String allowedList, IntUnaryOperator capacityOf, int bestCapacity) {
        List<Integer> cores = parseCores(allowedList);
        if (cores == null || cores.isEmpty()) {
            return "allowed cores not readable";
        }
        StringBuilder caps = new StringBuilder();
        int fast = 0, unreadable = 0;
        for (int core : cores) {
            int c = capacityOf.applyAsInt(core);
            caps.append(caps.length() > 0 ? "," : "").append(c < 0 ? "?" : String.valueOf(c));
            if (c < 0) {
                unreadable++;
            } else if (c * 10 >= bestCapacity * 6) {
                fast++;
            }
        }
        String head = "allowed cores " + allowedList.trim() + ": ";
        if (unreadable == cores.size() || bestCapacity <= 0) {
            return head + "capacity not readable";
        }
        return head + "capacity " + caps + " (" + fast + " of " + cores.size() + " fast" + (unreadable > 0 ? ", " + unreadable + " not readable" : "")
                + ", best on this phone " + bestCapacity + ")";
    }

    // -- the record ----------------------------------------------------------------------------------------

    // (no "console" in these names: CrashReport gives such a section twice the room in the shortened GitHub link,
    // and the console's own tail, which keeps that weight, must stay the biggest part of the link)
    static final String S_MAP = "first start, the commonest line kinds of serial.txt (top " + TOP_KINDS + ")",
            S_HEAD = "first start, the first " + HEAD + " lines of serial.txt",
            S_AROUND = "first start, around the first display off in serial.txt (" + BEFORE + " before, " + AFTER + " after)",
            S_SCREEN = "the screen when the first start gave up";

    /**
     * What the first start's record adds to its header (@h) and sections (@s, before the console's tail): the
     * display events and counters, the LED and the screen at the give-up (@g, null when the step stopped another
     * way), the console's map, its first lines, and the lines around the first display off.
     */
    static void addRecordParts(LinkedHashMap<String, String> h, LinkedHashMap<String, List<String>> s, Scan scan, GiveUp g) {
        h.put("first start console", (g != null ? g.events : scan.marks.events()) + " | " + scan.marks.summary()
                + (scan.truncated ? " (the first " + (MAX_READ >> 20) + " MB)" : "") + (scan.error.isEmpty() ? "" : " (read error: " + scan.error + ")"));
        if (g != null) {
            h.put("display LED at give-up", g.led);
            h.put("engine at give-up", g.engine);
            s.put(S_SCREEN, g.screen);
        }
        s.put(S_MAP, scan.map());
        s.put(S_HEAD, scan.head.isEmpty() ? Collections.singletonList("(the console file is empty or missing)") : scan.head);
        s.put(S_AROUND, scan.around.isEmpty() ? Collections.singletonList("(the console has no display off line)") : scan.window());
    }
}
