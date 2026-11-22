/* SPDX-License-Identifier: MIT
 * Synthetic native EL0 writes -> actual reims EFI texture -> GPU output.
 * All code, stacks, page tables and data are ordinary size-sealed memfd RAM.
 * The parent acknowledges only after comparing the GPU frame byte-for-byte.
 */
#include "native_efi_protocol.h"

.section .text.boot,"ax",%progbits
.global _start
.type _start,%function
_start:
    msr daifset, #0xf
    mrs x0, CurrentEL
    cmp x0, #4
    b.eq boot_el1
    cmp x0, #8
    b.ne fatal_early
    mov x0, #0x80000000
    msr hcr_el2, x0
    msr cptr_el2, xzr
    mov x0, #3
    msr cnthctl_el2, x0
    msr cntvoff_el2, xzr
    adrp x0, el1_stack_top
    add x0, x0, :lo12:el1_stack_top
    msr sp_el1, x0
    adr x0, boot_el1
    msr elr_el2, x0
    mov x0, #0x3c5
    msr spsr_el2, x0
    eret

boot_el1:
    adrp x0, el1_stack_top
    add x0, x0, :lo12:el1_stack_top
    mov sp, x0
    adrp x0, __bss_start
    add x0, x0, :lo12:__bss_start
    adrp x1, __bss_end
    add x1, x1, :lo12:__bss_end
1:  cmp x0, x1
    b.hs 2f
    stp xzr, xzr, [x0], #16
    b 1b
2:
    adrp x0, vectors
    add x0, x0, :lo12:vectors
    msr vbar_el1, x0
    adr x0, boot_message
    bl uart_puts

    /* 16 KiB tables, T0SZ=16: L0[0] -> L1[0] -> L2. */
    adrp x0, table_l0
    add x0, x0, :lo12:table_l0
    adrp x1, table_l1
    add x1, x1, :lo12:table_l1
    orr x2, x1, #3
    str x2, [x0]
    adrp x2, table_l2
    add x2, x2, :lo12:table_l2
    orr x3, x2, #3
    str x3, [x1]
    /* 512 MiB ordinary RAM, EL1 RWX, EL0 inaccessible. */
    mov x3, #0x40000000
    mov x4, #32
    mov x5, #16
    mov x8, #0x2000000
    mov x6, #0x701
    mov x7, #0x40000000000000
    orr x6, x6, x7
