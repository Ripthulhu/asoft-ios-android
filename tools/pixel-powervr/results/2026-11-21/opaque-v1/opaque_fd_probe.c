/* SPDX-License-Identifier: MIT
 * Bounded producer-owned Vulkan OPAQUE_FD experiment, not a guest-RAM importer.
 * One device and queue; only the imported buffer is accessed by GPU commands.
 * Producer/imported buffers alias. Readback is a THIRD independent allocation.
 * Optional POSIX mmap of an opaque FD is driver-specific, not a Vulkan promise.
 * No sparse resources, DMA-BUF ioctls, driver-private calls, or device changes.
 * Exit: 0 all requested tests pass; 1 failure; 2 Vulkan capability unavailable;
 *       3 Vulkan round trip passed but native FD mmap is unavailable.
 */
#define _GNU_SOURCE
#include <vulkan/vulkan.h>

#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <signal.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

enum { PAGES = 8 };
#define WAIT_NS UINT64_C(5000000000)
#define MAX_ALLOCATION UINT64_C(16777216)
#define HOST_CLASS (VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)
#define RUNTIME_USAGE (VK_BUFFER_USAGE_TRANSFER_SRC_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT | \
    VK_BUFFER_USAGE_UNIFORM_TEXEL_BUFFER_BIT | VK_BUFFER_USAGE_STORAGE_TEXEL_BUFFER_BIT | \
    VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT | VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | \
    VK_BUFFER_USAGE_INDEX_BUFFER_BIT | VK_BUFFER_USAGE_VERTEX_BUFFER_BIT | VK_BUFFER_USAGE_INDIRECT_BUFFER_BIT)

typedef struct Probe {
    VkInstance instance;
    VkPhysicalDevice physical;
    VkDevice device;
    VkQueue queue;
    uint32_t family;
    VkPhysicalDeviceMemoryProperties memory;
    VkBool32 bda;
    VkBufferUsageFlags usage;
    size_t page, bytes, allocation_bytes;
    VkBuffer producer, imported, readback;
    VkDeviceMemory producer_memory, imported_memory, readback_memory;
    void *producer_map, *imported_map, *readback_map;
    void *fd_map;
    int export_fd, import_fd;
    VkCommandPool pool;
    VkCommandBuffer command;
    VkFence fence;
} Probe;

#define TRY(call) do { \
    VkResult vr_ = (call); \
    if (vr_ != VK_SUCCESS) { \
        fprintf(stderr, "FAIL: %s VkResult=%d\n", #call, vr_); \
        return 1; \
    } \
} while (0)

static int unavailable(const char *message)
{
    printf("UNSUPPORTED: %s\n", message);
    return 2;
}

static int extension_present(const VkExtensionProperties *items, uint32_t count, const char *name)
{
    for (uint32_t i = 0; i < count; ++i)
        if (!strcmp(items[i].extensionName, name)) return 1;
    return 0;
}

static int host_type(const Probe *p, uint32_t bits)
{
    int fallback = -1;
    for (uint32_t i = 0; i < p->memory.memoryTypeCount; ++i) {
        VkMemoryPropertyFlags flags = p->memory.memoryTypes[i].propertyFlags;
        if (!(bits & (1u << i)) || (flags & HOST_CLASS) != HOST_CLASS) continue;
        if (flags & VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT) return (int)i;
        if (fallback < 0) fallback = (int)i;
    }
    return fallback;
}

