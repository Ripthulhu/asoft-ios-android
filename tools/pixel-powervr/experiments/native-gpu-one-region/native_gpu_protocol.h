/* SPDX-License-Identifier: MIT
 * Fixed, one-shot scalar native/GPU experiment; not a general memory protocol.
 * Wire ABI is native little-endian, fixed-width and naturally aligned.
 */
#ifndef PIXEL_NATIVE_GPU_PROTOCOL_H
#define PIXEL_NATIVE_GPU_PROTOCOL_H

#define NGP_PROTOCOL_VERSION 1
#define NGP_PACKET_BYTES 256
#define NGP_ALLOCATION_BYTES 32768
#define NGP_VIEW_OFFSET 16384
#define NGP_VIEW_BYTES 16384
#define NGP_HOST_PAGE_BYTES 4096
#define NGP_RAM_BYTES 0x20000000
#define NGP_GPA 0x80000000
#define NGP_CODE_PA 0x40084000
#define NGP_CODE_VA 0x100000000
#define NGP_DATA_VA 0x100004000
#define NGP_STACK_VA 0x100008000
#define NGP_LOAD_PC 0x100000008
#define NGP_STORE_PC 0x100000018
#define NGP_SVC_PC 0x100000020
#define NGP_COMPLETE_PC 0x100000024
#define NGP_PAYLOAD_BYTES 40
#define NGP_SVC_IMMEDIATE 0x80
#define NGP_SVC_TAG 0x4e47
#define NGP_GPU_FILL_BASE 0x6a1b2c30
#define NGP_XOR_MASK 0x00ff00ff00ff00ff
#define NGP_ADDEND 0x137
#define NGP_CODE_SHA256_HEX "20fc0284770e4f1d0ce6a5d662cd3b277be60579c3c0880d9e405a7a649d4540"
#define NGP_ACK_TIMEOUT_MS 2000
#define NGP_ENGINE_TIMEOUT_MS 15000
#define NGP_REAP_TIMEOUT_MS 3000
#define NGP_OWNER_TIMEOUT_SECONDS 45

#ifndef __ASSEMBLER__
#include <stdint.h>
#include <stddef.h>

#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "The diagnostic wire ABI requires a little-endian host."
#endif

#define NGP_MAGIC UINT64_C(0x31504f5250474e50)
enum NgpKind { NGP_EVENT = 1, NGP_ACK = 2 };
enum NgpPhase {
    NGP_READY = 1, NGP_ENTRY = 2, NGP_CODE_MAP = 3,
    NGP_DATA_FAULT = 4, NGP_DATA_MAP = 5, NGP_COMPLETE = 6
};
enum NgpAccess {
    NGP_ACCESS_NONE = 0, NGP_ACCESS_READ = 1,
    NGP_ACCESS_WRITE = 2, NGP_ACCESS_EXEC = 4
};
enum NgpFlags {
    NGP_F_CODE_CACHE = 1, NGP_F_STRICT_EL0 = 2,
    NGP_F_PRODUCER_NX = 4, NGP_F_FDS_ORDERED = 8,
    NGP_F_WORKER_MAPPED = 16, NGP_F_NATIVE_COMPLETE = 32
};
#define NGP_BASE_FLAGS (NGP_F_CODE_CACHE | NGP_F_STRICT_EL0 | \
                        NGP_F_PRODUCER_NX | NGP_F_FDS_ORDERED)

typedef struct NgpPacket {
    uint64_t magic;
    uint32_t version, bytes, kind, phase, sequence, status;
    uint64_t run_generation, inval_generation;
    uint64_t owner_pid, qemu_pid, factory_pid, stub_pid, worker_tid;
    uint64_t gpa, va, allocation_bytes, backing_offset, view_bytes;
    uint64_t pc, fault_address, access, input, output, instruction, proof_flags;
    uint8_t code_sha256[32];
    uint64_t reserved[5];
} NgpPacket;

