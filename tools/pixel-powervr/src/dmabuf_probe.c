/*
 * Minimal Android Vulkan / UDMABUF interoperability probe.
 *
 * Build (NDK r29, arm64):
 *   aarch64-linux-android35-clang -std=c11 -O2 -Wall -Wextra \
 *     -Wl,-z,max-page-size=16384 dmabuf_probe.c -lvulkan -o dmabuf_probe
 *
 * This creates only anonymous, synthetic data. It neither changes kernel state
 * nor loads modules. Four discontiguous pages of an eight-page memfd are exported
 * in a different order, imported as one Vulkan buffer, and exercised both ways:
 *   1. CPU writes original memfd -> GPU copies -> CPU checks Vulkan readback.
 *   2. GPU fills each logical page -> CPU checks original memfd and guard pages.
 * The guard check observes CPU-visible values only: the unexported guard pages
 * are outside this DMA-BUF's cache-maintenance range. It cannot prove absence of
 * device out-of-bounds writes on a noncoherent system.
 *
 * PASS establishes this small transfer-buffer path only. It does not establish
 * sparse binding, device-address/shader access, large guest RAM windows, image
 * import, arbitrary malloc import, or support for the complete asoft renderer.
 *
 * Exit status: 0 PASS, 1 FAIL, 2 BLOCKED, 3 UNSUPPORTED.
 * Kernel and Vulkan documentation consulted:
 *   https://www.kernel.org/doc/html/latest/driver-api/dma-buf.html
 *   https://github.com/torvalds/linux/blob/v6.6/drivers/dma-buf/udmabuf.c
 *   https://docs.vulkan.org/refpages/latest/refpages/source/VkImportMemoryFdInfoKHR.html
 *   https://docs.vulkan.org/spec/latest/chapters/synchronization.html
 */
#define _GNU_SOURCE 1
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <linux/dma-buf.h>
#include <linux/memfd.h>
#include <linux/udmabuf.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <unistd.h>
#include <vulkan/vulkan.h>

enum { RESULT_PASS = 0, RESULT_FAIL = 1, RESULT_BLOCKED = 2,
       RESULT_UNSUPPORTED = 3, BACKING_PAGES = 8, EXPORTED_PAGES = 4 };
static const unsigned page_order[EXPORTED_PAGES] = {5, 0, 7, 2};
static const uint64_t fence_timeout_ns = UINT64_C(5000000000);

struct context {
    VkInstance instance;
    VkPhysicalDevice physical;
    VkDevice device;
    VkQueue queue;
    uint32_t family;
    VkPhysicalDeviceMemoryProperties memory_properties;
    VkBuffer imported_buffer, readback_buffer;
    VkDeviceMemory imported_memory, readback_memory;
    VkCommandPool pool;
    VkCommandBuffer command;
    VkFence fence;
    void *readback_map;
    VkDeviceSize readback_allocation_size;
    bool readback_coherent;
    int memfd, udmabuf, dmafd, import_fd;
    void *guest_map;
    size_t backing_size, exported_size, page_size;
};

static int result_message(int result, const char *format, ...) {
    static const char *const labels[] = {"PASS", "FAIL", "BLOCKED", "UNSUPPORTED"};
    va_list args;
    printf("RESULT=%s: ", labels[result]);
    va_start(args, format);
    vprintf(format, args);
    va_end(args);
    putchar('\n');
    fflush(stdout);
    return result;
}

static const char *vk_result_name(VkResult result) {
    switch (result) {
    case VK_SUCCESS: return "VK_SUCCESS";
    case VK_TIMEOUT: return "VK_TIMEOUT";
    case VK_INCOMPLETE: return "VK_INCOMPLETE";
    case VK_ERROR_OUT_OF_HOST_MEMORY: return "VK_ERROR_OUT_OF_HOST_MEMORY";
    case VK_ERROR_OUT_OF_DEVICE_MEMORY: return "VK_ERROR_OUT_OF_DEVICE_MEMORY";
    case VK_ERROR_INITIALIZATION_FAILED: return "VK_ERROR_INITIALIZATION_FAILED";
    case VK_ERROR_DEVICE_LOST: return "VK_ERROR_DEVICE_LOST";
    case VK_ERROR_MEMORY_MAP_FAILED: return "VK_ERROR_MEMORY_MAP_FAILED";
    case VK_ERROR_EXTENSION_NOT_PRESENT: return "VK_ERROR_EXTENSION_NOT_PRESENT";
    case VK_ERROR_FEATURE_NOT_PRESENT: return "VK_ERROR_FEATURE_NOT_PRESENT";
    case VK_ERROR_INCOMPATIBLE_DRIVER: return "VK_ERROR_INCOMPATIBLE_DRIVER";
    case VK_ERROR_INVALID_EXTERNAL_HANDLE: return "VK_ERROR_INVALID_EXTERNAL_HANDLE";
    default: return "VkResult";
    }
}

