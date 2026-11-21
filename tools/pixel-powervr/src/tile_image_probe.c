/*
 * Test VK_EXT_shader_tile_image's coherent color reads, using the system ICD.
 *
 * A pass clears a 32x32 RGBA8_UINT image, then draws overlapping full-screen
 * triangles. Each fragment reads the attachment and updates exact integer
 * recurrences. Test one uses 32 triangles in one draw; test two uses 32 in each
 * of two draws with NO intervening barrier. Every pixel is checked after a
 * fenced image-to-buffer readback. This tests color ordering only: it does not
 * establish Metal translation, depth/stencil, MSAA or iOS support.
 *
 * Build the two authored GLSL files for Vulkan 1.3 as tile_image.vert.spv and
 * tile_image.frag.spv. Pass their directory with --shader-dir (default: .).
 * Exit status: 0 = passed, 1 = failed, 2 = required capability unavailable.
 * GPU waits are limited to 5 s; use a process timeout as well to bound driver
 * calls such as pipeline creation. No root, system changes or guest are used.
 */
#include <vulkan/vulkan.h>

#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { WIDTH = 32, HEIGHT = 32, TRIANGLES = 32 };
#define PIXEL_BYTES ((VkDeviceSize)WIDTH * HEIGHT * 4)
#define WAIT_NS UINT64_C(5000000000)

typedef struct Probe {
    VkInstance instance;
    VkDebugUtilsMessengerEXT messenger;
    PFN_vkDestroyDebugUtilsMessengerEXT destroy_messenger;
    VkPhysicalDevice physical;
    VkDevice device;
    VkQueue queue;
    uint32_t family;
    VkPhysicalDeviceMemoryProperties memory;
    VkImage image;
    VkDeviceMemory image_memory;
    VkImageView view;
    VkBuffer readback;
    VkDeviceMemory readback_memory;
    void *mapped;
    VkShaderModule vertex, fragment;
    VkPipelineLayout layout;
    VkPipeline pipeline;
    VkCommandPool pool;
    VkCommandBuffer command;
    VkFence fence;
    atomic_uint validation_errors;
} Probe;

#define TRY(p, call) do { \
    VkResult result_ = (call); \
    if (result_ != VK_SUCCESS) { \
        fprintf(stderr, "FAIL: %s returned %d\n", #call, result_); \
        return 1; \
    } \
} while (0)

static VKAPI_ATTR VkBool32 VKAPI_CALL validation_message(
    VkDebugUtilsMessageSeverityFlagBitsEXT severity,
    VkDebugUtilsMessageTypeFlagsEXT types,
    const VkDebugUtilsMessengerCallbackDataEXT *data, void *opaque)
{
    (void)types;
    Probe *p = opaque;
    if (severity & VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT)
        atomic_fetch_add(&p->validation_errors, 1);
    fprintf(stderr, "validation: %s\n", data->pMessage);
    return VK_FALSE;
}

static int has_instance_extension(const char *name)
{
    uint32_t count = 0;
    if (vkEnumerateInstanceExtensionProperties(NULL, &count, NULL) != VK_SUCCESS)
        return 0;
    VkExtensionProperties *items = calloc(count ? count : 1, sizeof(*items));
    if (!items) return 0;
    VkResult result = vkEnumerateInstanceExtensionProperties(NULL, &count, items);
    int found = 0;
    if (result == VK_SUCCESS)
        for (uint32_t i = 0; i < count; ++i)
            found |= strcmp(items[i].extensionName, name) == 0;
    free(items);
    return found;
}

static int has_validation_layer(void)
{
    uint32_t count = 0;
    if (vkEnumerateInstanceLayerProperties(&count, NULL) != VK_SUCCESS) return 0;
    VkLayerProperties *items = calloc(count ? count : 1, sizeof(*items));
    if (!items) return 0;
    VkResult result = vkEnumerateInstanceLayerProperties(&count, items);
    int found = 0;
    if (result == VK_SUCCESS)
        for (uint32_t i = 0; i < count; ++i)
            found |= strcmp(items[i].layerName, "VK_LAYER_KHRONOS_validation") == 0;
    free(items);
    return found;
}

