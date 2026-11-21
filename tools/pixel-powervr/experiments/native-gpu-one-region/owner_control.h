/* SPDX-License-Identifier: MIT
 * Owner-side event validation and bounded descendant closure. No GPU calls.
 * Included by the production owner and ordinary-host adversarial fixtures.
 */
#ifndef PIXEL_NATIVE_GPU_OWNER_CONTROL_H
#define PIXEL_NATIVE_GPU_OWNER_CONTROL_H

#include "native_gpu_protocol.h"
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <poll.h>
#include <signal.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

typedef struct NgpOwner {
    pid_t owner, leader;
    uid_t uid;
    gid_t gid;
    uint64_t generation, factory, stub, tid, invalidation;
    unsigned phase;
} NgpOwner;

static int64_t ngp_now_ms(void)
{
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts)) return -1;
    return (int64_t)ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}

static int ngp_durable(FILE *log)
{
    struct stat st;
    int fd = fileno(log);
    return fflush(log) || ferror(log) || fstat(fd, &st) ||
           !S_ISREG(st.st_mode) || fsync(fd) ? -1 : 0;
}

static bool ngp_pid(uint64_t p)
{
    return p > 0 && p <= INT_MAX;
}

/* No state is committed until the caller has durably written this event.
 * The caller copies the state, validates, writes+fsyncs, sends ACK, then commits.
 */
static const char *ngp_validate(NgpOwner *s, const NgpPacket *p)
{
    if (s->phase >= NGP_COMPLETE || p->phase != s->phase + 1 ||
        p->sequence != p->phase || p->magic != NGP_MAGIC ||
        p->version != NGP_PROTOCOL_VERSION || p->bytes != sizeof(*p) ||
        p->kind != NGP_EVENT || p->status) return "header/order";
    for (size_t i = 0; i < sizeof(p->reserved) / sizeof(p->reserved[0]); i++)
        if (p->reserved[i]) return "reserved field";
    if (p->run_generation != s->generation || !s->generation ||
        p->owner_pid != (uint64_t)s->owner ||
        p->qemu_pid != (uint64_t)s->leader) return "run/process identity";
    if (p->gpa != NGP_GPA || p->va != NGP_DATA_VA ||
        p->allocation_bytes != NGP_ALLOCATION_BYTES ||
        p->backing_offset != NGP_VIEW_OFFSET || p->view_bytes != NGP_VIEW_BYTES ||
        memcmp(p->code_sha256, ngp_code_sha256, sizeof(ngp_code_sha256)) ||
        p->proof_flags != ngp_phase_flags(p->phase)) return "geometry/hash/flags";
    if (!ngp_pid(p->factory_pid) || p->factory_pid == (uint64_t)s->leader ||
        p->factory_pid == (uint64_t)s->owner) return "factory identity";
    if (p->phase == NGP_READY) {
        if (p->stub_pid || p->worker_tid || p->inval_generation || p->pc ||
            p->fault_address || p->access || p->input || p->output ||
            p->instruction) return "READY fields";
        s->factory = p->factory_pid;
    } else {
        if (p->factory_pid != s->factory || !ngp_pid(p->stub_pid) ||
            !ngp_pid(p->worker_tid) || p->stub_pid == s->factory ||
            p->stub_pid == (uint64_t)s->leader || p->stub_pid == (uint64_t)s->owner ||
            p->worker_tid == p->stub_pid || p->worker_tid == s->factory ||
            p->worker_tid == (uint64_t)s->leader || p->worker_tid == (uint64_t)s->owner)
            return "worker identity";
        if (p->phase == NGP_ENTRY) {
            s->stub = p->stub_pid;
            s->tid = p->worker_tid;
            s->invalidation = p->inval_generation;
        } else if (p->stub_pid != s->stub || p->worker_tid != s->tid ||
                   p->inval_generation != s->invalidation) return "worker/generation changed";
        if (p->phase == NGP_ENTRY || p->phase == NGP_CODE_MAP) {
            bool mapped = p->phase == NGP_CODE_MAP;
            if (p->pc != NGP_CODE_VA || p->instruction != ngp_payload_words[0] ||
                p->fault_address != (mapped ? NGP_CODE_VA : 0) ||
                p->access != (mapped ? NGP_ACCESS_EXEC : NGP_ACCESS_NONE) ||
                p->input || p->output) return "code entry/map fields";
        } else if (p->phase == NGP_DATA_FAULT || p->phase == NGP_DATA_MAP) {
            if (p->pc != NGP_LOAD_PC || p->fault_address != NGP_DATA_VA ||
                p->access != NGP_ACCESS_READ || p->instruction != ngp_payload_words[2] ||
                p->input || p->output) return "data fault/map fields";
        } else if (p->phase == NGP_COMPLETE) {
            if (p->pc != NGP_COMPLETE_PC || p->fault_address || p->access ||
                p->input != ngp_input() || p->output != ngp_output(ngp_input()) ||
                p->instruction != ngp_payload_words[8]) return "native completion fields";
        } else return "unknown phase";
    }
    s->phase = p->phase;
    return NULL;
}