static int initialize(Probe *p)
{
    long page = sysconf(_SC_PAGESIZE);
    if (page <= 0 || page > 65536 || (page & (page - 1)))
        return unavailable("host page size outside small-probe limits");
    p->page = (size_t)page;
    p->bytes = PAGES * p->page;
    printf("host_page=%zu buffer_bytes=%zu pages=%u\n", p->page, p->bytes, PAGES);
    uint32_t loader = VK_API_VERSION_1_0;
    PFN_vkEnumerateInstanceVersion version = (PFN_vkEnumerateInstanceVersion)vkGetInstanceProcAddr(VK_NULL_HANDLE, "vkEnumerateInstanceVersion");
    if (version) TRY(version(&loader));
    printf("loader_api=%u.%u.%u requested_api=1.3\n", VK_API_VERSION_MAJOR(loader), VK_API_VERSION_MINOR(loader), VK_API_VERSION_PATCH(loader));
    if (loader < VK_API_VERSION_1_3) return unavailable("loader lacks Vulkan 1.3");
    const VkApplicationInfo app = {.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO, .pApplicationName = "pixel-producer-opaque-fd", .apiVersion = VK_API_VERSION_1_3};
    const VkInstanceCreateInfo instance = {.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO, .pApplicationInfo = &app};
    TRY(vkCreateInstance(&instance, NULL, &p->instance));
    uint32_t count = 0;
    TRY(vkEnumeratePhysicalDevices(p->instance, &count, NULL));
    if (!count || count > 256) return unavailable("physical device count outside probe limits");
    VkPhysicalDevice *devices = calloc(count, sizeof(*devices));
    if (!devices) return 1;
    VkResult result = vkEnumeratePhysicalDevices(p->instance, &count, devices);
    if (result == VK_SUCCESS && count) p->physical = devices[0];
    free(devices);
    if (result != VK_SUCCESS || !count) { printf("FAIL: physical device enumeration=%d\n", result); return 1; }
    VkPhysicalDeviceProperties properties;
    vkGetPhysicalDeviceProperties(p->physical, &properties);
    printf("device=%s vendor=0x%x device_id=0x%x driver=0x%x device_api=%u.%u.%u\n",
           properties.deviceName, properties.vendorID, properties.deviceID, properties.driverVersion,
           VK_API_VERSION_MAJOR(properties.apiVersion), VK_API_VERSION_MINOR(properties.apiVersion), VK_API_VERSION_PATCH(properties.apiVersion));
    if (properties.apiVersion < VK_API_VERSION_1_3) return unavailable("physical device lacks Vulkan 1.3");
    TRY(vkEnumerateDeviceExtensionProperties(p->physical, NULL, &count, NULL));
    if (count > 4096) return 1;
    VkExtensionProperties *extensions = calloc(count ? count : 1, sizeof(*extensions));
    if (!extensions) return 1;
    result = vkEnumerateDeviceExtensionProperties(p->physical, NULL, &count, extensions);
    int fd = result == VK_SUCCESS && extension_present(extensions, count, VK_KHR_EXTERNAL_MEMORY_FD_EXTENSION_NAME);
    free(extensions);
    if (result != VK_SUCCESS) { printf("FAIL: extension enumeration=%d\n", result); return 1; }
    if (!fd) return unavailable("VK_KHR_external_memory_fd absent");
    VkPhysicalDeviceVulkan12Features f12 = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_2_FEATURES};
    VkPhysicalDeviceFeatures2 f2 = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2, .pNext = &f12};
    vkGetPhysicalDeviceFeatures2(p->physical, &f2);
    p->bda = f12.bufferDeviceAddress;
    p->usage = RUNTIME_USAGE | (p->bda ? VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT : 0);
    printf("bufferDeviceAddress=%u enabled=%u usage=0x%x create_flags=0 sparse_resources=no\n", p->bda, p->bda, p->usage);
    const VkPhysicalDeviceExternalBufferInfo query = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_EXTERNAL_BUFFER_INFO,
        .usage = p->usage, .handleType = VK_EXTERNAL_MEMORY_HANDLE_TYPE_OPAQUE_FD_BIT,
    };
    VkExternalBufferProperties external = {.sType = VK_STRUCTURE_TYPE_EXTERNAL_BUFFER_PROPERTIES};
    vkGetPhysicalDeviceExternalBufferProperties(p->physical, &query, &external);
    VkExternalMemoryProperties ep = external.externalMemoryProperties;
    printf("external_handle=OPAQUE_FD features=0x%x compatible=0x%x export_from_imported=0x%x\n",
           ep.externalMemoryFeatures, ep.compatibleHandleTypes, ep.exportFromImportedHandleTypes);
    const VkExternalMemoryFeatureFlags required = VK_EXTERNAL_MEMORY_FEATURE_IMPORTABLE_BIT | VK_EXTERNAL_MEMORY_FEATURE_EXPORTABLE_BIT;
    if ((ep.externalMemoryFeatures & required) != required)
        return unavailable("OPAQUE_FD import and export unavailable for exact buffer usage");
    if (ep.externalMemoryFeatures & VK_EXTERNAL_MEMORY_FEATURE_DEDICATED_ONLY_BIT)
        return unavailable("probe targets non-dedicated producer pools; handle requires dedicated allocation");
    vkGetPhysicalDeviceMemoryProperties(p->physical, &p->memory);
    vkGetPhysicalDeviceQueueFamilyProperties(p->physical, &count, NULL);
    if (count > 4096) return 1;
    VkQueueFamilyProperties *families = calloc(count ? count : 1, sizeof(*families));
    if (!families) return 1;
    vkGetPhysicalDeviceQueueFamilyProperties(p->physical, &count, families);
    p->family = UINT32_MAX;
    for (uint32_t i = 0; i < count; ++i)
        if (families[i].queueCount && (families[i].queueFlags & (VK_QUEUE_GRAPHICS_BIT | VK_QUEUE_COMPUTE_BIT | VK_QUEUE_TRANSFER_BIT))) {
            p->family = i;
            printf("queue_family=%u flags=0x%x\n", i, families[i].queueFlags);
            break;
        }
    free(families);
    if (p->family == UINT32_MAX) return unavailable("no transfer-capable queue");
    const float priority = 1.0f;
    const VkDeviceQueueCreateInfo queue = {.sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO, .queueFamilyIndex = p->family, .queueCount = 1, .pQueuePriorities = &priority};
    VkPhysicalDeviceVulkan12Features enable = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_2_FEATURES, .bufferDeviceAddress = p->bda};
    const char *name = VK_KHR_EXTERNAL_MEMORY_FD_EXTENSION_NAME;
    const VkDeviceCreateInfo device = {
        .sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO, .pNext = &enable,
        .queueCreateInfoCount = 1, .pQueueCreateInfos = &queue,
        .enabledExtensionCount = 1, .ppEnabledExtensionNames = &name,
    };
    TRY(vkCreateDevice(p->physical, &device, NULL, &p->device));
    vkGetDeviceQueue(p->device, p->family, 0, &p->queue);
    return 0;
}

