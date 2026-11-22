package com.asoft.ios;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.zip.CRC32;
import org.json.JSONArray;
import org.json.JSONObject;

/** Narrow app_process entry point; no Context, APK installation, or support-gate changes.
 *
 * The packager compiles the committed Unpack, IpswFetch, CdnEdges and Io sources
 * unchanged alongside this adapter. The Python owner supplies one bounded JSON
 * request inside its exclusive attempt directory. Download/unpack algorithms
 * remain the established ones. Encrypted inputs are never punched or deleted.
 */
public final class PrepareInputs {
    private PrepareInputs() {}

    private static File output(JSONObject request, String key) throws Exception {
        File root = new File(request.getString("output_root")).getCanonicalFile();
        if (!root.isDirectory()) throw new IOException("output_root must already exist");
        File out = new File(request.getString(key)).getCanonicalFile();
        if (!out.toPath().startsWith(root.toPath()) || out.equals(root)) {
            throw new IOException("output escapes the owned attempt");
        }
        if (!out.getParentFile().isDirectory() && !out.getParentFile().mkdirs()) {
            throw new IOException("cannot create output parent");
        }
        return out;
    }

    private static File input(JSONObject request) throws Exception {
        File file = new File(request.getString("input")).getCanonicalFile();
        if (!file.isFile()) throw new IOException("input is not a regular file");
        String expected = request.getString("input_sha256");
        if (!expected.matches("[0-9a-f]{64}") || !expected.equals(Unpack.sha256(file))) {
            throw new IOException("input SHA256 differs from the stage plan");
        }
        return file;
    }

    private static JSONObject record(File file) throws Exception {
        JSONObject out = new JSONObject();
        out.put("path", file.getCanonicalPath());
        out.put("bytes", file.length());
        out.put("sha256", Unpack.sha256(file));
        return out;
    }

    private static String source(JSONObject request) throws Exception {
        String source = request.getString("source");
        if (!source.startsWith("https://") && !new File(source).isAbsolute()) {
            throw new IOException("source must be HTTPS or an explicit local archive");
        }
        return source;
    }

    private static void checkEntry(JSONObject wanted, IpswFetch.Entry actual) throws Exception {
        if (actual == null) throw new IOException("member missing from archive: " + wanted.getString("name"));
        if (wanted.has("bytes") && wanted.getLong("bytes") != actual.usize
                || wanted.has("zipBytes") && wanted.getLong("zipBytes") != actual.csize
                || wanted.has("method") && wanted.getInt("method") != actual.method
                || wanted.has("crc32") && Long.parseUnsignedLong(wanted.getString("crc32"), 16) != actual.crc) {
            throw new IOException("archive directory differs from pinned member: " + actual.name);
        }
    }

    private static JSONObject members(JSONObject request) throws Exception {
        IpswFetch fetch = new IpswFetch(source(request), new IpswFetch.Listener() {
            @Override public void progress(IpswFetch.Item item) {}
            @Override public void log(String line) { System.err.println(line); }
        }, 4, IpswFetch.CHUNK);
        Runtime.getRuntime().addShutdownHook(new Thread(fetch::stop));
        IpswFetch.Index index = fetch.index();
        if (request.has("source_bytes") && request.getLong("source_bytes") != index.size) {
            throw new IOException("archive size differs from pinned source");
        }
        JSONArray wanted = request.getJSONArray("members");
        if (wanted.length() == 0 || wanted.length() > 64) throw new IOException("invalid member count");
        List<IpswFetch.Item> items = new ArrayList<>();
        Set<String> names = new HashSet<>(), outputs = new HashSet<>();
        for (int i = 0; i < wanted.length(); i++) {
            JSONObject item = wanted.getJSONObject(i);
            String name = item.getString("name");
            checkEntry(item, index.entries.get(name));
            JSONObject location = new JSONObject();
            location.put("output_root", request.getString("output_root"));
            location.put("output", item.getString("output"));
            File out = output(location, "output");
            if (!names.add(name) || !outputs.add(out.getCanonicalPath())) {
                throw new IOException("duplicate member or output");
            }
            items.add(new IpswFetch.Item(name, out, IpswFetch.Kind.FILE, item.optLong("bytes", 0)));
        }
        fetch.prepare(index, items);
        fetch.run(items);
        JSONArray records = new JSONArray();
        // Recheck CRC even when IpswFetch reused its .ok marker. A marker is not
        // enough for a standalone stage's completion record after interruption.
        byte[] buffer = new byte[1 << 20];
        for (IpswFetch.Item item : items) {
            CRC32 crc = new CRC32();
            try (java.io.InputStream stream = Files.newInputStream(item.out.toPath())) {
                int count;
                while ((count = stream.read(buffer)) > 0) crc.update(buffer, 0, count);
            }
            if (item.out.length() != item.entry.usize || crc.getValue() != item.entry.crc) {
                throw new IOException("downloaded member length or CRC mismatch: " + item.member);
            }
            JSONObject row = record(item.out);
            row.put("member", item.member);
            row.put("crc32", String.format(java.util.Locale.ROOT, "%08x", crc.getValue()));
            row.put("method", item.entry.method);
            row.put("zip_bytes", item.entry.csize);
            records.put(row);
        }
        return new JSONObject().put("archive_bytes", index.size).put("files", records);
    }

