/* SPDX-License-Identifier: MIT
 * Ordinary Linux memfd fixture for the same alias/code-cache/IPC code. CPU only.
 * x86-64 executes an explicitly separate mov-eax/ret fixture, not AArch64 code.
 */
#define _GNU_SOURCE
#define NA_HOST_FIXTURE 1
#include "native_code_cache_exec.h"
#include "cached_policy.h"

static int fixture_cached_policy(void)
{
    const VkMemoryPropertyFlags cached = VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT |
                                         VK_MEMORY_PROPERTY_HOST_CACHED_BIT;
    VkPhysicalDeviceMemoryProperties memory = {.memoryTypeCount = 3};
    memory.memoryTypes[0].propertyFlags = VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT;
    memory.memoryTypes[1].propertyFlags = VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT |
        VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT;
    if (cached_select_type(&memory, 7) != -1) return 1;
    memory.memoryTypes[2].propertyFlags = cached | VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT;
    if (cached_select_type(&memory, 7) != 2 || cached_select_type(&memory, 3) != -1) return 1;
    memory.memoryTypes[2].propertyFlags = VK_MEMORY_PROPERTY_HOST_CACHED_BIT;
    if (cached_select_type(&memory, 7) != -1) return 1;
    memory.memoryTypes[2].propertyFlags = cached | VK_MEMORY_PROPERTY_PROTECTED_BIT;
    if (cached_select_type(&memory, 7) != -1) return 1;
    memory.memoryTypes[2].propertyFlags = cached;
    if (cached_select_type(&memory, 7) != 2) return 1;
    puts("FIXTURE_CACHED_POLICY=PASS coherent_uncached_rejected=yes requirements_respected=yes hidden_or_protected_rejected=yes cached_noncoherent_accepted=yes");
    return 0;
}

static void fixture_fill(void *mapping, const uint32_t *expected)
{
    volatile uint32_t *words = mapping;
    for (size_t i = 0; i < NA_BYTES / sizeof(uint32_t); ++i) words[i] = expected[i];
    atomic_thread_fence(memory_order_seq_cst);
}

static int fixture_owned_cleanup(int fd, const uint32_t *expected)
{
    NaAlias alias = NA_ALIAS_INIT;
    void *guard = MAP_FAILED;
    int result = 1;
    if (na_alias_prepare(&alias, fd)) goto done;
    if (cpu_alias_check_full(alias.source, expected, NA_BYTES, "FIXTURE_FULL_SOURCE_BEFORE_MOVE")) goto done;
    if (na_alias_move(&alias)) na_uncertain_exit("fixture_move_failed", 1);
    if (na_check_span(&alias, expected, "FIXTURE_16K_MOVED")) goto done;
    void *hole = (unsigned char *)alias.source + NA_OFFSET;
    void *prefix = alias.source_prefix.address;
    void *reservation = alias.reservation.address;
    size_t reservation_bytes = alias.reservation.bytes;
    guard = mmap(hole, NA_SPAN, PROT_READ | PROT_WRITE,
                 MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0);
    if (guard != hole) { puts("FIXTURE_FAIL: cannot claim source hole without replacement"); goto done; }
    volatile uint32_t *words = guard;
    for (size_t i = 0; i < NA_SPAN / sizeof(uint32_t); ++i) words[i] = UINT32_C(0xacf00291);
    if (na_alias_drop(&alias)) na_uncertain_exit("fixture_exact_cleanup", 1);
    unsigned char residency[NA_BYTES / NA_HOST_PAGE];
    if (mincore(guard, NA_SPAN, residency)) goto done;
    for (size_t i = 0; i < NA_SPAN / sizeof(uint32_t); ++i)
        if (words[i] != UINT32_C(0xacf00291)) goto done;
    errno = 0;
    if (mincore(prefix, NA_OFFSET, residency) != -1 || errno != ENOMEM) goto done;
    errno = 0;
    if (mincore(reservation, reservation_bytes, residency) != -1 || errno != ENOMEM) goto done;
    puts("FIXTURE_EXACT_CLEANUP=PASS moved16KiB_source_hole_reused_and_preserved=yes source_prefix_and_destination_removed=yes");
    result = 0;
done:
    if (na_alias_drop(&alias)) na_uncertain_exit("fixture_cleanup_failure", 1);
    if (guard != MAP_FAILED && munmap(guard, NA_SPAN)) result = 1;
    return result;
}