static int initialize(Probe *p, uint32_t device_index, int validation)
{
    uint32_t loader_version = VK_API_VERSION_1_0;
    PFN_vkEnumerateInstanceVersion version = (PFN_vkEnumerateInstanceVersion)
        vkGetInstanceProcAddr(VK_NULL_HANDLE, "vkEnumerateInstanceVersion");
    if (version) TRY(p, version(&loader_version));
    printf("loader_api: %u.%u.%u\n", VK_API_VERSION_MAJOR(loader_version),
           VK_API_VERSION_MINOR(loader_version), VK_API_VERSION_PATCH(loader_version));
    if (loader_version < VK_API_VERSION_1_3) {
        puts("UNSUPPORTED: VK_EXT_shader_tile_image requires Vulkan 1.3");
        return 2;
    }
    if (validation && (!has_validation_layer() ||
                      !has_instance_extension(VK_EXT_DEBUG_UTILS_EXTENSION_NAME))) {
        puts("UNSUPPORTED: --validation needs VK_LAYER_KHRONOS_validation and VK_EXT_debug_utils");
        return 2;
    }
    const char *layer = "VK_LAYER_KHRONOS_validation";
    const char *debug_extension = VK_EXT_DEBUG_UTILS_EXTENSION_NAME;
    VkDebugUtilsMessengerCreateInfoEXT debug = {
        .sType = VK_STRUCTURE_TYPE_DEBUG_UTILS_MESSENGER_CREATE_INFO_EXT,
        .messageSeverity = VK_DEBUG_UTILS_MESSAGE_SEVERITY_WARNING_BIT_EXT |
                           VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT,
        .messageType = VK_DEBUG_UTILS_MESSAGE_TYPE_GENERAL_BIT_EXT |
                       VK_DEBUG_UTILS_MESSAGE_TYPE_VALIDATION_BIT_EXT |
                       VK_DEBUG_UTILS_MESSAGE_TYPE_PERFORMANCE_BIT_EXT,
        .pfnUserCallback = validation_message, .pUserData = p
    };
    VkApplicationInfo application = {
        .sType = VK_STRUCTURE_TYPE_APPLICATION_INFO,
        .pApplicationName = "tile-image-ordering-probe",
        .applicationVersion = 1, .apiVersion = VK_API_VERSION_1_3
    };
    VkInstanceCreateInfo create = {
        .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
        .pNext = validation ? &debug : NULL,
        .pApplicationInfo = &application,
        .enabledLayerCount = validation ? 1u : 0u,
        .ppEnabledLayerNames = validation ? &layer : NULL,
        .enabledExtensionCount = validation ? 1u : 0u,
        .ppEnabledExtensionNames = validation ? &debug_extension : NULL
    };
    TRY(p, vkCreateInstance(&create, NULL, &p->instance));
    if (validation) {
        PFN_vkCreateDebugUtilsMessengerEXT make = (PFN_vkCreateDebugUtilsMessengerEXT)
            vkGetInstanceProcAddr(p->instance, "vkCreateDebugUtilsMessengerEXT");
        p->destroy_messenger = (PFN_vkDestroyDebugUtilsMessengerEXT)
            vkGetInstanceProcAddr(p->instance, "vkDestroyDebugUtilsMessengerEXT");
        if (!make || !p->destroy_messenger) {
            puts("FAIL: debug-utils entry points missing");
            return 1;
        }
        TRY(p, make(p->instance, &debug, NULL, &p->messenger));
    }
    uint32_t count = 0;
    TRY(p, vkEnumeratePhysicalDevices(p->instance, &count, NULL));
    if (device_index >= count) {
        printf("UNSUPPORTED: device index %u, available devices %u\n", device_index, count);
        return 2;
    }
    VkPhysicalDevice *devices = calloc(count, sizeof(*devices));
    if (!devices) return 1;
    VkResult result = vkEnumeratePhysicalDevices(p->instance, &count, devices);
    if (result == VK_SUCCESS) p->physical = devices[device_index];
    free(devices);
    if (result != VK_SUCCESS) {
        printf("FAIL: device enumeration returned %d\n", result);
        return 1;
    }
    VkPhysicalDeviceProperties properties;
    vkGetPhysicalDeviceProperties(p->physical, &properties);
    printf("device: %s\nvendor_id: 0x%04x\ndevice_id: 0x%04x\ndriver_version: 0x%x\n",
           properties.deviceName, properties.vendorID, properties.deviceID, properties.driverVersion);
    printf("device_api: %u.%u.%u\n", VK_API_VERSION_MAJOR(properties.apiVersion),
           VK_API_VERSION_MINOR(properties.apiVersion), VK_API_VERSION_PATCH(properties.apiVersion));
    TRY(p, vkEnumerateDeviceExtensionProperties(p->physical, NULL, &count, NULL));
    VkExtensionProperties *extensions = calloc(count ? count : 1, sizeof(*extensions));
    if (!extensions) return 1;
    result = vkEnumerateDeviceExtensionProperties(p->physical, NULL, &count, extensions);
    int tile = 0;
    if (result == VK_SUCCESS)
        for (uint32_t i = 0; i < count; ++i)
            tile |= strcmp(extensions[i].extensionName, VK_EXT_SHADER_TILE_IMAGE_EXTENSION_NAME) == 0;
    free(extensions);
    if (result != VK_SUCCESS) {
        printf("FAIL: extension enumeration returned %d\n", result);
        return 1;
    }
    printf("VK_EXT_shader_tile_image: %d\n", tile);
    if (!tile || properties.apiVersion < VK_API_VERSION_1_3) {
        puts("UNSUPPORTED: selected device lacks VK_EXT_shader_tile_image with Vulkan 1.3");
        return 2;
    }
    VkPhysicalDeviceShaderTileImagePropertiesEXT tile_properties = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_SHADER_TILE_IMAGE_PROPERTIES_EXT
    };
    VkPhysicalDeviceProperties2 properties2 = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2, .pNext = &tile_properties
    };
    vkGetPhysicalDeviceProperties2(p->physical, &properties2);
    VkPhysicalDeviceShaderTileImageFeaturesEXT tile_features = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_SHADER_TILE_IMAGE_FEATURES_EXT
    };
    VkPhysicalDeviceVulkan13Features core_features = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_3_FEATURES,
        .pNext = &tile_features
    };
    VkPhysicalDeviceFeatures2 features = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2, .pNext = &core_features
    };
    vkGetPhysicalDeviceFeatures2(p->physical, &features);
    printf("dynamicRendering: %u\nshaderTileImageColorReadAccess: %u\n"
           "shaderTileImageDepthReadAccess: %u\nshaderTileImageStencilReadAccess: %u\n",
           core_features.dynamicRendering, tile_features.shaderTileImageColorReadAccess,
           tile_features.shaderTileImageDepthReadAccess, tile_features.shaderTileImageStencilReadAccess);
    printf("shaderTileImageCoherentReadAccelerated: %u (performance property, not a capability gate)\n"
           "shaderTileImageReadSampleFromPixelRateInvocation: %u\n"
           "shaderTileImageReadFromHelperInvocation: %u\n",
           tile_properties.shaderTileImageCoherentReadAccelerated,
           tile_properties.shaderTileImageReadSampleFromPixelRateInvocation,
           tile_properties.shaderTileImageReadFromHelperInvocation);
    if (!core_features.dynamicRendering || !tile_features.shaderTileImageColorReadAccess) {
        puts("UNSUPPORTED: coherent color test needs dynamicRendering and shaderTileImageColorReadAccess");
        return 2;
    }
    VkFormatProperties format;
    vkGetPhysicalDeviceFormatProperties(p->physical, VK_FORMAT_R8G8B8A8_UINT, &format);
    VkFormatFeatureFlags required = VK_FORMAT_FEATURE_COLOR_ATTACHMENT_BIT |
                                   VK_FORMAT_FEATURE_TRANSFER_SRC_BIT;
    printf("RGBA8_UINT_optimal_features: 0x%x\n", format.optimalTilingFeatures);
    if ((format.optimalTilingFeatures & required) != required) {
        puts("UNSUPPORTED: RGBA8_UINT needs optimal color attachment and transfer-source support");
        return 2;
    }
    vkGetPhysicalDeviceQueueFamilyProperties(p->physical, &count, NULL);
    VkQueueFamilyProperties *families = calloc(count ? count : 1, sizeof(*families));
    if (!families) return 1;
    vkGetPhysicalDeviceQueueFamilyProperties(p->physical, &count, families);
    p->family = UINT32_MAX;
    for (uint32_t i = 0; i < count; ++i)
        if (families[i].queueCount && (families[i].queueFlags & VK_QUEUE_GRAPHICS_BIT)) {
            p->family = i;
            break;
        }
    free(families);
    if (p->family == UINT32_MAX) {
        puts("UNSUPPORTED: no graphics queue");
        return 2;
    }
    float priority = 1.0f;
    VkDeviceQueueCreateInfo queue = {
        .sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO, .queueFamilyIndex = p->family,
        .queueCount = 1, .pQueuePriorities = &priority
    };
    tile_features = (VkPhysicalDeviceShaderTileImageFeaturesEXT){
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_SHADER_TILE_IMAGE_FEATURES_EXT,
        .shaderTileImageColorReadAccess = VK_TRUE
    };
    core_features = (VkPhysicalDeviceVulkan13Features){
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_3_FEATURES,
        .pNext = &tile_features, .dynamicRendering = VK_TRUE
    };
    const char *extension = VK_EXT_SHADER_TILE_IMAGE_EXTENSION_NAME;
    VkDeviceCreateInfo device = {
        .sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO, .pNext = &core_features,
        .queueCreateInfoCount = 1, .pQueueCreateInfos = &queue,
        .enabledExtensionCount = 1, .ppEnabledExtensionNames = &extension
    };
    TRY(p, vkCreateDevice(p->physical, &device, NULL, &p->device));
    vkGetDeviceQueue(p->device, p->family, 0, &p->queue);
    vkGetPhysicalDeviceMemoryProperties(p->physical, &p->memory);
    return 0;
}

