package com.asoft.ios;

import java.io.FileDescriptor;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.PrintStream;
import java.net.URL;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;
import javax.net.ssl.HttpsURLConnection;

/** Download the exact previously inspected release for whitelisted tool extraction.
 * No APK installation or execution. Normal Android TLS validation stays enabled.
 * The Python caller creates a fresh private output directory and owns the process.
 */
public final class FetchPinnedRelease {
    private static final String SOURCE = "https://github.com/alpersamur3/asoft-ios-android/releases/download/v0.1.6/ASoftware-iOS-Android-0.1.6.apk";
    private static final long BYTES = 109357759L;
    private static final String SHA256 = "befbcc1b31d83f166870010300a2a302e3570a7d3622d8de9c02fd896eeaa0cf";
    private static final Set<String> HOSTS = new HashSet<>(Arrays.asList(
            "github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"));

    private FetchPinnedRelease() {}

    private static String hex(byte[] bytes) {
        StringBuilder result = new StringBuilder();
        for (byte value : bytes) result.append(String.format(Locale.ROOT, "%02x", value & 255));
        return result.toString();
    }

    public static void main(String[] args) throws Exception {
        System.setOut(new PrintStream(new FileOutputStream(FileDescriptor.out), true, "UTF-8"));
        System.setErr(new PrintStream(new FileOutputStream(FileDescriptor.err), true, "UTF-8"));
        if (args.length != 1) throw new IllegalArgumentException("one fresh private output directory required");
        Path requested = Paths.get(args[0]);
        if (!requested.isAbsolute() || !Files.isDirectory(requested, LinkOption.NOFOLLOW_LINKS)) {
            throw new IllegalArgumentException("output directory must already exist without a final symlink");
        }
        Path root = requested.toRealPath();
        Path part = root.resolve("source.apk.part"), result = root.resolve("source.apk");
        if (Files.exists(part, LinkOption.NOFOLLOW_LINKS) || Files.exists(result, LinkOption.NOFOLLOW_LINKS)) {
            throw new IllegalArgumentException("download output already exists");
        }
        long deadline = System.nanoTime() + 600_000_000_000L;
        HttpsURLConnection connection = null;
        URL address = new URL(SOURCE);
        try {
            for (int hop = 0; ; hop++) {
                if (hop > 6 || !address.getProtocol().equals("https") || address.getUserInfo() != null
                        || !HOSTS.contains(address.getHost()) || System.nanoTime() > deadline) {
                    throw new IllegalStateException("redirect is outside the pinned HTTPS source hosts or deadline");
                }
                connection = (HttpsURLConnection) address.openConnection();
                connection.setInstanceFollowRedirects(false);
                connection.setConnectTimeout(20_000);
                connection.setReadTimeout(30_000);
                connection.setRequestProperty("Accept-Encoding", "identity");
                int status = connection.getResponseCode();
                if (status == 200) break;
                if (status != 301 && status != 302 && status != 303 && status != 307 && status != 308) {
                    throw new IllegalStateException("source HTTP status " + status);
                }
                String location = connection.getHeaderField("Location");
                if (location == null) throw new IllegalStateException("redirect has no destination");
                URL next = new URL(address, location);
                connection.disconnect();
                connection = null;
                address = next;
            }
            long declared = connection.getContentLengthLong();
            if (declared >= 0 && declared != BYTES) throw new IllegalStateException("release length changed");
            Files.createFile(part);
            MessageDigest hash = MessageDigest.getInstance("SHA-256");
            long total = 0, reported = 0;
            try (InputStream input = connection.getInputStream();
                    FileOutputStream output = new FileOutputStream(part.toFile())) {
                byte[] buffer = new byte[65536];
                int count;
                while ((count = input.read(buffer)) != -1) {
                    total += count;
                    if (total > BYTES || System.nanoTime() > deadline) {
                        throw new IllegalStateException("release byte or time bound exceeded");
                    }
                    output.write(buffer, 0, count);
                    hash.update(buffer, 0, count);
                    if (total - reported >= (8L << 20)) {
                        System.out.println("APK_SOURCE_PROGRESS bytes=" + total);
                        reported = total;
                    }
                }
                output.getFD().sync();
            }
            String actual = hex(hash.digest());
            if (total != BYTES || !actual.equals(SHA256)) throw new IllegalStateException("release SHA256 or length changed");
            Files.move(part, result, StandardCopyOption.ATOMIC_MOVE);
            System.out.println("APK_SOURCE_VERIFIED bytes=" + total + " sha256=" + actual);
            System.out.println("No APK installed or executed.");
        } finally {
            if (connection != null) connection.disconnect();
        }
    }
}
