/* SPDX-License-Identifier: MIT
 * Real reims allocation/runtime -> strict native EL0 -> runtime GPU readback.
 * No raw Vulkan allocation or command path is linked into this owner.
 */
#include "native_owner.h"
#include "reims_vgpu.h"

static int checked(RvgStatus got, RvgStatus wanted, const char *phase)
{
    printf("REIMS_CALL phase=%s status=%u expected=%u result=%s\n",
           phase, got, wanted, got == wanted ? "PASS" : "FAIL");
    return got != wanted || ngp_durable(stdout);
}

static int words_equal(const volatile uint32_t *got, const uint32_t *expected,
                       const char *phase)
{
    for (size_t i = 0; i < NGP_ALLOCATION_BYTES / sizeof(uint32_t); i++) {
        uint32_t value = got[i];
        if (value != expected[i]) {
            printf("REIMS_WORDS phase=%s result=FAIL word=%zu got=%08x expected=%08x\n",
                   phase, i, value, expected[i]);
            return 1;
        }
    }
    printf("REIMS_WORDS phase=%s result=PASS checked_words=8192\n", phase);
    return ngp_durable(stdout);
}

static int proof(const char *directory)
{
    RvgProducer *producer = NULL;
    RvgProducerCpu *cpu = NULL;
    RvgProducerNative *native = NULL;
    RvgProducerInfo info = {0}, later = {0};
    uint32_t expected[NGP_ALLOCATION_BYTES / sizeof(uint32_t)];
    uint32_t readback[NGP_ALLOCATION_BYTES / sizeof(uint32_t)];
    void *pointer = NULL;
    uint64_t epoch = 0, next_epoch = 0;
    int fd = -1;
    if (checked(rvg_producer_create(NGP_ALLOCATION_BYTES, &producer), RVG_OK, "create") ||
        checked(rvg_producer_info(producer, &info, sizeof(info)), RVG_OK, "identity")) return 1;
    printf("REIMS_ALLOCATION id=%" PRIu64 " device=%" PRIu64 " runtime_object=%" PRIu64
           " logical=%" PRIu64 " allocation=%" PRIu64 " type=%u flags=0x%x atom=%" PRIu64 "\n",
           info.allocation_id, info.device_registry_id, info.runtime_object_id,
           info.logical_bytes, info.allocation_bytes, info.memory_type, info.memory_flags,
           info.noncoherent_atom_bytes);
    if (info.struct_size != sizeof(info) || info.reserved || !info.allocation_id ||
        !info.runtime_object_id || info.logical_bytes != NGP_ALLOCATION_BYTES ||
        info.allocation_bytes != NGP_ALLOCATION_BYTES || (info.memory_flags & 0xa) != 0xa ||
        !info.noncoherent_atom_bytes || info.flushes || info.invalidates || info.completed_submissions)
        return 1;
    expected_words(expected, false);
    if (checked(rvg_producer_upload(producer, expected, sizeof(expected)), RVG_OK, "runtime_GPU_upload") ||
        checked(rvg_producer_cpu_begin(producer, &cpu), RVG_OK, "CPU_begin") ||
        checked(rvg_producer_cpu_pointer(cpu, &pointer, &epoch), RVG_OK, "CPU_pointer") ||
        words_equal(pointer, expected, "GPU_to_CPU_initial") ||
        checked(rvg_producer_native_export(cpu, &native, &fd), RVG_OK, "native_export") || fd < 3)
        return 1;
    if (checked(rvg_producer_cpu_end(cpu), RVG_ERR_PRODUCER_STATE, "live_export_refuses_CPU_end") ||
        checked(rvg_producer_upload(producer, expected, sizeof(expected)), RVG_ERR_PRODUCER_STATE,
                "CPU_epoch_refuses_GPU") ||
        checked(rvg_producer_info(producer, &later, sizeof(later)), RVG_OK, "before_native") ||
        later.flushes != 1 || later.invalidates != 1 || later.completed_submissions != 1) return 1;
    printf("REIMS_NATIVE_LEASE epoch=%" PRIu64 " allocation=%" PRIu64 " borrowed_fd=%d\n",
           epoch, info.allocation_id, fd);
    if (ngp_durable(stdout) || run_engine(fd, directory)) {
        puts("REIMS_HANDOFF_BLOCKED=1 reason=native_protocol_or_process_tree_not_closed");
        return 1; /* no retirement, cache operation, mapping access or speculative cleanup */
    }
    /* run_engine succeeded only after exact QEMU completion/exit and all owned descendants
     * were reaped to ECHILD. The authenticated native protocol proves the selected bytes. */
    if (checked(rvg_producer_native_retire(native), RVG_OK, "native_retire_after_ECHILD") ||
        checked(rvg_producer_native_retire(native), RVG_ERR_PRODUCER_STATE, "retire_replay_refused")) return 1;
    rvg_producer_native_release(native); native = NULL;
    if (checked(rvg_producer_cpu_end(cpu), RVG_OK, "CPU_end_after_native_reap") ||
        checked(rvg_producer_cpu_end(cpu), RVG_ERR_PRODUCER_STATE, "CPU_end_replay_refused")) return 1;
    rvg_producer_cpu_release(cpu); cpu = NULL; pointer = NULL;
    expected_words(expected, true);
    if (checked(rvg_producer_download(producer, readback, sizeof(readback)), RVG_OK,
                "runtime_independent_GPU_readback") || words_equal(readback, expected, "native_to_GPU") ||
        checked(rvg_producer_cpu_begin(producer, &cpu), RVG_OK, "second_CPU_begin") ||
        checked(rvg_producer_cpu_pointer(cpu, &pointer, &next_epoch), RVG_OK, "second_CPU_pointer") ||
        next_epoch <= epoch || words_equal(pointer, expected, "GPU_to_CPU_after_invalidate") ||
        checked(rvg_producer_cpu_end(cpu), RVG_OK, "second_CPU_end")) return 1;
    rvg_producer_cpu_release(cpu); cpu = NULL; pointer = NULL;
    if (checked(rvg_producer_info(producer, &later, sizeof(later)), RVG_OK, "final_identity") ||
        later.allocation_id != info.allocation_id || later.runtime_object_id != info.runtime_object_id ||
        later.device_registry_id != info.device_registry_id || later.flushes != 2 ||
        later.invalidates != 2 || later.completed_submissions != 2) return 1;
    printf("REIMS_NATIVE_GPU=PASS allocation=%" PRIu64 " runtime_object=%" PRIu64
           " flushes=%" PRIu64 " invalidates=%" PRIu64 " completed_submissions=%" PRIu64
           " modified_bytes=8 modified_offset=16392 checked_words=8192 producer_atomics=0\n",
           later.allocation_id, later.runtime_object_id, later.flushes, later.invalidates,
           later.completed_submissions);
    if (ngp_durable(stdout)) return 1;
    rvg_producer_release(producer);
    return 0;
}

