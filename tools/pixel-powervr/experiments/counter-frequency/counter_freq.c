#define _POSIX_C_SOURCE 200809L
#include <inttypes.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <unistd.h>

/* Read-only: one architecture register read, process identity, and stdout.
 * No clock measurement, timers, sleeps, device files, or configuration writes.
 */
static void unsupported(int signo) {
    (void)signo;
    static const char message[] = "RESULT=COUNTER_REGISTER_UNREADABLE_SIGILL\n";
    (void)write(STDOUT_FILENO, message, sizeof(message) - 1);
    _exit(2);
}

int main(void) {
    struct sigaction action = {0};
    action.sa_handler = unsupported;
    sigemptyset(&action.sa_mask);
    if (sigaction(SIGILL, &action, NULL) != 0) {
        puts("RESULT=SIGNAL_HANDLER_FAILURE");
        return 1;
    }
    uint64_t hz;
    __asm__ volatile("mrs %0, cntfrq_el0" : "=r"(hz));
    printf("COUNTER_FREQ_PROBE=1 UID=%u EUID=%u\n", (unsigned)getuid(), (unsigned)geteuid());
    printf("CNTFRQ_EL0_HZ=%" PRIu64 "\n", hz);
    if (hz < UINT64_C(1000000) || hz > UINT32_MAX) {
        puts("RESULT=COUNTER_REGISTER_VALUE_UNUSABLE");
        return 2;
    }
    puts("RESULT=PASS");
    return 0;
}
