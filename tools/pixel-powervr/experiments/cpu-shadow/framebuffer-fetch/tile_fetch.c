/* Coherent tile reads on the three-color attachment layout used by the XR probe.
 * The first and third attachments use FP16 working storage. This program never
 * imports or modifies an iOS image. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <vulkan/vulkan.h>

enum { SIDE = 16, PIXELS = SIDE * SIDE, COLORS = 3, READBACK = PIXELS * 20 };

static const VkFormat formats[COLORS] = {
    VK_FORMAT_R16G16B16A16_SFLOAT, VK_FORMAT_R16G16_SFLOAT,
    VK_FORMAT_R16G16B16A16_SFLOAT,
};
static const VkFormat depth_format = VK_FORMAT_D32_SFLOAT_S8_UINT;
static const uint32_t channels[COLORS] = {4, 2, 4};
static const VkDeviceSize offsets[COLORS] = {0, PIXELS * 8, PIXELS * 12};
static const VkClearValue clear[COLORS] = {
    {.color.float32 = {-0.125f, 0.5f, 1.25f, 0.25f}},
    {.color.float32 = {0.75f, -0.25f, 0.0f, 0.0f}},
    {.color.float32 = {2.0f, -0.5f, 0.125f, 0.25f}},
};
static const uint16_t expected[COLORS][4] = {
    {0xafe0, 0x3804, 0x3d08, 0x3600},
    {0x3a00, 0xb400},
    {0x4000, 0xb800, 0x3000, 0x3400},
};

typedef struct {
    VkImage image;
    VkDeviceMemory memory;
    VkImageView view;
} Attachment;

static void check(VkResult result, const char *operation) {
    if (result != VK_SUCCESS) {
        fprintf(stderr, "%s failed with VkResult %d\n", operation, result);
        exit(1);
    }
}

static void require(int ok, const char *message) {
    if (!ok) {
        fprintf(stderr, "%s\n", message);
        exit(1);
    }
}

#define VK(call) check((call), #call)

static VkShaderModule module(VkDevice dev, const char *path) {
    FILE *f = fopen(path, "rb");
    require(f != NULL, "cannot open shader");
    uint32_t words[4096];
    size_t bytes = fread(words, 1, sizeof(words), f);
    require(feof(f) && !ferror(f) && bytes >= 20 && bytes % 4 == 0 &&
            words[0] == 0x07230203, "invalid shader module");
    fclose(f);
    VkShaderModuleCreateInfo info = {
        .sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,
        .codeSize = bytes, .pCode = words,
    };
    VkShaderModule out;
    VK(vkCreateShaderModule(dev, &info, NULL, &out));
    return out;
}

static VkDeviceMemory allocate(VkDevice dev, const VkPhysicalDeviceMemoryProperties *props,
                               VkMemoryRequirements need, VkMemoryPropertyFlags flags) {
    for (uint32_t i = 0; i < props->memoryTypeCount; ++i) {
        if (!(need.memoryTypeBits & (1u << i)) ||
            (props->memoryTypes[i].propertyFlags & flags) != flags) {
            continue;
        }
        VkMemoryAllocateInfo info = {
            .sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
            .allocationSize = need.size, .memoryTypeIndex = i,
        };
        VkDeviceMemory memory;
        VK(vkAllocateMemory(dev, &info, NULL, &memory));
        return memory;
    }
    fprintf(stderr, "no memory type for flags %#x\n", flags);
    exit(1);
}

static Attachment make_attachment(VkDevice dev, const VkPhysicalDeviceMemoryProperties *props,
                                  VkFormat format, VkImageUsageFlags usage,
                                  VkImageAspectFlags aspects) {
    Attachment out;
    VkImageCreateInfo info = {
        .sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO,
        .imageType = VK_IMAGE_TYPE_2D, .format = format, .extent = {SIDE, SIDE, 1},
        .mipLevels = 1, .arrayLayers = 1, .samples = VK_SAMPLE_COUNT_1_BIT,
        .tiling = VK_IMAGE_TILING_OPTIMAL,
        .usage = usage,
        .sharingMode = VK_SHARING_MODE_EXCLUSIVE, .initialLayout = VK_IMAGE_LAYOUT_UNDEFINED,
    };
    VK(vkCreateImage(dev, &info, NULL, &out.image));
    VkMemoryRequirements req;
    vkGetImageMemoryRequirements(dev, out.image, &req);
    out.memory = allocate(dev, props, req, VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);
    VK(vkBindImageMemory(dev, out.image, out.memory, 0));
    VkImageViewCreateInfo view = {
        .sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO,
        .image = out.image, .viewType = VK_IMAGE_VIEW_TYPE_2D, .format = format,
        .subresourceRange = {aspects, 0, 1, 0, 1},
    };
    VK(vkCreateImageView(dev, &view, NULL, &out.view));
    return out;
}

static VkPipeline pipeline(VkDevice dev, VkPipelineLayout layout,
                           VkShaderModule vert, VkShaderModule frag) {
    const VkPipelineShaderStageCreateInfo stages[] = {
        { .sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
          .stage = VK_SHADER_STAGE_VERTEX_BIT, .module = vert, .pName = "main" },
        { .sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
          .stage = VK_SHADER_STAGE_FRAGMENT_BIT, .module = frag, .pName = "main" },
    };
    const VkPipelineVertexInputStateCreateInfo vertices = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO,
    };
    const VkPipelineInputAssemblyStateCreateInfo assembly = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO,
        .topology = VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST,
    };
    const VkViewport viewport = {0, 0, SIDE, SIDE, 0, 1};
    const VkRect2D scissor = {{0, 0}, {SIDE, SIDE}};
    const VkPipelineViewportStateCreateInfo view = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO,
        .viewportCount = 1, .pViewports = &viewport, .scissorCount = 1, .pScissors = &scissor,
    };
    const VkPipelineRasterizationStateCreateInfo raster = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO,
        .polygonMode = VK_POLYGON_MODE_FILL, .lineWidth = 1.0f,
    };
    const VkPipelineMultisampleStateCreateInfo samples = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO,
        .rasterizationSamples = VK_SAMPLE_COUNT_1_BIT,
    };
    const VkPipelineColorBlendAttachmentState write[COLORS] = {
        {.colorWriteMask = VK_COLOR_COMPONENT_R_BIT | VK_COLOR_COMPONENT_G_BIT |
                           VK_COLOR_COMPONENT_B_BIT | VK_COLOR_COMPONENT_A_BIT},
        {0}, {0},
    };
    const VkPipelineColorBlendStateCreateInfo blend = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO,
        .attachmentCount = COLORS, .pAttachments = write,
    };
    const VkStencilOpState stencil = {
        .failOp = VK_STENCIL_OP_KEEP, .passOp = VK_STENCIL_OP_KEEP,
        .depthFailOp = VK_STENCIL_OP_KEEP, .compareOp = VK_COMPARE_OP_EQUAL,
        .compareMask = 0xff, .reference = 3,
    };
    const VkPipelineDepthStencilStateCreateInfo tests = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_DEPTH_STENCIL_STATE_CREATE_INFO,
        .depthTestEnable = VK_TRUE, .depthCompareOp = VK_COMPARE_OP_LESS,
        .stencilTestEnable = VK_TRUE, .front = stencil, .back = stencil,
    };
    const VkPipelineRenderingCreateInfo render = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_RENDERING_CREATE_INFO,
        .colorAttachmentCount = COLORS, .pColorAttachmentFormats = formats,
        .depthAttachmentFormat = depth_format, .stencilAttachmentFormat = depth_format,
    };
    const VkGraphicsPipelineCreateInfo info = {
        .sType = VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO, .pNext = &render,
        .stageCount = 2, .pStages = stages, .pVertexInputState = &vertices,
        .pInputAssemblyState = &assembly, .pViewportState = &view,
        .pRasterizationState = &raster, .pMultisampleState = &samples,
        .pDepthStencilState = &tests, .pColorBlendState = &blend, .layout = layout,
    };
    VkPipeline out;
    VK(vkCreateGraphicsPipelines(dev, VK_NULL_HANDLE, 1, &info, NULL, &out));
    return out;
}

int main(int argc, char **argv) {
    require(argc == 3, "usage: tile_fetch feedback.vert.spv feedback.frag.spv");
    const VkApplicationInfo application = {
        .sType = VK_STRUCTURE_TYPE_APPLICATION_INFO, .apiVersion = VK_API_VERSION_1_3,
    };
    const VkInstanceCreateInfo instance_info = {
        .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO, .pApplicationInfo = &application,
    };
    VkInstance instance;
    VK(vkCreateInstance(&instance_info, NULL, &instance));
    uint32_t count = 0;
    VK(vkEnumeratePhysicalDevices(instance, &count, NULL));
    require(count == 1, "run the probe with one visible Vulkan device");
    VkPhysicalDevice gpu;
    VK(vkEnumeratePhysicalDevices(instance, &count, &gpu));
    VkPhysicalDeviceShaderTileImagePropertiesEXT tile_props = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_SHADER_TILE_IMAGE_PROPERTIES_EXT,
    };
    VkPhysicalDeviceProperties2 props = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2, .pNext = &tile_props,
    };
    vkGetPhysicalDeviceProperties2(gpu, &props);
    VkPhysicalDeviceShaderTileImageFeaturesEXT tile = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_SHADER_TILE_IMAGE_FEATURES_EXT,
    };
    VkPhysicalDeviceVulkan13Features v13 = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_3_FEATURES, .pNext = &tile,
    };
    VkPhysicalDeviceFeatures2 caps = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2, .pNext = &v13,
    };
    vkGetPhysicalDeviceFeatures2(gpu, &caps);
    printf("device=%s coherentTileReadAccelerated=%u colorTileRead=%u independentBlend=%u\n",
           props.properties.deviceName, tile_props.shaderTileImageCoherentReadAccelerated,
           tile.shaderTileImageColorReadAccess, caps.features.independentBlend);
    require(tile.shaderTileImageColorReadAccess && v13.dynamicRendering &&
            caps.features.independentBlend, "required Vulkan features unavailable");

    vkGetPhysicalDeviceQueueFamilyProperties(gpu, &count, NULL);
    VkQueueFamilyProperties *queues = calloc(count, sizeof(*queues));
    require(queues != NULL, "queue allocation failed");
    vkGetPhysicalDeviceQueueFamilyProperties(gpu, &count, queues);
    uint32_t family = 0;
    while (family < count && !(queues[family].queueFlags & VK_QUEUE_GRAPHICS_BIT)) {
        ++family;
    }
    require(family < count, "no graphics queue");
    free(queues);
    const float priority = 1.0f;
    const VkDeviceQueueCreateInfo queue_info = {
        .sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
        .queueFamilyIndex = family, .queueCount = 1, .pQueuePriorities = &priority,
    };
    VkPhysicalDeviceShaderTileImageFeaturesEXT enable_tile = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_SHADER_TILE_IMAGE_FEATURES_EXT,
        .shaderTileImageColorReadAccess = VK_TRUE,
    };
    VkPhysicalDeviceVulkan13Features enable_render = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_3_FEATURES,
        .pNext = &enable_tile, .dynamicRendering = VK_TRUE,
    };
    const VkPhysicalDeviceFeatures enable_base = {.independentBlend = VK_TRUE};
    const char *extensions[] = {VK_EXT_SHADER_TILE_IMAGE_EXTENSION_NAME};
    const VkDeviceCreateInfo device_info = {
        .sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO, .pNext = &enable_render,
        .queueCreateInfoCount = 1, .pQueueCreateInfos = &queue_info,
        .enabledExtensionCount = 1, .ppEnabledExtensionNames = extensions,
        .pEnabledFeatures = &enable_base,
    };
    VkDevice dev;
    VK(vkCreateDevice(gpu, &device_info, NULL, &dev));
    VkQueue queue;
    vkGetDeviceQueue(dev, family, 0, &queue);
    PFN_vkCmdBeginRendering begin = (PFN_vkCmdBeginRendering)vkGetDeviceProcAddr(dev, "vkCmdBeginRendering");
    PFN_vkCmdEndRendering end = (PFN_vkCmdEndRendering)vkGetDeviceProcAddr(dev, "vkCmdEndRendering");
    require(begin && end, "dynamic rendering entry points unavailable");

    VkPhysicalDeviceMemoryProperties mem_props;
    vkGetPhysicalDeviceMemoryProperties(gpu, &mem_props);
    Attachment images[COLORS];
    VkRenderingAttachmentInfo bindings[COLORS];
    VkImageMemoryBarrier transitions[COLORS + 1];
    for (unsigned i = 0; i < COLORS; ++i) {
        images[i] = make_attachment(dev, &mem_props, formats[i],
            VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT | VK_IMAGE_USAGE_INPUT_ATTACHMENT_BIT |
            VK_IMAGE_USAGE_TRANSFER_SRC_BIT, VK_IMAGE_ASPECT_COLOR_BIT);
        bindings[i] = (VkRenderingAttachmentInfo) {
            .sType = VK_STRUCTURE_TYPE_RENDERING_ATTACHMENT_INFO,
            .imageView = images[i].view, .imageLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,
            .loadOp = VK_ATTACHMENT_LOAD_OP_CLEAR, .storeOp = VK_ATTACHMENT_STORE_OP_STORE,
            .clearValue = clear[i],
        };
        transitions[i] = (VkImageMemoryBarrier) {
            .sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,
            .dstAccessMask = VK_ACCESS_COLOR_ATTACHMENT_READ_BIT | VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT,
            .oldLayout = VK_IMAGE_LAYOUT_UNDEFINED, .newLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,
            .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED, .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
            .image = images[i].image, .subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1},
        };
    }
    const VkImageAspectFlags depth_aspects = VK_IMAGE_ASPECT_DEPTH_BIT | VK_IMAGE_ASPECT_STENCIL_BIT;
    Attachment depth = make_attachment(dev, &mem_props, depth_format,
        VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT, depth_aspects);
    const VkRenderingAttachmentInfo depth_binding = {
        .sType = VK_STRUCTURE_TYPE_RENDERING_ATTACHMENT_INFO, .imageView = depth.view,
        .imageLayout = VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL,
        .loadOp = VK_ATTACHMENT_LOAD_OP_CLEAR, .storeOp = VK_ATTACHMENT_STORE_OP_DONT_CARE,
        .clearValue.depthStencil = {0.75f, 3},
    };
    transitions[COLORS] = (VkImageMemoryBarrier) {
        .sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,
        .dstAccessMask = VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_READ_BIT |
                         VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_WRITE_BIT,
        .oldLayout = VK_IMAGE_LAYOUT_UNDEFINED,
        .newLayout = VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL,
        .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED, .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
        .image = depth.image, .subresourceRange = {depth_aspects, 0, 1, 0, 1},
    };
    const VkBufferCreateInfo buffer_info = {
        .sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO, .size = READBACK,
        .usage = VK_BUFFER_USAGE_TRANSFER_DST_BIT, .sharingMode = VK_SHARING_MODE_EXCLUSIVE,
    };
    VkBuffer buffer;
    VK(vkCreateBuffer(dev, &buffer_info, NULL, &buffer));
    VkMemoryRequirements req;
    vkGetBufferMemoryRequirements(dev, buffer, &req);
    VkDeviceMemory buf_mem = allocate(dev, &mem_props, req, VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT);
    VK(vkBindBufferMemory(dev, buffer, buf_mem, 0));

    VkShaderModule vert = module(dev, argv[1]), frag = module(dev, argv[2]);
    const VkPipelineLayoutCreateInfo layout_info = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,
    };
    VkPipelineLayout layout;
    VK(vkCreatePipelineLayout(dev, &layout_info, NULL, &layout));
    VkPipeline graphics = pipeline(dev, layout, vert, frag);

    const VkCommandPoolCreateInfo pool_info = {
        .sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO, .queueFamilyIndex = family,
    };
    VkCommandPool pool;
    VK(vkCreateCommandPool(dev, &pool_info, NULL, &pool));
    const VkCommandBufferAllocateInfo cmd_info = {
        .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO, .commandPool = pool,
        .level = VK_COMMAND_BUFFER_LEVEL_PRIMARY, .commandBufferCount = 1,
    };
    VkCommandBuffer cmd;
    VK(vkAllocateCommandBuffers(dev, &cmd_info, &cmd));
    const VkCommandBufferBeginInfo cmd_begin = {.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};
    VK(vkBeginCommandBuffer(cmd, &cmd_begin));
    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,
                         VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT |
                         VK_PIPELINE_STAGE_EARLY_FRAGMENT_TESTS_BIT |
                         VK_PIPELINE_STAGE_LATE_FRAGMENT_TESTS_BIT,
                         0, 0, NULL, 0, NULL, COLORS + 1, transitions);
    const VkRenderingInfo render = {
        .sType = VK_STRUCTURE_TYPE_RENDERING_INFO, .renderArea = {{0, 0}, {SIDE, SIDE}},
        .layerCount = 1, .colorAttachmentCount = COLORS, .pColorAttachments = bindings,
        .pDepthAttachment = &depth_binding, .pStencilAttachment = &depth_binding,
    };
    begin(cmd, &render);
    vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_GRAPHICS, graphics);
    // Two overlapping full-screen primitives per draw, two draws and no in-pass barriers.
    vkCmdDraw(cmd, 3, 2, 0, 0);
    vkCmdDraw(cmd, 3, 2, 0, 0);
    // The depth test must discard both of these overlapping primitives.
    vkCmdDraw(cmd, 3, 2, 0, 2);
    end(cmd);
    for (unsigned i = 0; i < COLORS; ++i) {
        transitions[i].srcAccessMask = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;
        transitions[i].dstAccessMask = VK_ACCESS_TRANSFER_READ_BIT;
        transitions[i].oldLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;
        transitions[i].newLayout = VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;
    }
    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT,
                         VK_PIPELINE_STAGE_TRANSFER_BIT, 0, 0, NULL, 0, NULL, COLORS, transitions);
    for (unsigned i = 0; i < COLORS; ++i) {
        VkBufferImageCopy region = {
            .bufferOffset = offsets[i], .imageSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1},
            .imageExtent = {SIDE, SIDE, 1},
        };
        vkCmdCopyImageToBuffer(cmd, images[i].image, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,
                               buffer, 1, &region);
    }
    const VkMemoryBarrier to_host = {
        .sType = VK_STRUCTURE_TYPE_MEMORY_BARRIER,
        .srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT, .dstAccessMask = VK_ACCESS_HOST_READ_BIT,
    };
    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_HOST_BIT,
                         0, 1, &to_host, 0, NULL, 0, NULL);
    VK(vkEndCommandBuffer(cmd));
    const VkSubmitInfo submit = {
        .sType = VK_STRUCTURE_TYPE_SUBMIT_INFO, .commandBufferCount = 1, .pCommandBuffers = &cmd,
    };
    VK(vkQueueSubmit(queue, 1, &submit, VK_NULL_HANDLE));
    VK(vkQueueWaitIdle(queue));

    void *mapped;
    VK(vkMapMemory(dev, buf_mem, 0, VK_WHOLE_SIZE, 0, &mapped));
    const VkMappedMemoryRange range = {
        .sType = VK_STRUCTURE_TYPE_MAPPED_MEMORY_RANGE, .memory = buf_mem, .size = VK_WHOLE_SIZE,
    };
    VK(vkInvalidateMappedMemoryRanges(dev, 1, &range));
    unsigned errors = 0;
    for (unsigned i = 0; i < COLORS; ++i) {
        const uint16_t *p = (const uint16_t *)((const uint8_t *)mapped + offsets[i]);
        for (unsigned j = 0; j < PIXELS; ++j) {
            if (memcmp(p + j * channels[i], expected[i], channels[i] * sizeof(*p)) != 0) {
                if (errors == 0) {
                    fprintf(stderr, "attachment %u pixel %u got", i, j);
                    for (unsigned k = 0; k < channels[i]; ++k) {
                        fprintf(stderr, " %04x", p[j * channels[i] + k]);
                    }
                    fprintf(stderr, "\n");
                }
                ++errors;
            }
        }
    }
    printf("checked_pixels=%u attachments=%u mismatches=%u\n", PIXELS, COLORS, errors);

    vkUnmapMemory(dev, buf_mem);
    vkDestroyCommandPool(dev, pool, NULL);
    vkDestroyPipeline(dev, graphics, NULL);
    vkDestroyPipelineLayout(dev, layout, NULL);
    vkDestroyShaderModule(dev, frag, NULL);
    vkDestroyShaderModule(dev, vert, NULL);
    vkDestroyBuffer(dev, buffer, NULL);
    vkFreeMemory(dev, buf_mem, NULL);
    for (unsigned i = 0; i < COLORS; ++i) {
        vkDestroyImageView(dev, images[i].view, NULL);
        vkDestroyImage(dev, images[i].image, NULL);
        vkFreeMemory(dev, images[i].memory, NULL);
    }
    vkDestroyImageView(dev, depth.view, NULL);
    vkDestroyImage(dev, depth.image, NULL);
    vkFreeMemory(dev, depth.memory, NULL);
    vkDestroyDevice(dev, NULL);
    vkDestroyInstance(instance, NULL);
    return errors ? 1 : 0;
}
