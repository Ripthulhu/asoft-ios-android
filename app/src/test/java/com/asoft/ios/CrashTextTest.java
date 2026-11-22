package com.asoft.ios;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.StringReader;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.junit.Test;

public class CrashTextTest {
    /** The newer engine's fatal line (the crash test's). */
    private static final String FATAL_552 = "reims-vgpu: fatal: platform call renderCommandEncoderWithDescriptor:: the Vulkan runtime"
            + " refused it: unsupported: Unsupported { feature: Format, needs: NotImplemented, location: None, symbol: None };"
            + " the pass's attachments: colour 0 552 (BGR10_XR) Type2D usage 0x4 Private";
    /** The older engine's, with Metal's own format names. */
    private static final String CAUSE_555 = "platform call renderCommandEncoderWithDescriptor:: the Vulkan runtime refused it:"
            + " unsupported: Unsupported { feature: Format, needs: NotImplemented, location: None, symbol: None }; the pass's"
            + " attachments: colour 0 555 (MTLPixelFormatBGR10_XR_sRGB) Type2D usage 0x4 Private";

    @Test
    public void fatalLinePicksTheLastAndDropsItsPrefix() {
        List<String> lines = Arrays.asList(
                "reims-vgpu: fatal: the first one",
                "something else",
                "[12.345] qemu: reims-vgpu: fatal: the last one",
                "after it");
        assertEquals("reims-vgpu: fatal: the last one", CrashText.fatalLine(lines));
        assertNull(CrashText.fatalLine(Arrays.asList("reims[warn] nothing fatal", "ok")));
    }

    @Test
    public void evidenceKeepsEarlyReimsLinesAndExactlyTheTail() throws IOException {
        StringBuilder log = new StringBuilder();
        log.append("reims[warn] create::function: Metal refused the function's IR\n");
        log.append("boring 0\n");
        log.append("reims[warn] create::function: Metal refused the function's IR\n");
        log.append("reims-vgpu: fatal: early\n");
        log.append("reims[warn] create::function: Metal refused the function's IR\n");
        for (int i = 1; i <= 500; i++) {
            log.append("line ").append(i).append('\n');
        }
        List<String> ev = CrashText.evidence(new BufferedReader(new StringReader(log.toString())), 200, 80);
        assertEquals("--- reims/panic lines before the last 200 lines ---", ev.get(0));
        assertEquals("reims[warn] create::function: Metal refused the function's IR (×3)", ev.get(1));
        assertEquals("reims-vgpu: fatal: early", ev.get(2));
        assertEquals("--- the last 200 lines ---", ev.get(3));
        assertEquals(4 + 200, ev.size());
        assertEquals("line 301", ev.get(4));
        assertEquals("line 500", ev.get(ev.size() - 1));
        assertFalse(ev.contains("boring 0"));
        // the fatal line before the tail is still found
        assertEquals("reims-vgpu: fatal: early", CrashText.fatalLine(ev));
    }

    @Test
    public void evidenceOfAShortLogIsAllTail() throws IOException {
        List<String> ev = CrashText.evidence(new BufferedReader(new StringReader("a\r\nreims[warn] x\nb")), 200, 80);
        assertEquals(Arrays.asList("--- the last 3 lines ---", "a", "reims[warn] x", "b"), ev);
    }

    @Test
    public void evidenceCountsWhatItLeavesOut() throws IOException {
        StringBuilder log = new StringBuilder();
        for (int i = 0; i < 10; i++) {
            log.append("reims[warn] distinct ").append(i).append('\n');
        }
        for (int i = 0; i < 5; i++) {
            log.append("tail ").append(i).append('\n');
        }
        List<String> ev = CrashText.evidence(new BufferedReader(new StringReader(log.toString())), 5, 4);
        assertEquals("reims[warn] distinct 3", ev.get(4));
        assertEquals("… 6 more distinct lines left out", ev.get(5));
    }

    @Test
    public void describeStatus() {
        assertEquals("signal 6 (SIGABRT)", CrashText.describeStatus(6));
        assertEquals("signal 6 (SIGABRT)", CrashText.describeStatus(0x86));     // with a core dump
        assertEquals("signal 9 (SIGKILL)", CrashText.describeStatus(9));
        assertEquals("exit code 1", CrashText.describeStatus(0x100));
        assertEquals("exit code 0", CrashText.describeStatus(0));
        assertEquals("unknown", CrashText.describeStatus(-1));
    }

    @Test
    public void isCrash() {
        assertFalse(CrashText.isCrash(0, null));
        assertTrue(CrashText.isCrash(0, "reims-vgpu: fatal: x"));
        assertTrue(CrashText.isCrash(6, null));
        assertTrue(CrashText.isCrash(0x100, null));
        assertTrue(CrashText.isCrash(-1, null));
    }

    @Test
    public void causeOfAFatalLine() {
        String c = CrashText.cause(FATAL_552, Collections.singletonList(FATAL_552), 6);
        assertTrue(c, c.startsWith("platform call renderCommandEncoderWithDescriptor:: the Vulkan runtime refused it"));
        assertTrue(c, c.contains("552 (BGR10_XR)"));
    }

    @Test
    public void causeOfARustPanicOnTwoLines() {
        List<String> tail = Arrays.asList(
                "something",
                "thread '<unnamed>' panicked at reims-vgpu/src/heap.rs:120:9:",
                "called `Option::unwrap()` on a `None` value",
                "note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace");
        assertEquals("thread '<unnamed>' panicked at reims-vgpu/src/heap.rs:120:9: called `Option::unwrap()` on a `None` value",
                CrashText.cause(null, tail, 6));
        // the older one-line form
        assertEquals("thread 'main' panicked at 'boom', src/main.rs:2:5",
                CrashText.cause(null, Arrays.asList("thread 'main' panicked at 'boom', src/main.rs:2:5", "note: x"), 0x6500));
    }