_Static_assert(sizeof(NgpPacket) == NGP_PACKET_BYTES, "fixed packet size");
_Static_assert(_Alignof(NgpPacket) == 8, "naturally aligned wire data");
_Static_assert(offsetof(NgpPacket, run_generation) == 32, "wire run offset");
_Static_assert(offsetof(NgpPacket, owner_pid) == 48, "wire identity offset");
_Static_assert(offsetof(NgpPacket, gpa) == 88, "wire geometry offset");
_Static_assert(offsetof(NgpPacket, pc) == 128, "wire PC offset");
_Static_assert(offsetof(NgpPacket, code_sha256) == 184, "wire code hash offset");

static const uint32_t ngp_payload_words[10] = {
    0xd2c00022, 0x91401042, 0xf9400040, 0x93c03401, 0xd2009c21,
    0x9104dc21, 0xf9000441, 0xd289c8f0, 0xd4001001, 0xd4200000
};
static const uint8_t ngp_code_sha256[32] = {
    0x20, 0xfc, 0x02, 0x84, 0x77, 0x0e, 0x4f, 0x1d, 0x0c, 0xe6, 0xa5, 0xd6, 0x62, 0xcd, 0x3b, 0x27,
    0x7b, 0xe6, 0x05, 0x79, 0xc3, 0xc0, 0x88, 0x0d, 0x9e, 0x40, 0x5a, 0x7a, 0x64, 0x9d, 0x45, 0x40
};

static inline uint64_t ngp_input(void)
{
    uint64_t word = (uint32_t)(NGP_GPU_FILL_BASE + 4);
    return word | (word << 32);
}
static inline uint64_t ngp_output(uint64_t value)
{
    return (((value >> 13) | (value << 51)) ^ (uint64_t)NGP_XOR_MASK) +
           (uint64_t)NGP_ADDEND;
}
static inline uint64_t ngp_phase_flags(unsigned phase)
{
    return NGP_BASE_FLAGS |
           (phase >= NGP_DATA_MAP ? NGP_F_WORKER_MAPPED : 0) |
           (phase == NGP_COMPLETE ? NGP_F_NATIVE_COMPLETE : 0);
}
static inline const char *ngp_phase_name(unsigned phase)
{
    switch (phase) {
    case NGP_READY: return "READY";
    case NGP_ENTRY: return "ENTRY";
    case NGP_CODE_MAP: return "CODE_MAP";
    case NGP_DATA_FAULT: return "DATA_FAULT";
    case NGP_DATA_MAP: return "DATA_MAP";
    case NGP_COMPLETE: return "COMPLETE";
    default: return "INVALID";
    }
}

/* Phase contract:
 * All packets: immutable geometry/hash/run nonce and owner/QEMU identities;
 * magic/version/bytes/kind/phase/sequence exact; status/reserved are zero.
 * READY: factory > 0; stub/worker are zero; pc/fault/access/input/output/insn 0.
 * ENTRY: positive stable factory/stub/worker; pc CODE_VA, insn word[0],
 *        fault/access/input/output 0.
 * CODE_MAP: pc/fault CODE_VA, access EXEC, insn word[0], input/output 0.
 * DATA_FAULT/DATA_MAP: pc LOAD_PC, fault DATA_VA, access READ, insn word[2],
 *                     input/output 0; DATA_MAP acknowledges completed move.
 * COMPLETE: pc COMPLETE_PC, insn word[8], fault/access 0, input/output exact.
 * DATA_MAP and COMPLETE report the same actual invalidation generation.
 * Flags equal ngp_phase_flags(phase); each sequence number equals its phase.
 * Owner verifies per-message SCM_CREDENTIALS PID == captured QEMU leader.
 * ACK is the event copied byte-for-byte except kind NGP_ACK; after durable
 * owner checkpoint. No duplicates, surplus packets or SCM_RIGHTS are accepted.
 */
#endif
#endif
