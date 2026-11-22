package com.asoft.ios;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import java.io.IOException;
import java.util.Arrays;
import java.util.Collections;

import org.junit.Test;

/** The deployed-runtime handshake must fail closed independently of driver log prose. */
public class GpuProbeReportTest {
    private static final String NONCE = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
    private static final String RESULT = "ASOFT_GPU_PROBE {\"schema\":1,\"nonce\":\"" + NONCE + "\","
            + "\"backend\":\"system_cpu_shadow\",\"status\":\"pass\",\"checks_passed\":127,"
            + "\"vendor_id\":4112,\"device_id\":1896223250,\"api_version\":4211032,"
            + "\"driver_version\":6967606,\"device_type\":1,"
            + "\"device_uuid\":\"00112233445566778899aabbccddeeff\","
            + "\"driver_uuid\":\"112233445566778899aabbccddeeff00\","
            + "\"chunks_created\":1,\"views_created\":2,\"epochs_prepared\":2,\"epochs_finished\":2,"
            + "\"bytes_uploaded\":98304,\"bytes_scattered\":17,\"bytes_compared\":196624}";

    private static GpuProbeReport parse(String result) throws IOException {
        return GpuProbeReport.parse(Collections.singletonList(result), NONCE, 0);
    }

    private static void refuses(String result) {
        try {
            parse(result);
            fail("accepted an invalid probe result");
        } catch (IOException expected) {
            assertFalse(expected.getMessage().isEmpty());
        }
    }

    @Test
    public void completeCurrentRunCarriesIdentityAndActualWork() throws Exception {
        GpuProbeReport report = parse(RESULT);
        assertTrue(report.hardwareGpu());
        assertEquals(2, report.finished);
        assertEquals(98304, report.uploaded);
        assertEquals(17, report.scattered);
        assertTrue(report.driverKey().contains("00112233445566778899aabbccddeeff"));
    }

    @Test
    public void staleOrPartialRecordsFail() {
        refuses(RESULT.replace(NONCE, NONCE.replace('0', '1')));
        refuses(RESULT.substring(0, RESULT.length() - 1));
        refuses(RESULT.replace("\"schema\":1", "\"schema\":2"));
        refuses(RESULT.replace("\"checks_passed\":127", "\"checks_passed\":63"));
        refuses(RESULT.replace("\"status\":\"pass\"", "\"status\":\"fail\""));
        refuses(RESULT.replace("system_cpu_shadow", "system"));
    }

    @Test
    public void missingAndDuplicateFieldsFail() {
        refuses(RESULT.replace("\"driver_version\":6967606,", ""));
        refuses(RESULT.replace("\"schema\":1", "\"schema\":0,\"schema\":1"));
        refuses(RESULT + " ignored");
    }

    @Test
    public void exitFailureAndDuplicateResultsFail() throws Exception {
        try {
            GpuProbeReport.parse(Collections.singletonList(RESULT), NONCE, 1);
            fail("accepted failed child");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("status 1"));
        }
        try {
            GpuProbeReport.parse(Arrays.asList(RESULT, RESULT), NONCE, 0);
            fail("accepted two results");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("one bounded result"));
        }
    }

    @Test
    public void unfinishedOrMissingGpuWorkFails() {
        refuses(RESULT.replace("\"epochs_finished\":2", "\"epochs_finished\":1"));
        refuses(RESULT.replace("\"bytes_scattered\":17", "\"bytes_scattered\":0"));
        refuses(RESULT.replace("\"bytes_uploaded\":98304", "\"bytes_uploaded\":1"));
        refuses(RESULT.replace("\"views_created\":2", "\"views_created\":1"));
    }

    @Test
    public void identityAndIntegerBoundsAreStrict() {
        refuses(RESULT.replace("00112233445566778899aabbccddeeff", "00000000000000000000000000000000"));
        refuses(RESULT.replace("\"driver_version\":6967606", "\"driver_version\":4294967296"));
        refuses(RESULT.replace("\"bytes_scattered\":17", "\"bytes_scattered\":18446744073709551615"));
        refuses(RESULT.replace("\"bytes_scattered\":17", "\"bytes_scattered\":-1"));
        refuses(RESULT.replace("\"api_version\":4211032", "\"api_version\":4198400"));
    }

    @Test
    public void aSoftwarePassRemainsIdentifiedAsSoftware() throws Exception {
        GpuProbeReport report = parse(RESULT.replace("\"device_type\":1", "\"device_type\":4"));
        assertFalse(report.hardwareGpu());
    }
}
