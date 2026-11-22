/* SPDX-License-Identifier: MIT */
#ifndef ASOFT_NATIVE_EFI_PROTOCOL_H
#define ASOFT_NATIVE_EFI_PROTOCOL_H

#define NEF_RAM_BYTES 0x20000000
#define NEF_FRAME_OFFSET 0x01000000
#define NEF_FRAME_PA 0x41000000
#define NEF_ACK_PA 0x41004000
#define NEF_FRAME_BYTES 16384
#define NEF_CODE_PA 0x40084000
#define NEF_CODE_VA 0x100000000
#define NEF_DATA_VA 0x100004000
#define NEF_STACK_VA 0x100008000
#define NEF_MMIO 0x0b000000
#define NEF_SVC_TAG 0x4546
#define NEF_TPIDRRO_BASE 0xcafe0000
#define NEF_TPIDRRO_PC 0x10000007c

/* The swap fixture places two different thread-data slots in ordinary stack
 * RAM. Nonzero guest TPIDR values distinguish the native CPU-hint rewrite
 * (which must read zero) from generic-trap or TCG execution. */
#define NEF_SWAP_TSD_OFFSET 0x100
#define NEF_SWAP_TSD_STRIDE 64
#define NEF_SWAP_TSD_VA (NEF_STACK_VA + NEF_SWAP_TSD_OFFSET)
#define NEF_SWAP_TSD_VALUE 0x123456789abc0000
#define NEF_SWAP_TPIDR_SENTINEL 0x56780000
#define NEF_SWAP_TPIDR_PC 0x100000080
#define NEF_SWAP_SVC_RETURN_PC 0x100000094

#endif
