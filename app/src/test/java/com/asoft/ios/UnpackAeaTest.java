package com.asoft.ios;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertThrows;
import static org.junit.Assert.assertTrue;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Random;

import javax.crypto.Cipher;
import javax.crypto.Mac;
import javax.crypto.spec.IvParameterSpec;
import javax.crypto.spec.SecretKeySpec;

import org.junit.After;
import org.junit.Before;
import org.junit.Test;

/**
 * Unpack.decryptAea on a small AEA file made here (profile 1, no compression: no libunpack needed): a decrypt that
 * is stopped and goes on gives the same file as one that is not, and what is freed behind it never includes the
 * header (A#247: every stop was "... is no AEA file" at the Resume).
 */
public class UnpackAeaTest {
    private static final int SEG = 256 << 10, NSEG = 8;          // a cluster is 2 MiB of plain text
    private static final long MIB = 1L << 20;
    private static final Unpack.DirectorySync JVM_DIRECTORY_SYNC = directory -> {};

    private File dir;
    private byte[] plain, key;
    private long dataAt;

    @Before
    public void dir() throws IOException {
        dir = Files.createTempDirectory("unpackaea").toFile();
        // three whole clusters and a part of a fourth
        plain = new byte[3 * NSEG * SEG + 700_000];
        new Random(247).nextBytes(plain);
        key = new byte[32];
        new Random(5).nextBytes(key);
    }

    @After
    public void clean() {
        File[] f = dir.listFiles();
        if (f != null) {
            for (File x : f) {
                x.delete();
            }
        }
        dir.delete();
    }