static void requirements(Probe *p, VkBuffer buffer, const char *label, VkMemoryRequirements *out, VkBool32 *dedicated)
{
    const VkBufferMemoryRequirementsInfo2 info = {.sType = VK_STRUCTURE_TYPE_BUFFER_MEMORY_REQUIREMENTS_INFO_2, .buffer = buffer};
    VkMemoryDedicatedRequirements d = {.sType = VK_STRUCTURE_TYPE_MEMORY_DEDICATED_REQUIREMENTS};
    VkMemoryRequirements2 r = {.sType = VK_STRUCTURE_TYPE_MEMORY_REQUIREMENTS_2, .pNext = &d};
    vkGetBufferMemoryRequirements2(p->device, &info, &r);
    *out = r.memoryRequirements;
    *dedicated = d.requiresDedicatedAllocation;
    printf("%s_requirements size=%" PRIu64 " alignment=%" PRIu64 " type_bits=0x%x dedicated_required=%u dedicated_preferred=%u\n",
           label, out->size, out->alignment, out->memoryTypeBits, d.requiresDedicatedAllocation, d.prefersDedicatedAllocation);
}

static int resources(Probe *p)
{
    const VkExternalMemoryBufferCreateInfo ext = {.sType = VK_STRUCTURE_TYPE_EXTERNAL_MEMORY_BUFFER_CREATE_INFO, .handleTypes = VK_EXTERNAL_MEMORY_HANDLE_TYPE_OPAQUE_FD_BIT};
    const VkBufferCreateInfo create = {
        .sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO, .pNext = &ext, .size = p->bytes,
        .usage = p->usage, .sharingMode = VK_SHARING_MODE_EXCLUSIVE,
    };
    TRY(vkCreateBuffer(p->device, &create, NULL, &p->producer));
    TRY(vkCreateBuffer(p->device, &create, NULL, &p->imported));
    VkMemoryRequirements a, b;
    VkBool32 dedicated_a, dedicated_b;
    requirements(p, p->producer, "producer", &a, &dedicated_a);
    requirements(p, p->imported, "imported", &b, &dedicated_b);
    if (dedicated_a || dedicated_b) return unavailable("probe requires ordinary non-dedicated aliasable allocation");
    VkDeviceSize allocation = a.size > b.size ? a.size : b.size;
    if (allocation < p->bytes || allocation > MAX_ALLOCATION || allocation > SIZE_MAX)
        return unavailable("allocation size outside bounded probe limits");
    p->allocation_bytes = (size_t)allocation;
    int type = host_type(p, a.memoryTypeBits & b.memoryTypeBits);
    if (type < 0) return unavailable("no compatible HOST_VISIBLE|HOST_COHERENT type for both actual buffers");
    printf("producer_memory_type=%d flags=0x%x allocation_size=%zu bind_offset=0\n", type, p->memory.memoryTypes[type].propertyFlags, p->allocation_bytes);
    const VkMemoryAllocateFlagsInfo address = {.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_FLAGS_INFO, .flags = VK_MEMORY_ALLOCATE_DEVICE_ADDRESS_BIT};
    const VkExportMemoryAllocateInfo export_info = {
        .sType = VK_STRUCTURE_TYPE_EXPORT_MEMORY_ALLOCATE_INFO, .pNext = p->bda ? &address : NULL,
        .handleTypes = VK_EXTERNAL_MEMORY_HANDLE_TYPE_OPAQUE_FD_BIT,
    };
    VkMemoryAllocateInfo allocate = {
        .sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO, .pNext = &export_info,
        .allocationSize = allocation, .memoryTypeIndex = (uint32_t)type,
    };
    TRY(vkAllocateMemory(p->device, &allocate, NULL, &p->producer_memory));
    TRY(vkBindBufferMemory(p->device, p->producer, p->producer_memory, 0));
    TRY(vkMapMemory(p->device, p->producer_memory, 0, VK_WHOLE_SIZE, 0, &p->producer_map));
    PFN_vkGetMemoryFdKHR get_fd = (PFN_vkGetMemoryFdKHR)vkGetDeviceProcAddr(p->device, "vkGetMemoryFdKHR");
    if (!get_fd) { puts("FAIL: enabled external-memory-fd extension has no export function"); return 1; }
    const VkMemoryGetFdInfoKHR fd_info = {.sType = VK_STRUCTURE_TYPE_MEMORY_GET_FD_INFO_KHR, .memory = p->producer_memory, .handleType = VK_EXTERNAL_MEMORY_HANDLE_TYPE_OPAQUE_FD_BIT};
    TRY(get_fd(p->device, &fd_info, &p->export_fd));
    p->import_fd = fcntl(p->export_fd, F_DUPFD_CLOEXEC, 0);
    if (p->import_fd < 0) { printf("FAIL: duplicate export FD errno=%d\n", errno); return 1; }
    const VkImportMemoryFdInfoKHR import_info = {
        .sType = VK_STRUCTURE_TYPE_IMPORT_MEMORY_FD_INFO_KHR, .pNext = p->bda ? &address : NULL,
        .handleType = VK_EXTERNAL_MEMORY_HANDLE_TYPE_OPAQUE_FD_BIT, .fd = p->import_fd,
    };
    allocate.pNext = &import_info;
    /* OPAQUE_FD requires the ORIGINAL Vulkan allocation size and memory type.
     * vkGetMemoryFdPropertiesKHR must NOT be queried for OPAQUE_FD. */
    TRY(vkAllocateMemory(p->device, &allocate, NULL, &p->imported_memory));
    p->import_fd = -1; /* Vulkan consumed the duplicate only after successful import. */
    TRY(vkBindBufferMemory(p->device, p->imported, p->imported_memory, 0));
    TRY(vkMapMemory(p->device, p->imported_memory, 0, VK_WHOLE_SIZE, 0, &p->imported_map));
    puts("OPAQUE_EXPORT_IMPORT=PASS same_physical_device=yes same_allocation_size=yes same_memory_type=yes import_duplicate_consumed=yes original_export_fd_retained=yes");
    printf("cpu_maps page_aligned_producer=%u page_aligned_imported=%u separate_virtual_addresses=%u\n",
           (unsigned)((uintptr_t)p->producer_map % p->page == 0), (unsigned)((uintptr_t)p->imported_map % p->page == 0), (unsigned)(p->producer_map != p->imported_map));
    if (p->bda) {
        VkBufferDeviceAddressInfo info = {.sType = VK_STRUCTURE_TYPE_BUFFER_DEVICE_ADDRESS_INFO, .buffer = p->producer};
        VkDeviceAddress producer_address = vkGetBufferDeviceAddress(p->device, &info);
        info.buffer = p->imported;
        VkDeviceAddress imported_address = vkGetBufferDeviceAddress(p->device, &info);
        printf("device_addresses producer=0x%" PRIx64 " imported=0x%" PRIx64 " equality_required=no shader_dereference_tested=no\n", producer_address, imported_address);
        if (!producer_address || !imported_address) { puts("FAIL: buffer device address is zero"); return 1; }
    }
    const VkBufferCreateInfo readback = {.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO, .size = p->bytes, .usage = VK_BUFFER_USAGE_TRANSFER_DST_BIT, .sharingMode = VK_SHARING_MODE_EXCLUSIVE};
    TRY(vkCreateBuffer(p->device, &readback, NULL, &p->readback));
    VkMemoryRequirements rr;
    VkBool32 rd;
    requirements(p, p->readback, "independent_readback", &rr, &rd);
    if (rr.size < p->bytes || rr.size > MAX_ALLOCATION) return unavailable("readback allocation outside probe limits");
    type = host_type(p, rr.memoryTypeBits);
    if (type < 0) return unavailable("no coherent host-visible readback memory");
    const VkMemoryDedicatedAllocateInfo rd_info = {.sType = VK_STRUCTURE_TYPE_MEMORY_DEDICATED_ALLOCATE_INFO, .buffer = p->readback};
    allocate = (VkMemoryAllocateInfo){.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO, .pNext = rd ? &rd_info : NULL, .allocationSize = rr.size, .memoryTypeIndex = (uint32_t)type};
    TRY(vkAllocateMemory(p->device, &allocate, NULL, &p->readback_memory));
    TRY(vkBindBufferMemory(p->device, p->readback, p->readback_memory, 0));
    TRY(vkMapMemory(p->device, p->readback_memory, 0, VK_WHOLE_SIZE, 0, &p->readback_map));
    printf("independent_readback_memory type=%d flags=0x%x bytes=%" PRIu64 "\n", type, p->memory.memoryTypes[type].propertyFlags, rr.size);
    const VkCommandPoolCreateInfo pool = {.sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO, .flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT, .queueFamilyIndex = p->family};
    TRY(vkCreateCommandPool(p->device, &pool, NULL, &p->pool));
    const VkCommandBufferAllocateInfo command = {.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO, .commandPool = p->pool, .level = VK_COMMAND_BUFFER_LEVEL_PRIMARY, .commandBufferCount = 1};
    TRY(vkAllocateCommandBuffers(p->device, &command, &p->command));
    const VkFenceCreateInfo fence = {.sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};
    TRY(vkCreateFence(p->device, &fence, NULL, &p->fence));
    return 0;
}

