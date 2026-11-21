/* SPDX-License-Identifier: MIT
 * Required CPU data-access preflight on our own bounded producer aliases.
 * Included after NaAlias and the full-view checker in native_code_cache.h.
 * This establishes only the individual operations below, not a memory-attribute
 * diagnosis, cross-core atomicity, or reims's unaligned atomic contracts.
 */
#ifndef PIXEL_NATIVE_CPU_MEMORY_H
#define PIXEL_NATIVE_CPU_MEMORY_H

#if defined(__aarch64__)
#include <sys/auxv.h>
#include <asm/hwcap.h>

/* Target only these called-after-HWCAP-check functions, not the whole program. */
__attribute__((target("lse"), noinline))
static uint64_t na_memory_set64(void *address, uint64_t bits)
{
    uint64_t old;
    __asm__ __volatile__("ldsetal %x[bits], %x[old], [%x[address]]"
                         : [old] "=&r" (old)
                         : [bits] "r" (bits), [address] "r" (address) : "memory");
    return old;
}

__attribute__((target("lse"), noinline))
static uint64_t na_memory_clear64(void *address, uint64_t bits)
{
    uint64_t old;
    __asm__ __volatile__("ldclral %x[bits], %x[old], [%x[address]]"
                         : [old] "=&r" (old)
                         : [bits] "r" (bits), [address] "r" (address) : "memory");
    return old;
}

static uint64_t na_memory_load64(const void *address)
{
    uint64_t value;
    __asm__ __volatile__("ldr %x[value], [%x[address]]"
                         : [value] "=r" (value) : [address] "r" (address) : "memory");
    return value;
}

static void na_memory_store64(void *address, uint64_t value)
{
    __asm__ __volatile__("str %x[value], [%x[address]]"
                         : : [value] "r" (value), [address] "r" (address) : "memory");
}

static int na_memory_capabilities(void)
{
    unsigned long caps = getauxval(AT_HWCAP), caps2 = getauxval(AT_HWCAP2);
    const unsigned long required = HWCAP_ATOMICS | HWCAP_LRCPC | HWCAP_USCAT;
    printf("NATIVE_CPU_HWCAP=0x%lx HWCAP2=0x%lx ATOMICS=%u LRCPC=%u USCAT=%u required_mask=0x%lx\n",
           caps, caps2, !!(caps & HWCAP_ATOMICS), !!(caps & HWCAP_LRCPC),
           !!(caps & HWCAP_USCAT), required);
    if ((caps & required) != required) {
        puts("NATIVE_CPU_MEMORY_PREFLIGHT=UNSUPPORTED required_AArch64_features_missing; no_preflight_writes=yes");
        return NA_UNSUPPORTED;
    }
    return 0;
}

#elif defined(NA_HOST_FIXTURE) && defined(__x86_64__)

static uint64_t na_memory_set64(void *address, uint64_t bits)
{
    return __atomic_fetch_or((uint64_t *)address, bits, __ATOMIC_SEQ_CST);
}

static uint64_t na_memory_clear64(void *address, uint64_t bits)
{
    return __atomic_fetch_and((uint64_t *)address, ~bits, __ATOMIC_SEQ_CST);
}

static uint64_t na_memory_load64(const void *address)
{
    uint64_t value;
    __asm__ __volatile__("movq (%[address]), %[value]"
                         : [value] "=r" (value) : [address] "r" (address) : "memory");
    return value;
}

static void na_memory_store64(void *address, uint64_t value)
{
    __asm__ __volatile__("movq %[value], (%[address])"
                         : : [value] "r" (value), [address] "r" (address) : "memory");
}

static int na_memory_capabilities(void)
{
    puts("NATIVE_CPU_HWCAP=HOST_FIXTURE architecture=x86_64 AArch64_features_tested=no");
    return 0;
}
#else
#error The CPU memory preflight requires AArch64 or the labelled x86-64 host fixture.
#endif

/* Chosen bytes lie within one aligned 16-byte granule in the selected interval,
 * well away from its ends. The two tests restore exactly their original bytes.
 * Mark dirty before each modifying instruction; a fault with that mark exits
 * immediately, and a child reply carrying it prohibits parent GPU work. */
