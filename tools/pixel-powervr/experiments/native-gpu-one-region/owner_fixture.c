/* SPDX-License-Identifier: MIT
 * Real Linux sockets/forks/reaping and an ordinary memfd mapping fixture.
 * This does not execute AArch64 or exercise a GPU/Android driver.
 */
#define _GNU_SOURCE
#include "owner_control.h"
#include <assert.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <sys/prctl.h>

static NgpPacket packet(const NgpOwner *s, unsigned phase)
{
    NgpPacket p = {.magic = NGP_MAGIC, .version = NGP_PROTOCOL_VERSION,
        .bytes = sizeof(p), .kind = NGP_EVENT, .phase = phase, .sequence = phase,
        .run_generation = s->generation, .owner_pid = s->owner, .qemu_pid = s->leader,
        .factory_pid = 1111111, .gpa = NGP_GPA, .va = NGP_DATA_VA,
        .allocation_bytes = NGP_ALLOCATION_BYTES, .backing_offset = NGP_VIEW_OFFSET,
        .view_bytes = NGP_VIEW_BYTES, .proof_flags = ngp_phase_flags(phase)};
    memcpy(p.code_sha256, ngp_code_sha256, sizeof(p.code_sha256));
    if (phase >= NGP_ENTRY) {
        p.stub_pid = 1111112;
        p.worker_tid = 1111113;
        p.inval_generation = 17;
    }
    if (phase == NGP_ENTRY || phase == NGP_CODE_MAP) {
        p.pc = NGP_CODE_VA; p.instruction = ngp_payload_words[0];
        if (phase == NGP_CODE_MAP) { p.fault_address = NGP_CODE_VA; p.access = NGP_ACCESS_EXEC; }
    } else if (phase == NGP_DATA_FAULT || phase == NGP_DATA_MAP) {
        p.pc = NGP_LOAD_PC; p.fault_address = NGP_DATA_VA;
        p.access = NGP_ACCESS_READ; p.instruction = ngp_payload_words[2];
    } else if (phase == NGP_COMPLETE) {
        p.pc = NGP_COMPLETE_PC; p.input = ngp_input();
        p.output = ngp_output(p.input); p.instruction = ngp_payload_words[8];
    }
    return p;
}

static void validate_bits(void)
{
    NgpOwner s = {.owner = 40, .leader = 41, .generation = 99};
    unsigned rejected = 0;
    for (unsigned phase = NGP_READY; phase <= NGP_COMPLETE; phase++) {
        NgpPacket p = packet(&s, phase);
        if (phase >= NGP_CODE_MAP) {
            for (size_t bit = 0; bit < sizeof(p) * CHAR_BIT; bit++) {
                NgpPacket bad = p;
                ((unsigned char *)&bad)[bit / CHAR_BIT] ^= 1u << (bit % CHAR_BIT);
                NgpOwner trial = s;
                assert(ngp_validate(&trial, &bad));
                rejected++;
            }
        }
        assert(!ngp_validate(&s, &p));
        assert(ngp_validate(&s, &p)); /* replay */
    }
    assert(s.phase == NGP_COMPLETE && rejected == 8192);
    assert(ngp_input() == UINT64_C(0x6a1b2c346a1b2c34));
    assert(ngp_output(ngp_input()) == UINT64_C(0x615c5026615c515d));
    printf("WIRE_VALIDATION=PASS single_bit_corruptions_rejected=%u replays_rejected=6\n", rejected);
}

enum Case { GOOD, DUPLICATE, BAD_PC, BAD_OUTPUT, RIGHTS, TRUNCATED, WRONG_SENDER,
            HANG, EARLY_EXIT, SURPLUS, NONREGULAR_LOG, REAP_DEADLINE, CASES };
