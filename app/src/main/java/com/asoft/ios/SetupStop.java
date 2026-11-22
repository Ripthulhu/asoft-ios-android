package com.asoft.ios;

import java.io.IOException;

/**
 * Why a setup step is asked to stop, and whether the "stopped" error that follows was that request (SetupStopTest).
 * SetupService.stopNow() is what the downloads and the helper steps ask between pieces of work; the step then ends
 * with IOException("stopped"). A Cancel is the user's end of the setup. A Pause, a download without Wi-Fi (Download
 * on Wi-Fi only) and a download without a network are waits: nothing failed, the run goes on from what is done once
 * they are over. They used to be told apart from a real error only by asking again when the exception arrived
 * (A#155: the network was back by then, or Pause was followed by Resume at once, and the screen said "stopped").
 */
final class SetupStop {
    /** The reason of a Cancel: the setup ends. */
    static final String CANCEL = "Cancel";
    static final String PAUSE = "Pause";
    static final String NO_WIFI = "no Wi-Fi (Download on Wi-Fi only is on)";
    static final String NO_NETWORK = "no network";

    private SetupStop() {
    }

    /**
     * Why the step should stop now: CANCEL, a wait reason, or null (go on). A download stops for Pause, for want of
     * Wi-Fi and for want of a network; a decrypt only for Pause (it goes on from its next cluster); any other step
     * only for Cancel (a helper VM job is held instead, it would have to start over).
     */
    static String reason(boolean cancel, boolean downloading, boolean decrypting, boolean pause, boolean noWifi, boolean noNetwork) {
        if (cancel) {
            return CANCEL;
        }
        if (pause && (downloading || decrypting)) {
            return PAUSE;
        }
        if (downloading) {
            if (noWifi) {
                return NO_WIFI;
            }
            if (noNetwork) {
                return NO_NETWORK;
            }
        }
        return null;
    }

    /**
     * Whether @e is the bare "stopped" of a stop that reason() asked for with a wait reason (@reasonSeen, null when
     * none was asked for or only a Cancel). Any other error stays an error, whatever was asked for before it.
     */
    static boolean isOwnStop(IOException e, String reasonSeen) {
        return reasonSeen != null && !CANCEL.equals(reasonSeen) && e != null && "stopped".equals(e.getMessage());
    }
}
