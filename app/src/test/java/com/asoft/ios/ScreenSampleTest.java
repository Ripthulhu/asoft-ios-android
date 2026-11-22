package com.asoft.ios;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.List;

import org.junit.Test;

/** The screen sample against small synthetic PPMs, written the way QEMU writes them (rows padded to 4 bytes). */
public class ScreenSampleTest {
    private interface Pixel {
        int[] at(int x, int y);
    }

    /** A binary PPM of @w x @h with rows padded to 4 bytes with @pad. */
    private static byte[] ppm(String header, int w, int h, int pad, Pixel p) {
        ByteArrayOutputStream o = new ByteArrayOutputStream();
        byte[] hd = header.getBytes(StandardCharsets.US_ASCII);
        o.write(hd, 0, hd.length);
        int stride = (w * 3 + 3) / 4 * 4;
        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                int[] c = p.at(x, y);
                o.write(c[0]);
                o.write(c[1]);
                o.write(c[2]);
            }
            for (int i = w * 3; i < stride; i++) {
                o.write(pad);
            }
        }
        return o.toByteArray();
    }

    private static final Pixel LEFT_HALF_WHITE = (x, y) -> x < 25 ? new int[] {255, 255, 255} : new int[] {0, 0, 0};

    @Test
    public void paddedRowsAreNotSheared() throws IOException {
        // 50 px = 150 bytes a row, padded to 152: reading 150-byte rows would slide every row 2 bytes along
        ScreenSample s = ScreenSample.parse(ppm("P6\n50 100\n255\n", 50, 100, 0xaa, LEFT_HALF_WHITE));
        assertEquals(50, s.width);
        assertEquals(100, s.height);
        assertEquals(152, s.stride);
        String row = "@@@@@@@@@@@@            ";
        assertEquals(ScreenSample.ROWS, s.picture.length);
        for (String r : s.picture) {
            assertEquals(row, r);
        }
        assertEquals(50.0, s.notBlackPct, 0.001);
        assertEquals(2, s.colours);
    }

    @Test
    public void aBlackScreenIsBlackWithOneColour() throws IOException {
        ScreenSample s = ScreenSample.parse(ppm("P6\n48 96\n255\n", 48, 96, 0, (x, y) -> new int[] {0, 0, 0}));
        assertEquals(0.0, s.notBlackPct, 0.0);
        assertEquals(1, s.colours);
        for (String r : s.picture) {
            assertEquals(" ".repeat(ScreenSample.COLS), r);
        }
    }

    @Test
    public void aLogoOnBlackHasFewColoursAndAGradientHasMany() throws IOException {
        Pixel logo = (x, y) -> Math.abs(x - 24) < 6 && Math.abs(y - 48) < 6 ? new int[] {255, 255, 255} : new int[] {0, 0, 0};
        ScreenSample l = ScreenSample.parse(ppm("P6\n48 96\n255\n", 48, 96, 0, logo));
        assertTrue(l.colours <= 2);
        assertTrue(l.notBlackPct > 0 && l.notBlackPct < 5);
        Pixel wallpaper = (x, y) -> new int[] {x * 5 % 256, y * 2 % 256, (x * y) % 256};
        ScreenSample w = ScreenSample.parse(ppm("P6\n350 200\n255\n", 350, 200, 0, wallpaper));
        assertTrue("colours " + w.colours, w.colours > 100);
        assertTrue(w.notBlackPct > 95);
    }

    @Test
    public void brightnessChoosesTheCharacter() throws IOException {
        // a column of cells from black to white, 8 px wide each: the ramp's first and last characters at the ends
        ScreenSample s = ScreenSample.parse(ppm("P6\n24 48\n255\n", 24, 48, 0, (x, y) -> {
            int v = y * 255 / 47;
            return new int[] {v, v, v};
        }));
        assertEquals(" ", s.picture[0].substring(0, 1));
        assertEquals("@", s.picture[47].substring(0, 1));
        char prev = ' ';
        for (String r : s.picture) {
            assertTrue(ScreenSample.RAMP.indexOf(r.charAt(0)) >= ScreenSample.RAMP.indexOf(prev));
            prev = r.charAt(0);
        }
    }

    @Test
    public void theHeaderMayHaveCommentsAndOddWhitespace() throws IOException {
        ScreenSample s = ScreenSample.parse(ppm("P6\n# made by QEMU\n 48\t96 \r\n255\n", 48, 96, 0, (x, y) -> new int[] {255, 255, 255}));
        assertEquals(48, s.width);
        assertEquals(100.0, s.notBlackPct, 0.001);
    }

    @Test
    public void badFilesSayWhy() {
        String[] cases = {"P5\n4 4\n255\n", "P6\n4 4\n255\n" + "xxxx", "P6\n0 4\n255\n", "P6\n4 4\n65535\n", "", "P6\n99999 4\n255\n"};
        for (String c : cases) {
            try {
                ScreenSample.parse(c.getBytes(StandardCharsets.US_ASCII));
                fail("accepted: " + c);
            } catch (IOException e) {
                assertFalse(e.getMessage().isEmpty());
            }
        }
    }

    @Test
    public void theRecordSectionHasTheFactsAndTheBarredPicture() throws IOException {
        ScreenSample s = ScreenSample.parse(ppm("P6\n50 100\n255\n", 50, 100, 0, LEFT_HALF_WHITE));
        assertEquals("screen 50x100, 50.0 % not black, 2 colours in a 4-bit sample", s.oneLine());
        List<String> l = s.lines();
        assertEquals(2 + ScreenSample.ROWS, l.size());
        assertEquals(s.oneLine(), l.get(0));
        assertTrue(l.get(1), l.get(1).startsWith("rows of 152 bytes;"));
        assertEquals("|@@@@@@@@@@@@            |", l.get(2));
    }
}
