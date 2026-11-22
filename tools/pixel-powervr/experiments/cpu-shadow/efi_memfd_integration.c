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
#include <stdbool.h>
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
    MAX_HEIGHT = 128,
    ROW_BYTES = WIDTH * 4,
    PAGE_BYTES = 16384,
    RAM_BYTES = PAGE_BYTES * 6,
    FRAME_OFFSET = PAGE_BYTES,
    ALIAS_BYTES = RAM_BYTES - FRAME_OFFSET,
    READBACK_ROW_BYTES = ROW_BYTES + 32,
};
static const uint64_t FIRST_GPA = UINT64_C(0x40000000);
static const uint64_t ALIAS_GPA = UINT64_C(0x50000000);
static unsigned int height = 64;
static bool fragmented;

static unsigned int frame_bytes(void) {
    return ROW_BYTES * height;
}

/* The second logical guest page can name a different, non-adjacent physical
 * file page. Both guest-physical views use the same permutation. */
static size_t file_offset(size_t logical) {
    return FRAME_OFFSET + logical + (fragmented && logical >= PAGE_BYTES ? PAGE_BYTES : 0);
}

static void write_frame(uint8_t *mapping, size_t mapping_offset, const uint8_t *expected) {
    for (size_t i = 0; i < frame_bytes(); ++i) {
        mapping[file_offset(i) - mapping_offset] = expected[i];
    }
}

static int check_ram(const uint8_t *mapping, size_t mapping_offset, const uint8_t *expected) {
    for (size_t i = 0; i < frame_bytes(); ++i) {
        if (mapping[file_offset(i) - mapping_offset] != expected[i]) {
            fprintf(stderr, "FAIL ordinary framebuffer byte changed at logical %zu\n", i);
            return -1;
        }
    }
    return 0;
}

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
    for (unsigned int y = 0; y < height; ++y) {
        for (unsigned int x = 0; x < WIDTH; ++x) {
            size_t at = (size_t)y * ROW_BYTES + x * 4;
            /* The second 16 KiB page has different bytes, so accidentally
             * repeating the first physical page cannot pass the fragmented case. */
            bytes[at + 0] = (((x / 8) ^ (y / 64) ^ phase) & 1) ? 255 : 0;
            bytes[at + 1] = (((y / 8) ^ phase) & 1) ? 255 : 0;
            bytes[at + 2] = (((x / 16) ^ (y / 16) ^ phase) & 1) ? 255 : 0;
            bytes[at + 3] = 255;
        }
    }
}

static void program_efi(RvgDevice *device, uint64_t address, unsigned int page_shift) {
    rvg_device_mmio_write(device, 0x1034, 0xf5);
    rvg_device_mmio_write(device, 0x1200, 1);
    rvg_device_mmio_write(device, 0x121c, (height << 16) | WIDTH);
    rvg_device_mmio_write(device, 0x1218, 32);
    rvg_device_mmio_write(device, 0x1228, ROW_BYTES);
    rvg_device_mmio_write(device, 0x1210, address >> page_shift);
    rvg_device_mmio_write(device, 0x1214, frame_bytes());
}

