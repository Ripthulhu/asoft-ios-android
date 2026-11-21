/* SPDX-License-Identifier: MIT
 * Ordinary-memfd host fixture for the EXACT one-page move helper. No Vulkan,
 * opaque FD, GPU execution, driver mapping or phone capability is tested here.
 */
#define _GNU_SOURCE
#include "cpu_move.h"

#include <fcntl.h>
#include <stdlib.h>
#include <sys/wait.h>
#include <unistd.h>

#define REQUIRE(condition, description) do { \
    if (!(condition)) { fprintf(stderr, "FIXTURE_FAIL: %s errno=%d\n", description, errno); goto done; } \
} while (0)

static void cpu_fill(void *mapping, const uint32_t *expected, size_t bytes)
{
    volatile uint32_t *words = mapping;
    for (size_t i = 0; i < bytes / sizeof(*words); ++i) words[i] = expected[i];
    atomic_thread_fence(memory_order_seq_cst);
}

static int failed_move_child(int fd, size_t page, size_t bytes)
{
    /* This child owns all of its mappings and immediately exits after a real
     * failed syscall. It does not try to repair or clean an uncertain layout. */
    CpuMovePage failed = CPU_MOVE_INITIALIZER;
    if (cpu_move_prepare(&failed, fd, page, bytes, 5)) return 1;
    void *source_page = (unsigned char *)failed.source_map + failed.offset;
    if (munmap(source_page, page)) return 1;
    errno = 0;
    if (!cpu_move_one_page(&failed) || errno != EFAULT ||
        failed.state != CPU_MOVE_UNCERTAIN) return 1;
    errno = 0;
    if (!cpu_move_drop(&failed) || errno != EBUSY) return 1;
    puts("FIXTURE_FAILED_SYSCALL_POLICY=PASS actual_mremap_EFAULT=yes cleanup_refused=yes process_exit_only=yes");
    return 0;
}

