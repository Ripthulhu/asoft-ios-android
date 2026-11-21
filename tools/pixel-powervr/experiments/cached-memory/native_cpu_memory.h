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
    ++na_atomic_calls;
    uint64_t old;
    __asm__ __volatile__("ldsetal %x[bits], %x[old], [%x[address]]"
                         : [old] "=&r" (old)
                         : [bits] "r" (bits), [address] "r" (address) : "memory");
    return old;
}

__attribute__((target("lse"), noinline))
static uint64_t na_memory_clear64(void *address, uint64_t bits)
{
    ++na_atomic_calls;
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
    if (na_cpu_atomics && (caps & required) != required) {
        puts("NATIVE_CPU_MEMORY_PREFLIGHT=UNSUPPORTED required_AArch64_features_missing; no_preflight_writes=yes");
        return NA_UNSUPPORTED;
    }
    return 0;
}

#elif defined(NA_HOST_FIXTURE) && defined(__x86_64__)

static uint64_t na_memory_set64(void *address, uint64_t bits)
{
    ++na_atomic_calls;
    return __atomic_fetch_or((uint64_t *)address, bits, __ATOMIC_SEQ_CST);
}

static uint64_t na_memory_clear64(void *address, uint64_t bits)
{
    ++na_atomic_calls;
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
    na_atomic_calls = 0;
    if (na_arm_limit(NA_CALL_MS)) { puts("FAIL: cannot arm memory preflight deadline"); return 1; }

    /* Start with ordinary accesses. The producer's LSE phase is an explicit
     * separate option and comes after these fully restored transactions. */
    na_memory_phase = 1;
    puts("CACHED_CPU_MEMORY_PHASE=aligned_load_store bits=64 alignment=16");
    memcpy(&original, (const unsigned char *)expected + absolute, sizeof(original));
    if (na_checkpoint("before_aligned_load")) return 1;
    observed = na_memory_load64(aligned);
    if (observed != original) { puts("FAIL: aligned read differs before modification"); return 1; }
    uint64_t modified = original ^ UINT64_C(0x0102030405060708);
    memcpy(changed, expected, sizeof(changed));
    memcpy((unsigned char *)changed + absolute, &modified, sizeof(modified));
    na_memory_state = NA_MEMORY_DIRTY;
    if (na_checkpoint("before_aligned_store")) return 1;
    na_memory_store64(aligned, modified);
    atomic_thread_fence(memory_order_seq_cst);
    if (na_memory_load64(aligned) != modified) bad = 1;
    if (na_check_views(a, b, canonical, changed, "aligned store and all guard pages")) bad = 1;
    na_memory_store64(aligned, original);
    atomic_thread_fence(memory_order_seq_cst);
    if (na_check_views(a, b, canonical, expected, "aligned restore and all guard pages")) {
        puts("FAIL: aligned preflight restoration not verified; later work prohibited");
        return 1;
    }
    na_memory_state = NA_MEMORY_RESTORED;
    if (bad) { puts("FAIL: aligned access returned unexpected data despite restoration"); return 1; }
    puts("CACHED_CPU_ALIGNED_LOAD_STORE=PASS all_bytes_restored=yes");

    /* Exactly one ordinary load/store, not C's possibly split unaligned access.
     * This does not execute or qualify an unaligned atomic instruction. */
    na_memory_phase = 2;
    puts("NATIVE_CPU_MEMORY_PHASE=unaligned_load_store bits=64 offset_within_16byte_granule=4 limit_ms=5000");
    memcpy(&original, (const unsigned char *)expected + absolute + UNALIGNED_SHIFT, sizeof(original));
    if (na_checkpoint("before_unaligned_load")) return 1;
    observed = na_memory_load64(unaligned);
    if (observed != original) { puts("FAIL: unaligned read differs before modification"); return 1; }
    modified = original ^ UINT64_C(0x0102030405060708);
    memcpy(changed, expected, sizeof(changed));
    memcpy((unsigned char *)changed + absolute + UNALIGNED_SHIFT, &modified, sizeof(modified));
    na_memory_state = NA_MEMORY_DIRTY;
    if (na_checkpoint("before_unaligned_store")) return 1;
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
    puts("CACHED_CPU_UNALIGNED_LOAD_STORE=PASS all_bytes_restored=yes unaligned_atomicity_proven=no");

    if (na_cpu_atomics) {
        na_memory_phase = 3;
        memcpy(&original, (const unsigned char *)expected + absolute, sizeof(original));
        bits = ~original;
        bits &= ~bits + 1;
        if (!bits) { puts("FAIL: atomic input has no clear bit"); return 1; }
        modified = original | bits;
        memcpy(changed, expected, sizeof(changed));
        memcpy((unsigned char *)changed + absolute, &modified, sizeof(modified));
        na_memory_state = NA_MEMORY_DIRTY;
        if (na_checkpoint("before_opt_in_aligned_ldsetal")) return 1;
        observed = na_memory_set64(aligned, bits);
        atomic_thread_fence(memory_order_seq_cst);
        if (observed != original) bad = 1;
        if (na_check_views(a, b, canonical, changed, "opt-in aligned atomic set and all guards")) bad = 1;
        if (na_checkpoint("before_opt_in_aligned_ldclral")) return 1;
        cleared = na_memory_clear64(aligned, bits);
        atomic_thread_fence(memory_order_seq_cst);
        if (cleared != modified) bad = 1;
        if (na_check_views(a, b, canonical, expected, "opt-in atomic restore and all guards")) {
            puts("FAIL: atomic restoration not verified; later work prohibited"); return 1;
        }
        na_memory_state = NA_MEMORY_RESTORED;
        if (bad || na_atomic_calls != 2) { puts("FAIL: aligned atomic result or call count"); return 1; }
        puts("CACHED_CPU_ALIGNED_ATOMIC=PASS calls=2 set_then_clear=yes bytes_restored=yes cross_core_atomicity_tested=no");
    } else {
        if (na_atomic_calls) { puts("FAIL: producer atomic executed without opt-in"); return 1; }
        puts("CACHED_CPU_ALIGNED_ATOMIC=NOT_TESTED calls=0 explicit_cpu_atomics_option_required=yes");
    }
    na_memory_state = NA_MEMORY_PASSED;
    na_memory_phase = 0;
    if (na_arm_limit(0)) { puts("FAIL: cannot restore remaining process deadline after preflight"); return 1; }
    printf("CACHED_CPU_MEMORY_PREFLIGHT=PASS aligned_and_unaligned64=yes cpu_atomics=%u atomic_calls=%u all_bytes_restored=yes Normal_memory_attributes_proven=no unaligned_atomicity_proven=no cache_performance_measured=no\n", na_cpu_atomics, na_atomic_calls);
    if (na_checkpoint("CPU_memory_preflight_restored")) return 1;
    return 0;
}

#endif