    @Test
    public void causeOfASigkillWithNoLines() {
        assertEquals("QEMU was ended by signal 9 (SIGKILL); Android ends an app's processes this way when the phone is short of memory",
                CrashText.cause(null, Collections.<String>emptyList(), 9));
        assertEquals("QEMU ended by itself", CrashText.cause(null, Collections.<String>emptyList(), -1));
        assertEquals("QEMU ended with exit code 1", CrashText.cause(null, Collections.singletonList("fine"), 0x100));
    }

    @Test
    public void sigkillTextOrdersTheCausesByMemory() {
        List<String> none = Collections.<String>emptyList();
        String mem = "Android ends an app's processes this way when the phone is short of memory";
        // below Android 12 the text stays as it was, whatever the samples say
        assertEquals("QEMU was ended by signal 9 (SIGKILL); " + mem, CrashText.cause(null, none, 9, 30, 5_000_000));
        // no sample, or a low one: memory first, the child process limit second
        String low = CrashText.cause(null, none, 9, 34, 200_000);
        assertTrue(low, low.startsWith("QEMU was ended by signal 9 (SIGKILL); " + mem + ". It may also be Android's limit on an app's child processes"));
        assertTrue(low, low.contains("Disable child process restrictions"));
        assertEquals(low, CrashText.cause(null, none, 9, 34, -1));
        assertEquals(low, CrashText.cause(null, none, 9, 31, CrashText.NOT_SHORT_KB - 1));
        // every sample at or above 1 GiB: the child process limit first
        String ok = CrashText.cause(null, none, 9, 34, CrashText.NOT_SHORT_KB);
        assertTrue(ok, ok.startsWith("QEMU was ended by signal 9 (SIGKILL); the phone did not look short of memory, so it may be Android's limit"));
        assertTrue(ok, ok.endsWith("Otherwise " + mem));
        // other signals are untouched
        assertEquals("QEMU was ended by signal 6 (SIGABRT)", CrashText.cause(null, none, 6, 34, 5_000_000));
    }

    @Test
    public void phantomSettingWords() {
        assertEquals("not set", CrashText.phantomSetting(null));
        assertEquals("not set", CrashText.phantomSetting(" "));
        assertEquals("false", CrashText.phantomSetting("false"));
    }

    @Test
    public void causeOfStorageAndAssertions() {
        assertEquals("the phone's storage was full",
                CrashText.cause(null, Arrays.asList("qcow2: write failed: No space left on device", "x"), 6));
        String a = CrashText.cause(null, Collections.singletonList(
                "qemu: ../hw/core/x.c:10: f: Assertion `n > 0' failed."), 6);
        assertTrue(a, a.startsWith("qemu: ../hw/core/x.c:10: f: Assertion `n > 0' failed."));
        assertTrue(a, a.endsWith("QEMU was ended by signal 6 (SIGABRT)"));
    }

    @Test
    public void shortCauseOfTheOldFormatStyle() {
        String s = CrashText.shortCause(CAUSE_555);
        assertTrue(s, s.contains("renderCommandEncoderWithDescriptor:"));
        assertTrue(s, s.contains("BGR10_XR_sRGB (555)"));
        assertTrue(s, s.length() <= 100);
    }

    @Test
    public void shortCauseOfTheNewFormatStyle() {
        String cause = CrashText.cause(FATAL_552, Collections.singletonList(FATAL_552), 6);
        assertEquals("renderCommandEncoderWithDescriptor:: BGR10_XR (552)", CrashText.shortCause(cause));
    }

    @Test
    public void shortCauseWithoutAFormat() {
        assertEquals("MTLCreateSystemDefaultDevice(): the Vulkan runtime refused it: Vulkan failure -13",
                CrashText.shortCause("platform call MTLCreateSystemDefaultDevice(): the Vulkan runtime refused it: Vulkan failure -13"));
        assertEquals("newBufferWithBytesNoCopy:length:options:deallocator:: unsupported HostMemory",
                CrashText.shortCause("platform call newBufferWithBytesNoCopy:length:options:deallocator:: the Vulkan runtime"
                        + " refused it: unsupported: Unsupported { feature: HostMemory, needs: NotImplemented }"));
        String longOne = "something went wrong in a way that takes many words to say, more than a title can hold, and then some more";
        String s = CrashText.shortCause(longOne);
        assertTrue(s, s.length() <= 100 && s.length() > 90);
        assertTrue(s, s.endsWith("…"));
    }

    @Test
    public void scrub() {
        Map<String, String> pre = new HashMap<>();
        pre.put("/data/user/0/com.asoft.ios.dev/files", "<files>");
        pre.put("/data/user/0/com.asoft.ios.dev", "<data>");
        pre.put("/data/data/com.asoft.ios.dev", "<data>");
        assertEquals("open <files>/run/x", CrashText.scrub("open /data/user/0/com.asoft.ios.dev/files/run/x", pre));
        assertEquals("<data>/cache/y", CrashText.scrub("/data/data/com.asoft.ios.dev/cache/y", pre));
        // without the app's folders the path still goes
        assertEquals("open <path>", CrashText.scrub("open /data/user/0/com.asoft.ios.dev/files/run/x", null));
        // a file the user named, space and all
        String s = CrashText.scrub("import /storage/emulated/0/Download/Ali Veli.asoft", pre);
        assertEquals("import <path>", s);
        assertEquals("file=<path>,if=none", CrashText.scrub("file=/sdcard/Download/a b.qcow2,if=none", pre));
        assertEquals("'<path>': No such file", CrashText.scrub("'/storage/emulated/0/x.asoft': No such file", pre));
        assertEquals("<lib>/libqemu26.so", CrashText.scrub("/data/app/~~AbC==/com.asoft.ios.dev-XyZ==/lib/arm64/libqemu26.so", pre));
        assertEquals("dns <ip>, guest 10.0.2.15, local 127.0.0.1, any 0.0.0.0",
                CrashText.scrub("dns 192.168.1.23, guest 10.0.2.15, local 127.0.0.1, any 0.0.0.0", pre));
        assertEquals("version v1.2.3.4 and 1.2.3.4.5", CrashText.scrub("version v1.2.3.4 and 1.2.3.4.5", pre));
        assertEquals("mail <email>", CrashText.scrub("mail someone@example.com", pre));
        assertEquals("AppIcon60x60@2x.png", CrashText.scrub("AppIcon60x60@2x.png", pre));
        assertEquals("wifi <mac>", CrashText.scrub("wifi 02:1A:2b:3c:4D:5e", pre));
        assertEquals("found adb-<id>._adb-tls-connect._tcp",
                CrashText.scrub("found adb-R5GYB4V4PKL-AbCdEf._adb-tls-connect._tcp", pre));
        assertEquals("built in /home/~/reims/target", CrashText.scrub("built in /home/alper/reims/target", pre));
        assertEquals("/Users/~/src and C:\\Users\\~\\src", CrashText.scrub("/Users/alper/src and C:\\Users\\alper\\src", pre));
    }