static int begin(Probe *p)
{
    TRY(vkResetFences(p->device, 1, &p->fence));
    TRY(vkResetCommandBuffer(p->command, 0));
    const VkCommandBufferBeginInfo info = {.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO, .flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT};
    TRY(vkBeginCommandBuffer(p->command, &info));
    return 0;
}

static void memory_barrier(Probe *p, VkPipelineStageFlags source_stage, VkAccessFlags source_access,
                           VkPipelineStageFlags destination_stage, VkAccessFlags destination_access)
{
    /* A global dependency covers accesses through both VkDeviceMemory aliases.
     * There are no external queues: both objects and all GPU uses are in this
     * same VkDevice. CPU mappings are not queues; do not invent an EXTERNAL or
     * FOREIGN ownership transfer for them. Only imported is accessed by GPU. */
    const VkMemoryBarrier barrier = {.sType = VK_STRUCTURE_TYPE_MEMORY_BARRIER, .srcAccessMask = source_access, .dstAccessMask = destination_access};
    vkCmdPipelineBarrier(p->command, source_stage, destination_stage, 0, 1, &barrier, 0, NULL, 0, NULL);
}

static int submit(Probe *p, const char *phase)
{
    TRY(vkEndCommandBuffer(p->command));
    const VkSubmitInfo info = {.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO, .commandBufferCount = 1, .pCommandBuffers = &p->command};
    VkResult result = vkQueueSubmit(p->queue, 1, &info, p->fence);
    if (result == VK_SUCCESS) result = vkWaitForFences(p->device, 1, &p->fence, VK_TRUE, WAIT_NS);
    if (result != VK_SUCCESS) {
        fprintf(stderr, "FAIL: %s submission/fence VkResult=%d; process exits without freeing possibly in-flight resources\n", phase, result);
        fflush(NULL);
        _Exit(1);
    }
    printf("%s fence=PASS wait_limit_ms=5000\n", phase);
    return 0;
}