/* Return 1 for one complete credentialed packet, 0 for closed peer, -1 invalid,
 * -2 for EAGAIN/EINTR. Unexpected delivered rights are closed on every path.
 */
static int ngp_receive(int fd, const NgpOwner *s, NgpPacket *p)
{
    union {
        struct cmsghdr align;
        char data[CMSG_SPACE(sizeof(struct ucred)) + CMSG_SPACE(16 * sizeof(int))];
    } control = {0};
    struct iovec iov = {.iov_base = p, .iov_len = sizeof(*p)};
    struct msghdr message = {.msg_iov = &iov, .msg_iovlen = 1,
        .msg_control = control.data, .msg_controllen = sizeof(control.data)};
    ssize_t n = recvmsg(fd, &message, MSG_DONTWAIT | MSG_CMSG_CLOEXEC);
    if (n < 0) return errno == EAGAIN || errno == EINTR ? -2 : -1;
    bool bad = (message.msg_flags & (MSG_TRUNC | MSG_CTRUNC)) != 0;
    unsigned credentials = 0;
    for (struct cmsghdr *c = CMSG_FIRSTHDR(&message); c; c = CMSG_NXTHDR(&message, c)) {
        if (c->cmsg_len < CMSG_LEN(0)) { bad = true; break; }
        if (c->cmsg_level == SOL_SOCKET && c->cmsg_type == SCM_RIGHTS) {
            size_t bytes = c->cmsg_len - CMSG_LEN(0);
            for (size_t i = 0; i + sizeof(int) <= bytes; i += sizeof(int)) {
                int received;
                memcpy(&received, (char *)CMSG_DATA(c) + i, sizeof(received));
                close(received);
            }
            bad = true;
        } else if (c->cmsg_level == SOL_SOCKET && c->cmsg_type == SCM_CREDENTIALS &&
                   c->cmsg_len == CMSG_LEN(sizeof(struct ucred))) {
            struct ucred cr;
            memcpy(&cr, CMSG_DATA(c), sizeof(cr));
            credentials++;
            if (cr.pid != s->leader || cr.uid != s->uid || cr.gid != s->gid) bad = true;
        } else bad = true;
    }
    if (!n && !credentials && !bad) {
        struct pollfd poller = {.fd = fd, .events = POLLIN | POLLHUP};
        if (poll(&poller, 1, 0) >= 0 && (poller.revents & POLLHUP)) return 0;
    }
    return n == sizeof(*p) && credentials == 1 && !bad ? 1 : -1;
}

static int ngp_checkpoint_ack(int fd, FILE *log, NgpOwner *state, const NgpPacket *event)
{
    NgpOwner next = *state;
    const char *invalid = ngp_validate(&next, event);
    if (invalid) {
        fprintf(log, "OWNER_PROTOCOL_FAIL reason=%s phase=%u\n", invalid, event->phase);
        return -1;
    }
    fprintf(log, "OWNER_EVENT phase=%s sequence=%u generation=%" PRIu64
            " invalidation=%" PRIu64 " owner=%" PRIu64 " qemu=%" PRIu64
            " factory=%" PRIu64 " stub=%" PRIu64 " tid=%" PRIu64
            " pc=0x%" PRIx64 " address=0x%" PRIx64 " access=%" PRIu64
            " input=0x%016" PRIx64 " output=0x%016" PRIx64
            " instruction=0x%08" PRIx64 " flags=0x%" PRIx64 "\n",
            ngp_phase_name(event->phase), event->sequence, event->run_generation,
            event->inval_generation, event->owner_pid, event->qemu_pid,
            event->factory_pid, event->stub_pid, event->worker_tid,
            event->pc, event->fault_address, event->access, event->input,
            event->output, event->instruction, event->proof_flags);
    if (ngp_durable(log)) return -1;
    NgpPacket ack = *event;
    ack.kind = NGP_ACK;
    if (send(fd, &ack, sizeof(ack), MSG_DONTWAIT | MSG_NOSIGNAL) != sizeof(ack)) return -1;
    *state = next;
    return 0;
}

