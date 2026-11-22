package com.asoft.ios;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.junit.After;
import org.junit.Before;
import org.junit.Test;

/**
 * GuestConsole against a stand-in for the guest's bash on the serial console: what the tty and bash do with the bytes
 * typed (echo, Ctrl-C, a line that stays open in a quote and shows "> ", a command that never ends).
 */
public class GuestConsoleTest {
    private Shell shell;
    private GuestConsole con;

    @Before
    public void start() throws IOException {
        shell = new Shell();
        con = new GuestConsole(shell);
    }

    @After
    public void stop() {
        con.close();
        shell.close();
    }

    @Test
    public void aCommandThatStartedIsNotTypedAgainWhileItsEndIsAwaited() {
        // bash printed the start marker and the command does not end (A#259, A#284: `cat` of the plist in a stuck guest)
        shell.hangNext = true;
        assertNull(con.run("cat /x", 2500, 600));
        // before the fix every 600 ms was another copy of the line in the tty's 1 KB input queue
        assertEquals(1, shell.commandLines());
        assertEquals(SetupTick.Poll.STARTED, con.lastPoll());
    }

    @Test
    public void aSlowAnswerIsWaitedForWithoutTypingTheLineAgain() {
        shell.endDelayMs = 1500;
        assertEquals("out:cat /x", con.run("cat /x", 4000, 500));
        assertEquals(1, shell.commandLines());
        assertEquals(SetupTick.Poll.DONE, con.lastPoll());
    }

    @Test
    public void aCommandThatNeverStartedIsTypedAgainWithANewTag() {
        shell.dropNext = 1;
        assertEquals("out:cat /x", con.run("cat /x", 4000, 700));
        assertEquals(2, shell.commandLines());
        assertEquals(SetupTick.Poll.DONE, con.lastPoll());
    }

    @Test
    public void aCommandThatNeverStartedStaysSentInThePollAccounting() {
        // the console went silent: "command sent, never started", for every line typed
        shell.dropNext = 100;
        assertNull(con.run("cat /x", 1800, 600));
        assertTrue(shell.commandLines() >= 2);
        assertEquals(SetupTick.Poll.SENT, con.lastPoll());
        assertEquals("shell silent 3 min (command sent, never started)", SetupTick.pollText(con.lastPoll(), false, 3));
    }

    @Test
    public void aResetEndsTheCommandThatNeverEndedAndTheLineGoesThrough() {
        shell.hangNext = true;
        assertNull(con.run("cat /x", 1500, 600));
        assertEquals(0, shell.ctrlC.get());
        // the next poll is typed after Ctrl-C, which ends the one that hangs
        assertEquals("out:cat /y", con.run("cat /y", 4000, 1500, true));
        assertEquals(1, shell.ctrlC.get());
        assertEquals(SetupTick.Poll.DONE, con.lastPoll());
    }

    @Test
    public void aConsoleThatEndsInTheContinuationPromptGetsACtrlC() throws Exception {
        assertEquals("out:true", con.run("true", 3000, 1000));
        // a byte of an earlier line was lost: bash waits for the closing quote and every line goes into it
        shell.openQuote();
        waitFor(() -> con.seen("\n> "));
        int before = shell.ctrlC.get();
        assertEquals("out:cat /x", con.run("cat /x", 4000, 1000));
        assertEquals(before + 1, shell.ctrlC.get());
        assertEquals(2, shell.commandLines());          // ("true", then "cat /x" once: the quote did not swallow it)
    }

    @Test
    public void theContinuationPromptIsAnsweredOnceNotAtEveryCommand() throws Exception {
        assertEquals("out:true", con.run("true", 3000, 1000));
        shell.openQuote();
        waitFor(() -> con.seen("\n> "));
        assertEquals("out:a", con.run("a", 4000, 1000));
        int after = shell.ctrlC.get();
        assertEquals("out:b", con.run("b", 3000, 1000));
        assertEquals(after, shell.ctrlC.get());
    }

    @Test
    public void aResetAlsoClearsTheOpenQuoteWithOneCtrlC() throws Exception {
        assertEquals("out:true", con.run("true", 3000, 1000));
        shell.openQuote();
        waitFor(() -> con.seen("\n> "));
        int before = shell.ctrlC.get();
        assertEquals("out:cat /x", con.run("cat /x", 4000, 1500, true));
        assertEquals(before + 1, shell.ctrlC.get());
    }

    @Test
    public void onlyANewLineAndGreaterThanIsTheContinuationPrompt() {
        assertTrue(GuestConsole.endsInContinuation("echo @@G1\"S\"@@; cat x\r\n> "));
        assertTrue(GuestConsole.endsInContinuation("a\n> "));
        assertFalse(GuestConsole.endsInContinuation("> "));
        assertFalse(GuestConsole.endsInContinuation("a> "));
        assertFalse(GuestConsole.endsInContinuation("a\n>"));
        assertFalse(GuestConsole.endsInContinuation("a\n> b"));
        assertFalse(GuestConsole.endsInContinuation("# "));
        assertFalse(GuestConsole.endsInContinuation(""));
    }

    // -- the stand-in --------------------------------------------------------------------------------------

    private interface Cond {
        boolean ok();
    }

    private static void waitFor(Cond c) throws InterruptedException {
        for (int i = 0; i < 100 && !c.ok(); i++) {
            Thread.sleep(50);
        }
        assertTrue("never happened", c.ok());
    }

