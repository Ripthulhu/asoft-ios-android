/* SPDX-License-Identifier: MIT
 * Query-only report for the Pixel PowerVR investigation.
 * Creates a Vulkan instance, but NO VkDevice, GPU resource, allocation, command,
 * queue, or submission. External-memory answers are capability declarations,
 * not proof that an actual FD can be imported or that CPU/GPU sharing works.
 */
#include <vulkan/vulkan.h>

#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define COUNT(a) (sizeof(a) / sizeof((a)[0]))
#define BIT(value, flag) ((unsigned)(((value) & (flag)) != 0))
/* NDK r29's headers expose 1.3; all commands used here are core <= 1.1.
 * Requesting loader-reported 1.4 requires only its standard version encoding. */
#define REPORT_API_1_4 VK_MAKE_API_VERSION(0, 1, 4, 0)
#define F(group, member) printf("feature %s=%u\n", #member, (group).member)
#define P(group, member) printf("property %s=%" PRIu64 "\n", #member, (uint64_t)(group).member)

static int has(const VkExtensionProperties *items, uint32_t count, const char *name)
{
    for (uint32_t i = 0; i < count; ++i)
        if (!strcmp(items[i].extensionName, name)) return 1;
    return 0;
}

static void version(const char *label, uint32_t value)
{
    printf("%s=%u.%u.%u raw=0x%08x\n", label, VK_API_VERSION_MAJOR(value),
           VK_API_VERSION_MINOR(value), VK_API_VERSION_PATCH(value), value);
}

static int fail(const char *operation, VkResult result)
{
    fprintf(stderr, "FAIL: %s VkResult=%d\n", operation, result);
    return 1;
}

/* The physical-device query has no enabled logical-device feature set.
 * BDA rows are only queried when the physical device advertises the feature;
 * using the resulting resource would still require enabling it on a VkDevice.
 */
static void matrix(VkPhysicalDevice pd, const VkExtensionProperties *extensions,
                   uint32_t count, VkBool32 bda)
{
    static const struct {
        const char *name;
        VkBufferUsageFlags usage;
        int needs_bda;
    } rows[] = {
        {"transfer_src", VK_BUFFER_USAGE_TRANSFER_SRC_BIT, 0},
        {"transfer_dst", VK_BUFFER_USAGE_TRANSFER_DST_BIT, 0},
        {"transfer_src_dst", VK_BUFFER_USAGE_TRANSFER_SRC_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT, 0},
        {"storage", VK_BUFFER_USAGE_STORAGE_BUFFER_BIT, 0},
        {"storage_src", VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_TRANSFER_SRC_BIT, 0},
        {"storage_dst", VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT, 0},
        {"storage_src_dst", VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_TRANSFER_SRC_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT, 0},
        {"uniform", VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT, 0},
        {"uniform_texel", VK_BUFFER_USAGE_UNIFORM_TEXEL_BUFFER_BIT, 0},
        {"storage_texel", VK_BUFFER_USAGE_STORAGE_TEXEL_BUFFER_BIT, 0},
        {"vertex", VK_BUFFER_USAGE_VERTEX_BUFFER_BIT, 0},
        {"index", VK_BUFFER_USAGE_INDEX_BUFFER_BIT, 0},
        {"indirect", VK_BUFFER_USAGE_INDIRECT_BUFFER_BIT, 0},
        {"runtime_base", 0x1ffu, 0},
        {"device_address", VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT, 1},
        {"storage_src_dst_bda", VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_TRANSFER_SRC_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT | VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT, 1},
        {"runtime_base_bda", 0x1ffu | VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT, 1},
    };
    static const struct {
        const char *name;
        VkExternalMemoryHandleTypeFlagBits type;
        const char *extension;
    } handles[] = {
        {"DMA_BUF", VK_EXTERNAL_MEMORY_HANDLE_TYPE_DMA_BUF_BIT_EXT, VK_EXT_EXTERNAL_MEMORY_DMA_BUF_EXTENSION_NAME},
        {"OPAQUE_FD", VK_EXTERNAL_MEMORY_HANDLE_TYPE_OPAQUE_FD_BIT, VK_KHR_EXTERNAL_MEMORY_FD_EXTENSION_NAME},
        {"ANDROID_HARDWARE_BUFFER", VK_EXTERNAL_MEMORY_HANDLE_TYPE_ANDROID_HARDWARE_BUFFER_BIT_ANDROID,
         "VK_ANDROID_external_memory_android_hardware_buffer"},
    };
    puts("matrix_scope=physical-device declarations; flags=0; no allocation/import/export/binding/submission");
    puts("matrix_import_rule=IMPORTABLE bit is required; compatible/export-from-imported bits do not imply importability");
    puts("matrix_runtime_rule=IMPORTABLE and not DEDICATED_ONLY are necessary, not sufficient; actual-FD memory class remains untested");
    for (size_t h = 0; h < COUNT(handles); ++h) {
        if (!has(extensions, count, handles[h].extension)) {
            printf("matrix_handle %s SKIPPED missing=%s\n", handles[h].name, handles[h].extension);
            continue;
        }
        for (size_t r = 0; r < COUNT(rows); ++r) {
            if (rows[r].needs_bda && !bda) {
                printf("matrix handle=%s row=%s SKIPPED bufferDeviceAddress=0\n", handles[h].name, rows[r].name);
                continue;
            }
            const VkPhysicalDeviceExternalBufferInfo info = {
                .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_EXTERNAL_BUFFER_INFO,
                .flags = 0, .usage = rows[r].usage, .handleType = handles[h].type,
            };
            VkExternalBufferProperties output = {.sType = VK_STRUCTURE_TYPE_EXTERNAL_BUFFER_PROPERTIES};
            vkGetPhysicalDeviceExternalBufferProperties(pd, &info, &output);
            VkExternalMemoryProperties p = output.externalMemoryProperties;
            printf("matrix handle=%s type=0x%x row=%s usage=0x%x flags=0 features=0x%x importable=%u exportable=%u dedicated_only=%u compatible=0x%x export_from_imported=0x%x\n",
                   handles[h].name, handles[h].type, rows[r].name, rows[r].usage,
                   p.externalMemoryFeatures,
                   BIT(p.externalMemoryFeatures, VK_EXTERNAL_MEMORY_FEATURE_IMPORTABLE_BIT),
                   BIT(p.externalMemoryFeatures, VK_EXTERNAL_MEMORY_FEATURE_EXPORTABLE_BIT),
                   BIT(p.externalMemoryFeatures, VK_EXTERNAL_MEMORY_FEATURE_DEDICATED_ONLY_BIT),
                   p.compatibleHandleTypes, p.exportFromImportedHandleTypes);
        }
    }
}

