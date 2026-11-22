"""Focused synthetic checks; no phone, guest, disk image or native binary execution."""
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name[:-3], HERE / name)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class DiagnosticTests(unittest.TestCase):
    def test_unreapable_owned_child_stays_recorded_and_cannot_look_clean(self):
        m = load('probe_qemu_img.py')
        with tempfile.TemporaryDirectory() as folder:
            m.OUT = Path(folder)
            child = mock.Mock(pid=4242)
            child.poll.return_value = None
            child.wait.side_effect = subprocess.TimeoutExpired('synthetic-child', 5)
            rows = []
            with mock.patch.object(m.subprocess, 'Popen', return_value=child):
                with self.assertRaisesRegex(RuntimeError, 'cleanup incomplete'):
                    m.run_tool('sample', ['synthetic-child'], {}, rows)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['pid'], 4242)
            self.assertFalse(rows[0]['reaped'])
            self.assertTrue(rows[0]['forced'])
            self.assertIn('TimeoutExpired', rows[0]['cleanup_error'])
            self.assertEqual(json.loads((m.OUT / 'sample.exit.json').read_text()), rows[0])

    def test_header_flags_keep_boot_and_runtime_inconsistency_distinct(self):
        m = load('inspect_hfs_headers_UNRELEASED.py')
        for mask, boot, runtime in [(0x2000 | 0x0100, False, False), (0x2000 | 0x0800, True, False),
                                    (0x2000 | 0x4000, False, True), (0x0800 | 0x4000, True, True)]:
            with self.subTest(mask=mask):
                raw = bytearray(512)
                struct.pack_into('>HHIII', raw, 0, 0x4858, 5, mask, 0x4846534a, 7)
                struct.pack_into('>III', raw, 40, 4096, 8388608, 123)
                struct.pack_into('>I', raw, 68, 29)
                row = m.decode_header(bytes(raw), 'saved', 'iOSRoot', 'primary', 1049600, 67108864)
                self.assertEqual(row['attributes'], mask)
                self.assertEqual(row['boot_inconsistent_bit11'], boot)
                self.assertEqual(row['runtime_inconsistent_bit14'], runtime)
                self.assertEqual(row['journaled_bit13'], bool(mask & 0x2000))
                self.assertEqual(row['write_count'], 29)
                self.assertEqual(row['free_blocks'], 123)
                self.assertTrue(row['geometry_matches_frozen_expectation'])

    def test_header_decoder_rejects_partial_read(self):
        m = load('inspect_hfs_headers_UNRELEASED.py')
        with self.assertRaisesRegex(ValueError, 'exact 512-byte'):
            m.decode_header(bytes(511), 'saved', 'iOSRoot', 'primary', 1049600, 67108864)


if __name__ == '__main__':
    unittest.main(verbosity=2)
