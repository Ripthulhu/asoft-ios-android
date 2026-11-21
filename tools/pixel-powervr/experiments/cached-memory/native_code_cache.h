/* SPDX-License-Identifier: MIT
 * Bounded native CPU code-cache experiment, separate from direct GPU-backed
 * execution. Data aliases keep their producer backing. Instruction bytes are
 * copied from a verified read-only 16 KiB alias into a new ordinary memfd.
 * Only disposable full offset-zero producer maps are moved; no Vulkan pointer.
 */
#ifndef PIXEL_NATIVE_CODE_CACHE_H
#define PIXEL_NATIVE_CODE_CACHE_H

#include "cpu_alias.h"
#include "exec_diag.h"
#include <inttypes.h>
#include <fcntl.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/time.h>

enum { NA_HOST_PAGE = 4096, NA_BYTES = 32768, NA_SPAN = 16384,
       NA_OFFSET = 16384, NA_UNSUPPORTED = 6, NA_PROTOCOL = 3,
       NA_VARIANT_CODE_CACHE = 3, NA_CALL_MS = 5000, NA_PROCESS_SECONDS = 60 };
#define NA_MAGIC UINT32_C(0x4e433033)
#define NA_SEED_A UINT32_C(0xb1250000)
#define NA_SEED_B UINT32_C(0xc9360000)

/* Stage is set before a write. Verified is advanced only after every CPU view
 * agrees, so a capability refusal after writes cannot conceal partial data. */
enum NaStage { NA_INITIAL, NA_PATTERN_A, NA_PATTERN_B,
               NA_CODE_42, NA_CODE_43, NA_CODE_42_RESTORED, NA_LAST_STAGE = NA_CODE_42_RESTORED };
enum NaMemoryState { NA_MEMORY_UNTESTED, NA_MEMORY_DIRTY,
                     NA_MEMORY_RESTORED, NA_MEMORY_PASSED };
typedef struct NaReply {
    uint32_t magic, protocol, variant, status, stage, verified_stage, memory_state, cpu_atomics;
} NaReply;

static volatile sig_atomic_t na_stage, na_verified_stage, na_exec_phase;
static volatile sig_atomic_t na_reply_fd = -1, na_memory_state, na_memory_phase;
static int64_t na_deadline_ms;
/* Producer atomics require the explicit --cpu-atomics option. Ordinary-memfd
 * controls set it only for their own, separately labelled normal RAM. */
static volatile sig_atomic_t na_cpu_atomics;
static unsigned na_atomic_calls;
static const char *na_process_role = "parent";

#if defined(NA_HOST_FIXTURE)
static const char *na_backing_name = "ordinary_memfd_host_fixture";
#else
static const char *na_backing_name = "cached_Vulkan_OPAQUE_FD";
#endif
#define NA_PRODUCER_NAME na_backing_name

/* If stdout is a regular retained log, commit the phase marker before the
 * operation. A userspace timer cannot contain an interconnect/kernel panic.
 * A terminal/pipe remains explicitly non-durable; no global sync is used. */
static int na_checkpoint(const char *phase)
{
    struct stat status;
    int regular = !fstat(STDOUT_FILENO, &status) && S_ISREG(status.st_mode);
    printf("CACHED_MEMORY_CHECKPOINT phase=%s role=%s pid=%lu ppid=%lu backing=%s cpu_atomics=%u state=%d stage=%d regular_log=%d kernel_panic_contained=no\n",
           phase, na_process_role, (unsigned long)getpid(), (unsigned long)getppid(), NA_PRODUCER_NAME, na_cpu_atomics, (int)na_memory_state,
           (int)na_stage, regular);
    if (fflush(stdout)) return 1;
    if (regular && fsync(STDOUT_FILENO)) {
        fprintf(stderr, "FAIL: cannot persist phase checkpoint errno=%d\n", errno);
        return 1;
    }
    return 0;
}

/* smaps describes VMAs, not ARM page-table AttrIndx/MAIR values. Never label
 * HOST_CACHED or these VmFlags as direct evidence of Normal write-back PTEs. */
