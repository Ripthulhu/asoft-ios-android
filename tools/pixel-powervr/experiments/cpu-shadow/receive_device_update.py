#!/usr/bin/env python3
"""TTY-only, checksummed, resumable ZIP receiver. Never extracts or executes it.

PART <sequence> <decoded-bytes> <lowercase-sha256>
<base64 lines, each at most 1024 characters>
END <sequence>

Commands between parts: STATUS, FINISH, QUIT. Use --resume after interruption.
"""
import argparse
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import select
import signal
import stat
import sys
import termios
import time

FORMAT = "pixel-tty-zip-v1"
MAX_PART = 1048576
MAX_PARTS = 16384
SHA = re.compile(r"[0-9a-f]{64}\Z")


def check(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def screen(*lines):
    sys.stdout.write("\033[2J\033[HCPU SHADOW TRANSFER\n" + "\n".join(lines) + "\n")
    sys.stdout.flush()


def hash_lines(value):
    return ["SHA256 1/2 " + value[:32], "SHA256 2/2 " + value[32:]]


def regular(path):
    info = path.lstat()
    check(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
          and not info.st_mode & 0o077, "unsafe owned file: " + path.name)


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def checkpoint(folder, value):
    temporary = folder / "checkpoint.tmp"
    with temporary.open("x", encoding="utf-8") as stream:
        os.chmod(temporary, 0o600)
        json.dump(value, stream, separators=(",", ":"))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, folder / "checkpoint.json")
    sync_dir(folder)


def copy_final(incoming, finished, size, wanted, resume=False):
    """Create exclusively, or append only after validating our interrupted copy."""
    with incoming.open("rb") as source:
        with finished.open("r+b" if resume else "xb") as target:
            if resume:
                # Never replace existing bytes, including an invalid partial copy.
                while block := target.read(65536):
                    check(source.read(len(block)) == block,
                          "partial final archive differs from verified input")
            else:
                finished.chmod(0o600)
            while block := source.read(65536):
                target.write(block)
            target.flush()
            os.fsync(target.fileno())
    check(finished.stat().st_size == size and digest(finished) == wanted,
          "final archive checksum failed")


class SignalExit(BaseException):
    def __init__(self, number):
        self.number = number


def interrupted(number, frame):
    raise SignalExit(number)


class Lines:
    def __init__(self, timeout, total):
        self.timeout = timeout
        self.end = time.monotonic() + 3600
        self.left = max(1048576, 8 * total + 1048576)
        self.pending = bytearray()

    def read(self, part_end=None):
        deadline = min(self.end, time.monotonic() + self.timeout,
                       part_end if part_end is not None else self.end)
        while b"\n" not in self.pending:
            check(len(self.pending) <= 1024, "input line exceeds 1024 bytes")
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([0], [], [], remaining)[0]:
                raise TimeoutError("input timeout; resume retained checkpoint")
            block = os.read(0, 4096)
            if not block:
                raise EOFError("terminal disconnected; resume retained checkpoint")
            self.left -= len(block)
            check(self.left >= 0, "session input budget exceeded")
            self.pending.extend(block)
        line, _, rest = self.pending.partition(b"\n")
        self.pending = bytearray(rest)
        line = line.removesuffix(b"\r")
        check(len(line) <= 1024, "input line exceeds 1024 bytes")
        return bytes(line)


