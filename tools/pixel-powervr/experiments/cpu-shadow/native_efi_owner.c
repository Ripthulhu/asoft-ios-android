/* SPDX-License-Identifier: MIT
 * Owns ordinary RAM and the output frame; QEMU owns the actual reims GPU device.
 * The two native phases advance only after exact independent GPU frame checks.
 */
#define _GNU_SOURCE
#include "native_efi_protocol.h"

#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/prctl.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t interrupted;

static void interrupted_run(int signal_number) {
    (void)signal_number;
    interrupted = 1;
}

static int64_t now_ms(void) {
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts)) {
        return -1;
    }
    return (int64_t)ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}

static void pause_poll(void) {
    struct timespec pause = {.tv_sec = 0, .tv_nsec = 10000000};
    nanosleep(&pause, NULL);
}

static int memfd(const char *name, size_t bytes) {
    int fd = (int)syscall(SYS_memfd_create, name, MFD_CLOEXEC | MFD_ALLOW_SEALING);
    if (fd >= 0 && (ftruncate(fd, (off_t)bytes) ||
                   fcntl(fd, F_ADD_SEALS, F_SEAL_SHRINK | F_SEAL_GROW | F_SEAL_SEAL))) {
        close(fd);
        fd = -1;
    }
    return fd;
}

static uint32_t expected_pixel(unsigned int x, unsigned int y, unsigned int phase) {
    uint32_t blue = (((x / 8) ^ phase) & 1) ? 255 : 0;
    uint32_t green = (((y / 8) ^ phase) & 1) ? 255 : 0;
    uint32_t red = (((x / 16) ^ (y / 16) ^ phase) & 1) ? 255 : 0;
    return UINT32_C(0xff000000) | (red << 16) | (green << 8) | blue;
}

/* The frame thread can be copying a newer frame while this is sampled. We
 * acknowledge only an exact complete pattern, never partial matching pixels. */
static bool frame_matches(const volatile uint32_t *pixels, unsigned int phase) {
    for (unsigned int y = 0; y < 64; ++y) {
        for (unsigned int x = 0; x < 64; ++x) {
            if (pixels[y * 64 + x] != expected_pixel(x, y, phase)) {
                return false;
            }
        }
    }
    return true;
}

#ifdef NEF_IOS_SWAP
#include "native_efi_swap_log.h"
#else
static bool verify_log(const char *path) {
    FILE *input = fopen(path, "r");
    if (!input) {
        return false;
    }
    char *line = NULL;
    size_t capacity = 0;
    bool init = false, complete = false, phase0 = false, phase1 = false;
    bool native = false, code = false, witness = false, gpu = false, failed = false;
    while (getline(&line, &capacity, input) >= 0) {
        uint64_t enters, svcs, copies, maps, reads, pc;
        uint64_t chunks, views, prepared, finished, uploaded, scattered;
        if (strstr(line, "required initialization ready mode=stubs;")) {
            init = true;
        }
        phase0 |= strstr(line, "NATIVE_EFI_PHASE_0_REGISTERS_OK") != NULL;
        phase1 |= strstr(line, "NATIVE_EFI_PHASE_1_REGISTERS_OK") != NULL;
        complete |= strstr(line, "NATIVE_EFI_GUEST_COMPLETE") != NULL;
        if (sscanf(line, "native-el0: enters %" SCNu64 " svc %" SCNu64, &enters, &svcs) == 2) {
            native |= enters >= 2 && svcs == 2;
        }
        if (sscanf(line, "native-el0: tpidrro-trap code-copies %" SCNu64
                   " code-map-requests %" SCNu64, &copies, &maps) == 2) {
            code |= copies > 0 && maps > 0;
        }
        if (sscanf(line, "native-el0: tpidrro-trap cpu0 reads %" SCNu64
                   " last-pc %" SCNx64, &reads, &pc) == 2) {
            witness |= reads == 2 && pc == NEF_TPIDRRO_PC;
        }
        if (sscanf(line, "vresearch-pvg-reims: cpu-shadow chunks=%" SCNu64
                   " views=%" SCNu64 " prepared=%" SCNu64 " finished=%" SCNu64
                   " uploaded=%" SCNu64 " scattered=%" SCNu64,
                   &chunks, &views, &prepared, &finished, &uploaded, &scattered) == 6) {
            gpu |= chunks > 0 && views > 0 && prepared >= 2 && finished >= 2 &&
                   uploaded >= NEF_FRAME_BYTES * 2;
        }
        failed |= strstr(line, "NATIVE_EFI_GUEST_FAIL") != NULL ||
                  strstr(line, "required initialization failed") != NULL ||
                  strstr(line, "TPIDRRO trap mode failed") != NULL ||
                  strstr(line, "staying on TCG") != NULL ||
                  strstr(line, "no stub factory") != NULL ||
                  strstr(line, "CPU-shadow counters unavailable") != NULL ||
                  strstr(line, "failed on the GPU") != NULL;
    }
    bool okay = !ferror(input) && !failed && init && phase0 && phase1 && complete &&
                native && code && witness && gpu;
    free(line);
    fclose(input);
    printf("NATIVE_EFI_WITNESS init=%d phases=%d,%d complete=%d native_svc=%d"
           " copied_code=%d exact_native_pc=%d real_gpu=%d rejected=%d\n",
           init, phase0, phase1, complete, native, code, witness, gpu, failed);
    return okay;
}
#endif