static int na_memory_preflight(const NaAlias *a, const NaAlias *b, const void *canonical,
                                const uint32_t expected[NA_BYTES / sizeof(uint32_t)])
{
    enum { LOCAL_OFFSET = 64, UNALIGNED_SHIFT = 4 };
    uint32_t changed[NA_BYTES / sizeof(uint32_t)];
    const size_t absolute = NA_OFFSET + LOCAL_OFFSET;
    unsigned char *aligned = (unsigned char *)a->slot + LOCAL_OFFSET;
    unsigned char *unaligned = aligned + UNALIGNED_SHIFT;
    uint64_t original, bits, observed, cleared;
    int bad = 0, result = na_memory_capabilities();
    if (result) return result;
    if ((uintptr_t)aligned % 16 || (uintptr_t)unaligned % 16 != 4) return 1;
    memcpy(&original, (const unsigned char *)expected + absolute, sizeof(original));
    bits = ~original;
    bits &= ~bits + 1; /* one originally clear bit, never a destructive all-bit fill */
    if (!bits) { puts("FAIL: preflight has no clear bit in its deterministic input"); return 1; }
    memcpy(changed, expected, sizeof(changed));
    uint64_t modified = original | bits;
    memcpy((unsigned char *)changed + absolute, &modified, sizeof(modified));
    if (na_arm_limit(NA_CALL_MS)) { puts("FAIL: cannot arm memory preflight deadline"); return 1; }
    na_memory_phase = 1;
    puts("NATIVE_CPU_MEMORY_PHASE=aligned_atomic_set_clear bits=64 limit_ms=5000");
    na_memory_state = NA_MEMORY_DIRTY;
    observed = na_memory_set64(aligned, bits);
    atomic_thread_fence(memory_order_seq_cst);
    if (observed != original) bad = 1;
    if (na_check_views(a, b, canonical, changed, "aligned atomic set and all guard pages")) bad = 1;
    cleared = na_memory_clear64(aligned, bits);
    atomic_thread_fence(memory_order_seq_cst);
    if (cleared != modified) bad = 1;
    if (na_check_views(a, b, canonical, expected, "aligned atomic restore and all guard pages")) {
        puts("FAIL: atomic preflight restoration not verified; later work prohibited");
        return 1;
    }
    na_memory_state = NA_MEMORY_RESTORED;
    if (bad) { puts("FAIL: aligned atomic returned unexpected data despite restoration"); return 1; }
    puts("NATIVE_CPU_ALIGNED_ATOMIC=PASS set_then_clear=yes bytes_restored=yes aliases_and_all_pages_checked=yes cross_core_atomicity_tested=no");

    /* Exactly one ordinary load/store, not C's possibly split unaligned access.
     * This does not execute or qualify an unaligned atomic instruction. */
    na_memory_phase = 2;
    puts("NATIVE_CPU_MEMORY_PHASE=unaligned_load_store bits=64 offset_within_16byte_granule=4 limit_ms=5000");
    memcpy(&original, (const unsigned char *)expected + absolute + UNALIGNED_SHIFT, sizeof(original));
    observed = na_memory_load64(unaligned);
    if (observed != original) { puts("FAIL: unaligned read differs before modification"); return 1; }
    modified = original ^ UINT64_C(0x0102030405060708);
    memcpy(changed, expected, sizeof(changed));
    memcpy((unsigned char *)changed + absolute + UNALIGNED_SHIFT, &modified, sizeof(modified));
    na_memory_state = NA_MEMORY_DIRTY;
    na_memory_store64(unaligned, modified);
    atomic_thread_fence(memory_order_seq_cst);
    if (na_memory_load64(unaligned) != modified) bad = 1;
    if (na_check_views(a, b, canonical, changed, "unaligned store and all guard pages")) bad = 1;
    na_memory_store64(unaligned, original);
    atomic_thread_fence(memory_order_seq_cst);
    if (na_check_views(a, b, canonical, expected, "unaligned restore and all guard pages")) {
        puts("FAIL: unaligned preflight restoration not verified; later work prohibited");
        return 1;
    }
    na_memory_state = NA_MEMORY_RESTORED;
    if (bad) { puts("FAIL: unaligned access returned unexpected data despite restoration"); return 1; }
    na_memory_state = NA_MEMORY_PASSED;
    na_memory_phase = 0;
    if (na_arm_limit(0)) { puts("FAIL: cannot restore remaining process deadline after preflight"); return 1; }
    puts("NATIVE_CPU_MEMORY_PREFLIGHT=PASS individual_aligned_atomic_and_unaligned64_operations=yes all_bytes_restored=yes Normal_memory_attributes_proven=no unaligned_atomicity_proven=no cache_performance_measured=no");
    return 0;
}

#endif
