/* SPDX-License-Identifier: MIT */
#ifndef PIXEL_CACHED_POLICY_H
#define PIXEL_CACHED_POLICY_H
#include <vulkan/vulkan_core.h>

/* Both buffer requirement masks must be supplied by the caller. A missing
 * cached type is an unsupported result, never a fallback to coherent-only. */
static int cached_select_type(const VkPhysicalDeviceMemoryProperties *memory, uint32_t bits)
{
    const VkMemoryPropertyFlags required = VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT |
                                           VK_MEMORY_PROPERTY_HOST_CACHED_BIT;
    int fallback = -1;
    if (memory->memoryTypeCount > VK_MAX_MEMORY_TYPES) return -1;
    for (uint32_t i = 0; i < memory->memoryTypeCount; ++i) {
        VkMemoryPropertyFlags flags = memory->memoryTypes[i].propertyFlags;
        if (!(bits & (1u << i)) || (flags & required) != required ||
            (flags & (VK_MEMORY_PROPERTY_LAZILY_ALLOCATED_BIT |
                      VK_MEMORY_PROPERTY_PROTECTED_BIT))) continue;
        if (flags & VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT) return (int)i;
        if (fallback < 0) fallback = (int)i;
    }
    return fallback;
}
#endif
