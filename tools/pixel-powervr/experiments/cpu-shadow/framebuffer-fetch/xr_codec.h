/* The codec keeps the packed words in the same typed image as the renderer. */
typedef struct {
    Attachment packed;
    VkBuffer buffer;
    VkDeviceMemory memory;
    uint32_t *words;
    VkDescriptorSetLayout set_layout;
    VkDescriptorPool pool;
    VkDescriptorSet set;
    VkPipelineLayout layout;
    VkPipeline load;
    VkPipeline store;
} XrCodec;

static const uint32_t xr_seeds[][2] = {
    {0x1409ffff, 0x40}, {0x09cbcaf8, 0x7f},
    {0x38410180, 0xc0}, {0x27f501f4, 0x11},
};
static const uint16_t xr_half[][4] = {
    {0xafe8, 0x3804, 0x3d09, 0x3604}, {0xb71f, 0x39d2, 0x39f6, 0x38fc},
    {0x3c0c, 0xb901, 0x2000, 0x3b06}, {0x3804, 0xafe8, 0x3387, 0x3222},
};
static const uint32_t xr_expected[][2] = {
    {0x141a03ff, 0x60}, {0x09dbcefc, 0x9f},
    {0x38410584, 0xe0}, {0x280505f8, 0x31},
};

static VkPipeline codec_pipeline(VkDevice dev, VkPipelineLayout layout, const char *shader) {
    VkShaderModule compute = module(dev, shader);
    const VkComputePipelineCreateInfo info = {
        .sType = VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO, .layout = layout,
        .stage = {.sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
                  .stage = VK_SHADER_STAGE_COMPUTE_BIT, .module = compute, .pName = "main"},
    };
    VkPipeline pipeline;
    VK(vkCreateComputePipelines(dev, VK_NULL_HANDLE, 1, &info, NULL, &pipeline));
    vkDestroyShaderModule(dev, compute, NULL);
    return pipeline;
}

static XrCodec make_codec(VkDevice dev, const VkPhysicalDeviceMemoryProperties *mem_props,
                          VkImageView working, const char *load, const char *store) {
    XrCodec codec = {0};
    codec.packed = make_attachment(dev, mem_props, VK_FORMAT_R32G32_UINT,
        VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT,
        VK_IMAGE_ASPECT_COLOR_BIT);
    const VkBufferCreateInfo buffer_info = {
        .sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO, .size = 8 * PIXELS,
        .usage = VK_BUFFER_USAGE_TRANSFER_SRC_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT,
        .sharingMode = VK_SHARING_MODE_EXCLUSIVE,
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
        {1, VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, 1, VK_SHADER_STAGE_COMPUTE_BIT, NULL},
    };
    const VkDescriptorSetLayoutCreateInfo set_info = {
        .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,
        .bindingCount = 2, .pBindings = bindings,
    };
    VK(vkCreateDescriptorSetLayout(dev, &set_info, NULL, &codec.set_layout));
    const VkDescriptorPoolSize size = {VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, 2};
    const VkDescriptorPoolCreateInfo pool_info = {
        .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO,
        .maxSets = 1, .poolSizeCount = 1, .pPoolSizes = &size,
    };
    VK(vkCreateDescriptorPool(dev, &pool_info, NULL, &codec.pool));
    const VkDescriptorSetAllocateInfo set_alloc = {
        .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO, .descriptorPool = codec.pool,
        .descriptorSetCount = 1, .pSetLayouts = &codec.set_layout,
    };
    VK(vkAllocateDescriptorSets(dev, &set_alloc, &codec.set));
    const VkDescriptorImageInfo image_desc = {.imageView = working, .imageLayout = VK_IMAGE_LAYOUT_GENERAL};
    const VkDescriptorImageInfo packed_desc = {
        .imageView = codec.packed.view, .imageLayout = VK_IMAGE_LAYOUT_GENERAL,
    };
    const VkWriteDescriptorSet writes[] = {
        {.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, .dstSet = codec.set,
         .dstBinding = 0, .descriptorCount = 1, .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE,
         .pImageInfo = &packed_desc},
        {.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, .dstSet = codec.set,
         .dstBinding = 1, .descriptorCount = 1, .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE,
         .pImageInfo = &image_desc},
    };
    vkUpdateDescriptorSets(dev, 2, writes, 0, NULL);
    const VkPushConstantRange push = {VK_SHADER_STAGE_COMPUTE_BIT, 0, sizeof(uint32_t)};
    const VkPipelineLayoutCreateInfo layout_info = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,
        .setLayoutCount = 1, .pSetLayouts = &codec.set_layout,
        .pushConstantRangeCount = store == NULL, .pPushConstantRanges = &push,
    };
    VK(vkCreatePipelineLayout(dev, &layout_info, NULL, &codec.layout));
    codec.load = codec_pipeline(dev, codec.layout, load);
    codec.store = store ? codec_pipeline(dev, codec.layout, store) : codec.load;
    return codec;
}

