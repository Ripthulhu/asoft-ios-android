package com.asoft.ios;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class OwnAnswerTest {
    @Test
    public void noRoomKeepsTheOldText() {
        // the literal SetupService built before OwnAnswer existed
        assertEquals("Not enough room: 2.3 GB free, about 6.5 GB needed. Free some space, then tap Resume.",
                OwnAnswer.noRoom(2_300_000_000L, 6_500_000_000L));
        assertEquals("Not enough room: 1.4 GB free, about 26.5 GB needed. Free some space, then tap Resume.",
                OwnAnswer.noRoom(1_400_000_000L, 26_500_000_000L));
    }

    @Test
    public void noRoomIsOwnAnswerWhateverTheNumbers() {
        assertTrue(OwnAnswer.is(OwnAnswer.noRoom(2_300_000_000L, 6_500_000_000L)));
        assertTrue(OwnAnswer.is(OwnAnswer.noRoom(0L, 6_500_000_000L)));
        assertTrue(OwnAnswer.is(OwnAnswer.noRoom(0L, 0L)));
        assertTrue(OwnAnswer.is(OwnAnswer.noRoom(Long.MAX_VALUE, Long.MAX_VALUE)));
        assertTrue(OwnAnswer.is(OwnAnswer.noRoom(512_000_000_000L, 1_500_000_000_000L)));
        assertTrue(OwnAnswer.noRoom(0L, 6_500_000_000L).startsWith("Not enough room: 0.0 GB free, about 6.5 GB needed."));
    }

    @Test
    public void noRoomUsesADotWhateverTheLanguage() {
        java.util.Locale was = java.util.Locale.getDefault();
        try {
            java.util.Locale.setDefault(java.util.Locale.forLanguageTag("tr-TR"));
            assertEquals("Not enough room: 2.3 GB free, about 6.5 GB needed. Free some space, then tap Resume.",
                    OwnAnswer.noRoom(2_300_000_000L, 6_500_000_000L));
        } finally {
            java.util.Locale.setDefault(was);
        }
    }

    @Test
    public void theIos26StepRoomMessageIsOwnAnswerToo() {
        // PhoneSetup26's check before a step starts the same way
        assertTrue(OwnAnswer.is("Not enough room: 1.2 GB free, the next step needs about 3.5 GB. Free some space, then tap Resume."));
    }

    @Test
    public void theFileEndingEarlyIsOwnAnswer() {
        assertTrue(OwnAnswer.is(OwnAnswer.FILE_ENDS_EARLY));
        assertTrue(OwnAnswer.is("the file ends early"));
        assertTrue(OwnAnswer.is("the file ends early: incomplete copy?"));
        assertTrue(OwnAnswer.is("Not set up: the file ends early"));
        assertTrue(OwnAnswer.is("Not set up: the file ends early: incomplete copy?"));
    }

    @Test
    public void everythingElseKeepsItsRecord() {
        assertFalse(OwnAnswer.is(null));
        assertFalse(OwnAnswer.is(""));
        assertFalse(OwnAnswer.is("not an ASoftware iOS bundle: no asoft-bundle.json first"));
        assertFalse(OwnAnswer.is("not an ASoftware iOS bundle: no payload.bin"));
        assertFalse(OwnAnswer.is("not a whole iOS 26 bundle: no disk.qcow2"));
        assertFalse(OwnAnswer.is("not enough space: the disk needs 6.5 GB and 1.0 GB more stay free, 2.0 GB are free"));
        assertFalse(OwnAnswer.is("Apple's server refused the download (HTTP 403)."));
        assertFalse(OwnAnswer.is("stopped"));
        assertFalse(OwnAnswer.is("No internet connection (Apple's server cannot be found). Tap Resume once the phone is online."));
        assertFalse(OwnAnswer.is("Apple's servers stopped answering. Tap Resume: it goes on where it stopped."));
        assertFalse(OwnAnswer.is("The phone is full. Free some space, then tap Resume."));
        assertFalse(OwnAnswer.is("the tar ends early"));
        assertFalse(OwnAnswer.is("the AEA file ends early (at 1024)"));
        assertFalse(OwnAnswer.is("The setup stopped on an error of the app's (java.lang.NullPointerException). Tap Resume to try again; please share the log."));
        // only a start counts for the room message, not a mention
        assertFalse(OwnAnswer.is("setup stopped: Not enough room: 1.4 GB free"));
    }

    @Test
    public void importTextGivesTheShortFileItsOwnWords() {
        for (String m : new String[] {"the file ends early", "the file ends early: incomplete copy?"}) {
            String t = OwnAnswer.importText(m);
            assertTrue(t, t.startsWith("Not set up: "));
            assertTrue(t, t.contains("empty or ends early"));
            assertTrue(t, t.contains("PC version of ASoftware"));
            assertTrue(t, t.contains(".asoft"));
            assertFalse(t, t.contains("incomplete copy"));
        }
    }

    @Test
    public void importTextKeepsEveryOtherMessage() {
        String[] others = {
            "not an ASoftware iOS bundle: no asoft-bundle.json first",
            "not enough space: the disk needs 6.5 GB and 1.0 GB more stay free, 2.0 GB are free",
            "disk.qcow2 is not a qcow2 image",
            "",
        };
        for (String m : others) {
            assertEquals("Not set up: " + m, OwnAnswer.importText(m));
        }
        assertEquals("Not set up: null", OwnAnswer.importText(null));
    }
}
