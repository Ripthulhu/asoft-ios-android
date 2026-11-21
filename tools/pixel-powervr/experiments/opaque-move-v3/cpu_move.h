/* SPDX-License-Identifier: MIT
 * One-page CPU mapping experiment shared by the Android probe and memfd fixture.
 * The source is a DISPOSABLE full offset-zero mmap, never a Vulkan-owned pointer.
 * On mremap failure all cleanup is forbidden: a fixed destination may be gone.
 */
#ifndef PIXEL_CPU_MOVE_H
#define PIXEL_CPU_MOVE_H

#include "cpu_alias.h"

enum CpuMoveState {
    CPU_MOVE_EMPTY,
    CPU_MOVE_PREPARED,
    CPU_MOVE_MOVED,
    CPU_MOVE_UNCERTAIN
};

typedef struct CpuMoveInterval {
    void *address;
    size_t bytes;
} CpuMoveInterval;

typedef struct CpuMovePage {
    void *source_map, *slot;
    size_t page, bytes, offset;
    enum CpuMoveState state;
    /* Initially [0] is the full source. After success [0]/[1] are only the
     * surviving prefix/suffix. [2] is the separately reserved destination. */
    CpuMoveInterval owned[3];
} CpuMovePage;

#define CPU_MOVE_INITIALIZER { .source_map = MAP_FAILED, .slot = MAP_FAILED }

static inline int cpu_move_prepare(CpuMovePage *m, int fd, size_t page,
                                   size_t bytes, unsigned source_page)
{
    if (m->state != CPU_MOVE_EMPTY || m->source_map != MAP_FAILED ||
        m->slot != MAP_FAILED || page < sizeof(uint32_t) || page > 65536 ||
        (page & (page - 1)) || bytes != CPU_ALIAS_PAGES * page ||
        source_page >= CPU_ALIAS_PAGES) { errno = EINVAL; return -1; }
    m->page = page;
    m->bytes = bytes;
    m->offset = (size_t)source_page * page;
    m->source_map = mmap(NULL, bytes, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (m->source_map == MAP_FAILED) return -1;
    m->owned[0] = (CpuMoveInterval){m->source_map, bytes};
    m->state = CPU_MOVE_PREPARED;
    m->slot = mmap(NULL, page, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (m->slot == MAP_FAILED) return -1;
    m->owned[2] = (CpuMoveInterval){m->slot, page};
    return 0;
}

static inline int cpu_move_one_page(CpuMovePage *m)
{
    if (m->state != CPU_MOVE_PREPARED || m->source_map == MAP_FAILED ||
        m->slot == MAP_FAILED || !m->page || m->bytes < m->page ||
        m->offset > m->bytes - m->page || m->offset % m->page) {
        errno = EINVAL; return -1;
    }
    void *source_page = (unsigned char *)m->source_map + m->offset;
    /* A failing fixed move can already have unmapped the destination. Do not
     * infer ownership from errno or bulk-unmap either original range afterward. */
    m->state = CPU_MOVE_UNCERTAIN;
    void *got = mremap(source_page, m->page, m->page,
                       MREMAP_MAYMOVE | MREMAP_FIXED, m->slot);
    if (got == MAP_FAILED) return -1;
    if (got != m->slot) { errno = EFAULT; return -1; }
    m->owned[0] = (CpuMoveInterval){m->source_map, m->offset};
    m->owned[1] = (CpuMoveInterval){
        (unsigned char *)source_page + m->page,
        m->bytes - m->offset - m->page
    };
    m->state = CPU_MOVE_MOVED;
    return 0;
}

static inline int cpu_move_check_page(const CpuMovePage *m,
                                      const uint32_t *expected, const char *label)
{
    if (m->state != CPU_MOVE_MOVED) return 1;
    const volatile uint32_t *words = m->slot;
    size_t offset_words = m->offset / sizeof(*words);
    for (size_t i = 0; i < m->page / sizeof(*words); ++i) {
        uint32_t got = words[i], wanted = expected[offset_words + i];
        if (got != wanted) {
            printf("FAIL: %s source_page=%zu word=%zu got=0x%08x expected=0x%08x\n",
                   label, m->offset / m->page, i, got, wanted);
            return 1;
        }
    }
    printf("%s=PASS source_page=%zu checked_words=%zu\n", label,
           m->offset / m->page, m->page / sizeof(*words));
    return 0;
}

static inline int cpu_move_write_page(CpuMovePage *m, uint32_t seed)
{
    if (m->state != CPU_MOVE_MOVED) { errno = EINVAL; return -1; }
    volatile uint32_t *words = m->slot;
    for (size_t i = 0; i < m->page / sizeof(*words); ++i)
        words[i] = cpu_alias_pattern(0, (unsigned)(m->offset / m->page), i, seed);
    atomic_thread_fence(memory_order_seq_cst);
    return 0;
}

static inline int cpu_move_drop(CpuMovePage *m)
{
    if (m->state == CPU_MOVE_UNCERTAIN) { errno = EBUSY; return -1; }
    for (unsigned i = 0; i < 3; ++i) {
        CpuMoveInterval *range = &m->owned[i];
        if (!range->bytes) continue;
        if (munmap(range->address, range->bytes)) {
            /* Do not retry ranges after an unexpected cleanup error. */
            m->state = CPU_MOVE_UNCERTAIN;
            return -1;
        }
        *range = (CpuMoveInterval){MAP_FAILED, 0};
    }
    m->source_map = m->slot = MAP_FAILED;
    m->state = CPU_MOVE_EMPTY;
    return 0;
}

#endif
