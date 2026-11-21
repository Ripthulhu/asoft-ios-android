/* SPDX-License-Identifier: MIT
 * Exact native-owner supervisor from the verified one-region diagnostic.
 * build.py verifies this body against that frozen source before compiling.
 */
#ifndef REIMS_NATIVE_OWNER_H
#define REIMS_NATIVE_OWNER_H
#define _GNU_SOURCE 1
#include "../native-gpu-one-region/owner_control.h"
#include <stdlib.h>
#include <sys/prctl.h>
#include <sys/random.h>
#include <sys/syscall.h>
static void owner_signal(int signal_number)
{
    (void)signal_number;
    static const char text[] = "NATIVE_GPU_OWNER_INTERRUPTED_OR_DEADLINE=FAIL\nRESULT=FAIL\n";
    (void)write(STDERR_FILENO, text, sizeof(text) - 1);
    /* QEMU -> factory -> stub each arms PDEATHSIG and checks its captured
     * parent. Do not race numeric PID reuse from an asynchronous handler. */
    _exit(1);
}

static int owner_watchdog(void)
{
    struct sigaction sa = {.sa_handler = owner_signal};
    sigemptyset(&sa.sa_mask);
    if (sigaction(SIGALRM, &sa, NULL) || sigaction(SIGINT, &sa, NULL) ||
        sigaction(SIGTERM, &sa, NULL)) return -1;
    sa.sa_handler = SIG_IGN;
    if (sigaction(SIGPIPE, &sa, NULL)) return -1;
    sa.sa_handler = SIG_DFL;
    if (sigaction(SIGCHLD, &sa, NULL)) return -1;
    alarm(NGP_OWNER_TIMEOUT_SECONDS);
    return 0;
}

static void expected_words(uint32_t *out, bool completed)
{
    for (size_t i = 0; i < NGP_ALLOCATION_BYTES / sizeof(*out); i++)
        out[i] = NGP_GPU_FILL_BASE + (uint32_t)(i / (NGP_HOST_PAGE_BYTES / sizeof(*out)));
    if (completed) {
        uint64_t result = ngp_output(ngp_input());
        memcpy((char *)out + NGP_VIEW_OFFSET + 8, &result, sizeof(result));
    }
}

/* Called after Vulkan may have started threads: prepare all strings and FDs
 * before fork. Child uses only direct kernel/libc syscall wrappers and execve;
 * no allocation, stdio, Vulkan calls, environment edits or directory walking.
 */
