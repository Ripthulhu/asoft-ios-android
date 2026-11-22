package com.asoft.ios;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import java.util.Arrays;
import java.util.Collections;

import org.junit.Test;

/** NetFacts' pure part: addresses are classified, never printed. */
public class NetFactsTest {
    private static final String PRIVATE4 = "IPv4 private (192.168/10/172.16-31)";

    @Test
    public void ipv4Classes() {
        assertEquals(PRIVATE4, NetFacts.classify("192.168.1.1"));
        assertEquals(PRIVATE4, NetFacts.classify("10.0.0.1"));
        assertEquals(PRIVATE4, NetFacts.classify("172.16.0.1"));
        assertEquals(PRIVATE4, NetFacts.classify("172.31.255.254"));
        assertEquals("IPv4 public", NetFacts.classify("172.32.0.1"));
        assertEquals("IPv4 public", NetFacts.classify("172.15.0.1"));
        assertEquals("IPv4 public", NetFacts.classify("8.8.8.8"));
        assertEquals("IPv4 public", NetFacts.classify("192.169.0.1"));
        assertEquals("IPv4 loopback", NetFacts.classify("127.0.0.1"));
        assertEquals("IPv4 link-local", NetFacts.classify("169.254.10.20"));
        assertEquals("IPv4 carrier-grade NAT (100.64/10)", NetFacts.classify("100.64.0.1"));
        assertEquals("IPv4 carrier-grade NAT (100.64/10)", NetFacts.classify("100.127.255.255"));
        assertEquals("IPv4 public", NetFacts.classify("100.128.0.1"));
    }

    @Test
    public void ipv6Classes() {
        assertEquals("IPv6 link-local (scoped)", NetFacts.classify("fe80::1%wlan0"));
        assertEquals("IPv6 link-local (scoped)", NetFacts.classify("fe80:0:0:0:abcd:1:2:3%rmnet_data1"));
        assertEquals("IPv6 link-local (scoped)", NetFacts.classify("FE80::1%2"));
        assertEquals("IPv6 link-local (no scope)", NetFacts.classify("fe80::1"));
        assertEquals("IPv6 unique-local", NetFacts.classify("fd12:3456:789a::1"));
        assertEquals("IPv6 unique-local", NetFacts.classify("fc00:0:0:0:0:0:0:53"));
        assertEquals("IPv6 global", NetFacts.classify("2001:4860:4860::8888"));
        assertEquals("IPv6 global", NetFacts.classify("2a00:1450:4001:81b:0:0:0:200e"));
        assertEquals("IPv6 loopback", NetFacts.classify("::1"));
        assertEquals("IPv6 loopback", NetFacts.classify("0:0:0:0:0:0:0:1"));
    }

    @Test
    public void whatIsNoAddressIsOther() {
        for (String s : new String[] {null, "", "garbage", "256.1.1.1", "1.2.3", "1.2.3.4.5", "0.0.0.0", "::", "ff02::1", "1::2::3", "fe80::g", "1:2:3:4:5:6:7:8:9", "12345::1"}) {
            assertEquals("for " + s, "other", NetFacts.classify(s));
        }
    }

    @Test
    public void theDnsListNamesClassesAndTheFallbacksAndWhichOneSlirpTakes() {
        assertEquals("1: " + PRIVATE4 + "; 2: IPv6 link-local (scoped); then the fallbacks 8.8.8.8 and 1.1.1.1 that Guest adds; "
                + "slirp uses: entry 1 (the first IPv4 nameserver line)", NetFacts.describeDns(Arrays.asList("192.168.43.1", "fe80::1%wlan0")));
        assertTrue(NetFacts.describeDns(Arrays.asList("fe80::1%wlan0", "10.20.30.40")).endsWith("slirp uses: entry 2 (the first IPv4 nameserver line)"));
        assertEquals("1: IPv6 global; then the fallbacks 8.8.8.8 and 1.1.1.1 that Guest adds; slirp uses: 8.8.8.8 (the network gave no IPv4 DNS server)",
                NetFacts.describeDns(Collections.singletonList("2001:db8::53")));
        assertEquals("none from the network; the fallbacks 8.8.8.8 and 1.1.1.1 that Guest adds; slirp uses: 8.8.8.8 (the network gave no IPv4 DNS server)",
                NetFacts.describeDns(Collections.<String>emptyList()));
    }

    @Test
    public void noAddressEverReachesTheText() {
        String d = NetFacts.describeDns(Arrays.asList("192.168.43.1", "fe80::1c2d:3e4f%wlan0", "100.88.12.7", "2001:db8:abcd::53"));
        for (String secret : new String[] {"43.1", "1c2d", "wlan0", "100.88", "12.7", "abcd", "db8"}) {
            assertFalse(secret, d.contains(secret));
        }
    }

    @Test
    public void transports() {
        assertEquals("none", NetFacts.transport(false, true, true, true, true));
        assertEquals("Wi-Fi", NetFacts.transport(true, true, false, false, false));
        assertEquals("cellular", NetFacts.transport(true, false, true, false, false));
        assertEquals("ethernet", NetFacts.transport(true, false, false, true, false));
        assertEquals("Wi-Fi + VPN", NetFacts.transport(true, true, false, false, true));
        assertEquals("other", NetFacts.transport(true, false, false, false, false));
    }
}