static int fixture_negative_controls(int fd, const uint32_t *expected)
{
    /* CPU-only fixture forks, with no Vulkan library/device. The phone path
     * continues to use posix_spawn and exec exclusively. */
    pid_t owner = getpid();
    pid_t pid = fork();
    if (pid < 0) return 1;
    if (!pid) {
        if (prctl(PR_SET_PDEATHSIG, SIGKILL) || getppid() != owner) _Exit(1);
        alarm(2);
        NaAlias failed = NA_ALIAS_INIT;
        if (na_alias_prepare(&failed, fd) ||
            cpu_alias_check_full(failed.source, expected, NA_BYTES, "FIXTURE_FAILED_MOVE_FULL_INITIAL")) _Exit(1);
        if (munmap((unsigned char *)failed.source + NA_OFFSET, NA_SPAN)) _Exit(1);
        errno = 0;
        if (!na_alias_move(&failed) || errno != EFAULT || !failed.uncertain) _Exit(1);
        errno = 0;
        if (!na_alias_drop(&failed) || errno != EBUSY) _Exit(1);
        puts("FIXTURE_UNCERTAIN_MOVE=PASS actual_EFAULT=yes cleanup_refused=yes process_exit_only=yes");
        _Exit(0);
    }
    int status;
    int64_t now = na_now_ms();
    if (now < 0 || na_reap(pid, &status, now + 1000)) { na_kill_reap(pid); return 1; }
    if (!WIFEXITED(status) || WEXITSTATUS(status)) return 1;
    int sockets[2];
    if (socketpair(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC | SOCK_NONBLOCK, 0, sockets)) return 1;
    NaReply reply;
    now = na_now_ms();
    int timed_out = now >= 0 && na_receive(sockets[0], &reply, sizeof(reply), NULL, now + 40) == -1 && errno == ETIMEDOUT;
    close(sockets[0]); close(sockets[1]);
    if (!timed_out) return 1;
    puts("FIXTURE_IPC_DEADLINE=PASS empty_live_socket_stopped_at_bounded_deadline=yes");
    pid = fork();
    if (pid < 0) return 1;
    if (!pid) {
        if (prctl(PR_SET_PDEATHSIG, SIGKILL) || getppid() != owner) _Exit(1);
        alarm(2);
        for (;;) pause();
    }
    na_kill_reap(pid);
    errno = 0;
    if (waitpid(pid, &status, WNOHANG) != -1 || errno != ECHILD) return 1;
    puts("FIXTURE_CHILD_CANCELLATION=PASS SIGKILL_and_bounded_reap=yes no_child_remains=yes");
    return 0;
}

int main(int argc, char **argv)
{
    setvbuf(stdout, NULL, _IOLBF, 0);
    if (argc >= 2 && !strcmp(argv[1], "--cached-memory-child")) return na_child_entry(argc, argv);
    if (argc != 1 || sysconf(_SC_PAGESIZE) != NA_HOST_PAGE || na_watchdog(NA_PROCESS_SECONDS)) return 1;
    if (fixture_cached_policy()) return 1;
    int fd = -1, result = 1;
    void *canonical = MAP_FAILED;
    uint32_t expected[NA_BYTES / sizeof(uint32_t)];
    fd = memfd_create("pixel-native-code-cache-fixture", MFD_CLOEXEC | MFD_ALLOW_SEALING);
    if (fd < 0 || ftruncate(fd, NA_BYTES) || fcntl(fd, F_ADD_SEALS, F_SEAL_SHRINK)) goto done;
    canonical = mmap(NULL, NA_BYTES, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (canonical == MAP_FAILED) goto done;
    na_expected(expected, UINT32_C(0x7b620000), NA_INITIAL);
    fixture_fill(canonical, expected);
    if (fixture_owned_cleanup(fd, expected)) goto done;
    if (fixture_negative_controls(fd, expected)) goto done;
    for (unsigned mode = 0; mode <= 1; ++mode) {
    na_cpu_atomics = mode;
    na_expected(expected, UINT32_C(0x7b620000), NA_INITIAL);
    fixture_fill(canonical, expected);
    printf("FIXTURE_MODE cpu_atomics=%u\n", mode);
    NaReply reply = {0};
    result = na_exercise(fd, canonical, UINT32_C(0x7b620000), 0, &reply);
    if (result) goto done;
    if (na_atomic_calls != 2 * mode || reply.cpu_atomics != mode) { result = 1; goto done; }
    na_expected(expected, UINT32_C(0x7b620000), NA_LAST_STAGE);
    if (cpu_alias_check_full(canonical, expected, NA_BYTES, "FIXTURE_PARENT_FINAL_ALL_PAGES")) { result = 1; goto done; }
    const uint32_t child_input = UINT32_C(0x924a0000);
    na_expected(expected, child_input, NA_INITIAL);
    fixture_fill(canonical, expected);
    puts("FIXTURE_CHILD_INPUT=CPU_fill_not_GPU");
    NaReply child_reply = {0};
    result = na_run_child(fd, child_input, &child_reply);
    if (result == 1) goto done;
    na_expected(expected, child_input, child_reply.stage);
    if (cpu_alias_check_full(canonical, expected, NA_BYTES, "FIXTURE_FRESH_EXEC_CHILD_TO_PARENT_ALL_PAGES")) { result = 1; goto done; }
    if (result) goto done;
    }
    puts("FIXTURE_RESULT=PASS ordinary_memfd_only=yes default_and_opt_in_modes_tested=yes GPU_tested=no opaque_FD_tested=no phone_tested=no");
done:
    if (canonical != MAP_FAILED && munmap(canonical, NA_BYTES)) result = 1;
    if (fd >= 0 && close(fd)) result = 1;
    alarm(0);
    if (result) printf("FIXTURE_RESULT=%s exit=%d errno=%d\n", result == NA_UNSUPPORTED ? "UNSUPPORTED" : "FAIL", result, errno);
    return result;
}
