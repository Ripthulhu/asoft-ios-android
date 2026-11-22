/*
 * Real reims device/display integration over ordinary guest RAM.
 *
 * This deliberately does not call the standalone producer API. EFI maps a
 * registered guest memfd through the product task-memory path, creates its
 * no-copy buffer and linear texture, and submits a real display frame. Runtime
 * counters must witness actual CPU-shadow allocation and uploads. A pass is
 * evidence for this path, not a guest boot or general Metal qualification.
 */
#define _GNU_SOURCE
#include "reims_vgpu.h"

#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

enum {
    WIDTH = 64,
    HEIGHT = 64,
    ROW_BYTES = WIDTH * 4,
    FRAME_BYTES = ROW_BYTES * HEIGHT,
    RAM_BYTES = FRAME_BYTES * 4,
    FRAME_OFFSET = FRAME_BYTES,
    READBACK_ROW_BYTES = ROW_BYTES + 32,
};
static const uint64_t FIRST_GPA = UINT64_C(0x40000000);
static const uint64_t ALIAS_GPA = UINT64_C(0x50000000);

/* Isolated ARM guest mappings must not inherit an accidental 4 KiB-only host
 * address alignment. MAP_FIXED replaces only our own private reservation. */
static void *map_guest_ram(int fd, size_t length, off_t offset) {
    const size_t alignment = 65536;
    size_t reserve_length = length + alignment;
    void *reserve = mmap(NULL, reserve_length, PROT_NONE,
                         MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (reserve == MAP_FAILED) {
        return MAP_FAILED;
    }
    uintptr_t aligned = ((uintptr_t)reserve + alignment - 1) & ~(alignment - 1);
    void *mapped = mmap((void *)aligned, length, PROT_READ | PROT_WRITE,
                       MAP_SHARED | MAP_FIXED, fd, offset);
    if (mapped == MAP_FAILED) {
        int error = errno;
        munmap(reserve, reserve_length);
        errno = error;
        return MAP_FAILED;
    }
    size_t prefix = aligned - (uintptr_t)reserve;
    size_t suffix = reserve_length - prefix - length;
    if (prefix) {
        munmap(reserve, prefix);
    }
    if (suffix) {
        munmap((uint8_t *)mapped + length, suffix);
    }
    return mapped;
}

typedef struct {
    atomic_uint frames;
    atomic_uint interrupts;
} Callbacks;

static void raise_interrupt(void *ctx, uint32_t vector) {
    Callbacks *callbacks = ctx;
    (void)vector;
    atomic_fetch_add_explicit(&callbacks->interrupts, 1, memory_order_relaxed);
}

static void new_frame(void *ctx) {
    Callbacks *callbacks = ctx;
    atomic_fetch_add_explicit(&callbacks->frames, 1, memory_order_release);
}

static void log_line(void *ctx, RvgLogLevel level, const char *target,
                     size_t target_length, const char *message, size_t message_length) {
    (void)ctx;
    fprintf(stderr, "reims[%" PRIu32 "] %.*s: %.*s\n", level,
            (int)target_length, target, (int)message_length, message);
}

static int failed_status(const char *operation, RvgStatus status) {
    if (status == RVG_OK) {
        return 0;
    }
    fprintf(stderr, "FAIL %s: status=%" PRIu32 " (%s)\n", operation, status,
            rvg_status_message(status));
    return -1;
}

static int wait_for_frame(Callbacks *callbacks, unsigned int previous) {
    struct timespec pause = {.tv_sec = 0, .tv_nsec = 10000000};
    for (unsigned int i = 0; i < 300; ++i) {
        if (atomic_load_explicit(&callbacks->frames, memory_order_acquire) > previous) {
            return 0;
        }
        nanosleep(&pause, NULL);
    }
    fprintf(stderr, "FAIL timed out waiting for EFI presentation\n");
    return -1;
}

/* Binary color components avoid assumptions about normalized rounding. Tile
 * positions distinguish both axes, and each successive phase inverts RGB. */
static void fill_frame(uint8_t *bytes, unsigned int phase) {
    for (unsigned int y = 0; y < HEIGHT; ++y) {
        for (unsigned int x = 0; x < WIDTH; ++x) {
            size_t at = (size_t)y * ROW_BYTES + x * 4;
            bytes[at + 0] = (((x / 8) ^ phase) & 1) ? 255 : 0;
            bytes[at + 1] = (((y / 8) ^ phase) & 1) ? 255 : 0;
            bytes[at + 2] = (((x / 16) ^ (y / 16) ^ phase) & 1) ? 255 : 0;
            bytes[at + 3] = 255;
        }
    }
}

static void program_efi(RvgDevice *device, uint64_t address, unsigned int page_shift) {
    rvg_device_mmio_write(device, 0x1034, 0xf5);
    rvg_device_mmio_write(device, 0x1200, 1);
    rvg_device_mmio_write(device, 0x121c, (HEIGHT << 16) | WIDTH);
    rvg_device_mmio_write(device, 0x1218, 32);
    rvg_device_mmio_write(device, 0x1228, ROW_BYTES);
    rvg_device_mmio_write(device, 0x1210, address >> page_shift);
    rvg_device_mmio_write(device, 0x1214, FRAME_BYTES);
}

static int check_frame(RvgDisplay *display, RvgFrameTarget *target,
                       const uint8_t *expected, unsigned int phase) {
    uint8_t pixels[READBACK_ROW_BYTES * HEIGHT];
    RvgFrame *frame = NULL;
    if (failed_status("encode frame", rvg_display_encode_frame(display, target, NULL, &frame))) {
        return -1;
    }
    int result = failed_status("commit frame", rvg_frame_commit(frame));
    if (!result) {
        result = failed_status("wait frame", rvg_frame_wait(frame));
    }
    rvg_frame_release(frame);
    if (result) {
        return result;
    }
    memset(pixels, 0xa5, sizeof pixels);
    if (failed_status("read frame", rvg_frame_target_read_pixels(
            target, pixels, READBACK_ROW_BYTES, sizeof pixels))) {
        return -1;
    }
    size_t wrong = 0;
    size_t changed_padding = 0;
    for (size_t y = 0; y < HEIGHT; ++y) {
        for (size_t x = 0; x < ROW_BYTES; ++x) {
            uint8_t actual = pixels[y * READBACK_ROW_BYTES + x];
            uint8_t wanted = expected[y * ROW_BYTES + x];
            if (actual != wanted) {
                if (!wrong) {
                    fprintf(stderr,
                            "FAIL phase=%u first mismatch at row=%zu byte=%zu: %u != %u\n",
                            phase, y, x, actual, wanted);
                }
                ++wrong;
            }
        }
        for (size_t x = ROW_BYTES; x < READBACK_ROW_BYTES; ++x) {
            changed_padding += pixels[y * READBACK_ROW_BYTES + x] != 0xa5;
        }
    }
    printf("FRAME phase=%u compared=%u wrong=%zu changed_padding=%zu\n",
           phase, FRAME_BYTES, wrong, changed_padding);
    return wrong || changed_padding ? -1 : 0;
}

static int get_counts(RvgDevice *device, RvgCpuShadowCounts *counts) {
    memset(counts, 0, sizeof *counts);
    counts->struct_size = sizeof *counts;
    return failed_status("CPU-shadow counts",
                         rvg_device_cpu_shadow_counts(device, counts, sizeof *counts));
}

int main(int argc, char **argv) {
    unsigned int page_shift = 14;
    if (argc == 2 && strcmp(argv[1], "--guest-page-shift=12") == 0) {
        page_shift = 12;
    } else if (argc != 1) {
        fprintf(stderr, "usage: %s [--guest-page-shift=12]\n", argv[0]);
        return 2;
    }
    const char *enabled = getenv("REIMS_VGPU_CPU_SHADOW");
    if (!enabled || strcmp(enabled, "1") != 0) {
        fprintf(stderr, "FAIL explicitly select REIMS_VGPU_CPU_SHADOW=1\n");
        return 2;
    }

    /* Ordinary memfd mappings only. Never map or execute producer allocations. */
    setvbuf(stdout, NULL, _IOLBF, 0);
    alarm(30);
    int result = 1;
    int fd = -1;
    uint8_t *ram = MAP_FAILED;
    uint8_t *alias = MAP_FAILED;
    uint8_t expected[FRAME_BYTES];
    RvgDevice *device = NULL;
    RvgDisplay *display = NULL;
    RvgFrameTarget *target = NULL;
    Callbacks callbacks = {0};
    RvgCpuShadowCounts before = {0}, after = {0};

    fd = (int)syscall(SYS_memfd_create, "reims-efi-guest-ram", MFD_CLOEXEC | MFD_ALLOW_SEALING);
    if (fd < 0 || ftruncate(fd, RAM_BYTES) ||
        fcntl(fd, F_ADD_SEALS, F_SEAL_SHRINK | F_SEAL_GROW) != 0) {
        perror("memfd guest RAM");
        goto done;
    }
    ram = map_guest_ram(fd, RAM_BYTES, 0);
    /* A distinct CPU address and a nonzero file offset refer to the same page. */
    alias = map_guest_ram(fd, FRAME_BYTES * 2, FRAME_OFFSET);
    if (ram == MAP_FAILED || alias == MAP_FAILED) {
        perror("mmap guest RAM");
        goto done;
    }
    memset(ram, 0x3c, RAM_BYTES);
    fill_frame(expected, 0);
    memcpy(ram + FRAME_OFFSET, expected, FRAME_BYTES);

    RvgMemoryRange ranges[] = {
        {.physical_address = FIRST_GPA, .physical_length = RAM_BYTES, .host_address = ram},
        {.physical_address = ALIAS_GPA, .physical_length = FRAME_BYTES * 2, .host_address = alias},
    };
    RvgMemoryRangeFile files[] = {
        {.fd = fd, .flags = 0, .offset = 0},
        {.fd = fd, .flags = 0, .offset = FRAME_OFFSET},
    };
    RvgMemoryMap memory = {.ranges = ranges, .range_count = 2};
    RvgHostCallbacks host_callbacks = {
        .struct_size = sizeof host_callbacks,
        .ctx = &callbacks,
        .raise_interrupt = raise_interrupt,
    };
    RvgDeviceConfig config = {
        .struct_size = sizeof config,
        .display_port_count = 1,
        .use_iosurface_mapper = true,
        .process_isolation = true,
        .memory_map = &memory,
        .callbacks = &host_callbacks,
        .memory_files = files,
    };
    rvg_log_set_handler(log_line, NULL, RVG_LOG_INFO);
    if (failed_status("create device", rvg_device_create(&config, &device))) {
        goto done;
    }
    /* The public C API promises its own duplicated descriptors after create. */
    close(fd);
    fd = -1;
    if (get_counts(device, &before)) {
        goto done;
    }

    RvgDisplayCallbacks display_callbacks = {
        .struct_size = sizeof display_callbacks,
        .ctx = &callbacks,
        .new_frame = new_frame,
    };
    RvgDisplayConfig display_config = {
        .struct_size = sizeof display_config,
        .serial_number = 0x53484457,
        .port = 0,
        .width_millimeters = 64,
        .height_millimeters = 64,
        .callbacks = &display_callbacks,
    };
    if (failed_status("create display", rvg_display_create(device, &display_config, &display))) {
        goto done;
    }
    RvgDisplayMode mode = {WIDTH, HEIGHT, 0, 60.0};
    rvg_display_set_modes(display, &mode, 1);
    RvgFrameTargetConfig target_config = {
        .struct_size = sizeof target_config,
        .width = WIDTH,
        .height = HEIGHT,
        .format = RVG_PIXEL_FORMAT_BGRA8_UNORM,
    };
    if (failed_status("create target", rvg_frame_target_create(device, &target_config, &target))) {
        goto done;
    }

    unsigned int presents = atomic_load_explicit(&callbacks.frames, memory_order_acquire);
    program_efi(device, FIRST_GPA + FRAME_OFFSET, page_shift);
    if (wait_for_frame(&callbacks, presents) || check_frame(display, target, expected, 0)) {
        goto done;
    }

    /* Change CPU bytes through the second address after GPU completion. The
     * same live EFI resource must see the new data on its next submission. */
    fill_frame(expected, 1);
    memcpy(alias, expected, FRAME_BYTES);
    if (check_frame(display, target, expected, 1) ||
        memcmp(ram + FRAME_OFFSET, expected, FRAME_BYTES) != 0) {
        goto done;
    }

    /* Remap EFI to the registered alias GPA, whose RAM entry starts part-way
     * through the same memfd. Neither that offset nor FD lifetime may be lost. */
    fill_frame(expected, 2);
    memcpy(ram + FRAME_OFFSET, expected, FRAME_BYTES);
    presents = atomic_load_explicit(&callbacks.frames, memory_order_acquire);
    rvg_device_mmio_write(device, 0x1210, ALIAS_GPA >> page_shift);
    if (wait_for_frame(&callbacks, presents) || check_frame(display, target, expected, 2) ||
        memcmp(alias, expected, FRAME_BYTES) != 0) {
        goto done;
    }

    if (get_counts(device, &after)) {
        goto done;
    }
    if (after.chunks_created <= before.chunks_created ||
        after.views_created < before.views_created + 2 ||
        after.epochs_prepared < before.epochs_prepared + 3 ||
        after.epochs_finished < before.epochs_finished + 3 ||
        after.bytes_uploaded < before.bytes_uploaded + FRAME_BYTES * 3) {
        fprintf(stderr, "FAIL no complete device-backed CPU-shadow execution witness\n");
        goto done;
    }
    for (size_t i = 0; i < RAM_BYTES; ++i) {
        if ((i < FRAME_OFFSET || i >= FRAME_OFFSET + FRAME_BYTES) && ram[i] != 0x3c) {
            fprintf(stderr, "FAIL unrelated guest byte changed at %zu\n", i);
            goto done;
        }
    }
    result = 0;

done:
    if (device) {
        rvg_device_mmio_write(device, 0x1200, 0);
    }
    rvg_frame_target_release(target);
    rvg_display_release(display);
    rvg_device_release(device);
    rvg_log_set_handler(NULL, NULL, RVG_LOG_INFO);
    if (alias != MAP_FAILED) {
        munmap(alias, FRAME_BYTES * 2);
    }
    if (ram != MAP_FAILED) {
        munmap(ram, RAM_BYTES);
    }
    if (fd >= 0) {
        close(fd);
    }
    alarm(0);
    printf("{\"status\":\"%s\",\"guest_page_shift\":%u,\"frames_checked\":%u,"
           "\"chunks_created\":%" PRIu64 ",\"views_created\":%" PRIu64 ","
           "\"epochs_prepared\":%" PRIu64 ",\"epochs_finished\":%" PRIu64 ","
           "\"bytes_uploaded\":%" PRIu64 ",\"bytes_scattered\":%" PRIu64 ","
           "\"native_guest_execution_tested\":false,\"gpu_path_complete\":false}\n",
           result ? "EFI_CPU_SHADOW_FAIL" : "EFI_CPU_SHADOW_PASS", page_shift,
           result ? 0u : 3u, after.chunks_created, after.views_created,
           after.epochs_prepared, after.epochs_finished,
           after.bytes_uploaded, after.bytes_scattered);
    return result;
}