3:  orr x7, x3, x6
    str x7, [x2, x4, lsl #3]
    add x3, x3, x8
    add x4, x4, #1
    subs x5, x5, #1
    b.ne 3b
    /* Device blocks for UART and the real reims test MMIO aperture. */
    mov x3, #0x08000000
    mov x4, #0x705
    orr x3, x3, x4
    mov x4, #0x60000000000000
    orr x3, x3, x4
    str x3, [x2, #(4 * 8)]
    mov x3, #0x0a000000
    mov x4, #0x705
    orr x3, x3, x4
    mov x4, #0x60000000000000
    orr x3, x3, x4
    str x3, [x2, #(5 * 8)]

    adrp x3, table_l3_user
    add x3, x3, :lo12:table_l3_user
    orr x4, x3, #3
    str x4, [x2, #(128 * 8)]
    ldr x4, =NEF_CODE_PA
    mov x5, #0x7c3
    orr x4, x4, x5
    mov x5, #0x20000000000000
    orr x4, x4, x5
    str x4, [x3]
    ldr x4, =NEF_FRAME_PA
    mov x5, #0x743
    orr x4, x4, x5
    mov x5, #0x60000000000000
    orr x4, x4, x5
    str x4, [x3, #8]
    adrp x4, el0_stack
    add x4, x4, :lo12:el0_stack
    mov x5, #0x743
    orr x4, x4, x5
    mov x5, #0x60000000000000
    orr x4, x4, x5
    str x4, [x3, #16]
    mov x1, #0xff
    msr mair_el1, x1
    ldr x1, =0x80b510
    msr tcr_el1, x1
    msr ttbr0_el1, x0
    msr ttbr1_el1, xzr
    mov x1, #0x300000
    msr cpacr_el1, x1
    dsb sy
    tlbi vmalle1
    dsb sy
    isb
    ldr x1, =0x30d01805
    msr sctlr_el1, x1
    isb
    mov x0, #0
enter_el0:
    ldr x1, =(NEF_STACK_VA + NEF_FRAME_BYTES)
    msr sp_el0, x1
    ldr x1, =NEF_CODE_VA
    msr elr_el1, x1
    mov x1, #0x3c0
    msr spsr_el1, x1
    msr tpidr_el0, xzr
    mov x1, #NEF_TPIDRRO_BASE
    add x1, x1, x0
    msr tpidrro_el0, x1
    eret
.size _start, .-_start

.balign 2048
vectors:
    .rept 8
    b fatal_exception
    .balign 128
    .endr
    b lower_sync
    .balign 128
    .rept 7
    b fatal_exception
    .balign 128
    .endr

lower_sync:
    mrs x2, esr_el1
    lsr x3, x2, #26
    cmp x3, #0x15
    b.ne fatal_exception
    and x2, x2, #0xffff
    cmp x2, #0x80
    b.ne fatal_exception
    mrs x2, elr_el1
    ldr x3, =(NEF_CODE_VA + native_efi_svc - native_efi_payload + 4)
    cmp x2, x3
    b.ne fatal_exception
    mov x2, #NEF_SVC_TAG
    cmp x16, x2
    b.ne fatal_exception
    mov x2, #NEF_TPIDRRO_BASE
    add x2, x2, x0
    cmp x17, x2
    b.ne fatal_exception
    cmp x0, #1
    b.hi fatal_exception
    mov x19, x0
    cbnz x0, phase_one
    adr x0, phase_zero_message
    bl uart_puts
    /* First native-produced frame, with its real physical RAM address. */
    mov x2, #NEF_MMIO
    add x2, x2, #0x1000
    mov w3, #0xf5
    str w3, [x2, #0x34]
    mov w3, #1
    str w3, [x2, #0x200]
    ldr w3, =0x400040
    str w3, [x2, #0x21c]
    mov w3, #32
    str w3, [x2, #0x218]
    mov w3, #256
    str w3, [x2, #0x228]
    ldr w3, =(NEF_FRAME_PA >> 14)
    str w3, [x2, #0x210]
    mov w3, #NEF_FRAME_BYTES
    str w3, [x2, #0x214]
    b wait_parent
phase_one:
    adr x0, phase_one_message
    bl uart_puts
wait_parent:
    dsb sy
    ldr x2, =NEF_ACK_PA
    add w3, w19, #1
    /* Parent has a process-wide timeout; never inspect a GPU mapping here. */
4:  ldar w4, [x2]
    cmp w4, w3
    b.eq parent_done
    yield
    b 4b
parent_done:
    cbnz x19, complete
    mov x0, #1
    b enter_el0
complete:
    adr x0, success_message
    bl uart_puts
    ldr x0, =0x84000008
    hvc #0
    b fatal_early

fatal_exception:
    adr x0, failure_message
    bl uart_puts
fatal_early:
    msr daifset, #0xf
5:  wfi
    b 5b

uart_puts:
    mov x4, #0x09000000
6:  ldrb w5, [x0], #1
    cbz w5, 8f
7:  ldr w6, [x4, #0x18]
    tbnz w6, #5, 7b
    str w5, [x4]
    b 6b
8:  ret

.section .rodata,"a",%progbits
boot_message: .asciz "NATIVE_EFI_BOOT_EL1\n"
phase_zero_message: .asciz "NATIVE_EFI_PHASE_0_REGISTERS_OK\n"
phase_one_message: .asciz "NATIVE_EFI_PHASE_1_REGISTERS_OK\n"
success_message: .asciz "NATIVE_EFI_GUEST_COMPLETE\n"
failure_message: .asciz "NATIVE_EFI_GUEST_FAIL\n"

.section .payload,"ax",%progbits
.global native_efi_payload, native_efi_tpidrro, native_efi_svc
.type native_efi_payload,%function
native_efi_payload:
    movz x2, #1, lsl #32
    add x2, x2, #4, lsl #12
    mov w3, #0
row:
    mov w4, #0
pixel:
    lsr w5, w4, #3
    eor w5, w5, w0
    and w5, w5, #1
    neg w5, w5
    and w5, w5, #0xff
    lsr w6, w3, #3
    eor w6, w6, w0
    and w6, w6, #1
    neg w6, w6
    and w6, w6, #0xff
    orr w5, w5, w6, lsl #8
    lsr w6, w4, #4
    lsr w7, w3, #4
    eor w6, w6, w7
    eor w6, w6, w0
    and w6, w6, #1
    neg w6, w6
    and w6, w6, #0xff
    orr w5, w5, w6, lsl #16
    orr w5, w5, #0xff000000
    str w5, [x2], #4
    add w4, w4, #1
    cmp w4, #64
    b.lo pixel
    add w3, w3, #1
    cmp w3, #64
    b.lo row
native_efi_tpidrro:
    mrs x17, tpidrro_el0
    mov x16, #NEF_SVC_TAG
native_efi_svc:
    svc #0x80
    brk #0
.size native_efi_payload, .-native_efi_payload
.zero NEF_FRAME_BYTES - (. - native_efi_payload)

.section .bss.stack,"aw",%nobits
.balign 16384
el0_stack: .skip 16384
.section .bss.tables,"aw",%nobits
.balign 16384
table_l0: .skip 16384
table_l1: .skip 16384
table_l2: .skip 16384
table_l3_user: .skip 16384
.section .bss.kernel_stack,"aw",%nobits
.balign 16384
el1_stack: .skip 16384
el1_stack_top:
.section .note.GNU-stack,"",%progbits
