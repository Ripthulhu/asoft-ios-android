package com.asoft.ios;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.LinkProperties;
import android.net.Network;
import android.net.NetworkCapabilities;

import java.util.ArrayList;
import java.util.List;

/**
 * What the phone's network looked like when a guest started, for the reports (which are posted in public): the
 * kind of network, whether Android's Private DNS is in the way, and what kind of address each DNS server has. An
 * address itself is never printed, only its class. The guest's network is QEMU's user networking (slirp), whose
 * DNS comes from the files/resolv.conf that Guest.writeResolvConf writes: the active network's servers, then
 * 8.8.8.8 and 1.1.1.1.
 *
 * The pure part (classify, describeDns, transport) has no Android in it; describe() is the thin Android part and
 * never throws.
 */
final class NetFacts {
    private NetFacts() {}

    static final String FALLBACKS = "the fallbacks 8.8.8.8 and 1.1.1.1 that Guest adds";

    // -- the pure part -------------------------------------------------------------------------------

    /** What kind of address @address is (Java's getHostAddress form, an IPv6 scope as "%wlan0" included). */
    static String classify(String address) {
        if (address == null) {
            return "other";
        }
        String a = address.trim().toLowerCase(java.util.Locale.ROOT);
        if (a.indexOf(':') >= 0) {
            return classify6(a);
        }
        int[] v = parse4(a);
        if (v == null) {
            return "other";
        }
        if (v[0] == 127) {
            return "IPv4 loopback";
        }
        if (v[0] == 169 && v[1] == 254) {
            return "IPv4 link-local";
        }
        if (v[0] == 10 || v[0] == 172 && v[1] >= 16 && v[1] <= 31 || v[0] == 192 && v[1] == 168) {
            return "IPv4 private (192.168/10/172.16-31)";
        }
        if (v[0] == 100 && v[1] >= 64 && v[1] <= 127) {
            return "IPv4 carrier-grade NAT (100.64/10)";
        }
        if (v[0] == 0) {
            return "other";
        }
        return "IPv4 public";
    }

    private static int[] parse4(String a) {
        String[] p = a.split("\\.", -1);
        if (p.length != 4) {
            return null;
        }
        int[] v = new int[4];
        for (int i = 0; i < 4; i++) {
            if (p[i].isEmpty() || p[i].length() > 3 || !p[i].chars().allMatch(c -> c >= '0' && c <= '9')) {
                return null;
            }
            v[i] = Integer.parseInt(p[i]);
            if (v[i] > 255) {
                return null;
            }
        }
        return v;
    }

    private static String classify6(String a) {
        int pct = a.indexOf('%');
        String zone = pct >= 0 ? a.substring(pct + 1) : null;
        int[] g = parse6(pct >= 0 ? a.substring(0, pct) : a);
        if (g == null) {
            return "other";
        }
        boolean zero7 = true;
        for (int i = 0; i < 7; i++) {
            zero7 &= g[i] == 0;
        }
        if (zero7 && g[7] == 1) {
            return "IPv6 loopback";
        }
        if (g[0] >= 0xfe80 && g[0] <= 0xfebf) {
            return zone != null && !zone.isEmpty() ? "IPv6 link-local (scoped)" : "IPv6 link-local (no scope)";
        }
        if (g[0] >= 0xfc00 && g[0] <= 0xfdff) {
            return "IPv6 unique-local";
        }
        if (g[0] >= 0x2000 && g[0] <= 0x3fff) {
            return "IPv6 global";
        }
        return "other";
    }

    /** The eight 16-bit groups of an IPv6 address (with "::" compression), null when it is not one. */
    private static int[] parse6(String a) {
        int dc = a.indexOf("::");
        if (dc >= 0 && a.indexOf("::", dc + 1) >= 0) {
            return null;
        }
        List<Integer> head = groups(dc >= 0 ? a.substring(0, dc) : a), tail = dc >= 0 ? groups(a.substring(dc + 2)) : new ArrayList<Integer>();
        if (head == null || tail == null) {
            return null;
        }
        int n = head.size() + tail.size();
        if (dc >= 0 ? n > 7 : n != 8) {
            return null;
        }
        int[] g = new int[8];
        for (int i = 0; i < head.size(); i++) {
            g[i] = head.get(i);
        }
        for (int i = 0; i < tail.size(); i++) {
            g[8 - tail.size() + i] = tail.get(i);
        }
        return g;
    }

