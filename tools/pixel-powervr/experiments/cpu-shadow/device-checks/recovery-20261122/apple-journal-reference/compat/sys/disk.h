#pragma once
#include <stdint.h>
#include <sys/ioctl.h>

/* The regular journal extract returns ENOTTY, enabling Apple's size fallback. */
#define DKIOCGETBLOCKSIZE _IOR('d', 24, uint32_t)