static uint32_t pattern(size_t i, uint32_t seed)
{
    return seed ^ ((uint32_t)i * UINT32_C(0x9e3779b9));
}

static void write_pattern(void *mapping, size_t bytes, uint32_t seed)
{
    volatile uint32_t *words = mapping;
    for (size_t i = 0; i < bytes / sizeof(*words); ++i) words[i] = pattern(i, seed);
    atomic_thread_fence(memory_order_seq_cst);
}

static int check_pattern(const void *mapping, size_t bytes, uint32_t seed, const char *label)
{
    const volatile uint32_t *words = mapping;
    for (size_t i = 0; i < bytes / sizeof(*words); ++i) {
        uint32_t got = words[i], expected = pattern(i, seed);
        if (got != expected) {
            printf("FAIL: %s word=%zu got=0x%08x expected=0x%08x\n", label, i, got, expected);
            return 1;
        }
    }
    printf("%s=PASS checked_words=%zu\n", label, bytes / sizeof(*words));
    return 0;
}

static int check_fill(const Probe *p, const void *mapping, uint32_t base, const char *label)
{
    const volatile uint32_t *words = mapping;
    size_t per_page = p->page / sizeof(*words);
    for (size_t i = 0; i < p->bytes / sizeof(*words); ++i) {
        uint32_t got = words[i], expected = base + (uint32_t)(i / per_page);
        if (got != expected) {
            printf("FAIL: %s word=%zu page=%zu got=0x%08x expected=0x%08x\n", label, i, i / per_page, got, expected);
            return 1;
        }
    }
    printf("%s=PASS checked_words=%zu distinct_page_values=%u\n", label, p->bytes / sizeof(*words), PAGES);
    return 0;
}