static const VkBufferImageCopy packed_region = {
    .imageSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1},
    .imageExtent = {SIDE, SIDE, 1},
};

static VkImageMemoryBarrier packed_transition(const XrCodec *codec, VkImageLayout old_layout,
    VkImageLayout new_layout, VkAccessFlags src_access, VkAccessFlags dst_access) {
    return (VkImageMemoryBarrier) {
        .sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,
        .srcAccessMask = src_access, .dstAccessMask = dst_access,
        .oldLayout = old_layout, .newLayout = new_layout,
        .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED, .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
        .image = codec->packed.image, .subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1},
    };
}

static void record_packed_upload(VkCommandBuffer cmd, const XrCodec *codec,
                                 VkImageMemoryBarrier working) {
    VkImageMemoryBarrier prepare = packed_transition(codec, VK_IMAGE_LAYOUT_UNDEFINED,
        VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 0, VK_ACCESS_TRANSFER_WRITE_BIT);
    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT,
                         0, 0, NULL, 0, NULL, 1, &prepare);
    vkCmdCopyBufferToImage(cmd, codec->buffer, codec->packed.image,
                           VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 1, &packed_region);
    VkImageMemoryBarrier ready[] = {
        working, packed_transition(codec, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
            VK_IMAGE_LAYOUT_GENERAL, VK_ACCESS_TRANSFER_WRITE_BIT, VK_ACCESS_SHADER_READ_BIT),
    };
    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
                         0, 0, NULL, 0, NULL, 2, ready);
}

static void record_packed_readback(VkCommandBuffer cmd, const XrCodec *codec) {
    VkImageMemoryBarrier ready = packed_transition(codec, VK_IMAGE_LAYOUT_GENERAL,
        VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, VK_ACCESS_SHADER_WRITE_BIT, VK_ACCESS_TRANSFER_READ_BIT);
    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT,
                         0, 0, NULL, 0, NULL, 1, &ready);
    vkCmdCopyImageToBuffer(cmd, codec->packed.image, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,
                           codec->buffer, 1, &packed_region);
}

static void record_codec(VkCommandBuffer cmd, const XrCodec *codec, uint32_t store_codes) {
    vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, store_codes ? codec->store : codec->load);
    vkCmdBindDescriptorSets(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, codec->layout, 0, 1,
                            &codec->set, 0, NULL);
    if (codec->load == codec->store) {
        vkCmdPushConstants(cmd, codec->layout, VK_SHADER_STAGE_COMPUTE_BIT, 0,
                           sizeof(store_codes), &store_codes);
    }
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
    if (codec->load != codec->store) {
        vkDestroyPipeline(dev, codec->store, NULL);
    }
    vkDestroyPipeline(dev, codec->load, NULL);
    vkDestroyPipelineLayout(dev, codec->layout, NULL);
    vkDestroyDescriptorPool(dev, codec->pool, NULL);
    vkDestroyDescriptorSetLayout(dev, codec->set_layout, NULL);
    vkDestroyImageView(dev, codec->packed.view, NULL);
    vkDestroyImage(dev, codec->packed.image, NULL);
    vkFreeMemory(dev, codec->packed.memory, NULL);
    vkDestroyBuffer(dev, codec->buffer, NULL);
    vkFreeMemory(dev, codec->memory, NULL);
}