static int memory_type(const Probe *p, uint32_t bits, VkMemoryPropertyFlags required,
                       VkMemoryPropertyFlags preferred)
{
    int fallback = -1;
    for (uint32_t i = 0; i < p->memory.memoryTypeCount; ++i) {
        VkMemoryPropertyFlags flags = p->memory.memoryTypes[i].propertyFlags;
        if (!(bits & (1u << i)) || (flags & required) != required) continue;
        if ((flags & preferred) == preferred) return (int)i;
        if (fallback < 0) fallback = (int)i;
    }
    return fallback;
}

static int resources(Probe *p)
{
    VkImageCreateInfo image = {
        .sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO, .imageType = VK_IMAGE_TYPE_2D,
        .format = VK_FORMAT_R8G8B8A8_UINT, .extent = {WIDTH, HEIGHT, 1},
        .mipLevels = 1, .arrayLayers = 1, .samples = VK_SAMPLE_COUNT_1_BIT,
        .tiling = VK_IMAGE_TILING_OPTIMAL,
        .usage = VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT,
        .sharingMode = VK_SHARING_MODE_EXCLUSIVE, .initialLayout = VK_IMAGE_LAYOUT_UNDEFINED
    };
    TRY(p, vkCreateImage(p->device, &image, NULL, &p->image));
    VkMemoryRequirements requirements;
    vkGetImageMemoryRequirements(p->device, p->image, &requirements);
    int index = memory_type(p, requirements.memoryTypeBits, 0, VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);
    if (index < 0) return 1;
    VkMemoryAllocateInfo allocate = {
        .sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
        .allocationSize = requirements.size, .memoryTypeIndex = (uint32_t)index
    };
    TRY(p, vkAllocateMemory(p->device, &allocate, NULL, &p->image_memory));
    TRY(p, vkBindImageMemory(p->device, p->image, p->image_memory, 0));
    VkImageViewCreateInfo view = {
        .sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO, .image = p->image,
        .viewType = VK_IMAGE_VIEW_TYPE_2D, .format = VK_FORMAT_R8G8B8A8_UINT,
        .subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1}
    };
    TRY(p, vkCreateImageView(p->device, &view, NULL, &p->view));
    VkBufferCreateInfo buffer = {
        .sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO, .size = PIXEL_BYTES,
        .usage = VK_BUFFER_USAGE_TRANSFER_DST_BIT, .sharingMode = VK_SHARING_MODE_EXCLUSIVE
    };
    TRY(p, vkCreateBuffer(p->device, &buffer, NULL, &p->readback));
    vkGetBufferMemoryRequirements(p->device, p->readback, &requirements);
    index = memory_type(p, requirements.memoryTypeBits, VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT,
                        VK_MEMORY_PROPERTY_HOST_COHERENT_BIT | VK_MEMORY_PROPERTY_HOST_CACHED_BIT);
    if (index < 0) {
        puts("UNSUPPORTED: no host-visible readback memory");
        return 2;
    }
    allocate.allocationSize = requirements.size;
    allocate.memoryTypeIndex = (uint32_t)index;
    TRY(p, vkAllocateMemory(p->device, &allocate, NULL, &p->readback_memory));
    TRY(p, vkBindBufferMemory(p->device, p->readback, p->readback_memory, 0));
    TRY(p, vkMapMemory(p->device, p->readback_memory, 0, VK_WHOLE_SIZE, 0, &p->mapped));
    VkCommandPoolCreateInfo pool = {
        .sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,
        .flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT, .queueFamilyIndex = p->family
    };
    TRY(p, vkCreateCommandPool(p->device, &pool, NULL, &p->pool));
    VkCommandBufferAllocateInfo command = {
        .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO, .commandPool = p->pool,
        .level = VK_COMMAND_BUFFER_LEVEL_PRIMARY, .commandBufferCount = 1
    };
    TRY(p, vkAllocateCommandBuffers(p->device, &command, &p->command));
    VkFenceCreateInfo fence = { .sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO };
    TRY(p, vkCreateFence(p->device, &fence, NULL, &p->fence));
    return 0;
}