    @Test
    public void issueUrlEncodesSpacesAndNewlines() {
        String u = CrashText.issueUrl("o/r", "a b", "x\ny+z");
        assertEquals("https://github.com/o/r/issues/new?title=a%20b&body=x%0Ay%2Bz", u);
    }

    @Test
    public void bodyKeepsItsFences() {
        LinkedHashMap<String, String> facts = new LinkedHashMap<>();
        facts.put("App", "0.1.2 | dev");
        String b = CrashText.body(facts, "iOS 26 crashed", "cause", Collections.singletonList("a ``` b"),
                Collections.singletonList("app"), false);
        assertTrue(b, b.contains("| App | 0.1.2 \\| dev |"));
        assertTrue(b, b.contains("a ''' b"));
        assertFalse(b, b.contains("shortened"));
        assertTrue(b, b.endsWith("_Written by ASoftware's crash report; nothing was sent by itself._\n"));
    }

    @Test
    public void fitBodyKeepsTheEarlierReimsLines() throws IOException {
        StringBuilder in = new StringBuilder("reims[warn] create::function: Metal refused the function's IR\n");
        for (int i = 0; i < 600; i++) {
            in.append("native-el0: stats line ").append(i).append(" with some more words to make it longer\n");
        }
        in.append(FATAL_552).append('\n');
        List<String> ev = CrashText.evidence(new BufferedReader(new StringReader(in.toString())), 200, 80);
        LinkedHashMap<String, String> facts = new LinkedHashMap<>();
        facts.put("App", "0.1.2-dev (4)");
        String b = CrashText.fitBody("o/r", "t", facts, "w", FATAL_552, ev, Collections.singletonList("app"), 7000);
        assertTrue(CrashText.issueUrl("o/r", "t", b).length() <= 7000);
        assertTrue(b, b.contains("reims[warn] create::function"));
        assertTrue(b, b.contains("--- reims/panic lines before the last 200 lines ---"));
        // the tail lost its oldest lines, and says how many it kept
        assertTrue(b, b.contains("stats line 599 with"));
        assertFalse(b, b.contains("stats line 401 with"));
        assertFalse(b, b.contains("--- the last 200 lines ---"));
        assertTrue(b, b.matches("(?s).*--- the last \\d+ lines ---.*"));
    }

    @Test
    public void fitBodyStaysWithinTheLink() {
        LinkedHashMap<String, String> facts = new LinkedHashMap<>();
        facts.put("App", "0.1.2-dev (4)");
        facts.put("Phone", "samsung SM-S938B, SoC SM8750, Android 16 (SDK 36)");
        List<String> err = new ArrayList<>();
        for (int i = 0; i < 500; i++) {
            err.add("reims[info] a long line of QEMU's output number " + i + " with some more words to make it longer");
        }
        List<String> app = new ArrayList<>();
        for (int i = 0; i < 150; i++) {
            app.add("11-10 12:00:00 app line " + i);
        }
        String title = "iOS 26: renderCommandEncoderWithDescriptor:: BGR10_XR (552)";
        String cause = CrashText.cause(FATAL_552, Collections.singletonList(FATAL_552), 6);
        String b = CrashText.fitBody("alpersamur3/asoft-ios-android", title, facts, "iOS 26 crashed", FATAL_552, err, app, 7000);
        String url = CrashText.issueUrl("alpersamur3/asoft-ios-android", title, b);
        assertTrue(url.length() + " > 7000", url.length() <= 7000);
        assertTrue(url.length() + " is far below 7000", url.length() > 6000);
        assertTrue(b.contains(FATAL_552));
        assertTrue(b.contains(cause));
        assertTrue(b.contains("_The logs were shortened"));
        // the newest lines stay
        assertTrue(b.contains("number 499 with"));
        assertTrue(b.contains("app line 149"));
        assertFalse(b.contains("number 0 with"));
        // a short report goes whole
        String whole = CrashText.fitBody("o/r", "t", facts, "w", "c", err.subList(0, 3), app.subList(0, 3), 7000);
        assertFalse(whole.contains("_The logs were shortened"));
        assertTrue(whole.contains("number 2 with"));
    }

    // -- a helper VM's end (Helper.Result.failure)

    @Test
    public void helperKilledForMemorySaysSoAndWhatItWasDoing() {
        assertEquals("the helper VM was killed (signal 9, probably Android freeing memory) while unpacking the iOS images (7137 MB)",
                CrashText.helperFailure(-1, 9, null, "unpacking the iOS images (7137 MB)", "tar: something"));
        assertTrue(CrashText.killedForMemory(9));
        assertFalse(CrashText.killedForMemory(6));
        assertFalse(CrashText.killedForMemory(0x900));      // exit code 9 is not signal 9
        assertFalse(CrashText.killedForMemory(-1));
        // without a progress line yet
        assertEquals("the helper VM was killed (signal 9, probably Android freeing memory)",
                CrashText.helperFailure(-1, 9, null, "", ""));
    }

