package com.asoft.ios;

import java.io.IOException;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * The exact version-one stdout record of QEMU26's installed-runtime probe. The grammar is
 * deliberately the small fixed record the executable emits, so duplicate keys, missing fields,
 * a second result and an old challenge cannot be accepted as a successful run. Driver log text
 * belongs in stderr; an unrecognized stdout line is also a failed protocol.
 *
 * This parses evidence only. The caller still verifies the executable/runtime qualification,
 * chooses the system loader, enforces a deadline, waits for exit zero, and matches the actual
 * driver identity. It does not grant the app a GPU pass by itself.
 */
final class GpuProbeReport {
    private static final String PREFIX = "ASOFT_GPU_PROBE ";
    private static final String UINT = "([0-9]{1,20})";
    private static final String HEX32 = "([0-9a-f]{32})";
    private static final Pattern RECORD = Pattern.compile("\\A" + PREFIX + "\\{"
            + "\"schema\":" + UINT + ",\"nonce\":\"([0-9a-f]{64})\","
            + "\"backend\":\"system_cpu_shadow\",\"status\":\"pass\","
            + "\"checks_passed\":" + UINT + ","
            + "\"vendor_id\":" + UINT + ",\"device_id\":" + UINT + ","
            + "\"api_version\":" + UINT + ",\"driver_version\":" + UINT + ","
            + "\"device_type\":" + UINT + ","
            + "\"device_uuid\":\"" + HEX32 + "\",\"driver_uuid\":\"" + HEX32 + "\","
            + "\"chunks_created\":" + UINT + ",\"views_created\":" + UINT + ","
            + "\"epochs_prepared\":" + UINT + ",\"epochs_finished\":" + UINT + ","
            + "\"bytes_uploaded\":" + UINT + ",\"bytes_scattered\":" + UINT + ","
            + "\"bytes_compared\":" + UINT + "\\}\\z");

    final long vendor, device, api, driver, deviceType;
    final String deviceUuid, driverUuid;
    final long chunks, views, prepared, finished, uploaded, scattered, compared;

    private GpuProbeReport(Matcher m) throws IOException {
        vendor = uint32(m.group(4));
        device = uint32(m.group(5));
        api = uint32(m.group(6));
        driver = uint32(m.group(7));
        deviceType = uint32(m.group(8));
        deviceUuid = m.group(9);
        driverUuid = m.group(10);
        chunks = positive(m.group(11));
        views = positive(m.group(12));
        prepared = positive(m.group(13));
        finished = positive(m.group(14));
        uploaded = positive(m.group(15));
        scattered = positive(m.group(16));
        compared = positive(m.group(17));
        if (prepared != finished || finished < 2 || views < 2 || uploaded < 98_304 || compared < 49_152) {
            throw new IOException("GPU probe did not finish its required memory operations");
        }
        if ((api >>> 22 & 0x7f) < 1 || (api >>> 22 & 0x7f) == 1 && (api >>> 12 & 0x3ff) < 2) {
            throw new IOException("GPU probe selected a device below Vulkan 1.2");
        }
        if (deviceUuid.equals("00000000000000000000000000000000")
                || driverUuid.equals("00000000000000000000000000000000")) {
            throw new IOException("GPU probe did not identify its device and driver");
        }
    }

    /** Accept only one complete, current successful process result; never a partial log. */
    static GpuProbeReport parse(List<String> stdout, String nonce, int exitCode) throws IOException {
        if (exitCode != 0) {
            throw new IOException("GPU probe exited with status " + exitCode);
        }
        if (nonce == null || !nonce.matches("[0-9a-f]{64}") || stdout.size() != 1
                || stdout.get(0).length() > 4096) {
            throw new IOException("GPU probe did not return one bounded result for this run");
        }
        Matcher m = RECORD.matcher(stdout.get(0));
        if (!m.matches() || !"1".equals(m.group(1)) || !nonce.equals(m.group(2))
                || !"127".equals(m.group(3))) {
            throw new IOException("GPU probe returned an incomplete or incompatible result");
        }
        return new GpuProbeReport(m);
    }

    /** Vulkan calls CPU renderers type 4; a phone route requires actual GPU hardware. */
    boolean hardwareGpu() {
        return deviceType == 1 || deviceType == 2; // integrated or discrete
    }

    /** Every driver component that a packaged qualification must bind to. */
    String driverKey() {
        return vendor + "/" + device + "/" + api + "/" + driver + "/" + deviceType
                + "/" + deviceUuid + "/" + driverUuid;
    }

    private static long uint32(String value) throws IOException {
        long n = number(value);
        if (n > 0xffff_ffffL) {
            throw new IOException("GPU probe identity exceeds its 32-bit field");
        }
        return n;
    }

    private static long positive(String value) throws IOException {
        long n = number(value);
        if (n == 0) {
            throw new IOException("GPU probe contains an empty work counter");
        }
        return n;
    }

    private static long number(String value) throws IOException {
        try {
            return Long.parseLong(value);
        } catch (NumberFormatException e) {
            throw new IOException("GPU probe contains an oversized integer", e);
        }
    }
}
