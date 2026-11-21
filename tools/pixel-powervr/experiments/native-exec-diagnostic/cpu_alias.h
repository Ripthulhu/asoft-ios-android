/* SPDX-License-Identifier: MIT
 * CPU-only native aliases shared by the Android probe and ordinary-memfd
 * fixture. MAP_FIXED is restricted to slots inside a live owned reservation.
 */
#ifndef PIXEL_CPU_ALIAS_H
#define PIXEL_CPU_ALIAS_H

#include <errno.h>
#include <stdatomic.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/mman.h>

enum { CPU_ALIAS_SLOTS = 4, CPU_ALIAS_PAGES = 8 };

typedef struct CpuAliases {
    void *base;
    size_t page, source_bytes;
    unsigned source_page[CPU_ALIAS_SLOTS];
    unsigned mapped[CPU_ALIAS_SLOTS];
} CpuAliases;

static inline int cpu_alias_reserve(CpuAliases *a, size_t page, size_t source_bytes)
{
    if (a->base != MAP_FAILED || !page || page > 65536 || (page & (page - 1)) ||
        page > SIZE_MAX / CPU_ALIAS_SLOTS || source_bytes < CPU_ALIAS_PAGES * page ||
        source_bytes % page) { errno = EINVAL; return -1; }
    a->page = page;
    a->source_bytes = source_bytes;
    a->base = mmap(NULL, CPU_ALIAS_SLOTS * page, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    return a->base == MAP_FAILED ? -1 : 0;
}

static inline int cpu_alias_map_slot(CpuAliases *a, int fd, unsigned slot, unsigned source_page)
{
    if (a->base == MAP_FAILED || !a->page || slot >= CPU_ALIAS_SLOTS ||
        source_page >= a->source_bytes / a->page) { errno = EINVAL; return -1; }
    size_t offset = (size_t)source_page * a->page;
    off_t file_offset = (off_t)offset;
    if (file_offset < 0 || (uintmax_t)file_offset != (uintmax_t)offset) { errno = EOVERFLOW; return -1; }
    void *target = (unsigned char *)a->base + (size_t)slot * a->page;
    void *got = mmap(target, a->page, PROT_READ | PROT_WRITE, MAP_SHARED | MAP_FIXED, fd, file_offset);
    if (got == MAP_FAILED) return -1;
    if (got != target) { munmap(got, a->page); errno = EFAULT; return -1; }
    a->source_page[slot] = source_page;
    a->mapped[slot] = 1;
    return 0;
}

static inline int cpu_alias_drop(CpuAliases *a)
{
    int result = 0;
    if (a->base != MAP_FAILED) result = munmap(a->base, CPU_ALIAS_SLOTS * a->page);
    if (!result) {
        a->base = MAP_FAILED;
        for (unsigned i = 0; i < CPU_ALIAS_SLOTS; ++i) a->mapped[i] = 0;
    }
    return result;
}

static inline int cpu_alias_setup(CpuAliases *a, int fd, size_t page, size_t source_bytes)
{
    static const unsigned order[CPU_ALIAS_SLOTS] = {5, 0, 7, 2};
    if (cpu_alias_reserve(a, page, source_bytes)) return -1;
    for (unsigned i = 0; i < CPU_ALIAS_SLOTS; ++i) {
        if (cpu_alias_map_slot(a, fd, i, order[i])) {
            int saved = errno;
            cpu_alias_drop(a);
            errno = saved;
            return -1;
        }
    }
    return 0;
}

static inline uint32_t cpu_alias_pattern(unsigned slot, unsigned page, size_t word, uint32_t seed)
{
    /* At most 64 KiB pages: word occupies bits0..13, slot16..17, page20..22. */
    return seed ^ ((uint32_t)page << 20) ^ ((uint32_t)slot << 16) ^ (uint32_t)word;
}

static inline int cpu_alias_write_slot(CpuAliases *a, unsigned slot, uint32_t seed)
{
    if (a->base == MAP_FAILED || slot >= CPU_ALIAS_SLOTS || !a->mapped[slot]) { errno = EINVAL; return -1; }
    volatile uint32_t *words = (volatile uint32_t *)((unsigned char *)a->base + (size_t)slot * a->page);
    for (size_t i = 0; i < a->page / sizeof(*words); ++i)
        words[i] = cpu_alias_pattern(slot, a->source_page[slot], i, seed);
    atomic_thread_fence(memory_order_seq_cst);
    return 0;
}

static inline void cpu_alias_expected_fill(uint32_t *expected, size_t page, uint32_t base)
{
    size_t words = page / sizeof(*expected);
    for (unsigned p = 0; p < CPU_ALIAS_PAGES; ++p)
        for (size_t i = 0; i < words; ++i) expected[(size_t)p * words + i] = base + p;
}

static inline void cpu_alias_expected_slot(uint32_t *expected, size_t page, unsigned slot, unsigned source_page, uint32_t seed)
{
    size_t words = page / sizeof(*expected);
    for (size_t i = 0; i < words; ++i)
        expected[(size_t)source_page * words + i] = cpu_alias_pattern(slot, source_page, i, seed);
}

static inline int cpu_alias_check_full(const void *mapping, const uint32_t *expected, size_t bytes, const char *label)
{
    const volatile uint32_t *words = mapping;
    for (size_t i = 0; i < bytes / sizeof(*words); ++i) {
        uint32_t got = words[i];
        if (got != expected[i]) {
            printf("FAIL: %s word=%zu got=0x%08x expected=0x%08x\n", label, i, got, expected[i]);
            return 1;
        }
    }
    printf("%s=PASS checked_words=%zu including_unselected_pages=yes\n", label, bytes / sizeof(*words));
    return 0;
}

static inline int cpu_alias_check_slots(const CpuAliases *a, const uint32_t *expected, const char *label)
{
    if (a->base == MAP_FAILED) return 1;
    size_t words = a->page / sizeof(*expected);
    for (unsigned slot = 0; slot < CPU_ALIAS_SLOTS; ++slot) {
        if (!a->mapped[slot]) return 1;
        const volatile uint32_t *actual = (const volatile uint32_t *)((const unsigned char *)a->base + (size_t)slot * a->page);
        for (size_t i = 0; i < words; ++i) {
            uint32_t got = actual[i], wanted = expected[(size_t)a->source_page[slot] * words + i];
            if (got != wanted) {
                printf("FAIL: %s slot=%u source_page=%u word=%zu got=0x%08x expected=0x%08x\n", label, slot, a->source_page[slot], i, got, wanted);
                return 1;
            }
        }
    }
    printf("%s=PASS checked_words=%zu order=%u,%u,%u,%u\n", label, CPU_ALIAS_SLOTS * words,
           a->source_page[0], a->source_page[1], a->source_page[2], a->source_page[3]);
    return 0;
}

#endif