    @Test
    public void helperJobExitCodeKeepsTheScriptsLastWords() {
        assertEquals("its job failed with exit code 1 while checking the disk: fsck_hfs: volume needs repair",
                CrashText.helperFailure(1, 0, null, "checking the disk", "fsck_hfs: volume needs repair"));
        assertEquals("its job failed with exit code 2", CrashText.helperFailure(2, 0, null, null, null));
        // its own exit code wins over how QEMU ended after it
        assertTrue(CrashText.helperFailure(3, 9, null, "", "").startsWith("its job failed with exit code 3"));
    }

    @Test
    public void helperOtherEnds() {
        assertEquals("the helper VM crashed (signal 11 (SIGSEGV)) while x", CrashText.helperFailure(-1, 11, null, "x", ""));
        assertEquals("the helper VM's QEMU ended with exit code 1", CrashText.helperFailure(-1, 0x100, null, "", ""));
        assertEquals("the helper VM stopped before its job was done while y", CrashText.helperFailure(-1, 0, null, " y ", ""));
        assertEquals("the helper VM stopped before its job was done", CrashText.helperFailure(-1, -1, null, "", ""));
        // the app ended it as hung: its words first
        assertEquals("the helper VM stopped making progress (5 minutes) while z",
                CrashText.helperFailure(-1, -1, "the helper VM stopped making progress (5 minutes)", "z", ""));
    }

    @Test
    public void helperLastOutputIsCapped() {
        StringBuilder l = new StringBuilder();
        for (int i = 0; i < 100; i++) {
            l.append("word ");
        }
        String s = CrashText.helperFailure(1, 0, null, "", l.toString());
        assertTrue(s, s.length() < 350);
    }

    // -- the app's own end (AppExit)

    @Test
    public void exitWeightKeepsTheUsersEndsOut() {
        assertEquals(-1, CrashText.exitWeight(CrashText.EXIT_USER_REQUESTED, "force stop"));
        assertEquals(-1, CrashText.exitWeight(CrashText.EXIT_USER_STOPPED, null));
        assertEquals(-1, CrashText.exitWeight(CrashText.EXIT_PACKAGE_UPDATED, null));
        assertEquals(-1, CrashText.exitWeight(CrashText.EXIT_SELF, null));
        assertEquals(-1, CrashText.exitWeight(CrashText.EXIT_OTHER, "remove task"));
        assertEquals(0, CrashText.exitWeight(CrashText.EXIT_OTHER, "something else"));
        assertEquals(0, CrashText.exitWeight(CrashText.EXIT_LOW_MEMORY, null));
        assertEquals(0, CrashText.exitWeight(CrashText.EXIT_SIGNALED, null));
        assertEquals(0, CrashText.exitWeight(CrashText.EXIT_UNKNOWN, null));
        assertEquals(1, CrashText.exitWeight(CrashText.EXIT_CRASH, null));
        assertEquals(1, CrashText.exitWeight(CrashText.EXIT_CRASH_NATIVE, null));
        assertEquals(1, CrashText.exitWeight(CrashText.EXIT_ANR, null));
    }

    @Test
    public void exitWordsAndSummary() {
        assertEquals("The app was closed by Android while the iOS 16 setup was running: low memory",
                CrashText.appExitSummary(CrashText.EXIT_LOW_MEMORY, 0, null, "the iOS 16 setup was running"));
        assertEquals("The app was closed by Android while iOS 26 was running: killed (signal 9), usually Android freeing memory",
                CrashText.appExitSummary(CrashText.EXIT_SIGNALED, 9, null, "iOS 26 was running"));
        assertEquals("The app crashed: a crash in its native code (signal 11 (SIGSEGV))",
                CrashText.appExitSummary(CrashText.EXIT_CRASH_NATIVE, 11, null, null));
        assertEquals("The app crashed while an import from the PC was running: a crash (a Java exception)",
                CrashText.appExitSummary(CrashText.EXIT_CRASH, 0, null, "an import from the PC was running"));
        assertEquals("The app stopped responding while x, and Android closed it",
                CrashText.appExitSummary(CrashText.EXIT_ANR, 0, null, "x"));
        assertEquals("The app was closed while x (Android 10 does not tell apps why)",
                CrashText.appExitSummary(CrashText.EXIT_NOT_KEPT, 0, null, "x"));
        assertEquals("ended by signal 15 (SIGTERM)", CrashText.exitWords(CrashText.EXIT_SIGNALED, 15, null));
        assertEquals("Android did not say why", CrashText.exitWords(CrashText.EXIT_UNKNOWN, 0, null));
        assertEquals("LOW_MEMORY (3)", CrashText.exitName(CrashText.EXIT_LOW_MEMORY));
        assertEquals("not kept (-2)", CrashText.exitName(CrashText.EXIT_NOT_KEPT));
        assertEquals("reason (99)", CrashText.exitName(99));
    }

    @Test
    public void makerBatteryManagerKillIsNamed() {
        String w = CrashText.exitWords(CrashText.EXIT_OTHER, 0, "o-kill(6)");
        assertTrue(w, w.contains("battery manager"));
        assertTrue(w, w.contains("(o-kill(6))"));
        assertTrue(w, w.contains("without restrictions"));
        assertEquals(0, CrashText.exitWeight(CrashText.EXIT_OTHER, "O-Kill(6)"));
        // an unknown description is still shown raw
        assertEquals("Android closed it (something else)", CrashText.exitWords(CrashText.EXIT_OTHER, 0, "something else"));
        assertFalse(CrashText.makerKill(null));
    }

    // -- why QEMU ended, in a shortened link

    private static final String SAMPLE_LINE = "el-sample t=1234.5 vcpu0 el0=6% tcg=71% futex=46% tlbi=12 stubs=24 "
            + "rss=5120M maps=4800 gpu=idle q=0 ipc=0.8 irq=1200 wfi=88% syscalls=91000 pf=12 tlbflush=3 ".repeat(2);
    private static final String MAPPINGS_FATAL = "reims-vgpu: fatal: platform call mmap: the library's views of memory ran out of kernel"
            + " mappings (vm.max_map_count 65530) while mapping a texture heap; " + "the engine cannot go on and ends here ".repeat(10);

