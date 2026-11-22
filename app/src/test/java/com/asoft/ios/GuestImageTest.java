package com.asoft.ios;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

public class GuestImageTest {
    @Test
    public void maxMemIsAdded() {
        assertEquals("a=1 b cpus=4 maxmem=2048", GuestImage.withMaxMem("a=1 b cpus=4", 2048));
    }

    @Test
    public void maxMemReplacesAnExistingOne() {
        assertEquals("a=1 b maxmem=3072", GuestImage.withMaxMem("a=1 maxmem=2048 b", 3072));
    }

    @Test
    public void maxMemZeroRemovesIt() {
        assertEquals("a=1 b", GuestImage.withMaxMem("a=1 maxmem=2048 b", 0));
        assertEquals("a=1 b", GuestImage.withMaxMem("a=1 b", 0));
    }
}
