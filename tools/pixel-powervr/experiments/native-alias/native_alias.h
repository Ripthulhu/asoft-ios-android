/* SPDX-License-Identifier: MIT
 * Bounded CPU contract shared by the Vulkan probe and ordinary-memfd fixture.
 * Only disposable full offset-zero maps are moved. No Vulkan pointer is moved.
 */
#ifndef PIXEL_NATIVE_ALIAS_H
#define PIXEL_NATIVE_ALIAS_H

#include "cpu_alias.h"
#include <inttypes.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

enum { NA_HOST_PAGE = 4096, NA_BYTES = 32768, NA_SPAN = 16384,
       NA_OFFSET = 16384, NA_UNSUPPORTED = 6, NA_PROTOCOL = 1 };
#define NA_MAGIC UINT32_C(0x4e413031)
#define NA_SEED_A UINT32_C(0xb1250000)
#define NA_SEED_B UINT32_C(0xc9360000)

/* Stage is set before a write. Verified is advanced only after every CPU view
 * agrees, so a capability refusal after writes cannot conceal partial data. */
enum NaStage { NA_INITIAL, NA_PATTERN_A, NA_PATTERN_B, NA_CODE };
typedef struct NaReply {
    uint32_t magic, protocol, status, stage, verified_stage, reserved;
} NaReply;

static volatile sig_atomic_t na_stage, na_verified_stage, na_exec_phase;
static volatile sig_atomic_t na_reply_fd = -1, na_active_child;

static void na_write_reply_signal(int status)
{
    if (na_reply_fd >= 0) {
        NaReply r = {NA_MAGIC, NA_PROTOCOL, (uint32_t)status,
                     (uint32_t)na_stage, (uint32_t)na_verified_stage, 0};
        (void)write((int)na_reply_fd, &r, sizeof(r));
    }
}

static void na_fatal_signal(int number)
{
    int result = number == SIGALRM || number == SIGTERM || number == SIGINT
                 ? 1 : na_exec_phase || na_stage == NA_INITIAL ? NA_UNSUPPORTED : 1;
    if (na_active_child > 0) (void)kill((pid_t)na_active_child, SIGKILL);
    if (result == NA_UNSUPPORTED) {
        static const char msg[] = "NATIVE_ALIAS=UNSUPPORTED signal during pre-write mapping or verified-code execution; stopping\nRESULT=VULKAN_FD_MMAP_PASS_NATIVE_ALIAS_UNSUPPORTED\n";
        (void)write(STDERR_FILENO, msg, sizeof(msg) - 1);
    } else {
        static const char msg[] = "NATIVE_ALIAS=FAIL signal after data writes or bounded deadline/interruption; stopping\nRESULT=FAIL\n";
        (void)write(STDERR_FILENO, msg, sizeof(msg) - 1);
    }
    na_write_reply_signal(result);
    _Exit(result);
}

static int na_watchdog(unsigned seconds)
{
    struct sigaction a = {0};
    a.sa_handler = na_fatal_signal;
    sigemptyset(&a.sa_mask);
    if (sigaction(SIGALRM, &a, NULL) || sigaction(SIGTERM, &a, NULL) ||
        sigaction(SIGINT, &a, NULL)) return 1;
    a.sa_handler = SIG_IGN;
    if (sigaction(SIGPIPE, &a, NULL)) return 1;
    alarm(seconds);
    return 0;
}

static void na_uncertain_exit(const char *why, int result)
{
    printf("NATIVE_ALIAS_UNCERTAIN=%s errno=%d message=%s cleanup=process_exit_only\n",
           why, errno, strerror(errno));
    puts(result == NA_UNSUPPORTED ? "RESULT=VULKAN_FD_MMAP_PASS_NATIVE_ALIAS_UNSUPPORTED" : "RESULT=FAIL");
    na_write_reply_signal(result);
    fflush(NULL);
    _Exit(result);
}

typedef struct NaInterval { void *address; size_t bytes; } NaInterval;
typedef struct NaAlias {
    void *source, *slot;
    NaInterval source_prefix, source_suffix, reservation;
    int moved, uncertain;
} NaAlias;
#define NA_ALIAS_INIT { .source = MAP_FAILED, .slot = MAP_FAILED }