static void na_mapping_report(const void *address, size_t bytes, const char *label)
{
    FILE *stream = fopen("/proc/self/smaps", "re");
    if (!stream) {
        printf("CACHED_MAPPING label=%s smaps=unavailable errno=%d PTE_cacheability_observed=no\n", label, errno);
        return;
    }
    char line[1024];
    uintptr_t at = (uintptr_t)address;
    int selected = 0, found = 0;
    while (fgets(line, sizeof(line), stream)) {
        unsigned long low, high;
        if (sscanf(line, "%lx-%lx", &low, &high) == 2) {
            if (selected) break;
            selected = at >= low && at < high;
            if (selected) {
                found = 1;
                printf("CACHED_MAPPING label=%s range_covers_requested_span=%u PTE_cacheability_observed=no\n",
                       label, bytes <= high - at);
                fputs(line, stdout);
            }
        } else if (selected && (!strncmp(line, "VmFlags:", 8) ||
                                !strncmp(line, "KernelPageSize:", 15) ||
                                !strncmp(line, "MMUPageSize:", 12))) {
            fputs(line, stdout);
        }
    }
    fclose(stream);
    if (!found) printf("CACHED_MAPPING label=%s smaps=range_not_found PTE_cacheability_observed=no\n", label);
}

static int64_t na_now_ms(void)
{
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t)) return -1;
    return (int64_t)t.tv_sec * 1000 + t.tv_nsec / 1000000;
}

/* One timer always expires at or before the original process deadline.
 * A call temporarily tightens it to 5 s; returning restores only the remaining
 * process budget. No repeated call can extend the process lifetime. */
static int na_arm_limit(unsigned call_ms)
{
    int64_t now = na_now_ms();
    if (now < 0 || !na_deadline_ms) return -1;
    int64_t remaining = na_deadline_ms - now;
    if (remaining <= 0) { errno = ETIMEDOUT; return -1; }
    if (call_ms && remaining > call_ms) remaining = call_ms;
    struct itimerval timer = { .it_value = {
        .tv_sec = (time_t)(remaining / 1000),
        .tv_usec = (suseconds_t)((remaining % 1000) * 1000) } };
    return setitimer(ITIMER_REAL, &timer, NULL);
}

static void na_write_reply_signal(int status)
{
    if (na_reply_fd >= 0) {
        NaReply r = {NA_MAGIC, NA_PROTOCOL, NA_VARIANT_CODE_CACHE, (uint32_t)status,
                     (uint32_t)na_stage, (uint32_t)na_verified_stage,
                     (uint32_t)na_memory_state, na_cpu_atomics};
        (void)write((int)na_reply_fd, &r, sizeof(r));
    }
}

static void na_fatal_signal(int number, siginfo_t *info, void *context)
{
    ed_signal_log(number, info, context);
    EdText state = {{0}, 0};
    ed_text(&state, "NATIVE_CPU_MEMORY_SIGNAL phase=");
    ed_signed(&state, na_memory_phase);
    ed_text(&state, " state=");
    ed_signed(&state, na_memory_state);
    ed_text(&state, " dirty_state_is_1; unverified_memory_never_reaches_later_GPU_work=yes\n");
    (void)write(STDERR_FILENO, state.bytes, state.used);
    int result = number == SIGALRM || number == SIGTERM || number == SIGINT
                 || na_memory_state == NA_MEMORY_DIRTY
                 ? 1 : na_exec_phase || na_stage == NA_INITIAL ? NA_UNSUPPORTED : 1;
    /* Never signal a numeric child PID from this asynchronous handler: a reap
     * may have just freed it. The exec child arms PDEATHSIG and checks getppid
     * before receiving or mapping the producer FD. */
    if (result == NA_UNSUPPORTED) {
        static const char msg[] = "NATIVE_CODE_CACHE=UNSUPPORTED signal during clean memory preflight, pre-write mapping or verified ordinary-memfd execution; stopping\nRESULT=NATIVE_CODE_CACHE_UNSUPPORTED\n";
        (void)write(STDERR_FILENO, msg, sizeof(msg) - 1);
    } else {
        static const char msg[] = "NATIVE_CODE_CACHE=FAIL signal with unverified data/preflight writes or bounded deadline/interruption; stopping\nRESULT=FAIL\n";
        (void)write(STDERR_FILENO, msg, sizeof(msg) - 1);
    }
    na_write_reply_signal(result);
    _Exit(result);
}

