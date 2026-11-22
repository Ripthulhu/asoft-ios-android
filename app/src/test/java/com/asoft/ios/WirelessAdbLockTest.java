package com.asoft.ios;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import java.lang.reflect.Field;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import org.junit.Test;

/**
 * The settings screen asks WirelessAdb.connected() on the main thread every 1.5 s; shell() holds LOCK through a
 * connection attempt (about 12 s with Wireless debugging off). connected() waited for it: ANR (A#234, A#297).
 */
public class WirelessAdbLockTest {
    @Test
    public void connectedDoesNotWaitForTheLock() throws Exception {
        Field f = WirelessAdb.class.getDeclaredField("LOCK");
        f.setAccessible(true);
        Object lock = f.get(null);
        CountDownLatch held = new CountDownLatch(1), done = new CountDownLatch(1);
        Thread holder = new Thread(() -> {
            synchronized (lock) {           // as shell() does while it looks for adbd's port
                held.countDown();
                try {
                    done.await(10, TimeUnit.SECONDS);
                } catch (InterruptedException ignored) {
                    // the test ends
                }
            }
        });
        holder.start();
        assertTrue(held.await(5, TimeUnit.SECONDS));
        long t0 = System.nanoTime();
        boolean c = WirelessAdb.connected();
        long ms = (System.nanoTime() - t0) / 1_000_000;
        done.countDown();
        holder.join(5_000);
        assertFalse(c);                     // no connection in a JVM test
        assertTrue("connected() waited " + ms + " ms for the lock", ms < 500);
    }
}
