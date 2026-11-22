package com.asoft.ios;

/**
 * The GPU check's recorded pass as a start of iOS 26 / watchOS and a begun setup read it (GpuCheck.forStart): the
 * keys GpuCheck.run wrote against this build's key. Setup downloads require a current pass.
 * Ordinary GPU modes can be restored for a start after an app update. CPU shadow also needs an intact
 * current qualification and a fresh installed-runtime probe from Guest.
 * Before 0.1.7 an update made a start forget it: a Mali that had passed on its own Vulkan driver started on Turnip
 * and died at device creation (A#296, Vulkan -3), and an Adreno 740/750/660 started without the compatibility mode.
 * A check of this build replaces the recorded pass, a failed one too.
 */
final class GpuPass {
    /** The key of the build whose check passed; "" when the last check failed or none ran. */
    final String by;
    /** A pass by this build: Set up may download iOS 26 and watchOS (GpuCheck.passed). */
    final boolean thisBuild;
    /** A pass by this build or by the build before an update: a start uses its mode, a begun setup goes on. */
    final boolean any;
    /** That pass was in the compatibility mode (REIMS_VGPU_DEFERRED_VIEWS=0). */
    final boolean noSparse;
    /** That pass was on the phone's own Vulkan driver (the engine opens Android's loader; always compatibility mode). */
    final boolean system;
    final boolean cpuShadow;
    final boolean shadowBlocked;

    /**
     * @param current this build's key; @param pass, @param nosparse, @param system the keys the last check wrote;
     * @param forceSystem the debug flag files/gpucheck-force-system (with a pass).
     */
    GpuPass(String current, String pass, String nosparse, String system, boolean forceSystem) {
        this(current, pass, nosparse, system, forceSystem, false, false);
    }

    private GpuPass(String current, String pass, String nosparse, String system, boolean forceSystem,
            boolean cpuShadow, boolean shadowBlocked) {
        by = pass == null ? "" : pass;
        any = !by.isEmpty();
        thisBuild = any && by.equals(current);
        this.system = any && (cpuShadow || by.equals(system) || forceSystem);
        this.noSparse = any && !cpuShadow && by.equals(nosparse);
        this.cpuShadow = cpuShadow;
        this.shadowBlocked = shadowBlocked;
    }

    static GpuPass forRuntime(String current, String pass, String nosparse, String system, String shadowKey,
            boolean shadowQualified, boolean turnipDisabled, boolean forceSystem) {
        if (pass != null && !pass.isEmpty() && pass.equals(shadowKey)) {
            boolean ready = current.equals(pass) && shadowQualified;
            return new GpuPass(current, ready ? pass : "", "", "", false, ready, !ready);
        }
        return new GpuPass(current, turnipDisabled ? "" : pass, nosparse, system, forceSystem);
    }

    /** The mode in the app's log's words. */
    String mode() {
        if (cpuShadow) {
            return "the qualified CPU-shadow route";
        }
        return !any ? "no pass" : system ? "the phone's own driver" : noSparse ? "the compatibility mode" : "the full mode";
    }
}