    private static List<String> samplesThen(String... first) throws IOException {
        StringBuilder in = new StringBuilder();
        for (String f : first) {
            in.append(f).append('\n');
        }
        for (int i = 0; i < 300; i++) {
            in.append(SAMPLE_LINE).append(i).append('\n');
        }
        return CrashText.evidence(new BufferedReader(new StringReader(in.toString())), 200, 80);
    }

    @Test
    public void longFatalLineSurvivesTheSamplesAfterIt() throws IOException {
        assertTrue(MAPPINGS_FATAL.length() > 400);
        List<String> ev = samplesThen(MAPPINGS_FATAL);
        LinkedHashMap<String, String> facts = new LinkedHashMap<>();
        facts.put("App", "0.1.5");
        String cause = CrashText.cause(CrashText.fatalLine(ev), ev, 6);
        assertEquals(true, cause.startsWith("platform call mmap"));
        // the fatal line is only in the head, and the room is small
        for (int max : new int[] {3000, 2500, 2200}) {
            String b = CrashText.fitBody("o/r", "t", facts, "w", "c", ev, Collections.singletonList("app"), max);
            assertTrue(CrashText.issueUrl("o/r", "t", b).length() <= max);
            assertTrue(max + ": " + b, b.contains("reims-vgpu: fatal: platform call mmap"));
            assertFalse(b, b.contains("el-sample"));
        }
        assertEquals("Android's limit of 65,530 memory mappings per app was reached",
                CrashText.cause(null, ev, 6));
    }

    /** What the engine prints at every start, and in its census: both name the limit, neither says it was reached. */
    private static final String MAPPINGS_WARNING = "reims[warn] reims_vgpu_vulkan::os: vm.max_map_count is 65530: views of guest"
            + " memory end the process past 49146 mappings, about 767 MiB of the guest's 4133 MiB in 16 KiB pieces;"
            + " `sysctl -w vm.max_map_count=1048576` or more lets them cover it";
    private static final String CENSUS = "reims[info] reims_vgpu_vulkan::os: reims-vgpu: views census: held 3 of budget 49146"
            + " (vm.max_map_count 65530); aliases 0";
    /** The phone's own driver without the host import (Qualcomm's, 2026-11-15). */
    private static final String FATAL_HOST = "reims-vgpu: fatal: platform call newBufferWithBytesNoCopy:length:options:deallocator::"
            + " the Vulkan runtime refused it: unsupported: Unsupported { feature: HostMemory, needs:"
            + " AnyOf([[Extension(ExtExternalMemoryHost)]]), location: None, symbol: None }";

    @Test
    public void namingTheMappingLimitIsNotReachingIt() {
        assertFalse(CrashText.mappingsRanOut(MAPPINGS_WARNING));
        assertFalse(CrashText.mappingsRanOut(CENSUS));
        assertTrue(CrashText.mappingsRanOut(MAPPINGS_FATAL));
        assertTrue(CrashText.mappingsRanOut("reims-vgpu: fatal: platform call mmap: the process ran out of kernel mappings: the"
                + " kernel refused a view (ENOMEM) with 65529 of vm.max_map_count 65530 held"));
        // a map the kernel refused short of the limit is a lack of memory, not of mappings
        assertFalse(CrashText.mappingsRanOut("reims[error] reims_vgpu_vulkan::os: a view: the kernel refused the map (ENOMEM):"
                + " the process has 4100 mappings, vm.max_map_count is 65530"));
        // a run that ended in its first seconds on a save this host could not load (record 20261115-191907)
        List<String> ev = Arrays.asList(MAPPINGS_WARNING, CENSUS,
                "qemu: resume refused: this host lacks what the suspended guest asked for");
        assertEquals("QEMU ended with exit code 1", CrashText.cause(null, ev, 1 << 8));
        // ...and one the engine ended for another reason says that reason
        List<String> host = Arrays.asList(MAPPINGS_WARNING, CENSUS, FATAL_HOST);
        String cause = CrashText.cause(CrashText.fatalLine(host), host, 6);
        assertTrue(cause, cause.startsWith("platform call newBufferWithBytesNoCopy"));
    }

    @Test
    public void graphicsStopSaysTheMappingLimitOnlyWhenItWasReached() {
        String start = MAPPINGS_WARNING + "\n" + CENSUS + "\n";
        assertNull(CrashText.graphicsStop(start + "qemu: resume refused: this host lacks what the suspended guest asked for\n", ""));
        String refused = CrashText.graphicsStop(start + FATAL_HOST + "\n", "");
        assertTrue(refused, refused.startsWith("the phone's GPU driver refused to take the memory iOS draws with"));
        String other = CrashText.graphicsStop(start + "reims-vgpu: fatal: platform call newTextureWithDescriptor: the Vulkan"
                + " runtime refused it: unsupported: Unsupported { feature: Format, needs: NotImplemented }\n", "");
        assertTrue(other, other.startsWith("its graphics asked the phone's GPU for something"));
        String full = CrashText.graphicsStop(start + MAPPINGS_FATAL + "\n", "");
        assertTrue(full, full.contains("65,530 memory mappings"));
        // the last error line alone may carry it (a stderr longer than the tail read)
        assertTrue(CrashText.graphicsStop("", MAPPINGS_FATAL).contains("65,530 memory mappings"));
        assertNull(CrashText.graphicsStop("", ""));
    }

    @Test
    public void singleOverLongNotableLineIsShortenedNotDropped() {
        String longWarn = "reims[warn] " + "a very long warning that goes on and on ".repeat(60);
        List<String> err = new ArrayList<>();
        err.add("--- reims/panic lines before the last 200 lines ---");
        err.add(longWarn);
        err.add("--- the last 3 lines ---");
        err.addAll(Arrays.asList("t1", "t2", "t3"));
        List<String> fit = CrashText.fitStderr(err, 1000);
        assertEquals("--- reims/panic lines before the last 200 lines ---", fit.get(0));
        String kept = fit.get(1);
        assertTrue(kept, kept.startsWith("reims[warn] a very long warning"));
        assertTrue(kept, kept.endsWith("…"));
        assertTrue(kept.length() < longWarn.length());
        assertTrue(fit.contains("t3"));
    }