int main(int argc, char **argv) {
    if (argc != 3 || argv[1][0] != '/' || argv[2][0] != '/') {
        fprintf(stderr, "usage: %s /absolute/package /absolute/new-result-directory\n", argv[0]);
        return 2;
    }
    setvbuf(stdout, NULL, _IOLBF, 0);
    struct sigaction action = {.sa_handler = interrupted_run};
    sigemptyset(&action.sa_mask);
    sigaction(SIGTERM, &action, NULL);
    sigaction(SIGINT, &action, NULL);
    sigaction(SIGALRM, &action, NULL);
    alarm(45);
    int result = 1, ram = -1, frame = -1, log = -1, nullfd = -1;
    int child_status = 0;
    pid_t child = -1;
    bool leader_reaped = false, tree_closed = false;
    unsigned int checked = 0;
    volatile uint32_t *pixels = MAP_FAILED;
    char qemu[PATH_MAX], guest[PATH_MAX], log_path[PATH_MAX], cache_path[PATH_MAX];
    char library_env[PATH_MAX + 32], cache_env[PATH_MAX + 32];
    char ram_env[64], frame_env[64];
    pid_t owner = getpid();
    if (snprintf(qemu, sizeof qemu, "%s/qemu-system-aarch64", argv[1]) >= (int)sizeof qemu ||
#ifdef NEF_IOS_SWAP
        snprintf(guest, sizeof guest, "%s/native-efi-swap-guest.elf", argv[1]) >= (int)sizeof guest ||
#else
        snprintf(guest, sizeof guest, "%s/native-efi-guest.elf", argv[1]) >= (int)sizeof guest ||
#endif
        snprintf(log_path, sizeof log_path, "%s/qemu.log", argv[2]) >= (int)sizeof log_path ||
        snprintf(cache_path, sizeof cache_path, "%s/cache", argv[2]) >= (int)sizeof cache_path ||
        snprintf(library_env, sizeof library_env, "LD_LIBRARY_PATH=%s/lib", argv[1]) >= (int)sizeof library_env ||
        snprintf(cache_env, sizeof cache_env, "XDG_CACHE_HOME=%s", cache_path) >= (int)sizeof cache_env) {
        fprintf(stderr, "path too long\n");
        goto done;
    }
    if (mkdir(argv[2], 0700) || mkdir(cache_path, 0700) ||
        prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0)) {
        perror("new result directory/subreaper");
        goto done;
    }
    ram = memfd("native-efi-ram", NEF_RAM_BYTES);
    frame = memfd("native-efi-frame", NEF_FRAME_BYTES);
    log = open(log_path, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    nullfd = open("/dev/null", O_RDONLY | O_CLOEXEC);
    if (ram < 0 || frame < 0 || log < 0 || nullfd < 0) {
        perror("fixture descriptors");
        goto done;
    }
    pixels = mmap(NULL, NEF_FRAME_BYTES, PROT_READ | PROT_WRITE, MAP_SHARED, frame, 0);
    if (pixels == MAP_FAILED) {
        perror("output frame mapping");
        goto done;
    }
    memset((void *)pixels, 0x3c, NEF_FRAME_BYTES);
    snprintf(ram_env, sizeof ram_env, "ASOFT_GUEST_RAM_FD=%d", ram);
    snprintf(frame_env, sizeof frame_env, "ASOFT_FRAME_FD=%d", frame);
    char *const environment[] = {
        "PATH=/system/bin", library_env, cache_env, ram_env, frame_env,
        "ASOFT_NATIVE_EL0=1", "ASOFT_NATIVE_EL0_REQUIRED=1",
        "ASOFT_NATIVE_EL0_STUBS=1", "ASOFT_NATIVE_EL0_STATS=1",
#ifdef NEF_IOS_SWAP
        /* This is the iOS rewrite contract. The deliberately nonzero guest
         * TPIDR values must read as the zero CPU hint only in native EL0. */
        "ASOFT_NATIVE_EL0_TPIDRRO=1", "ASOFT_NATIVE_EL0_PAC=off",
        "ASOFT_VIRT_REIMS_TEST=1", "REIMS_VGPU_DEFERRED_VIEWS=1",
#else
        /* This generic authored guest needs the tested generic TPIDRRO contract.
         * iOS's separate TPIDRRO swap mode is not selected or changed here. */
        "ASOFT_NATIVE_EL0_TPIDRRO_TRAP=1", "ASOFT_VIRT_REIMS_TEST=1",
#endif
        "REIMS_VGPU_CPU_SHADOW=1", "REIMS_VGPU_LOG=info", NULL
    };
    char *const arguments[] = {
        qemu, "-M", "virt,memory-backend=m0",
        "-object", "memory-backend-memfd,id=m0,size=512M,share=on",
        "-cpu", "max,pauth-impdef=on", "-smp", "1", "-m", "512",
        "-accel", "tcg,thread=single", "-kernel", guest,
        "-display", "none", "-monitor", "none", "-serial", "stdio",
        "-nic", "none", "-no-reboot", "-no-user-config", NULL
    };
    child = fork();
    if (child == 0) {
        if (setpgid(0, 0) || prctl(PR_SET_PDEATHSIG, SIGKILL) ||
            getppid() != owner || dup2(nullfd, STDIN_FILENO) < 0 ||
            dup2(log, STDOUT_FILENO) < 0 || dup2(log, STDERR_FILENO) < 0 ||
            fcntl(ram, F_SETFD, 0) || fcntl(frame, F_SETFD, 0)) {
            _exit(120);
        }
        execve(qemu, arguments, environment);
        _exit(121);
    }
    if (child < 0) {
        perror("fork");
        goto done;
    }
    if (setpgid(child, child) != 0 && errno != EACCES && errno != ESRCH) {
        perror("child group");
        goto done;
    }
    int64_t deadline = now_ms() + 35000;
    for (unsigned int phase = 0; phase < 2 && !interrupted; ++phase) {
        bool seen = false;
        while (now_ms() < deadline && !interrupted) {
            if (frame_matches(pixels, phase)) {
                seen = true;
                break;
            }
            pid_t ended = waitpid(child, &child_status, WNOHANG);
            if (ended == child) {
                leader_reaped = true;
                break;
            }
            if (ended < 0 && errno != EINTR) {
                break;
            }
            pause_poll();
        }
        if (!seen || leader_reaped) {
            fprintf(stderr, "FAIL no complete GPU frame for native phase %u\n", phase);
            goto done;
        }
        ++checked;
#ifdef NEF_IOS_SWAP
        printf("NATIVE_EFI_SWAP_FRAME phase=%u exact_pixels=4096 ordinary_ram=1\n", phase);
#else
        printf("NATIVE_EFI_FRAME phase=%u exact_pixels=4096 ordinary_ram=1\n", phase);
#endif
        uint32_t acknowledge = phase + 1;
        if (pwrite(ram, &acknowledge, sizeof acknowledge,
                   NEF_FRAME_OFFSET + NEF_FRAME_BYTES) != sizeof acknowledge) {
            perror("ordinary RAM acknowledgement");
            goto done;
        }
    }
    if (checked != 2 || interrupted) {
        goto done;
    }
    deadline = now_ms() + 5000;
    while (now_ms() < deadline && !interrupted) {
        pid_t ended = waitpid(child, &child_status, WNOHANG);
        if (ended == child) {
            leader_reaped = true;
            break;
        }
        if (ended < 0 && errno != EINTR) {
            break;
        }
        pause_poll();
    }
    if (!leader_reaped || !WIFEXITED(child_status) || WEXITSTATUS(child_status) != 0) {
        fprintf(stderr, "FAIL QEMU did not exit successfully\n");
        goto done;
    }
    result = 0;

done:
    if (interrupted) {
        result = 1;
    }
    if (child > 0) {
        /* Only this child's process group is signalled. Its descendants inherit
         * it; subreaping proves closure even when QEMU exits before its stubs. */
        if (!leader_reaped) {
            kill(-child, SIGKILL);
        }
        for (unsigned int attempt = 0; attempt < 300; ++attempt) {
            int status;
            pid_t ended = waitpid(-1, &status, WNOHANG);
            if (ended == child) {
                leader_reaped = true;
                child_status = status;
            } else if (ended < 0 && errno == ECHILD) {
                tree_closed = true;
                break;
            } else if (ended == 0) {
                kill(-child, SIGKILL);
                pause_poll();
            }
        }
        if (!leader_reaped || !tree_closed) {
            result = 1;
        }
    }
    if (log >= 0) {
        if (fsync(log)) {
            result = 1;
        }
        close(log);
    }
    if (!result && !verify_log(log_path)) {
        result = 1;
    }
    if (pixels != MAP_FAILED) {
        munmap((void *)pixels, NEF_FRAME_BYTES);
    }
    if (ram >= 0) {
        close(ram);
    }
    if (frame >= 0) {
        close(frame);
    }
    if (nullfd >= 0) {
        close(nullfd);
    }
    alarm(0);
    int exit_code = !leader_reaped ? -1 : WIFEXITED(child_status) ? WEXITSTATUS(child_status)
                                                               : 128 + WTERMSIG(child_status);
#ifdef NEF_IOS_SWAP
    printf("NATIVE_EFI_SWAP_TREE leader_reaped=%d ECHILD=%d qemu_exit=%d\n",
           leader_reaped, tree_closed, exit_code);
    printf("RESULT=%s frames=%u gpu_path_complete=0\n",
           result ? "NATIVE_EFI_SWAP_INTEGRATION_FAIL" : "NATIVE_EFI_SWAP_INTEGRATION_PASS", checked);
#else
    printf("NATIVE_EFI_TREE leader_reaped=%d ECHILD=%d qemu_exit=%d\n",
           leader_reaped, tree_closed, exit_code);
    printf("RESULT=%s frames=%u gpu_path_complete=0\n",
           result ? "NATIVE_EFI_INTEGRATION_FAIL" : "NATIVE_EFI_INTEGRATION_PASS", checked);
#endif
    return result;
}
