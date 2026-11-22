package com.asoft.ios;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Arrays;
import java.util.concurrent.atomic.AtomicBoolean;
import javax.crypto.Cipher;
import javax.crypto.Mac;
import javax.crypto.spec.IvParameterSpec;
import javax.crypto.spec.SecretKeySpec;

/** Synthetic AEA fixture: real native hole punching, no Apple downloads or Android device. */
public final class UnpackResumeTest {
    private static final int SEGMENT = 1 << 20;

    private static byte[] cat(byte[]... chunks) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        for (byte[] chunk : chunks) out.write(chunk);
        return out.toByteArray();
    }

    private static byte[] le(int n) {
        return ByteBuffer.allocate(4).order(ByteOrder.LITTLE_ENDIAN).putInt(n).array();
    }

    private static byte[][] material(byte[] key, String label, byte[] extra) throws Exception {
        byte[] b = Unpack.hkdf(key, new byte[0], cat(label.getBytes(StandardCharsets.US_ASCII), extra), 80);
        return new byte[][] {Arrays.copyOfRange(b, 0, 32), Arrays.copyOfRange(b, 32, 64), Arrays.copyOfRange(b, 64, 80)};
    }

    private static byte[] crypt(byte[][] key, byte[] plain) throws Exception {
        Cipher c = Cipher.getInstance("AES/CTR/NoPadding");
        c.init(Cipher.ENCRYPT_MODE, new SecretKeySpec(key[1], "AES"), new IvParameterSpec(key[2]));
        return c.doFinal(plain);
    }

    private static byte[] mac(byte[] key, byte[] data, byte[] salt) throws Exception {
        Mac m = Mac.getInstance("HmacSHA256");
        m.init(new SecretKeySpec(key, "HmacSHA256"));
        m.update(salt);
        m.update(data);
        return m.doFinal(ByteBuffer.allocate(8).order(ByteOrder.LITTLE_ENDIAN).putLong(salt.length).array());
    }

    private static byte[] archive(byte[] plain, byte[] key) throws Exception {
        byte[] salt = new byte[32];
        Arrays.fill(salt, (byte) 0x21);
        byte[] main = Unpack.hkdf(key, salt, cat("AEA_AMK".getBytes(StandardCharsets.US_ASCII), le(1)), 32);
        byte[][] clusters = new byte[2][];
        byte[] next = new byte[32];
        for (int cluster = 1; cluster >= 0; cluster--) {
            byte[] ck = Unpack.hkdf(main, new byte[0], cat("AEA_CK".getBytes(StandardCharsets.US_ASCII), le(cluster)), 32);
            byte[][] chk = material(ck, "AEA_CHEK", new byte[0]);
            ByteBuffer header = ByteBuffer.allocate(16).order(ByteOrder.LITTLE_ENDIAN);
            byte[][] encrypted = new byte[2][];
            byte[][] tags = new byte[2][];
            for (int segment = 0; segment < 2; segment++) {
                byte[][] sk = material(ck, "AEA_SK", le(segment));
                int off = (cluster * 2 + segment) * SEGMENT;
                encrypted[segment] = crypt(sk, Arrays.copyOfRange(plain, off, off + SEGMENT));
                tags[segment] = mac(sk[0], encrypted[segment], new byte[0]);
                header.putInt(SEGMENT).putInt(SEGMENT);
            }
            byte[] h = crypt(chk, header.array()), tagsWithNext = cat(next, tags[0], tags[1]);
            next = mac(chk[0], h, tagsWithNext);
            clusters[cluster] = cat(h, tagsWithNext, encrypted[0], encrypted[1]);
        }
        ByteBuffer root = ByteBuffer.allocate(48).order(ByteOrder.LITTLE_ENDIAN);
        root.putLong(0, plain.length);
        root.putInt(16, SEGMENT).putInt(20, 2);
        root.put(24, (byte) '-');
        byte[][] rk = material(main, "AEA_RHEK", new byte[0]);
        byte[] encryptedRoot = crypt(rk, root.array());
        return cat(new byte[] {'A', 'E', 'A', '1'}, le(1), le(0), salt,
                mac(rk[0], encryptedRoot, next), encryptedRoot, next, clusters[0], clusters[1]);
    }

    private static void require(boolean condition, String why) {
        if (!condition) throw new AssertionError(why);
    }

    public static void main(String[] args) throws Exception {
        File dir = new File(args[0]);
        byte[] plain = new byte[4 * SEGMENT], key = new byte[32];
        for (int i = 0; i < plain.length; i++) plain[i] = (byte) (i * 31 + i / 97);
        Arrays.fill(key, (byte) 0x52);
        byte[] encoded = archive(plain, key);
        File input = new File(dir, "synthetic.aea"), output = new File(dir, "plain.img");
        Files.write(input.toPath(), encoded);
        AtomicBoolean pause = new AtomicBoolean();
        try {
            Unpack.decryptAea(input, output, key, true, done -> pause.set(true), pause::get);
            throw new AssertionError("first-cluster pause was ignored");
        } catch (IOException e) {
            require("stopped".equals(e.getMessage()), "unexpected pause error: " + e);
        }
        byte[] interrupted = Files.readAllBytes(input.toPath());
        require(Arrays.equals(Arrays.copyOf(encoded, 156), Arrays.copyOf(interrupted, 156)), "resume header was destroyed");
        for (int i = SEGMENT; i < 2 * SEGMENT; i++) require(interrupted[i] == 0, "test did not actually release ciphertext blocks");
        require(!Unpack.aeaComplete(output), "partial output marked complete");
        long size = Unpack.decryptAea(input, output, key, true, done -> {}, () -> false);
        require(size == plain.length && Arrays.equals(plain, Files.readAllBytes(output.toPath())), "resumed plaintext mismatch");
        require(Unpack.aeaComplete(output), "complete checkpoint missing");
        Unpack.decryptAea(input, output, key, true, done -> { throw new AssertionError("completed ciphertext was read again"); }, () -> false);
        require(Arrays.equals(plain, Files.readAllBytes(output.toPath())), "cleanup retry changed plaintext");
        require(input.delete() && Unpack.aeaComplete(output), "completion not recoverable after input deletion");
        Files.write(input.toPath(), encoded);
        Files.write(new File(output + ".progress").toPath(), "1 broken checkpoint".getBytes(StandardCharsets.US_ASCII));
        try {
            Unpack.decryptAea(input, output, key, true, done -> {}, () -> false);
            throw new AssertionError("malformed checkpoint accepted");
        } catch (IOException e) {
            require(e.getMessage().contains("damaged decrypt checkpoint"), "wrong checkpoint error: " + e);
        }
        require(Arrays.equals(encoded, Files.readAllBytes(input.toPath())), "bad checkpoint changed the input");
        System.out.println("PASS: actual hole punch, preserved header, pause/resume, full plaintext, completion retry, malformed checkpoint");
    }
}
