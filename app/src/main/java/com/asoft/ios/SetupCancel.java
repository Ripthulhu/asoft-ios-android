package com.asoft.ios;

import java.io.File;

/**
 * Which setup a Cancel is for, and which work folder that is (SetupCancelTest). The service's state says which target
 * ran last, and a fresh process (Android killed the app while a setup was stopped) says "ios16" whatever ran before:
 * a Cancel of a stopped run, with no worker in the service, therefore names its target (SetupService.cancel(c, target)),
 * so that it deletes that setup's work and not another's.
 */
final class SetupCancel {
    /** The targets a Cancel names: iOS 16 (PhoneSetup) and iOS 26 / watchOS (PhoneSetup26). */
    static final String IOS16 = "ios16";
    static final String A26 = "a26";

    private SetupCancel() {
    }

    /** The target a Cancel is for: the one it names, else the one the service ran last (@last, State.target). */
    static String target(String named, String last) {
        return named != null ? named : last;
    }

    /**
     * The work folder a Cancel of @target deletes (iOS 26 / watchOS: SetupService.cancelA26 trims it, and keeps the
     * part an installed OS rests on), or null for a target that is not one of the two: nothing is deleted for it.
     */
    static File work(String target, File ios16Work, File a26Work) {
        if (IOS16.equals(target)) {
            return ios16Work;
        }
        if (A26.equals(target)) {
            return a26Work;
        }
        return null;
    }
}