static int gpu_copy(Probe *p, uint32_t seed, const char *phase)
{
    if (begin(p)) return 1;
    memory_barrier(p, VK_PIPELINE_STAGE_HOST_BIT, VK_ACCESS_HOST_WRITE_BIT | VK_ACCESS_HOST_READ_BIT,
                   VK_PIPELINE_STAGE_TRANSFER_BIT, VK_ACCESS_TRANSFER_READ_BIT | VK_ACCESS_TRANSFER_WRITE_BIT);
    const VkBufferCopy copy = {.size = p->bytes};
    vkCmdCopyBuffer(p->command, p->imported, p->readback, 1, &copy);
    memory_barrier(p, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_ACCESS_TRANSFER_WRITE_BIT,
                   VK_PIPELINE_STAGE_HOST_BIT, VK_ACCESS_HOST_READ_BIT | VK_ACCESS_HOST_WRITE_BIT);
    if (submit(p, phase)) return 1;
    return check_pattern(p->readback_map, p->bytes, seed, phase);
}

static int gpu_fill(Probe *p, uint32_t base, const char *phase)
{
    if (begin(p)) return 1;
    memory_barrier(p, VK_PIPELINE_STAGE_HOST_BIT, VK_ACCESS_HOST_READ_BIT | VK_ACCESS_HOST_WRITE_BIT,
                   VK_PIPELINE_STAGE_TRANSFER_BIT, VK_ACCESS_TRANSFER_WRITE_BIT);
    for (uint32_t page = 0; page < PAGES; ++page)
        vkCmdFillBuffer(p->command, p->imported, (VkDeviceSize)page * p->page, p->page, base + page);
    memory_barrier(p, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_ACCESS_TRANSFER_WRITE_BIT,
                   VK_PIPELINE_STAGE_HOST_BIT, VK_ACCESS_HOST_READ_BIT | VK_ACCESS_HOST_WRITE_BIT);
    return submit(p, phase);
}