int main(int argc, char **argv)
{
    setvbuf(stdout, NULL, _IOLBF, 0);
    if (argc != 2 || argv[1][0] != '/') {
        fprintf(stderr, "Usage: %s /absolute/verified/qemu-package\n", argv[0]);
        return 2;
    }
    char directory[PATH_MAX];
    if (!realpath(argv[1], directory) || ngp_durable(stdout) ||
        sysconf(_SC_PAGESIZE) != NGP_HOST_PAGE_BYTES ||
        prctl(PR_SET_CHILD_SUBREAPER, 1) || owner_watchdog()) return 1;
    int status;
    errno = 0;
    if (waitpid(-1, &status, WNOHANG) != -1 || errno != ECHILD) return 1;
    printf("REIMS_NATIVE_OWNER uid=%lu euid=%lu pid=%ld owner_deadline_s=%u"
           " exact_payload_sha256=%s\n", (unsigned long)getuid(), (unsigned long)geteuid(),
           (long)getpid(), NGP_OWNER_TIMEOUT_SECONDS, NGP_CODE_SHA256_HEX);
    if (ngp_durable(stdout)) return 1;
    int result = proof(directory);
    printf("RESULT=%s\n", result ? "FAIL" : "REIMS_NATIVE_GPU_ONE_REGION_PASS");
    if (ngp_durable(stdout)) result = 1;
    alarm(0);
    _exit(result ? 1 : 0);
}
