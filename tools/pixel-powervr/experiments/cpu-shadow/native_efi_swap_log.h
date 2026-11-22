/* SPDX-License-Identifier: MIT
 * Only the authored swap-mode supervisor includes this verifier. The generic
 * trap case keeps its original independent trap-count/PC verifier.
 */
#ifndef ASOFT_NATIVE_EFI_SWAP_LOG_H
#define ASOFT_NATIVE_EFI_SWAP_LOG_H

static bool swap_line_end(const char *suffix) {
    return !strcmp(suffix, "\n") || !strcmp(suffix, "\r\n") || !*suffix;
}

static bool swap_line(const char *line, const char *expected) {
    size_t length = strlen(expected);
    return !strncmp(line, expected, length) && swap_line_end(line + length);
}

static bool verify_log(const char *path) {
    FILE *input = fopen(path, "r");
    if (!input) {
        return false;
    }
    char *line = NULL;
    size_t capacity = 0;
    unsigned int registers = 0;
    bool init = false, boot = false, complete = false, phase0 = false, phase1 = false;
    bool native = false, gpu = false, failed = false;
    while (getline(&line, &capacity, input) >= 0) {
        uint64_t enters, svcs, chunks, views, prepared, finished, uploaded, scattered;
        if (strstr(line, "required initialization ready mode=stubs;")) {
            init = true;
        }
        if (swap_line(line, "NATIVE_EFI_SWAP_BOOT_EL1")) {
            failed |= boot || registers != 0;
            boot = true;
        }
        if (!strncmp(line, "NATIVE_EFI_SWAP_REGISTERS ", 26)) {
            uint64_t phase, ro, rw, data, saved_rw, saved_ro, read_pc, svc_return;
            int end = 0;
            int fields = sscanf(line,
                "NATIVE_EFI_SWAP_REGISTERS phase=%" SCNx64
                " tpidrro=%" SCNx64 " tpidr=%" SCNx64 " data=%" SCNx64
                " el1_tpidr=%" SCNx64 " el1_tpidrro=%" SCNx64
                " read_pc=%" SCNx64 " svc_return=%" SCNx64 "%n",
                &phase, &ro, &rw, &data, &saved_rw, &saved_ro, &read_pc, &svc_return, &end);
            if (fields != 8 || end <= 0 || !swap_line_end(line + end) || !boot ||
                phase != registers || phase > 1 || complete ||
                ro != (uint64_t)NEF_SWAP_TSD_VA + phase * NEF_SWAP_TSD_STRIDE || rw != 0 ||
                data != (uint64_t)NEF_SWAP_TSD_VALUE + phase ||
                saved_rw != (uint64_t)NEF_SWAP_TPIDR_SENTINEL + phase || saved_ro != ro ||
                read_pc != NEF_TPIDRRO_PC || svc_return != NEF_SWAP_SVC_RETURN_PC) {
                failed = true;
            } else {
                ++registers;
            }
        }
        if (swap_line(line, "NATIVE_EFI_SWAP_PHASE_0_REGISTERS_OK")) {
            failed |= registers != 1 || phase0 || phase1;
            phase0 = true;
        }
        if (swap_line(line, "NATIVE_EFI_SWAP_PHASE_1_REGISTERS_OK")) {
            failed |= registers != 2 || !phase0 || phase1;
            phase1 = true;
        }
        if (swap_line(line, "NATIVE_EFI_SWAP_GUEST_COMPLETE")) {
            failed |= registers != 2 || !phase0 || !phase1 || complete;
            complete = true;
        }
        if (sscanf(line, "native-el0: enters %" SCNu64 " svc %" SCNu64, &enters, &svcs) == 2) {
            /* The final reported totals, not one earlier matching sample. */
            native = enters >= 2 && svcs == 2;
        }
        if (sscanf(line, "vresearch-pvg-reims: cpu-shadow chunks=%" SCNu64
                   " views=%" SCNu64 " prepared=%" SCNu64 " finished=%" SCNu64
                   " uploaded=%" SCNu64 " scattered=%" SCNu64,
                   &chunks, &views, &prepared, &finished, &uploaded, &scattered) == 6) {
            gpu = chunks > 0 && views > 0 && prepared >= 2 && prepared == finished &&
                  uploaded >= NEF_FRAME_BYTES * 2;
        }
        failed |= strstr(line, "NATIVE_EFI_SWAP_GUEST_FAIL") != NULL ||
                  strstr(line, "NATIVE_EFI_GUEST_FAIL") != NULL ||
                  strstr(line, "NATIVE_EFI_GUEST_COMPLETE") != NULL ||
                  strstr(line, "tpidrro-trap") != NULL ||
                  strstr(line, "required initialization failed") != NULL ||
                  strstr(line, "TPIDRRO trap mode failed") != NULL ||
                  strstr(line, "staying on TCG") != NULL ||
                  strstr(line, "no stub factory") != NULL ||
                  strstr(line, "CPU-shadow counters unavailable") != NULL ||
                  strstr(line, "failed on the GPU") != NULL;
    }
    bool okay = !ferror(input) && !failed && init && boot && complete && phase0 && phase1 &&
                registers == 2 && native && gpu;
    free(line);
    fclose(input);
    printf("NATIVE_EFI_SWAP_WITNESS init=%d phases=%d,%d complete=%d native_svc=%d"
           " exact_register_records=%u real_gpu=%d rejected=%d\n",
           init, phase0, phase1, complete, native, registers, gpu, failed);
    return okay;
}

#endif
