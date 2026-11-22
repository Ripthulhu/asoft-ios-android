package com.asoft.ios;

import android.app.Activity;
import android.graphics.Color;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.Switch;
import android.widget.TextView;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Set up's iOS 16: a section of the setup page (SetupSection) with its state in one line, its one action, and under
 * Details the description, the download with a row per file, every step and the Wi-Fi switch. Reads SetupService.state
 * twice a second.
 */
final class SetupScreen {
    private static final int GRAY = Ui.DIM, DIM = Ui.FAINT, RED = Ui.RED, GREEN = Ui.GREEN, ORANGE = Ui.ORANGE;

    /** What a member is, for people. */
    private static final Map<String, String> NAMES = new LinkedHashMap<>();

    static {
        NAMES.put("087-86698-044.dmg", "iOS itself");
        NAMES.put("087-86593-047.dmg", "System libraries (SystemOS)");
        NAMES.put("087-86715-047.dmg", "Built-in apps (AppOS)");
        NAMES.put("BuildManifest.plist", "Build manifest");
        NAMES.put("Firmware/all_flash/DeviceTree.d22ap.im4p", "iPhone X device tree");
    }

    /** iOS 16's steps and what the screen calls them (SetupRecord names the failed one with them too). */
    static final String[][] STEPS = {
            {"ipsw", "Download from Apple"},
            {"payload", "Kernel with the iPhone's device tree"},
            {"disk", "Build the iOS disk"},
            {"pack", "Pack the disk"},
            {"install", "Set it up in the app"},
            {"firststart", "First start of iOS (once, about 40 min)"},
    };

    private final Activity a;
    private final SetupSection sec;
    private final Handler h = new Handler(Looper.getMainLooper());
    private TextView total, details, free, memory, replaces;
    /** Share log and Report on GitHub under a failed step's red line (its record: SetupService.state.record). */
    private View errorButtons;
    private ProgressBar totalBar;
    private LinearLayout files;
    private final Map<String, TextView[]> fileRows = new LinkedHashMap<>();
    private final Map<String, ProgressBar> fileBars = new LinkedHashMap<>();
    private final Map<String, TextView> stepRows = new LinkedHashMap<>();
    /** The members asoft-setup.json lists (their bytes in the zip), shown before the download reads the IPSW. */
    private final Map<String, Long> planned = new LinkedHashMap<>();
    private long plannedTotal;
    private TextView primary, cancel;
    /** What the set-up system takes on the disk, measured once off the UI thread (SetupState.size). */
    private volatile String sizeText;
    private boolean measuring, wasComplete;

    SetupScreen(Activity a) {
        this.a = a;
        sec = new SetupSection(a, "iOS 16", DeviceView.HOME, new int[] {0xff5ad1c8, 0xff2f8fe0, 0xff3a56c9});
        build();
        tick();
    }

    /** Its views, for the setup screen to place (again, after it rebuilds its list). */
    View view() {
        if (sec.root.getParent() instanceof android.view.ViewGroup) {
            ((android.view.ViewGroup) sec.root.getParent()).removeView(sec.root);
        }
        return sec.root;
    }

    private TextView text(LinearLayout to, String s, float size, int color) {
        return Ui.text(a, to, s, size, color);
    }