static int check_frame(RvgDisplay *display, RvgFrameTarget *target,
                       const uint8_t *expected, unsigned int phase) {
    uint8_t pixels[READBACK_ROW_BYTES * MAX_HEIGHT];
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
    for (size_t y = 0; y < height; ++y) {
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
           phase, frame_bytes(), wrong, changed_padding);
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
    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--guest-page-shift=12") == 0) {
            page_shift = 12;
        } else if (strcmp(argv[i], "--fragmented") == 0) {
            fragmented = true;
            height = MAX_HEIGHT;
        } else {
            fprintf(stderr, "usage: %s [--guest-page-shift=12] [--fragmented]\n", argv[0]);
            return 2;
        }
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
    uint8_t expected[ROW_BYTES * MAX_HEIGHT];
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
    alias = map_guest_ram(fd, ALIAS_BYTES, FRAME_OFFSET);
    if (ram == MAP_FAILED || alias == MAP_FAILED) {
        perror("mmap guest RAM");
        goto done;
    }
    memset(ram, 0x3c, RAM_BYTES);
    fill_frame(expected, 0);
    write_frame(ram, 0, expected);

    RvgMemoryRange ranges[4] = {0};
    RvgMemoryRangeFile files[4] = {0};
    ranges[0] = (RvgMemoryRange){.physical_address = FIRST_GPA,
        .physical_length = fragmented ? PAGE_BYTES * 2 : RAM_BYTES, .host_address = ram};
    files[0] = (RvgMemoryRangeFile){.fd = fd, .offset = 0};
    if (fragmented) {
        ranges[1] = (RvgMemoryRange){.physical_address = FIRST_GPA + PAGE_BYTES * 2,
            .physical_length = PAGE_BYTES, .host_address = ram + PAGE_BYTES * 3};
        files[1] = (RvgMemoryRangeFile){.fd = fd, .offset = PAGE_BYTES * 3};
        ranges[2] = (RvgMemoryRange){.physical_address = ALIAS_GPA,
            .physical_length = PAGE_BYTES, .host_address = alias};
        files[2] = (RvgMemoryRangeFile){.fd = fd, .offset = FRAME_OFFSET};
        ranges[3] = (RvgMemoryRange){.physical_address = ALIAS_GPA + PAGE_BYTES,
            .physical_length = PAGE_BYTES, .host_address = alias + PAGE_BYTES * 2};
        files[3] = (RvgMemoryRangeFile){.fd = fd, .offset = PAGE_BYTES * 3};
    } else {
        ranges[1] = (RvgMemoryRange){.physical_address = ALIAS_GPA,
            .physical_length = ALIAS_BYTES, .host_address = alias};
        files[1] = (RvgMemoryRangeFile){.fd = fd, .offset = FRAME_OFFSET};
    }
    RvgMemoryMap memory = {.ranges = ranges, .range_count = fragmented ? 4 : 2};
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
    RvgDisplayMode mode = {WIDTH, height, 0, 60.0};
    rvg_display_set_modes(display, &mode, 1);
    RvgFrameTargetConfig target_config = {
        .struct_size = sizeof target_config,
        .width = WIDTH,
        .height = height,
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
    write_frame(alias, FRAME_OFFSET, expected);
    if (check_frame(display, target, expected, 1) ||
        check_ram(ram, 0, expected)) {
        goto done;
    }

    /* Remap EFI to the registered alias GPA, whose RAM entry starts part-way
     * through the same memfd. Neither that offset nor FD lifetime may be lost. */
    fill_frame(expected, 2);
    write_frame(ram, 0, expected);
    presents = atomic_load_explicit(&callbacks.frames, memory_order_acquire);
    rvg_device_mmio_write(device, 0x1210, ALIAS_GPA >> page_shift);
    if (wait_for_frame(&callbacks, presents) || check_frame(display, target, expected, 2) ||
        check_ram(alias, FRAME_OFFSET, expected)) {
        goto done;
    }

    if (get_counts(device, &after)) {
        goto done;
    }
    if (after.chunks_created <= before.chunks_created ||
        after.views_created < before.views_created + 2 ||
        after.epochs_prepared < before.epochs_prepared + 3 ||
        after.epochs_finished < before.epochs_finished + 3 ||
        after.bytes_uploaded < before.bytes_uploaded + frame_bytes() * 3) {
        fprintf(stderr, "FAIL no complete device-backed CPU-shadow execution witness\n");
        goto done;
    }
    for (size_t i = 0; i < RAM_BYTES; ++i) {
        bool used = i >= FRAME_OFFSET && i < FRAME_OFFSET + PAGE_BYTES;
        if (fragmented) {
            used |= i >= PAGE_BYTES * 3 && i < PAGE_BYTES * 4;
        }
        if (!used && ram[i] != 0x3c) {
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
        munmap(alias, ALIAS_BYTES);
    }
    if (ram != MAP_FAILED) {
        munmap(ram, RAM_BYTES);
    }
    if (fd >= 0) {
        close(fd);
    }
    alarm(0);
    printf("{\"status\":\"%s\",\"guest_page_shift\":%u,\"frames_checked\":%u,"
           "\"fragmented\":%s,\"frame_bytes\":%u,"
           "\"chunks_created\":%" PRIu64 ",\"views_created\":%" PRIu64 ","
           "\"epochs_prepared\":%" PRIu64 ",\"epochs_finished\":%" PRIu64 ","
           "\"bytes_uploaded\":%" PRIu64 ",\"bytes_scattered\":%" PRIu64 ","
           "\"native_guest_execution_tested\":false,\"gpu_path_complete\":false}\n",
           result ? "EFI_CPU_SHADOW_FAIL" : "EFI_CPU_SHADOW_PASS", page_shift,
           result ? 0u : 3u, fragmented ? "true" : "false", frame_bytes(),
           after.chunks_created, after.views_created,
           after.epochs_prepared, after.epochs_finished,
           after.bytes_uploaded, after.bytes_scattered);
    return result;
}