    private static JSONObject run(JSONObject request) throws Exception {
        if (request.getInt("schema") != 1) throw new IOException("unknown request schema");
        String op = request.getString("op");
        if (op.equals("tls-probe")) {
            JSONArray urls = request.getJSONArray("urls"), reports = new JSONArray();
            if (urls.length() == 0 || urls.length() > 8) throw new IOException("invalid probe count");
            for (int i = 0; i < urls.length(); i++) {
                String address = urls.getString(i);
                if (!address.startsWith("https://")) throw new IOException("TLS probe requires HTTPS");
                JSONObject report = new JSONObject().put("url", address);
                java.net.HttpURLConnection connection = null;
                try {
                    connection = (java.net.HttpURLConnection) new java.net.URL(address).openConnection();
                    connection.setConnectTimeout(20_000);
                    connection.setReadTimeout(20_000);
                    connection.setInstanceFollowRedirects(false);
                    connection.setRequestMethod("HEAD");
                    report.put("status", connection.getResponseCode());
                    report.put("location", connection.getHeaderField("Location"));
                    report.put("content_length", connection.getHeaderField("Content-Length"));
                } catch (IOException failure) {
                    report.put("error", failure.toString());
                } finally {
                    if (connection != null) connection.disconnect();
                }
                reports.put(report);
            }
            return new JSONObject().put("tls_probe", reports).put("verification_disabled", false);
        }
        if (op.equals("members")) return members(request);
        File out = output(request, "output");
        if (op.equals("url")) {
            String expected = request.getString("sha256").toLowerCase(java.util.Locale.ROOT);
            if (!expected.matches("[0-9a-f]{64}")) throw new IOException("missing pinned URL hash");
            if (!out.isFile() || !expected.equals(Unpack.sha256(out))) {
                File part = new File(out + ".part");
                Files.write(part.toPath(), Unpack.get(source(request), 64 << 20));
                if (!expected.equals(Unpack.sha256(part))) throw new IOException("URL SHA256 mismatch");
                Files.move(part.toPath(), out.toPath(), java.nio.file.StandardCopyOption.REPLACE_EXISTING);
            }
        } else if (op.equals("im4p")) {
            File from = input(request);
            if (from.equals(out)) throw new IOException("input and output must differ");
            Unpack.im4p(from, out);
        } else if (op.equals("aea")) {
            File from = input(request);
            if (from.equals(out)) throw new IOException("input and output must differ");
            // The original decoder's cluster marker does not authenticate an
            // existing plaintext prefix. Preserve failed output for review and
            // restart into a fresh attempt; never bless it by hashing afterward.
            if (out.exists() || new File(out + ".progress").exists()) {
                throw new IOException("AEA output must be fresh; preserve the failed attempt");
            }
            File cache = output(request, "key_cache");
            if (!cache.isDirectory() && !cache.mkdirs()) throw new IOException("cannot create key cache");
            JSONObject keys = request.getJSONObject("keys");
            Unpack.KeySource keySource = Unpack.keySource(cache, keys.getString("url"),
                    keys.getString("sha256"), System.err::println);
            byte[] key = Unpack.key(Unpack.head(from), keySource);
            long[] last = {0};
            Unpack.decryptAea(from, out, key, false, bytes -> {
                long now = System.nanoTime();
                if (now - last[0] >= 10_000_000_000L) {
                    System.err.println("AEA authenticated plaintext bytes " + bytes);
                    last[0] = now;
                }
            }, () -> false);
            if (!Unpack.aeaComplete(out)) throw new IOException("AEA did not produce a complete checkpoint");
        } else {
            throw new IOException("unknown operation");
        }
        return new JSONObject().put("file", record(out));
    }

    private static void writeResult(JSONObject request, JSONObject result) throws Exception {
        if (!request.has("result_file")) return;
        File out = output(request, "result_file");
        File part = new File(out + ".part");
        if (out.exists() || part.exists()) throw new IOException("result path must be fresh");
        try (java.io.FileOutputStream stream = new java.io.FileOutputStream(part)) {
            stream.write((result.toString() + "\n").getBytes(StandardCharsets.UTF_8));
            stream.getFD().sync();
        }
        Files.move(part.toPath(), out.toPath(), java.nio.file.StandardCopyOption.ATOMIC_MOVE);
    }

    public static void main(String[] args) {
        JSONObject request = null;
        try {
            // RuntimeInit redirects System.out/err to logcat under app_process.
            // Keep this command's result/progress in its owner's private pipes.
            System.setOut(new java.io.PrintStream(new java.io.FileOutputStream(java.io.FileDescriptor.out), true, "UTF-8"));
            System.setErr(new java.io.PrintStream(new java.io.FileOutputStream(java.io.FileDescriptor.err), true, "UTF-8"));
            if (args.length != 1) throw new IOException("one request JSON path required");
            File file = new File(args[0]);
            if (!file.isFile() || file.length() > (1 << 20)) throw new IOException("invalid request file");
            request = new JSONObject(new String(Files.readAllBytes(file.toPath()), StandardCharsets.UTF_8));
            if (request.has("result_file")) {
                File resultPath = output(request, "result_file");
                if (resultPath.exists() || new File(resultPath + ".part").exists()) {
                    throw new IOException("result path must be fresh before starting work");
                }
            }
            JSONObject result = run(request);
            result.put("schema", 1).put("status", "COMPLETE");
            writeResult(request, result);
            System.out.println(result.toString());
        } catch (Throwable failure) {
            System.err.println("PrepareInputs: " + failure);
            if (request != null) {
                try {
                    writeResult(request, new JSONObject().put("schema", 1).put("status", "INCOMPLETE").put("error", failure.toString()));
                } catch (Exception reporting) {
                    System.err.println("PrepareInputs result: " + reporting);
                }
            }
            System.exit(2);
        }
    }
}
