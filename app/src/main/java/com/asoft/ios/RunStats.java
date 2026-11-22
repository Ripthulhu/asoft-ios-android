package com.asoft.ios;

import android.content.Context;
import android.os.SystemClock;

import java.io.File;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Speed figures of a guest run for the app log, so that a report of "laggy" can be judged from it (asoft-ios-android
 * issue 36): a start line (cold boot or quick-save load, RAM, cpuset, free memory, thermal), the time to the live
 * view's first frame, and every few minutes one compact line with the engine's own EL sampler figures (QEMU's
 * ASOFT_EL_SAMPLER lines in qemu-stderr.txt, already on), reims' views census when it prints one, and what the app
 * measures itself: frames the live view drew, MemAvailable, thermal status, cpuset. A few lines per run.
 */
final class RunStats {
    private RunStats() {}

    /** Seconds between the periodic lines for the first hour, then after it. */
    static final int EVERY_S = 300, LATER_EVERY_S = 1800, FIRST_HOUR_S = 3600;

    private static final Pattern EL_ALL = Pattern.compile(
            "el-sample t=(\\d+)s all: halted +([\\d.]+)%(?: el1 +([\\d.]+)% el0-tcg +([\\d.]+)% el0-nat +([\\d.]+)%)?");
    private static final Pattern CENSUS = Pattern.compile("views census: held (\\d+) of budget (\\d+)");

    // the run being watched (set by start, read by the live view's render thread through frame)
    private static final Object LOCK = new Object();
    private static volatile int pid = -1;
    private static long t0;                 // SystemClock.elapsedRealtime() at the QEMU start
    private static Context app;
    private static boolean firstFrameLogged;
    private static long lastFrameMs;        // the live view: when the last frame was asked for
    private static long periodFrames, periodViewMs;
    // MemAvailable (kB) sampled every 10 s of the run of sampledPid; the crash record reads the lowest one
    private static volatile int sampledPid = -1;
    private static volatile long lowestKb = -1;
    // what the works report keeps of the run (WorksReport.keep): its guest, how it started, the live view's first frame
    // (seconds after the start, -1 = not yet), the highest thermal status sampled, the newest fps and EL shares seen
    private static int runOs;
    private static boolean runResumed;
    private static int runRamMiB;
    private static String runScreen = "";
    private static volatile int firstFrameS = -1;
    private static volatile int thermalMax = -1;
    private static double lastFps = -1;
    private static final Peak peak = new Peak();
    private static El newestEl;

    /** The lowest MemAvailable (kB) sampled during the run of QEMU @p; -1 when none (or another run's). */
    static long lowestAvailKb(int p) {
        return p == sampledPid ? lowestKb : -1;
    }

    private static void sample(int p) {
        long kb = CrashReport.memInfoKb("MemAvailable");
        if (kb >= 0 && p == sampledPid) {
            lowestKb = lowestKb < 0 ? kb : Math.min(lowestKb, kb);
        }
        Context c = app;
        if (c != null && p == sampledPid) {
            android.os.PowerManager pm = c.getSystemService(android.os.PowerManager.class);
            if (pm != null) {
                thermalMax = Math.max(thermalMax, pm.getCurrentThermalStatus());
            }
        }
    }

    /**
     * The most changed frames of the live view in any one whole second of a run (the busiest second): frames are
     * counted per second of the clock, a new second closes the one before. Not thread-safe; RunStats holds LOCK.
     */
    static final class Peak {
        private long sec = -1;
        private int count;
        private int best;

        /** One changed frame at @nowMs (a monotonic clock in ms). */
        void add(long nowMs) {
            long s = nowMs / 1000;
            if (s != sec) {
                best = Math.max(best, count);
                sec = s;
                count = 0;
            }
            count++;
        }

        /** The busiest second so far, the open one included; 0 when no frame was counted. */
        int peak() {
            return Math.max(best, count);
        }

        void reset() {
            sec = -1;
            count = 0;
            best = 0;
        }
    }