static int shader(Probe *p, const char *directory, const char *name, VkShaderModule *module)
{
    char path[4096];
    int written = snprintf(path, sizeof(path), "%s/%s", directory, name);
    if (written < 0 || (size_t)written >= sizeof(path)) return 1;
    FILE *file = fopen(path, "rb");
    if (!file) { fprintf(stderr, "FAIL: opening %s: %s\n", path, strerror(errno)); return 1; }
    if (fseek(file, 0, SEEK_END)) { fclose(file); return 1; }
    long length = ftell(file);
    if (length < 20 || length > 1024 * 1024 || length % 4 || fseek(file, 0, SEEK_SET)) {
        fprintf(stderr, "FAIL: invalid shader size: %s\n", path);
        fclose(file);
        return 1;
    }
    uint32_t *words = malloc((size_t)length);
    if (!words) { fclose(file); return 1; }
    size_t bytes = fread(words, 1, (size_t)length, file);
    fclose(file);
    if (bytes != (size_t)length || words[0] != UINT32_C(0x07230203)) {
        fprintf(stderr, "FAIL: malformed SPIR-V file: %s\n", path);
        free(words);
        return 1;
    }
    VkShaderModuleCreateInfo info = {
        .sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,
        .codeSize = (size_t)length, .pCode = words
    };
    VkResult result = vkCreateShaderModule(p->device, &info, NULL, module);
    free(words);
    if (result != VK_SUCCESS) {
        fprintf(stderr, "FAIL: creating %s: %d\n", name, result);
        return 1;
    }
    return 0;
}

