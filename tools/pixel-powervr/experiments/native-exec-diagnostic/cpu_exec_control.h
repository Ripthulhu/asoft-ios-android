/* SPDX-License-Identifier: MIT
 * CPU-only controls: private anonymous or a new ordinary memfd. No Vulkan API.
 */
#ifndef PIXEL_CPU_EXEC_CONTROL_H
#define PIXEL_CPU_EXEC_CONTROL_H

#include "exec_diag.h"
#include <fcntl.h>
#include <stdatomic.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>

static void ec_signal(int number, siginfo_t *info, void *context)
{
    ed_signal_log(number, info, context);
    const int result = number == SIGALRM || number == SIGTERM || number == SIGINT ? 1 : 6;
    static const char failed[] = "CPU_EXEC_CONTROL=FAIL bounded_deadline_or_interruption\nRESULT=FAIL\n";
    static const char unsupported[] = "CPU_EXEC_CONTROL=UNSUPPORTED synchronous_execution_or_mapping_signal\nRESULT=CPU_EXEC_UNSUPPORTED\n";
    if (result == 1) (void)write(STDERR_FILENO, failed, sizeof(failed) - 1);
    else (void)write(STDERR_FILENO, unsupported, sizeof(unsupported) - 1);
    _Exit(result);
}

static int ec_run(int ordinary_memfd)
{
    enum { SPAN = 16384 };
    int fd = -1, result = 1;
    void *memory = MAP_FAILED;
    if (ed_init()) return 1;
    struct sigaction guard = {0};
    guard.sa_sigaction = ec_signal;
    guard.sa_flags = SA_SIGINFO;
    sigemptyset(&guard.sa_mask);
    const int signals[] = {SIGBUS, SIGSEGV, SIGILL, SIGALRM, SIGTERM, SIGINT};
    for (unsigned i = 0; i < sizeof(signals) / sizeof(signals[0]); ++i)
        if (sigaction(signals[i], &guard, NULL)) return 1;
    alarm(5);
    printf("CPU_EXEC_CONTROL mode=%s uid=%lu euid=%lu page_size=%ld bytes=%u watchdog_seconds=5 Vulkan_calls=no\n",
           ordinary_memfd ? "ordinary_memfd" : "private_anonymous",
           (unsigned long)getuid(), (unsigned long)geteuid(), sysconf(_SC_PAGESIZE), SPAN);
    if (ordinary_memfd) {
        fd = memfd_create("pixel-fixed-code-control", MFD_CLOEXEC);
        if (fd < 0 || ftruncate(fd, SPAN)) {
            printf("CPU_EXEC_CONTROL=UNSUPPORTED memfd_create_or_size errno=%d message=%s\n", errno, strerror(errno));
            result = 6; goto done;
        }
    }
    memory = mmap(NULL, SPAN, PROT_READ | PROT_WRITE,
                  ordinary_memfd ? MAP_SHARED : MAP_PRIVATE | MAP_ANONYMOUS, fd, 0);
    if (memory == MAP_FAILED) {
        printf("CPU_EXEC_CONTROL=UNSUPPORTED fresh_mapping errno=%d message=%s\n", errno, strerror(errno));
        result = 6; goto done;
    }
    uint32_t code[2];
#if defined(__aarch64__)
    code[0] = UINT32_C(0x52800540); /* mov w0, #42 */
    code[1] = UINT32_C(0xd65f03c0); /* ret */
#elif defined(EC_HOST_FIXTURE) && defined(__x86_64__)
    code[0] = UINT32_C(0x00002ab8); /* separate x86-64 host fixture only */
    code[1] = UINT32_C(0x9090c300);
#else
#error AArch64 required, except an explicitly selected x86-64 host fixture.
#endif
    ed_set_phase(ED_WRITE);
    volatile uint32_t *words = memory;
    words[0] = code[0]; words[1] = code[1];
    atomic_thread_fence(memory_order_seq_cst);
    if (ed_check_code(memory, memory, code, "before_icache_RW")) goto done;
    ed_set_phase(ED_ICACHE);
    __builtin___clear_cache((char *)memory, (char *)memory + sizeof(code));
    puts("CPU_EXEC_ICACHE_SYNC=PASS code_bytes=8");
    ed_set_phase(ED_RX);
    if (mprotect(memory, SPAN, PROT_READ | PROT_EXEC)) {
        printf("CPU_EXEC_CONTROL=UNSUPPORTED RW_to_RX errno=%d message=%s\n", errno, strerror(errno));
        result = 6; goto done;
    }
    puts("CPU_EXEC_PERMISSION=PASS transition=RW_to_RX individual_VMA_W_plus_X=no");
    ed_set_phase(ED_READ_RX);
    if (ed_check_code(memory, memory, code, "after_mprotect_RX")) goto done;
    int (*function)(void);
    _Static_assert(sizeof(function) == sizeof(memory), "Function and data pointer sizes must match");
    memcpy(&function, &memory, sizeof(function));
    ed_set_phase(ED_CALL);
    int got = function();
    ed_set_phase(ED_RETURNED);
    printf("CPU_EXEC_RETURN value=%d expected=42\n", got);
    if (got != 42) {
        puts("CPU_EXEC_CONTROL=FAIL unexpected_return"); goto done;
    }
    ed_set_phase(ED_RESTORE);
    if (mprotect(memory, SPAN, PROT_READ | PROT_WRITE)) {
        printf("CPU_EXEC_CONTROL=FAIL restore_RW errno=%d\n", errno); goto done;
    }
    if (ed_check_code(memory, memory, code, "after_return_RW")) goto done;
    result = 0;
done:
    ed_set_phase(ED_CLEANUP);
    if (memory != MAP_FAILED && munmap(memory, SPAN)) result = 1;
    if (fd >= 0 && close(fd)) result = 1;
    alarm(0);
    puts(result == 0 ? "CPU_EXEC_CONTROL=PASS fixed_return_42; no_GPU_or_exported_memory_tested\nRESULT=CPU_EXEC_PASS" :
         result == 6 ? "RESULT=CPU_EXEC_UNSUPPORTED" : "RESULT=FAIL");
    return result;
}
#endif
