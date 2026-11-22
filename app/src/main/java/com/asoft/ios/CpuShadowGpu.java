package com.asoft.ios;

import android.content.Context;
import android.os.Build;
import android.os.SystemClock;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.util.Map;
import java.util.Properties;
import java.util.concurrent.TimeUnit;

/**
 * Explicit system-Vulkan CPU-shadow qualification. This route is unavailable without a packaged
 * qualification record for the exact QEMU/runtime, Android build and measured hardware driver.
 * That record is a prerequisite; every invocation also executes the installed runtime's GPU work.
 * No qualification record ships until the complete external device suite has passed.
 */
final class CpuShadowGpu {
    private CpuShadowGpu() {}

    private static final String ASSET = "cpu-shadow-qualified.properties";
    /** Serializes a probe and the guest start that consumes it without holding Guest's UI-facing monitor. */
    static final Object START_LOCK = new Object();
    private static final long DEADLINE_MS = 90_000;
    private static final String[] DRIVER_ENV = {"VK_DRIVER_FILES", "VK_ICD_FILENAMES", "VK_ADD_DRIVER_FILES"};

    private static final class Qualification {
        final String qemuSha, fingerprint, driver;

        Qualification(Properties p) throws IOException {
            qemuSha = p.getProperty("qemu_sha256", "");
            fingerprint = p.getProperty("android_fingerprint", "");
            driver = p.getProperty("driver_key", "");
            if (!"1".equals(p.getProperty("schema")) || !"static".equals(p.getProperty("runtime_linkage"))
                    || !qemuSha.matches("[0-9a-f]{64}") || fingerprint.isEmpty()
                    || !driver.matches("[0-9]+/[0-9]+/[0-9]+/[0-9]+/[12]/[0-9a-f]{32}/[0-9a-f]{32}")) {
                throw new IOException("invalid packaged CPU-shadow qualification record");
            }
        }

        String key() {
            return "1/" + qemuSha + "/" + fingerprint + "/" + driver;
        }
    }

    private static Qualification qualification(Context c) throws IOException {
        Properties p = new Properties();
        try (InputStream in = c.getAssets().open(ASSET)) {
            p.load(in);
        }
        Qualification q = new Qualification(p);
        if (!q.fingerprint.equals(Build.FINGERPRINT)) {
            throw new IOException("this Android build has no CPU-shadow qualification");
        }
        return q;
    }

    /** Cheap enough for the setup screen; binary hashes and actual driver work are checked by run(). */
    static String qualificationKey(Context c) {
        try {
            return qualification(c).key();
        } catch (IOException e) {
            return ""; // absent by default, or this is a different build
        }
    }

    static boolean available(Context c) {
        return !qualificationKey(c).isEmpty();
    }

    /** One successful fresh process result, consumed by one guest launch. */
    static final class Proof {
        final GpuProbeReport report;
        private final String key;
        private final long at;
        private boolean consumed;

        Proof(GpuProbeReport report, String key) {
            this.report = report;
            this.key = key;
            at = SystemClock.elapsedRealtime();
        }

        void consume(Context c) throws IOException {
            if (consumed || SystemClock.elapsedRealtime() - at > 120_000
                    || !key.equals(qualificationKey(c)) || !Guest.nativeMissing().isEmpty()) {
                throw new IOException("the CPU-shadow launch needs a fresh GPU/native-engine check");
            }
            consumed = true;
        }
    }