static int pipeline(Probe *p, const char *directory)
{
    if (shader(p, directory, "tile_image.vert.spv", &p->vertex) ||
        shader(p, directory, "tile_image.frag.spv", &p->fragment)) return 1;
    VkPushConstantRange push = {VK_SHADER_STAGE_VERTEX_BIT, 0, sizeof(uint32_t)};
    VkPipelineLayoutCreateInfo layout = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,
        .pushConstantRangeCount = 1, .pPushConstantRanges = &push
    };
    TRY(p, vkCreatePipelineLayout(p->device, &layout, NULL, &p->layout));
    VkPipelineShaderStageCreateInfo stages[2] = {
        {.sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
         .stage = VK_SHADER_STAGE_VERTEX_BIT, .module = p->vertex, .pName = "main"},
        {.sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
         .stage = VK_SHADER_STAGE_FRAGMENT_BIT, .module = p->fragment, .pName = "main"}
    };
    VkPipelineVertexInputStateCreateInfo vertex = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO
    };
    VkPipelineInputAssemblyStateCreateInfo assembly = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO,
        .topology = VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST
    };
    VkViewport viewport = {0, 0, WIDTH, HEIGHT, 0, 1};
    VkRect2D scissor = {{0, 0}, {WIDTH, HEIGHT}};
    VkPipelineViewportStateCreateInfo viewport_state = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO,
        .viewportCount = 1, .pViewports = &viewport, .scissorCount = 1, .pScissors = &scissor
    };
    VkPipelineRasterizationStateCreateInfo raster = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO,
        .polygonMode = VK_POLYGON_MODE_FILL, .cullMode = VK_CULL_MODE_NONE,
        .frontFace = VK_FRONT_FACE_COUNTER_CLOCKWISE, .lineWidth = 1.0f
    };
    VkPipelineMultisampleStateCreateInfo samples = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO,
        .rasterizationSamples = VK_SAMPLE_COUNT_1_BIT
    };
    VkPipelineColorBlendAttachmentState color = {
        .colorWriteMask = VK_COLOR_COMPONENT_R_BIT | VK_COLOR_COMPONENT_G_BIT |
                          VK_COLOR_COMPONENT_B_BIT | VK_COLOR_COMPONENT_A_BIT
    };
    VkPipelineColorBlendStateCreateInfo blending = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO,
        .attachmentCount = 1, .pAttachments = &color
    };
    VkFormat format = VK_FORMAT_R8G8B8A8_UINT;
    VkPipelineRenderingCreateInfo rendering = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_RENDERING_CREATE_INFO,
        .colorAttachmentCount = 1, .pColorAttachmentFormats = &format
    };
    VkGraphicsPipelineCreateInfo info = {
        .sType = VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO, .pNext = &rendering,
        .stageCount = 2, .pStages = stages, .pVertexInputState = &vertex,
        .pInputAssemblyState = &assembly, .pViewportState = &viewport_state,
        .pRasterizationState = &raster, .pMultisampleState = &samples,
        .pColorBlendState = &blending, .layout = p->layout,
        .renderPass = VK_NULL_HANDLE
    };
    TRY(p, vkCreateGraphicsPipelines(p->device, VK_NULL_HANDLE, 1, &info, NULL, &p->pipeline));
    return 0;
}