static int na_alias_prepare(NaAlias *a, int fd)
{
    if (a->source != MAP_FAILED || a->slot != MAP_FAILED || a->uncertain) {
        errno = EINVAL; return -1;
    }
    a->source = mmap(NULL, NA_BYTES, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (a->source == MAP_FAILED) return -1;
    a->source_prefix = (NaInterval){a->source, NA_BYTES};
    /* Retain the whole anonymous reservation. The middle aligned span changes
     * backing after mremap; both anonymous guards remain owned throughout. */
    void *r = mmap(NULL, 2 * NA_SPAN, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (r == MAP_FAILED) return -1;
    a->reservation = (NaInterval){r, 2 * NA_SPAN};
    uintptr_t aligned = ((uintptr_t)r + NA_SPAN - 1) & ~(uintptr_t)(NA_SPAN - 1);
    a->slot = (void *)aligned;
    if (aligned < (uintptr_t)r || aligned + NA_SPAN > (uintptr_t)r + 2 * NA_SPAN) {
        errno = EOVERFLOW; return -1;
    }
    return 0;
}

static int na_alias_move(NaAlias *a)
{
    if (a->source == MAP_FAILED || a->slot == MAP_FAILED || a->moved || a->uncertain ||
        (uintptr_t)a->slot % NA_SPAN) { errno = EINVAL; return -1; }
    a->uncertain = 1; /* A failing fixed move may already remove its destination. */
    void *got = mremap((unsigned char *)a->source + NA_OFFSET, NA_SPAN, NA_SPAN,
                        MREMAP_MAYMOVE | MREMAP_FIXED, a->slot);
    if (got == MAP_FAILED) return -1;
    if (got != a->slot) { errno = EFAULT; return -1; }
    a->source_prefix = (NaInterval){a->source, NA_OFFSET};
    a->source_suffix = (NaInterval){(unsigned char *)a->source + NA_OFFSET + NA_SPAN,
                                   NA_BYTES - NA_OFFSET - NA_SPAN};
    a->moved = 1;
    a->uncertain = 0;
    return 0;
}

static int na_alias_drop(NaAlias *a)
{
    if (a->uncertain) { errno = EBUSY; return -1; }
    NaInterval *ranges[] = {&a->source_prefix, &a->source_suffix, &a->reservation};
    for (unsigned i = 0; i < sizeof(ranges) / sizeof(ranges[0]); ++i) {
        NaInterval *r = ranges[i];
        if (!r->bytes) continue;
        if (munmap(r->address, r->bytes)) { a->uncertain = 1; return -1; }
        *r = (NaInterval){MAP_FAILED, 0};
    }
    a->source = a->slot = MAP_FAILED;
    a->moved = 0;
    return 0;
}

static void na_code(uint32_t words[2])
{
#if defined(__aarch64__)
    words[0] = UINT32_C(0x52800540); /* mov w0, #42 */
    words[1] = UINT32_C(0xd65f03c0); /* ret */
#elif defined(NA_HOST_FIXTURE) && defined(__x86_64__)
    words[0] = UINT32_C(0x00002ab8); /* b8 2a 00 00 00 c3: mov eax,42; ret */
    words[1] = UINT32_C(0x9090c300); /* trailing two nops are not executed */
#else
#error This test needs AArch64, or the explicitly labelled x86-64 host fixture.
#endif
}

static uint32_t na_pattern(size_t i, unsigned stage)
{
    return (stage == NA_PATTERN_A ? NA_SEED_A : NA_SEED_B) ^
           ((uint32_t)i * UINT32_C(0x9e3779b9));
}

static void na_expected(uint32_t expected[NA_BYTES / 4], uint32_t initial, unsigned stage)
{
    cpu_alias_expected_fill(expected, NA_HOST_PAGE, initial);
    if (stage == NA_INITIAL) return;
    for (size_t i = 0; i < NA_SPAN / sizeof(uint32_t); ++i)
        expected[NA_OFFSET / sizeof(uint32_t) + i] = na_pattern(i, stage);
    if (stage == NA_CODE) na_code(&expected[NA_OFFSET / sizeof(uint32_t)]);
}

static int na_check_span(const NaAlias *a, const uint32_t *expected, const char *label)
{
    return cpu_alias_check_full(a->slot, expected + NA_OFFSET / sizeof(uint32_t), NA_SPAN, label);
}

static int na_check_views(const NaAlias *a, const NaAlias *b, const void *canonical,
                          const uint32_t *expected, const char *phase)
{
    printf("NATIVE_CPU_VIEW_PHASE=%s\n", phase);
    return na_check_span(a, expected, "NATIVE_ALIAS_A_16K") ||
           na_check_span(b, expected, "NATIVE_ALIAS_B_16K") ||
           cpu_alias_check_full(canonical, expected, NA_BYTES, "NATIVE_CANONICAL_ALL_8_PAGES");
}

static int na_permission(void *mapping, int protection, const char *label)
{
    if (mprotect(mapping, NA_SPAN, protection)) {
        printf("NATIVE_PERMISSION=UNSUPPORTED phase=%s errno=%d message=%s verified_write_stage=%d\n",
               label, errno, strerror(errno), (int)na_verified_stage);
        return NA_UNSUPPORTED;
    }
    printf("NATIVE_PERMISSION=PASS phase=%s prot=0x%x bytes=%d individual_VMA_W_plus_X=no\n", label, protection, NA_SPAN);
    return 0;
}

/* Caller retains the producer/FD/canonical map until return. No Vulkan call is
 * made here. Every complete expected image is deterministic from stage. */
static int na_exercise(int fd, const void *canonical, uint32_t initial, int fresh_canonical, NaReply *reply)
{
    NaAlias a = NA_ALIAS_INIT, b = NA_ALIAS_INIT;
    uint32_t expected[NA_BYTES / sizeof(uint32_t)];
    struct sigaction previous[3], guard = {0};
    const int signals[] = {SIGBUS, SIGSEGV, SIGILL};
    unsigned guards = 0;
    int result = 1;
    na_stage = na_verified_stage = NA_INITIAL;
    na_exec_phase = 0;
    guard.sa_handler = na_fatal_signal;
    sigemptyset(&guard.sa_mask);
    for (; guards < sizeof(signals) / sizeof(signals[0]); ++guards)
        if (sigaction(signals[guards], &guard, &previous[guards])) goto done;
    na_expected(expected, initial, NA_INITIAL);
    if (cpu_alias_check_full(canonical, expected, NA_BYTES, "NATIVE_CANONICAL_INITIAL")) {
        puts(fresh_canonical
             ? "NATIVE_ALIAS=UNSUPPORTED fresh child offset-zero mapping does not expose expected payload; no child writes"
             : "NATIVE_ALIAS=FAIL previously established canonical identity changed; no alias writes");
        result = fresh_canonical ? NA_UNSUPPORTED : 1; goto done;
    }
    NaAlias *list[] = {&a, &b};
    for (unsigned i = 0; i < 2; ++i) {
        NaAlias *m = list[i];
        if (na_alias_prepare(m, fd)) {
            printf("NATIVE_ALIAS=UNSUPPORTED prepare_alias=%u errno=%d message=%s\n", i, errno, strerror(errno));
            result = NA_UNSUPPORTED; goto done;
        }
        printf("NATIVE_ALIAS_LAYOUT alias=%u source_offset=%d span=%d destination_aligned_16k=%u\n",
               i, NA_OFFSET, NA_SPAN, (unsigned)((uintptr_t)m->slot % NA_SPAN == 0));
        if (cpu_alias_check_full(m->source, expected, NA_BYTES, "NATIVE_DISPOSABLE_FULL_INITIAL")) {
            puts("NATIVE_ALIAS=UNSUPPORTED disposable full identity failed before move/writes");
            result = NA_UNSUPPORTED; goto done;
        }
        if (na_alias_move(m)) na_uncertain_exit("move_16k_failed", NA_UNSUPPORTED);
        if (na_check_span(m, expected, "NATIVE_MOVED_16K_INITIAL")) {
            puts("NATIVE_ALIAS=UNSUPPORTED moved interval identity failed before writes");
            result = NA_UNSUPPORTED; goto done;
        }
    }
    if (na_check_views(&a, &b, canonical, expected, "two simultaneous aliases before writes")) {
        result = NA_UNSUPPORTED; goto done;
    }
    puts("NATIVE_TWO_ALIASES=PASS selected_host_pages=4,5,6,7 unselected_guards=0,1,2,3");

    if ((result = na_permission(b.slot, PROT_READ, "alias_B_RW_to_R"))) goto done;
    na_stage = NA_PATTERN_A;
    volatile uint32_t *words = a.slot;
    for (size_t i = 0; i < NA_SPAN / sizeof(uint32_t); ++i) words[i] = na_pattern(i, NA_PATTERN_A);
    atomic_thread_fence(memory_order_seq_cst);
    na_expected(expected, initial, NA_PATTERN_A);
    if (na_check_views(&a, &b, canonical, expected, "alias A writes visible through read-only B")) { result = 1; goto done; }
    na_verified_stage = NA_PATTERN_A;

    if ((result = na_permission(b.slot, PROT_READ | PROT_WRITE, "alias_B_R_to_RW"))) goto done;
    if ((result = na_permission(a.slot, PROT_READ, "alias_A_RW_to_R"))) goto done;
    na_stage = NA_PATTERN_B;
    words = b.slot;
    for (size_t i = 0; i < NA_SPAN / sizeof(uint32_t); ++i) words[i] = na_pattern(i, NA_PATTERN_B);
    atomic_thread_fence(memory_order_seq_cst);
    na_expected(expected, initial, NA_PATTERN_B);
    if (na_check_views(&a, &b, canonical, expected, "alias B writes visible through read-only A")) { result = 1; goto done; }
    na_verified_stage = NA_PATTERN_B;
    puts("NATIVE_ALIAS_BIDIRECTIONAL_WRITES=PASS canonical_pages_checked=8 guard_pages=4");

    if ((result = na_permission(a.slot, PROT_READ | PROT_WRITE, "alias_A_R_to_RW_for_code"))) goto done;
    uint32_t code[2];
    na_code(code);
    na_stage = NA_CODE;
    words = a.slot;
    words[0] = code[0]; words[1] = code[1];
    atomic_thread_fence(memory_order_seq_cst);
    na_expected(expected, initial, NA_CODE);
    if (na_check_views(&a, &b, canonical, expected, "fixed code bytes written and checked")) { result = 1; goto done; }
    na_verified_stage = NA_CODE;
    if ((result = na_permission(b.slot, PROT_READ, "alias_B_R_only_during_execution"))) goto done;
    puts("NATIVE_EXEC_POLICY=no_individual_RWX_mapping_request; retained_canonical_and_Vulkan_RW_aliases_coexist_with_RX_alias");
    na_exec_phase = 1;
    __builtin___clear_cache((char *)a.slot, (char *)a.slot + sizeof(code));
    puts("NATIVE_ICACHE_SYNC=PASS code_bytes=8");
    if ((result = na_permission(a.slot, PROT_READ | PROT_EXEC, "alias_A_RW_to_RX"))) goto done;
    int (*function)(void);
    _Static_assert(sizeof(function) == sizeof(a.slot), "Function and data pointer sizes must match");
    memcpy(&function, &a.slot, sizeof(function));
    int got = function();
    if (got != 42) {
        printf("NATIVE_EXEC=UNSUPPORTED returned=%d expected=42 code_bytes_verified=yes\n", got);
        result = NA_UNSUPPORTED; goto done;
    }
    na_exec_phase = 0;
#if defined(__aarch64__)
    puts("NATIVE_EXEC=PASS architecture=aarch64 instructions=mov_w0_42,ret return=42 individual_VMA_W_plus_X=no");
#else
    puts("NATIVE_EXEC=PASS architecture=x86_64_host_fixture instructions=mov_eax_42,ret return=42 AArch64_execution_tested=no");
#endif
    if ((result = na_permission(a.slot, PROT_READ | PROT_WRITE, "alias_A_RX_to_RW"))) goto done;
    if ((result = na_permission(b.slot, PROT_READ | PROT_WRITE, "alias_B_R_to_RW_final"))) goto done;
    if (na_check_views(&a, &b, canonical, expected, "post execution and restored permissions")) { result = 1; goto done; }
    result = 0;
done:
    na_exec_phase = 0;
    if (na_alias_drop(&b) || na_alias_drop(&a)) na_uncertain_exit("exact_alias_cleanup_failed", 1);
    puts("NATIVE_ALIAS_CLEANUP=PASS exact_source_prefix_suffix_and_owned_destination_reservations=yes vacated_holes_unowned=yes");
    while (guards) {
        --guards;
        if (sigaction(signals[guards], &previous[guards], NULL)) result = 1;
    }
    *reply = (NaReply){NA_MAGIC, NA_PROTOCOL, (uint32_t)result,
                       (uint32_t)na_stage, (uint32_t)na_verified_stage, 0};
    return result;
}

#endif