static int na_watchdog(unsigned seconds)
{
    if (ed_init()) return 1;
    struct sigaction a = {0};
    a.sa_sigaction = na_fatal_signal;
    a.sa_flags = SA_SIGINFO;
    sigemptyset(&a.sa_mask);
    if (sigaction(SIGALRM, &a, NULL) || sigaction(SIGTERM, &a, NULL) ||
        sigaction(SIGINT, &a, NULL)) return 1;
    a.sa_handler = SIG_IGN;
    a.sa_flags = 0;
    if (sigaction(SIGPIPE, &a, NULL)) return 1;
    int64_t now = na_now_ms();
    if (now < 0 || !seconds || seconds > NA_PROCESS_SECONDS) return 1;
    na_deadline_ms = now + (int64_t)seconds * 1000;
    return na_arm_limit(0);
}

static void na_uncertain_exit(const char *why, int result)
{
    printf("NATIVE_CODE_CACHE_UNCERTAIN=%s errno=%d message=%s cleanup=process_exit_only\n",
           why, errno, strerror(errno));
    puts(result == NA_UNSUPPORTED ? "RESULT=NATIVE_CODE_CACHE_UNSUPPORTED" : "RESULT=FAIL");
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
    if (na_checkpoint("before_disposable_full_FD_mmap")) return -1;
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
    if (na_checkpoint("before_owned_16KiB_mremap")) return -1;
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

static void na_code(uint32_t words[2], unsigned return_value)
{
#if defined(__aarch64__)
    words[0] = UINT32_C(0x52800000) | (return_value << 5); /* mov w0, #42 or #43 */
    words[1] = UINT32_C(0xd65f03c0); /* ret */
#elif defined(NA_HOST_FIXTURE) && defined(__x86_64__)
    words[0] = UINT32_C(0x000000b8) | (return_value << 8); /* mov eax,42 or 43 */
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
    if (stage >= NA_CODE_42)
        na_code(&expected[NA_OFFSET / sizeof(uint32_t)], stage == NA_CODE_43 ? 43 : 42);
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

#include "native_cpu_memory.h"

static int na_permission(void *mapping, int protection, const char *label)
{
    if (na_checkpoint(label)) return 1;
    if (mprotect(mapping, NA_SPAN, protection)) {
        printf("NATIVE_PERMISSION=UNSUPPORTED phase=%s errno=%d message=%s verified_write_stage=%d\n",
               label, errno, strerror(errno), (int)na_verified_stage);
        return NA_UNSUPPORTED;
    }
    printf("NATIVE_PERMISSION=PASS phase=%s prot=0x%x bytes=%d individual_VMA_W_plus_X=no\n", label, protection, NA_SPAN);
    return 0;
}

typedef struct NaCodeCache { void *mapping; int fd; } NaCodeCache;
#define NA_CODE_CACHE_INIT { .mapping = MAP_FAILED, .fd = -1 }

static int na_cache_drop(NaCodeCache *cache)
{
    if (cache->mapping != MAP_FAILED) {
        if (munmap(cache->mapping, NA_SPAN)) return -1;
        cache->mapping = MAP_FAILED;
    }
    if (cache->fd >= 0) {
        int fd = cache->fd;
        cache->fd = -1; /* Linux close must not be retried even after EINTR. */
        if (close(fd)) return -1;
    }
    return 0;
}

/* No producer writes, Vulkan submissions, or other execution overlap this
 * snapshot/call. The source VMA is read-only but canonical/driver RW aliases
 * remain; this is deliberately not a physical W^X or race/invalidation proof.
 * Each generation owns one fresh memfd + exactly one 16 KiB VMA. That VMA is
 * RW only during fill, then RX. The old generation has returned and is fully
 * unmapped/closed before the next producer-code mutation starts. */
static int na_cache_execute(const void *source, const uint32_t *expected,
                            unsigned wanted, unsigned generation)
{
    NaCodeCache cache = NA_CODE_CACHE_INIT;
    int result = 1;
    uint32_t code[2];
    na_code(code, wanted);
    printf("NATIVE_CODE_CACHE_GENERATION=%u expected_return=%u copied_instruction_bytes=yes source_protection=R source_backing=%s snapshot_bytes=%d\n",
           generation, wanted, NA_PRODUCER_NAME, NA_SPAN);
    cache.fd = memfd_create("pixel-native-code-cache", MFD_CLOEXEC | MFD_ALLOW_SEALING);
    if (cache.fd < 0 || ftruncate(cache.fd, NA_SPAN) ||
        fcntl(cache.fd, F_ADD_SEALS, F_SEAL_SHRINK | F_SEAL_GROW)) {
        printf("NATIVE_CODE_CACHE=UNSUPPORTED create_size_seal_ordinary_memfd errno=%d message=%s\n", errno, strerror(errno));
        result = NA_UNSUPPORTED; goto done;
    }
    cache.mapping = mmap(NULL, NA_SPAN, PROT_READ | PROT_WRITE, MAP_SHARED, cache.fd, 0);
    if (cache.mapping == MAP_FAILED) {
        printf("NATIVE_CODE_CACHE=UNSUPPORTED map_ordinary_memfd errno=%d message=%s\n", errno, strerror(errno));
        result = NA_UNSUPPORTED; goto done;
    }
    ed_set_phase(ED_WRITE);
    if (na_checkpoint("before_producer_to_memfd_instruction_snapshot")) goto done;
    const volatile uint32_t *src = source;
    volatile uint32_t *dst = cache.mapping;
    for (size_t i = 0; i < NA_SPAN / sizeof(uint32_t); ++i) dst[i] = src[i];
    atomic_thread_fence(memory_order_seq_cst);
    if (cpu_alias_check_full(source, expected, NA_SPAN, "NATIVE_CODE_CACHE_SOURCE_AFTER_COPY") ||
        cpu_alias_check_full(cache.mapping, expected, NA_SPAN, "NATIVE_CODE_CACHE_COPIED_ALL_16K") ||
        ed_check_code(cache.mapping, cache.mapping, code, "ordinary_memfd_before_icache_RW")) goto done;
    puts("NATIVE_CODE_CACHE_SNAPSHOT=PASS bytes_copied=16384 full_expected_image_verified=yes concurrent_snapshot_or_invalidation_tested=no");
    na_exec_phase = 1;
    ed_set_phase(ED_ICACHE);
    __builtin___clear_cache((char *)cache.mapping, (char *)cache.mapping + NA_SPAN);
    puts("NATIVE_CODE_CACHE_ICACHE_SYNC=PASS bytes=16384 backing=ordinary_memfd");
    ed_set_phase(ED_RX);
    if ((result = na_permission(cache.mapping, PROT_READ | PROT_EXEC, "ordinary_code_cache_RW_to_RX"))) goto done;
    ed_set_phase(ED_READ_RX);
    result = 1;
    if (cpu_alias_check_full(cache.mapping, expected, NA_SPAN, "NATIVE_CODE_CACHE_RX_ALL_16K") ||
        ed_check_code(cache.mapping, cache.mapping, code, "ordinary_memfd_after_RX") ||
        ed_check_code(source, cache.mapping, code, "producer_read_only_source_after_cache_RX")) goto done;
    int (*function)(void);
    _Static_assert(sizeof(function) == sizeof(cache.mapping), "Function and data pointer sizes must match");
    memcpy(&function, &cache.mapping, sizeof(function));
    if (na_arm_limit(NA_CALL_MS)) { puts("FAIL: cannot arm 5-second code-cache call deadline"); goto done; }
    ed_set_phase(ED_CALL);
    if (na_checkpoint("before_ordinary_memfd_code_call")) goto done;
    int got = function();
    ed_set_phase(ED_RETURNED);
    na_exec_phase = 0;
    if (na_arm_limit(0)) { puts("FAIL: cannot restore remaining process deadline"); goto done; }
    printf("NATIVE_CODE_CACHE_RETURN generation=%u value=%d expected=%u instruction_backing=ordinary_memfd direct_GPU_backing_execution=no call_limit_ms=%d\n",
           generation, got, wanted, NA_CALL_MS);
    if (got != (int)wanted) { puts("NATIVE_CODE_CACHE=FAIL unexpected_return"); goto done; }
    if (cpu_alias_check_full(cache.mapping, expected, NA_SPAN, "NATIVE_CODE_CACHE_AFTER_RETURN_ALL_16K")) goto done;
#if defined(__aarch64__)
    puts("NATIVE_CODE_CACHE_EXEC=PASS architecture=aarch64 CPU_native_EL0=yes TCG_used=no actual_QEMU_native_stub_tested=no");
#else
    puts("NATIVE_CODE_CACHE_EXEC=PASS architecture=x86_64_host_fixture AArch64_execution_tested=no phone_tested=no");
#endif
    result = 0;
done:
    na_exec_phase = 0;
    ed_set_phase(ED_CLEANUP);
    if (na_cache_drop(&cache)) na_uncertain_exit("exact_code_cache_cleanup_failed", 1);
    printf("NATIVE_CODE_CACHE_CLEANUP=PASS generation=%u exact_16K_VMA_unmapped_and_ordinary_memfd_closed=yes\n", generation);
    return result;
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
    na_memory_state = NA_MEMORY_UNTESTED;
    na_memory_phase = 0;
    guard.sa_sigaction = na_fatal_signal;
    guard.sa_flags = SA_SIGINFO;
    sigemptyset(&guard.sa_mask);
    for (; guards < sizeof(signals) / sizeof(signals[0]); ++guards)
        if (sigaction(signals[guards], &guard, &previous[guards])) goto done;
    na_expected(expected, initial, NA_INITIAL);
    if (na_checkpoint("before_canonical_payload_identity_read")) goto done;
    if (cpu_alias_check_full(canonical, expected, NA_BYTES, "NATIVE_CANONICAL_INITIAL")) {
        puts(fresh_canonical
             ? "NATIVE_DATA_ALIAS=UNSUPPORTED fresh child offset-zero mapping does not expose expected payload; no child writes"
             : "NATIVE_DATA_ALIAS=FAIL previously established canonical identity changed; no alias writes");
        result = fresh_canonical ? NA_UNSUPPORTED : 1; goto done;
    }
    NaAlias *list[] = {&a, &b};
    for (unsigned i = 0; i < 2; ++i) {
        NaAlias *m = list[i];
        if (na_alias_prepare(m, fd)) {
            printf("NATIVE_DATA_ALIAS=UNSUPPORTED prepare_alias=%u errno=%d message=%s\n", i, errno, strerror(errno));
            result = NA_UNSUPPORTED; goto done;
        }
        printf("NATIVE_DATA_ALIAS_LAYOUT alias=%u source_offset=%d span=%d destination_aligned_16k=%u\n",
               i, NA_OFFSET, NA_SPAN, (unsigned)((uintptr_t)m->slot % NA_SPAN == 0));
        if (na_checkpoint("before_disposable_full_identity_read")) goto done;
        if (cpu_alias_check_full(m->source, expected, NA_BYTES, "NATIVE_DISPOSABLE_FULL_INITIAL")) {
            puts("NATIVE_DATA_ALIAS=UNSUPPORTED disposable full identity failed before move/writes");
            result = NA_UNSUPPORTED; goto done;
        }
        if (na_alias_move(m)) na_uncertain_exit("move_16k_failed", NA_UNSUPPORTED);
        if (na_checkpoint("after_mremap_before_moved_identity_read")) goto done;
        if (na_check_span(m, expected, "NATIVE_MOVED_16K_INITIAL")) {
            puts("NATIVE_DATA_ALIAS=UNSUPPORTED moved interval identity failed before writes");
            result = NA_UNSUPPORTED; goto done;
        }
        na_mapping_report(m->slot, NA_SPAN, i ? "moved_data_alias_B" : "moved_data_alias_A");
    }
    if (na_check_views(&a, &b, canonical, expected, "two simultaneous aliases before writes")) {
        result = NA_UNSUPPORTED; goto done;
    }
    puts("NATIVE_TWO_ALIASES=PASS selected_host_pages=4,5,6,7 unselected_guards=0,1,2,3");

    result = na_memory_preflight(&a, &b, canonical, expected);
    if (result) goto done;

    if ((result = na_permission(b.slot, PROT_READ, "alias_B_RW_to_R"))) goto done;
    na_stage = NA_PATTERN_A;
    if (na_checkpoint("before_alias_A_pattern_write")) { result = 1; goto done; }
    volatile uint32_t *words = a.slot;
    for (size_t i = 0; i < NA_SPAN / sizeof(uint32_t); ++i) words[i] = na_pattern(i, NA_PATTERN_A);
    atomic_thread_fence(memory_order_seq_cst);
    na_expected(expected, initial, NA_PATTERN_A);
    if (na_check_views(&a, &b, canonical, expected, "alias A writes visible through read-only B")) { result = 1; goto done; }
    na_verified_stage = NA_PATTERN_A;

    if ((result = na_permission(b.slot, PROT_READ | PROT_WRITE, "alias_B_R_to_RW"))) goto done;
    if ((result = na_permission(a.slot, PROT_READ, "alias_A_RW_to_R"))) goto done;
    na_stage = NA_PATTERN_B;
    if (na_checkpoint("before_alias_B_pattern_write")) { result = 1; goto done; }
    words = b.slot;
    for (size_t i = 0; i < NA_SPAN / sizeof(uint32_t); ++i) words[i] = na_pattern(i, NA_PATTERN_B);
    atomic_thread_fence(memory_order_seq_cst);
    na_expected(expected, initial, NA_PATTERN_B);
    if (na_check_views(&a, &b, canonical, expected, "alias B writes visible through read-only A")) { result = 1; goto done; }
    na_verified_stage = NA_PATTERN_B;
    puts("NATIVE_DATA_ALIAS_BIDIRECTIONAL_WRITES=PASS canonical_pages_checked=8 guard_pages=4");

    puts("NATIVE_CODE_CACHE_POLICY=producer_data_aliases_keep_original_backing; only_instruction_image_is_copied; no_individual_RWX_mapping_request; strict_physical_W_X_not_claimed; concurrent_snapshot_and_execution_not_tested");
    if ((result = na_permission(b.slot, PROT_READ, "data_alias_B_R_during_code_cache_sequence"))) goto done;
    for (unsigned stage = NA_CODE_42; stage <= NA_CODE_42_RESTORED; ++stage) {
        /* The preceding cache generation is fully disposed before this write.
         * Stages never go backwards, including the final return-to-42 image. */
        if ((result = na_permission(a.slot, PROT_READ | PROT_WRITE, "data_alias_A_R_to_RW_for_code_update"))) goto done;
        uint32_t code[2];
        unsigned wanted = stage == NA_CODE_43 ? 43 : 42;
        na_code(code, wanted);
        ed_set_phase(ED_WRITE);
        na_stage = (sig_atomic_t)stage;
        if (na_checkpoint("before_producer_instruction_image_update")) { result = 1; goto done; }
        words = a.slot;
        words[0] = code[0]; words[1] = code[1];
        atomic_thread_fence(memory_order_seq_cst);
        na_expected(expected, initial, stage);
        if (na_check_views(&a, &b, canonical, expected, "producer code image and all guard pages")) { result = 1; goto done; }
        na_verified_stage = (sig_atomic_t)stage;
        if ((result = na_permission(a.slot, PROT_READ, "data_alias_A_RW_to_R_before_snapshot"))) goto done;
        if (na_check_views(&a, &b, canonical, expected, "read-only source immediately before snapshot")) { result = 1; goto done; }
        result = na_cache_execute(a.slot, expected + NA_OFFSET / sizeof(uint32_t),
                                  wanted, stage - NA_CODE_42 + 1);
        if (result) goto done;
        if (na_check_views(&a, &b, canonical, expected, "after ordinary-memfd execution and exact cache disposal")) { result = 1; goto done; }
    }
    puts("NATIVE_CODE_CACHE_REPLACEMENT=PASS returned_sequence=42,43,42 generations=3 old_generation_disposed_before_source_update=yes concurrency_tested=no");
    ed_set_phase(ED_RESTORE);
    if ((result = na_permission(a.slot, PROT_READ | PROT_WRITE, "alias_A_R_to_RW_final"))) goto done;
    if ((result = na_permission(b.slot, PROT_READ | PROT_WRITE, "alias_B_R_to_RW_final"))) goto done;
    if (na_check_views(&a, &b, canonical, expected, "post execution and restored permissions")) { result = 1; goto done; }
    result = 0;
done:
    ed_set_phase(ED_CLEANUP);
    na_exec_phase = 0;
    if (na_alias_drop(&b) || na_alias_drop(&a)) na_uncertain_exit("exact_alias_cleanup_failed", 1);
    puts("NATIVE_DATA_ALIAS_CLEANUP=PASS exact_source_prefix_suffix_and_owned_destination_reservations=yes vacated_holes_unowned=yes");
    while (guards) {
        --guards;
        if (sigaction(signals[guards], &previous[guards], NULL)) result = 1;
    }
    *reply = (NaReply){NA_MAGIC, NA_PROTOCOL, NA_VARIANT_CODE_CACHE, (uint32_t)result,
                       (uint32_t)na_stage, (uint32_t)na_verified_stage,
                       (uint32_t)na_memory_state, na_cpu_atomics};
    return result;
}

#endif