def receive(args):
    folder = args.out.absolute()
    if not args.resume:
        folder.mkdir(mode=0o700)
    info = folder.lstat()
    check(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
          and not info.st_mode & 0o077, "output must be an owned private directory")
    lock_path = folder / "receiver.lock"
    flags = os.O_RDWR | os.O_NOFOLLOW | (0 if args.resume else os.O_CREAT | os.O_EXCL)
    lock = os.open(lock_path, flags, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        regular(lock_path)
        parts = folder / "parts"
        incoming = folder / "incoming.zip"
        finished = folder / "device-update.zip"
        if args.resume:
            regular(folder / "checkpoint.json")
            state = json.loads((folder / "checkpoint.json").read_text())
            check(state["format"] == FORMAT and state["bytes"] == args.bytes
                  and state["sha256"] == args.sha256,
                  "resume parameters differ from retained transfer")
            check(parts.is_dir() and not parts.is_symlink(), "unsafe parts directory")
            if (folder / "checkpoint.tmp").exists():
                regular(folder / "checkpoint.tmp")
                (folder / "checkpoint.tmp").unlink()
        else:
            parts.mkdir(mode=0o700)
            with incoming.open("xb"):
                pass
            incoming.chmod(0o600)
            state = {"format": FORMAT, "bytes": args.bytes, "sha256": args.sha256,
                     "parts": [], "complete": False}
            checkpoint(folder, state)
        check(len(state["parts"]) <= MAX_PARTS, "too many retained parts")
        total = 0
        expected = set()
        for sequence, item in enumerate(state["parts"]):
            name = "%08d.part" % sequence
            expected.add(name)
            path = parts / name
            regular(path)
            check(0 < item["bytes"] <= MAX_PART and SHA.fullmatch(item["sha256"]),
                  "invalid checkpoint part")
            check(path.stat().st_size == item["bytes"] and digest(path) == item["sha256"],
                  "retained part checksum failed: " + str(sequence))
            total += item["bytes"]
        check(total <= args.bytes, "checkpoint exceeds expected archive size")
        for path in parts.iterdir():
            regular(path)
            check(re.fullmatch(r"[0-9]{8}\.part", path.name), "unexpected file in parts")
            if path.name not in expected:
                # A crash before checkpoint publication can leave one unacknowledged part.
                check(int(path.stem) == len(state["parts"]), "unexpected orphan part")
                path.unlink()
        if finished.exists():
            regular(finished)
            check(total == args.bytes, "final archive has missing checkpointed parts")
            if finished.stat().st_size != args.bytes or digest(finished) != args.sha256:
                check(state.get("finalizing") is True and not state["complete"],
                      "unrecognized partial final archive")
                regular(incoming)
                check(incoming.stat().st_size == args.bytes and digest(incoming) == args.sha256,
                      "incoming archive checksum failed during finalization recovery")
                copy_final(incoming, finished, args.bytes, args.sha256, resume=True)
            state = {**state, "complete": True, "finalizing": False}
            checkpoint(folder, state)
            if incoming.exists():
                regular(incoming)
                incoming.unlink()
                sync_dir(folder)
            screen("DONE bytes=" + str(total), *hash_lines(args.sha256),
                   "FILE device-update.zip", "Verified; not extracted or executed.")
            return
        check(not state["complete"], "completed archive is missing")
        regular(incoming)
        # Rebuild only our private aggregate, using verified durable parts.
        with incoming.open("wb") as stream:
            for sequence in range(len(state["parts"])):
                with (parts / ("%08d.part" % sequence)).open("rb") as source:
                    while block := source.read(1048576):
                        stream.write(block)
            stream.flush()
            os.fsync(stream.fileno())

        lines = Lines(args.timeout, args.bytes)

        def ready(*notice):
            screen(*notice, "READY next=" + str(len(state["parts"])),
                   "BYTES " + str(total) + "/" + str(args.bytes))

        ready("Max part=1048576; base64 line<=1024")
        while True:
            command = lines.read()
            if not command:
                continue
            if command == b"STATUS":
                ready()
                continue
            if command == b"QUIT":
                ready("PAUSED; restart with --resume")
                return
            if command == b"FINISH":
                if total != args.bytes:
                    ready("NACK FINISH missing bytes")
                    continue
                actual = digest(incoming)
                if actual != args.sha256:
                    ready("NACK FINISH archive checksum", *hash_lines(actual))
                    continue
                check(not finished.exists(), "final archive already exists; resume to verify")
                # Journal before the exclusive copy. An interrupted destination is
                # retained and resume validates its entire prefix before appending.
                state = {**state, "finalizing": True}
                checkpoint(folder, state)
                copy_final(incoming, finished, args.bytes, actual)
                sync_dir(folder)
                state = {**state, "complete": True, "finalizing": False}
                checkpoint(folder, state)
                incoming.unlink()
                sync_dir(folder)
                screen("DONE bytes=" + str(total), *hash_lines(actual),
                       "FILE device-update.zip", "Verified; not extracted or executed.")
                return
            match = re.fullmatch(rb"PART ([0-9]{1,5}) ([0-9]{1,7}) ([0-9a-f]{64})", command)
            check(match is not None, "expected PART, STATUS, FINISH or QUIT")
            sequence, size = int(match[1]), int(match[2])
            wanted = match[3].decode("ascii")
            check(sequence < MAX_PARTS and 0 < size <= MAX_PART, "part bounds exceeded")
            screen("RECEIVING part=" + str(sequence), "BYTES " + str(total) + "/" + str(args.bytes))
            encoded_left = 4 * ((size + 2) // 3)
            body = bytearray()
            part_end = time.monotonic() + 600
            while encoded_left:
                line = lines.read(part_end)
                if not line:
                    continue
                check(len(line) <= encoded_left and len(line) % 4 == 0,
                      "invalid base64 line length")
                check(b"=" not in line or len(line) == encoded_left,
                      "base64 padding before final line")
                body.extend(base64.b64decode(line, validate=True))
                encoded_left -= len(line)
                check(len(body) <= size, "decoded part exceeds declared size")
            check(lines.read(part_end) == ("END " + str(sequence)).encode(),
                  "missing or wrong END sequence")
            actual = hashlib.sha256(body).hexdigest()
            if len(body) != size or actual != wanted:
                ready("NACK " + str(sequence) + " CHECKSUM", *hash_lines(actual))
                continue
            next_part = len(state["parts"])
            if sequence > next_part:
                ready("NACK " + str(sequence) + " ORDER")
                continue
            duplicate = sequence < next_part
            item = {"bytes": size, "sha256": actual}
            if duplicate:
                if item != state["parts"][sequence]:
                    ready("NACK " + str(sequence) + " DUPLICATE_MISMATCH")
                    continue
            else:
                if total + size > args.bytes:
                    ready("NACK " + str(sequence) + " TOTAL_LIMIT")
                    continue
                part = parts / ("%08d.part" % sequence)
                with part.open("xb") as stream:
                    part.chmod(0o600)
                    stream.write(body)
                    stream.flush()
                    os.fsync(stream.fileno())
                sync_dir(parts)
                with incoming.open("ab") as stream:
                    stream.write(body)
                    stream.flush()
                    os.fsync(stream.fileno())
                updated = {**state, "parts": [*state["parts"], item]}
                checkpoint(folder, updated)
                state = updated
                total += size
            ready("ACK " + str(sequence) + " bytes=" + str(size),
                  "TOTAL " + str(total), *hash_lines(actual),
                  "DUPLICATE" if duplicate else "CHECKPOINT saved")
    finally:
        os.close(lock)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--bytes", type=int, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--timeout", type=float, default=180,
                        help="input idle timeout in seconds (default 180)")
    args = parser.parse_args()
    check(0 < args.bytes <= 1073741824, "archive size must be 1..1073741824 bytes")
    check(SHA.fullmatch(args.sha256), "invalid SHA-256")
    check(0 < args.timeout <= 600, "timeout must be in (0,600]")
    check(os.isatty(0) and os.isatty(1), "stdin and stdout must be a terminal")
    saved = termios.tcgetattr(0)
    quiet = saved.copy()
    quiet[3] = (quiet[3] | termios.ICANON | termios.ISIG) & ~(termios.ECHO | termios.ECHONL)
    handlers = {}
    try:
        for name in ("SIGINT", "SIGTERM", "SIGHUP", "SIGQUIT", "SIGTSTP"):
            number = getattr(signal, name)
            handlers[number] = signal.signal(number, interrupted)
        termios.tcsetattr(0, termios.TCSANOW, quiet)
        receive(args)
        return 0
    except SignalExit as error:
        screen("PAUSED signal=" + str(error.number), "Resume with the same arguments + --resume")
        return 128 + error.number
    except Exception as error:
        screen("ERROR " + type(error).__name__, str(error),
               "Retained data is not executed.", "Resume from the last saved checkpoint.")
        return 1
    finally:
        try:
            termios.tcflush(0, termios.TCIFLUSH)
            termios.tcsetattr(0, termios.TCSANOW, saved)
        except termios.error:
            pass
        for number, handler in handlers.items():
            signal.signal(number, handler)


if __name__ == "__main__":
    sys.exit(main())
