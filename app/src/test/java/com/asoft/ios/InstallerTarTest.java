package com.asoft.ios;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Random;

import org.junit.Test;

public class InstallerTarTest {
    /** A ustar header for @name with @size, its checksum written the usual way (six octal digits, NUL, space). */
    private static byte[] header(String name, long size) {
        byte[] h = new byte[512];
        byte[] n = name.getBytes(StandardCharsets.US_ASCII);
        System.arraycopy(n, 0, h, 0, n.length);
        put(h, 100, "0000644");
        put(h, 108, "0000000");
        put(h, 116, "0000000");
        put(h, 124, String.format("%011o", size));
        put(h, 136, "00000000000");
        h[156] = '0';
        put(h, 257, "ustar");
        put(h, 263, "00");
        long sum = 0;
        for (int i = 0; i < 512; i++) {
            sum += (i >= 148 && i < 156) ? ' ' : (h[i] & 0xff);
        }
        put(h, 148, String.format("%06o", sum));
        h[154] = 0;
        h[155] = ' ';
        return h;
    }

    private static void put(byte[] h, int at, String s) {
        byte[] b = s.getBytes(StandardCharsets.US_ASCII);
        System.arraycopy(b, 0, h, at, b.length);
    }

    private static String refusal(byte[] h, boolean first) {
        try {
            TarHeader.checkedSize(h, first, 0);
        } catch (IOException e) {
            return e.getMessage();
        }
        fail("accepted");
        return null;
    }

    @Test
    public void aValidHeaderGivesItsSize() throws IOException {
        assertEquals(1234, TarHeader.checkedSize(header("disk.qcow2", 1234), true, 0));
        assertEquals(0, TarHeader.checkedSize(header("a", 0), true, 0));
    }

    @Test
    public void theSignedChecksumOfOldTarsIsAccepted() throws IOException {
        byte[] h = header("name-é", 10);
        h[0] = (byte) 0xe9;     // a high byte: the signed sum differs from the unsigned one
        long signed = 0;
        for (int i = 0; i < 512; i++) {
            signed += (i >= 148 && i < 156) ? ' ' : h[i];
        }
        put(h, 148, String.format("%06o", signed));
        h[154] = 0;
        h[155] = ' ';
        assertEquals(10, TarHeader.checkedSize(h, true, 0));
    }

    @Test
    public void aNonTarFirstBlockIsNotABundle() {
        byte[] h = new byte[512];
        new Random(42).nextBytes(h);
        String m = refusal(h, true);
        assertTrue(m, m.startsWith(OwnAnswer.NOT_A_BUNDLE));
        assertTrue(OwnAnswer.is(m));
    }

    @Test
    public void manyRandomBlocksNeverEscapeAsANumberFormatException() {
        Random r = new Random(7);
        for (int i = 0; i < 2000; i++) {
            byte[] h = new byte[512];
            r.nextBytes(h);
            try {
                TarHeader.checkedSize(h, i % 2 == 0, 0);
            } catch (IOException e) {
                // fine
            }
        }
    }

    @Test
    public void theStartOfAZipIsNotABundle() {
        byte[] h = new byte[512];
        h[0] = 'P';
        h[1] = 'K';
        h[2] = 3;
        h[3] = 4;
        for (int i = 4; i < 512; i++) {
            h[i] = (byte) (i * 31);
        }
        assertTrue(refusal(h, true).startsWith(OwnAnswer.NOT_A_BUNDLE));
    }

    @Test
    public void aSizeThatIsNoNumberWithARightChecksumIsRefusedPlainly() {
        // the size field of A#171, "2?": the checksum is made to fit, so only the size is bad
        byte[] h = header("disk.qcow2", 1);
        put(h, 124, "2?         ");
        long sum = 0;
        for (int i = 0; i < 512; i++) {
            sum += (i >= 148 && i < 156) ? ' ' : (h[i] & 0xff);
        }
        put(h, 148, String.format("%06o", sum));
        h[154] = 0;
        h[155] = ' ';
        String m = refusal(h, true);
        assertTrue(m, m.startsWith(OwnAnswer.NOT_A_BUNDLE));
    }

    @Test
    public void aBadHeaderLaterIsADamagedFileThatKeepsItsRecord() {
        byte[] h = header("disk.qcow2", 100);
        h[0] ^= 0x55;       // the checksum no longer fits
        String m = refusal(h, false);
        assertTrue(m, m.contains("damaged"));
        assertFalse(OwnAnswer.is(m));
    }

    @Test
    public void anEmptyOrShortFileKeepsItsOwnAnswer() {
        assertTrue(OwnAnswer.is(OwnAnswer.FILE_ENDS_EARLY + ": incomplete copy?"));
    }

    @Test
    public void notABundleHasAPlainLineAndNoRecord() {
        String m = OwnAnswer.NOT_A_BUNDLE + " (the first block is no tar header: its checksum is wrong)";
        assertTrue(OwnAnswer.is(m));
        String t = OwnAnswer.importText(m);
        assertTrue(t, t.startsWith("Not set up: this is not a setup file."));
        assertTrue(t.contains("Send-ToPhone.cmd"));
        assertFalse(t.contains("checksum"));
    }
}
