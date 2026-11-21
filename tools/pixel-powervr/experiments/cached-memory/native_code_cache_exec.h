/* SPDX-License-Identifier: MIT
 * Fresh-exec CPU-only recipient of a real SCM_RIGHTS FD. No Vulkan API calls.
 */
#ifndef PIXEL_NATIVE_CODE_CACHE_EXEC_H
#define PIXEL_NATIVE_CODE_CACHE_EXEC_H

#include "native_code_cache.h"
#include <fcntl.h>
#include <limits.h>
#include <poll.h>
#include <spawn.h>
#include <sys/prctl.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <time.h>

extern char **environ;
enum { NA_CHILD_SOCKET = 198, NA_IPC_MS = 25000, NA_REAP_MS = 2000 };
typedef struct NaRequest {
    uint32_t magic, protocol, variant, bytes, page, offset, span, initial, cpu_atomics;
} NaRequest;

static int na_poll(int fd, short events, int64_t deadline)
{
    for (;;) {
        int64_t now = na_now_ms();
        if (now < 0) return -1;
        if (now >= deadline) { errno = ETIMEDOUT; return -1; }
        int remaining = (int)(deadline - now);
        struct pollfd p = {.fd = fd, .events = events};
        int result = poll(&p, 1, remaining);
        if (result < 0 && errno == EINTR) continue;
        if (result > 0 && (p.revents & events)) return 0;
        if (!result) errno = ETIMEDOUT;
        else if (result > 0) errno = EPIPE;
        return -1;
    }
}

static int na_send(int socket, const void *body, size_t bytes, int fd, int64_t deadline)
{
    struct iovec iov = {.iov_base = (void *)body, .iov_len = bytes};
    union { struct cmsghdr alignment; unsigned char data[CMSG_SPACE(sizeof(int))]; } control;
    memset(&control, 0, sizeof(control));
    struct msghdr message = {.msg_iov = &iov, .msg_iovlen = 1};
    if (fd >= 0) {
        message.msg_control = control.data;
        message.msg_controllen = sizeof(control.data);
        struct cmsghdr *c = CMSG_FIRSTHDR(&message);
        c->cmsg_level = SOL_SOCKET;
        c->cmsg_type = SCM_RIGHTS;
        c->cmsg_len = CMSG_LEN(sizeof(int));
        memcpy(CMSG_DATA(c), &fd, sizeof(fd));
    }
    for (;;) {
        if (na_poll(socket, POLLOUT, deadline)) return -1;
        ssize_t sent = sendmsg(socket, &message, MSG_NOSIGNAL | MSG_DONTWAIT);
        if (sent < 0 && (errno == EINTR || errno == EAGAIN || errno == EWOULDBLOCK)) continue;
        if (sent != (ssize_t)bytes) { if (sent >= 0) errno = EIO; return -1; }
        return 0;
    }
}

static int na_receive(int socket, void *body, size_t bytes, int *fd, int64_t deadline)
{
    /* Enough space to inspect and close a malformed small rights set. Linux
     * closes rights truncated beyond this receive buffer; rights actually
     * received here are all closed unless exactly the requested one is valid. */
    union { struct cmsghdr alignment; unsigned char data[CMSG_SPACE(4 * sizeof(int))]; } control;
    for (;;) {
        if (na_poll(socket, POLLIN, deadline)) return -1;
        memset(&control, 0, sizeof(control));
        struct iovec iov = {.iov_base = body, .iov_len = bytes};
        struct msghdr message = {.msg_iov = &iov, .msg_iovlen = 1,
                                .msg_control = control.data, .msg_controllen = sizeof(control.data)};
        ssize_t received = recvmsg(socket, &message, MSG_CMSG_CLOEXEC | MSG_DONTWAIT);
        if (received < 0 && (errno == EINTR || errno == EAGAIN || errno == EWOULDBLOCK)) continue;
        int rights[4], count = 0, malformed = 0, headers = 0;
        if (received >= 0) for (struct cmsghdr *c = CMSG_FIRSTHDR(&message);
                               c; c = CMSG_NXTHDR(&message, c)) {
            ++headers;
            if (c->cmsg_level != SOL_SOCKET || c->cmsg_type != SCM_RIGHTS ||
                c->cmsg_len < CMSG_LEN(0)) { malformed = 1; continue; }
            size_t payload = c->cmsg_len - CMSG_LEN(0);
            if (payload % sizeof(int)) malformed = 1;
            for (size_t i = 0; i < payload / sizeof(int); ++i) {
                int received_fd;
                memcpy(&received_fd, (unsigned char *)CMSG_DATA(c) + i * sizeof(int), sizeof(int));
                if (count < 4) rights[count++] = received_fd;
                else { close(received_fd); malformed = 1; }
            }
        }
        if (received != (ssize_t)bytes || (message.msg_flags & (MSG_TRUNC | MSG_CTRUNC)) ||
            malformed || (fd ? count != 1 || headers != 1 : headers != 0)) {
            for (int i = 0; i < count; ++i) close(rights[i]);
            errno = EPROTO; return -1;
        }
        if (fd) *fd = rights[0];
        return 0;
    }
}

