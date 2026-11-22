package com.asoft.ios;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

import org.junit.Test;

/** The cache-sync lack of the GPU check: a host import that works only with cache syncs, which the engine does only in part. */
public class GpuCheckCacheTest {
    private static final String NOT_COHERENT = GpuCheck.HOST_NOT_COHERENT + " (flags 0xb)";

    /** A driver with a coherent import: every test passes (Snapdragons, the S25). */
    private static final List<String> COHERENT = Arrays.asList(
            "gpu: Some GPU", "device api: Vulkan 1.3.0", "device: vkCreateDevice VkResult 0",
            "test: compute", "compute: 0 of 4096 words wrong", "test: render", "render: 0 of 4096 pixels wrong",
            "test: host memory", "host import: memory types 0x2 (wanted 0x7)", "host import: memory type 1, flags 0xf",
            "host memory: 0 of 1048576 words the GPU wrote into the phone's own pages wrong",
            "test: sparse gather", "sparse gather: 0 of 256 pieces wrong",
            "result: pass");

    private static List<String> with(List<String> log, String line) {
        List<String> l = new ArrayList<>(log);
        l.add(l.indexOf("host import: memory type 1, flags 0xf") + 1, line);
        return l;
    }

    /** Mali-G1-Ultra: the only importable type is 1 (flags 0xb), cached and not coherent; no sparse binding. */
    private static final List<String> MALI_G1 = Arrays.asList(
            "gpu: Mali-G1-Ultra", "device api: Vulkan 1.3.0", "device: vkCreateDevice VkResult 0",
            "lacks: sparseBinding", "lacks: sparseResidencyBuffer", "lacks: a queue that binds sparse memory",
            "test: compute", "compute: 0 of 4096 words wrong", "test: render", "render: 0 of 4096 pixels wrong",
            "test: host memory", "host import: memory types 0x2 (wanted 0x7)", "host import: memory type 1, flags 0xb",
            NOT_COHERENT,
            "host memory: 0 of 1048576 words the GPU wrote into the phone's own pages wrong",
            "missing: sparseBinding, sparseResidencyBuffer, a queue that binds sparse memory",
            "result: fail");

    private static GpuCheck.Result sorted(List<String> log, boolean adreno) {
        GpuCheck.Result r = new GpuCheck.Result();
        r.pass = GpuCheck.passes(log.contains("result: pass"), log);
        r.ran = true;
        if (!r.pass) {
            GpuCheck.sort(r, log, adreno, GpuCheck.hostCacheLack(log));
        }
        return r;
    }

    @Test
    public void allTestsPassedButTheImportNeedsSyncsIsNoPass() {
        List<String> log = with(COHERENT, NOT_COHERENT);
        assertFalse(GpuCheck.passes(true, log));
        GpuCheck.Result r = sorted(log, false);
        assertFalse(r.pass);
        assertFalse(r.never);
        assertTrue(r.why.contains(GpuCheck.HOST_CACHE_SYNC));
    }

    @Test
    public void theSameLogWithoutTheLineStaysAPass() {
        assertNull(GpuCheck.hostCacheLack(COHERENT));
        assertTrue(GpuCheck.passes(true, COHERENT));
        GpuCheck.Result r = sorted(COHERENT, false);
        assertTrue(r.pass);
        assertTrue(r.why.isEmpty());
    }

    @Test
    public void maliG1GetsTheCacheLackAndTheSparseLackButNotTheOldHostImportLack() {
        GpuCheck.Result r = sorted(MALI_G1, false);
        assertFalse(r.pass);
        assertFalse(r.never);
        assertTrue(r.why.contains(GpuCheck.HOST_CACHE_SYNC));
        boolean sparse = false;
        for (String w : r.why) {
            sparse |= w.contains("sparse");
            assertFalse(w, w.contains("host pointer import"));
        }
        assertTrue(sparse);
        assertEquals(2, r.why.size());
    }

    @Test
    public void theCompatibilityModeDoesNotCoverIt() {
        // Adreno 640's log (sparse lacks only) would pass in the compatibility mode; with the line it must not
        List<String> adreno = new ArrayList<>(Arrays.asList(
                "lacks: sparseBinding", "lacks: sparseResidencyBuffer", "lacks: a queue that binds sparse memory",
                "device: vkCreateDevice VkResult 0", "test: compute", "compute: 0 of 4096 words wrong",
                "test: render", "render: 0 of 4096 pixels wrong", "test: host memory",
                "host import: memory types 0x2 (wanted 0x7)", "host import: memory type 1, flags 0xb",
                "host memory: 0 of 1048576 words the GPU wrote into the phone's own pages wrong",
                "missing: sparseBinding, sparseResidencyBuffer, a queue that binds sparse memory", "result: fail"));
        assertTrue(GpuCheck.fallbackPassOfLog(adreno));
        adreno.add(adreno.indexOf("host import: memory type 1, flags 0xb") + 1, NOT_COHERENT);
        assertFalse(GpuCheck.fallbackPassOfLog(adreno));
    }

    @Test
    public void turnipOnAnAdrenoAlsoGetsTheLack() {
        List<String> log = with(COHERENT, NOT_COHERENT);
        GpuCheck.Result r = sorted(log, true);
        assertFalse(r.pass);
        assertTrue(r.why.contains(GpuCheck.HOST_CACHE_SYNC));
        assertNotNull(GpuCheck.hostCacheLack(log));
    }
}
