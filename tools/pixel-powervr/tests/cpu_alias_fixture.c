/* SPDX-License-Identifier: MIT
 * Host-only ordinary-memfd validation of the EXACT native alias helpers used
 * by opaque_fd_probe.c. This does not test a Vulkan opaque FD or GPU execution.
 */
#define _GNU_SOURCE
#include "cpu_alias.h"

#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
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

int main(void)
{
    setvbuf(stdout, NULL, _IOLBF, 0);
    int result = 1, fd = -1;
    void *canonical = MAP_FAILED, *second = MAP_FAILED, *full = MAP_FAILED;
    uint32_t *expected = NULL;
    CpuAliases aliases = {.base = MAP_FAILED}, partial = {.base = MAP_FAILED};
    long host_page = sysconf(_SC_PAGESIZE);
    size_t bytes = 0;
    REQUIRE(host_page > 0 && host_page <= 65536, "supported host page size");
    size_t page = (size_t)host_page;
    bytes = CPU_ALIAS_PAGES * page;
    fd = memfd_create("pixel-cpu-alias-fixture", MFD_CLOEXEC | MFD_ALLOW_SEALING);
    REQUIRE(fd >= 0, "create ordinary memfd");
    REQUIRE(!ftruncate(fd, (off_t)bytes), "size ordinary memfd");
    REQUIRE(!fcntl(fd, F_ADD_SEALS, F_SEAL_SHRINK), "seal against shrink");
    canonical = mmap(NULL, bytes, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    second = mmap(NULL, bytes, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    full = mmap(NULL, bytes, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    REQUIRE(canonical != MAP_FAILED && second != MAP_FAILED && full != MAP_FAILED, "three ordinary full aliases");
    expected = malloc(bytes);
    REQUIRE(expected, "allocate independent expected data");
    cpu_alias_expected_fill(expected, page, UINT32_C(0x7b620000));
    cpu_fill(canonical, expected, bytes);
    REQUIRE(!cpu_alias_setup(&aliases, fd, page, bytes), "create reordered aliases");
    const unsigned wanted[CPU_ALIAS_SLOTS] = {5, 0, 7, 2};
    REQUIRE(!memcmp(aliases.source_page, wanted, sizeof(wanted)), "exact slot order5,0,7,2");
    REQUIRE(!cpu_alias_check_slots(&aliases, expected, "FIXTURE_INITIAL_REORDERED_CONTENTS"), "initial slot bytes");
    for (unsigned slot = 0; slot < CPU_ALIAS_SLOTS; ++slot) {
        REQUIRE(!cpu_alias_write_slot(&aliases, slot, UINT32_C(0x4c000000)), "write per-slot pattern");
        cpu_alias_expected_slot(expected, page, slot, wanted[slot], UINT32_C(0x4c000000));
    }
    REQUIRE(!cpu_alias_check_full(canonical, expected, bytes, "FIXTURE_SCATTER_TO_CANONICAL"), "canonical pages and guards");
    REQUIRE(!cpu_alias_check_full(second, expected, bytes, "FIXTURE_SCATTER_TO_SECOND"), "second full view");
    REQUIRE(!cpu_alias_check_full(full, expected, bytes, "FIXTURE_SCATTER_TO_FULL"), "third full view");

    /* The fixture writes the canonical CPU view; only the Android probe uses
     * a real GPU fill for this transition. */
    cpu_alias_expected_fill(expected, page, UINT32_C(0x34ed0000));
    cpu_fill(canonical, expected, bytes);
    REQUIRE(!cpu_alias_check_slots(&aliases, expected, "FIXTURE_CANONICAL_TO_REORDERED"), "canonical fill reflected in slots");
    REQUIRE(!cpu_alias_map_slot(&aliases, fd, 3, 5), "replace owned slot3 page2 with page5");
    REQUIRE(!cpu_alias_check_slots(&aliases, expected, "FIXTURE_REMAP_INITIAL"), "replacement sees source page5");
    REQUIRE(!cpu_alias_write_slot(&aliases, 3, UINT32_C(0xda000000)), "write repeated page5 alias");
    cpu_alias_expected_slot(expected, page, 3, 5, UINT32_C(0xda000000));
    REQUIRE(!cpu_alias_check_slots(&aliases, expected, "FIXTURE_REPEATED_PAGE_ALIAS"), "slots0 and3 share page5");
    REQUIRE(!cpu_alias_check_full(canonical, expected, bytes, "FIXTURE_REMAP_CANONICAL_GUARDS"), "page2 and all other guards preserved");
    REQUIRE(!cpu_alias_check_full(second, expected, bytes, "FIXTURE_REMAP_SECOND"), "second full view after remap");
    REQUIRE(!cpu_alias_check_full(full, expected, bytes, "FIXTURE_REMAP_FULL"), "third full view after remap");

    errno = 0;
    REQUIRE(cpu_alias_map_slot(&aliases, fd, CPU_ALIAS_SLOTS, 0) == -1 && errno == EINVAL, "reject destination outside owned slots");
    errno = 0;
    REQUIRE(cpu_alias_map_slot(&aliases, fd, 0, CPU_ALIAS_PAGES) == -1 && errno == EINVAL, "reject source outside known allocation");
    REQUIRE(!cpu_alias_check_slots(&aliases, expected, "FIXTURE_INVALID_REQUESTS_UNCHANGED"), "rejected remaps leave live mappings unchanged");

    REQUIRE(!cpu_alias_reserve(&partial, page, bytes), "reserve partial-failure window");
    REQUIRE(!cpu_alias_map_slot(&partial, fd, 0, 5), "partial setup first slot");
    REQUIRE(!cpu_alias_map_slot(&partial, fd, 1, 0), "partial setup second slot");
    errno = 0;
    REQUIRE(cpu_alias_map_slot(&partial, -1, 2, 7) == -1 && errno == EBADF, "force third-slot mapping failure using invalid FD");
    void *old_base = partial.base;
    REQUIRE(!cpu_alias_drop(&partial), "drop whole owned partial reservation");
    unsigned char residency[CPU_ALIAS_SLOTS];
    errno = 0;
    REQUIRE(mincore(old_base, CPU_ALIAS_SLOTS * page, residency) == -1 && errno == ENOMEM, "verify partial-failure reservation is unmapped");
    puts("FIXTURE_BOUNDS_AND_PARTIAL_CLEANUP=PASS");
    puts("FIXTURE_RESULT=PASS ordinary_memfd_only=yes GPU_tested=no opaque_FD_tested=no");
    result = 0;
done:
    cpu_alias_drop(&partial);
    cpu_alias_drop(&aliases);
    free(expected);
    if (full != MAP_FAILED) munmap(full, bytes);
    if (second != MAP_FAILED) munmap(second, bytes);
    if (canonical != MAP_FAILED) munmap(canonical, bytes);
    if (fd >= 0) close(fd);
    return result;
}
