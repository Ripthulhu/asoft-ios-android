#!/usr/bin/env python3
"""Host PTY rehearsal only; synthetic bytes, no device or network access."""
import base64
import hashlib
import json
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import sys
import tempfile
import termios
import time

HERE = Path(__file__).resolve().parent
RECEIVER = HERE / "receive_device_update.py"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def frame(sequence, data, wanted=None):
    encoded = base64.b64encode(data)
    lines = [encoded[i:i + 1024] for i in range(0, len(encoded), 1024)]
    return (("PART %d %d %s\n" % (sequence, len(data), wanted or sha(data))).encode()
            + b"\n".join(lines) + ("\nEND %d\n" % sequence).encode())


class Terminal:
    def __init__(self, out, payload, *extra, expected=None, partial_final=False):
        self.master, self.slave = pty.openpty()
        self.saved = termios.tcgetattr(self.slave)
        self.output = bytearray()
        # Match Termux's missing API, and optionally interrupt a real final-copy
        # write after 1234 bytes. This test hook is outside the receiver source.
        launch = '''
import os, runpy, sys
from pathlib import Path
if hasattr(os, "link"):
    delattr(os, "link")
fault = sys.argv.pop(1) == "partial"
sys.argv.pop(0)
namespace = runpy.run_path(sys.argv[0], run_name="receiver_rehearsal")
if fault:
    original_open = Path.open
    class PartialWriter:
        def __init__(self, stream): self.stream = stream
        def __enter__(self): return self
        def __exit__(self, *args): self.stream.close()
        def write(self, data):
            self.stream.write(data[:1234])
            self.stream.flush()
            os.fsync(self.stream.fileno())
            raise namespace["SignalExit"](15)
        def __getattr__(self, name): return getattr(self.stream, name)
    def inject(path, mode="r", *args, **kwargs):
        stream = original_open(path, mode, *args, **kwargs)
        return PartialWriter(stream) if path.name == "device-update.zip" and mode == "xb" else stream
    Path.open = inject
sys.exit(namespace["main"]())
'''
        self.process = subprocess.Popen(
            [sys.executable, "-c", launch, "partial" if partial_final else "normal",
             str(RECEIVER), "--out", str(out), "--bytes", str(len(payload)),
             "--sha256", expected or sha(payload), *extra],
            stdin=self.slave, stdout=self.slave, stderr=self.slave,
            start_new_session=True, close_fds=True)
        os.set_blocking(self.master, False)

    def drain(self):
        try:
            while block := os.read(self.master, 65536):
                self.output.extend(block)
        except BlockingIOError:
            pass

    def expect(self, wanted, start=0, timeout=10):
        end = time.monotonic() + timeout
        while wanted not in self.output[start:]:
            if time.monotonic() >= end:
                raise AssertionError((wanted, bytes(self.output[-2000:])))
            select.select([self.master], [], [], 0.05)
            self.drain()
        return bytes(self.output[start:])

    def send(self, data):
        start = len(self.output)
        offset = 0
        end = time.monotonic() + 20
        while offset < len(data):
            assert time.monotonic() < end, "PTY paste stalled"
            self.drain()
            if select.select([], [self.master], [], 0.1)[1]:
                try:
                    offset += os.write(self.master, data[offset:offset + 2048])
                except BlockingIOError:
                    pass
        return start

    def finish(self, expected):
        result = self.process.wait(timeout=5)
        self.drain()
        assert result == expected, (result, bytes(self.output[-2000:]))
        assert termios.tcgetattr(self.slave) == self.saved, "TTY settings were not restored"
        os.close(self.master)
        os.close(self.slave)