    /** What the freeing does to the bytes: they read as zeros afterwards. */
    private static void zero(String path, long off, long len) {
        try (RandomAccessFile f = new RandomAccessFile(path, "rw")) {
            f.seek(off);
            f.write(new byte[(int) len]);
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    @Test
    public void aDecryptStoppedAfterTheFirstClusterGoesOnToTheSameFile() throws IOException {
        File aea = build("a.aea");
        File out = new File(dir, "a");
        List<long[]> freed = new ArrayList<>();
        Unpack.Hole hole = (path, off, len) -> {
            freed.add(new long[] {off, len});
            zero(path, off, len);
        };
        int[] done = {0};
        IOException e = assertThrows(IOException.class,
                () -> Unpack.decryptAea(aea, out, key, hole, JVM_DIRECTORY_SYNC, p -> done[0]++, () -> done[0] >= 1));
        assertEquals("stopped", e.getMessage());
        assertTrue(new File(out.getPath() + ".progress").isFile());
        // the first cluster's bytes are freed, from the first whole MiB behind the header, and the header reads as before
        assertEquals(1, freed.size());
        assertEquals(MIB, freed.get(0)[0]);
        assertEquals(Unpack.head(aea).dataAt, dataAt);

        long size = Unpack.decryptAea(aea, out, key, hole, JVM_DIRECTORY_SYNC, p -> {
        }, () -> false);
        assertEquals(plain.length, size);
        assertArrayEquals(plain, Files.readAllBytes(out.toPath()));
        assertTrue(Unpack.aeaComplete(out));
        // no freed range ever began below the header's end
        for (long[] r : freed) {
            assertTrue("freed from " + r[0] + ", the header ends at " + dataAt, r[0] >= dataAt);
        }
        // and it equals a decrypt that was never stopped, on a copy that is not freed at all
        File aea2 = build("b.aea");
        File straight = new File(dir, "b");
        Unpack.decryptAea(aea2, straight, key, null, JVM_DIRECTORY_SYNC, p -> {
        }, () -> false);
        assertArrayEquals(Files.readAllBytes(straight.toPath()), Files.readAllBytes(out.toPath()));
    }

    @Test
    public void aDecryptStoppedAfterTwoClustersGoesOnToo() throws IOException {
        File aea = build("a.aea");
        File out = new File(dir, "a");
        Unpack.Hole hole = UnpackAeaTest::zero;
        int[] done = {0};
        assertThrows(IOException.class, () -> Unpack.decryptAea(aea, out, key, hole, JVM_DIRECTORY_SYNC, p -> done[0]++, () -> done[0] >= 2));
        // (a second stop on the way, too)
        int[] more = {0};
        assertThrows(IOException.class, () -> Unpack.decryptAea(aea, out, key, hole, JVM_DIRECTORY_SYNC, p -> more[0]++, () -> more[0] >= 1));
        Unpack.decryptAea(aea, out, key, hole, JVM_DIRECTORY_SYNC, p -> {
        }, () -> false);
        assertArrayEquals(plain, Files.readAllBytes(out.toPath()));
    }

    @Test
    public void holeFromNeverGoesBelowTheHeaderEnd() {
        // the cluster at the header's end: before, the MiB boundary below it, 0
        assertEquals(0, 300 & ~(MIB - 1));
        assertEquals(MIB, Unpack.holeFrom(300, 300));
        // a later cluster: its own boundary
        assertEquals(5 * MIB, Unpack.holeFrom(5 * MIB + 10, 300));
        assertEquals(5 * MIB, Unpack.holeFrom(5 * MIB, 300));
        // a header that ends past the first MiB (a big auth block): the next boundary after it
        assertEquals(3 * MIB, Unpack.holeFrom(3 * MIB - 100, 2 * MIB + 5));
        assertEquals(2 * MIB, Unpack.holeFrom(2 * MIB - 100, 2 * MIB));
    }

    @Test
    public void replacingAnOldHeaderErasedInputLetsTheExistingCheckpointResume() throws IOException {
        File aea = build("a.aea");
        File out = new File(dir, "a");
        Unpack.Hole old = (path, off, len) -> zero(path, 0, off + len);
        int[] done = {0};
        assertThrows(IOException.class, () -> Unpack.decryptAea(aea, out, key, old, JVM_DIRECTORY_SYNC,
                p -> done[0]++, () -> done[0] >= 1));
        assertTrue(Unpack.hasErasedAeaHeader(aea));
        assertThrows(IOException.class, () -> Unpack.head(aea));

        File checkpoint = new File(out.getPath() + ".progress");
        assertTrue(checkpoint.isFile());
        File restored = build("restored.aea");
        assertFalse(Unpack.hasErasedAeaHeader(restored));
        Unpack.decryptAea(restored, out, key, UnpackAeaTest::zero, JVM_DIRECTORY_SYNC, progress -> {}, () -> false);
        assertArrayEquals(plain, Files.readAllBytes(out.toPath()));
        assertTrue(Unpack.aeaComplete(out));
    }

    @Test
    public void aZeroMagicWithRemainingHeaderBytesIsNotAnOldHolePunch() throws IOException {
        File aea = build("wrong-magic.aea");
        zero(aea.getPath(), 0, 4);
        assertFalse(Unpack.hasErasedAeaHeader(aea));
        assertThrows(IOException.class, () -> Unpack.head(aea));
    }

    @Test
    public void theEncryptedInputIsNotPunchedWhenTheCheckpointDirectorySyncFails() throws IOException {
        File aea = build("a.aea");
        File out = new File(dir, "a");
        List<Long> freed = new ArrayList<>();
        IOException error = assertThrows(IOException.class, () -> Unpack.decryptAea(aea, out, key,
                (path, off, len) -> freed.add(off), directory -> {
                    throw new IOException("directory sync failed");
                }, progress -> {}, () -> false));
        assertEquals("directory sync failed", error.getMessage());
        assertTrue(freed.isEmpty());
        assertFalse(Unpack.hasErasedAeaHeader(aea));
    }

    // -- an AEA file as the format has it (profile 1, no compression) ---------------------------------------

    private static byte[] cat(byte[]... parts) {
        ByteArrayOutputStream o = new ByteArrayOutputStream();
        for (byte[] p : parts) {
            o.write(p, 0, p.length);
        }
        return o.toByteArray();
    }

    private static byte[] le32(int v) {
        return ByteBuffer.allocate(4).order(ByteOrder.LITTLE_ENDIAN).putInt(v).array();
    }

    private static byte[] ascii(String s) {
        return s.getBytes(StandardCharsets.US_ASCII);
    }

    /** HMAC-SHA256(key, salt || data || le64(len(salt))). */
    private static byte[] mac(byte[] key, byte[] data, byte[] salt) {
        try {
            Mac m = Mac.getInstance("HmacSHA256");
            m.init(new SecretKeySpec(key, "HmacSHA256"));
            m.update(salt);
            m.update(data);
            m.update(ByteBuffer.allocate(8).order(ByteOrder.LITTLE_ENDIAN).putLong(salt.length).array());
            return m.doFinal();
        } catch (java.security.GeneralSecurityException e) {
            throw new IllegalStateException(e);
        }
    }

    /** AES-256-CTR in place (the same call encrypts and decrypts). */
    private static void ctr(byte[] key, byte[] iv, byte[] data) {
        try {
            Cipher c = Cipher.getInstance("AES/CTR/NoPadding");
            c.init(Cipher.ENCRYPT_MODE, new SecretKeySpec(key, "AES"), new IvParameterSpec(iv));
            c.doFinal(data, 0, data.length, data, 0);
        } catch (java.security.GeneralSecurityException e) {
            throw new IllegalStateException(e);
        }
    }

    /** HKDF's 80 bytes for @info: MAC key 32, AES key 32, IV 16. */
    private static byte[][] material(byte[] key, String info, byte[] more) throws IOException {
        byte[] b = Unpack.hkdf(key, new byte[0], cat(ascii(info), more), 80);
        return new byte[][] {Arrays.copyOfRange(b, 0, 32), Arrays.copyOfRange(b, 32, 64), Arrays.copyOfRange(b, 64, 80)};
    }

    /** The file @name in the temp folder: the header, then every cluster (headers, MACs, segments), of this test's plain text. */
    private File build(String name) throws IOException {
        byte[] salt = new byte[32];
        new Random(9).nextBytes(salt);
        int profileWord = 1;
        byte[] auth = cat(le32(4 + 6), ascii("meta"), new byte[] {0}, ascii("x"), new byte[] {0});
        byte[] main = Unpack.hkdf(key, salt, cat(ascii("AEA_AMK"), le32(profileWord)), 32);
        int clusterBytes = NSEG * SEG;
        int clusters = (plain.length + clusterBytes - 1) / clusterBytes;
        byte[][] cluster = new byte[clusters][];
        byte[] nextMac = new byte[32];              // the last cluster's: nothing follows it
        for (int k = clusters - 1; k >= 0; k--) {
            byte[] ck = Unpack.hkdf(main, new byte[0], cat(ascii("AEA_CK"), le32(k)), 32);
            byte[][] chk = material(ck, "AEA_CHEK", new byte[0]);
            byte[] hdr = new byte[8 * NSEG], macs = new byte[32 + 32 * NSEG];
            System.arraycopy(nextMac, 0, macs, 0, 32);
            ByteArrayOutputStream data = new ByteArrayOutputStream();
            ByteBuffer hb = ByteBuffer.wrap(hdr).order(ByteOrder.LITTLE_ENDIAN);
            for (int i = 0; i < NSEG; i++) {
                long pos = ((long) k * NSEG + i) * SEG;
                int size = (int) Math.max(0, Math.min(SEG, plain.length - pos));
                hb.putInt(i * 8, size).putInt(i * 8 + 4, size);
                if (size == 0) {
                    continue;
                }
                byte[][] sk = material(ck, "AEA_SK", le32(i));
                byte[] enc = Arrays.copyOfRange(plain, (int) pos, (int) pos + size);
                ctr(sk[1], sk[2], enc);
                System.arraycopy(mac(sk[0], enc, new byte[0]), 0, macs, 32 + 32 * i, 32);
                data.write(enc, 0, enc.length);
            }
            ctr(chk[1], chk[2], hdr);
            nextMac = mac(chk[0], hdr, macs);
            cluster[k] = cat(hdr, macs, data.toByteArray());
        }
        byte[] root = new byte[48];
        ByteBuffer rb = ByteBuffer.wrap(root).order(ByteOrder.LITTLE_ENDIAN);
        rb.putLong(0, plain.length).putInt(16, SEG).putInt(20, NSEG);
        root[24] = '-';
        byte[][] rk = material(main, "AEA_RHEK", new byte[0]);
        ctr(rk[1], rk[2], root);
        byte[] rootMac = mac(rk[0], root, cat(nextMac, auth));
        byte[] head = cat(ascii("AEA1"), le32(profileWord), le32(auth.length), auth, salt, rootMac, root, nextMac);
        dataAt = head.length;
        File f = new File(dir, name);
        try (java.io.FileOutputStream o = new java.io.FileOutputStream(f)) {
            o.write(head);
            for (byte[] c : cluster) {
                o.write(c);
            }
        }
        return f;
    }
}