static int test(Probe *p, uint32_t draw_count, const char *name)
{
    TRY(p, vkResetFences(p->device, 1, &p->fence));
    TRY(p, vkResetCommandBuffer(p->command, 0));
    VkCommandBufferBeginInfo begin = {
        .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO,
        .flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT
    };
    TRY(p, vkBeginCommandBuffer(p->command, &begin));
    VkImageMemoryBarrier barrier = {
        .sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,
        .dstAccessMask = VK_ACCESS_COLOR_ATTACHMENT_READ_BIT | VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT,
        .oldLayout = VK_IMAGE_LAYOUT_UNDEFINED, .newLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,
        .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED, .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
        .image = p->image, .subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1}
    };
    vkCmdPipelineBarrier(p->command, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,
                         VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT | VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT,
                         0, 0, NULL, 0, NULL, 1, &barrier);
    VkRenderingAttachmentInfo attachment = {
        .sType = VK_STRUCTURE_TYPE_RENDERING_ATTACHMENT_INFO, .imageView = p->view,
        .imageLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,
        .loadOp = VK_ATTACHMENT_LOAD_OP_CLEAR, .storeOp = VK_ATTACHMENT_STORE_OP_STORE,
        .clearValue = {.color = {.uint32 = {0, 0, 0, 0}}}
    };
    VkRenderingInfo rendering = {
        .sType = VK_STRUCTURE_TYPE_RENDERING_INFO,
        .renderArea = {{0, 0}, {WIDTH, HEIGHT}}, .layerCount = 1,
        .colorAttachmentCount = 1, .pColorAttachments = &attachment
    };
    vkCmdBeginRendering(p->command, &rendering);
    vkCmdBindPipeline(p->command, VK_PIPELINE_BIND_POINT_GRAPHICS, p->pipeline);
    for (uint32_t draw = 0; draw < draw_count; ++draw) {
        uint32_t base = draw * TRIANGLES;
        vkCmdPushConstants(p->command, p->layout, VK_SHADER_STAGE_VERTEX_BIT, 0, sizeof(base), &base);
        vkCmdDraw(p->command, 3 * TRIANGLES, 1, 0, 0);
        // No inter-draw barrier: coherent tile reads must supply the ordering.
    }
    vkCmdEndRendering(p->command);
    barrier.srcAccessMask = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;
    barrier.dstAccessMask = VK_ACCESS_TRANSFER_READ_BIT;
    barrier.oldLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;
    barrier.newLayout = VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;
    vkCmdPipelineBarrier(p->command, VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT,
                         VK_PIPELINE_STAGE_TRANSFER_BIT, 0, 0, NULL, 0, NULL, 1, &barrier);
    VkBufferImageCopy copy = {
        .imageSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1},
        .imageExtent = {WIDTH, HEIGHT, 1}
    };
    vkCmdCopyImageToBuffer(p->command, p->image, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,
                           p->readback, 1, &copy);
    VkBufferMemoryBarrier readback = {
        .sType = VK_STRUCTURE_TYPE_BUFFER_MEMORY_BARRIER,
        .srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT, .dstAccessMask = VK_ACCESS_HOST_READ_BIT,
        .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED, .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
        .buffer = p->readback, .offset = 0, .size = VK_WHOLE_SIZE
    };
    vkCmdPipelineBarrier(p->command, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_HOST_BIT,
                         0, 0, NULL, 1, &readback, 0, NULL);
    TRY(p, vkEndCommandBuffer(p->command));
    VkSubmitInfo submit = {
        .sType = VK_STRUCTURE_TYPE_SUBMIT_INFO, .commandBufferCount = 1, .pCommandBuffers = &p->command
    };
    TRY(p, vkQueueSubmit(p->queue, 1, &submit, p->fence));
    VkResult waited = vkWaitForFences(p->device, 1, &p->fence, VK_TRUE, WAIT_NS);
    if (waited == VK_TIMEOUT) {
        fprintf(stderr, "FAIL: %s GPU wait exceeded 5 s; exiting without destroying in-flight resources\n", name);
        fflush(NULL);
        _Exit(1);
    }
    if (waited != VK_SUCCESS) {
        fprintf(stderr, "FAIL: %s fence wait returned %d\n", name, waited);
        return 1;
    }
    VkMappedMemoryRange invalidate = {
        .sType = VK_STRUCTURE_TYPE_MAPPED_MEMORY_RANGE, .memory = p->readback_memory,
        .offset = 0, .size = VK_WHOLE_SIZE
    };
    TRY(p, vkInvalidateMappedMemoryRanges(p->device, 1, &invalidate));
    uint8_t expected[4] = {0};
    for (uint32_t tag = 0; tag < draw_count * TRIANGLES; ++tag) {
        expected[0] = (uint8_t)(expected[0] + 1u);
        expected[1] = (uint8_t)(expected[1] * 3u + tag + 1u);
        expected[2] = (uint8_t)(expected[2] * 5u + tag + 1u);
        expected[3] = 255;
    }
    const uint8_t *pixels = p->mapped;
    uint32_t wrong = 0;
    for (uint32_t pixel = 0; pixel < WIDTH * HEIGHT; ++pixel) {
        const uint8_t *got = pixels + pixel * 4;
        if (memcmp(got, expected, sizeof(expected))) {
            if (wrong < 4)
                printf("%s mismatch (%u,%u): [%u,%u,%u,%u], expected [%u,%u,%u,%u]\n",
                       name, pixel % WIDTH, pixel / WIDTH, got[0], got[1], got[2], got[3],
                       expected[0], expected[1], expected[2], expected[3]);
            ++wrong;
        }
    }
    printf("%s: %s; draws=%u primitives=%u checked_pixels=%u wrong_pixels=%u expected=[%u,%u,%u,%u]\n",
           name, wrong ? "FAIL" : "PASS", draw_count, draw_count * TRIANGLES, WIDTH * HEIGHT,
           wrong, expected[0], expected[1], expected[2], expected[3]);
    return wrong != 0;
}

