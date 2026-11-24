#define _GNU_SOURCE
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
#include <vulkan/vulkan.h>

enum { CHUNK = 1024 * 1024, CHUNKS = 8, SIZE = CHUNK * CHUNKS };

static void check(bool condition, const char *operation) {
    if (!condition) {
        fprintf(stderr, "%s failed\n", operation);
        exit(1);
    }
}

static uint64_t now(void) {
    struct timespec value;
    check(clock_gettime(CLOCK_MONOTONIC, &value) == 0, "clock_gettime");
    return (uint64_t)value.tv_sec * 1000000000u + value.tv_nsec;
}

static inline uint64_t scan(const uint8_t *before, const uint8_t *after, bool fast) {
    uint64_t signature = 0;
    size_t next = 0;
    while (next < CHUNK) {
        if (fast) {
            while (CHUNK - next >= 64 && memcmp(before + next, after + next, 64) == 0)
                next += 64;
        }
        while (next < CHUNK && before[next] == after[next])
            ++next;
        size_t first = next;
        while (next < CHUNK && before[next] != after[next])
            ++next;
        if (first != next)
            signature = signature * 31 + first * 37 + next;
    }
    return signature;
}

__attribute__((noinline)) static uint64_t scans_scalar(const uint8_t *before, const uint8_t *after) {
    uint64_t sum = 0;
    for (size_t offset = 0; offset < SIZE; offset += CHUNK)
        sum += scan(before + offset, after + offset, false);
    return sum;
}

__attribute__((noinline)) static uint64_t scans_blocks(const uint8_t *before, const uint8_t *after) {
    uint64_t sum = 0;
    for (size_t offset = 0; offset < SIZE; offset += CHUNK)
        sum += scan(before + offset, after + offset, true);
    return sum;
}

