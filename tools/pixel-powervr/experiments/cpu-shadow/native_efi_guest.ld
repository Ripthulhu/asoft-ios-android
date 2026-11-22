/* SPDX-License-Identifier: MIT */
OUTPUT_ARCH(aarch64)
ENTRY(_start)
PHDRS {
    boot PT_LOAD FLAGS(5);
    code PT_LOAD FLAGS(5);
    data PT_LOAD FLAGS(6);
}
SECTIONS {
    . = 0x40080000;
    .boot : { KEEP(*(.text.boot)) *(.text*) *(.rodata*) } :boot
    ASSERT(. <= 0x40084000, "EL1 boot exceeds reserved first 16KiB")
    . = 0x40084000;
    .payload : { KEEP(*(.payload)) } :code
    ASSERT(SIZEOF(.payload) == 16384, "code page must be exactly 16KiB")
    ASSERT(native_efi_tpidrro == 0x4008407c, "native witness PC changed")
    . = 0x40088000;
    __bss_start = .;
    .bss (NOLOAD) : {
        *(.bss.stack) *(.bss.tables) *(.bss.kernel_stack) *(.bss*) *(COMMON)
    } :data
    __bss_end = .;
    ASSERT((__bss_end & 16383) == 0, "BSS must end on a 16KiB boundary")
    ASSERT(__bss_end < 0x41000000, "setup memory must precede the framebuffer")
    /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