static int report(VkPhysicalDevice pd)
{
    VkPhysicalDeviceProperties basic;
    vkGetPhysicalDeviceProperties(pd, &basic);
    printf("device=%s vendor_id=0x%x device_id=0x%x driver_version=0x%x type=%u\n",
           basic.deviceName, basic.vendorID, basic.deviceID, basic.driverVersion, basic.deviceType);
    version("device_api", basic.apiVersion);
    if (basic.apiVersion < VK_API_VERSION_1_3) {
        puts("UNSUPPORTED: this focused reporter requires a Vulkan 1.3 physical device");
        return 2;
    }
    uint32_t count = 0;
    VkResult vr = vkEnumerateDeviceExtensionProperties(pd, NULL, &count, NULL);
    if (vr != VK_SUCCESS) return fail("extension count", vr);
    if (count > 4096) { puts("FAIL: implausible extension count"); return 1; }
    VkExtensionProperties *extensions = calloc(count ? count : 1, sizeof(*extensions));
    if (!extensions) { puts("FAIL: CPU allocation for extension list"); return 1; }
    vr = vkEnumerateDeviceExtensionProperties(pd, NULL, &count, extensions);
    if (vr != VK_SUCCESS) { free(extensions); return fail("extension list", vr); }
    printf("device_extension_count=%u\n", count);
    static const char *const relevant[] = {
        VK_EXT_EXTERNAL_MEMORY_DMA_BUF_EXTENSION_NAME,
        VK_KHR_EXTERNAL_MEMORY_FD_EXTENSION_NAME,
        "VK_ANDROID_external_memory_android_hardware_buffer",
        VK_EXT_EXTERNAL_MEMORY_HOST_EXTENSION_NAME,
        VK_EXT_QUEUE_FAMILY_FOREIGN_EXTENSION_NAME,
        VK_EXT_SHADER_TILE_IMAGE_EXTENSION_NAME,
        VK_EXT_RASTERIZATION_ORDER_ATTACHMENT_ACCESS_EXTENSION_NAME,
        VK_ARM_RASTERIZATION_ORDER_ATTACHMENT_ACCESS_EXTENSION_NAME,
        VK_EXT_FRAGMENT_SHADER_INTERLOCK_EXTENSION_NAME,
        VK_EXT_IMAGE_DRM_FORMAT_MODIFIER_EXTENSION_NAME,
        VK_KHR_BUFFER_DEVICE_ADDRESS_EXTENSION_NAME,
        VK_KHR_DYNAMIC_RENDERING_EXTENSION_NAME,
        VK_EXT_SHADER_STENCIL_EXPORT_EXTENSION_NAME,
        VK_EXT_ROBUSTNESS_2_EXTENSION_NAME,
    };
    for (size_t i = 0; i < COUNT(relevant); ++i)
        printf("extension %s=%u\n", relevant[i], has(extensions, count, relevant[i]));

    int tile_present = has(extensions, count, VK_EXT_SHADER_TILE_IMAGE_EXTENSION_NAME);
    int roaa_present = has(extensions, count, VK_EXT_RASTERIZATION_ORDER_ATTACHMENT_ACCESS_EXTENSION_NAME)
                    || has(extensions, count, VK_ARM_RASTERIZATION_ORDER_ATTACHMENT_ACCESS_EXTENSION_NAME);
    int interlock_present = has(extensions, count, VK_EXT_FRAGMENT_SHADER_INTERLOCK_EXTENSION_NAME);
    int host_present = has(extensions, count, VK_EXT_EXTERNAL_MEMORY_HOST_EXTENSION_NAME);

    VkPhysicalDeviceShaderTileImagePropertiesEXT tile_p = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_SHADER_TILE_IMAGE_PROPERTIES_EXT};
    VkPhysicalDeviceExternalMemoryHostPropertiesEXT host_p = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_EXTERNAL_MEMORY_HOST_PROPERTIES_EXT};
    VkPhysicalDeviceMaintenance3Properties maintenance_p = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_MAINTENANCE_3_PROPERTIES};
    VkPhysicalDeviceVulkan13Properties p13 = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_3_PROPERTIES, .pNext = &maintenance_p};
    VkPhysicalDeviceDriverProperties driver = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DRIVER_PROPERTIES, .pNext = &p13};
    VkPhysicalDeviceProperties2 p2 = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2, .pNext = &driver};
    if (host_present) { host_p.pNext = p2.pNext; p2.pNext = &host_p; }
    if (tile_present) { tile_p.pNext = p2.pNext; p2.pNext = &tile_p; }
    vkGetPhysicalDeviceProperties2(pd, &p2);
    printf("driver_name=%.*s\ndriver_info=%.*s\ndriver_id=%u conformance=%u.%u.%u.%u\n",
           VK_MAX_DRIVER_NAME_SIZE, driver.driverName, VK_MAX_DRIVER_INFO_SIZE, driver.driverInfo,
           driver.driverID, driver.conformanceVersion.major, driver.conformanceVersion.minor,
           driver.conformanceVersion.subminor, driver.conformanceVersion.patch);
    P(p13, maxBufferSize); P(maintenance_p, maxMemoryAllocationSize);
    P(basic.limits, maxMemoryAllocationCount); P(basic.limits, maxStorageBufferRange);
    P(basic.limits, maxUniformBufferRange); P(basic.limits, bufferImageGranularity);
    P(basic.limits, minMemoryMapAlignment); P(basic.limits, nonCoherentAtomSize);
    P(basic.limits, minStorageBufferOffsetAlignment); P(basic.limits, minUniformBufferOffsetAlignment);
    if (host_present) P(host_p, minImportedHostPointerAlignment);
    if (tile_present) {
        P(tile_p, shaderTileImageCoherentReadAccelerated);
        P(tile_p, shaderTileImageReadSampleFromPixelRateInvocation);
        P(tile_p, shaderTileImageReadFromHelperInvocation);
    }

    VkPhysicalDeviceShaderTileImageFeaturesEXT tile_f = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_SHADER_TILE_IMAGE_FEATURES_EXT};
    VkPhysicalDeviceRasterizationOrderAttachmentAccessFeaturesEXT roaa_f = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_RASTERIZATION_ORDER_ATTACHMENT_ACCESS_FEATURES_EXT};
    VkPhysicalDeviceFragmentShaderInterlockFeaturesEXT interlock_f = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FRAGMENT_SHADER_INTERLOCK_FEATURES_EXT};
    VkPhysicalDeviceVulkan13Features f13 = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_3_FEATURES};
    VkPhysicalDeviceVulkan12Features f12 = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_2_FEATURES, .pNext = &f13};
    VkPhysicalDeviceVulkan11Features f11 = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_1_FEATURES, .pNext = &f12};
    VkPhysicalDeviceFeatures2 f2 = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2, .pNext = &f11};
    if (tile_present) { tile_f.pNext = f2.pNext; f2.pNext = &tile_f; }
    if (roaa_present) { roaa_f.pNext = f2.pNext; f2.pNext = &roaa_f; }
    if (interlock_present) { interlock_f.pNext = f2.pNext; f2.pNext = &interlock_f; }
    vkGetPhysicalDeviceFeatures2(pd, &f2);
    puts("feature_scope=physical-device support; no logical device created or features enabled");
    F(f2.features, sparseBinding); F(f2.features, sparseResidencyBuffer);
    F(f2.features, sparseResidencyAliased); F(f2.features, sparseResidencyImage2D);
    F(f2.features, shaderInt16); F(f2.features, shaderInt64); F(f2.features, shaderFloat64);
    F(f2.features, fragmentStoresAndAtomics); F(f2.features, vertexPipelineStoresAndAtomics);
    F(f2.features, independentBlend); F(f2.features, imageCubeArray);
    F(f2.features, shaderStorageImageWriteWithoutFormat); F(f2.features, shaderStorageImageReadWithoutFormat);
    F(f2.features, sampleRateShading); F(f2.features, robustBufferAccess);
    F(f11, storageBuffer16BitAccess); F(f11, uniformAndStorageBuffer16BitAccess);
    F(f12, shaderFloat16); F(f12, shaderInt8); F(f12, storageBuffer8BitAccess);
    F(f12, timelineSemaphore); F(f12, bufferDeviceAddress); F(f12, bufferDeviceAddressCaptureReplay);
    F(f12, descriptorIndexing); F(f12, runtimeDescriptorArray); F(f12, descriptorBindingPartiallyBound);
    F(f12, scalarBlockLayout); F(f12, vulkanMemoryModel); F(f12, separateDepthStencilLayouts);
    F(f13, dynamicRendering); F(f13, synchronization2); F(f13, maintenance4);
    F(f13, shaderDemoteToHelperInvocation); F(f13, robustImageAccess);
    if (tile_present) { F(tile_f, shaderTileImageColorReadAccess); F(tile_f, shaderTileImageDepthReadAccess); F(tile_f, shaderTileImageStencilReadAccess); }
    if (roaa_present) { F(roaa_f, rasterizationOrderColorAttachmentAccess); F(roaa_f, rasterizationOrderDepthAttachmentAccess); F(roaa_f, rasterizationOrderStencilAttachmentAccess); }
    if (interlock_present) { F(interlock_f, fragmentShaderPixelInterlock); F(interlock_f, fragmentShaderSampleInterlock); F(interlock_f, fragmentShaderShadingRateInterlock); }

    VkPhysicalDeviceMemoryProperties memory;
    vkGetPhysicalDeviceMemoryProperties(pd, &memory);
    for (uint32_t i = 0; i < memory.memoryHeapCount; ++i)
        printf("memory_heap index=%u size=%" PRIu64 " flags=0x%x\n", i, memory.memoryHeaps[i].size, memory.memoryHeaps[i].flags);
    for (uint32_t i = 0; i < memory.memoryTypeCount; ++i) {
        VkMemoryPropertyFlags f = memory.memoryTypes[i].propertyFlags;
        printf("memory_type index=%u heap=%u flags=0x%x device_local=%u host_visible=%u host_coherent=%u host_cached=%u\n",
               i, memory.memoryTypes[i].heapIndex, f, BIT(f, VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT),
               BIT(f, VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT), BIT(f, VK_MEMORY_PROPERTY_HOST_COHERENT_BIT),
               BIT(f, VK_MEMORY_PROPERTY_HOST_CACHED_BIT));
    }
    uint32_t queues = 0;
    vkGetPhysicalDeviceQueueFamilyProperties(pd, &queues, NULL);
    if (queues > 4096) { free(extensions); puts("FAIL: implausible queue count"); return 1; }
    VkQueueFamilyProperties *families = calloc(queues ? queues : 1, sizeof(*families));
    if (!families) { free(extensions); puts("FAIL: CPU allocation for queues"); return 1; }
    vkGetPhysicalDeviceQueueFamilyProperties(pd, &queues, families);
    for (uint32_t i = 0; i < queues; ++i)
        printf("queue_family index=%u count=%u flags=0x%x graphics=%u compute=%u transfer=%u sparse=%u\n",
               i, families[i].queueCount, families[i].queueFlags, BIT(families[i].queueFlags, VK_QUEUE_GRAPHICS_BIT),
               BIT(families[i].queueFlags, VK_QUEUE_COMPUTE_BIT), BIT(families[i].queueFlags, VK_QUEUE_TRANSFER_BIT),
               BIT(families[i].queueFlags, VK_QUEUE_SPARSE_BINDING_BIT));
    free(families);
    matrix(pd, extensions, count, f12.bufferDeviceAddress);
    free(extensions);
    return 0;
}

