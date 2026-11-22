package com.asoft.ios;

import java.util.Locale;

/**
 * The failures that are their own answer (OwnAnswerTest): the phone has too little room for a setup, or the file
 * picked for an import is empty or ends early. The message says all there is to say and nothing in the app's
 * logs would add to it, so these stops write no record (no Share log, no Report on GitHub, no notice); the
 * message alone is shown. One place holds the texts, so the code that throws them and the code that
 * recognizes them cannot drift apart. Everything else keeps its record. Pure, so it is tested without Android.
 */
final class OwnAnswer {
    /** What the room message starts with (SetupService's check before a run, PhoneSetup26's before a step). */
    static final String NO_ROOM = "Not enough room:";
    /** What the three reads of Installer say when a bundle file runs out before its tar does (an empty or cut-short file). */
    static final String FILE_ENDS_EARLY = "the file ends early";

    /** What Installer says when the first tar header of a picked file does not check out: the file is no setup bundle at all (A#171). */
    static final String NOT_A_BUNDLE = "not a setup file";

    private OwnAnswer() {}

    /** The setup's "not enough room" message, from the bytes free and the bytes the run needs. */
    static String noRoom(long freeBytes, long needBytes) {
        return String.format(Locale.ROOT,
                NO_ROOM + " %.1f GB free, about %.1f GB needed. Free some space, then tap Resume.", freeBytes / 1e9, needBytes / 1e9);
    }

    /** Whether @message is one of these answers: a stop that gets no record. False for null and for every other message. */
    static boolean is(String message) {
        return message != null && (message.startsWith(NO_ROOM) || message.contains(FILE_ENDS_EARLY) || message.contains(NOT_A_BUNDLE));
    }

    /** The import's status line for a failure with @message: the empty or short file gets its own words, the rest "Not set up: " + message. */
    static String importText(String message) {
        if (message != null && message.contains(FILE_ENDS_EARLY)) {
            return "Not set up: the file is empty or ends early. Use the .asoft file that the PC version of ASoftware made "
                    + "(Send-ToPhone.cmd) and copy it to the phone again. Without a PC, use Set up in the iOS 16 or iOS 26 part: "
                    + "the phone downloads iOS from Apple itself.";
        }
        if (message != null && message.contains(NOT_A_BUNDLE)) {
            return "Not set up: this is not a setup file. Use the .asoft file that the PC version of ASoftware made "
                    + "(Send-ToPhone.cmd). Without a PC, use Set up in the iOS 16 or iOS 26 part: "
                    + "the phone downloads iOS from Apple itself.";
        }
        return "Not set up: " + message;
    }
}
