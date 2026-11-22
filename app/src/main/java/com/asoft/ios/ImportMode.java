package com.asoft.ios;

import java.io.File;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * The compatibility mode's engine switches for a phone on its own Vulkan driver, in the test build for a Mali phone:
 * the engine logs why a host-memory import is refused and has an optional startup probe of it, and its lazy views of
 * IOSurface memory can be turned off (the older path) to see whether they are what the driver refuses. No Android
 * here, so the JVM unit tests run it (ImportModeTest).
 */
final class ImportMode {
    private ImportMode() {}

    /** The engine's startup probe of the host-memory import (harmless where the import works). */
    static final String PROBE = "REIMS_VGPU_IMPORT_PROBE";
    /** Unset: the engine's default (lazy IOSurface views on in the compatibility mode); LISTS turns them off. */
    static final String LAZY_MAPPINGS = "REIMS_VGPU_LAZY_MAPPINGS";
    static final String LISTS = "lists";
    /** A file in files/run: a QEMU ended on a host-memory refusal once, so the next starts run with LISTS (named by the test build: the one of an earlier test build does not carry over). */
    static final String MARKER = "import-refused-once-mali2";

    static File marker(File runDir) {
        return new File(runDir, MARKER);
    }

    /**
     * What start26 adds to QEMU's environment. Nothing unless @compat26. Then the probe, and with the marker
     * (@markerExists) the lazy views off. @overrides: the start's ios26.txt settings (debug builds; keys "env.NAME"):
     * a variable the test file sets stays as the file has it.
     */
    static Map<String, String> envAdditions(boolean compat26, boolean markerExists, Map<String, String> overrides) {
        Map<String, String> add = new LinkedHashMap<>();
        if (!compat26) {
            return add;
        }
        if (!overrides.containsKey("env." + PROBE)) {
            add.put(PROBE, "1");
        }
        if (markerExists && !overrides.containsKey("env." + LAZY_MAPPINGS)) {
            add.put(LAZY_MAPPINGS, LISTS);
        }
        return add;
    }

    /** The app log's line for a compatibility-mode start, from QEMU's final environment: it goes into the crash report. */
    static String describe(Map<String, String> env, boolean markerExisted) {
        String lazy = env.get(LAZY_MAPPINGS);
        return "gpu: import probe " + ("1".equals(env.get(PROBE)) ? "on" : "off") + ", lazy surface views "
                + (lazy == null ? "default (on)" : LISTS.equals(lazy) ? "off (" + LAZY_MAPPINGS + "=" + LISTS + ")"
                        : LAZY_MAPPINGS + "=" + lazy)
                + (markerExisted ? ", " + MARKER + " is set" : "");
    }
}
