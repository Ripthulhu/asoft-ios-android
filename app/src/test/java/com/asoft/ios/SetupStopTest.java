package com.asoft.ios;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import java.io.IOException;
import org.junit.Test;

public class SetupStopTest {
    private static String reason(boolean cancel, boolean downloading, boolean decrypting, boolean pause, boolean noWifi,
            boolean noNetwork) {
        return SetupStop.reason(cancel, downloading, decrypting, pause, noWifi, noNetwork);
    }

    @Test
    public void nothingAskedMeansGoOn() {
        assertNull(reason(false, false, false, false, false, false));
        assertNull(reason(false, true, false, false, false, false));
        assertNull(reason(false, false, true, false, false, false));
    }

    @Test
    public void cancelDominatesEverything() {
        for (int bits = 0; bits < 32; bits++) {
            assertEquals("bits " + bits, SetupStop.CANCEL,
                    reason(true, (bits & 1) != 0, (bits & 2) != 0, (bits & 4) != 0, (bits & 8) != 0, (bits & 16) != 0));
        }
    }

    @Test
    public void aStepThatIsNeitherADownloadNorADecryptStopsOnlyForCancel() {
        // a helper VM job is held for Pause, never stopped (it would have to start over)
        assertNull(reason(false, false, false, true, false, false));
        assertNull(reason(false, false, false, false, true, false));
        assertNull(reason(false, false, false, false, false, true));
        assertNull(reason(false, false, false, true, true, true));
        assertEquals(SetupStop.CANCEL, reason(true, false, false, false, false, false));
    }

    @Test
    public void aDecryptStopsForPauseOnly() {
        assertEquals(SetupStop.PAUSE, reason(false, false, true, true, false, false));
        assertEquals(SetupStop.PAUSE, reason(false, false, true, true, true, true));
        assertNull(reason(false, false, true, false, true, false));
        assertNull(reason(false, false, true, false, false, true));
        assertNull(reason(false, false, true, false, true, true));
    }

    @Test
    public void aDownloadStopsForPauseNoWifiAndNoNetwork() {
        assertEquals(SetupStop.PAUSE, reason(false, true, false, true, false, false));
        assertEquals(SetupStop.NO_WIFI, reason(false, true, false, false, true, false));
        assertEquals(SetupStop.NO_NETWORK, reason(false, true, false, false, false, true));
    }

    @Test
    public void pauseComesFirstThenWifiThenNetwork() {
        assertEquals(SetupStop.PAUSE, reason(false, true, false, true, true, true));
        assertEquals(SetupStop.PAUSE, reason(false, true, false, true, true, false));
        assertEquals(SetupStop.PAUSE, reason(false, true, false, true, false, true));
        assertEquals(SetupStop.NO_WIFI, reason(false, true, false, false, true, true));
    }

    @Test
    public void theReasonsAreInPlainWords() {
        assertEquals("Pause", SetupStop.PAUSE);
        assertTrue(SetupStop.NO_WIFI.contains("Wi-Fi"));
        assertTrue(SetupStop.NO_NETWORK.contains("network"));
    }

    @Test
    public void stopsExactlyWhereStopNowDidBefore() {
        // the old SetupService.stopNow(): cancel, or a decrypt with Pause, or a download with Pause / no Wi-Fi / no network
        for (int bits = 0; bits < 64; bits++) {
            boolean cancel = (bits & 1) != 0, downloading = (bits & 2) != 0, decrypting = (bits & 4) != 0;
            boolean pause = (bits & 8) != 0, noWifi = (bits & 16) != 0, noNetwork = (bits & 32) != 0;
            boolean old = cancel || (decrypting && pause) || (downloading && (pause || noWifi || noNetwork));
            assertEquals("bits " + bits, old, reason(cancel, downloading, decrypting, pause, noWifi, noNetwork) != null);
        }
    }

    @Test
    public void aBareStoppedAfterAWaitReasonIsOwn() {
        assertTrue(SetupStop.isOwnStop(new IOException("stopped"), SetupStop.PAUSE));
        assertTrue(SetupStop.isOwnStop(new IOException("stopped"), SetupStop.NO_WIFI));
        assertTrue(SetupStop.isOwnStop(new IOException("stopped"), SetupStop.NO_NETWORK));
    }

    @Test
    public void aBareStoppedWithoutAWaitReasonIsNotOwn() {
        assertFalse(SetupStop.isOwnStop(new IOException("stopped"), null));
        assertFalse(SetupStop.isOwnStop(new IOException("stopped"), SetupStop.CANCEL));
    }

    @Test
    public void aRealErrorIsNeverOwn() {
        String[] errors = {
                "connection reset",
                "the connection ended early",
                "HTTP 404",
                "Not enough room: 1.2 GB free, about 20.0 GB needed. Free some space, then tap Resume.",
                "Unable to resolve host \"updates.cdn-apple.com\": No address associated with hostname",
        };
        for (String m : errors) {
            assertFalse(m, SetupStop.isOwnStop(new IOException(m), SetupStop.PAUSE));
            assertFalse(m, SetupStop.isOwnStop(new IOException(m), SetupStop.NO_NETWORK));
        }
        // (an IpswFetch.HttpError is an IOException with a message like these)
        assertFalse(SetupStop.isOwnStop(new IOException("HTTP 403"), SetupStop.NO_WIFI));
        assertFalse(SetupStop.isOwnStop(new IOException(), SetupStop.PAUSE));
        assertFalse(SetupStop.isOwnStop(new IOException((String) null), SetupStop.PAUSE));
    }

    @Test
    public void stoppedInsideALongerMessageIsNotOwn() {
        assertFalse(SetupStop.isOwnStop(new IOException("iOS stopped during its first start (null)"), SetupStop.PAUSE));
        assertFalse(SetupStop.isOwnStop(new IOException("stopped: Unable to resolve host"), SetupStop.NO_NETWORK));
        assertFalse(SetupStop.isOwnStop(new IOException("Stopped"), SetupStop.PAUSE));
        assertFalse(SetupStop.isOwnStop(new IOException(" stopped"), SetupStop.PAUSE));
        assertFalse(SetupStop.isOwnStop(new IOException("stopped "), SetupStop.PAUSE));
    }

    @Test
    public void noException() {
        assertFalse(SetupStop.isOwnStop(null, SetupStop.PAUSE));
    }
}
