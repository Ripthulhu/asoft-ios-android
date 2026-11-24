.text
.global _start
_start:
    mrs x2, CurrentEL
    cmp x2, #4
    b.ne failure
    movz x0, #0xff00
    movk x0, #0x8600, lsl #16
    mov x1, #0x1111
    hvc #0

    mov x2, #0x2a
    cmp x0, x2
    b.ne failure
    movz x3, #0x4001, lsl #16
    mov x4, #0x1234
    str x4, [x3]
    ldr x5, [x3]
    cmp x4, x5
    b.ne failure
    mov x1, #0x2222
    b done

failure:
    mov x1, #0xdead
done:
    movz x0, #0xff00
    movk x0, #0x8600, lsl #16
    hvc #0
1:  wfe
    b 1b