    /** Blocking, off the UI thread and Guest's monitor. A failed/hung child never earns a pass. */
    static Proof run(Context c) throws IOException {
        synchronized (START_LOCK) {
            if (Guest.running()) {
                throw new IOException("close the running guest before checking its GPU route");
            }
            Qualification q = qualification(c);
            String nativeMissing = Guest.nativeMissing();
            if (!nativeMissing.isEmpty()) {
                throw new IOException("CPU-shadow native execution needs " + nativeMissing);
            }
            File executable = new File(Emu.qemu26Path(c));
            if (!q.qemuSha.equals(sha256(executable))) {
                throw new IOException("the installed QEMU/runtime differs from its CPU-shadow qualification");
            }
            File dir = GpuCheck.dir(c);
            if (!dir.isDirectory() && !dir.mkdirs()) {
                throw new IOException("cannot create the GPU probe log directory");
            }
            File stdout = new File(dir, "cpu-shadow.stdout"), stderr = new File(dir, "cpu-shadow.log");
            byte[] challenge = new byte[32];
            new SecureRandom().nextBytes(challenge);
            String nonce = hex(challenge);
            ProcessBuilder builder = new ProcessBuilder(executable.getPath(), "--asoft-gpu-probe", nonce)
                    .redirectOutput(stdout).redirectError(stderr);
            Map<String, String> env = builder.environment();
            Emu.baseEnv(c, Emu.linkLibrariesSystem(c), env);
            for (String name : DRIVER_ENV) {
                env.remove(name);
            }
            env.put("REIMS_VGPU_CPU_SHADOW", "1");
            env.put("REIMS_VGPU_DEFERRED_VIEWS", "1");
            // This is a GPU-only command, before QEMU creates a VM. Its dedicated process must
            // not inherit native-worker settings; the real guest launch requires native EL0.
            env.keySet().removeIf(name -> name.startsWith("ASOFT_NATIVE_EL0"));
            env.put("ASOFT_NATIVE_EL0", "0");
            env.put("REIMS_VGPU_LOG", "info");
            Process process = builder.start();
            boolean interrupted = false;
            try {
                long deadline = SystemClock.elapsedRealtime() + DEADLINE_MS;
                while (!process.waitFor(200, TimeUnit.MILLISECONDS)) {
                    if (SystemClock.elapsedRealtime() >= deadline) {
                        throw new IOException("installed-runtime GPU probe timed out after 90 seconds");
                    }
                    if (stdout.length() > 8192 || stderr.length() > 2 * 1024 * 1024) {
                        throw new IOException("installed-runtime GPU probe exceeded its log limit");
                    }
                }
                if (stdout.length() > 8192) {
                    throw new IOException("installed-runtime GPU probe result is too large");
                }
                GpuProbeReport result = GpuProbeReport.parse(
                        Files.readAllLines(stdout.toPath(), StandardCharsets.US_ASCII), nonce, process.exitValue());
                if (!result.hardwareGpu() || !q.driver.equals(result.driverKey())) {
                    throw new IOException("the actual Vulkan driver differs from the qualified hardware driver");
                }
                if (!q.qemuSha.equals(sha256(executable))) {
                    throw new IOException("QEMU/runtime changed during its GPU probe");
                }
                AppLog.note(c, "gpu: installed CPU-shadow runtime passed on " + result.driverKey()
                        + "; " + result.finished + " epochs, " + result.uploaded + " bytes uploaded, "
                        + result.scattered + " bytes scattered, " + result.compared + " bytes compared");
                return new Proof(result, q.key());
            } catch (InterruptedException e) {
                interrupted = true;
                throw new IOException("installed-runtime GPU probe interrupted", e);
            } finally {
                if (process.isAlive()) {
                    process.destroyForcibly();
                    try {
                        if (!process.waitFor(5, TimeUnit.SECONDS)) {
                            AppLog.note(c, "gpu: failed probe child did not exit after forced termination");
                        }
                    } catch (InterruptedException e) {
                        interrupted = true;
                    }
                }
                if (interrupted) {
                    Thread.currentThread().interrupt();
                }
            }
        }
    }

    /** A pass for this route is not the old host-pointer compatibility mode. */
    static void describe(GpuCheck.Result result) {
        result.pass = true;
        result.cpuShadow = true;
        result.system = true;
        result.nosparse = false;
        result.never = false;
        result.why.clear();
        result.missing.clear();
        result.summary = "This build's GPU memory checks passed on the phone's own graphics driver. "
                + "iOS 26 and watchOS use ordinary RAM with Vulkan copies and native CPU execution.";
    }

    /** Bounded diagnostics for the setup report; this text never decides whether the probe passed. */
    static String report(Context c) {
        StringBuilder out = new StringBuilder();
        for (String name : new String[] {"cpu-shadow.log", "cpu-shadow.stdout"}) {
            File file = new File(GpuCheck.dir(c), name);
            if (!file.isFile()) {
                continue;
            }
            try (InputStream in = new FileInputStream(file)) {
                byte[] bytes = new byte[64 * 1024];
                int count = 0, got;
                while (count < bytes.length && (got = in.read(bytes, count, bytes.length - count)) > 0) {
                    count += got;
                }
                out.append(name).append(":\n").append(new String(bytes, 0, count, StandardCharsets.UTF_8));
                if (file.length() > bytes.length) {
                    out.append("\n(log truncated)\n");
                }
            } catch (IOException e) {
                out.append(name).append(": ").append(e.getMessage()).append('\n');
            }
        }
        return out.toString();
    }

    /** The qualified route must survive debug environment overrides without changing its meaning. */
    static void requireLaunchEnvironment(Map<String, String> env, File systemLinks) throws IOException {
        if (!"1".equals(env.get("REIMS_VGPU_CPU_SHADOW"))
                || !"1".equals(env.get("REIMS_VGPU_DEFERRED_VIEWS"))
                || !"1".equals(env.get("ASOFT_NATIVE_EL0"))
                || !"1".equals(env.get("ASOFT_NATIVE_EL0_REQUIRED"))
                || !systemLinks.getPath().equals(env.get("LD_LIBRARY_PATH"))) {
            throw new IOException("CPU-shadow launch settings differ from the qualified GPU/native route");
        }
        for (String name : DRIVER_ENV) {
            if (env.containsKey(name)) {
                throw new IOException("CPU-shadow uses the system Vulkan driver; remove override " + name);
            }
        }
    }

    private static String sha256(File file) throws IOException {
        MessageDigest digest;
        try {
            digest = MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException e) {
            throw new IOException("SHA-256 is unavailable", e);
        }
        try (InputStream in = new FileInputStream(file)) {
            byte[] bytes = new byte[128 * 1024];
            int count;
            while ((count = in.read(bytes)) >= 0) {
                digest.update(bytes, 0, count);
            }
        }
        return hex(digest.digest());
    }

    private static String hex(byte[] bytes) {
        final char[] alphabet = "0123456789abcdef".toCharArray();
        char[] result = new char[2 * bytes.length];
        for (int i = 0; i < bytes.length; i++) {
            result[2 * i] = alphabet[(bytes[i] & 255) >>> 4];
            result[2 * i + 1] = alphabet[bytes[i] & 15];
        }
        return new String(result);
    }
}