static const char *const names[] = {"good_with_orphan", "duplicate", "bad_pc", "bad_output",
    "unexpected_rights", "truncated_packet", "wrong_sender", "engine_deadline",
    "early_exit", "surplus_packet", "nonregular_log_blocks_ack", "reap_deadline_blocks_gpu"};

static void fake_engine(int fd, int report, NgpOwner state, enum Case which)
{
    assert(!setpgid(0, 0));
    state.leader = getpid();
    alarm(5);
    pid_t descendant = fork();
    assert(descendant >= 0);
    if (!descendant) {
        if (which == REAP_DEADLINE) assert(setsid() == getpid());
        pid_t me = getpid();
        assert(write(report, &me, sizeof(me)) == sizeof(me));
        close(report);
        if (which == WRONG_SENDER) {
            NgpPacket p = packet(&state, NGP_READY);
            assert(send(fd, &p, sizeof(p), MSG_NOSIGNAL) == sizeof(p));
        }
        close(fd);
        /* Deliberately survives leader exit until owner's one group signal. */
        for (;;) pause();
    }
    close(report);
    if (which == HANG || which == WRONG_SENDER) for (;;) pause();
    if (which == EARLY_EXIT) _exit(0);
    for (unsigned phase = NGP_READY; phase <= NGP_COMPLETE; phase++) {
        NgpPacket p = packet(&state, phase), ack;
        if (which == DUPLICATE && phase == NGP_ENTRY) p = packet(&state, NGP_READY);
        if (which == BAD_PC && phase == NGP_DATA_MAP) p.pc += 4;
        if (which == BAD_OUTPUT && phase == NGP_COMPLETE) p.output ^= 1;
        if (which == RIGHTS && phase == NGP_READY) {
            int extra = open("/dev/null", O_RDONLY);
            assert(extra >= 0);
            union { struct cmsghdr align; char data[CMSG_SPACE(sizeof(int))]; } control = {0};
            struct iovec iov = {.iov_base = &p, .iov_len = sizeof(p)};
            struct msghdr msg = {.msg_iov = &iov, .msg_iovlen = 1,
                .msg_control = control.data, .msg_controllen = sizeof(control.data)};
            struct cmsghdr *c = CMSG_FIRSTHDR(&msg);
            c->cmsg_level = SOL_SOCKET; c->cmsg_type = SCM_RIGHTS; c->cmsg_len = CMSG_LEN(sizeof(int));
            memcpy(CMSG_DATA(c), &extra, sizeof(extra));
            assert(sendmsg(fd, &msg, MSG_NOSIGNAL) == sizeof(p));
            close(extra);
        } else if (which == TRUNCATED && phase == NGP_READY) {
            char bigger[sizeof(p) + 1];
            memcpy(bigger, &p, sizeof(p)); bigger[sizeof(p)] = 0;
            assert(send(fd, bigger, sizeof(bigger), MSG_NOSIGNAL) == sizeof(bigger));
        } else assert(send(fd, &p, sizeof(p), MSG_NOSIGNAL) == sizeof(p));
        ssize_t n;
        do { n = recv(fd, &ack, sizeof(ack), 0); } while (n < 0 && errno == EINTR);
        if (n != sizeof(ack)) _exit(10);
        p.kind = NGP_ACK;
        if (memcmp(&p, &ack, sizeof(ack))) _exit(11);
    }
    if (which == SURPLUS) {
        NgpPacket p = packet(&state, NGP_COMPLETE);
        assert(send(fd, &p, sizeof(p), MSG_NOSIGNAL) == sizeof(p));
    }
    close(fd);
    _exit(0);
}