/* Never reap the leader before the one group signal. A live or WNOWAIT zombie
 * leader pins the numeric PGID; after releasing it we never signal that PGID.
 * ECHILD is mandatory before a caller may touch the producer again.
 */
static int ngp_close_tree(pid_t leader, bool group_owned, FILE *log, int timeout_ms)
{
    int64_t now = ngp_now_ms(), deadline = now + timeout_ms;
    if (now < 0 || leader <= 0) return -1;
    errno = 0;
    int killed = kill(group_owned ? -leader : leader, SIGKILL);
    if (killed && errno != ESRCH) {
        fprintf(log, "OWNER_TREE_FAIL signal_errno=%d\n", errno);
        return -1;
    }
    bool leader_reaped = false;
    unsigned reaped = 0;
    for (;;) {
        int status = 0;
        pid_t p = waitpid(-1, &status, WNOHANG);
        if (p > 0) {
            if (p == leader) leader_reaped = true;
            reaped++;
            fprintf(log, "OWNER_REAP pid=%ld raw_status=%d\n", (long)p, status);
            continue;
        }
        if (p < 0 && errno == EINTR) continue;
        if (p < 0 && errno == ECHILD) {
            fprintf(log, "OWNER_TREE_CLOSED leader_reaped=%u reaped=%u ECHILD=1 group_signals=1\n",
                    leader_reaped, reaped);
            return leader_reaped && !ngp_durable(log) ? 0 : -1;
        }
        now = ngp_now_ms();
        if (p < 0 || now < 0 || now >= deadline) {
            fprintf(log, "OWNER_TREE_FAIL reason=reap_deadline_or_error leader_reaped=%u reaped=%u\n",
                    leader_reaped, reaped);
            return -1;
        }
        (void)poll(NULL, 0, 5);
    }
}

/* Returns success only for all six saved/ACKed events, exact leader exit 0,
 * peer closure without surplus data, and complete bounded descendant reap.
 * Failure is sticky; even a subsequent successful cleanup cannot permit GPU.
 */
static int ngp_supervise(int fd, NgpOwner *state, FILE *log,
                         int engine_timeout_ms, int reap_timeout_ms)
{
    int64_t now = ngp_now_ms(), deadline = now + engine_timeout_ms;
    bool good_exit = false, peer_closed = false;
    int result = -1;
    if (now < 0) goto cleanup;
    for (;;) {
        NgpPacket event = {0};
        int received = peer_closed ? -2 : ngp_receive(fd, state, &event);
        if (received == 1) {
            if (ngp_checkpoint_ack(fd, log, state, &event)) goto cleanup;
        } else if (received == 0) {
            peer_closed = true;
            if (state->phase != NGP_COMPLETE) goto cleanup;
        } else if (received == -1) {
            fputs("OWNER_PROTOCOL_FAIL reason=packet_or_credentials\n", log);
            goto cleanup;
        }
        siginfo_t si = {0};
        if (waitid(P_PID, (id_t)state->leader, &si, WEXITED | WNOHANG | WNOWAIT)) {
            if (errno == EINTR) continue;
            goto cleanup;
        }
        if (si.si_pid) {
            if (si.si_pid != state->leader || si.si_code != CLD_EXITED || si.si_status != 0) {
                fprintf(log, "OWNER_QEMU_EXIT_FAIL pid=%ld code=%d status=%d\n",
                        (long)si.si_pid, si.si_code, si.si_status);
                goto cleanup;
            }
            good_exit = true;
            if (peer_closed && state->phase == NGP_COMPLETE) { result = 0; break; }
        }
        now = ngp_now_ms();
        if (now < 0 || now >= deadline) {
            fputs("OWNER_ENGINE_DEADLINE=FAIL\n", log);
            goto cleanup;
        }
        struct pollfd p = {.fd = fd, .events = POLLIN | POLLHUP};
        int wait = (int)(deadline - now);
        if (wait > 10) wait = 10;
        if (peer_closed) (void)poll(NULL, 0, wait);
        else if (poll(&p, 1, wait) < 0 && errno != EINTR) goto cleanup;
    }
cleanup:
    fprintf(log, "OWNER_ENGINE_STOP phase=%u clean_exit=%u protocol_complete=%u\n",
            state->phase, good_exit, result == 0);
    if (ngp_close_tree(state->leader, true, log, reap_timeout_ms)) result = -1;
    if (!result && ngp_durable(log)) result = -1;
    return result;
}
#endif