static void cleanup(Probe *p)
{
    if (p->device) {
        if (p->fence) vkDestroyFence(p->device, p->fence, NULL);
        if (p->pool) vkDestroyCommandPool(p->device, p->pool, NULL);
        if (p->pipeline) vkDestroyPipeline(p->device, p->pipeline, NULL);
        if (p->layout) vkDestroyPipelineLayout(p->device, p->layout, NULL);
        if (p->vertex) vkDestroyShaderModule(p->device, p->vertex, NULL);
        if (p->fragment) vkDestroyShaderModule(p->device, p->fragment, NULL);
        if (p->view) vkDestroyImageView(p->device, p->view, NULL);
        if (p->image) vkDestroyImage(p->device, p->image, NULL);
        if (p->image_memory) vkFreeMemory(p->device, p->image_memory, NULL);
        if (p->mapped) vkUnmapMemory(p->device, p->readback_memory);
        if (p->readback) vkDestroyBuffer(p->device, p->readback, NULL);
        if (p->readback_memory) vkFreeMemory(p->device, p->readback_memory, NULL);
        vkDestroyDevice(p->device, NULL);
    }
    if (p->messenger) p->destroy_messenger(p->instance, p->messenger, NULL);
    if (p->instance) vkDestroyInstance(p->instance, NULL);
}