    private static List<Integer> groups(String s) {
        List<Integer> out = new ArrayList<>();
        if (s.isEmpty()) {
            return out;
        }
        for (String p : s.split(":", -1)) {
            if (p.isEmpty() || p.length() > 4) {
                return null;
            }
            try {
                out.add(Integer.parseInt(p, 16));
            } catch (NumberFormatException e) {
                return null;
            }
        }
        return out;
    }

    /**
     * The DNS servers the network gave, by class and in the order of resolv.conf, then the two public fallbacks:
     * "1: IPv4 private (...); 2: IPv6 link-local (scoped); then the fallbacks ... that Guest adds; slirp uses: ...".
     * libslirp (not part of this repo: patch-slirp.py only moves the path it reads) takes the first IPv4
     * nameserver line of that file for the guest's 10.0.2.3, so a network with no IPv4 DNS server leaves it the
     * fallback 8.8.8.8.
     */
    static String describeDns(List<String> addresses) {
        StringBuilder b = new StringBuilder();
        int firstV4 = -1;
        for (int i = 0; i < addresses.size(); i++) {
            String k = classify(addresses.get(i));
            if (firstV4 < 0 && k.startsWith("IPv4")) {
                firstV4 = i;
            }
            b.append(i + 1).append(": ").append(k).append("; ");
        }
        b.append(addresses.isEmpty() ? "none from the network; " : "then ").append(FALLBACKS);
        b.append("; slirp uses: ").append(firstV4 >= 0 ? "entry " + (firstV4 + 1) + " (the first IPv4 nameserver line)"
                : "8.8.8.8 (the network gave no IPv4 DNS server)");
        return b.toString();
    }

    /** "Wi-Fi", "cellular + VPN", "none" (no active network), "other" (one with none of the four). */
    static String transport(boolean network, boolean wifi, boolean cellular, boolean ethernet, boolean vpn) {
        if (!network) {
            return "none";
        }
        List<String> t = new ArrayList<>();
        if (wifi) {
            t.add("Wi-Fi");
        }
        if (cellular) {
            t.add("cellular");
        }
        if (ethernet) {
            t.add("ethernet");
        }
        if (vpn) {
            t.add("VPN");
        }
        return t.isEmpty() ? "other" : String.join(" + ", t);
    }

    private static String yesNo(boolean b) {
        return b ? "yes" : "no";
    }

    // -- the Android part ----------------------------------------------------------------------------

    /**
     * "Wi-Fi; validated yes; metered no; private DNS active no, server name set no, setting off; DNS 1: ...". Every
     * fact is read on its own: one that cannot be says "not readable" and the others stay.
     */
    static String describe(Context c) {
        String transport = "not readable", validated = "not readable", metered = "not readable", active = "not readable",
                named = "not readable", mode = "not readable", dns = "not readable";
        try {
            ConnectivityManager cm = c.getSystemService(ConnectivityManager.class);
            Network n = cm.getActiveNetwork();
            NetworkCapabilities nc = n == null ? null : cm.getNetworkCapabilities(n);
            LinkProperties lp = n == null ? null : cm.getLinkProperties(n);
            try {
                transport = transport(n != null, nc != null && nc.hasTransport(NetworkCapabilities.TRANSPORT_WIFI),
                        nc != null && nc.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR),
                        nc != null && nc.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET),
                        nc != null && nc.hasTransport(NetworkCapabilities.TRANSPORT_VPN));
            } catch (RuntimeException ignored) {
                // stays "not readable"
            }
            if (nc != null) {
                try {
                    validated = yesNo(nc.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED));
                    metered = yesNo(!nc.hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_METERED));
                } catch (RuntimeException ignored) {
                    // stays "not readable"
                }
            } else if (n == null) {
                validated = metered = "no network";
            }
            if (lp != null) {
                try {
                    active = yesNo(lp.isPrivateDnsActive());
                    named = yesNo(lp.getPrivateDnsServerName() != null);
                } catch (RuntimeException ignored) {
                    // stays "not readable"
                }
                try {
                    List<String> a = new ArrayList<>();
                    for (java.net.InetAddress i : lp.getDnsServers()) {
                        a.add(i.getHostAddress());
                    }
                    dns = describeDns(a);
                } catch (RuntimeException ignored) {
                    // stays "not readable"
                }
            }
        } catch (RuntimeException ignored) {
            // the values stay "not readable"
        }
        try {
            String m = android.provider.Settings.Global.getString(c.getContentResolver(), "private_dns_mode");
            mode = m == null ? "not readable" : m;
        } catch (RuntimeException ignored) {
            // stays "not readable"
        }
        return transport + "; validated " + validated + "; metered " + metered + "; private DNS active " + active
                + ", server name set " + named + ", setting " + mode + "; DNS " + dns;
    }
}