static int syscall_failure_class(int err) {
    if (err == EACCES || err == EPERM || err == ENOENT || err == ENODEV ||
        err == ENOSYS) return RESULT_BLOCKED;
    if (err == ENOTTY || err == EOPNOTSUPP) return RESULT_UNSUPPORTED;
    return RESULT_FAIL;
}

/* Retry interruption / transient busy responses a finite number of times. */
static int dma_sync(int fd, uint64_t flags) {
    struct dma_buf_sync sync = {.flags = flags};
    int ret;
    for (unsigned attempt = 0; attempt < 8; ++attempt) {
        ret = ioctl(fd, DMA_BUF_IOCTL_SYNC, &sync);
        if (ret == 0 || (errno != EINTR && errno != EAGAIN)) return ret;
    }
    return -1;
}

static bool has_extension(const VkExtensionProperties *properties, uint32_t count,
                          const char *name) {
    for (uint32_t i = 0; i < count; ++i)
        if (strcmp(properties[i].extensionName, name) == 0) return true;
    return false;
}

static uint32_t memory_type(const struct context *ctx, uint32_t bits,
                            VkMemoryPropertyFlags required,
                            VkMemoryPropertyFlags preferred) {
    uint32_t fallback = UINT32_MAX;
    for (uint32_t i = 0; i < ctx->memory_properties.memoryTypeCount; ++i) {
        const VkMemoryPropertyFlags flags =
            ctx->memory_properties.memoryTypes[i].propertyFlags;
        if ((bits & (UINT32_C(1) << i)) && (flags & required) == required) {
            if ((flags & preferred) == preferred) return i;
            if (fallback == UINT32_MAX) fallback = i;
        }
    }
    return fallback;
}

static uint32_t guard_word(unsigned page, size_t word) {
    return UINT32_C(0x19f37a6b) ^ ((uint32_t)page * UINT32_C(0x9e3779b9)) ^
           ((uint32_t)word * UINT32_C(0x45d9f3b));
}

static uint32_t guest_word(unsigned page, size_t word) {
    return guard_word(page, word) ^ UINT32_C(0xa5c369f0);
}

static uint32_t gpu_word(unsigned logical_page) {
    return UINT32_C(0xd00d0000) | ((logical_page + 1u) * UINT32_C(0x111));
}

static void acquire_foreign(const struct context *ctx, VkAccessFlags access) {
    /* UDMABUF is a non-Vulkan exporter; EXTERNAL's same-driver assumption is
     * inappropriate. CPU cache maintenance is separately done through SYNC. */
    const VkBufferMemoryBarrier barrier = {
        .sType = VK_STRUCTURE_TYPE_BUFFER_MEMORY_BARRIER,
        .srcAccessMask = 0,
        .dstAccessMask = access,
        .srcQueueFamilyIndex = VK_QUEUE_FAMILY_FOREIGN_EXT,
        .dstQueueFamilyIndex = ctx->family,
        .buffer = ctx->imported_buffer,
        .offset = 0,
        .size = ctx->exported_size,
    };
    vkCmdPipelineBarrier(ctx->command, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,
                         VK_PIPELINE_STAGE_TRANSFER_BIT, 0, 0, NULL, 1, &barrier,
                         0, NULL);
}

static void release_foreign(const struct context *ctx, VkAccessFlags access) {
    const VkBufferMemoryBarrier barrier = {
        .sType = VK_STRUCTURE_TYPE_BUFFER_MEMORY_BARRIER,
        .srcAccessMask = access,
        .dstAccessMask = 0,
        .srcQueueFamilyIndex = ctx->family,
        .dstQueueFamilyIndex = VK_QUEUE_FAMILY_FOREIGN_EXT,
        .buffer = ctx->imported_buffer,
        .offset = 0,
        .size = ctx->exported_size,
    };
    vkCmdPipelineBarrier(ctx->command, VK_PIPELINE_STAGE_TRANSFER_BIT,
                         VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, 0, 0, NULL, 1,
                         &barrier, 0, NULL);
}

static VkResult submit_and_wait(struct context *ctx, const char *phase) {
    VkResult result = vkEndCommandBuffer(ctx->command);
    if (result != VK_SUCCESS) return result;
    result = vkResetFences(ctx->device, 1, &ctx->fence);
    if (result != VK_SUCCESS) return result;
    const VkSubmitInfo submit = {
        .sType = VK_STRUCTURE_TYPE_SUBMIT_INFO,
        .commandBufferCount = 1,
        .pCommandBuffers = &ctx->command,
    };
    result = vkQueueSubmit(ctx->queue, 1, &submit, ctx->fence);
    if (result != VK_SUCCESS) return result;
    result = vkWaitForFences(ctx->device, 1, &ctx->fence, VK_TRUE, fence_timeout_ns);
    if (result != VK_SUCCESS) {
        result_message(RESULT_FAIL, "%s fence: %s (%d); terminating without "
                       "freeing potentially in-flight Vulkan resources",
                       phase, vk_result_name(result), result);
        /* Do not perform unbounded vkDeviceWaitIdle or free pending commands.
         * Process exit lets the kernel reclaim this process's resources. */
        _Exit(RESULT_FAIL);
    }
    printf("%s: GPU fence completed (timeout limit 5 seconds)\n", phase);
    return VK_SUCCESS;
}

