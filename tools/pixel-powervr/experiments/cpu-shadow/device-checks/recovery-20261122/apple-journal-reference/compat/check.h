#pragma once
#include <stdint.h>

#ifndef __unused
#define __unused __attribute__((unused))
#endif

/* Suppress Apple diagnostic logs, which can include private block numbers. */
static const struct { int debug; } state = {0};
#define fsck_print(...) ((void)0)
