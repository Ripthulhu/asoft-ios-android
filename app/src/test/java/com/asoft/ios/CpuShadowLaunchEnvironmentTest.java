package com.asoft.ios;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.fail;

import java.io.File;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

import org.junit.Test;

/** A measured CPU-shadow route must not silently launch the old importer or TCG-only mode. */
public class CpuShadowLaunchEnvironmentTest {
    private static final File SYSTEM = new File("/data/user/0/test/files/lib-system");

    private static Map<String, String> route() {
        Map<String, String> env = new HashMap<>();
        env.put("REIMS_VGPU_CPU_SHADOW", "1");
        env.put("REIMS_VGPU_DEFERRED_VIEWS", "1");
        env.put("ASOFT_NATIVE_EL0", "1");
        env.put("ASOFT_NATIVE_EL0_REQUIRED", "1");
        env.put("LD_LIBRARY_PATH", SYSTEM.getPath());
        return env;
    }

    private static void refuses(Map<String, String> env) {
        try {
            CpuShadowGpu.requireLaunchEnvironment(env, SYSTEM);
            fail("accepted an environment that changes the qualified route");
        } catch (IOException expected) {
            assertFalse(expected.getMessage().isEmpty());
        }
    }

    @Test
    public void measuredSystemRouteWithRequiredNativeEngineIsAccepted() throws Exception {
        CpuShadowGpu.requireLaunchEnvironment(route(), SYSTEM);
    }

    @Test
    public void modeAndNativeFallbackOverridesAreRefused() {
        for (String name : new String[] {"REIMS_VGPU_CPU_SHADOW", "REIMS_VGPU_DEFERRED_VIEWS",
                "ASOFT_NATIVE_EL0", "ASOFT_NATIVE_EL0_REQUIRED", "LD_LIBRARY_PATH"}) {
            Map<String, String> env = route();
            env.remove(name);
            refuses(env);
            env.put(name, "0");
            refuses(env);
        }
    }

    @Test
    public void driverOverridesCannotReuseSystemQualification() {
        for (String name : new String[] {"VK_DRIVER_FILES", "VK_ICD_FILENAMES", "VK_ADD_DRIVER_FILES"}) {
            Map<String, String> env = route();
            env.put(name, "/other/driver.json");
            refuses(env);
        }
    }
}