    @Test
    public void fatalLineBeatsOtherHeadLines() {
        String fatal = "reims-vgpu: fatal: " + "x".repeat(900);
        List<String> err = new ArrayList<>();
        err.add("--- reims/panic lines before the last 200 lines ---");
        err.add(fatal);
        for (int i = 0; i < 20; i++) {
            err.add("reims[warn] newer warning number " + i);
        }
        err.add("--- the last 1 lines ---");
        err.add("end");
        List<String> fit = CrashText.fitStderr(err, 1200);
        boolean has = false;
        for (String l : fit) {
            has |= l.startsWith("reims-vgpu: fatal: x");
        }
        assertTrue(fit.toString(), has);
        assertTrue(fit.contains("end"));
    }

    @Test
    public void glibAssertionIsTheCause() {
        List<String> lines = Arrays.asList("--- the last 3 lines ---", "ok",
                "ERROR:../foo.c:12:bar: assertion failed: (x)", "Bail out! ERROR:../foo.c:12:bar: assertion failed: (x)");
        assertTrue(CrashText.cause(null, lines, 0x100).contains("assertion failed: (x)"));
        // a bare "Bail out!" after it
        lines = Arrays.asList("ERROR:../foo.c:12:bar: assertion failed: (x)", "Bail out!");
        assertEquals("ERROR:../foo.c:12:bar: assertion failed: (x)", CrashText.cause(null, lines, 0x100));
        assertTrue(CrashText.cause(null, lines, 6).startsWith("ERROR:../foo.c:12:bar: assertion failed: (x); QEMU was ended by signal 6"));
        // a statistics line is never the cause
        assertEquals("QEMU ended with exit code 1", CrashText.cause(null, Arrays.asList(SAMPLE_LINE + " errors=0"), 0x100));
    }

    @Test
    public void samplesAreInTheFullTextNotInTheLink() throws IOException {
        List<String> ev = samplesThen("reims[warn] early warning");
        LinkedHashMap<String, String> facts = new LinkedHashMap<>();
        facts.put("App", "0.1.5");
        List<String> app = Collections.singletonList("app");
        String whole = CrashText.body(facts, "w", "c", ev, app, false);
        assertTrue(whole.contains("el-sample"));
        String link = CrashText.fitBody("o/r", "t", facts, "w", "c", ev, app, 100_000);
        assertFalse(link, link.contains("el-sample"));
        assertTrue(link.contains("reims[warn] early warning"));
        // el-sample lines are not kept as notable ones
        List<String> kept = CrashText.evidence(new BufferedReader(new StringReader(SAMPLE_LINE + "\n" + "x\n".repeat(300))), 5, 80);
        assertFalse(kept.toString(), kept.get(0).startsWith("--- reims"));
        // and QEMU's own last words, glib's assertions and the allocator's notes are
        kept = CrashText.evidence(new BufferedReader(new StringReader("qemu-system-aarch64: out of memory\nScudo ERROR: x\n"
                + "x\n".repeat(300))), 5, 80);
        assertEquals("qemu-system-aarch64: out of memory", kept.get(1));
        assertEquals("Scudo ERROR: x", kept.get(2));
    }

    // -- a record's file (CrashReport)

    private static LinkedHashMap<String, String> header() {
        LinkedHashMap<String, String> h = new LinkedHashMap<>();
        h.put("id", "20261112-101500-setup");
        h.put("kind", "setup");
        h.put("what", "iOS 16 setup stopped at Build the iOS disk");
        h.put("cause", "building the iOS disk failed: the helper VM was killed\n(signal 9)");
        return h;
    }

    @Test
    public void recordRoundTrip() {
        LinkedHashMap<String, List<String>> s = new LinkedHashMap<>();
        s.put("helper console", Arrays.asList("ASOFT: progress 2 unpacking", "== asoft: not a section ==", ""));
        s.put(CrashText.RUN_APPLOG, Collections.singletonList("11-12 10:15:00 setup: begin"));
        List<String> lines = CrashText.recordLines(header(), s, 200_000);
        assertEquals(CrashText.MAGIC + " 1", lines.get(0));
        assertTrue(lines.contains("cause: building the iOS disk failed: the helper VM was killed (signal 9)"));
        CrashText.Parsed p = CrashText.parseRecord(lines);
        assertEquals(Arrays.asList("id", "kind", "what", "cause"), new ArrayList<>(p.header.keySet()));
        assertEquals("setup", p.header.get("kind"));
        assertEquals(Arrays.asList("helper console", CrashText.RUN_APPLOG), new ArrayList<>(p.sections.keySet()));
        // a log line that looks like a section's header stays in its section, with a space before it
        assertEquals(Arrays.asList("ASOFT: progress 2 unpacking", " == asoft: not a section ==", ""), p.sections.get("helper console"));
        assertNull(CrashText.parseRecord(Arrays.asList("not a record", "kind: x")));
        assertNull(CrashText.parseRecord(Collections.<String>emptyList()));
    }

    @Test
    public void recordOfTheOldGuestFormat() {
        List<String> old = Arrays.asList(CrashText.MAGIC + " 1", "os: ios26", "cause: c", CrashText.OLD_STDERR, "e1", "e2",
                CrashText.OLD_APPLOG, "a1");
        CrashText.Parsed p = CrashText.parseRecord(old);
        assertEquals("ios26", p.header.get("os"));
        assertEquals(Arrays.asList("e1", "e2"), p.sections.get(CrashText.QEMU_STDERR));
        assertEquals(Collections.singletonList("a1"), p.sections.get(CrashText.RUN_APPLOG));
    }

    private static int bytes(List<String> lines) {
        int n = 0;
        for (String l : lines) {
            n += l.getBytes(java.nio.charset.StandardCharsets.UTF_8).length + 1;
        }
        return n;
    }

