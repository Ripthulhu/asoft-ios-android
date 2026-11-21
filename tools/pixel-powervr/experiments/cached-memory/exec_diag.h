/* SPDX-License-Identifier: MIT
 * Signal diagnostics for our own bounded fixed-code execution experiment.
 * The signal path reads only the supplied context and preinitialized scalars;
 * it never dereferences the fault PC, target, or si_addr.
 */
#ifndef PIXEL_EXEC_DIAG_H
#define PIXEL_EXEC_DIAG_H

#include <errno.h>
#include <inttypes.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <time.h>
#include <ucontext.h>
#include <unistd.h>

enum EdPhase { ED_START, ED_WRITE, ED_ICACHE, ED_RX, ED_READ_RX,
               ED_CALL, ED_RETURNED, ED_RESTORE, ED_CLEANUP };
static struct timespec ed_started;
static volatile sig_atomic_t ed_ready, ed_phase, ed_phase_begin_ms;

static const char *ed_phase_name(int phase)
{
    switch (phase) {
    case ED_START: return "start";
    case ED_WRITE: return "write_fixed_code";
    case ED_ICACHE: return "synchronize_icache";
    case ED_RX: return "mprotect_RW_to_RX";
    case ED_READ_RX: return "read_code_after_RX";
    case ED_CALL: return "call_fixed_code";
    case ED_RETURNED: return "returned_from_fixed_code";
    case ED_RESTORE: return "restore_RW";
    case ED_CLEANUP: return "cleanup";
    default: return "unknown";
    }
}

static int64_t ed_elapsed_ms(void)
{
    struct timespec now;
    if (!ed_ready || clock_gettime(CLOCK_MONOTONIC, &now)) return -1;
    return (int64_t)(now.tv_sec - ed_started.tv_sec) * 1000 +
           (now.tv_nsec - ed_started.tv_nsec) / 1000000;
}

static int ed_init(void)
{
    if (ed_ready) return 0;
    if (clock_gettime(CLOCK_MONOTONIC, &ed_started)) return -1;
    ed_phase = ED_START;
    ed_phase_begin_ms = 0;
    ed_ready = 1;
    return 0;
}

static void ed_set_phase(enum EdPhase phase)
{
    int64_t elapsed = ed_elapsed_ms();
    ed_phase_begin_ms = elapsed >= 0 && elapsed < INT32_MAX ? (sig_atomic_t)elapsed : -1;
    ed_phase = phase;
    printf("EXEC_DIAG_PHASE=%s elapsed_ms=%" PRId64 "\n", ed_phase_name(phase), elapsed);
}

/* Fixed-size, allocation-free formatting for the async signal handler. */
typedef struct EdText { char bytes[1024]; size_t used; } EdText;
static void ed_text(EdText *out, const char *text)
{
    while (*text && out->used < sizeof(out->bytes)) out->bytes[out->used++] = *text++;
}
static void ed_unsigned(EdText *out, uint64_t value, unsigned base)
{
    char digits[32];
    unsigned count = 0;
    do { digits[count++] = "0123456789abcdef"[value % base]; value /= base; } while (value);
    while (count && out->used < sizeof(out->bytes)) out->bytes[out->used++] = digits[--count];
}
static void ed_signed(EdText *out, int64_t value)
{
    if (value < 0) { ed_text(out, "-"); ed_unsigned(out, (uint64_t)(-(value + 1)) + 1, 10); }
    else ed_unsigned(out, (uint64_t)value, 10);
}
static void ed_hex(EdText *out, const char *name, uint64_t value)
{
    ed_text(out, name); ed_text(out, "0x"); ed_unsigned(out, value, 16);
}

static void ed_signal_log(int number, const siginfo_t *info, const void *context)
{
    const int saved_errno = errno;
    const int phase = ed_phase;
    const int phase_begin = ed_phase_begin_ms;
    const int64_t elapsed = ed_elapsed_ms();
    EdText out = {{0}, 0};
    ed_text(&out, "EXEC_DIAG_SIGNAL number="); ed_signed(&out, number);
    ed_text(&out, " si_code="); ed_signed(&out, info ? info->si_code : 0);
    ed_text(&out, " phase="); ed_text(&out, ed_phase_name(phase));
    ed_text(&out, " elapsed_ms="); ed_signed(&out, elapsed);
    ed_text(&out, " phase_ms="); ed_signed(&out, elapsed < 0 || phase_begin < 0 ? -1 : elapsed - phase_begin);
    if (info && (number == SIGSEGV || number == SIGBUS || number == SIGILL))
        ed_hex(&out, " fault_address=", (uintptr_t)info->si_addr);
#if defined(__aarch64__)
    if (context) {
        const ucontext_t *uc = context;
        ed_hex(&out, " pc=", uc->uc_mcontext.pc);
        ed_hex(&out, " lr=", uc->uc_mcontext.regs[30]);
        ed_hex(&out, " sp=", uc->uc_mcontext.sp);
        ed_hex(&out, " x0=", uc->uc_mcontext.regs[0]);
        ed_hex(&out, " x8=", uc->uc_mcontext.regs[8]);
    }
#elif defined(__x86_64__) && defined(REG_RIP)
    if (context) {
        const ucontext_t *uc = context;
        ed_hex(&out, " pc=", uc->uc_mcontext.gregs[REG_RIP]);
        ed_hex(&out, " sp=", uc->uc_mcontext.gregs[REG_RSP]);
    }
#else
    (void)context;
#endif
    ed_text(&out, " code_memory_dereferenced_in_handler=no\n");
    (void)write(STDERR_FILENO, out.bytes, out.used);
    errno = saved_errno;
}

static int ed_check_code(const void *readable, const void *target, const uint32_t expected[2], const char *label)
{
    const volatile uint32_t *p = readable;
    uint32_t first = p[0], second = p[1];
    printf("EXEC_DIAG_CODE label=%s readable=%p target=%p words=%08" PRIx32 ",%08" PRIx32
           " expected=%08" PRIx32 ",%08" PRIx32 " elapsed_ms=%" PRId64 "\n",
           label, readable, target, first, second, expected[0], expected[1], ed_elapsed_ms());
    if (first != expected[0] || second != expected[1]) {
        puts("EXEC_DIAG_CODE=FAIL changed_instruction_bytes; indirect call skipped");
        return -1;
    }
    return 0;
}
#endif
