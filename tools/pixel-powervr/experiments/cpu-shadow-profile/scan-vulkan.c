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

int main(void) {
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
        .usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT, .sharingMode = VK_SHARING_MODE_EXCLUSIVE,
    };
    VkBuffer buffer;
    check(vkCreateBuffer(device, &buffer_info, NULL, &buffer) == VK_SUCCESS, "vkCreateBuffer");
    VkMemoryRequirements requirements;
    VkPhysicalDeviceMemoryProperties memory;
    vkGetBufferMemoryRequirements(device, buffer, &requirements);
    vkGetPhysicalDeviceMemoryProperties(physical, &memory);
    const uint32_t required = VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT;
    uint32_t type = memory.memoryTypeCount;
    for (uint32_t index = 0; index < memory.memoryTypeCount; ++index) {
        const uint32_t flags = memory.memoryTypes[index].propertyFlags;
        if ((requirements.memoryTypeBits & (1u << index)) && (flags & required) == required &&
            !(flags & VK_MEMORY_PROPERTY_HOST_CACHED_BIT)) {
            type = index;
            break;
        }
    }
    check(type < memory.memoryTypeCount, "selecting host-coherent uncached memory");
    const VkMemoryAllocateInfo allocation_info = {
        .sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
        .allocationSize = requirements.size, .memoryTypeIndex = type,
    };
    VkDeviceMemory allocation;
    check(vkAllocateMemory(device, &allocation_info, NULL, &allocation) == VK_SUCCESS, "allocating memory");
    check(vkBindBufferMemory(device, buffer, allocation, 0) == VK_SUCCESS, "binding memory");
    void *mapped;
    check(vkMapMemory(device, allocation, 0, SIZE, 0, &mapped) == VK_SUCCESS, "mapping memory");
    uint8_t *after = mapped;
    uint8_t *before = malloc(SIZE);
    check(before != NULL, "allocating snapshot");
    memset(before, 42, SIZE);
    const int source = memfd_create("shadow-copy-measurement", MFD_CLOEXEC);
    check(source >= 0 && write(source, before, SIZE) == SIZE, "populating snapshot source");
    printf("device=%s memory_flags=%#x bytes=%d\n", properties.deviceName,
           memory.memoryTypes[type].propertyFlags, SIZE);

    for (int trial = 0; trial < 5; ++trial) {
        uint64_t t0 = now();
        check(pread(source, before, SIZE, 0) == SIZE, "reading snapshot");
        uint64_t t1 = now();
        memcpy(after, before, SIZE);
        uint64_t t2 = now();
        for (size_t offset = 4093; offset < SIZE - 16; offset += 16384)
            memset(after + offset, 99, 8);
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
        check(scalar == block && block != 0, "comparing changed ranges");
        printf("trial=%d read_ns=%" PRIu64 " upload_ns=%" PRIu64 " scalar_ns=%" PRIu64
               " block_ns=%" PRIu64 " signature=%" PRIu64 "\n", trial, t1 - t0, t2 - t1,
               scalar_ns, block_ns, block);
    }

    close(source);
    free(before);
    vkUnmapMemory(device, allocation);
    vkDestroyBuffer(device, buffer, NULL);
    vkFreeMemory(device, allocation, NULL);
    vkDestroyDevice(device, NULL);
    vkDestroyInstance(instance, NULL);
    return 0;
}
