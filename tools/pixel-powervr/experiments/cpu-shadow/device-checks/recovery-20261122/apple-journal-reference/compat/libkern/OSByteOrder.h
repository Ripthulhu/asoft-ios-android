#pragma once
#define OSSwapInt16(value) __builtin_bswap16(value)
#define OSSwapInt32(value) __builtin_bswap32(value)
#define OSSwapInt64(value) __builtin_bswap64(value)