static int run_engine(int producer, const char *directory)
{
    char qemu[PATH_MAX], guest[PATH_MAX], library[PATH_MAX + 32];
    char fd_env[64], event_env[64], owner_env[64], generation_env[80];
    int sockets[2] = {-1, -1}, keep_producer = -1, keep_event = -1, nullfd = -1;
    int result = -1, enabled = 1;
    NgpOwner state = {.owner = getpid(), .uid = getuid(), .gid = getgid()};
    if (snprintf(qemu, sizeof(qemu), "%s/qemu-system-aarch64", directory) >= (int)sizeof(qemu) ||
        snprintf(guest, sizeof(guest), "%s/native-gpu-guest.elf", directory) >= (int)sizeof(guest) ||
        snprintf(library, sizeof(library), "LD_LIBRARY_PATH=%s/lib", directory) >= (int)sizeof(library))
        goto done;
    if (getrandom(&state.generation, sizeof(state.generation), 0) != sizeof(state.generation) ||
        !state.generation) goto done;
    if (socketpair(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC, 0, sockets) ||
        setsockopt(sockets[0], SOL_SOCKET, SO_PASSCRED, &enabled, sizeof(enabled))) goto done;
    keep_producer = fcntl(producer, F_DUPFD_CLOEXEC, 100);
    keep_event = fcntl(sockets[1], F_DUPFD_CLOEXEC, 100);
    nullfd = open("/dev/null", O_RDONLY | O_CLOEXEC);
    if (keep_producer < 100 || keep_event < 100 || nullfd < 0) goto done;
    snprintf(fd_env, sizeof(fd_env), "ASOFT_NATIVE_GPU_FD=%d", keep_producer);
    snprintf(event_env, sizeof(event_env), "ASOFT_NATIVE_GPU_EVENT_FD=%d", keep_event);
    snprintf(owner_env, sizeof(owner_env), "ASOFT_NATIVE_GPU_OWNER_PID=%ld", (long)state.owner);
    snprintf(generation_env, sizeof(generation_env), "ASOFT_NATIVE_GPU_GENERATION=%" PRIu64, state.generation);
    char *const env[] = {
        "PATH=/system/bin", library,
        "ASOFT_NATIVE_EL0=1", "ASOFT_NATIVE_EL0_REQUIRED=1",
        "ASOFT_NATIVE_EL0_STUBS=1", "ASOFT_NATIVE_EL0_STATS=1",
        "ASOFT_NATIVE_EL0_TPIDRRO_TRAP=1", "ASOFT_NATIVE_GPU_ONE_REGION=1",
        fd_env, event_env, owner_env, generation_env, NULL
    };
    char *const args[] = {
        qemu, "-M", "virt,memory-backend=m0",
        "-object", "memory-backend-memfd,id=m0,size=512M,share=on",
        "-cpu", "max,pauth-impdef=on", "-smp", "1", "-m", "512",
        "-accel", "tcg,thread=single", "-kernel", guest,
        "-nographic", "-monitor", "none", "-serial", "stdio", "-nic", "none",
        "-no-reboot", "-no-user-config", NULL
    };
    fprintf(stdout, "OWNER_LAUNCH generation=%" PRIu64 " owner=%ld inherited_producer_fd=%d event_fd=%d"
            " EL1_setup=TCG EL0_payload=required_native cpu_count=1 workers=1\n",
            state.generation, (long)state.owner, keep_producer, keep_event);
    if (ngp_durable(stdout) || fflush(stderr)) goto done;
    state.leader = fork();
    if (state.leader == 0) {
        if (setpgid(0, 0) || prctl(PR_SET_PDEATHSIG, SIGKILL) ||
            getppid() != state.owner || dup2(nullfd, STDIN_FILENO) < 0 ||
            fcntl(keep_producer, F_SETFD, 0) || fcntl(keep_event, F_SETFD, 0)) _exit(120);
        unsigned first = (unsigned)(keep_producer < keep_event ? keep_producer : keep_event);
        unsigned last = (unsigned)(keep_producer > keep_event ? keep_producer : keep_event);
        if (syscall(__NR_close_range, 3u, first - 1, 0u) ||
            (first + 1 < last && syscall(__NR_close_range, first + 1, last - 1, 0u)) ||
            syscall(__NR_close_range, last + 1, UINT_MAX, 0u)) _exit(121);
        execve(qemu, args, env);
        _exit(122);
    }
    if (state.leader < 0) goto done;
    /* Until this verification, the child cannot execute QEMU unless its own
     * setpgid succeeded. A still-live or unreaped leader pins the identity. */
    int group_rc = setpgid(state.leader, state.leader);
    bool private_group = !group_rc || getpgid(state.leader) == state.leader;
    close(sockets[1]); sockets[1] = -1;
    close(keep_event); keep_event = -1;
    close(keep_producer); keep_producer = -1;
    close(nullfd); nullfd = -1;
    if (!private_group) {
        fputs("OWNER_PRIVATE_GROUP=FAIL\n", stdout);
        (void)ngp_close_tree(state.leader, false, stdout, NGP_REAP_TIMEOUT_MS);
        goto done;
    }
    result = ngp_supervise(sockets[0], &state, stdout, NGP_ENGINE_TIMEOUT_MS, NGP_REAP_TIMEOUT_MS);
    fprintf(stdout, "OWNER_NATIVE_PROTOCOL=%s phase=%u\n", result ? "FAIL" : "PASS", state.phase);
    if (ngp_durable(stdout)) result = -1;
done:
    if (nullfd >= 0) close(nullfd);
    if (keep_producer >= 0) close(keep_producer);
    if (keep_event >= 0) close(keep_event);
    if (sockets[0] >= 0) close(sockets[0]);
    if (sockets[1] >= 0) close(sockets[1]);
    return result;
}

#endif