def main():
    work = Path(tempfile.mkdtemp(prefix="pixel-receiver-pty-", dir="/tmp"))
    payload = bytes((i * 37 + 11) % 256 for i in range(196608 + 27977 + 123))
    chunks = [payload[:196608], payload[196608:-123], payload[-123:]]
    destination = work / "transfer"
    p = Terminal(destination, payload)
    p.expect(b"READY next=0")
    assert not termios.tcgetattr(p.slave)[3] & termios.ECHO

    start = p.send(frame(0, chunks[0][:4096], "0" * 64))
    p.expect(b"NACK 0 CHECKSUM", start)
    assert json.loads((destination / "checkpoint.json").read_text())["parts"] == []
    assert (destination / "incoming.zip").stat().st_size == 0

    start = p.send(frame(0, chunks[0]))
    got = p.expect(b"READY next=1", start)
    assert b"ACK 0 bytes=196608" in got and b"TOTAL 196608" in got
    assert sha(chunks[0])[:32].encode() in got and sha(chunks[0])[32:].encode() in got
    start = p.send(frame(0, chunks[0]))
    got = p.expect(b"READY next=1", start)
    assert b"DUPLICATE" in got and b"TOTAL 196608" in got
    start = p.send(b"QUIT\n")
    p.expect(b"PAUSED", start)
    p.finish(0)

    p = Terminal(destination, payload, "--resume")
    p.expect(b"READY next=1")
    # A disconnected/incomplete next part must not become a checkpoint.
    partial = frame(1, chunks[1])
    p.send(partial[:partial.index(b"\n") + 1] + partial.split(b"\n")[1] + b"\n")
    p.expect(b"RECEIVING part=1")
    os.kill(p.process.pid, signal.SIGTERM)
    p.expect(b"PAUSED signal=15")
    p.finish(143)

    p = Terminal(destination, payload, "--resume")
    p.expect(b"READY next=1")
    for sequence in (1, 2):
        start = p.send(frame(sequence, chunks[sequence]))
        got = p.expect(("READY next=%d" % (sequence + 1)).encode(), start)
        assert ("ACK %d " % sequence).encode() in got
    start = p.send(b"FINISH\n")
    p.expect(b"DONE bytes=224708", start)
    p.finish(0)
    assert (destination / "device-update.zip").read_bytes() == payload
    assert not (destination / "incoming.zip").exists()
    assert json.loads((destination / "checkpoint.json").read_text())["complete"] is True
    assert not (destination / "device-update.zip").stat().st_mode & 0o111

    interrupted_copy = work / "partial-final"
    p = Terminal(interrupted_copy, payload, partial_final=True)
    p.expect(b"READY next=0")
    start = p.send(frame(0, payload))
    p.expect(b"READY next=1", start)
    start = p.send(b"FINISH\n")
    p.expect(b"PAUSED signal=15", start)
    p.finish(143)
    partial_file = interrupted_copy / "device-update.zip"
    prefix = partial_file.read_bytes()
    assert prefix == payload[:1234]
    assert (interrupted_copy / "incoming.zip").read_bytes() == payload
    assert json.loads((interrupted_copy / "checkpoint.json").read_text())["finalizing"] is True
    # Existing mismatched bytes are refused, never overwritten by recovery.
    partial_file.write_bytes(b"!" + prefix[1:])
    p = Terminal(interrupted_copy, payload, "--resume")
    p.expect(b"ERROR ValueError")
    p.finish(1)
    assert partial_file.read_bytes() == b"!" + prefix[1:]
    partial_file.write_bytes(prefix)
    p = Terminal(interrupted_copy, payload, "--resume")
    p.expect(b"DONE bytes=224708")
    p.finish(0)
    assert partial_file.read_bytes() == payload
    assert not (interrupted_copy / "incoming.zip").exists()
    assert json.loads((interrupted_copy / "checkpoint.json").read_text())["complete"] is True

    p = Terminal(work / "wrong-whole", b"abc", expected="0" * 64)
    p.expect(b"READY next=0")
    start = p.send(frame(0, b"abc"))
    p.expect(b"READY next=1", start)
    start = p.send(b"FINISH\n")
    p.expect(b"NACK FINISH archive checksum", start)
    assert not (work / "wrong-whole/device-update.zip").exists()
    p.send(b"QUIT\n")
    p.finish(0)

    p = Terminal(work / "timeout", b"x", "--timeout", "0.1")
    p.expect(b"ERROR TimeoutError")
    p.finish(1)
    p = Terminal(work / "bounds", b"x")
    p.expect(b"READY next=0")
    p.send(("PART 0 1048577 " + "0" * 64 + "\n").encode())
    p.expect(b"ERROR ValueError")
    p.finish(1)

    report = {
        "status": "HOST_PTY_RECEIVER_PASS", "work": str(work),
        "receiver_sha256": sha(RECEIVER.read_bytes()), "synthetic_bytes": len(payload),
        "normal_part_bytes": [len(chunk) for chunk in chunks],
        "checks": ["bad-part-checksum-refused", "196608-byte-paste-with-1024-char-lines",
                   "exact-ack-sequence-hash-and-byte-count", "duplicate-idempotent",
                   "quit-and-resume", "signal-during-part-and-resume",
                   "full-handshake-and-whole-sha", "wrong-whole-sha-refused",
                   "input-timeout", "declared-part-bound", "tty-restored-on-every-exit",
                   "all-runs-without-os-link", "interrupted-final-copy-resumed",
                   "mismatched-partial-final-refused-without-overwrite"],
        "android_device_executed": False,
    }
    path = work / "rehearsal.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": str(path), **report}, indent=2))


if __name__ == "__main__":
    main()