static void lifecycle(void)
{
    assert(!prctl(PR_SET_CHILD_SUBREAPER, 1));
    for (enum Case which = GOOD; which < CASES; which++) {
        int sv[2], report[2], enabled = 1;
        assert(!pipe2(report, O_CLOEXEC));
        assert(!socketpair(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC, 0, sv));
        assert(!setsockopt(sv[0], SOL_SOCKET, SO_PASSCRED, &enabled, sizeof(enabled)));
        FILE *log = which == NONREGULAR_LOG ? fopen("/dev/null", "w") : tmpfile();
        assert(log);
        NgpOwner state = {.owner = getpid(), .uid = getuid(), .gid = getgid(), .generation = 99};
        state.leader = fork();
        assert(state.leader >= 0);
        if (!state.leader) {
            close(sv[0]); close(report[0]);
            fake_engine(sv[1], report[1], state, which);
        }
        close(sv[1]);
        close(report[1]);
        int rc = setpgid(state.leader, state.leader);
        assert(!rc || getpgid(state.leader) == state.leader);
        pid_t descendant;
        assert(read(report[0], &descendant, sizeof(descendant)) == sizeof(descendant));
        close(report[0]);
        int result = ngp_supervise(sv[0], &state, log, 350, 100);
        assert((which == GOOD) == (result == 0));
        if (which == GOOD) assert(state.phase == NGP_COMPLETE);
        int status;
        if (which == REAP_DEADLINE) {
            /* This deliberately escaping fixture is outside the production
             * fixed engine. It must deny GPU even after all six events.
             * The adopted child is still ours and unreaped: exact PID pinned. */
            assert(state.phase == NGP_COMPLETE);
            assert(waitpid(descendant, &status, WNOHANG) == 0);
            assert(!kill(descendant, SIGKILL));
            assert(waitpid(descendant, &status, 0) == descendant);
        }
        errno = 0;
        assert(waitpid(-1, &status, WNOHANG) == -1 && errno == ECHILD);
        fclose(log); close(sv[0]);
        printf("LIFECYCLE_CASE=%s PASS ECHILD=1 GPU_permission=%u\n", names[which], result == 0);
    }
}

static void selected_mapping(void)
{
    const size_t view = NGP_VIEW_BYTES, bytes = NGP_ALLOCATION_BYTES;
    int fd = memfd_create("ordinary-owner-fixture", MFD_CLOEXEC);
    assert(fd >= 0 && !ftruncate(fd, bytes));
    unsigned char *canonical = mmap(NULL, bytes, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    unsigned char *source = mmap(NULL, bytes, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    unsigned char *arena = mmap(NULL, 3 * view, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    assert(canonical != MAP_FAILED && source != MAP_FAILED && arena != MAP_FAILED);
    assert(!mprotect(arena, view, PROT_READ | PROT_WRITE));
    assert(!mprotect(arena + 2 * view, view, PROT_READ | PROT_WRITE));
    memset(arena, 0x15, view); memset(arena + 2 * view, 0x61, view);
    for (size_t i = 0; i < bytes; i++) canonical[i] = (unsigned char)(i * 37 + 11);
    void *moved = mremap(source + view, view, view, MREMAP_MAYMOVE | MREMAP_FIXED, arena + view);
    assert(moved == arena + view);
    for (size_t i = 0; i < view; i++) {
        assert(source[i] == canonical[i]);
        assert(arena[view + i] == canonical[view + i]);
        assert(arena[i] == 0x15 && arena[2 * view + i] == 0x61);
    }
    uint64_t value = UINT64_C(0xb9a2dd48f17c005e);
    memcpy(arena + view + 8, &value, sizeof(value));
    assert(!memcmp(canonical + view + 8, &value, sizeof(value)));
    assert(!munmap(source, view) && !munmap(arena, 3 * view) && !munmap(canonical, bytes));
    close(fd);
    puts("OWNED_SELECTED_MEMFD_MAPPING=PASS source_prefix_retained=1 adjacent_guards_intact=1 shared_write_observed=1");
}

int main(void)
{
    alarm(15);
    validate_bits();
    selected_mapping();
    lifecycle();
    puts("OWNER_HOST_FIXTURE=PASS AArch64_executed=0 GPU_tested=0 Android_tested=0");
    return 0;
}