int main(void)
{
    setvbuf(stdout, NULL, _IOLBF, 0);
    int result = 1, fd = -1;
    void *canonical = MAP_FAILED, *second = MAP_FAILED, *hole_guard = MAP_FAILED;
    uint32_t *expected = NULL;
    CpuMovePage moved = CPU_MOVE_INITIALIZER;
    size_t page = 0, bytes = 0;
    long host_page = sysconf(_SC_PAGESIZE);
    REQUIRE(host_page > 0 && host_page <= 65536, "supported host page size");
    page = (size_t)host_page;
    bytes = CPU_ALIAS_PAGES * page;
    fd = memfd_create("pixel-cpu-move-fixture", MFD_CLOEXEC | MFD_ALLOW_SEALING);
    REQUIRE(fd >= 0, "create ordinary memfd");
    REQUIRE(!ftruncate(fd, (off_t)bytes), "size ordinary memfd");
    REQUIRE(!fcntl(fd, F_ADD_SEALS, F_SEAL_SHRINK), "seal against shrink");
    canonical = mmap(NULL, bytes, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    second = mmap(NULL, bytes, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    REQUIRE(canonical != MAP_FAILED && second != MAP_FAILED, "canonical ordinary aliases");
    expected = malloc(bytes);
    REQUIRE(expected, "allocate expected data");
    cpu_alias_expected_fill(expected, page, UINT32_C(0x7b620000));
    cpu_fill(canonical, expected, bytes);

    errno = 0;
    REQUIRE(cpu_move_prepare(&moved, fd, page, bytes, CPU_ALIAS_PAGES) == -1 && errno == EINVAL,
            "reject source page beyond known allocation");
    REQUIRE(moved.state == CPU_MOVE_EMPTY && moved.source_map == MAP_FAILED,
            "invalid source creates no mapping");
    REQUIRE(!cpu_move_prepare(&moved, fd, page, bytes, 5), "prepare disposable source and owned slot");
    REQUIRE(!cpu_alias_check_full(moved.source_map, expected, bytes, "FIXTURE_DISPOSABLE_FULL_MAP"),
            "verify and populate every source page before moving");
    void *old_source = moved.source_map;
    void *old_slot = moved.slot;
    REQUIRE(!cpu_move_one_page(&moved), "move exactly page5 into owned slot");
    REQUIRE(!cpu_move_check_page(&moved, expected, "FIXTURE_MOVED_INITIAL"), "moved page is page5");
    REQUIRE(!cpu_move_write_page(&moved, UINT32_C(0xd9000000)), "write moved page");
    cpu_alias_expected_slot(expected, page, 0, 5, UINT32_C(0xd9000000));
    REQUIRE(!cpu_alias_check_full(canonical, expected, bytes, "FIXTURE_MOVED_TO_CANONICAL_GUARDS"),
            "all eight canonical pages including seven guards");
    REQUIRE(!cpu_alias_check_full(second, expected, bytes, "FIXTURE_MOVED_TO_SECOND_GUARDS"),
            "independent CPU alias sees exact changed page");
    cpu_alias_expected_fill(expected, page, UINT32_C(0x95d40000));
    cpu_fill(canonical, expected, bytes);
    REQUIRE(!cpu_move_check_page(&moved, expected, "FIXTURE_CANONICAL_TO_MOVED"),
            "canonical CPU writes reach moved page");

    /* Reuse the vacated source hole WITHOUT overwriting any intervening mapping.
     * A successful helper cleanup must leave this independent live mapping alone. */
    void *old_hole = (unsigned char *)old_source + 5 * page;
    hole_guard = mmap(old_hole, page, PROT_READ | PROT_WRITE,
                      MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0);
    REQUIRE(hole_guard == old_hole, "claim vacated source hole without replacing anything");
    volatile uint32_t *guard_words = hole_guard;
    for (size_t i = 0; i < page / sizeof(*guard_words); ++i) guard_words[i] = UINT32_C(0xabc00271);
    REQUIRE(!cpu_move_drop(&moved), "drop exact owned prefix, suffix and destination");
    unsigned char residency[CPU_ALIAS_PAGES];
    REQUIRE(!mincore(hole_guard, page, residency), "hole guard mapping survived helper cleanup");
    for (size_t i = 0; i < page / sizeof(*guard_words); ++i)
        REQUIRE(guard_words[i] == UINT32_C(0xabc00271), "hole guard contents survived cleanup");
    errno = 0;
    REQUIRE(mincore(old_source, 5 * page, residency) == -1 && errno == ENOMEM,
            "source prefix was unmapped");
    errno = 0;
    REQUIRE(mincore((unsigned char *)old_source + 6 * page, 2 * page, residency) == -1 && errno == ENOMEM,
            "source suffix was unmapped");
    errno = 0;
    REQUIRE(mincore(old_slot, page, residency) == -1 && errno == ENOMEM, "destination was unmapped");
    puts("FIXTURE_EXACT_CLEANUP=PASS prefix_pages=5 suffix_pages=2 moved_slot_pages=1 reused_source_hole_preserved=yes");

    pid_t child = fork();
    REQUIRE(child >= 0, "fork isolated syscall-failure fixture");
    if (!child) _Exit(failed_move_child(fd, page, bytes));
    int child_status;
    REQUIRE(waitpid(child, &child_status, 0) == child && WIFEXITED(child_status) && WEXITSTATUS(child_status) == 0,
            "child exercised real failure without uncertain cleanup");
    puts("FIXTURE_RESULT=PASS ordinary_memfd_only=yes GPU_tested=no opaque_FD_tested=no");
    result = 0;
done:
    if (moved.state == CPU_MOVE_UNCERTAIN) {
        fputs("FIXTURE_EXIT: uncertain mapping layout; no cleanup attempted\n", stderr);
        fflush(NULL);
        _Exit(result);
    }
    if (cpu_move_drop(&moved)) result = 1;
    if (hole_guard != MAP_FAILED) munmap(hole_guard, page);
    free(expected);
    if (second != MAP_FAILED) munmap(second, bytes);
    if (canonical != MAP_FAILED) munmap(canonical, bytes);
    if (fd >= 0) close(fd);
    return result;
}