static void cleanup(struct context *ctx) {
    if (ctx->device) {
        if (ctx->readback_map) vkUnmapMemory(ctx->device, ctx->readback_memory);
        if (ctx->fence) vkDestroyFence(ctx->device, ctx->fence, NULL);
        if (ctx->pool) vkDestroyCommandPool(ctx->device, ctx->pool, NULL);
        if (ctx->readback_buffer)
            vkDestroyBuffer(ctx->device, ctx->readback_buffer, NULL);
        if (ctx->readback_memory)
            vkFreeMemory(ctx->device, ctx->readback_memory, NULL);
        if (ctx->imported_buffer)
            vkDestroyBuffer(ctx->device, ctx->imported_buffer, NULL);
        if (ctx->imported_memory)
            vkFreeMemory(ctx->device, ctx->imported_memory, NULL);
        vkDestroyDevice(ctx->device, NULL);
    }
    if (ctx->instance) vkDestroyInstance(ctx->instance, NULL);
    if (ctx->guest_map != MAP_FAILED) munmap(ctx->guest_map, ctx->backing_size);
    if (ctx->import_fd >= 0) close(ctx->import_fd);
    if (ctx->dmafd >= 0) close(ctx->dmafd);
    if (ctx->udmabuf >= 0) close(ctx->udmabuf);
    if (ctx->memfd >= 0) close(ctx->memfd);
}

#define STOP(code, ...) do { result = result_message((code), __VA_ARGS__); \
                            goto done; } while (0)
#define CHECK_VK(call) do { VkResult vr_ = (call); if (vr_ != VK_SUCCESS) \
    STOP(RESULT_FAIL, "%s: %s (%d)", #call, vk_result_name(vr_), vr_); } while (0)
#define CHECK_SYS(call) do { if ((call) < 0) { int err_ = errno; \
    STOP(syscall_failure_class(err_), "%s: errno=%d (%s)", #call, err_, \
         strerror(err_)); } } while (0)

