/* Local fixture helpers. The codec owns a buffer for the two packed words per texel. */
typedef struct {
    VkBuffer buffer;
    VkDeviceMemory memory;
    uint32_t *words;
    VkDescriptorSetLayout set_layout;
    VkDescriptorPool pool;
    VkDescriptorSet set;
    VkPipelineLayout layout;
    VkPipeline pipeline;
} XrCodec;

static const uint32_t xr_seeds[][2] = {
    {0x1409ffe8, 0x40}, {0x09cbcaf8, 0x7f},
    {0x38410180, 0xc0}, {0x27f501f4, 0x11},
};
static const uint16_t xr_half[][4] = {
    {0xafe8, 0x3804, 0x3cdd, 0x3604}, {0xb71f, 0x39d2, 0x39f6, 0x38fc},
    {0x3c0c, 0xb901, 0x2000, 0x3b06}, {0x3804, 0xafe8, 0x3387, 0x3222},
};
static const uint32_t xr_expected[][2] = {
    {0x141a03ec, 0x60}, {0x09dbcefc, 0x9f},
    {0x38410584, 0xe0}, {0x280505f8, 0x31},
};

static XrCodec make_codec(VkDevice dev, const VkPhysicalDeviceMemoryProperties *mem_props,
                          VkImageView working, const char *shader) {
    XrCodec codec = {0};
    const VkBufferCreateInfo buffer_info = {
        .sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO, .size = 8 * PIXELS,
        .usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT, .sharingMode = VK_SHARING_MODE_EXCLUSIVE,
    };
    VK(vkCreateBuffer(dev, &buffer_info, NULL, &codec.buffer));
    VkMemoryRequirements need;
    vkGetBufferMemoryRequirements(dev, codec.buffer, &need);
    codec.memory = allocate(dev, mem_props, need, VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT);
    VK(vkBindBufferMemory(dev, codec.buffer, codec.memory, 0));
    void *mapped;
    VK(vkMapMemory(dev, codec.memory, 0, VK_WHOLE_SIZE, 0, &mapped));
    codec.words = mapped;
    for (unsigned i = 0; i < PIXELS; ++i) {
        memcpy(codec.words + i * 2, xr_seeds[i % 4], sizeof(xr_seeds[0]));
    }
    const VkMappedMemoryRange range = {
        .sType = VK_STRUCTURE_TYPE_MAPPED_MEMORY_RANGE,
        .memory = codec.memory, .size = VK_WHOLE_SIZE,
    };
    VK(vkFlushMappedMemoryRanges(dev, 1, &range));

    const VkDescriptorSetLayoutBinding bindings[] = {
        {0, VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, 1, VK_SHADER_STAGE_COMPUTE_BIT, NULL},
        {1, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 1, VK_SHADER_STAGE_COMPUTE_BIT, NULL},
    };
    const VkDescriptorSetLayoutCreateInfo set_info = {
        .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,
        .bindingCount = 2, .pBindings = bindings,
    };
    VK(vkCreateDescriptorSetLayout(dev, &set_info, NULL, &codec.set_layout));
    const VkDescriptorPoolSize sizes[] = {
        {VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, 1}, {VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 1},
    };
    const VkDescriptorPoolCreateInfo pool_info = {
        .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO,
        .maxSets = 1, .poolSizeCount = 2, .pPoolSizes = sizes,
    };
    VK(vkCreateDescriptorPool(dev, &pool_info, NULL, &codec.pool));
    const VkDescriptorSetAllocateInfo set_alloc = {
        .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO, .descriptorPool = codec.pool,
        .descriptorSetCount = 1, .pSetLayouts = &codec.set_layout,
    };
    VK(vkAllocateDescriptorSets(dev, &set_alloc, &codec.set));
    const VkDescriptorImageInfo image_desc = {.imageView = working, .imageLayout = VK_IMAGE_LAYOUT_GENERAL};
    const VkDescriptorBufferInfo buffer_desc = {.buffer = codec.buffer, .range = VK_WHOLE_SIZE};
    const VkWriteDescriptorSet writes[] = {
        {.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, .dstSet = codec.set,
         .dstBinding = 0, .descriptorCount = 1, .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE,
         .pImageInfo = &image_desc},
        {.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, .dstSet = codec.set,
         .dstBinding = 1, .descriptorCount = 1, .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,
         .pBufferInfo = &buffer_desc},
    };
    vkUpdateDescriptorSets(dev, 2, writes, 0, NULL);
    const VkPushConstantRange push = {VK_SHADER_STAGE_COMPUTE_BIT, 0, sizeof(uint32_t)};
    const VkPipelineLayoutCreateInfo layout_info = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,
        .setLayoutCount = 1, .pSetLayouts = &codec.set_layout,
        .pushConstantRangeCount = 1, .pPushConstantRanges = &push,
    };
    VK(vkCreatePipelineLayout(dev, &layout_info, NULL, &codec.layout));
    VkShaderModule compute = module(dev, shader);
    const VkComputePipelineCreateInfo info = {
        .sType = VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO, .layout = codec.layout,
        .stage = {.sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
                  .stage = VK_SHADER_STAGE_COMPUTE_BIT, .module = compute, .pName = "main"},
    };
    VK(vkCreateComputePipelines(dev, VK_NULL_HANDLE, 1, &info, NULL, &codec.pipeline));
    vkDestroyShaderModule(dev, compute, NULL);
    return codec;
}

static void record_codec(VkCommandBuffer cmd, const XrCodec *codec, uint32_t store_codes) {
    vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, codec->pipeline);
    vkCmdBindDescriptorSets(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, codec->layout, 0, 1,
                            &codec->set, 0, NULL);
    vkCmdPushConstants(cmd, codec->layout, VK_SHADER_STAGE_COMPUTE_BIT, 0,
                       sizeof(store_codes), &store_codes);
    vkCmdDispatch(cmd, (SIDE + 7) / 8, (SIDE + 7) / 8, 1);
}

static unsigned check_codes(VkDevice dev, const XrCodec *codec) {
    const VkMappedMemoryRange range = {
        .sType = VK_STRUCTURE_TYPE_MAPPED_MEMORY_RANGE,
        .memory = codec->memory, .size = VK_WHOLE_SIZE,
    };
    VK(vkInvalidateMappedMemoryRanges(dev, 1, &range));
    unsigned errors = 0;
    for (unsigned i = 0; i < PIXELS; ++i) {
        const uint32_t *got = codec->words + i * 2;
        if (memcmp(got, xr_expected[i % 4], sizeof(xr_expected[0])) != 0) {
            if (errors == 0) {
                fprintf(stderr, "packed texel %u got %08x %08x, expected %08x %08x\n",
                        i, got[0], got[1], xr_expected[i % 4][0], xr_expected[i % 4][1]);
            }
            ++errors;
        }
    }
    printf("checked_packed_texels=%u packed_mismatches=%u\n", PIXELS, errors);
    return errors;
}

static void destroy_codec(VkDevice dev, const XrCodec *codec) {
    vkUnmapMemory(dev, codec->memory);
    vkDestroyPipeline(dev, codec->pipeline, NULL);
    vkDestroyPipelineLayout(dev, codec->layout, NULL);
    vkDestroyDescriptorPool(dev, codec->pool, NULL);
    vkDestroyDescriptorSetLayout(dev, codec->set_layout, NULL);
    vkDestroyBuffer(dev, codec->buffer, NULL);
    vkFreeMemory(dev, codec->memory, NULL);
}
