/* SPDX-License-Identifier: MIT
 * One CPU, EL1 setup in ordinary memfd RAM, ten fixed scalar EL0 instructions.
 * No IRQ source, EL0 syscall other than the completion SVC, or atomic payload.
 */
#include "native_gpu_protocol.h"

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
    adrp x0, boot_message
    add x0, x0, :lo12:boot_message
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

    /* Identity map the 512 MiB memfd as 16 EL1-only 32 MiB blocks.
     * UXN=1, PXN=0, AP=EL1 RW, AF=1, SH=inner, Attr0=Normal WB. */
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

    /* PL011 0x09000000 in the EL1-only Device block at 0x08000000. */
    mov x3, #0x08000000
    mov x4, #0x705
    orr x3, x3, x4
    mov x4, #0x60000000000000
    orr x3, x3, x4
    str x3, [x2, #(4 * 8)]

    adrp x3, table_l3_user
    add x3, x3, :lo12:table_l3_user
    orr x4, x3, #3
    str x4, [x2, #(128 * 8)]

    /* Code leaf: EL0 RX, EL1 NX, ordinary memfd physical code page. */
    ldr x4, =NGP_CODE_PA
    mov x5, #0x7c3
    orr x4, x4, x5
    mov x5, #0x20000000000000
    orr x4, x4, x5
    str x4, [x3, #0]

    /* Producer data leaf: EL0 RW, both execution-never bits set. */
    mov x4, #NGP_GPA
    mov x5, #0x743
    orr x4, x4, x5
    mov x5, #0x60000000000000
    orr x4, x4, x5
    str x4, [x3, #8]

    /* EL0 stack is another ordinary memfd page, never producer storage. */
    adrp x4, el0_stack
    add x4, x4, :lo12:el0_stack
    mov x5, #0x743
    orr x4, x4, x5
    mov x5, #0x60000000000000
    orr x4, x4, x5
    str x4, [x3, #16]

    mov x1, #0xff
    msr mair_el1, x1
    /* T0SZ16, WB/WA walks, inner shareable, TG0=16KiB, EPD1=1, IPS32. */
    ldr x1, =0x80b510
    msr tcr_el1, x1
    msr ttbr0_el1, x0
    msr ttbr1_el1, xzr
    /* The native engine requires FPEN even for an integer-only payload.
     * Leave SVE disabled; this proof never executes FP/SIMD instructions. */
    mov x1, #0x300000
    msr cpacr_el1, x1
    dsb sy
    tlbi vmalle1
    dsb sy
    isb
    ldr x1, =0x30d01805
    msr sctlr_el1, x1
    isb

    ldr x0, =(NGP_STACK_VA + NGP_VIEW_BYTES)
    msr sp_el0, x0
    ldr x0, =NGP_CODE_VA
    msr elr_el1, x0
    mov x0, #0x3c0
    msr spsr_el1, x0
    msr tpidr_el0, xzr
    msr tpidrro_el0, xzr
    mov x0, #0
    mov x1, #0
    mov x2, #0
    mov x16, #0
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
    cmp x2, #NGP_SVC_IMMEDIATE
    b.ne fatal_exception
    mrs x2, elr_el1
    ldr x3, =NGP_COMPLETE_PC
    cmp x2, x3
    b.ne fatal_exception
    mov x2, #NGP_SVC_TAG
    cmp x16, x2
    b.ne fatal_exception
    ldr x2, =0x6a1b2c346a1b2c34
    cmp x0, x2
    b.ne fatal_exception
    ldr x2, =0x615c5026615c515d
    cmp x1, x2
    b.ne fatal_exception
    adrp x0, success_message
    add x0, x0, :lo12:success_message
    bl uart_puts
    ldr x0, =0x84000008
    hvc #0
    b fatal_early

fatal_exception:
    adrp x0, failure_message
    add x0, x0, :lo12:failure_message
    bl uart_puts
fatal_early:
    msr daifset, #0xf
4:  wfi
    b 4b

uart_puts:
    mov x4, #0x09000000
5:  ldrb w5, [x0], #1
    cbz w5, 7f
6:  ldr w6, [x4, #0x18]
    tbnz w6, #5, 6b
    str w5, [x4]
    b 5b
7:  ret

.section .rodata,"a",%progbits
boot_message: .asciz "NATIVE_GPU_GUEST_BOOT_EL1\n"
success_message: .asciz "NATIVE_GPU_GUEST_SVC_OK\n"
failure_message: .asciz "NATIVE_GPU_GUEST_FAIL\n"

.section .payload,"ax",%progbits
.global native_gpu_payload, native_gpu_payload_end, native_gpu_code_page_end
.type native_gpu_payload,%function
native_gpu_payload:
    movz x2, #1, lsl #32
    add x2, x2, #4, lsl #12
    ldr x0, [x2]
    ror x1, x0, #13
    eor x1, x1, #NGP_XOR_MASK
    add x1, x1, #NGP_ADDEND
    str x1, [x2, #8]
    movz x16, #NGP_SVC_TAG
    svc #NGP_SVC_IMMEDIATE
    brk #0
native_gpu_payload_end:
.size native_gpu_payload, .-native_gpu_payload
/* Explicit zero padding: executable-section alignment may otherwise use NOP. */
.zero NGP_VIEW_BYTES - (. - native_gpu_payload)
native_gpu_code_page_end:

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