int main(void) {
    struct context ctx = {.memfd = -1, .udmabuf = -1, .dmafd = -1,
                          .import_fd = -1, .guest_map = MAP_FAILED};
    int result = RESULT_FAIL;
    VkPhysicalDevice *devices = NULL;
    VkExtensionProperties *extensions = NULL;
    VkQueueFamilyProperties *families = NULL;
    struct udmabuf_create_list *list = NULL;
    const char *const required_extensions[] = {
        VK_KHR_EXTERNAL_MEMORY_FD_EXTENSION_NAME,
        VK_EXT_EXTERNAL_MEMORY_DMA_BUF_EXTENSION_NAME,
        VK_EXT_QUEUE_FAMILY_FOREIGN_EXTENSION_NAME,
    };
    const VkBufferUsageFlags buffer_usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT |
        VK_BUFFER_USAGE_TRANSFER_SRC_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT;
    const VkExternalMemoryHandleTypeFlagBits handle_type =
        VK_EXTERNAL_MEMORY_HANDLE_TYPE_DMA_BUF_BIT_EXT;
    setvbuf(stdout, NULL, _IOLBF, 0);
    printf("powervr dmabuf probe v1; uid=%lu euid=%lu\n",
           (unsigned long)getuid(), (unsigned long)geteuid());

    const long page_size = sysconf(_SC_PAGESIZE);
    if (page_size <= 0 || page_size > 65536 || (page_size & (page_size - 1)) != 0)
        STOP(RESULT_UNSUPPORTED, "host page size %ld outside small-probe limits",
             page_size);
    ctx.page_size = (size_t)page_size;
    ctx.backing_size = BACKING_PAGES * ctx.page_size;
    ctx.exported_size = EXPORTED_PAGES * ctx.page_size;
    printf("host_page=%zu backing_bytes=%zu exported_bytes=%zu "
           "page_order=5,0,7,2\n", ctx.page_size, ctx.backing_size,
           ctx.exported_size);

    const VkApplicationInfo app_info = {
        .sType = VK_STRUCTURE_TYPE_APPLICATION_INFO,
        .pApplicationName = "powervr-dmabuf-probe",
        .applicationVersion = 1,
        .apiVersion = VK_API_VERSION_1_1,
    };
    const VkInstanceCreateInfo instance_info = {
        .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
        .pApplicationInfo = &app_info,
    };
    VkResult vr = vkCreateInstance(&instance_info, NULL, &ctx.instance);
    if (vr != VK_SUCCESS)
        STOP(vr == VK_ERROR_INCOMPATIBLE_DRIVER ? RESULT_UNSUPPORTED : RESULT_FAIL,
             "vkCreateInstance: %s (%d)", vk_result_name(vr), vr);
    uint32_t device_count = 0;
    CHECK_VK(vkEnumeratePhysicalDevices(ctx.instance, &device_count, NULL));
    if (!device_count) STOP(RESULT_BLOCKED, "no Vulkan physical device visible");
    devices = calloc(device_count, sizeof(*devices));
    if (!devices) STOP(RESULT_FAIL, "host allocation failed");
    CHECK_VK(vkEnumeratePhysicalDevices(ctx.instance, &device_count, devices));
    ctx.physical = devices[0];
    for (uint32_t i = 0; i < device_count; ++i) {
        VkPhysicalDeviceProperties candidate;
        vkGetPhysicalDeviceProperties(devices[i], &candidate);
        if (candidate.vendorID == 0x1010) { ctx.physical = devices[i]; break; }
    }
    VkPhysicalDeviceProperties properties;
    vkGetPhysicalDeviceProperties(ctx.physical, &properties);
    printf("GPU=%s vendor=0x%04x device=0x%08x API=%u.%u.%u driver=0x%08x\n",
           properties.deviceName, properties.vendorID, properties.deviceID,
           VK_API_VERSION_MAJOR(properties.apiVersion),
           VK_API_VERSION_MINOR(properties.apiVersion),
           VK_API_VERSION_PATCH(properties.apiVersion), properties.driverVersion);
    if (properties.apiVersion < VK_API_VERSION_1_1)
        STOP(RESULT_UNSUPPORTED, "Vulkan 1.1 is required by this probe");
    vkGetPhysicalDeviceMemoryProperties(ctx.physical, &ctx.memory_properties);
    uint32_t extension_count = 0;
    CHECK_VK(vkEnumerateDeviceExtensionProperties(ctx.physical, NULL,
                                                  &extension_count, NULL));
    extensions = calloc(extension_count ? extension_count : 1, sizeof(*extensions));
    if (!extensions) STOP(RESULT_FAIL, "host allocation failed");
    CHECK_VK(vkEnumerateDeviceExtensionProperties(ctx.physical, NULL,
                                                &extension_count, extensions));
    bool missing_extension = false;
    for (size_t i = 0; i < sizeof(required_extensions) / sizeof(*required_extensions);
         ++i) {
        bool present = has_extension(extensions, extension_count,
                                     required_extensions[i]);
        printf("extension %s=%s\n", required_extensions[i], present ? "yes" : "no");
        missing_extension |= !present;
    }
    printf("extension %s=%s (not required by this probe)\n",
           VK_EXT_EXTERNAL_MEMORY_HOST_EXTENSION_NAME,
           has_extension(extensions, extension_count,
                         VK_EXT_EXTERNAL_MEMORY_HOST_EXTENSION_NAME) ? "yes" : "no");
    if (missing_extension)
        STOP(RESULT_UNSUPPORTED, "a required DMA-BUF / FD / foreign-queue extension "
             "is missing");
    const VkPhysicalDeviceExternalBufferInfo external_query = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_EXTERNAL_BUFFER_INFO,
        .usage = buffer_usage,
        .handleType = handle_type,
    };
    VkExternalBufferProperties external_properties = {
        .sType = VK_STRUCTURE_TYPE_EXTERNAL_BUFFER_PROPERTIES,
    };
    vkGetPhysicalDeviceExternalBufferProperties(ctx.physical, &external_query,
                                                 &external_properties);
    const VkExternalMemoryProperties ep = external_properties.externalMemoryProperties;
    printf("external_buffer usage=0x%x features=0x%x compatible_handles=0x%x "
           "export_from_imported=0x%x\n", buffer_usage, ep.externalMemoryFeatures,
           ep.compatibleHandleTypes, ep.exportFromImportedHandleTypes);
    if (!(ep.externalMemoryFeatures & VK_EXTERNAL_MEMORY_FEATURE_IMPORTABLE_BIT) ||
        !(ep.compatibleHandleTypes & handle_type))
        STOP(RESULT_UNSUPPORTED, "DMA-BUF not importable for a storage/transfer buffer");

    uint32_t family_count = 0;
    vkGetPhysicalDeviceQueueFamilyProperties(ctx.physical, &family_count, NULL);
    families = calloc(family_count ? family_count : 1, sizeof(*families));
    if (!families) STOP(RESULT_FAIL, "host allocation failed");
    vkGetPhysicalDeviceQueueFamilyProperties(ctx.physical, &family_count, families);
    ctx.family = UINT32_MAX;
    for (uint32_t i = 0; i < family_count; ++i) {
        if (families[i].queueCount && (families[i].queueFlags &
            (VK_QUEUE_TRANSFER_BIT | VK_QUEUE_GRAPHICS_BIT | VK_QUEUE_COMPUTE_BIT))) {
            ctx.family = i;
            break;
        }
    }
    if (ctx.family == UINT32_MAX) STOP(RESULT_UNSUPPORTED, "no transfer-capable queue");
    printf("queue_family=%u flags=0x%x\n", ctx.family,
           families[ctx.family].queueFlags);
    const float priority = 1.0f;
    const VkDeviceQueueCreateInfo queue_info = {
        .sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
        .queueFamilyIndex = ctx.family,
        .queueCount = 1,
        .pQueuePriorities = &priority,
    };
    const VkDeviceCreateInfo device_info = {
        .sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,
        .queueCreateInfoCount = 1,
        .pQueueCreateInfos = &queue_info,
        .enabledExtensionCount = sizeof(required_extensions) / sizeof(*required_extensions),
        .ppEnabledExtensionNames = required_extensions,
    };
    CHECK_VK(vkCreateDevice(ctx.physical, &device_info, NULL, &ctx.device));
    vkGetDeviceQueue(ctx.device, ctx.family, 0, &ctx.queue);
    PFN_vkGetMemoryFdPropertiesKHR get_fd_properties =
        (PFN_vkGetMemoryFdPropertiesKHR)vkGetDeviceProcAddr(
            ctx.device, "vkGetMemoryFdPropertiesKHR");
    if (!get_fd_properties)
        STOP(RESULT_FAIL, "advertised extension has no vkGetMemoryFdPropertiesKHR");

    /* Opening an existing exporter does not create a device node or load a module. */
    ctx.udmabuf = open("/dev/udmabuf", O_RDWR | O_CLOEXEC);
    if (ctx.udmabuf < 0) {
        const int err = errno;
        STOP(syscall_failure_class(err), "/dev/udmabuf open: errno=%d (%s); root "
             "cannot supply an exporter absent from the running kernel",
             err, strerror(err));
    }
    ctx.memfd = (int)syscall(SYS_memfd_create, "powervr-dmabuf-probe",
                             MFD_CLOEXEC | MFD_ALLOW_SEALING);
    CHECK_SYS(ctx.memfd);
    CHECK_SYS(ftruncate(ctx.memfd, (off_t)ctx.backing_size));
    CHECK_SYS(fcntl(ctx.memfd, F_ADD_SEALS, F_SEAL_SHRINK));
    const int seals = fcntl(ctx.memfd, F_GET_SEALS);
    CHECK_SYS(seals);
    printf("memfd seals=0x%x (SHRINK required; WRITE/FUTURE_WRITE not set)\n", seals);
    ctx.guest_map = mmap(NULL, ctx.backing_size, PROT_READ | PROT_WRITE,
                         MAP_SHARED, ctx.memfd, 0);
    if (ctx.guest_map == MAP_FAILED) {
        const int err = errno;
        STOP(syscall_failure_class(err), "memfd mmap: errno=%d (%s)",
             err, strerror(err));
    }
    volatile uint32_t *guest = ctx.guest_map;
    const size_t words_per_page = ctx.page_size / sizeof(*guest);
    for (unsigned page = 0; page < BACKING_PAGES; ++page)
        for (size_t word = 0; word < words_per_page; ++word)
            guest[page * words_per_page + word] = guard_word(page, word);
    list = calloc(1, sizeof(*list) + EXPORTED_PAGES * sizeof(list->list[0]));
    if (!list) STOP(RESULT_FAIL, "host allocation failed");
    list->flags = UDMABUF_FLAGS_CLOEXEC;
    list->count = EXPORTED_PAGES;
    for (unsigned i = 0; i < EXPORTED_PAGES; ++i) {
        list->list[i].memfd = (uint32_t)ctx.memfd;
        list->list[i].offset = (uint64_t)page_order[i] * ctx.page_size;
        list->list[i].size = ctx.page_size;
    }
    ctx.dmafd = ioctl(ctx.udmabuf, UDMABUF_CREATE_LIST, list);
    CHECK_SYS(ctx.dmafd);
    printf("UDMABUF_CREATE_LIST=success chunks=%u discontiguous=yes reordered=yes\n",
           EXPORTED_PAGES);

    const VkExternalMemoryBufferCreateInfo external_buffer_info = {
        .sType = VK_STRUCTURE_TYPE_EXTERNAL_MEMORY_BUFFER_CREATE_INFO,
        .handleTypes = handle_type,
    };
    const VkBufferCreateInfo imported_buffer_info = {
        .sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
        .pNext = &external_buffer_info,
        .size = ctx.exported_size,
        .usage = buffer_usage,
        .sharingMode = VK_SHARING_MODE_EXCLUSIVE,
    };
    CHECK_VK(vkCreateBuffer(ctx.device, &imported_buffer_info, NULL,
                            &ctx.imported_buffer));
    VkMemoryDedicatedRequirements dedicated_requirements = {
        .sType = VK_STRUCTURE_TYPE_MEMORY_DEDICATED_REQUIREMENTS,
    };
    VkMemoryRequirements2 imported_requirements = {
        .sType = VK_STRUCTURE_TYPE_MEMORY_REQUIREMENTS_2,
        .pNext = &dedicated_requirements,
    };
    const VkBufferMemoryRequirementsInfo2 requirements_info = {
        .sType = VK_STRUCTURE_TYPE_BUFFER_MEMORY_REQUIREMENTS_INFO_2,
        .buffer = ctx.imported_buffer,
    };
    vkGetBufferMemoryRequirements2(ctx.device, &requirements_info,
                                    &imported_requirements);
    const VkMemoryRequirements req = imported_requirements.memoryRequirements;
    printf("import_buffer requirements_size=%" PRIu64 " alignment=%" PRIu64
           " type_bits=0x%x dedicated_required=%u dedicated_preferred=%u\n",
           (uint64_t)req.size, (uint64_t)req.alignment, req.memoryTypeBits,
           dedicated_requirements.requiresDedicatedAllocation,
           dedicated_requirements.prefersDedicatedAllocation);
    if (req.size != ctx.exported_size)
        STOP(RESULT_UNSUPPORTED, "buffer allocation size %" PRIu64 " differs from "
             "the probe's %zu-byte DMA-BUF; no oversized external import attempted",
             (uint64_t)req.size, ctx.exported_size);
    VkMemoryFdPropertiesKHR fd_properties = {
        .sType = VK_STRUCTURE_TYPE_MEMORY_FD_PROPERTIES_KHR,
    };
    vr = get_fd_properties(ctx.device, handle_type, ctx.dmafd, &fd_properties);
    if (vr != VK_SUCCESS)
        STOP(vr == VK_ERROR_INVALID_EXTERNAL_HANDLE ? RESULT_UNSUPPORTED : RESULT_FAIL,
             "vkGetMemoryFdPropertiesKHR on real UDMABUF FD: %s (%d)",
             vk_result_name(vr), vr);
    const uint32_t compatible_bits = fd_properties.memoryTypeBits & req.memoryTypeBits;
    const VkMemoryPropertyFlags runtime_required_flags =
        VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT;
    /* The candidate runtime importer requires this class. Prefer it so the
     * small probe tests a relevant type; retain a transfer-only fallback to
     * distinguish driver interoperability from that stricter requirement. */
    const uint32_t runtime_type = memory_type(&ctx, compatible_bits,
        runtime_required_flags, VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);
    const bool runtime_class_available = runtime_type != UINT32_MAX;
    const uint32_t import_type = runtime_class_available ? runtime_type :
        memory_type(&ctx, compatible_bits, 0, VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);
    printf("fd_memory_type_bits=0x%x buffer_intersection=0x%x\n",
           fd_properties.memoryTypeBits, compatible_bits);
    printf("RUNTIME_MEMORY_CLASS_REQUIRED=HOST_VISIBLE|HOST_COHERENT flags=0x%x\n",
           runtime_required_flags);
    printf("RUNTIME_MEMORY_CLASS_AVAILABLE=%s\n", runtime_class_available ? "yes" : "no");
    if (import_type == UINT32_MAX)
        STOP(RESULT_UNSUPPORTED, "UDMABUF handle and storage/transfer buffer have "
             "no compatible Vulkan memory type");
    const VkMemoryPropertyFlags import_flags =
        ctx.memory_properties.memoryTypes[import_type].propertyFlags;
    const bool runtime_class_chosen =
        (import_flags & runtime_required_flags) == runtime_required_flags;
    printf("import_memory_type=%u flags=0x%x\n", import_type, import_flags);
    printf("RUNTIME_MEMORY_CLASS_CHOSEN=%s\n", runtime_class_chosen ? "yes" : "no");
    if (!runtime_class_chosen)
        printf("RUNTIME_MEMORY_CLASS_REQUIREMENT=UNSATISFIED: continuing only the "
               "transfer probe; a PASS cannot satisfy the candidate runtime "
               "importer's HOST_VISIBLE|HOST_COHERENT requirement.\n");
    /* Vulkan owns this duplicate only after successful vkAllocateMemory. Keep the
     * original dmafd for CPU cache handoffs and close it during cleanup. */
    ctx.import_fd = fcntl(ctx.dmafd, F_DUPFD_CLOEXEC, 0);
    CHECK_SYS(ctx.import_fd);
    const VkMemoryDedicatedAllocateInfo dedicated_info = {
        .sType = VK_STRUCTURE_TYPE_MEMORY_DEDICATED_ALLOCATE_INFO,
        .buffer = ctx.imported_buffer,
    };
    const VkImportMemoryFdInfoKHR import_info = {
        .sType = VK_STRUCTURE_TYPE_IMPORT_MEMORY_FD_INFO_KHR,
        .pNext = &dedicated_info,
        .handleType = handle_type,
        .fd = ctx.import_fd,
    };
    const VkMemoryAllocateInfo import_allocation = {
        .sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
        .pNext = &import_info,
        .allocationSize = ctx.exported_size,
        .memoryTypeIndex = import_type,
    };
    vr = vkAllocateMemory(ctx.device, &import_allocation, NULL, &ctx.imported_memory);
    if (vr != VK_SUCCESS)
        STOP(vr == VK_ERROR_INVALID_EXTERNAL_HANDLE ? RESULT_UNSUPPORTED : RESULT_FAIL,
             "vkAllocateMemory importing UDMABUF: %s (%d)", vk_result_name(vr), vr);
    ctx.import_fd = -1;
    CHECK_VK(vkBindBufferMemory(ctx.device, ctx.imported_buffer,
                                 ctx.imported_memory, 0));
    printf("DMA-BUF Vulkan import and bind=success; guest CPU view is original "
           "memfd mmap\n");

    const VkBufferCreateInfo readback_info = {
        .sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
        .size = ctx.exported_size,
        .usage = VK_BUFFER_USAGE_TRANSFER_DST_BIT,
        .sharingMode = VK_SHARING_MODE_EXCLUSIVE,
    };
    CHECK_VK(vkCreateBuffer(ctx.device, &readback_info, NULL, &ctx.readback_buffer));
    VkMemoryRequirements readback_requirements;
    vkGetBufferMemoryRequirements(ctx.device, ctx.readback_buffer,
                                   &readback_requirements);
    const uint32_t readback_type = memory_type(&ctx,
        readback_requirements.memoryTypeBits, VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT,
        VK_MEMORY_PROPERTY_HOST_COHERENT_BIT);
    if (readback_type == UINT32_MAX)
        STOP(RESULT_UNSUPPORTED, "no host-visible Vulkan readback memory");
    ctx.readback_coherent = (ctx.memory_properties.memoryTypes[readback_type].propertyFlags &
                             VK_MEMORY_PROPERTY_HOST_COHERENT_BIT) != 0;
    ctx.readback_allocation_size = readback_requirements.size;
    const VkMemoryAllocateInfo readback_allocation = {
        .sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
        .allocationSize = ctx.readback_allocation_size,
        .memoryTypeIndex = readback_type,
    };
    CHECK_VK(vkAllocateMemory(ctx.device, &readback_allocation, NULL,
                               &ctx.readback_memory));
    CHECK_VK(vkBindBufferMemory(ctx.device, ctx.readback_buffer,
                                 ctx.readback_memory, 0));
    CHECK_VK(vkMapMemory(ctx.device, ctx.readback_memory, 0, VK_WHOLE_SIZE, 0,
                          &ctx.readback_map));
    printf("readback_memory_type=%u flags=0x%x coherent=%s\n", readback_type,
           ctx.memory_properties.memoryTypes[readback_type].propertyFlags,
           ctx.readback_coherent ? "yes" : "no");

    const VkCommandPoolCreateInfo pool_info = {
        .sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,
        .flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT,
        .queueFamilyIndex = ctx.family,
    };
    CHECK_VK(vkCreateCommandPool(ctx.device, &pool_info, NULL, &ctx.pool));
    const VkCommandBufferAllocateInfo command_info = {
        .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,
        .commandPool = ctx.pool,
        .level = VK_COMMAND_BUFFER_LEVEL_PRIMARY,
        .commandBufferCount = 1,
    };
    CHECK_VK(vkAllocateCommandBuffers(ctx.device, &command_info, &ctx.command));
    const VkFenceCreateInfo fence_info = {.sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};
    CHECK_VK(vkCreateFence(ctx.device, &fence_info, NULL, &ctx.fence));
    const VkCommandBufferBeginInfo begin_info = {
        .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO,
        .flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT,
    };

    CHECK_SYS(dma_sync(ctx.dmafd, DMA_BUF_SYNC_START | DMA_BUF_SYNC_WRITE));
    for (unsigned i = 0; i < EXPORTED_PAGES; ++i)
        for (size_t word = 0; word < words_per_page; ++word)
            guest[page_order[i] * words_per_page + word] = guest_word(page_order[i], word);
    CHECK_SYS(dma_sync(ctx.dmafd, DMA_BUF_SYNC_END | DMA_BUF_SYNC_WRITE));
    CHECK_VK(vkBeginCommandBuffer(ctx.command, &begin_info));
    acquire_foreign(&ctx, VK_ACCESS_TRANSFER_READ_BIT);
    const VkBufferCopy copy = {.size = ctx.exported_size};
    vkCmdCopyBuffer(ctx.command, ctx.imported_buffer, ctx.readback_buffer, 1, &copy);
    const VkBufferMemoryBarrier host_read_barrier = {
        .sType = VK_STRUCTURE_TYPE_BUFFER_MEMORY_BARRIER,
        .srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT,
        .dstAccessMask = VK_ACCESS_HOST_READ_BIT,
        .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
        .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
        .buffer = ctx.readback_buffer,
        .size = VK_WHOLE_SIZE,
    };
    vkCmdPipelineBarrier(ctx.command, VK_PIPELINE_STAGE_TRANSFER_BIT,
                         VK_PIPELINE_STAGE_HOST_BIT, 0, 0, NULL, 1,
                         &host_read_barrier, 0, NULL);
    release_foreign(&ctx, VK_ACCESS_TRANSFER_READ_BIT);
    CHECK_VK(submit_and_wait(&ctx, "CPU_TO_GPU"));
    if (!ctx.readback_coherent) {
        const VkMappedMemoryRange range = {
            .sType = VK_STRUCTURE_TYPE_MAPPED_MEMORY_RANGE,
            .memory = ctx.readback_memory,
            .size = VK_WHOLE_SIZE,
        };
        CHECK_VK(vkInvalidateMappedMemoryRanges(ctx.device, 1, &range));
    }
    const volatile uint32_t *readback = ctx.readback_map;
    size_t mismatch_count = 0;
    for (unsigned i = 0; i < EXPORTED_PAGES; ++i) {
        for (size_t word = 0; word < words_per_page; ++word) {
            const uint32_t expected = guest_word(page_order[i], word);
            const uint32_t actual = readback[i * words_per_page + word];
            if (actual != expected) {
                if (mismatch_count < 4)
                    printf("CPU_TO_GPU mismatch logical_page=%u original_page=%u "
                           "word=%zu expected=0x%08x actual=0x%08x\n", i,
                           page_order[i], word, expected, actual);
                ++mismatch_count;
            }
        }
    }
    if (mismatch_count)
        STOP(RESULT_FAIL, "CPU_TO_GPU mismatched %zu/%zu words", mismatch_count,
             ctx.exported_size / sizeof(uint32_t));
    printf("CPU_TO_GPU=PASS checked_words=%zu\n", ctx.exported_size / sizeof(uint32_t));

    CHECK_VK(vkResetCommandBuffer(ctx.command, 0));
    CHECK_VK(vkBeginCommandBuffer(ctx.command, &begin_info));
    acquire_foreign(&ctx, VK_ACCESS_TRANSFER_WRITE_BIT);
    for (unsigned i = 0; i < EXPORTED_PAGES; ++i)
        vkCmdFillBuffer(ctx.command, ctx.imported_buffer, (VkDeviceSize)i * ctx.page_size,
                        ctx.page_size, gpu_word(i));
    release_foreign(&ctx, VK_ACCESS_TRANSFER_WRITE_BIT);
    CHECK_VK(submit_and_wait(&ctx, "GPU_TO_CPU"));
    CHECK_SYS(dma_sync(ctx.dmafd, DMA_BUF_SYNC_START | DMA_BUF_SYNC_READ));
    mismatch_count = 0;
    size_t guard_mismatch_count = 0;
    for (unsigned page = 0; page < BACKING_PAGES; ++page) {
        int selected = -1;
        for (unsigned i = 0; i < EXPORTED_PAGES; ++i)
            if (page_order[i] == page) selected = (int)i;
        for (size_t word = 0; word < words_per_page; ++word) {
            const uint32_t expected = selected >= 0 ? gpu_word((unsigned)selected) :
                                                       guard_word(page, word);
            const uint32_t actual = guest[page * words_per_page + word];
            if (actual != expected) {
                if (mismatch_count + guard_mismatch_count < 4)
                    printf("GPU_TO_CPU mismatch original_page=%u selected=%d word=%zu "
                           "expected=0x%08x actual=0x%08x\n", page, selected, word,
                           expected, actual);
                if (selected >= 0) ++mismatch_count;
                else ++guard_mismatch_count;
            }
        }
    }
    CHECK_SYS(dma_sync(ctx.dmafd, DMA_BUF_SYNC_END | DMA_BUF_SYNC_READ));
    if (mismatch_count || guard_mismatch_count)
        STOP(RESULT_FAIL, "GPU_TO_CPU mismatched exported_words=%zu guard_words=%zu",
             mismatch_count, guard_mismatch_count);
    printf("GPU_TO_CPU=PASS checked_words=%zu; CPU_VISIBLE_GUARD_VALUES=PASS "
           "checked_words=%zu\n",
           ctx.exported_size / sizeof(uint32_t),
           (ctx.backing_size - ctx.exported_size) / sizeof(uint32_t));
    printf("Guard scope: unexported pages are outside DMA-BUF cache maintenance; "
           "this CPU-view check cannot exclude device out-of-bounds writes "
           "on a noncoherent system.\n");
    result = result_message(RESULT_PASS, "sealed memfd -> discontiguous UDMABUF -> "
        "Vulkan storage/transfer-capable buffer: CPU-to-GPU copy and GPU-to-CPU "
        "fill round trips passed with FOREIGN ownership and DMA_BUF_IOCTL_SYNC. "
        "Candidate runtime HOST_VISIBLE|HOST_COHERENT memory-class requirement=%s. "
        "Shader/device-address/sparse/image/large-RAM paths remain untested; "
        "this is not a full runtime compatibility result.",
        runtime_class_chosen ? "SATISFIED" : "UNSATISFIED");

done:
    free(list);
    free(families);
    free(extensions);
    free(devices);
    cleanup(&ctx);
    return result;
}
