/* SPDX-License-Identifier: MIT */
package com.ripthulhu.pixelpowervr.probe;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.graphics.Typeface;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.view.View;
import android.view.WindowInsets;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.lang.ref.WeakReference;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Date;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.TimeZone;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;

/** Permission-free diagnostic UI. Only nativeLibraryDir contains executable code. */
public final class MainActivity extends Activity {
    private TextView status;
    private TextView output;
    private Button run;
    private Runner runner;

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        final LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        final int pad = (int) (12 * getResources().getDisplayMetrics().density);
        root.setPadding(pad, pad, pad, pad);
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars());
            view.setPadding(pad + bars.left, pad + bars.top, pad + bars.right, pad + bars.bottom);
            return insets;
        });
        status = new TextView(this);
        status.setTextSize(17);
        root.addView(status);
        final LinearLayout actions = new LinearLayout(this);
        run = new Button(this);
        run.setText("Run again");
        final Button copy = new Button(this);
        copy.setText("Copy report");
        actions.addView(run, new LinearLayout.LayoutParams(0, -2, 1));
        actions.addView(copy, new LinearLayout.LayoutParams(0, -2, 1));
        root.addView(actions);
        final ScrollView scroll = new ScrollView(this);
        output = new TextView(this);
        output.setTypeface(Typeface.MONOSPACE);
        output.setTextSize(11);
        output.setTextIsSelectable(true);
        scroll.addView(output);
        root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
        setContentView(root);
        runner = Runner.get(getApplicationContext());
        runner.attach(this);
        run.setOnClickListener(v -> runner.start());
        copy.setOnClickListener(v -> {
            ClipboardManager clipboard = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
            clipboard.setPrimaryClip(ClipData.newPlainText("Pixel PowerVR report", runner.snapshot()));
            Toast.makeText(this, "Report copied", Toast.LENGTH_SHORT).show();
        });
        if (!runner.started) runner.start();
    }

    @Override protected void onDestroy() {
        if (runner != null) runner.detach(this);
        super.onDestroy();
    }

    private void render(String text, String state, boolean running) {
        output.setText(text);
        status.setText(state);
        run.setEnabled(!running);
    }

    private static final class Runner {
        private static Runner instance;
        private final Context context;
        private final File report;
        private final File summary;
        private final Handler main = new Handler(Looper.getMainLooper());
        private final AtomicBoolean running = new AtomicBoolean(false);
        private final AtomicBoolean updatePending = new AtomicBoolean(false);
        private final StringBuilder transcript = new StringBuilder();
        private WeakReference<MainActivity> activity = new WeakReference<>(null);
        private volatile String state = "Pixel PowerVR Probe";
        private volatile boolean started;
        private volatile boolean halted;
        private volatile IOException reportFailure;
        private FileOutputStream reportStream;
        private FileOutputStream summaryStream;

        static synchronized Runner get(Context context) {
            if (instance == null) instance = new Runner(context);
            return instance;
        }

        Runner(Context context) {
            this.context = context;
            report = new File(context.getFilesDir(), "report.txt");
            summary = new File(context.getFilesDir(), "summary.txt");
            if (report.isFile()) {
                try (InputStream input = new FileInputStream(report)) {
                    transcript.append(readText(input, 2 * 1024 * 1024));
                } catch (IOException error) {
                    transcript.append("Previous report could not be loaded: ").append(error).append('\n');
                }
            }
        }

        synchronized void attach(MainActivity value) {
            activity = new WeakReference<>(value);
            refresh();
        }

        synchronized void detach(MainActivity value) {
            if (activity.get() == value) activity.clear();
        }

        synchronized String snapshot() { return transcript.toString(); }

        private void refresh() {
            if (!updatePending.compareAndSet(false, true)) return;
            main.post(() -> {
                updatePending.set(false);
                synchronized (Runner.this) {
                    MainActivity value = activity.get();
                    if (value != null) value.render(transcript.toString(), state, running.get() || halted);
                }
            });
        }

        private synchronized void append(String line) {
            transcript.append(line).append('\n');
            if (reportStream != null && reportFailure == null) {
                try {
                    reportStream.write((line + "\n").getBytes(StandardCharsets.UTF_8));
                    reportStream.flush();
                    if (summaryStream != null && summaryLine(line)) {
                        summaryStream.write((line + "\n").getBytes(StandardCharsets.UTF_8));
                        summaryStream.flush();
                    }
                } catch (IOException error) {
                    reportFailure = error;
                    transcript.append("STOP: report write failed: ").append(error).append('\n');
                }
            }
            refresh();
        }

        private void finish(String summary) {
            if (summary.startsWith("STOP:")) halted = true;
            state = summary;
            append(summary);
        }

        private static boolean summaryLine(String line) {
            for (String prefix : new String[]{"===", "\n===", "started_utc=", "finished_utc=", "package=",
                    "app_uid=", "app_selinux=", "selinux_enforce=", "device=", "apk_sha256=", "payload_sha256=",
                    "bounds=", "END ", "stage_exit_codes", "STOP:", "COMPLETE:", "PASS:", "result:", "RESULT=",
                    "vulkan-caps-query", "opaque-fd-producer-probe", "same_draw_overlap:", "across_draws_overlap:",
                    "VULKAN_PRODUCER_ROUNDTRIP=", "FD_MMAP_ROUNDTRIP=", "CPU_SCATTER_WRITE_ROUNDTRIP=",
                    "CPU_SCATTER_REMAP=", "timeout_child_terminated="}) {
                if (line.startsWith(prefix)) return true;
            }
            return line.contains("UNSUPPORTED") || line.contains("FAIL:") || line.contains(" mismatch ");
        }

        void start() {
            if (halted) return;
            if (!running.compareAndSet(false, true)) return;
            started = true;
            reportFailure = null;
            state = "Running in ordinary app context…";
            refresh();
            new Thread(() -> {
                try {
                    synchronized (Runner.this) {
                        reportStream = new FileOutputStream(report, true);
                        summaryStream = new FileOutputStream(summary, false);
                    }
                    perform();
                } catch (Exception error) {
                    finish("STOP: " + error.getClass().getSimpleName() + ": " + error.getMessage());
                } finally {
                    synchronized (Runner.this) {
                        if (reportStream != null) {
                            try { reportStream.close(); }
                            catch (IOException error) { reportFailure = error; }
                            reportStream = null;
                        }
                        if (summaryStream != null) {
                            try { summaryStream.close(); }
                            catch (IOException error) { reportFailure = error; }
                            summaryStream = null;
                        }
                    }
                    if (reportFailure != null) {
                        state = "STOP: report storage failed";
                        halted = true;
                    }
                    running.set(false);
                    refresh();
                }
            }, "pixel-probe-runner").start();
        }

        private void perform() throws Exception {
            final SimpleDateFormat clock = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.ROOT);
            clock.setTimeZone(TimeZone.getTimeZone("UTC"));
            append("\n=== PIXEL POWERVR APP PROBE v1 / opaque v2 ===");
            append("started_utc=" + clock.format(new Date()));
            append("package=" + context.getPackageName() + " target_sdk=" + context.getApplicationInfo().targetSdkVersion);
            append("app_uid=" + android.os.Process.myUid() + " app_pid=" + android.os.Process.myPid());
            final String domain = readFile(new File("/proc/self/attr/current"), 4096).replace("\u0000", "").trim();
            append("app_selinux=" + domain);
            append("selinux_enforce=" + optionalFile(new File("/sys/fs/selinux/enforce")));
            append("device=" + Build.MANUFACTURER + " " + Build.MODEL + " sdk=" + Build.VERSION.SDK_INT + " build=" + Build.ID);
            append("report=" + report.getAbsolutePath());
            append("summary=" + summary.getAbsolutePath());
            append("native_library_dir=" + context.getApplicationInfo().nativeLibraryDir);
            append("apk_sha256=" + sha256(new File(context.getApplicationInfo().sourceDir)));
            append("execution=direct ProcessBuilder from nativeLibraryDir; no shell, root, network, or storage permissions");
            append("bounds=query 45s; tile 45s; opaque 60s; native GPU fence waits 5s; first unexpected failure stops sequence");
            if (android.os.Process.myUid() % 100000 < 10000 || !domain.contains(":untrusted_app")) {
                throw new IOException("ordinary app UID/SELinux context was not observed; probes were not started");
            }
            final Map<String, String> hashes = loadHashes();
            final File shaderDir = new File(context.getFilesDir(), "shaders");
            if (!shaderDir.isDirectory() && !shaderDir.mkdirs()) throw new IOException("Cannot create shader directory");
            for (String filename : new String[]{"tile_image.vert.spv", "tile_image.frag.spv"}) {
                final File destination = new File(shaderDir, filename);
                try (InputStream input = context.getAssets().open("shaders/" + filename);
                     FileOutputStream output = new FileOutputStream(destination)) {
                    byte[] buffer = new byte[8192];
                    int count;
                    while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
                }
                verify(destination, "assets/shaders/" + filename, hashes);
            }
            for (String filename : new String[]{"libvulkan_caps.so", "libtile_image_probe.so", "libopaque_fd_probe.so"}) {
                final File executable = new File(context.getApplicationInfo().nativeLibraryDir, filename);
                verify(executable, "lib/arm64-v8a/" + filename, hashes);
                if (!executable.canExecute()) throw new IOException("Packaged native executable is not executable: " + filename);
            }
            int caps = runChild("vulkan_caps", 45, "--api", "1.3");
            if (caps != 0) {
                finish(caps == 2 ? "STOP: Vulkan 1.3 query unsupported; execution probes skipped" : "STOP: capability query failed");
                return;
            }
            int tile = runChild("tile_image_probe", 45, "--shader-dir", shaderDir.getAbsolutePath());
            if (tile != 0 && tile != 2) {
                finish("STOP: tile probe failed; opaque probe skipped");
                return;
            }
            int opaque = runChild("opaque_fd_probe", 60);
            if (opaque != 0 && opaque != 2 && opaque != 3 && opaque != 4) {
                finish("STOP: opaque FD probe failed");
                return;
            }
            append("stage_exit_codes query=" + caps + " tile=" + tile + " opaque_v2=" + opaque);
            finish(tile == 0 && opaque == 0
                ? "PASS: query, tile ordering, and opaque FD v2 passed in ordinary app context"
                : "COMPLETE: one or more capabilities unsupported; inspect stage output and exit codes");
            append("scope=standalone driver probes; no claim of iOS GPU integration, arbitrary guest-page import, or sparse GPU aliasing");
            append("finished_utc=" + clock.format(new Date()));
        }

        private int runChild(String name, int seconds, String... arguments) throws Exception {
            if (reportFailure != null) throw reportFailure;
            final ArrayList<String> command = new ArrayList<>();
            command.add(new File(context.getApplicationInfo().nativeLibraryDir, "lib" + name + ".so").getAbsolutePath());
            command.addAll(Arrays.asList(arguments));
            state = "Running " + name + "…";
            append("\nBEGIN " + name + " timeout_seconds=" + seconds);
            append("argv=" + command);
            final long startedAt = SystemClock.elapsedRealtime();
            final java.lang.Process child = new ProcessBuilder(command)
                .directory(context.getFilesDir()).redirectErrorStream(true).start();
            child.getOutputStream().close();
            final AtomicReference<IOException> readFailure = new AtomicReference<>();
            final AtomicBoolean outputLimit = new AtomicBoolean(false);
            final Thread reader = new Thread(() -> {
                try (BufferedReader input = new BufferedReader(new InputStreamReader(child.getInputStream(), StandardCharsets.UTF_8))) {
                    int chars = 0;
                    String line;
                    while ((line = input.readLine()) != null) {
                        chars += line.length() + 1;
                        if (chars > 512 * 1024) {
                            outputLimit.set(true);
                            child.destroyForcibly();
                            break;
                        }
                        append(line);
                    }
                } catch (IOException error) { readFailure.set(error); }
            }, "pixel-probe-output");
            reader.setDaemon(true);
            reader.start();
            final boolean ended = child.waitFor(seconds, TimeUnit.SECONDS);
            if (!ended) {
                append("END " + name + " TIMEOUT after " + seconds + "s; terminating own child; no later probes will run");
                child.destroyForcibly();
                final boolean reaped = child.waitFor(5, TimeUnit.SECONDS);
                append("timeout_child_terminated=" + reaped);
                // A kernel-stuck process cannot be synchronously reaped. Do not let
                // a pipe close or reader join turn the outer deadline into a hang.
                if (!reaped) return -1;
            }
            reader.join(2000);
            if (reader.isAlive()) {
                try { child.getInputStream().close(); } catch (IOException ignored) { }
                append("STOP: output reader did not finish for " + name);
                return -1;
            }
            if (!ended) {
                return -1;
            }
            final int exit = child.exitValue();
            append("END " + name + " exit=" + exit + " elapsed_ms=" + (SystemClock.elapsedRealtime() - startedAt));
            if (outputLimit.get() || readFailure.get() != null || reportFailure != null) {
                append("STOP: incomplete output; limit=" + outputLimit.get() + " read_error=" + readFailure.get() + " report_error=" + reportFailure);
                return -1;
            }
            return exit;
        }

        private Map<String, String> loadHashes() throws IOException {
            Map<String, String> hashes = new HashMap<>();
            try (BufferedReader input = new BufferedReader(new InputStreamReader(context.getAssets().open("payload-sha256.txt"), StandardCharsets.UTF_8))) {
                String line;
                while ((line = input.readLine()) != null) {
                    if (line.length() < 67 || !line.substring(64, 66).equals("  ")) throw new IOException("Invalid payload hash manifest");
                    hashes.put(line.substring(66), line.substring(0, 64));
                }
            }
            return hashes;
        }

        private void verify(File file, String key, Map<String, String> hashes) throws Exception {
            String actual = sha256(file);
            if (!actual.equals(hashes.get(key))) throw new IOException("Payload hash mismatch: " + key);
            append("payload_sha256=" + actual + " " + key);
        }

        private static String sha256(File file) throws Exception {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (InputStream input = new FileInputStream(file)) {
                byte[] buffer = new byte[65536];
                int count;
                while ((count = input.read(buffer)) != -1) digest.update(buffer, 0, count);
            }
            StringBuilder result = new StringBuilder(64);
            for (byte value : digest.digest()) result.append(String.format(Locale.ROOT, "%02x", value & 255));
            return result.toString();
        }

        private static String readText(InputStream input, int limit) throws IOException {
            ByteArrayOutputStream output = new ByteArrayOutputStream();
            byte[] buffer = new byte[4096];
            int count;
            while ((count = input.read(buffer)) != -1) {
                if (output.size() + count > limit) throw new IOException("Text file exceeds size bound");
                output.write(buffer, 0, count);
            }
            return new String(output.toByteArray(), StandardCharsets.UTF_8);
        }

        private static String readFile(File file, int limit) throws IOException {
            try (InputStream input = new FileInputStream(file)) { return readText(input, limit); }
        }

        private static String optionalFile(File file) {
            try { return readFile(file, 4096).trim(); }
            catch (IOException error) { return "unreadable (" + error.getClass().getSimpleName() + ")"; }
        }
    }
}
