package com.asoft.ios;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.Test;

/** Closing the guest races input, queued commands and a busy monitor. None may strand a caller. */
public class QmpShutdownTest {
    @Test
    public void lateInputAfterCloseIsFinishedWithoutWriting() throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        Qmp q = new Qmp(bytes);
        q.close();
        assertNull(q.send("{\"execute\":\"query-status\"}").get(1, TimeUnit.SECONDS));
        q.key("f1");
        q.touch(0.5f, 0.5f, false);
        q.close();
        assertEquals(0, bytes.size());
    }

    @Test
    public void closeCompletesBothQueuedAndInFlightCommands() throws Exception {
        CountDownLatch writing = new CountDownLatch(1), release = new CountDownLatch(1), wrote = new CountDownLatch(1);
        AtomicInteger writes = new AtomicInteger();
        Qmp q = new Qmp(new OutputStream() {
            @Override
            public void write(int b) {
                throw new AssertionError("expected a whole command");
            }

            @Override
            public void write(byte[] b) {
                writes.incrementAndGet();
                writing.countDown();
                // Model a blocked socket independently of executor interruption.
                while (release.getCount() != 0) {
                    try {
                        release.await();
                    } catch (InterruptedException ignored) {
                    }
                }
                wrote.countDown();
            }
        });
        try {
            CompletableFuture<String> first = q.send("first");
            assertTrue(writing.await(2, TimeUnit.SECONDS));
            CompletableFuture<String> second = q.send("second");
            q.close();
            assertNull(first.get(1, TimeUnit.SECONDS));
            assertNull(second.get(1, TimeUnit.SECONDS));
            release.countDown();
            assertTrue(wrote.await(2, TimeUnit.SECONDS));
            assertEquals(1, writes.get());
        } finally {
            release.countDown();
            q.close();
        }
    }

    @Test
    public void failedWriteReleasesEveryQueuedCommand() throws Exception {
        Qmp q = new Qmp(new OutputStream() {
            @Override
            public void write(int b) throws IOException {
                throw new IOException("monitor disconnected");
            }
        });
        try {
            List<CompletableFuture<String>> replies = new ArrayList<>();
            for (int i = 0; i < 100; i++) {
                replies.add(q.send("command-" + i));
            }
            for (CompletableFuture<String> reply : replies) {
                assertNull(reply.get(2, TimeUnit.SECONDS));
            }
        } finally {
            q.close();
        }
    }

    @Test
    public void closingDuringInputDoesNotThrowOrStrandCommands() throws Exception {
        for (int run = 0; run < 20; run++) {
            Qmp q = new Qmp(new ByteArrayOutputStream());
            CountDownLatch start = new CountDownLatch(1);
            CompletableFuture<Void> sending = CompletableFuture.runAsync(() -> {
                try {
                    start.await();
                    for (int i = 0; i < 100; i++) {
                        q.send("command-" + i).get(2, TimeUnit.SECONDS);
                    }
                } catch (Exception e) {
                    throw new RuntimeException(e);
                }
            });
            start.countDown();
            q.close();
            sending.get(3, TimeUnit.SECONDS);
        }
    }
}