int main(int argc, char **argv) {
    check(argc == 1 || (argc == 2 && strcmp(argv[1], "cached") == 0), "usage: scan-vulkan [cached]");
    const bool cached = argc == 2;
    const VkApplicationInfo app = {
        .sType = VK_STRUCTURE_TYPE_APPLICATION_INFO, .apiVersion = VK_API_VERSION_1_1,
    };
    const VkInstanceCreateInfo instance_info = {
        .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO, .pApplicationInfo = &app,
    };
    VkInstance instance;
    check(vkCreateInstance(&instance_info, NULL, &instance) == VK_SUCCESS, "vkCreateInstance");
    uint32_t devices = 1;
    VkPhysicalDevice physical;
    const VkResult listed = vkEnumeratePhysicalDevices(instance, &devices, &physical);
    check((listed == VK_SUCCESS || listed == VK_INCOMPLETE) && devices == 1, "enumerating device");
    VkPhysicalDeviceProperties properties;
    vkGetPhysicalDeviceProperties(physical, &properties);
    float priority = 1.0f;
    const VkDeviceQueueCreateInfo queue_info = {
        .sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO, .queueFamilyIndex = 0,
        .queueCount = 1, .pQueuePriorities = &priority,
    };
    const VkDeviceCreateInfo device_info = {
        .sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO, .queueCreateInfoCount = 1,
        .pQueueCreateInfos = &queue_info,
    };
    VkDevice device;
    check(vkCreateDevice(physical, &device_info, NULL, &device) == VK_SUCCESS, "vkCreateDevice");
    const VkBufferCreateInfo buffer_info = {
        .sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO, .size = SIZE,
        .usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT |
                 VK_BUFFER_USAGE_TRANSFER_SRC_BIT,
        .sharingMode = VK_SHARING_MODE_EXCLUSIVE,
    };
    VkBuffer buffer;
    check(vkCreateBuffer(device, &buffer_info, NULL, &buffer) == VK_SUCCESS, "vkCreateBuffer");
    VkMemoryRequirements requirements;
    VkPhysicalDeviceMemoryProperties memory;
    vkGetBufferMemoryRequirements(device, buffer, &requirements);
    vkGetPhysicalDeviceMemoryProperties(physical, &memory);
    const uint32_t required = VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT |
        (cached ? VK_MEMORY_PROPERTY_HOST_CACHED_BIT : VK_MEMORY_PROPERTY_HOST_COHERENT_BIT);
    uint32_t type = memory.memoryTypeCount;
    for (uint32_t index = 0; index < memory.memoryTypeCount; ++index) {
        const uint32_t flags = memory.memoryTypes[index].propertyFlags;
        if ((requirements.memoryTypeBits & (1u << index)) && (flags & required) == required &&
            (cached || !(flags & VK_MEMORY_PROPERTY_HOST_CACHED_BIT))) {
            type = index;
            break;
        }
    }
    check(type < memory.memoryTypeCount, "selecting compatible mappable memory");
    const uint32_t flags = memory.memoryTypes[type].propertyFlags;
    const bool noncoherent = !(flags & VK_MEMORY_PROPERTY_HOST_COHERENT_BIT);
    const VkMemoryAllocateInfo allocation_info = {
        .sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
        .allocationSize = requirements.size, .memoryTypeIndex = type,
    };
    VkDeviceMemory allocation;
    check(vkAllocateMemory(device, &allocation_info, NULL, &allocation) == VK_SUCCESS, "allocating memory");
    check(vkBindBufferMemory(device, buffer, allocation, 0) == VK_SUCCESS, "binding memory");
    void *mapped;
    check(vkMapMemory(device, allocation, 0, VK_WHOLE_SIZE, 0, &mapped) == VK_SUCCESS, "mapping memory");
    uint8_t *after = mapped;
    uint8_t *before = malloc(SIZE);
    check(before != NULL, "allocating snapshot");
    memset(before, 42, SIZE);
    const int source = memfd_create("shadow-copy-measurement", MFD_CLOEXEC);
    check(source >= 0 && write(source, before, SIZE) == SIZE, "populating snapshot source");
    printf("device=%s memory_flags=%#x bytes=%d cache_atom=%" PRIu64 "\n", properties.deviceName,
           flags, SIZE, properties.limits.nonCoherentAtomSize);

    const VkCommandPoolCreateInfo pool_info = {
        .sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO, .queueFamilyIndex = 0,
    };
    VkCommandPool pool;
    check(vkCreateCommandPool(device, &pool_info, NULL, &pool) == VK_SUCCESS, "creating command pool");
    const VkCommandBufferAllocateInfo cmd_info = {
        .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO, .commandPool = pool,
        .level = VK_COMMAND_BUFFER_LEVEL_PRIMARY, .commandBufferCount = 1,
    };
    VkCommandBuffer command;
    check(vkAllocateCommandBuffers(device, &cmd_info, &command) == VK_SUCCESS, "allocating command buffer");
    const VkCommandBufferBeginInfo begin = {.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};
    check(vkBeginCommandBuffer(command, &begin) == VK_SUCCESS, "beginning command buffer");
    const VkBufferCopy copy = {.srcOffset = 0, .dstOffset = SIZE - 8, .size = 8};
    vkCmdCopyBuffer(command, buffer, buffer, 1, &copy);
    for (size_t offset = 4092; offset < SIZE - 16; offset += 16384)
        vkCmdFillBuffer(command, buffer, offset, 8, 0x63636363u);
    const VkMemoryBarrier barrier = {
        .sType = VK_STRUCTURE_TYPE_MEMORY_BARRIER, .srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT,
        .dstAccessMask = VK_ACCESS_HOST_READ_BIT,
    };
    vkCmdPipelineBarrier(command, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_HOST_BIT,
                         0, 1, &barrier, 0, NULL, 0, NULL);
    check(vkEndCommandBuffer(command) == VK_SUCCESS, "ending command buffer");
    const VkSubmitInfo submit = {
        .sType = VK_STRUCTURE_TYPE_SUBMIT_INFO, .commandBufferCount = 1, .pCommandBuffers = &command,
    };
    const VkFenceCreateInfo fence_info = {.sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};
    VkFence fence;
    check(vkCreateFence(device, &fence_info, NULL, &fence) == VK_SUCCESS, "creating fence");
    VkQueue queue;
    vkGetDeviceQueue(device, 0, 0, &queue);
    const VkMappedMemoryRange range = {
        .sType = VK_STRUCTURE_TYPE_MAPPED_MEMORY_RANGE, .memory = allocation, .size = VK_WHOLE_SIZE,
    };
    uint8_t *expected = malloc(SIZE);
    check(expected != NULL, "allocating expected bytes");
    memcpy(expected, before, SIZE);
    for (size_t offset = 4092; offset < SIZE - 16; offset += 16384)
        memset(expected + offset, 99, 8);

    for (int trial = 0; trial < 5; ++trial) {
        uint8_t sentinel[8];
        memset(sentinel, 71 + trial, sizeof(sentinel));
        check(pwrite(source, sentinel, sizeof(sentinel), 0) == sizeof(sentinel), "changing upload witness");
        memcpy(expected, sentinel, sizeof(sentinel));
        memcpy(expected + SIZE - sizeof(sentinel), sentinel, sizeof(sentinel));
        uint64_t t0 = now();
        check(pread(source, before, SIZE, 0) == SIZE, "reading snapshot");
        uint64_t t1 = now();
        memcpy(after, before, SIZE);
        uint64_t t2 = now();
        if (noncoherent)
            check(vkFlushMappedMemoryRanges(device, 1, &range) == VK_SUCCESS, "flushing CPU writes");
        uint64_t t3 = now();
        check(vkResetFences(device, 1, &fence) == VK_SUCCESS, "resetting fence");
        check(vkQueueSubmit(queue, 1, &submit, fence) == VK_SUCCESS, "submitting GPU writes");
        check(vkWaitForFences(device, 1, &fence, VK_TRUE, 1000000000) == VK_SUCCESS, "waiting for GPU writes");
        uint64_t t4 = now();
        if (noncoherent)
            check(vkInvalidateMappedMemoryRanges(device, 1, &range) == VK_SUCCESS, "invalidating GPU writes");
        uint64_t t5 = now();
        uint64_t scalar_ns, block_ns, scalar, block;
        if (trial % 2 == 0) {
            uint64_t start = now();
            scalar = scans_scalar(before, after);
            scalar_ns = now() - start;
            start = now();
            block = scans_blocks(before, after);
            block_ns = now() - start;
        } else {
            uint64_t start = now();
            block = scans_blocks(before, after);
            block_ns = now() - start;
            start = now();
            scalar = scans_scalar(before, after);
            scalar_ns = now() - start;
        }
        check(scalar == block && block != 0 && memcmp(after, expected, SIZE) == 0, "comparing GPU writeback");
        printf("trial=%d read_ns=%" PRIu64 " upload_ns=%" PRIu64 " flush_ns=%" PRIu64
               " gpu_ns=%" PRIu64 " invalidate_ns=%" PRIu64 " scalar_ns=%" PRIu64
               " block_ns=%" PRIu64 " signature=%" PRIu64 "\n", trial, t1 - t0, t2 - t1,
               t3 - t2, t4 - t3, t5 - t4, scalar_ns, block_ns, block);
    }

    close(source);
    free(expected);
    free(before);
    vkDestroyFence(device, fence, NULL);
    vkDestroyCommandPool(device, pool, NULL);
    vkUnmapMemory(device, allocation);
    vkDestroyBuffer(device, buffer, NULL);
    vkFreeMemory(device, allocation, NULL);
    vkDestroyDevice(device, NULL);
    vkDestroyInstance(instance, NULL);
    return 0;
}