    @Test
    public void recordStaysWithinItsSize() {
        List<String> big = new ArrayList<>(), small = new ArrayList<>();
        for (int i = 0; i < 5000; i++) {
            big.add("console line " + i + " with some words to make it longer than a few bytes");
        }
        StringBuilder huge = new StringBuilder();
        for (int i = 0; i < 2000; i++) {
            huge.append('x');
        }
        small.add(huge.toString());
        small.add("the newest app line");
        LinkedHashMap<String, List<String>> s = new LinkedHashMap<>();
        s.put("helper console", big);
        s.put(CrashText.RUN_APPLOG, small);
        List<String> lines = CrashText.recordLines(header(), s, 50_000);
        assertTrue(bytes(lines) + " > 50000", bytes(lines) <= 50_000);
        CrashText.Parsed p = CrashText.parseRecord(lines);
        List<String> con = p.sections.get("helper console");
        // the big section lost its oldest lines, says so, and kept its newest
        assertTrue(con.get(0), con.get(0).matches("… \\d+ older lines left out \\(the record's size limit\\)"));
        assertEquals("console line 4999 with some words to make it longer than a few bytes", con.get(con.size() - 1));
        assertFalse(con.contains("console line 0 with some words to make it longer than a few bytes"));
        // the small one stays, its long line cut to 500 characters
        List<String> app = p.sections.get(CrashText.RUN_APPLOG);
        assertEquals(2, app.size());
        assertEquals(501, app.get(0).length());
        assertEquals("the newest app line", app.get(1));
        // within its size nothing is cut
        List<String> whole = CrashText.recordLines(header(), s, 10_000_000);
        assertEquals(2000, CrashText.parseRecord(whole).sections.get(CrashText.RUN_APPLOG).get(0).length());
    }

    // -- an issue with any logs

    @Test
    public void fitBodyOfBlocksSharesTheRoomByWeight() {
        LinkedHashMap<String, String> facts = new LinkedHashMap<>();
        facts.put("App", "0.1.5-dev (7)");
        List<String> console = new ArrayList<>(), stderr = new ArrayList<>(), app = new ArrayList<>();
        for (int i = 0; i < 400; i++) {
            console.add("console line " + i + " with some more words to make it longer");
            stderr.add("stderr line " + i + " with some more words to make it longer");
            app.add("app line " + i + " with some more words to make it longer");
        }
        List<CrashText.Block> blocks = new ArrayList<>();
        blocks.add(new CrashText.Block("Helper console", console, 2));
        blocks.add(new CrashText.Block("Helper QEMU stderr", stderr, 2));
        blocks.add(new CrashText.Block("App log", app, 1));
        blocks.add(new CrashText.Block("Short one", Collections.singletonList("the only line"), 1));
        String b = CrashText.fitBody("o/r", "t", facts, "w", "c", blocks, 4500);
        assertTrue(CrashText.issueUrl("o/r", "t", b).length() <= 4500);
        assertTrue(CrashText.issueUrl("o/r", "t", b).length() > 4000);
        assertTrue(b.contains("_The logs were shortened"));
        // every block keeps its newest line, the short one all of it
        assertTrue(b.contains("console line 399 with"));
        assertTrue(b.contains("stderr line 399 with"));
        assertTrue(b.contains("app line 399 with"));
        assertTrue(b.contains("the only line"));
        // the weight-2 blocks got about twice the app log's room
        int c = count(b, "console line "), a = count(b, "app line ");
        assertTrue(c + " vs " + a, c > a * 3 / 2);
    }

    private static int count(String s, String what) {
        int n = 0;
        for (int i = s.indexOf(what); i >= 0; i = s.indexOf(what, i + 1)) {
            n++;
        }
        return n;
    }

    // -- the helper VM's RAM (Helper)

    @Test
    public void helperRamFollowsThePhone() {
        long gb = 1_000_000_000L;
        // what phones report as MemTotal: a little under their label
        assertEquals(4096, Helper.sizeFor(11_200_000_000L, Helper.FLOOR_WORK_IN_RAM));     // 12 GB (the S25 Ultra)
        assertEquals(4096, Helper.sizeFor(15 * gb, Helper.FLOOR_IOS16));                    // 16 GB: never above 4 GiB
        assertEquals(3072, Helper.sizeFor(7_400_000_000L, Helper.FLOOR_IOS16));            // 8 GB
        assertEquals(2048, Helper.sizeFor(5_600_000_000L, Helper.FLOOR_IOS16));            // 6 GB
        assertEquals(1536, Helper.sizeFor(3_700_000_000L, Helper.FLOOR_IOS16));            // 4 GB
        // the jobs that keep their work in RAM never get less than 2 GiB
        assertEquals(2048, Helper.sizeFor(3_700_000_000L, Helper.FLOOR_WORK_IN_RAM));
    }

    @Test
    public void helperRetryStepsDownAfterTheMemoryKiller() {
        assertEquals(3072, Helper.smaller(4096, Helper.FLOOR_IOS16));
        assertEquals(1536, Helper.smaller(2048, Helper.FLOOR_IOS16));
        assertEquals(1536, Helper.smaller(1536, Helper.FLOOR_IOS16));
        assertEquals(2048, Helper.smaller(2048, Helper.FLOOR_WORK_IN_RAM));
        Helper.Result r = new Helper.Result();
        r.ramMiB = 3072;
        r.status = 9;
        assertTrue(r.killedForMemory());
        assertTrue(Helper.worthRetry(r, Helper.FLOOR_WORK_IN_RAM));
        assertEquals(2048, Helper.retryRam(r, Helper.FLOOR_WORK_IN_RAM));
        // at the floor already: no retry under TCG (it would end the same way), unless it ran native
        r.ramMiB = 2048;
        assertFalse(Helper.worthRetry(r, Helper.FLOOR_WORK_IN_RAM));
        r.nat = true;
        assertTrue(Helper.worthRetry(r, Helper.FLOOR_WORK_IN_RAM));
        assertEquals(2048, Helper.retryRam(r, Helper.FLOOR_WORK_IN_RAM));
        // a job's own failure under native: the retry keeps the size
        Helper.Result j = new Helper.Result();
        j.nat = true;
        j.rc = 1;
        j.status = 0;
        j.ramMiB = 4096;
        assertFalse(j.killedForMemory());
        assertTrue(Helper.worthRetry(j, Helper.FLOOR_IOS16));
        assertEquals(4096, Helper.retryRam(j, Helper.FLOOR_IOS16));
        // done (rc 0): nothing to retry
        j.rc = 0;
        assertFalse(Helper.worthRetry(j, Helper.FLOOR_IOS16));
    }

