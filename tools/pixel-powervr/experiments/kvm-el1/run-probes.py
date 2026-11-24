"""Exercise ARM64 KVM compatibility primitives with two synthetic EL1 guests."""

import argparse
import ctypes
import fcntl
import mmap
import os
from contextlib import ExitStack, contextmanager
from pathlib import Path
import signal
import struct


GUEST_PC = 0x40000000
EL_TABLE = 0x40100000
GL_TABLE = 0x40104000
DATA = 0x42000000
READ_ONLY = 0x40010000
FILTER_FUNCTION = 0x8600FF00
KVM_EXIT_HYPERCALL = 3
KVM_EXIT_MMIO = 6
REG_CORE = 0x6030000000100000
REG_X0 = REG_CORE
REG_X1 = REG_CORE + 2
REG_X10 = REG_CORE + 20
REG_PC = REG_CORE + 64
REG_PSTATE = REG_CORE + 66
REG_TTBR0_EL1 = 0x603000000013C100


def request(direction, opcode, size=0):
    return direction << 30 | size << 16 | 0xAE << 8 | opcode


def address(buffer):
    return ctypes.addressof(ctypes.c_ubyte.from_buffer(buffer))


def one_reg(vcpu, register, value=None):
    data = ctypes.c_uint64(0 if value is None else value)
    operation = 0xAB if value is None else 0xAC
    fcntl.ioctl(vcpu, request(1, operation, 16), struct.pack("=QQ", register, ctypes.addressof(data)))
    return data.value


def exit_reason(vcpu, run):
    fcntl.ioctl(vcpu, request(0, 0x80))
    return struct.unpack_from("=I", run, 8)[0]


def require(predicate, message):
    if not predicate:
        raise RuntimeError(message)


@contextmanager
def guest(payload, regions):
    with ExitStack() as cleanup:
        def own(fd):
            cleanup.callback(os.close, fd)
            return fd

        def mapping(size):
            return cleanup.enter_context(mmap.mmap(-1, size))

        kvm = own(os.open("/dev/kvm", os.O_RDWR | os.O_CLOEXEC))
        require(fcntl.ioctl(kvm, request(0, 0)) == 12, "unexpected KVM API version")
        vm = own(fcntl.ioctl(kvm, request(0, 1), 0))

        # KVM_ARM_VM_SMCCC_FILTER, KVM_SMCCC_FILTER_FWD_TO_USER.
        filter_entry = bytearray(struct.pack("=IIB15x", FILTER_FUNCTION, 1, 2))
        fcntl.ioctl(vm, request(1, 0xE1, 24), struct.pack("=IIQQ", 0, 0, 0, address(filter_entry)))

        code = mapping(mmap.PAGESIZE)
        require(0 < len(payload) <= len(code), "guest code must fit one host page")
        code[:len(payload)] = payload
        buffers = {GUEST_PC: code}
        for slot, (ipa, size, flags) in enumerate([(GUEST_PC, len(code), 0), *regions]):
            buffer = code if slot == 0 else mapping(size)
            buffers[ipa] = buffer
            data = struct.pack("=IIQQQ", slot, flags, ipa, size, address(buffer))
            fcntl.ioctl(vm, request(1, 0x46, 32), data)

        vcpu = own(fcntl.ioctl(vm, request(0, 0x41), 0))
        target = bytearray(32)
        fcntl.ioctl(vm, request(2, 0xAF, 32), target)
        fcntl.ioctl(vcpu, request(1, 0xAE, 32), target)
        one_reg(vcpu, REG_PC, GUEST_PC)
        one_reg(vcpu, REG_PSTATE, 0x3C5)
        run_size = fcntl.ioctl(kvm, request(0, 4))
        run = cleanup.enter_context(mmap.mmap(vcpu, run_size))
        yield vcpu, run, buffers


def expect_hvc(vcpu, run, tag):
    observed = exit_reason(vcpu, run), one_reg(vcpu, REG_X0), one_reg(vcpu, REG_X1)
    require(observed == (KVM_EXIT_HYPERCALL, FILTER_FUNCTION, tag), f"unexpected HVC witness {observed}")


def test_userspace_exits(payload):
    # KVM_MEM_READONLY lets the host observe and service the test page's store.
    with guest(payload, [(READ_ONLY, mmap.PAGESIZE, 2)]) as (vcpu, run, buffers):
        expect_hvc(vcpu, run, 0x1111)
        one_reg(vcpu, REG_X0, 0x2A)

        reason = exit_reason(vcpu, run)
        ipa, data, size, writing = struct.unpack_from("=Q8sIB", run, 32)
        require((reason, ipa, size, writing) == (KVM_EXIT_MMIO, READ_ONLY, 8, 1), "missing write exit")
        buffer = buffers[READ_ONLY]
        require(not any(buffer[:8]) and int.from_bytes(data, "little") == 0x1234, "incorrect trapped store")
        buffer[:size] = data[:size]

        expect_hvc(vcpu, run, 0x2222)
        print("KVM_EL1_HVC_AND_READONLY_WRITE_PASS", flush=True)


def test_permissions(payload):
    regions = [(EL_TABLE, 16384, 0), (GL_TABLE, 16384, 0), (DATA, mmap.PAGESIZE, 0)]
    with guest(payload, regions) as (vcpu, run, buffers):
        for address, permissions in ((EL_TABLE, 0x785), (GL_TABLE, 0x705)):
            table = buffers[address]
            struct.pack_into("=Q", table, (GUEST_PC >> 25) * 8, GUEST_PC | 0x705)
            struct.pack_into("=Q", table, (DATA >> 25) * 8, DATA | permissions)

        expect_hvc(vcpu, run, 1)
        require(one_reg(vcpu, REG_X10) == 2, "expected two undefined Apple operations")
        one_reg(vcpu, REG_TTBR0_EL1, GL_TABLE)
        expect_hvc(vcpu, run, 2)
        one_reg(vcpu, REG_TTBR0_EL1, EL_TABLE)
        expect_hvc(vcpu, run, 3)
        require(struct.unpack_from("=Q", buffers[DATA])[0] == 0x1234, "guarded store missing")
        print("KVM_EL1_UNDEF_AND_PERMISSION_SWITCH_PASS", flush=True)


def expiry(_signum, _frame):
    raise TimeoutError("KVM_RUN exceeded the fixture deadline")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exits", type=Path)
    parser.add_argument("permissions", type=Path)
    args = parser.parse_args()
    signal.signal(signal.SIGALRM, expiry)
    signal.alarm(10)
    try:
        test_userspace_exits(args.exits.read_bytes())
        test_permissions(args.permissions.read_bytes())
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    main()