    private void build() {
        sec.error.setVisibility(View.GONE);
        errorButtons = logButtons(a, sec.main, () -> SetupService.state.record);

        primary = Ui.capsule(a, "Set up", false, v -> onPrimary());
        sec.actions.addView(primary, new LinearLayout.LayoutParams(-2, -2));
        cancel = Ui.link(a, "Cancel", RED, v -> new android.app.AlertDialog.Builder(a)
                .setTitle("Cancel the install?")
                .setMessage("What was downloaded and built so far is deleted.")
                .setPositiveButton("Cancel install", (d, w) -> SetupService.cancel(a, SetupCancel.IOS16))
                .setNegativeButton("Keep going", null)
                .show());
        sec.actions.addView(cancel, new LinearLayout.LayoutParams(-2, -2));

        // -- Details
        text(sec.body, "iOS 16.7.16 for the iPhone X: about 5.8 GB from Apple's own servers, then the phone builds the iOS disk "
                + "itself, as the PC installer does, and starts iOS once so that your first start is quick. About 1.5 hours "
                + "on a Galaxy S25 Ultra. Keep the phone on its charger; you can use it meanwhile.", 13.5f, GRAY)
                .setLineSpacing(Ui.dp(a, 1.5f), 1f);
        free = text(sec.body, "", 12.5f, DIM);
        free.setPadding(0, Ui.dp(a, 8), 0, 0);
        replaces = text(sec.body, "Importing or installing again replaces it: this iPhone's settings, apps and saves go.", 13.5f, Color.rgb(0xbb, 0xbb, 0xbb));
        replaces.setPadding(0, Ui.dp(a, 8), 0, 0);

        sec.heading("Download");
        total = text(sec.body, "", 15, Ui.TEXT);
        totalBar = sec.bar(sec.body, 4);
        details = text(sec.body, "", 13, GRAY);
        details.setPadding(0, Ui.dp(a, 8), 0, 0);
        files = new LinearLayout(a);
        files.setOrientation(LinearLayout.VERTICAL);
        sec.body.addView(files, Ui.top(Ui.dp(a, 6)));
        try {
            org.json.JSONArray m = PhoneSetup.manifest(a).getJSONObject("os").getJSONObject("ios16")
                    .getJSONObject("sources").getJSONObject("ipsw").getJSONArray("members");
            for (int i = 0; i < m.length(); i++) {
                org.json.JSONObject e = m.getJSONObject(i);
                long zip = e.optLong("zipBytes", e.optLong("bytes"));
                planned.put(e.getString("name"), zip);
                plannedTotal += zip;
            }
        } catch (java.io.IOException | org.json.JSONException ignored) {
            // the list shows once the download has read the IPSW
        }

        sec.heading("Steps");
        for (String[] s : STEPS) {
            TextView t = text(sec.body, "○  " + s[1], 14.5f, GRAY);
            t.setPadding(0, Ui.dp(a, 5), 0, Ui.dp(a, 5));
            stepRows.put(s[0], t);
        }
        memory = text(sec.body, "", 13, GRAY);
        memory.setPadding(0, Ui.dp(a, 10), 0, 0);

        Switch wifi = new Switch(a);
        wifi.setText("Download on Wi-Fi only");
        wifi.setTextColor(Ui.TEXT);
        wifi.setTextSize(15);
        // iOS's colours: green when on (the dark theme's own switch hardly shows)
        int[][] states = {{android.R.attr.state_checked}, {}};
        wifi.setThumbTintList(new android.content.res.ColorStateList(states, new int[] {Color.WHITE, 0xffd0d0d0}));
        wifi.setTrackTintList(new android.content.res.ColorStateList(states, new int[] {0xff30d158, 0xff48484a}));
        wifi.setChecked(SetupService.wifiOnly(a));
        wifi.setOnCheckedChangeListener((v, on) -> SetupService.setWifiOnly(a, on));
        sec.body.addView(wifi, Ui.top(Ui.dp(a, 14)));
    }

    private void onPrimary() {
        SetupService.State s = SetupService.state;
        if (s.running && !s.paused) {
            SetupService.pause(a);
        } else if (Guest.running()) {
            s.record = null;
            s.error = "Close iOS first (side bar > Saves > Save and close): the setup needs its memory.";
        } else {
            // (a helper VM of this phone's size takes memory too: say so when little is free, K5)
            LowMemory.askBeforeStart(a, "the iOS 16 setup", Helper.needBytes(Helper.ramMiB(a, Helper.FLOOR_IOS16)),
                    () -> Battery.askOnce(a, "The setup takes over an hour", true, () -> SetupService.start(a)));
        }
    }

    /**
     * Share log and Report on GitHub for the record @id gives (a failed step's), added to @to; hidden until the
     * screen shows it. Setup26Screen's error line has them too.
     */
    static View logButtons(Activity a, LinearLayout to, java.util.function.Supplier<String> id) {
        LinearLayout row = new LinearLayout(a);
        row.setOrientation(LinearLayout.HORIZONTAL);
        TextView share = Ui.link(a, "Share log", Ui.LINK, v -> {
            CrashReport.Record r = CrashReport.find(a, id.get());
            if (r != null) {
                CrashReport.share(a, r);
            }
        });
        TextView report = Ui.link(a, "Report on GitHub", Ui.LINK, v -> {
            CrashReport.Record r = CrashReport.find(a, id.get());
            if (r != null) {
                CrashReport.openIssue(a, r);
            }
        });
        share.setPadding(0, Ui.dp(a, 9), Ui.dp(a, 18), Ui.dp(a, 9));
        row.addView(share);
        row.addView(report);
        row.setVisibility(View.GONE);
        to.addView(row);
        return row;
    }

