package com.asoft.ios;

import android.net.LocalSocket;
import android.net.LocalSocketAddress;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

/**
 * The guest's root shell (com.asoft.bash on the serial console) for the setup's boots: ios26/scripts/
 * guest-shell.py in Java, over the console's UNIX socket (Guest.startSetup). Each command goes as
 * echo @@TAG"S"@@; CMD; echo @@TAG"E"@@, so its output is told from the console's echo and the kernel's
 * messages; one that never started (no start marker) is sent again with a new tag (idempotent commands only).
 * One that did start is waited for and never typed again: the guest's tty holds ~1 KB of typed input, and a
 * second copy behind a command that runs for ever overflowed it (A#259: the console's tail was ~240 BEL
 * characters), which drops bytes of a line and leaves bash in an open quote (A#284: the echoed poll line, then a
 * lone "> ", bash's PS2). A "> " at the console's end is cleared with Ctrl-C before the next command.
 *
 * While connected, a reader thread drains the console all the time. QEMU's socket chardev writes the
 * guest's console output with the main lock held and waits when the socket is full: a client that stops
 * reading froze the whole watch 30 s after its last command (2026-11-08, the kernel's AppleSEPKeyStore
 * lines filled the socket). guest-shell.py on the PC disconnects after each call, so it never met this.
 */
final class GuestConsole implements AutoCloseable {
    /** A connection to the console: what the guest prints, and what is typed to it. */
    interface Link {
        InputStream in() throws IOException;

        OutputStream out() throws IOException;

        void close() throws IOException;
    }

    /** Opens the connection; null while there is none (the socket is not there yet). The tests give it their own. */
    interface Opener {
        Link open() throws IOException;
    }

    private final Opener opener;
    private Link s;
    private OutputStream out;
    private Thread reader;
    private final StringBuilder buf = new StringBuilder();
    private int n;
    private volatile SetupTick.Poll lastPoll = SetupTick.Poll.NOT_SENT;

    GuestConsole(File path) {
        this(() -> socket(path));
    }

    GuestConsole(Opener opener) {
        this.opener = opener;
    }

    /** The console's UNIX socket (Guest.startSetup makes it), or null when it is not there. */
    private static Link socket(File path) throws IOException {
        if (!path.exists()) {
            return null;
        }
        LocalSocket l = new LocalSocket();
        l.connect(new LocalSocketAddress(path.getPath(), LocalSocketAddress.Namespace.FILESYSTEM));
        return new Link() {
            @Override
            public InputStream in() throws IOException {
                return l.getInputStream();
            }

            @Override
            public OutputStream out() throws IOException {
                return l.getOutputStream();
            }

            @Override
            public void close() throws IOException {
                l.close();
            }
        };
    }

    private synchronized boolean connect() {
        if (s != null) {
            return true;
        }
        try {
            Link l = opener.open();
            if (l == null) {
                return false;
            }
            s = l;
            out = l.out();
            InputStream in = l.in();
            reader = new Thread(() -> drain(l, in), "guest-console");
            reader.setDaemon(true);
            reader.start();
            out.write('\r');
            return true;
        } catch (IOException e) {
            return false;
        }
    }

    private void drain(Link l, InputStream in) {
        byte[] b = new byte[65536];
        try {
            int r;
            while ((r = in.read(b)) >= 0) {
                synchronized (buf) {
                    buf.append(new String(b, 0, r, StandardCharsets.ISO_8859_1));
                    if (buf.length() > (4 << 20)) {
                        buf.delete(0, buf.length() - (1 << 20));
                    }
                }
            }
        } catch (IOException ignored) {
            // closed
        }
        synchronized (this) {
            if (s == l) {
                s = null;
                out = null;
            }
        }
    }

    /** The command's output, or null when it got none within @waitMs (sent again every @retryMs). */
    String run(String cmd, long waitMs, long retryMs) {
        return run(cmd, waitMs, retryMs, false);
    }