int main(int argc, char **argv)
{
    uint32_t requested = 0, selected = 0;
    for (int i = 1; i < argc; ++i) {
        if (!strcmp(argv[i], "--api") && i + 1 < argc) {
            const char *value = argv[++i];
            if (!strcmp(value, "1.3")) requested = VK_API_VERSION_1_3;
            else if (!strcmp(value, "1.4")) requested = REPORT_API_1_4;
            else { fputs("--api must be 1.3 or 1.4\n", stderr); return 1; }
        } else if (!strcmp(argv[i], "--device") && i + 1 < argc) {
            const char *value = argv[++i];
            char *end = NULL;
            errno = 0;
            unsigned long index = strtoul(value, &end, 10);
            if (errno || end == value || *end || value[0] == '-' || index > UINT32_MAX) {
                fputs("Invalid --device index\n", stderr); return 1;
            }
            selected = (uint32_t)index;
        } else {
            fprintf(stderr, "Usage: %s [--api 1.3|1.4] [--device INDEX]\n", argv[0]);
            return strcmp(argv[i], "--help") != 0;
        }
    }
    setvbuf(stdout, NULL, _IOLBF, 0);
    printf("vulkan-caps-query v1 uid=%lu euid=%lu\n", (unsigned long)getuid(), (unsigned long)geteuid());
    puts("scope=query-only; no VkDevice, GPU allocation, import, resource, queue, or submission; no UUID output");
    uint32_t loader_api = VK_API_VERSION_1_0;
    PFN_vkEnumerateInstanceVersion enumerate_version = (PFN_vkEnumerateInstanceVersion)vkGetInstanceProcAddr(VK_NULL_HANDLE, "vkEnumerateInstanceVersion");
    VkResult vr = enumerate_version ? enumerate_version(&loader_api) : VK_SUCCESS;
    if (vr != VK_SUCCESS) return fail("vkEnumerateInstanceVersion", vr);
    version("loader_api", loader_api);
    if (!requested) requested = loader_api >= REPORT_API_1_4 ? REPORT_API_1_4 : VK_API_VERSION_1_3;
    version("requested_api", requested);
    if (loader_api < requested) { puts("UNSUPPORTED: loader API below requested version"); return 2; }
    const VkApplicationInfo app = {.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO, .pApplicationName = "pixel-vulkan-query", .apiVersion = requested};
    const VkInstanceCreateInfo create = {.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO, .pApplicationInfo = &app};
    VkInstance instance = VK_NULL_HANDLE;
    vr = vkCreateInstance(&create, NULL, &instance);
    if (vr != VK_SUCCESS) return fail("vkCreateInstance", vr);
    int result = 1;
    uint32_t count = 0;
    vr = vkEnumeratePhysicalDevices(instance, &count, NULL);
    if (vr != VK_SUCCESS) { fail("physical device count", vr); goto done; }
    printf("physical_device_count=%u selected_device=%u\n", count, selected);
    if (selected >= count || count > 256) { puts("UNSUPPORTED: unavailable device index/count"); result = 2; goto done; }
    VkPhysicalDevice *devices = calloc(count, sizeof(*devices));
    if (!devices) { puts("FAIL: CPU allocation for device list"); goto done; }
    vr = vkEnumeratePhysicalDevices(instance, &count, devices);
    if (vr != VK_SUCCESS || selected >= count) {
        free(devices); fail("physical device list", vr); goto done;
    }
    result = report(devices[selected]);
    free(devices);
done:
    vkDestroyInstance(instance, NULL);
    if (!result) puts("result=QUERY_COMPLETE; capability enumeration only, not an import or rendering test");
    return result;
}
