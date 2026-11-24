.text
.global _start
_start:
    mrs     x3, CurrentEL
    cmp     x3, #4
    b.ne    fail

    /* Leave architectural faults in the guest to observe the missing Apple operations. */
    adr     x3, vectors
    msr     vbar_el1, x3
    isb
    mov     x10, #0
    mrs     x4, S3_6_C15_C8_1
    .inst   0x00201420
    cmp     x10, #2
    b.ne    fail

    movz    x5, #0x4010, lsl #16
    msr     ttbr0_el1, x5
    mov     x5, #0xff00
    msr     mair_el1, x5
    movz    x5, #0xb51c
    movk    x5, #0x8080, lsl #16
    msr     tcr_el1, x5
    isb
    tlbi    vmalle1
    dsb     sy
    isb
    mrs     x5, sctlr_el1
    orr     x5, x5, #1
    msr     sctlr_el1, x5
    isb

    mov     x8, #0x42000000
    at      s1e1r, x8
    isb
    mrs     x9, par_el1
    tbnz    x9, #0, fail
    at      s1e1w, x8
    isb
    mrs     x9, par_el1
    tbz     x9, #0, fail
    mov     x1, #1
    bl      call_host

    tlbi    vmalle1
    dsb     sy
    isb
    at      s1e1w, x8
    isb
    mrs     x9, par_el1
    tbnz    x9, #0, fail
    mov     x3, #0x1234
    str     x3, [x8]
    mov     x1, #2
    bl      call_host

    tlbi    vmalle1
    dsb     sy
    isb
    at      s1e1w, x8
    isb
    mrs     x9, par_el1
    tbz     x9, #0, fail
    ldr     x4, [x8]
    cmp     x4, x3
    b.ne    fail
    mov     x1, #3
    bl      call_host
fail:
    mov     x1, #0xffff
    bl      call_host
1:  wfe
    b       1b

call_host:
    movz    x0, #0xff00
    movk    x0, #0x8600, lsl #16
    hvc     #0
    ret

unknown:
    mrs     x11, esr_el1
    lsr     x11, x11, #26
    cbnz    x11, fail
    mrs     x11, elr_el1
    add     x11, x11, #4
    msr     elr_el1, x11
    add     x10, x10, #1
    eret

.balign 2048
vectors:
    .space  0x200
    b       unknown