static int vulkan_roundtrip(Probe *p)
{
    const uint32_t seed = UINT32_C(0x6ac01735), fill = UINT32_C(0xa5310000);
    write_pattern(p->producer_map, p->bytes, seed);
    if (check_pattern(p->imported_map, p->bytes, seed, "CPU_VKMAP_ALIAS")) return 1;
    if (gpu_copy(p, seed, "CPU_VKMAP_TO_GPU_READBACK")) return 1;
    if (gpu_fill(p, fill, "GPU_FILL_TO_VKMAP")) return 1;
    if (check_fill(p, p->producer_map, fill, "GPU_TO_PRODUCER_VKMAP")) return 1;
    if (check_fill(p, p->imported_map, fill, "GPU_TO_IMPORTED_VKMAP")) return 1;
    puts("VULKAN_PRODUCER_ROUNDTRIP=PASS coherent_memory=yes explicit_flush_invalidate=no shader_BDA_access_tested=no");
    return 0;
}

static void alias_bus_fault(int signal_number)
{
    (void)signal_number;
    static const char text[] = "FD_MMAP=UNSUPPORTED: native alias access raised SIGBUS after Vulkan baseline passed; stopping\n";
    (void)write(STDERR_FILENO, text, sizeof(text) - 1);
    _Exit(3);
}

static int native_fd_roundtrip(Probe *p)
{
    puts("FD_MMAP_SCOPE=driver-specific POSIX observation; not guaranteed by Vulkan OPAQUE_FD; no DMA-BUF ioctls");
    struct stat status;
    if (!fstat(p->export_fd, &status))
        printf("export_fd_stat size=%" PRId64 " mode=0%o (not used as an import contract)\n", (int64_t)status.st_size, (unsigned)status.st_mode);
    errno = 0;
    p->fd_map = mmap(NULL, p->allocation_bytes, PROT_READ | PROT_WRITE, MAP_SHARED, p->export_fd, 0);
    if (p->fd_map == MAP_FAILED) {
        printf("FD_MMAP=UNSUPPORTED errno=%d message=%s; Vulkan baseline already passed\n", errno, strerror(errno));
        return 3;
    }
    printf("FD_MMAP=CREATED bytes=%zu offset=0 page_aligned=%u\n", p->allocation_bytes, (unsigned)((uintptr_t)p->fd_map % p->page == 0));
    struct sigaction previous, action;
    memset(&action, 0, sizeof(action));
    action.sa_handler = alias_bus_fault;
    sigemptyset(&action.sa_mask);
    if (sigaction(SIGBUS, &action, &previous)) { printf("FAIL: installing SIGBUS guard errno=%d\n", errno); return 1; }
    int result = 1;
    /* An opaque FD can map driver metadata rather than the payload at offset
     * zero. Verify ALL existing bytes before any native write, and classify a
     * mismatch as absence of this native alias contract, not Vulkan failure. */
    const volatile uint32_t *initial = p->fd_map;
    for (size_t i = 0; i < p->bytes / sizeof(*initial); ++i) {
        uint32_t got = initial[i];
        uint32_t expected = UINT32_C(0xa5310000) + (uint32_t)(i / (p->page / sizeof(*initial)));
        if (got != expected) {
            printf("FD_MMAP=UNSUPPORTED offset=0 word=%zu got=0x%08x expected=0x%08x; does not alias payload; no writes through native view\n", i, got, expected);
            result = 3;
            goto done;
        }
    }
    printf("FD_MMAP_INITIAL_CONTENTS=PASS checked_words=%zu\n", p->bytes / sizeof(*initial));
    const uint32_t seed = UINT32_C(0xc42d930f), fill = UINT32_C(0x7b620000);
    write_pattern(p->fd_map, p->bytes, seed);
    if (check_pattern(p->producer_map, p->bytes, seed, "FD_MMAP_TO_PRODUCER_VKMAP")) goto done;
    if (check_pattern(p->imported_map, p->bytes, seed, "FD_MMAP_TO_IMPORTED_VKMAP")) goto done;
    if (gpu_copy(p, seed, "FD_MMAP_TO_GPU_READBACK")) goto done;
    if (gpu_fill(p, fill, "GPU_FILL_TO_FD_MMAP")) goto done;
    if (check_fill(p, p->producer_map, fill, "FD_PHASE_GPU_TO_PRODUCER_VKMAP")) goto done;
    if (check_fill(p, p->imported_map, fill, "FD_PHASE_GPU_TO_IMPORTED_VKMAP")) goto done;
    if (check_fill(p, p->fd_map, fill, "GPU_TO_FD_MMAP")) goto done;
    puts("FD_MMAP_ROUNDTRIP=PASS offset=0 only; scattered/remapped CPU views not tested");
    result = 0;
done:
    if (sigaction(SIGBUS, &previous, NULL)) { printf("FAIL: restoring SIGBUS handler errno=%d\n", errno); result = 1; }
    return result;
}

