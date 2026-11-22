package com.asoft.ios;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

import org.junit.Test;

/**
 * The log-only "kernel:" and "kgsl import:" lines of gpucheck.c's kgsl_probe (and its "host memory: a shared memfd..."
 * line) must not move any decision: the judge sees the same verdict with and without them.
 */
public class GpuCheckKgslProbeTest {
    private static final List<String> PASSING = Arrays.asList(
            "loader: /data/app/x/files/links/libvulkan.so",
            "gpu: Turnip Adreno (TM) 740", "device api: Vulkan 1.3.0", "device: vkCreateDevice VkResult 0",
            "test: compute", "compute: 0 of 4096 words wrong", "test: render", "render: 0 of 4096 pixels wrong",
            "test: host memory",
            "host memory: a shared memfd mapping, its descriptor open while it is imported (as the engine's guest RAM)",
            "host import: memory types 0x2 (wanted 0x7)", "host import: memory type 1, flags 0xf",
            "host memory: 0 of 1048576 words the GPU wrote into the phone's own pages wrong",
            "test: sparse gather", "sparse gather: 0 of 256 pieces wrong",
            "result: pass");

    /** A phone the compatibility mode covers: it lacks only sparse binds from host memory, and ran every test. */
    private static final List<String> COMPAT = Arrays.asList(
            "gpu: Turnip Adreno (TM) 750", "device api: Vulkan 1.3.0", "device: vkCreateDevice VkResult 0",
            "test: compute", "compute: 0 of 4096 words wrong", "test: render", "render: 0 of 4096 pixels wrong",
            "test: host memory", "host import: memory type 1, flags 0xf",
            "host memory: 0 of 1048576 words the GPU wrote into the phone's own pages wrong",
            "test: sparse gather", "lacks: " + GpuCheck.SPARSE_HOST,
            "missing: " + GpuCheck.SPARSE_HOST,
            "result: fail");

    private static final List<String> PROBE = Arrays.asList(
            "kernel: 5.4.210-qgki",
            "kgsl import: anonymous shared mapping: ok",
            "kgsl import: memfd mapping, descriptor open: refused, Invalid argument (errno 22)",
            "kgsl import: memfd mapping, descriptor closed: ok",
            "kgsl import: memfd mapping, descriptor open, imported from a thread with its own descriptor table: ok",
            "kgsl import: the kernel takes a mapping of a file with an open descriptor: no");

    /** The probe lines sit before the result/missing lines, as check() prints them. */
    private static List<String> withProbe(List<String> log) {
        List<String> l = new ArrayList<>(log);
        int end = l.size();
        while (end > 0 && (l.get(end - 1).startsWith("result: ") || l.get(end - 1).startsWith("missing: "))) {
            end--;
        }
        l.addAll(end, PROBE);
        return l;
    }

    private static GpuCheck.Result sorted(List<String> log) {
        GpuCheck.Result r = new GpuCheck.Result();
        r.pass = GpuCheck.passes(log.contains("result: pass"), log);
        r.ran = true;
        if (!r.pass) {
            GpuCheck.sort(r, log, true, GpuCheck.hostCacheLack(log));
        }
        return r;
    }

    @Test
    public void aPassingLogStaysAPass() {
        List<String> with = withProbe(PASSING);
        assertTrue(with.size() > PASSING.size());
        assertEquals(GpuCheck.passes(true, PASSING), GpuCheck.passes(true, with));
        assertTrue(GpuCheck.passes(true, with));
        GpuCheck.Result a = sorted(PASSING), b = sorted(with);
        assertTrue(b.pass);
        assertEquals(a.pass, b.pass);
        assertEquals(a.never, b.never);
        assertEquals(a.why, b.why);
        assertEquals(GpuCheck.hostCacheLack(PASSING), GpuCheck.hostCacheLack(with));
        assertEquals(GpuCheck.framebufferFetchLack(PASSING), GpuCheck.framebufferFetchLack(with));
    }

    @Test
    public void theCompatibilityModeDecisionDoesNotChange() {
        List<String> with = withProbe(COMPAT);
        assertTrue(GpuCheck.fallbackPassOfLog(COMPAT));
        assertEquals(GpuCheck.fallbackPassOfLog(COMPAT), GpuCheck.fallbackPassOfLog(with));
        assertEquals(GpuCheck.systemPassOfLog(COMPAT), GpuCheck.systemPassOfLog(with));
        GpuCheck.Result a = sorted(COMPAT), b = sorted(with);
        assertEquals(a.pass, b.pass);
        assertEquals(a.never, b.never);
        assertEquals(a.why, b.why);
    }
}