    /** The guest's console: a tty (echo, Ctrl-C, Ctrl-U) and the bash behind it, as far as GuestConsole meets them. */
    private static final class Shell implements GuestConsole.Opener {
        private static final Pattern CMD = Pattern.compile("echo @@(\\w+?)\"S\"@@; (.*); echo @@\\1\"E\"@@");

        private final ServerSocket server;
        private volatile Socket conn;
        private volatile boolean closed;

        /** Lines the tty got, whole (CR sent). */
        private final List<String> lines = new CopyOnWriteArrayList<>();
        final AtomicInteger ctrlC = new AtomicInteger();
        /** The next command line(s) the tty loses: no echo of an answer, bash never sees them. */
        volatile int dropNext;
        /** The next command prints its start marker and then runs for ever (until Ctrl-C). */
        volatile boolean hangNext;
        /** A command's end comes this long after its start. */
        volatile long endDelayMs;

        private volatile boolean hanging;
        private volatile String open;       // the text of a line left open by a quote, null at the prompt
        private volatile long epoch;        // a Ctrl-C ends what a timer would still print

        Shell() throws IOException {
            server = new ServerSocket(0, 1, InetAddress.getLoopbackAddress());
            Thread t = new Thread(() -> {
                try {
                    while (!closed) {
                        Socket s = server.accept();
                        conn = s;
                        serve(s);
                    }
                } catch (IOException ignored) {
                    // closed
                }
            }, "fake-guest");
            t.setDaemon(true);
            t.start();
        }

        @Override
        public GuestConsole.Link open() throws IOException {
            Socket s = new Socket(InetAddress.getLoopbackAddress(), server.getLocalPort());
            return new GuestConsole.Link() {
                @Override
                public InputStream in() throws IOException {
                    return s.getInputStream();
                }

                @Override
                public OutputStream out() throws IOException {
                    return s.getOutputStream();
                }

                @Override
                public void close() throws IOException {
                    s.close();
                }
            };
        }

        /** Lines typed that carry a command (the connect's bare CR and the Ctrl-C's are not). */
        int commandLines() {
            int n = 0;
            for (String l : lines) {
                if (l.startsWith("echo @@")) {
                    n++;
                }
            }
            return n;
        }

        /** bash is waiting for the rest of a line (a quote was lost in the tty): it prints its second prompt. */
        void openQuote() {
            open = "echo \"";
            print("\r\n> ");
        }

        void close() {
            closed = true;
            try {
                server.close();
                if (conn != null) {
                    conn.close();
                }
            } catch (IOException ignored) {
                // gone
            }
        }

        private synchronized void print(String s) {
            try {
                Socket c = conn;
                if (c != null) {
                    c.getOutputStream().write(s.getBytes(StandardCharsets.ISO_8859_1));
                    c.getOutputStream().flush();
                }
            } catch (IOException ignored) {
                // the console went
            }
        }

        private void serve(Socket s) throws IOException {
            InputStream in = s.getInputStream();
            StringBuilder typed = new StringBuilder();
            int b;
            while ((b = in.read()) >= 0) {
                if (b == 3) {
                    // ISIG: the tty drops what was typed, bash drops its line, the command is killed
                    ctrlC.incrementAndGet();
                    typed.setLength(0);
                    hanging = false;
                    open = null;
                    epoch++;
                    print("^C\r\n# ");
                } else if (b == 21) {
                    print("\b \b".repeat(typed.length()));
                    typed.setLength(0);
                } else if (b == '\r' || b == '\n') {
                    String line = typed.toString();
                    typed.setLength(0);
                    print("\r\n");
                    enter(line);
                } else {
                    typed.append((char) b);
                    print(String.valueOf((char) b));       // the tty echoes
                }
            }
        }

        private void enter(String line) {
            if (!line.isEmpty()) {
                lines.add(line);
            }
            if (hanging) {
                return;                 // bash is busy: the line waits in the tty's queue (a Ctrl-C drops it)
            }
            if (line.isEmpty() && open == null) {
                print("# ");
                return;
            }
            if (dropNext > 0 && !line.isEmpty()) {
                dropNext--;
                print("# ");
                return;
            }
            String all = open == null ? line : open + "\n" + line;
            if (all.chars().filter(ch -> ch == '"').count() % 2 == 1) {
                open = all;             // an open quote swallows the line
                print("> ");
                return;
            }
            open = null;
            Matcher m = CMD.matcher(all);
            if (!m.matches()) {
                print("sh: " + all + ": command not found\r\n# ");
                return;
            }
            String tag = m.group(1);
            print("@@" + tag + "S@@\r\n");
            if (hangNext) {
                hangNext = false;
                hanging = true;
                return;
            }
            String done = "out:" + m.group(2) + "\r\n@@" + tag + "E@@\r\n# ";
            if (endDelayMs <= 0) {
                print(done);
                return;
            }
            long at = epoch;
            hanging = true;
            Thread t = new Thread(() -> {
                try {
                    Thread.sleep(endDelayMs);
                } catch (InterruptedException e) {
                    return;
                }
                if (epoch == at) {
                    hanging = false;
                    print(done);
                }
            }, "fake-command");
            t.setDaemon(true);
            t.start();
        }
    }
}
