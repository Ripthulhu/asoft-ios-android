package com.asoft.ios;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

/**
 * The checks of a tar header before Installer.untar trusts it (InstallerTarTest): the checksum, and a size that parses.
 * Pure, so it is tested without Android.
 */
final class TarHeader {
    private TarHeader() {}

    private static String field(byte[] h, int at, int len) {
        int n = 0;
        while (n < len && h[at + n] != 0) {
            n++;
        }
        return new String(h, at, n, StandardCharsets.UTF_8).trim();
    }

    private static long size(byte[] h) {
        if ((h[124] & 0x80) != 0) {         // GNU base-256
            long v = 0;
            for (int i = 125; i < 136; i++) {
                v = (v << 8) | (h[i] & 0xff);
            }
            return v;
        }
        String s = field(h, 124, 12);
        return s.isEmpty() ? 0 : Long.parseLong(s, 8);
    }

    /** The header's checksum (bytes 148-155) as the tar format has it: an octal number, ended by a NUL and/or spaces; -1 if it is none. */
    private static long storedChecksum(byte[] h) {
        int a = 148, b = 156;
        while (a < b && (h[a] == ' ' || h[a] == 0)) {
            a++;
        }
        while (b > a && (h[b - 1] == ' ' || h[b - 1] == 0)) {
            b--;
        }
        if (a == b) {
            return -1;
        }
        long v = 0;
        for (int i = a; i < b; i++) {
            if (h[i] < '0' || h[i] > '7') {
                return -1;
            }
            v = v * 8 + (h[i] - '0');
        }
        return v;
    }

    /** Whether the checksum of the header @h is right: the sum of its 512 bytes with the checksum field as spaces, unsigned or signed (old tars summed signed). */
    static boolean checksumOk(byte[] h) {
        long stored = storedChecksum(h);
        if (stored < 0) {
            return false;
        }
        long unsigned = 0, signed = 0;
        for (int i = 0; i < 512; i++) {
            byte x = (i >= 148 && i < 156) ? (byte) ' ' : h[i];
            unsigned += x & 0xff;
            signed += x;
        }
        return stored == unsigned || stored == signed;
    }

    /**
     * The size a tar header @h (not the end-of-archive block) says, after the header was checked: its checksum, and a size
     * that parses and is not negative. The first header of a file that fails is no tar at all, so the file is no setup
     * bundle (OwnAnswer.NOT_A_BUNDLE, A#171: a 0.11 GB file that was no tar ended as a NumberFormatException with a crash
     * record); a bad header later is a damaged file. Never a NumberFormatException.
     */
    static long checkedSize(byte[] h, boolean first, long at) throws IOException {
        if (!checksumOk(h)) {
            throw badHeader(first, at, "its checksum is wrong");
        }
        try {
            long size = size(h);
            if (size < 0) {
                throw badHeader(first, at, "its size is negative");
            }
            return size;
        } catch (NumberFormatException e) {
            throw badHeader(first, at, "its size is no number");
        }
    }

    private static IOException badHeader(boolean first, long at, String why) {
        return first ? new IOException(OwnAnswer.NOT_A_BUNDLE + " (the first block is no tar header: " + why + ")")
                : new IOException("the setup file is damaged: the tar header at byte " + at + " is bad (" + why + ")");
    }
}