static int na_reap(pid_t pid, int *status, int64_t deadline)
{
    for (;;) {
        pid_t got = waitpid(pid, status, WNOHANG);
        if (got == pid) return 0;
        if (got < 0 && errno != EINTR) return -1;
        int64_t now = na_now_ms();
        if (now < 0) return -1;
        if (now >= deadline) { errno = ETIMEDOUT; return -1; }
        (void)poll(NULL, 0, deadline - now < 20 ? (int)(deadline - now) : 20);
    }
}

static void na_kill_reap(pid_t pid)
{
    int status;
    pid_t observed;
    do { observed = waitpid(pid, &status, WNOHANG); } while (observed < 0 && errno == EINTR);
    if (observed == pid) return;
    if (observed < 0) {
        puts("FAIL: lost child ownership before kill; stopping without signaling a possibly reused PID");
        fflush(NULL);
        _Exit(1);
    }
    (void)kill(pid, SIGKILL);
    int64_t now = na_now_ms();
    if (now < 0 || na_reap(pid, &status, now + NA_REAP_MS)) {
        puts("FAIL: child could not be reaped within deadline; producer lifetime ends only with process exit");
        fflush(NULL);
        _Exit(1);
    }
}

static int na_child_entry(int argc, char **argv)
{
    /* This branch is entered after exec, before any Vulkan initialization.
     * Parent-death protection is armed before receiving or mapping the FD. */
    if (argc != 4 || strcmp(argv[1], "--cached-memory-child")) return 1;
    na_process_role = "fresh_exec_child";
    char *end = NULL;
    long socket_value = strtol(argv[2], &end, 10);
    if (!end || *end || socket_value != NA_CHILD_SOCKET) return 1;
    end = NULL;
    long parent_value = strtol(argv[3], &end, 10);
    if (!end || *end || parent_value <= 1 || parent_value > INT_MAX) return 1;
    int death_signal = 0;
    if (prctl(PR_SET_PDEATHSIG, SIGKILL) || prctl(PR_GET_PDEATHSIG, &death_signal) ||
        death_signal != SIGKILL || getppid() != (pid_t)parent_value) return 1;
    na_reply_fd = NA_CHILD_SOCKET;
    na_stage = na_verified_stage = NA_INITIAL;
    na_exec_phase = 0;
    na_memory_state = NA_MEMORY_UNTESTED;
    na_memory_phase = 0;
    if (na_watchdog(25)) return 1;
    printf("NATIVE_CODE_CACHE_FRESH_EXEC_CHILD variant=ordinary_memfd_instruction_copy pid=%lu ppid=%lu uid=%lu euid=%lu Vulkan_calls=no inherited_VMAs=no pdeathsig=SIGKILL watchdog_seconds=25\n",
           (unsigned long)getpid(), (unsigned long)getppid(), (unsigned long)getuid(), (unsigned long)geteuid());
    NaRequest request = {0};
    NaReply reply = {NA_MAGIC, NA_PROTOCOL, NA_VARIANT_CODE_CACHE, 1,
                    NA_INITIAL, NA_INITIAL, NA_MEMORY_UNTESTED, 0};
    int fd = -1, result = 1;
    void *canonical = MAP_FAILED;
    int64_t now = na_now_ms();
    if (now < 0 || na_receive(NA_CHILD_SOCKET, &request, sizeof(request), &fd, now + NA_IPC_MS)) {
        printf("FAIL: child receive exported FD errno=%d\n", errno); goto done;
    }
    if (request.magic != NA_MAGIC || request.protocol != NA_PROTOCOL || request.variant != NA_VARIANT_CODE_CACHE || request.bytes != NA_BYTES ||
        request.page != NA_HOST_PAGE || request.offset != NA_OFFSET || request.span != NA_SPAN ||
        request.cpu_atomics > 1 || sysconf(_SC_PAGESIZE) != NA_HOST_PAGE) {
        puts("FAIL: child request shape/host page mismatch"); goto done;
    }
    na_cpu_atomics = request.cpu_atomics;
    reply.cpu_atomics = na_cpu_atomics;
    int fd_flags = fcntl(fd, F_GETFD);
    if (fd_flags < 0 || !(fd_flags & FD_CLOEXEC)) { puts("FAIL: received FD lacks close-on-exec"); goto done; }
    printf("NATIVE_CODE_CACHE_SCM_RIGHTS=PASS same_producer_fd=yes producer_backing=%s source=inherited_private_socket_only protocol=%d variant=%d\n", NA_PRODUCER_NAME, NA_PROTOCOL, NA_VARIANT_CODE_CACHE);
    if (na_checkpoint("before_fresh_child_canonical_FD_mmap")) goto done;
    canonical = mmap(NULL, NA_BYTES, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (canonical == MAP_FAILED) {
        printf("NATIVE_CODE_CACHE_CHILD_FULL_MAP=UNSUPPORTED errno=%d message=%s\n", errno, strerror(errno));
        result = NA_UNSUPPORTED; goto done;
    }
    na_mapping_report(canonical, NA_BYTES, "fresh_exec_canonical_FD_map");
    result = na_exercise(fd, canonical, request.initial, 1, &reply);
done:
    if (canonical != MAP_FAILED && munmap(canonical, NA_BYTES)) result = 1;
    if (fd >= 0) close(fd);
    reply.status = (uint32_t)result;
    reply.stage = (uint32_t)na_stage;
    reply.verified_stage = (uint32_t)na_verified_stage;
    reply.memory_state = (uint32_t)na_memory_state;
    reply.cpu_atomics = na_cpu_atomics;
    now = na_now_ms();
    if (now < 0 || na_send(NA_CHILD_SOCKET, &reply, sizeof(reply), -1, now + 1000)) result = 1;
    printf("NATIVE_CODE_CACHE_CHILD_RESULT status=%d stage=%u verified_stage=%u memory_state=%u\n",
           result, reply.stage, reply.verified_stage, reply.memory_state);
    na_reply_fd = -1;
    close(NA_CHILD_SOCKET);
    alarm(0);
    return result;
}

static int na_run_child(int producer_fd, uint32_t initial, NaReply *reply)
{
    if (na_checkpoint("before_fresh_exec_child_setup")) return 1;
    int sockets[2] = {-1, -1}, status = 0, result = 1;
    pid_t pid = -1;
    char executable[4096], parent_text[32], socket_text[32];
    ssize_t path_length = readlink("/proc/self/exe", executable, sizeof(executable) - 1);
    if (path_length <= 0 || path_length >= (ssize_t)sizeof(executable) - 1) return 1;
    executable[path_length] = '\0';
    int flags = fcntl(producer_fd, F_GETFD);
    if (flags < 0 || fcntl(producer_fd, F_SETFD, flags | FD_CLOEXEC)) return 1;
    if (socketpair(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC | SOCK_NONBLOCK, 0, sockets)) return 1;
    if (sockets[1] == NA_CHILD_SOCKET) {
        int duplicate = fcntl(sockets[1], F_DUPFD_CLOEXEC, NA_CHILD_SOCKET + 1);
        if (duplicate < 0) goto done;
        close(sockets[1]); sockets[1] = duplicate;
    }
    posix_spawn_file_actions_t actions;
    if (posix_spawn_file_actions_init(&actions)) goto done;
    int action_error = posix_spawn_file_actions_adddup2(&actions, sockets[1], NA_CHILD_SOCKET);
    if (!action_error && sockets[0] != NA_CHILD_SOCKET)
        action_error = posix_spawn_file_actions_addclose(&actions, sockets[0]);
    if (!action_error) action_error = posix_spawn_file_actions_addclose(&actions, sockets[1]);
    snprintf(parent_text, sizeof(parent_text), "%lu", (unsigned long)getpid());
    snprintf(socket_text, sizeof(socket_text), "%d", NA_CHILD_SOCKET);
    char *arguments[] = {executable, "--cached-memory-child", socket_text, parent_text, NULL};
    if (!action_error && na_checkpoint("before_fresh_exec_child_spawn")) action_error = EIO;
    int spawn_error = action_error ? action_error : posix_spawn(&pid, executable, &actions, NULL, arguments, environ);
    posix_spawn_file_actions_destroy(&actions);
    if (spawn_error) { printf("FAIL: posix_spawn child error=%d\n", spawn_error); pid = -1; goto done; }
    close(sockets[1]); sockets[1] = -1;
    int64_t now = na_now_ms();
    if (now < 0) goto stop;
    int64_t deadline = now + NA_IPC_MS;
    NaRequest request = {NA_MAGIC, NA_PROTOCOL, NA_VARIANT_CODE_CACHE, NA_BYTES, NA_HOST_PAGE, NA_OFFSET, NA_SPAN, initial, na_cpu_atomics};
    if (na_send(sockets[0], &request, sizeof(request), producer_fd, deadline) ||
        na_receive(sockets[0], reply, sizeof(*reply), NULL, deadline)) {
        printf("FAIL: child IPC/deadline errno=%d message=%s\n", errno, strerror(errno)); goto stop;
    }
    now = na_now_ms();
    if (now < 0 || na_reap(pid, &status, now + NA_REAP_MS)) {
        printf("FAIL: child exit deadline errno=%d\n", errno); goto stop;
    }
    pid = -1;
    if (reply->magic != NA_MAGIC || reply->protocol != NA_PROTOCOL || reply->variant != NA_VARIANT_CODE_CACHE || reply->cpu_atomics != (uint32_t)na_cpu_atomics ||
        reply->stage > NA_LAST_STAGE || reply->verified_stage > reply->stage ||
        reply->memory_state > NA_MEMORY_PASSED ||
        (reply->status != 0 && reply->status != 1 && reply->status != NA_UNSUPPORTED) ||
        !WIFEXITED(status) || WEXITSTATUS(status) != (int)reply->status) {
        puts("FAIL: malformed/inconsistent child reply or exit status"); goto done;
    }
    if (reply->status != 1 && (reply->stage != reply->verified_stage ||
                               reply->memory_state == NA_MEMORY_DIRTY)) {
        puts("FAIL: child reported pass/unsupported with unverified data or memory-preflight writes"); goto done;
    }
    if (!reply->status && (reply->stage != NA_LAST_STAGE ||
                          reply->memory_state != NA_MEMORY_PASSED)) {
        puts("FAIL: child reported pass without memory preflight and every code-cache generation"); goto done;
    }
    printf("NATIVE_CODE_CACHE_FRESH_EXEC_REAP=PASS exit=%u stage=%u verified_stage=%u memory_state=%u cpu_atomics=%u child_stopped_before_parent_GPU_access=yes\n",
           reply->status, reply->stage, reply->verified_stage, reply->memory_state, reply->cpu_atomics);
    result = (int)reply->status;
    goto done;
stop:
    na_kill_reap(pid);
    pid = -1;
done:
    if (sockets[0] >= 0) close(sockets[0]);
    if (sockets[1] >= 0) close(sockets[1]);
    return result;
}

#endif