    static String gb(long b) {
        return b >= 1e9 ? String.format(Locale.ROOT, "%.2f GB", b / 1e9)
                : b >= 1e6 ? String.format(Locale.ROOT, "%.0f MB", b / 1e6)
                : String.format(Locale.ROOT, "%.0f KB", b / 1e3);
    }

    static String minutes(double s) {
        if (s < 60) {
            return "less than a minute";
        }
        long m = Math.round(s / 60);
        return m < 60 ? m + " min" : (m / 60) + " h " + (m % 60) + " min";
    }

    private void tick() {
        if (a.isFinishing() || a.isDestroyed()) {
            return;
        }
        update();
        h.postDelayed(this::tick, 500);
    }

    private void update() {
        SetupService.State s = SetupService.state;
        long freeBytes = a.getFilesDir().getUsableSpace();
        long need = PhoneSetup.needBytes(a);
        String freeLine = String.format(Locale.ROOT, "%s free on this phone; the install needs about %s more at its height and leaves about 6.5 GB.",
                gb(freeBytes), gb(need));
        free.setText(freeLine);
        free.setTextColor(freeBytes < need ? ORANGE : DIM);

        boolean mine = !"a26".equals(s.target);
        boolean running = s.running && mine;
        boolean other = s.running && !mine;       // the iOS 26 / watchOS install runs: one install at a time
        boolean all = PhoneSetup.done(a, "firststart");
        boolean started = PhoneSetup.work(a).isDirectory();
        // set up: the Apple route finished its first start, or a bundle from the PC was brought in (no work folder)
        boolean complete = !running && (all || Installer.installed(a) && !started);
        if (complete && !wasComplete) {
            sizeText = null;
        }
        wasComplete = complete;
        if (complete && sizeText == null && !measuring) {
            measuring = true;
            new Thread(() -> {
                String t = SetupState.size(Installer.removal(a, Guest.IOS16).bytes);
                sizeText = t;
                measuring = false;
            }, "setup16-size").start();
        }

        // the state line and what it needs
        String progress = running ? SetupState.running(a, Guest.IOS16)
                : started && !complete ? SetupState.progress(SetupState.plan16(a, true), -1) : null;
        sec.setState(complete ? SetupSection.THERE : running ? SetupSection.WORKING : SetupSection.OFF,
                SetupState.line(complete, running, s.paused, progress, sizeText == null ? "" : sizeText,
                        SetupState.day(SetupState.installedAt(a, Guest.IOS16))));
        sec.device.show(null, complete, false);
        if (mine && s.error != null) {
            SetupSection.say(sec.error, s.error, RED);
        } else {
            SetupSection.say(sec.error, "", RED);
        }
        String info;
        if (complete) {
            info = "Start it from the home screen: it comes up in about 10 s.";
        } else if (other) {
            info = "iOS 26 or watchOS is being set up: one install at a time.";
        } else if (running && s.held && s.holdNote != null) {
            info = s.holdNote;      // a hot or flat phone holds the build: say so (HoldRule)
        } else if (running) {
            info = s.text.isEmpty() ? "" : s.text;
        } else {
            info = "5.8 GB from Apple, about 1.5 hours. Keep the phone on its charger.";
        }
        SetupSection.say(sec.info, info, Ui.DIM);
        // short on room is said outside the details: it stops the install
        SetupSection.say(sec.extra, !complete && !running && freeBytes < need ? freeLine : "", ORANGE);
        errorButtons.setVisibility(mine && s.error != null && s.record != null && !s.running ? View.VISIBLE : View.GONE);
        replaces.setVisibility(complete ? View.VISIBLE : View.GONE);
        free.setVisibility(complete ? View.GONE : View.VISIBLE);
        String note = Helper.memoryNote;
        memory.setText(note == null ? "" : note);
        memory.setVisibility(running && note != null ? View.VISIBLE : View.GONE);

        // the buttons: only the download pauses (a helper VM step or iOS's first start would have to start over)
        primary.setText(running ? (s.paused ? "Resume" : "Pause") : started && !complete ? "Resume" : "Set up");
        primary.setVisibility(complete || running && !s.paused && !"ipsw".equals(s.step) ? View.GONE : View.VISIBLE);
        primary.setEnabled(!other);
        primary.setAlpha(other ? 0.4f : 1f);
        cancel.setVisibility(!complete && !other && (running || started) ? View.VISIBLE : View.GONE);
        sec.follow(running);

        // the download and its steps (Details)
        List<IpswFetch.Item> items = running ? s.items : java.util.Collections.emptyList();
        long got = 0, size = 0;
        for (IpswFetch.Item it : items) {
            got += it.done.get();
            size += it.total;
            row(it.member, it.done.get(), it.total, it.state, it.error);
        }
        boolean downloadedEarlier = PhoneSetup.done(a, "ipsw") || PhoneSetup.done(a, "disk");
        if (items.isEmpty()) {
            for (Map.Entry<String, Long> e : planned.entrySet()) {
                row(e.getKey(), downloadedEarlier ? e.getValue() : 0, e.getValue(), downloadedEarlier ? "ok" : "waiting", null);
            }
        }
        boolean fetching = "ipsw".equals(s.step) && running;
        if (size > 0) {
            total.setText(String.format(Locale.ROOT, "%s of %s from Apple", gb(got), gb(size)));
            totalBar.setProgress((int) (got * 1000 / size));
        } else {
            total.setText(downloadedEarlier ? "Downloaded and checked" : plannedTotal > 0 ? gb(plannedTotal) + " from Apple" : "From Apple");
            totalBar.setProgress(downloadedEarlier ? 1000 : 0);
        }
        if (fetching && s.mbps > 0) {
            double left = (size - got) / 1e6 / s.mbps;
            details.setText(String.format(Locale.ROOT, "%.1f MB/s · %s left · %d connections%s", s.mbps, minutes(left), s.connections,
                    s.servers.isEmpty() ? "" : " · " + s.servers));
        } else if (s.waitingForNetwork && mine) {
            details.setText("No internet connection: it goes on by itself when the phone is online again");
        } else if (s.waitingForWifi && mine) {
            details.setText("Waiting for Wi-Fi (Download on Wi-Fi only is on)");
        } else if (s.paused && mine) {
            details.setText("Paused: what came stays, Resume goes on from there");
        } else {
            details.setText(fetching ? "Finding Apple's fastest servers…" : "");
        }
        for (String[] st : STEPS) {
            TextView t = stepRows.get(st[0]);
            // (the download's marker goes when its files are dropped early: a built disk means it was done)
            boolean isDone = PhoneSetup.done(a, st[0]) || ("ipsw".equals(st[0]) && PhoneSetup.done(a, "disk"));
            boolean now = st[0].equals(s.step) && running;
            if (isDone) {
                t.setText("✓  " + st[1]);
                t.setTextColor(GREEN);
            } else if (now) {
                t.setText("●  " + st[1] + (s.pct >= 0 && !"ipsw".equals(st[0]) ? " (" + s.pct + "%)" : "")
                        + (s.text.isEmpty() || "ipsw".equals(st[0]) ? "" : "\n    " + s.text));
                t.setTextColor(Ui.TEXT);
            } else {
                t.setText("○  " + st[1]);
                t.setTextColor(GRAY);
            }
        }
    }

    private void row(String member, long d, long size, String st0, String err) {
        TextView[] r = fileRows.get(member);
        ProgressBar b = fileBars.get(member);
        if (r == null) {
            r = sec.fileRow(files, NAMES.getOrDefault(member, member), fileRows.isEmpty());
            b = sec.bar(files, 3);
            fileRows.put(member, r);
            fileBars.put(member, b);
        }
        long t = Math.max(1, size);
        String state;
        int color = GRAY;
        switch (st0) {
            case "ok":
                state = "✓ " + gb(size) + " checked";
                color = GREEN;
                break;
            case "verifying":
                state = "Checking…";
                color = Ui.TEXT;
                break;
            case "failed":
                state = "✕ " + (err == null ? "failed" : err);
                color = RED;
                break;
            case "fetching":
                state = gb(d) + " of " + gb(size);
                color = Ui.TEXT;
                break;
            default:
                state = d > 0 ? gb(d) + " of " + gb(size) : gb(size);
                break;
        }
        r[1].setText(state);
        r[1].setTextColor(color);
        b.setProgress((int) (Math.min(d, t) * 1000 / t));
    }
}