    // -- reports from a log (title, nothing to report, the same report twice, the GPU family)

    @Test
    public void logTitleComesFromTheLastStopOrHoldLine() {
        List<String> log = Arrays.asList(
                "11-13 17:13:22 setup: payload 0%: The kernel",
                "11-13 17:14:05 setup stopped: Not enough room: 1.4 GB free, about 26.5 GB needed",
                "11-13 17:40:00 setup: disk 40%: copying iOS",
                "11-13 18:19:12 helper build-root: held (the phone is hot)",
                "11-13 18:20:00 update check: nothing newer than 0.1.5");
        assertEquals("helper build-root: held (the phone is hot)", CrashText.telling(log));
        assertEquals("Helper build-root: held (the phone is hot)", CrashText.logTitle(CrashText.telling(log)));
        // an earlier stop counts when nothing later does
        assertEquals("setup stopped: Not enough room: 1.4 GB free, about 26.5 GB needed", CrashText.telling(log.subList(0, 3)));
        assertEquals("Setup stopped: Not enough room: 1.4 GB free, about 26.5 GB needed",
                CrashText.logTitle(CrashText.telling(log.subList(0, 3))));
        assertTrue(CrashText.logTitle(CrashText.telling(Arrays.asList("11-13 18:00:00 app crash: " + "x".repeat(300)))).length() <= 100);
    }

    @Test
    public void aLogOfRoutineLinesHasNothingToReport() {
        assertNull(CrashText.telling(Arrays.asList("11-13 16:32:08 update check: nothing newer than 0.1.5")));
        assertNull(CrashText.telling(Collections.<String>emptyList()));
        // start-up, progress, slow servers, an update check that failed, the GPU check (it has its own log)
        assertNull(CrashText.telling(Arrays.asList(
                "11-13 17:03:41 setup: start (30 GB free)",
                "11-13 17:04:13 setup: x.dmg: chunk 110 at 2 MB, retry 1: slow server (93 KB/s, the others 372 KB/s)",
                "11-13 17:13:23 helper: short of memory: 1.4 GB available, the VM takes up to 2.1 GB",
                "11-13 17:13:24 update check failed: java.net.UnknownHostException",
                "11-13 16:48:50 gpu check: not supported yet: sparse memory binding (turnip skipped)")));
    }

    @Test
    public void theSameReportTwiceInOneDayIsRemembered() {
        String a = CrashText.reportKey("2026-11-14", "setup", "Not enough room: 1.4 GB free");
        assertEquals(a, CrashText.reportKey("2026-11-14", "setup", " Not enough room: 1.4 GB free "));
        java.util.Set<String> opened = CrashText.rememberReport(new java.util.HashSet<String>(), "2026-11-14", a);
        assertTrue(opened.contains(a));
        // another cause, another kind, another day: a new report
        assertFalse(opened.contains(CrashText.reportKey("2026-11-14", "setup", "Not enough room: 2.0 GB free")));
        assertFalse(opened.contains(CrashText.reportKey("2026-11-14", "guest", "Not enough room: 1.4 GB free")));
        assertFalse(opened.contains(CrashText.reportKey("2026-11-15", "setup", "Not enough room: 1.4 GB free")));
        // the next day's list holds the old key no more
        String b = CrashText.reportKey("2026-11-15", "setup", "x");
        java.util.Set<String> next = CrashText.rememberReport(opened, "2026-11-15", b);
        assertEquals(1, next.size());
        assertTrue(next.contains(b));
    }

    @Test
    public void gpuFamilyComesFromTheGpuName() {
        assertEquals("Mali", CrashText.gpuFamily("Mali-G720 MC7"));
        assertEquals("Mali", CrashText.gpuFamily("Mali-G57"));
        assertEquals("PowerVR", CrashText.gpuFamily("PowerVR B-Series BXM-8-256"));
        assertEquals("Xclipse", CrashText.gpuFamily("Samsung Xclipse 940"));
        assertEquals("Adreno 618", CrashText.gpuFamily("Adreno (TM) 618"));
        assertEquals("", CrashText.gpuFamily(""));
        assertEquals("Foo", CrashText.gpuFamily("Foo 3000"));
        assertEquals("Mali-G720 MC7", CrashText.gpuName("== the phone's own Vulkan driver\ngpu: Mali-G720 MC7\ndriver: x\n"));
        assertEquals("", CrashText.gpuName("result: fail\n"));
        assertEquals("https://github.com/o/r/issues?q=is%3Aissue%20Mali", CrashText.gpuIssuesUrl("o/r", "Mali"));
    }

    @Test
    public void theQuestionComesFirstInTheBody() {
        String b = CrashText.body(new LinkedHashMap<String, String>(), "w", "c", new ArrayList<CrashText.Block>(), false);
        assertTrue(b.startsWith("**What were you doing, and what went wrong?**"));
    }

    @Test
    public void aSigkillDuringAHelperJobCountsAsAMemoryKill() {
        assertTrue(CrashText.memoryKill(CrashText.EXIT_LOW_MEMORY, 0));
        assertTrue(CrashText.memoryKill(CrashText.EXIT_SIGNALED, 9));       // A#282
        assertFalse(CrashText.memoryKill(CrashText.EXIT_SIGNALED, 6));      // an abort is not
        assertFalse(CrashText.memoryKill(CrashText.EXIT_CRASH_NATIVE, 9));
        assertFalse(CrashText.memoryKill(CrashText.EXIT_USER_REQUESTED, 9));
    }
}