    /** What a run's EL sampler said last: seconds into the run and the vCPUs' shares, -1 when absent. */
    static final class El {
        int t = -1;
        double halted = -1, el1 = -1, el0tcg = -1, el0nat = -1;
    }

    /** The last "all:" line of the EL sampler in @text; null when there is none. */
    static El lastEl(String text) {
        Matcher m = EL_ALL.matcher(text);
        El e = null;
        while (m.find()) {
            e = new El();
            e.t = Integer.parseInt(m.group(1));
            e.halted = Double.parseDouble(m.group(2));
            if (m.group(3) != null) {
                e.el1 = Double.parseDouble(m.group(3));
                e.el0tcg = Double.parseDouble(m.group(4));
                e.el0nat = Double.parseDouble(m.group(5));
            }
        }
        return e;
    }

    /** "held N/BUDGET" of the last views census line in @text; null when there is none. */
    static String lastCensus(String text) {
        Matcher m = CENSUS.matcher(text);
        String r = null;
        while (m.find()) {
            r = m.group(1) + "/" + m.group(2);
        }
        return r;
    }

    /** True when the next periodic line is due @sinceStartS seconds into the run, the last one at @lastS. */
    static boolean due(long sinceStartS, long lastS) {
        long gap = sinceStartS < FIRST_HOUR_S ? EVERY_S : LATER_EVERY_S;
        return sinceStartS - lastS >= gap;
    }

    /** One compact line of the figures; "-" for what is not known, fps below 0 when the live view was not drawing. */
    static String line(long sinceStartS, El el, String census, double fps, long viewS, long availMb, String thermal, String cpus) {
        StringBuilder b = new StringBuilder("run: ").append(sinceStartS / 60).append(" min:");
        if (el == null) {
            b.append(" engine -");
        } else if (el.el1 >= 0) {
            b.append(String.format(Locale.ROOT, " vCPUs halted %.0f%% el1 %.0f%% el0-tcg %.0f%% el0-native %.0f%% (sampled at %d s)",
                    el.halted, el.el1, el.el0tcg, el.el0nat, el.t));
        } else {
            b.append(String.format(Locale.ROOT, " vCPUs halted %.0f%% (sampled at %d s)", el.halted, el.t));
        }
        if (census != null) {
            b.append("; views ").append(census);
        }
        b.append(fps < 0 ? "; live view not drawing" : String.format(Locale.ROOT, "; live view %.1f fps over %d s", fps, viewS));
        b.append("; MemAvailable ").append(availMb < 0 ? "-" : availMb + " MB");
        b.append("; thermal ").append(thermal).append("; cpuset ").append(cpus);
        return b.toString();
    }

    /**
     * The RAM in MiB the started guest really has: what it booted or loaded with (@booted, Guest.bootRamMiB;
     * 0 when unknown), else the size chosen for it (@chosen). For iOS 16 this is the memory XNU manages
     * (maxmem), not the 7 GiB QEMU maps.
     */
    static int startRam(int os, int booted, int chosen) {
        return booted > 0 ? booted : chosen;
    }

    /** The start of QEMU @p; @t0Ms is SystemClock.elapsedRealtime() taken just before it was spawned. */
    static void start(Context c, int p, int os, boolean resumed, long t0Ms) {
        Context a = c.getApplicationContext();
        synchronized (LOCK) {
            pid = p;
            sampledPid = p;
            lowestKb = -1;
            t0 = t0Ms;
            app = a;
            firstFrameLogged = false;
            lastFrameMs = 0;
            periodFrames = 0;
            periodViewMs = 0;
            runOs = os;
            runResumed = resumed;
            runRamMiB = startRam(os, Guest.bootRamMiB(), Guest.ramMiB(a, os));
            runScreen = os == Guest.IOS26 ? (Guest.scale26(a) == 2 ? "2x (786x1704)" : "3x (1179x2556)") : "";
            firstFrameS = -1;
            thermalMax = -1;
            lastFps = -1;
            peak.reset();
            newestEl = null;
        }
        AppLog.note(a, "run: " + Guest.osName(os) + " " + (resumed ? "quick-save load" : "cold boot") + ", "
                + runRamMiB + " MiB, cpuset " + cpus(p) + ", MemAvailable " + availMb() + " MB, thermal "
                + CrashReport.thermal(a));
        sample(p);
        Thread t = new Thread(() -> watch(a, p), "run-stats");
        t.setDaemon(true);
        t.start();
    }

