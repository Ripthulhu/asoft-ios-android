package com.asoft.ios;

import java.io.IOException;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;

/**
 * A small picture of the guest's screen from a QEMU screendump (PPM), for the record of a first start that gave
 * up: is the screen black, the Apple logo (a few colours) or a lock screen (tens to hundreds: 49 on the iOS 16 lock screen of a Linux harness run)? QEMU pads each PPM row to
 * 4 bytes (1179 pixels: 3540 bytes, not 3537), so the row length comes from the file's size, not from the
 * header's width. No Android in here.
 */
final class ScreenSample {
    static final String RAMP = " .:-=+*#%@";
    static final int COLS = 24, ROWS = 48;
    /** A pixel counts as black below this on every channel. */
    private static final int BLACK = 16;

    final int width, height, stride;
    /** Share of the pixels that are not black, 0..100. */
    final double notBlackPct;
    /** Distinct colours (4 bits per channel) among every 7th pixel of every 7th row, as Guest.frameVariety counts. */
    final int colours;
    /** ROWS strings of COLS characters from RAMP: dark to light. */
    final String[] picture;

    private ScreenSample(int width, int height, int stride, double notBlackPct, int colours, String[] picture) {
        this.width = width;
        this.height = height;
        this.stride = stride;
        this.notBlackPct = notBlackPct;
        this.colours = colours;
        this.picture = picture;
    }

    /** @return the sample of the binary PPM @ppm; throws with the reason when it is none. */
    static ScreenSample parse(byte[] ppm) throws IOException {
        int[] at = {0};
        if (ppm.length < 2 || ppm[0] != 'P' || ppm[1] != '6') {
            throw new IOException("not a P6 PPM");
        }
        at[0] = 2;
        int w = number(ppm, at), h = number(ppm, at), max = number(ppm, at);
        if (w < 1 || h < 1 || w > 16384 || h > 16384) {
            throw new IOException("odd size " + w + "x" + h);
        }
        if (max != 255) {
            throw new IOException("maxval " + max + " is not 255");
        }
        int data = at[0] + 1;           // one whitespace byte ends the header
        long stride = data > ppm.length ? 0 : (ppm.length - data) / h;
        if (stride < (long) w * 3) {
            throw new IOException("truncated: " + (ppm.length - data) + " bytes of pixels for " + w + "x" + h);
        }
        int[] cell = new int[COLS * ROWS], count = new int[COLS * ROWS];
        int[] col = new int[w];
        for (int x = 0; x < w; x++) {
            col[x] = (int) ((long) x * COLS / w);
        }
        long notBlack = 0;
        HashSet<Integer> seen = new HashSet<>();
        for (int y = 0; y < h; y++) {
            int row = data + (int) (y * stride), base = (int) ((long) y * ROWS / h) * COLS;
            for (int x = 0; x < w; x++) {
                int r = ppm[row + x * 3] & 255, g = ppm[row + x * 3 + 1] & 255, b = ppm[row + x * 3 + 2] & 255;
                cell[base + col[x]] += (299 * r + 587 * g + 114 * b) / 1000;
                count[base + col[x]]++;
                if (r >= BLACK || g >= BLACK || b >= BLACK) {
                    notBlack++;
                }
                if (y % 7 == 0 && x % 7 == 0) {
                    seen.add((r & 0xf0) << 8 | (g & 0xf0) << 4 | (b & 0xf0));
                }
            }
        }
        String[] pic = new String[ROWS];
        for (int ry = 0; ry < ROWS; ry++) {
            StringBuilder b = new StringBuilder(COLS);
            for (int cx = 0; cx < COLS; cx++) {
                int n = count[ry * COLS + cx];
                int lum = n == 0 ? 0 : cell[ry * COLS + cx] / n;
                b.append(RAMP.charAt(Math.min(RAMP.length() - 1, lum * RAMP.length() / 256)));
            }
            pic[ry] = b.toString();
        }
        return new ScreenSample(w, h, (int) stride, 100.0 * notBlack / ((long) w * h), seen.size(), pic);
    }

    /** The next decimal number of a PPM header after whitespace and #comments; -1 when there is none. */
    private static int number(byte[] b, int[] at) {
        int i = at[0];
        while (i < b.length && (b[i] == ' ' || b[i] == '\n' || b[i] == '\r' || b[i] == '\t' || b[i] == '#')) {
            if (b[i] == '#') {
                while (i < b.length && b[i] != '\n') {
                    i++;
                }
            } else {
                i++;
            }
        }
        long v = -1;
        while (i < b.length && b[i] >= '0' && b[i] <= '9') {
            v = (v < 0 ? 0 : v * 10) + (b[i] - '0');
            if (v > Integer.MAX_VALUE) {
                v = Integer.MAX_VALUE;
            }
            i++;
        }
        at[0] = i;
        return (int) v;
    }

    /** One line for the app log. */
    String oneLine() {
        return String.format(Locale.ROOT, "screen %dx%d, %.1f %% not black, %d colours in a 4-bit sample", width, height, notBlackPct, colours);
    }

    /** The record's section: the facts, then the picture between bars. */
    List<String> lines() {
        List<String> out = new ArrayList<>();
        out.add(oneLine());
        out.add(String.format(Locale.ROOT, "rows of %d bytes; the colours are counted on every 7th pixel of every 7th row (the Apple logo has a few,"
                + " a lock screen tens to hundreds: 49 on the iOS 16 lock screen of a Linux harness run); the picture, dark to light: \"%s\"", stride, RAMP));
        for (String r : picture) {
            out.add("|" + r + "|");
        }
        return out;
    }
}