    /**
     * As run(); with @reset every send (the first too) goes after a reset: a retry typed onto a half line of the
     * last one (or behind a command still running) never started, and nothing else cleared bash's input.
     *
     * A command that never printed its start marker is typed again every @retryMs (with a new tag). One that did
     * print it is only waited for, up to @waitMs: bash has it, and a second copy would sit in the tty's small input
     * queue behind it. And a console that ends in bash's continuation prompt (a new line and "> ": an open quote
     * that swallows every line typed after it) gets a Ctrl-C before the next command, reset or not.
     */
    String run(String cmd, long waitMs, long retryMs, boolean reset) {
        lastPoll = SetupTick.Poll.NOT_SENT;
        long until = System.currentTimeMillis() + waitMs;
        boolean started = false;
        while (System.currentTimeMillis() < until) {
            if (!connect()) {
                sleep(1000);
                continue;
            }
            n++;
            String tag = "G" + (System.currentTimeMillis() % 1_000_000_000L) + n + "G";
            String start = "@@" + tag + "S@@", end = "@@" + tag + "E@@";
            try {
                OutputStream o;
                synchronized (this) {
                    o = out;
                }
                if (o == null) {
                    continue;
                }
                boolean open = takeContinuation();
                if (reset) {
                    // Ctrl-C ends what runs and gives a new prompt, Ctrl-U drops what is typed, then a fresh line
                    o.write(new byte[] {3, 21, '\r'});
                    o.flush();
                    sleep(300);
                } else if (open) {
                    // an open quote swallows this command too: Ctrl-C closes the line
                    o.write(3);
                    o.flush();
                    sleep(300);
                }
                o.write(("echo @@" + tag + "\"S\"@@; " + cmd + "; echo @@" + tag + "\"E\"@@\r").getBytes(StandardCharsets.UTF_8));
                o.flush();
                advance(SetupTick.Poll.SENT);
                long again = Math.min(until, System.currentTimeMillis() + retryMs);
                // (once bash has started a command of this run, its end is waited for until the deadline: no resend)
                while (System.currentTimeMillis() < (started ? until : again)) {
                    synchronized (buf) {
                        int i = buf.indexOf(start);
                        int j = i >= 0 ? buf.indexOf(end, i + 1) : -1;
                        if (i >= 0) {
                            // (the unquoted marker is bash's own output: the echoed command line has it quoted)
                            advance(j > i ? SetupTick.Poll.DONE : SetupTick.Poll.STARTED);
                            started = true;
                        }
                        if (j > i && i >= 0) {
                            String got = buf.substring(i + start.length(), j);
                            buf.delete(0, j + end.length());
                            return new String(got.getBytes(StandardCharsets.ISO_8859_1), StandardCharsets.UTF_8)
                                    .replaceAll("^[\r\n]+|[\r\n]+$", "");
                        }
                    }
                    sleep(200);
                }
            } catch (IOException e) {
                close();
                sleep(1000);
            }
        }
        return null;
    }

    /** The console's text ends in bash's continuation prompt, a new line and "> ": a line is open (typically an unclosed quote). */
    static boolean endsInContinuation(CharSequence text) {
        int len = text.length();
        return len >= 3 && text.charAt(len - 1) == ' ' && text.charAt(len - 2) == '>' && text.charAt(len - 3) == '\n';
    }

    /**
     * True when the console ends in the continuation prompt; the prompt is taken out of the buffer then, so one
     * Ctrl-C answers it once (the guest's next output replaces it).
     */
    private boolean takeContinuation() {
        synchronized (buf) {
            if (!endsInContinuation(buf)) {
                return false;
            }
            buf.setLength(buf.length() - 2);
            return true;
        }
    }

    /** How far the last run() got (never goes back within one run: a retry has a new tag). */
    SetupTick.Poll lastPoll() {
        return lastPoll;
    }

    private void advance(SetupTick.Poll p) {
        if (p.ordinal() > lastPoll.ordinal()) {
            lastPoll = p;
        }
    }

    /** True when the console has shown @word and no command's answer has taken it out of the buffer since. */
    boolean seen(String word) {
        synchronized (buf) {
            return buf.indexOf(word) >= 0;
        }
    }

    /** True when @cmd printed a line that is exactly @word (the command line's own echo has the word too). */
    boolean says(String cmd, String word, long waitMs) {
        String o = run(cmd, waitMs, 30_000);
        if (o == null) {
            return false;
        }
        for (String l : o.split("\r?\n")) {
            if (l.trim().equals(word)) {
                return true;
            }
        }
        return false;
    }

    private static void sleep(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    @Override
    public synchronized void close() {
        if (s != null) {
            try {
                s.close();
            } catch (IOException ignored) {
                // gone
            }
        }
        s = null;
        out = null;
    }
}