    /** One display frame of the live view (render thread): @changed is what Render.frame answered. */
    static void frame(int p, boolean changed) {
        long now = SystemClock.elapsedRealtime();
        Context log = null;
        long sinceS = 0;
        synchronized (LOCK) {
            if (p != pid || app == null) {
                return;
            }
            if (lastFrameMs != 0) {
                periodViewMs += Math.min(now - lastFrameMs, 1000);
            }
            lastFrameMs = now;
            if (changed) {
                periodFrames++;
                peak.add(now);
                if (!firstFrameLogged) {
                    firstFrameLogged = true;
                    log = app;
                    sinceS = (now - t0) / 1000;
                    firstFrameS = (int) sinceS;
                }
            }
        }
        if (log != null) {
            AppLog.note(log, "run: first frame of the live view " + sinceS + " s after QEMU started (the framebuffer's"
                    + " first change, seen only while the screen is open)");
        }
    }

    private static void watch(Context c, int p) {
        long lastS = 0;
        while (pid == p) {
            try {
                Thread.sleep(10_000);
            } catch (InterruptedException e) {
                return;
            }
            if (!Guest.running() || Guest.pid(c) != p) {
                return;
            }
            sample(p);
            long s = (SystemClock.elapsedRealtime() - t0) / 1000;
            if (!due(s, lastS)) {
                continue;
            }
            lastS = s;
            String tail = tail(new File(Guest.runDir(c), "qemu-stderr.txt"));
            double fps = -1;
            long viewS = 0;
            int peakFps;
            synchronized (LOCK) {
                if (periodViewMs >= 2000) {
                    fps = periodFrames * 1000.0 / periodViewMs;
                    viewS = periodViewMs / 1000;
                }
                periodFrames = 0;
                periodViewMs = 0;
                peakFps = peak.peak();
            }
            El el = lastEl(tail);
            AppLog.note(c, line(s, el, lastCensus(tail), fps, viewS, availMb(), CrashReport.thermal(c), cpus(p)));
            // the works report keeps the run once it has shown a first frame and lived 10 minutes; the newest figures win
            if (fps >= 0) {
                lastFps = fps;
            }
            if (el != null) {
                newestEl = el;
            }
            if (pid == p) {
                long low = lowestKb;
                WorksReport.keep(c, runOs, runResumed, firstFrameS, (int) s, lastFps, peakFps, newestEl, runRamMiB, runScreen, thermalMax,
                        low < 0 ? -1 : low / 1024);
            }
        }
    }

    /** The last 256 KB of @f (a QEMU's stderr), "" when unreadable. */
    private static String tail(File f) {
        try (RandomAccessFile r = new RandomAccessFile(f, "r")) {
            long from = Math.max(0, r.length() - (256 << 10));
            byte[] b = new byte[(int) (r.length() - from)];
            r.seek(from);
            r.readFully(b);
            return new String(b, StandardCharsets.ISO_8859_1);
        } catch (IOException e) {
            return "";
        }
    }

    private static long availMb() {
        long kb = CrashReport.memInfoKb("MemAvailable");
        return kb < 0 ? -1 : kb / 1024;
    }

    /** The cores QEMU @p may run on (Cpus_allowed_list of /proc/PID/status: the cpuset's doing), "-" when unreadable. */
    static String cpus(int p) {
        try {
            for (String l : java.nio.file.Files.readAllLines(new File("/proc/" + p + "/status").toPath(), StandardCharsets.ISO_8859_1)) {
                if (l.startsWith("Cpus_allowed_list:")) {
                    return l.substring(18).trim();
                }
            }
        } catch (IOException | RuntimeException e) {
            // gone already
        }
        return "-";
    }
}