int main(int argc, char **argv)
{
    const char *directory = ".";
    uint32_t device_index = 0;
    int validation = 0;
    for (int i = 1; i < argc; ++i) {
        if (!strcmp(argv[i], "--validation")) validation = 1;
        else if (!strcmp(argv[i], "--shader-dir") && i + 1 < argc) directory = argv[++i];
        else if (!strcmp(argv[i], "--device") && i + 1 < argc) {
            char *end;
            errno = 0;
            const char *text = argv[++i];
            unsigned long value = strtoul(text, &end, 10);
            if (errno || *end || end == text || text[0] == '-' || value > UINT32_MAX) {
                fputs("Invalid --device index\n", stderr);
                return 1;
            }
            device_index = (uint32_t)value;
        } else {
            fprintf(stderr, "Usage: %s [--shader-dir DIRECTORY] [--device INDEX] [--validation]\n", argv[0]);
            return strcmp(argv[i], "--help") != 0;
        }
    }
    setvbuf(stdout, NULL, _IOLBF, 0);
    puts("tile-image-ordering-probe v1; standalone system-driver test, not an iOS compatibility result");
    Probe probe = {0};
    atomic_init(&probe.validation_errors, 0);
    int result = initialize(&probe, device_index, validation);
    if (!result) result = resources(&probe);
    if (!result) result = pipeline(&probe, directory);
    if (!result) {
        int first = test(&probe, 1, "same_draw_overlap");
        int second = test(&probe, 2, "across_draws_overlap");
        result = first || second;
    }
    cleanup(&probe);
    unsigned validation_errors = atomic_load(&probe.validation_errors);
    printf("validation_errors: %u\n", validation_errors);
    if (validation_errors) result = 1;
    printf("result: %s\n", result == 0 ? "PASS" : result == 2 ? "UNSUPPORTED" : "FAIL");
    return result;
}