static void cleanup(Probe *p)
{
    if (p->fd_map != MAP_FAILED) munmap(p->fd_map, p->allocation_bytes);
    if (p->device) {
        if (p->fence) vkDestroyFence(p->device, p->fence, NULL);
        if (p->pool) vkDestroyCommandPool(p->device, p->pool, NULL);
        if (p->readback_map) vkUnmapMemory(p->device, p->readback_memory);
        if (p->readback) vkDestroyBuffer(p->device, p->readback, NULL);
        if (p->readback_memory) vkFreeMemory(p->device, p->readback_memory, NULL);
        if (p->imported_map) vkUnmapMemory(p->device, p->imported_memory);
        if (p->imported) vkDestroyBuffer(p->device, p->imported, NULL);
        if (p->imported_memory) vkFreeMemory(p->device, p->imported_memory, NULL);
        if (p->producer_map) vkUnmapMemory(p->device, p->producer_memory);
        if (p->producer) vkDestroyBuffer(p->device, p->producer, NULL);
        if (p->producer_memory) vkFreeMemory(p->device, p->producer_memory, NULL);
        vkDestroyDevice(p->device, NULL);
    }
    if (p->import_fd >= 0) close(p->import_fd);
    if (p->export_fd >= 0) close(p->export_fd);
    if (p->instance) vkDestroyInstance(p->instance, NULL);
}

int main(int argc, char **argv)
{
    int skip_mmap = 0;
    if (argc == 2 && !strcmp(argv[1], "--no-fd-mmap")) skip_mmap = 1;
    else if (argc != 1) {
        fprintf(stderr, "Usage: %s [--no-fd-mmap]\n", argv[0]);
        return argc == 2 && !strcmp(argv[1], "--help") ? 0 : 1;
    }
    setvbuf(stdout, NULL, _IOLBF, 0);
    printf("opaque-fd-producer-probe v1 uid=%lu euid=%lu\n", (unsigned long)getuid(), (unsigned long)geteuid());
    puts("scope=Vulkan-owned new allocation; no arbitrary existing guest-page import; no sparse aliasing; use an outer process timeout");
    Probe probe = {.export_fd = -1, .import_fd = -1, .fd_map = MAP_FAILED};
    int result = initialize(&probe);
    if (!result) result = resources(&probe);
    if (!result) result = vulkan_roundtrip(&probe);
    if (!result && !skip_mmap) result = native_fd_roundtrip(&probe);
    if (!result && skip_mmap) puts("FD_MMAP=SKIPPED by --no-fd-mmap");
    cleanup(&probe);
    printf("RESULT=%s\n", result == 0 ? "PASS" : result == 2 ? "UNSUPPORTED" : result == 3 ? "VULKAN_PASS_FD_MMAP_UNSUPPORTED" : "FAIL");
    return result;
}
