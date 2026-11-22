package com.asoft.ios;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import java.io.File;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;

import org.junit.Test;

/** The test build's engine switches for the compatibility mode (ImportMode) and its host-memory retry (CrashText.importRefusal). */
public class ImportModeTest {
    private static final Map<String, String> NO_FILE = Collections.emptyMap();

    /** The engine's line from the Mali phone's report, shortened. */
    private static final String REFUSED = "reims-vgpu: fatal: platform call newBufferWithBytesNoCopy:length:options:deallocator::"
            + " the Vulkan runtime refused it: unsupported: Unsupported { feature: HostMemory, needs: NotRepresentable,"
            + " location: None, symbol: None }; no dma-buf of its 0x34000 bytes at 0x6fc5232000: /dev/udmabuf would not"
            + " open (Permission denied (os error 13))";

    // -- the environment

    @Test
    public void outsideTheCompatibilityModeNothingIsAdded() {
        assertTrue(ImportMode.envAdditions(false, false, NO_FILE).isEmpty());
        // not even with the marker: the Adreno route's start stays as it was
        assertTrue(ImportMode.envAdditions(false, true, NO_FILE).isEmpty());
    }

    @Test
    public void theCompatibilityModeWithoutTheMarkerAddsTheProbeOnly() {
        Map<String, String> add = ImportMode.envAdditions(true, false, NO_FILE);
        assertEquals(1, add.size());
        assertEquals("1", add.get("REIMS_VGPU_IMPORT_PROBE"));
        assertFalse(add.containsKey("REIMS_VGPU_LAZY_MAPPINGS"));
    }

    @Test
    public void theMarkerAddsTheLazyViewsOff() {
        Map<String, String> add = ImportMode.envAdditions(true, true, NO_FILE);
        assertEquals(2, add.size());
        assertEquals("1", add.get("REIMS_VGPU_IMPORT_PROBE"));
        assertEquals("lists", add.get("REIMS_VGPU_LAZY_MAPPINGS"));
    }

    @Test
    public void theTestFilesOwnSettingsWin() {
        Map<String, String> ov = new HashMap<>();
        ov.put("env.REIMS_VGPU_LAZY_MAPPINGS", "on");
        Map<String, String> add = ImportMode.envAdditions(true, true, ov);
        assertFalse(add.containsKey("REIMS_VGPU_LAZY_MAPPINGS"));
        assertEquals("1", add.get("REIMS_VGPU_IMPORT_PROBE"));
        ov.clear();
        ov.put("env.REIMS_VGPU_IMPORT_PROBE", "0");
        add = ImportMode.envAdditions(true, true, ov);
        assertFalse(add.containsKey("REIMS_VGPU_IMPORT_PROBE"));
        assertEquals("lists", add.get("REIMS_VGPU_LAZY_MAPPINGS"));
        // other settings of the file change nothing
        ov.clear();
        ov.put("cpu", "max");
        ov.put("env.REIMS_VGPU_DEFERRED_VIEWS", "0");
        assertEquals(1, ImportMode.envAdditions(true, false, ov).size());
    }

    @Test
    public void theMarkerIsAFileInTheRunFolder() {
        assertEquals(new File("run", "import-refused-once-mali2"), ImportMode.marker(new File("run")));
    }

    @Test
    public void theAppLogLineSaysWhatTheEngineGot() {
        Map<String, String> env = new LinkedHashMap<>();
        assertEquals("gpu: import probe off, lazy surface views default (on)", ImportMode.describe(env, false));
        env.putAll(ImportMode.envAdditions(true, false, NO_FILE));
        assertEquals("gpu: import probe on, lazy surface views default (on)", ImportMode.describe(env, false));
        env.putAll(ImportMode.envAdditions(true, true, NO_FILE));
        assertEquals("gpu: import probe on, lazy surface views off (REIMS_VGPU_LAZY_MAPPINGS=lists), import-refused-once-mali2 is set",
                ImportMode.describe(env, true));
        env.put("REIMS_VGPU_LAZY_MAPPINGS", "on");
        assertTrue(ImportMode.describe(env, true).contains("REIMS_VGPU_LAZY_MAPPINGS=on"));
    }

    @Test
    public void theTestBuildsVersionNameIsTheReleasesVersionToTheUpdateCheck() {
        // 0.1.6-mali2 is not older than the 0.1.6 release (no notice for the build that is the release's own), and
        // not newer than the next one
        assertFalse(UpdateCheck.newer("v0.1.6", "0.1.6-mali2"));
        assertTrue(UpdateCheck.newer("v0.1.7", "0.1.6-mali2"));
    }

    // -- the stop's retry

    @Test
    public void aFirstHostMemoryRefusalWritesTheMarkerAndSaysSo() {
        CrashText.ImportRefusal r = CrashText.importRefusal(true, false, "reims[warn] something\n" + REFUSED + "\n");
        assertTrue(r.writeMarker);
        assertEquals("This test build tries another memory mode on the next start; tap Resume once more.", r.sentence);
    }

    @Test
    public void aRefusalWithTheMarkerAlreadyThereWritesNothingAndSaysBothModes() {
        CrashText.ImportRefusal r = CrashText.importRefusal(true, true, REFUSED + "\n");
        assertFalse(r.writeMarker);
        assertEquals("This happened in both memory modes of this test build; please send the report.", r.sentence);
    }

    @Test
    public void anythingElseAddsNothing() {
        // not the compatibility mode
        CrashText.ImportRefusal r = CrashText.importRefusal(false, false, REFUSED);
        assertFalse(r.writeMarker);
        assertEquals("", r.sentence);
        // a fatal line without HostMemory, and HostMemory outside a fatal line: the words must be on one line
        String other = "reims-vgpu: fatal: platform call mmap: the process ran out of kernel mappings";
        r = CrashText.importRefusal(true, false, other + "\n");
        assertFalse(r.writeMarker);
        assertEquals("", r.sentence);
        r = CrashText.importRefusal(true, false, "reims[warn] the probe: feature: HostMemory is there\n" + other + "\n");
        assertFalse(r.writeMarker);
        assertEquals("", r.sentence);
        assertEquals("", CrashText.importRefusal(true, false, "").sentence);
        assertEquals("", CrashText.importRefusal(true, false, null).sentence);
    }

    @Test
    public void theStopTextCarriesTheSentenceAfterTheGenericOne() {
        String plain = CrashText.graphicsStop(REFUSED + "\n", "");
        assertTrue(plain, plain.startsWith("the phone's GPU driver refused") && plain.endsWith("Its disk and saves are kept."));
        CrashText.ImportRefusal r = CrashText.importRefusal(true, false, REFUSED + "\n");
        String text = CrashText.graphicsStop(REFUSED + "\n", "", r.sentence);
        assertEquals(plain + " " + r.sentence, text);
        // an empty or missing extra changes nothing, and the mapping limit's text takes none
        assertEquals(plain, CrashText.graphicsStop(REFUSED + "\n", "", ""));
        assertEquals(plain, CrashText.graphicsStop(REFUSED + "\n", "", null));
        String mappings = "reims-vgpu: fatal: platform call mmap: the library's views of memory ran out of kernel mappings";
        assertFalse(CrashText.graphicsStop(mappings, "", r.sentence).contains("another memory mode"));
        // the text stays the same from a second look at the same stop (the screen asks every second)
        assertEquals(text, CrashText.graphicsStop(REFUSED + "\n", "",
                CrashText.importRefusal(true, false, REFUSED + "\n").sentence));
    }
}
