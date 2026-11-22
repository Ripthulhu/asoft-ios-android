/*
 * The GPU check before iOS 26 and watchOS are downloaded (GpuCheck.java): can this phone's Vulkan driver
 * run reims-vgpu + metal2vulkan as the S25 Ultra's Turnip does? It opens the device, reads what it has,
 * and runs what the guest's GPU work rests on:
 *   - a compute dispatch (Metal's kernels become compute shaders),
 *   - a render pass with a draw (Metal's render passes),
 *   - a buffer over host memory (VK_EXT_external_memory_host: reims hands the guest's RAM to the GPU
 *     without a copy; with Turnip that is the KGSL host-pointer import),
 *   - a sparse buffer bound from pieces of a host import, scattered and out of order (the 256 KiB gather
 *     that keeps a long run under Android's 65,530 mappings, APK-PLAN 6.26),
 *   - (recommended) a sparse LINEAR image bound the same way (heap textures; shadowed without it).
 * The host memory of those two tests is a shared memfd mapping whose descriptor stays open, as the engine's
 * guest RAM is (old KGSL refuses such a pointer; an anonymous mapping would pass on those phones).
 * After the tests, on the app's Turnip only, a log-only diagnostic (kgsl_probe) imports 256 KiB four ways
 * straight through KGSL's ioctl and logs which the kernel takes, with errno; it never changes the result.
 * It runs in its own process (GpuCheckService, :gpucheck): a driver that crashes takes only that one.
 * Every line goes to the log at once ("key: value"), so a crash leaves what came before it; the last
 * line is "result: pass" or "result: fail".
 *
 * mode 0: the Vulkan loader at @loader (the app's Khronos loader, which takes Turnip's ICD from
 * VK_DRIVER_FILES); mode 1: the system's own loader and driver (libvulkan.so), for the log only.
 */
#define VK_NO_PROTOTYPES
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <jni.h>
#include <pthread.h>
#include <sched.h>
#include <signal.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/syscall.h>
#include <sys/utsname.h>
#include <unistd.h>
#include <vulkan/vulkan.h>

#include "gpucheck-spv.h"

static FILE *out;
static int failed;
static char missing[4096];

static void say(const char *fmt, ...)
{
    va_list a;
    va_start(a, fmt);
    vfprintf(out, fmt, a);
    va_end(a);
    fputc('\n', out);
    fflush(out);
}

/* a requirement the phone lacks: into the "missing:" line and the result */
static void lack(const char *what)
{
    failed = 1;
    say("lacks: %s", what);
    size_t n = strlen(missing);
    snprintf(missing + n, sizeof missing - n, "%s%s", n ? ", " : "", what);
}

static PFN_vkGetInstanceProcAddr gipa;
static PFN_vkGetDeviceProcAddr gdpa;
static VkInstance inst;
static VkDevice dev;

#define IFN(name) PFN_##name name = (PFN_##name)gipa(inst, #name)
#define DFN(name) PFN_##name name = (PFN_##name)gdpa(dev, #name)
#define TRY(what, x) do { VkResult r_ = (x); if (r_ != VK_SUCCESS) { say("error: %s: VkResult %d", what, r_); return r_; } } while (0)

static int has_ext(const VkExtensionProperties *e, uint32_t n, const char *name)
{
    for (uint32_t i = 0; i < n; i++) {
        if (!strcmp(e[i].extensionName, name)) {
            return 1;
        }
    }
    return 0;
}

/* -- what the device runs on --------------------------------------------------------------------- */

static VkPhysicalDevice pd;
static VkPhysicalDeviceMemoryProperties mp;
static uint32_t gfx_family = UINT32_MAX, sparse_family = UINT32_MAX;
static VkQueue gq, sq;
static VkCommandPool pool;
static VkFence fence;

static uint32_t host_type(uint32_t bits)
{
    for (uint32_t t = 0; t < mp.memoryTypeCount; t++) {
        VkMemoryPropertyFlags f = mp.memoryTypes[t].propertyFlags;
        if ((bits & (1u << t)) && (f & VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT) && (f & VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)) {
            return t;
        }
    }
    return UINT32_MAX;
}

static VkResult plain_buffer(VkDeviceSize size, VkBufferUsageFlags use, VkBuffer *b, VkDeviceMemory *m, void **map)
{
    DFN(vkCreateBuffer);
    DFN(vkGetBufferMemoryRequirements);
    DFN(vkAllocateMemory);
    DFN(vkBindBufferMemory);
    DFN(vkMapMemory);
    VkBufferCreateInfo bci = {.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO, .size = size, .usage = use};
    TRY("vkCreateBuffer", vkCreateBuffer(dev, &bci, NULL, b));
    VkMemoryRequirements r;
    vkGetBufferMemoryRequirements(dev, *b, &r);
    VkMemoryAllocateInfo ai = {.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO, .allocationSize = r.size,
                               .memoryTypeIndex = host_type(r.memoryTypeBits)};
    if (ai.memoryTypeIndex == UINT32_MAX) {
        say("error: no host-visible coherent memory for a buffer");
        return VK_ERROR_FEATURE_NOT_PRESENT;
    }
    TRY("vkAllocateMemory", vkAllocateMemory(dev, &ai, NULL, m));
    TRY("vkBindBufferMemory", vkBindBufferMemory(dev, *b, *m, 0));
    TRY("vkMapMemory", vkMapMemory(dev, *m, 0, size, 0, map));
    return VK_SUCCESS;
}

static VkCommandBuffer begin(void)
{
    DFN(vkAllocateCommandBuffers);
    DFN(vkBeginCommandBuffer);
    VkCommandBufferAllocateInfo ai = {.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO, .commandPool = pool,
                                      .level = VK_COMMAND_BUFFER_LEVEL_PRIMARY, .commandBufferCount = 1};
    VkCommandBuffer cb = VK_NULL_HANDLE;
    if (vkAllocateCommandBuffers(dev, &ai, &cb) != VK_SUCCESS) {
        return VK_NULL_HANDLE;
    }
    VkCommandBufferBeginInfo bi = {.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO,
                                   .flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT};
    vkBeginCommandBuffer(cb, &bi);
    return cb;
}

static VkResult submit(VkCommandBuffer cb, const char *what)
{
    DFN(vkEndCommandBuffer);
    DFN(vkQueueSubmit);
    DFN(vkWaitForFences);
    DFN(vkResetFences);
    TRY(what, vkEndCommandBuffer(cb));
    VkSubmitInfo si = {.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO, .commandBufferCount = 1, .pCommandBuffers = &cb};
    vkResetFences(dev, 1, &fence);
    TRY(what, vkQueueSubmit(gq, 1, &si, fence));
    TRY(what, vkWaitForFences(dev, 1, &fence, VK_TRUE, 10000000000ull));
    return VK_SUCCESS;
}

static VkShaderModule shader(const uint32_t *code, size_t bytes)
{
    DFN(vkCreateShaderModule);
    VkShaderModuleCreateInfo ci = {.sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO, .codeSize = bytes, .pCode = code};
    VkShaderModule m = VK_NULL_HANDLE;
    VkResult r = vkCreateShaderModule(dev, &ci, NULL, &m);
    if (r != VK_SUCCESS) {
        say("error: vkCreateShaderModule: VkResult %d", r);
    }
    return m;
}

/* -- compute: out[i] = 3i + 1 into @buf (a plain buffer, or one over host memory) ----------------- */

static VkResult compute_into(VkBuffer buf, uint32_t n)
{
    DFN(vkCreateDescriptorSetLayout);
    DFN(vkCreatePipelineLayout);
    DFN(vkCreateComputePipelines);
    DFN(vkCreateDescriptorPool);
    DFN(vkAllocateDescriptorSets);
    DFN(vkUpdateDescriptorSets);
    DFN(vkCmdBindPipeline);
    DFN(vkCmdBindDescriptorSets);
    DFN(vkCmdDispatch);
    DFN(vkCmdPipelineBarrier);
    VkDescriptorSetLayoutBinding b = {.binding = 0, .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, .descriptorCount = 1,
                                      .stageFlags = VK_SHADER_STAGE_COMPUTE_BIT};
    VkDescriptorSetLayoutCreateInfo lci = {.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO, .bindingCount = 1, .pBindings = &b};
    VkDescriptorSetLayout dsl;
    TRY("vkCreateDescriptorSetLayout", vkCreateDescriptorSetLayout(dev, &lci, NULL, &dsl));
    VkPipelineLayoutCreateInfo pli = {.sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO, .setLayoutCount = 1, .pSetLayouts = &dsl};
    VkPipelineLayout pl;
    TRY("vkCreatePipelineLayout", vkCreatePipelineLayout(dev, &pli, NULL, &pl));
    VkShaderModule m = shader(spv_comp, sizeof spv_comp);
    if (!m) {
        return VK_ERROR_INITIALIZATION_FAILED;
    }
    VkComputePipelineCreateInfo cpi = {.sType = VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO, .layout = pl,
                                       .stage = {.sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
                                                 .stage = VK_SHADER_STAGE_COMPUTE_BIT, .module = m, .pName = "main"}};
    VkPipeline p;
    TRY("vkCreateComputePipelines", vkCreateComputePipelines(dev, VK_NULL_HANDLE, 1, &cpi, NULL, &p));
    VkDescriptorPoolSize ps = {.type = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, .descriptorCount = 1};
    VkDescriptorPoolCreateInfo dpi = {.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO, .maxSets = 1, .poolSizeCount = 1, .pPoolSizes = &ps};
    VkDescriptorPool dp;
    TRY("vkCreateDescriptorPool", vkCreateDescriptorPool(dev, &dpi, NULL, &dp));
    VkDescriptorSetAllocateInfo dai = {.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO, .descriptorPool = dp,
                                       .descriptorSetCount = 1, .pSetLayouts = &dsl};
    VkDescriptorSet ds;
    TRY("vkAllocateDescriptorSets", vkAllocateDescriptorSets(dev, &dai, &ds));
    VkDescriptorBufferInfo bi = {.buffer = buf, .range = (VkDeviceSize)n * 4};
    VkWriteDescriptorSet w = {.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, .dstSet = ds, .descriptorCount = 1,
                              .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, .pBufferInfo = &bi};
    vkUpdateDescriptorSets(dev, 1, &w, 0, NULL);
    VkCommandBuffer cb = begin();
    if (!cb) {
        return VK_ERROR_OUT_OF_HOST_MEMORY;
    }
    vkCmdBindPipeline(cb, VK_PIPELINE_BIND_POINT_COMPUTE, p);
    vkCmdBindDescriptorSets(cb, VK_PIPELINE_BIND_POINT_COMPUTE, pl, 0, 1, &ds, 0, NULL);
    vkCmdDispatch(cb, n / 64, 1, 1);
    VkMemoryBarrier mb = {.sType = VK_STRUCTURE_TYPE_MEMORY_BARRIER, .srcAccessMask = VK_ACCESS_SHADER_WRITE_BIT,
                          .dstAccessMask = VK_ACCESS_HOST_READ_BIT};
    vkCmdPipelineBarrier(cb, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, VK_PIPELINE_STAGE_HOST_BIT, 0, 1, &mb, 0, NULL, 0, NULL);
    return submit(cb, "compute");
}

static uint32_t wrong_words(const uint32_t *v, uint32_t n)
{
    uint32_t bad = 0;
    for (uint32_t i = 0; i < n; i++) {
        if (v[i] != i * 3 + 1) {
            if (bad++ < 3) {
                say("  word %u: %#x, want %#x", i, v[i], i * 3 + 1);
            }
        }
    }
    return bad;
}

static int test_compute(void)
{
    uint32_t n = 4096;
    VkBuffer b;
    VkDeviceMemory m;
    void *map;
    if (plain_buffer(n * 4, VK_BUFFER_USAGE_STORAGE_BUFFER_BIT, &b, &m, &map) != VK_SUCCESS) {
        return 0;
    }
    memset(map, 0, n * 4);
    if (compute_into(b, n) != VK_SUCCESS) {
        return 0;
    }
    uint32_t bad = wrong_words(map, n);
    say("compute: %u of %u words wrong", bad, n);
    return bad == 0;
}

/* -- render: a 64x64 RGBA8 target, one triangle over it, read back --------------------------------- */

static int test_render(void)
{
    IFN(vkGetPhysicalDeviceFormatProperties);
    DFN(vkCreateImage);
    DFN(vkGetImageMemoryRequirements);
    DFN(vkAllocateMemory);
    DFN(vkBindImageMemory);
    DFN(vkCreateImageView);
    DFN(vkCreateRenderPass);
    DFN(vkCreateFramebuffer);
    DFN(vkCreatePipelineLayout);
    DFN(vkCreateGraphicsPipelines);
    DFN(vkCmdBeginRenderPass);
    DFN(vkCmdBindPipeline);
    DFN(vkCmdDraw);
    DFN(vkCmdEndRenderPass);
    DFN(vkCmdCopyImageToBuffer);
    DFN(vkCmdPipelineBarrier);
    const uint32_t W = 64;
    VkFormat fmt = VK_FORMAT_R8G8B8A8_UNORM;
    VkFormatProperties fp;
    vkGetPhysicalDeviceFormatProperties(pd, fmt, &fp);
    if (!(fp.optimalTilingFeatures & VK_FORMAT_FEATURE_COLOR_ATTACHMENT_BIT)) {
        say("render: RGBA8 is no color attachment");
        return 0;
    }
    VkImageCreateInfo ici = {.sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO, .imageType = VK_IMAGE_TYPE_2D, .format = fmt,
                             .extent = {W, W, 1}, .mipLevels = 1, .arrayLayers = 1, .samples = VK_SAMPLE_COUNT_1_BIT,
                             .tiling = VK_IMAGE_TILING_OPTIMAL,
                             .usage = VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT,
                             .initialLayout = VK_IMAGE_LAYOUT_UNDEFINED};
    VkImage img;
    if (vkCreateImage(dev, &ici, NULL, &img) != VK_SUCCESS) {
        say("error: vkCreateImage (render target)");
        return 0;
    }
    VkMemoryRequirements r;
    vkGetImageMemoryRequirements(dev, img, &r);
    uint32_t t = 0;
    while (t < mp.memoryTypeCount && !(r.memoryTypeBits & (1u << t))) {
        t++;
    }
    VkMemoryAllocateInfo ai = {.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO, .allocationSize = r.size, .memoryTypeIndex = t};
    VkDeviceMemory im;
    if (vkAllocateMemory(dev, &ai, NULL, &im) != VK_SUCCESS || vkBindImageMemory(dev, img, im, 0) != VK_SUCCESS) {
        say("error: render target memory");
        return 0;
    }
    VkImageViewCreateInfo vci = {.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO, .image = img, .viewType = VK_IMAGE_VIEW_TYPE_2D,
                                 .format = fmt, .subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1}};
    VkImageView view;
    if (vkCreateImageView(dev, &vci, NULL, &view) != VK_SUCCESS) {
        say("error: vkCreateImageView");
        return 0;
    }
    VkAttachmentDescription ad = {.format = fmt, .samples = VK_SAMPLE_COUNT_1_BIT, .loadOp = VK_ATTACHMENT_LOAD_OP_CLEAR,
                                  .storeOp = VK_ATTACHMENT_STORE_OP_STORE, .stencilLoadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE,
                                  .stencilStoreOp = VK_ATTACHMENT_STORE_OP_DONT_CARE, .initialLayout = VK_IMAGE_LAYOUT_UNDEFINED,
                                  .finalLayout = VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL};
    VkAttachmentReference ar = {0, VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL};
    VkSubpassDescription sd = {.pipelineBindPoint = VK_PIPELINE_BIND_POINT_GRAPHICS, .colorAttachmentCount = 1, .pColorAttachments = &ar};
    VkSubpassDependency dep = {.srcSubpass = 0, .dstSubpass = VK_SUBPASS_EXTERNAL,
                               .srcStageMask = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT, .dstStageMask = VK_PIPELINE_STAGE_TRANSFER_BIT,
                               .srcAccessMask = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT, .dstAccessMask = VK_ACCESS_TRANSFER_READ_BIT};
    VkRenderPassCreateInfo rpi = {.sType = VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO, .attachmentCount = 1, .pAttachments = &ad,
                                  .subpassCount = 1, .pSubpasses = &sd, .dependencyCount = 1, .pDependencies = &dep};
    VkRenderPass rp;
    if (vkCreateRenderPass(dev, &rpi, NULL, &rp) != VK_SUCCESS) {
        say("error: vkCreateRenderPass");
        return 0;
    }
    VkFramebufferCreateInfo fbi = {.sType = VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO, .renderPass = rp, .attachmentCount = 1,
                                   .pAttachments = &view, .width = W, .height = W, .layers = 1};
    VkFramebuffer fb;
    if (vkCreateFramebuffer(dev, &fbi, NULL, &fb) != VK_SUCCESS) {
        say("error: vkCreateFramebuffer");
        return 0;
    }
    VkPipelineLayoutCreateInfo pli = {.sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};
    VkPipelineLayout pl;
    if (vkCreatePipelineLayout(dev, &pli, NULL, &pl) != VK_SUCCESS) {
        return 0;
    }
    VkShaderModule vs = shader(spv_vert, sizeof spv_vert), fs = shader(spv_frag, sizeof spv_frag);
    if (!vs || !fs) {
        return 0;
    }
    VkPipelineShaderStageCreateInfo st[2] = {
        {.sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO, .stage = VK_SHADER_STAGE_VERTEX_BIT, .module = vs, .pName = "main"},
        {.sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO, .stage = VK_SHADER_STAGE_FRAGMENT_BIT, .module = fs, .pName = "main"}};
    VkPipelineVertexInputStateCreateInfo vi = {.sType = VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO};
    VkPipelineInputAssemblyStateCreateInfo ia = {.sType = VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO,
                                                 .topology = VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST};
    VkViewport vp = {0, 0, (float)W, (float)W, 0, 1};
    VkRect2D sc = {{0, 0}, {W, W}};
    VkPipelineViewportStateCreateInfo vps = {.sType = VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO, .viewportCount = 1,
                                             .pViewports = &vp, .scissorCount = 1, .pScissors = &sc};
    VkPipelineRasterizationStateCreateInfo rs = {.sType = VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO,
                                                 .polygonMode = VK_POLYGON_MODE_FILL, .cullMode = VK_CULL_MODE_NONE, .lineWidth = 1};
    VkPipelineMultisampleStateCreateInfo ms = {.sType = VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO,
                                               .rasterizationSamples = VK_SAMPLE_COUNT_1_BIT};
    VkPipelineColorBlendAttachmentState cba = {.colorWriteMask = 0xf};
    VkPipelineColorBlendStateCreateInfo cb = {.sType = VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO, .attachmentCount = 1,
                                              .pAttachments = &cba};
    VkGraphicsPipelineCreateInfo gpi = {.sType = VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO, .stageCount = 2, .pStages = st,
                                        .pVertexInputState = &vi, .pInputAssemblyState = &ia, .pViewportState = &vps,
                                        .pRasterizationState = &rs, .pMultisampleState = &ms, .pColorBlendState = &cb,
                                        .layout = pl, .renderPass = rp};
    VkPipeline p;
    VkResult pr = vkCreateGraphicsPipelines(dev, VK_NULL_HANDLE, 1, &gpi, NULL, &p);
    if (pr != VK_SUCCESS) {
        say("error: vkCreateGraphicsPipelines: VkResult %d", pr);
        return 0;
    }
    VkBuffer rb;
    VkDeviceMemory rm;
    void *map;
    if (plain_buffer(W * W * 4, VK_BUFFER_USAGE_TRANSFER_DST_BIT, &rb, &rm, &map) != VK_SUCCESS) {
        return 0;
    }
    memset(map, 0, W * W * 4);
    VkCommandBuffer c = begin();
    if (!c) {
        return 0;
    }
    VkClearValue clear = {.color = {{1, 0, 0, 1}}};
    VkRenderPassBeginInfo rbi = {.sType = VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO, .renderPass = rp, .framebuffer = fb,
                                 .renderArea = {{0, 0}, {W, W}}, .clearValueCount = 1, .pClearValues = &clear};
    vkCmdBeginRenderPass(c, &rbi, VK_SUBPASS_CONTENTS_INLINE);
    vkCmdBindPipeline(c, VK_PIPELINE_BIND_POINT_GRAPHICS, p);
    vkCmdDraw(c, 3, 1, 0, 0);
    vkCmdEndRenderPass(c);
    VkBufferImageCopy bic = {.imageSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1}, .imageExtent = {W, W, 1}};
    vkCmdCopyImageToBuffer(c, img, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, rb, 1, &bic);
    VkMemoryBarrier mb = {.sType = VK_STRUCTURE_TYPE_MEMORY_BARRIER, .srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT,
                          .dstAccessMask = VK_ACCESS_HOST_READ_BIT};
    vkCmdPipelineBarrier(c, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_HOST_BIT, 0, 1, &mb, 0, NULL, 0, NULL);
    if (submit(c, "render") != VK_SUCCESS) {
        return 0;
    }
    /* (0.25, 0.5, 0.75, 1) in UNORM8: 64, 128, 191, 255 (+-1 for the device's rounding) */
    const uint8_t *px = map;
    uint32_t bad = 0;
    for (uint32_t i = 0; i < W * W; i++) {
        const uint8_t *q = px + i * 4;
        if (abs(q[0] - 64) > 1 || abs(q[1] - 128) > 1 || abs(q[2] - 191) > 1 || q[3] != 255) {
            if (bad++ < 3) {
                say("  pixel %u: %u %u %u %u", i, q[0], q[1], q[2], q[3]);
            }
        }
    }
    say("render: %u of %u pixels wrong", bad, W * W);
    return bad == 0;
}

/* -- host memory: a buffer over an mmap (VK_EXT_external_memory_host), written by the GPU ---------- */

static size_t host_align = 4096;

/* The memory type the host import landed on (import_host), so the test can tell whether it must do the
 * cache maintenance a HOST_CACHED non-coherent type needs. */
static uint32_t host_import_type = UINT32_MAX;

static int import_host(void *host, size_t size, uint32_t want_bits, VkDeviceMemory *m)
{
    DFN(vkGetMemoryHostPointerPropertiesEXT);
    DFN(vkAllocateMemory);
    if (!vkGetMemoryHostPointerPropertiesEXT) {
        say("error: no vkGetMemoryHostPointerPropertiesEXT");
        return 0;
    }
    VkMemoryHostPointerPropertiesEXT hp = {.sType = VK_STRUCTURE_TYPE_MEMORY_HOST_POINTER_PROPERTIES_EXT};
    VkResult r = vkGetMemoryHostPointerPropertiesEXT(dev, VK_EXTERNAL_MEMORY_HANDLE_TYPE_HOST_ALLOCATION_BIT_EXT, host, &hp);
    if (r != VK_SUCCESS) {
        say("error: vkGetMemoryHostPointerPropertiesEXT: VkResult %d", r);
        return 0;
    }
    uint32_t bits = hp.memoryTypeBits & want_bits;
    say("host import: memory types %#x (wanted %#x)", hp.memoryTypeBits, want_bits);
    uint32_t t = 0;
    while (t < 32 && !(bits & (1u << t))) {
        t++;
    }
    if (t == 32) {
        say("error: no memory type both the resource and the host import take");
        return 0;
    }
    host_import_type = t;
    say("host import: memory type %u, flags %#x", t, mp.memoryTypes[t].propertyFlags);
    if (!(mp.memoryTypes[t].propertyFlags & VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)) {
        /* The engine imports the guest's RAM the same way and does no cache sync yet, so GpuCheck.java turns
         * this line into a lack of its own: a pass here would start iOS 26 on stale reads and writes. The
         * text up to "sync" is matched exactly there. */
        say("host import: not coherent: the CPU and the GPU see each other's writes only after a cache sync (flags %#x)",
            mp.memoryTypes[t].propertyFlags);
    }
    VkImportMemoryHostPointerInfoEXT imp = {.sType = VK_STRUCTURE_TYPE_IMPORT_MEMORY_HOST_POINTER_INFO_EXT,
                                            .handleType = VK_EXTERNAL_MEMORY_HANDLE_TYPE_HOST_ALLOCATION_BIT_EXT, .pHostPointer = host};
    VkMemoryAllocateInfo ai = {.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO, .pNext = &imp, .allocationSize = size, .memoryTypeIndex = t};
    r = vkAllocateMemory(dev, &ai, NULL, m);
    if (r != VK_SUCCESS) {
        say("error: vkAllocateMemory (host import of %zu bytes): VkResult %d", size, r);
        return 0;
    }
    return 1;
}

#ifndef MFD_CLOEXEC
#define MFD_CLOEXEC 1U
#endif

/* The memory the engine imports is its guest RAM: a MAP_SHARED mapping of a memfd whose descriptor stays
 * open. Old KGSL (msm-5.4 and older) refuses a pointer into a file mapping while the file has a descriptor
 * in the caller's table, and takes anonymous memory, so the check must import the engine's kind. bionic's
 * memfd_create wrapper needs API 30, hence the syscall. *fdp gets the descriptor (kept open), or -1. */
static void *host_mapping(size_t size, int *fdp)
{
    *fdp = -1;
    int fd = (int)syscall(__NR_memfd_create, "gpucheck-host", MFD_CLOEXEC);
    const char *why = NULL;
    void *p = MAP_FAILED;
    if (fd < 0) {
        why = strerror(errno);
    } else if (ftruncate(fd, (off_t)size) < 0) {
        why = strerror(errno);
    } else {
        p = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
        if (p == MAP_FAILED) {
            why = strerror(errno);
        }
    }
    if (p != MAP_FAILED) {
        *fdp = fd;
        say("host memory: a shared memfd mapping, its descriptor open while it is imported (as the engine's guest RAM)");
        return p;
    }
    if (fd >= 0) {
        close(fd);
    }
    say("host memory: no memfd (%s), an anonymous shared mapping instead", why);
    return mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED | MAP_ANONYMOUS, -1, 0);
}

static int host_run(uint32_t *host, size_t size);

static int test_host(void)
{
    uint32_t n = 1 << 20;                  /* 4 MiB */
    size_t size = (size_t)n * 4;
    int fd;
    uint32_t *host = host_mapping(size, &fd);
    if (host == MAP_FAILED) {
        say("error: mmap");
        return 0;
    }
    int ok = host_run(host, size);
    /* the mapping stays: the imported memory is never freed, and its pages must not go away under it */
    if (fd >= 0) {
        close(fd);
    }
    return ok;
}

static int host_run(uint32_t *host, size_t size)
{
    DFN(vkCreateBuffer);
    DFN(vkGetBufferMemoryRequirements);
    DFN(vkBindBufferMemory);
    DFN(vkMapMemory);
    DFN(vkUnmapMemory);
    DFN(vkFlushMappedMemoryRanges);
    DFN(vkInvalidateMappedMemoryRanges);
    uint32_t n = (uint32_t)(size / 4);
    memset(host, 0, size);
    VkExternalMemoryBufferCreateInfo eb = {.sType = VK_STRUCTURE_TYPE_EXTERNAL_MEMORY_BUFFER_CREATE_INFO,
                                           .handleTypes = VK_EXTERNAL_MEMORY_HANDLE_TYPE_HOST_ALLOCATION_BIT_EXT};
    VkBufferCreateInfo bci = {.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO, .pNext = &eb, .size = size,
                              .usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT};
    VkBuffer b;
    VkResult r = vkCreateBuffer(dev, &bci, NULL, &b);
    if (r != VK_SUCCESS) {
        say("error: vkCreateBuffer (external host): VkResult %d", r);
        return 0;
    }
    VkMemoryRequirements mr;
    vkGetBufferMemoryRequirements(dev, b, &mr);
    VkDeviceMemory m;
    if (!import_host(host, size, mr.memoryTypeBits, &m)) {
        return 0;
    }
    r = vkBindBufferMemory(dev, b, m, 0);
    if (r != VK_SUCCESS) {
        say("error: vkBindBufferMemory (host import): VkResult %d", r);
        return 0;
    }
    /* A HOST_CACHED type that is not HOST_COHERENT needs explicit cache maintenance: flush what the CPU
     * wrote before the GPU reads it, invalidate before the CPU reads what the GPU wrote. Without it the
     * comparison below sees stale (cached) lines and the test reports a working import as broken -- which
     * is what happens on Mali-G1-Ultra, whose only importable type is cached and non-coherent. */
    VkBool32 coherent = (mp.memoryTypes[host_import_type].propertyFlags & VK_MEMORY_PROPERTY_HOST_COHERENT_BIT) != 0;
    void *mapped = NULL;
    VkMappedMemoryRange range = {.sType = VK_STRUCTURE_TYPE_MAPPED_MEMORY_RANGE, .memory = m, .offset = 0, .size = VK_WHOLE_SIZE};
    if (!coherent) {
        if (!vkMapMemory || !vkUnmapMemory || !vkFlushMappedMemoryRanges || !vkInvalidateMappedMemoryRanges) {
            say("error: host-import cache maintenance functions missing");
            return 0;
        }
        r = vkMapMemory(dev, m, 0, VK_WHOLE_SIZE, 0, &mapped);
        if (r != VK_SUCCESS) {
            say("error: vkMapMemory (host import): VkResult %d", r);
            return 0;
        }
        r = vkFlushMappedMemoryRanges(dev, 1, &range);
        if (r != VK_SUCCESS) {
            say("error: vkFlushMappedMemoryRanges: VkResult %d", r);
            vkUnmapMemory(dev, m);
            return 0;
        }
    }
    if (compute_into(b, n) != VK_SUCCESS) {
        if (mapped) {
            vkUnmapMemory(dev, m);
        }
        return 0;
    }
    if (mapped) {
        r = vkInvalidateMappedMemoryRanges(dev, 1, &range);
        if (r != VK_SUCCESS) {
            say("error: vkInvalidateMappedMemoryRanges: VkResult %d", r);
            vkUnmapMemory(dev, m);
            return 0;
        }
    }
    uint32_t bad = wrong_words(mapped ? (const uint32_t *)mapped : host, n);
    say("host memory: %u of %u words the GPU wrote into the phone's own pages wrong", bad, n);
    if (mapped) {
        vkUnmapMemory(dev, m);
    }
    return bad == 0;
}

/* -- sparse: a buffer gathered from scattered pieces of one host import, read back by a copy -------- */

static VkResult bind_sparse(const VkBindSparseInfo *bsi)
{
    DFN(vkQueueBindSparse);
    DFN(vkWaitForFences);
    DFN(vkResetFences);
    vkResetFences(dev, 1, &fence);
    TRY("vkQueueBindSparse", vkQueueBindSparse(sq, 1, bsi, fence));
    TRY("vkWaitForFences (bind)", vkWaitForFences(dev, 1, &fence, VK_TRUE, 10000000000ull));
    return VK_SUCCESS;
}

static uint8_t *sparse_host;
static int sparse_fd = -1;
static const size_t SPARSE_BIG = 32 << 20;
static VkDeviceMemory sparse_mem;

static int sparse_import(uint32_t want_bits)
{
    if (sparse_host) {
        return 1;
    }
    /* the same kind as the engine's RAM; the descriptor stays open until the process ends */
    sparse_host = host_mapping(SPARSE_BIG, &sparse_fd);
    if (sparse_host == MAP_FAILED) {
        sparse_host = NULL;
        say("error: mmap");
        return 0;
    }
    for (size_t i = 0; i < SPARSE_BIG; i += 4) {
        *(uint32_t *)(sparse_host + i) = (uint32_t)(i / 4096);     /* each 4 KiB holds its own number */
    }
    if (!import_host(sparse_host, SPARSE_BIG, want_bits, &sparse_mem)) {
        munmap(sparse_host, SPARSE_BIG);
        sparse_host = NULL;
        if (sparse_fd >= 0) {
            close(sparse_fd);
            sparse_fd = -1;
        }
        return 0;
    }
    if (!(mp.memoryTypes[host_import_type].propertyFlags & VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)) {
        /* The pattern above sits in the CPU's cache on a non-coherent type: flush it so the GPU's copy reads
         * it, not what was in the pages before (the gather would be reported wrong for that reason alone). The
         * copy only reads the import, so nothing needs invalidating. A failure here is not fatal: the
         * comparison then says what it sees. */
        DFN(vkMapMemory);
        DFN(vkUnmapMemory);
        DFN(vkFlushMappedMemoryRanges);
        void *mapped = NULL;
        VkMappedMemoryRange range = {.sType = VK_STRUCTURE_TYPE_MAPPED_MEMORY_RANGE, .memory = sparse_mem, .offset = 0,
                                     .size = VK_WHOLE_SIZE};
        if (vkMapMemory && vkUnmapMemory && vkFlushMappedMemoryRanges
            && vkMapMemory(dev, sparse_mem, 0, VK_WHOLE_SIZE, 0, &mapped) == VK_SUCCESS) {
            vkFlushMappedMemoryRanges(dev, 1, &range);
            vkUnmapMemory(dev, sparse_mem);
        }
    }
    return 1;
}

static int test_sparse_buffer(void)
{
    DFN(vkCreateBuffer);
    DFN(vkGetBufferMemoryRequirements);
    DFN(vkCmdCopyBuffer);
    DFN(vkCmdPipelineBarrier);
    VkExternalMemoryBufferCreateInfo eb = {.sType = VK_STRUCTURE_TYPE_EXTERNAL_MEMORY_BUFFER_CREATE_INFO,
                                           .handleTypes = VK_EXTERNAL_MEMORY_HANDLE_TYPE_HOST_ALLOCATION_BIT_EXT};
    VkDeviceSize size = 1 << 20;
    VkBufferCreateInfo bci = {.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO, .pNext = &eb, .size = size,
                              .usage = VK_BUFFER_USAGE_TRANSFER_SRC_BIT | VK_BUFFER_USAGE_STORAGE_BUFFER_BIT,
                              .flags = VK_BUFFER_CREATE_SPARSE_BINDING_BIT};
    VkBuffer sb;
    VkResult r = vkCreateBuffer(dev, &bci, NULL, &sb);
    if (r != VK_SUCCESS) {
        say("error: vkCreateBuffer (sparse): VkResult %d", r);
        return 0;
    }
    VkMemoryRequirements mr;
    vkGetBufferMemoryRequirements(dev, sb, &mr);
    say("sparse buffer: block %llu bytes, memory types %#x", (unsigned long long)mr.alignment, mr.memoryTypeBits);
    if (mr.alignment > (1 << 16) || SPARSE_BIG % mr.alignment) {
        say("error: sparse block of %llu bytes", (unsigned long long)mr.alignment);
        return 0;
    }
    if (!sparse_import(mr.memoryTypeBits)) {
        return 0;
    }
    VkDeviceSize blk = mr.alignment, pieces = size / blk, inbig = SPARSE_BIG / blk;
    VkSparseMemoryBind *binds = calloc(pieces, sizeof *binds);
    for (VkDeviceSize i = 0; i < pieces; i++) {
        /* piece i from piece (37i + 11) mod N of the import: scattered and out of order */
        binds[i] = (VkSparseMemoryBind){.resourceOffset = i * blk, .size = blk, .memory = sparse_mem,
                                        .memoryOffset = ((37ull * i + 11) % inbig) * blk};
    }
    VkSparseBufferMemoryBindInfo bbi = {.buffer = sb, .bindCount = (uint32_t)pieces, .pBinds = binds};
    VkBindSparseInfo bsi = {.sType = VK_STRUCTURE_TYPE_BIND_SPARSE_INFO, .bufferBindCount = 1, .pBufferBinds = &bbi};
    if (bind_sparse(&bsi) != VK_SUCCESS) {
        return 0;
    }
    VkBuffer db;
    VkDeviceMemory dm;
    void *map;
    if (plain_buffer(size, VK_BUFFER_USAGE_TRANSFER_DST_BIT, &db, &dm, &map) != VK_SUCCESS) {
        return 0;
    }
    memset(map, 0xff, size);
    VkCommandBuffer c = begin();
    VkBufferCopy cp = {.size = size};
    vkCmdCopyBuffer(c, sb, db, 1, &cp);
    VkMemoryBarrier mb = {.sType = VK_STRUCTURE_TYPE_MEMORY_BARRIER, .srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT,
                          .dstAccessMask = VK_ACCESS_HOST_READ_BIT};
    vkCmdPipelineBarrier(c, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_HOST_BIT, 0, 1, &mb, 0, NULL, 0, NULL);
    if (submit(c, "sparse copy") != VK_SUCCESS) {
        return 0;
    }
    uint32_t bad = 0;
    for (VkDeviceSize i = 0; i < pieces; i++) {
        uint32_t want = (uint32_t)((((37ull * i + 11) % inbig) * blk) / 4096);
        uint32_t got = *(uint32_t *)((uint8_t *)map + i * blk);
        if (got != want && bad++ < 3) {
            say("  piece %llu: %u, want %u", (unsigned long long)i, got, want);
        }
    }
    free(binds);
    say("sparse gather: %u of %llu pieces wrong", bad, (unsigned long long)pieces);
    return bad == 0;
}

/* recommended: a sparse LINEAR BGRA8 image, its opaque memory from scattered pieces of the host import */
static int test_sparse_image(void)
{
    DFN(vkCreateImage);
    DFN(vkGetImageMemoryRequirements);
    DFN(vkCmdCopyImageToBuffer);
    DFN(vkCmdPipelineBarrier);
    DFN(vkGetImageSubresourceLayout);
    const uint32_t W = 256, H = 64;
    VkExternalMemoryImageCreateInfo ei = {.sType = VK_STRUCTURE_TYPE_EXTERNAL_MEMORY_IMAGE_CREATE_INFO,
                                          .handleTypes = VK_EXTERNAL_MEMORY_HANDLE_TYPE_HOST_ALLOCATION_BIT_EXT};
    VkImageCreateInfo ici = {.sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO, .pNext = &ei, .flags = VK_IMAGE_CREATE_SPARSE_BINDING_BIT,
                             .imageType = VK_IMAGE_TYPE_2D, .format = VK_FORMAT_B8G8R8A8_UNORM, .extent = {W, H, 1},
                             .mipLevels = 1, .arrayLayers = 1, .samples = VK_SAMPLE_COUNT_1_BIT, .tiling = VK_IMAGE_TILING_LINEAR,
                             .usage = VK_IMAGE_USAGE_TRANSFER_SRC_BIT | VK_IMAGE_USAGE_SAMPLED_BIT,
                             .initialLayout = VK_IMAGE_LAYOUT_UNDEFINED};
    VkImage img;
    VkResult r = vkCreateImage(dev, &ici, NULL, &img);
    if (r != VK_SUCCESS) {
        say("sparse image: vkCreateImage (sparse, linear): VkResult %d", r);
        return 0;
    }
    VkMemoryRequirements mr;
    vkGetImageMemoryRequirements(dev, img, &mr);
    VkImageSubresource sub = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0};
    VkSubresourceLayout lay;
    vkGetImageSubresourceLayout(dev, img, &sub, &lay);
    say("sparse image: %llu bytes, block %llu, row pitch %llu", (unsigned long long)mr.size, (unsigned long long)mr.alignment,
        (unsigned long long)lay.rowPitch);
    if (!sparse_import(mr.memoryTypeBits) || mr.alignment > (1 << 16) || SPARSE_BIG % mr.alignment) {
        return 0;
    }
    VkDeviceSize blk = mr.alignment, pieces = (mr.size + blk - 1) / blk, inbig = SPARSE_BIG / blk;
    VkSparseMemoryBind *binds = calloc(pieces, sizeof *binds);
    for (VkDeviceSize i = 0; i < pieces; i++) {
        binds[i] = (VkSparseMemoryBind){.resourceOffset = i * blk, .size = blk, .memory = sparse_mem,
                                        .memoryOffset = ((53ull * i + 7) % inbig) * blk};
    }
    VkSparseImageOpaqueMemoryBindInfo ob = {.image = img, .bindCount = (uint32_t)pieces, .pBinds = binds};
    VkBindSparseInfo bsi = {.sType = VK_STRUCTURE_TYPE_BIND_SPARSE_INFO, .imageOpaqueBindCount = 1, .pImageOpaqueBinds = &ob};
    if (bind_sparse(&bsi) != VK_SUCCESS) {
        return 0;
    }
    VkBuffer db;
    VkDeviceMemory dm;
    void *map;
    if (plain_buffer(W * H * 4, VK_BUFFER_USAGE_TRANSFER_DST_BIT, &db, &dm, &map) != VK_SUCCESS) {
        return 0;
    }
    VkCommandBuffer c = begin();
    /* UNDEFINED -> GENERAL: Turnip keeps a linear image's bytes (APK-PLAN 6.19's probe); the copy reads them */
    VkImageMemoryBarrier ib = {.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER, .dstAccessMask = VK_ACCESS_TRANSFER_READ_BIT,
                               .oldLayout = VK_IMAGE_LAYOUT_UNDEFINED, .newLayout = VK_IMAGE_LAYOUT_GENERAL,
                               .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED, .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
                               .image = img, .subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1}};
    vkCmdPipelineBarrier(c, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT, 0, 0, NULL, 0, NULL, 1, &ib);
    VkBufferImageCopy bic = {.imageSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1}, .imageExtent = {W, H, 1}};
    vkCmdCopyImageToBuffer(c, img, VK_IMAGE_LAYOUT_GENERAL, db, 1, &bic);
    VkMemoryBarrier mb = {.sType = VK_STRUCTURE_TYPE_MEMORY_BARRIER, .srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT,
                          .dstAccessMask = VK_ACCESS_HOST_READ_BIT};
    vkCmdPipelineBarrier(c, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_HOST_BIT, 0, 1, &mb, 0, NULL, 0, NULL);
    if (submit(c, "sparse image copy") != VK_SUCCESS) {
        return 0;
    }
    /* each texel: the number of the 4 KiB of the import its byte offset in the image's memory falls in */
    uint32_t bad = 0;
    for (uint32_t y = 0; y < H; y++) {
        for (uint32_t x = 0; x < W; x++) {
            VkDeviceSize off = lay.offset + y * lay.rowPitch + x * 4;
            VkDeviceSize piece = off / blk, src = ((53ull * piece + 7) % inbig) * blk + off % blk;
            uint32_t want = (uint32_t)(src / 4096), got = ((uint32_t *)map)[y * W + x];
            if (got != want && bad++ < 3) {
                say("  texel %u,%u: %u, want %u", x, y, got, want);
            }
        }
    }
    free(binds);
    say("sparse image: %u of %u texels wrong", bad, W * H);
    return bad == 0;
}

/* -- the check --------------------------------------------------------------------------------- */

static const char *vendor(uint32_t id)
{
    switch (id) {
    case 0x5143: return "Qualcomm";
    case 0x13b5: return "ARM";
    case 0x1010: return "Imagination";
    case 0x144d: return "Samsung";
    case 0x10de: return "NVIDIA";
    case 0x1002: return "AMD";
    case 0x8086: return "Intel";
    case 0x10005: return "Mesa";
    default: return "?";
    }
}

/* -- KGSL import diagnostic: log only, never a lack ------------------------------------------------ */

/* From Mesa's src/freedreno/vulkan/msm_kgsl.h (the NDK has no KGSL header) */
#define KGSL_IOC_TYPE 0x09
struct kgsl_gpuobj_import {
    uint64_t priv;
    uint64_t priv_len;
    uint64_t flags;
    unsigned int type;
    unsigned int id;
};
struct kgsl_gpuobj_import_useraddr {
    uint64_t virtaddr;
};
struct kgsl_gpumem_free_id {
    unsigned int id;
    unsigned int pad;
};
#define IOCTL_KGSL_GPUOBJ_IMPORT _IOWR(KGSL_IOC_TYPE, 0x48, struct kgsl_gpuobj_import)
#define IOCTL_KGSL_GPUMEM_FREE_ID _IOWR(KGSL_IOC_TYPE, 0x35, struct kgsl_gpumem_free_id)
#define KGSL_USER_MEM_TYPE_ADDR 0x2
#define KGSL_CACHEMODE_WRITEBACK 3
#define KGSL_CACHEMODE_SHIFT 26

struct linux_dirent64 {
    uint64_t d_ino;
    int64_t d_off;
    unsigned short d_reclen;
    unsigned char d_type;
    char d_name[];
};

#define PROBE_SIZE (256 << 10)
#define MAX_FDS 4096

static int kgsl_import(int kg, void *p, unsigned *id)
{
    struct kgsl_gpuobj_import_useraddr u = {.virtaddr = (uintptr_t)p};
    struct kgsl_gpuobj_import req = {.priv = (uintptr_t)&u, .priv_len = PROBE_SIZE,
                                     .flags = (uint64_t)KGSL_CACHEMODE_WRITEBACK << KGSL_CACHEMODE_SHIFT,
                                     .type = KGSL_USER_MEM_TYPE_ADDR};
    int r;
    do {
        r = ioctl(kg, IOCTL_KGSL_GPUOBJ_IMPORT, &req);
    } while (r < 0 && (errno == EINTR || errno == EAGAIN));
    *id = req.id;
    return r;
}

static void kgsl_free(int kg, unsigned id)
{
    struct kgsl_gpumem_free_id f = {.id = id};
    ioctl(kg, IOCTL_KGSL_GPUMEM_FREE_ID, &f);
}

/* one result line from an import's return value and errno */
static void kgsl_line(const char *name, int r, int err)
{
    if (r == 0) {
        say("kgsl import: %s: ok", name);
    } else {
        say("kgsl import: %s: refused, %s (errno %d)", name, strerror(err), err);
    }
}

struct kgsl_job {
    int kg;
    void *ptr;
    int ret, err, unshare_err;
    unsigned id;
    int fds[MAX_FDS];
};

/* Runs with its own descriptor table. Android's fdsan tracks descriptor ownership by number for the whole
 * process and aborts when libc closes a number it thinks someone else owns, so everything here that touches
 * descriptors is a raw syscall, and nothing calls say()/fprintf. */
static void *kgsl_thread(void *arg)
{
    struct kgsl_job *j = arg;
    if (syscall(__NR_unshare, CLONE_FILES) != 0) {
        j->unshare_err = errno;
        return NULL;
    }
    int nfd = 0, overflow = 0;
    long dfd = syscall(__NR_openat, AT_FDCWD, "/proc/thread-self/fd", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (dfd >= 0) {
        char buf[2048];
        long got;
        while ((got = syscall(__NR_getdents64, (int)dfd, buf, sizeof buf)) > 0) {
            for (long off = 0; off < got;) {
                struct linux_dirent64 *d = (struct linux_dirent64 *)(buf + off);
                off += d->d_reclen;
                if (d->d_name[0] < '0' || d->d_name[0] > '9') {
                    continue;              /* "." and ".." */
                }
                int n = 0;
                for (const char *c = d->d_name; *c >= '0' && *c <= '9'; c++) {
                    n = n * 10 + (*c - '0');
                }
                if (n == j->kg || n == (int)dfd) {
                    continue;
                }
                if (nfd < MAX_FDS) {
                    j->fds[nfd++] = n;
                } else {
                    overflow = 1;
                }
            }
        }
        for (int i = 0; i < nfd; i++) {
            syscall(__NR_close, j->fds[i]);
        }
        syscall(__NR_close, (int)dfd);
    }
    if (dfd < 0 || overflow) {
        struct rlimit rl;
        long lim = 65536;
        if (getrlimit(RLIMIT_NOFILE, &rl) == 0 && rl.rlim_cur < (rlim_t)lim) {
            lim = (long)rl.rlim_cur;
        }
        for (long n = 0; n < lim; n++) {
            if (n != j->kg) {
                syscall(__NR_close, (int)n);
            }
        }
    }
    j->ret = kgsl_import(j->kg, j->ptr, &j->id);
    j->err = errno;
    return NULL;
}

/* a touched mapping of PROBE_SIZE bytes for one variant; *fd_out is the memfd (still open) or -1 */
static void *probe_map(int memfd, int *fd_out, int *err)
{
    *fd_out = -1;
    void *p = MAP_FAILED;
    if (!memfd) {
        p = mmap(NULL, PROBE_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED | MAP_ANONYMOUS, -1, 0);
        if (p == MAP_FAILED) {
            *err = errno;
            return p;
        }
    } else {
        int fd = (int)syscall(__NR_memfd_create, "gpucheck-kgsl", MFD_CLOEXEC);
        if (fd >= 0 && ftruncate(fd, PROBE_SIZE) == 0) {
            p = mmap(NULL, PROBE_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
        }
        if (p == MAP_FAILED) {
            *err = errno;
            if (fd >= 0) {
                close(fd);
            }
            return p;
        }
        *fd_out = fd;
    }
    memset(p, 0x5a, PROBE_SIZE);
    return p;
}

/* Which ways of handing KGSL a user pointer the kernel takes, for a reporter's log. Log only. */
static void kgsl_probe(void)
{
    int kg = open("/dev/kgsl-3d0", O_RDWR | O_CLOEXEC);
    if (kg < 0) {
        return;
    }
    struct utsname un;
    if (uname(&un) == 0) {
        say("kernel: %s", un.release);
    }
    static const char *const names[4] = {"anonymous shared mapping", "memfd mapping, descriptor open",
                                         "memfd mapping, descriptor closed",
                                         "memfd mapping, descriptor open, imported from a thread with its own descriptor table"};
    int b_ok = -1;
    for (int v = 0; v < 4; v++) {
        int fd, err = 0;
        void *p = probe_map(v != 0, &fd, &err);
        if (p == MAP_FAILED) {
            say("kgsl import: %s: not run, mapping failed, %s (errno %d)", names[v], strerror(err), err);
            continue;
        }
        if (v == 2) {
            close(fd);
            fd = -1;
        }
        if (v < 3) {
            unsigned id = 0;
            int r = kgsl_import(kg, p, &id);
            err = errno;
            kgsl_line(names[v], r, err);
            if (r == 0) {
                kgsl_free(kg, id);
            }
            if (v == 1) {
                b_ok = r == 0;
            }
        } else {
            struct kgsl_job *j = calloc(1, sizeof *j);
            pthread_t th;
            sigset_t all, old;
            int started = 0;
            if (j) {
                j->kg = kg;
                j->ptr = p;
                sigfillset(&all);
                pthread_sigmask(SIG_SETMASK, &all, &old);      /* no signal handler may run in the thread */
                started = pthread_create(&th, NULL, kgsl_thread, j) == 0;
                pthread_sigmask(SIG_SETMASK, &old, NULL);
            }
            if (!started) {
                say("kgsl import: %s: not run, no thread", names[v]);
            } else {
                pthread_join(th, NULL);
                if (j->unshare_err) {
                    say("kgsl import: %s: not run, unshare failed, %s (errno %d)", names[v], strerror(j->unshare_err),
                        j->unshare_err);
                } else {
                    kgsl_line(names[v], j->ret, j->err);
                    if (j->ret == 0) {
                        kgsl_free(kg, j->id);
                    }
                }
            }
            free(j);
        }
        munmap(p, PROBE_SIZE);
        if (fd >= 0) {
            close(fd);
        }
    }
    if (b_ok >= 0) {
        say("kgsl import: the kernel takes a mapping of a file with an open descriptor: %s", b_ok ? "yes" : "no");
    }
    close(kg);
}

static int check(const char *loader)
{
    /* the app's Turnip is loaded by a full path; the system's own by the bare name libvulkan.so */
    int turnip_mode = strchr(loader, '/') != NULL;
    void *lib = dlopen(loader, RTLD_NOW | RTLD_LOCAL);
    if (!lib) {
        say("error: cannot load the Vulkan loader %s: %s", loader, dlerror());
        lack("a Vulkan loader");
        return 2;
    }
    gipa = (PFN_vkGetInstanceProcAddr)dlsym(lib, "vkGetInstanceProcAddr");
    if (!gipa) {
        lack("vkGetInstanceProcAddr");
        return 2;
    }
    PFN_vkEnumerateInstanceVersion eiv = (PFN_vkEnumerateInstanceVersion)gipa(NULL, "vkEnumerateInstanceVersion");
    uint32_t iv = VK_API_VERSION_1_0;
    if (eiv) {
        eiv(&iv);
    }
    say("instance: Vulkan %u.%u.%u", VK_API_VERSION_MAJOR(iv), VK_API_VERSION_MINOR(iv), VK_API_VERSION_PATCH(iv));
    PFN_vkCreateInstance ci = (PFN_vkCreateInstance)gipa(NULL, "vkCreateInstance");
    VkApplicationInfo app = {.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO, .pApplicationName = "asoft-gpucheck",
                             .apiVersion = iv >= VK_API_VERSION_1_3 ? VK_API_VERSION_1_3 : VK_API_VERSION_1_2};
    VkInstanceCreateInfo ici = {.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO, .pApplicationInfo = &app};
    VkResult r = ci(&ici, NULL, &inst);
    if (r != VK_SUCCESS) {
        say("error: vkCreateInstance: VkResult %d", r);
        lack("a Vulkan 1.2 instance");
        return 2;
    }
    IFN(vkEnumeratePhysicalDevices);
    IFN(vkGetPhysicalDeviceProperties2);
    IFN(vkGetPhysicalDeviceFeatures2);
    IFN(vkGetPhysicalDeviceMemoryProperties);
    IFN(vkGetPhysicalDeviceQueueFamilyProperties);
    IFN(vkEnumerateDeviceExtensionProperties);
    IFN(vkCreateDevice);
    gdpa = (PFN_vkGetDeviceProcAddr)gipa(inst, "vkGetDeviceProcAddr");
    uint32_t n = 0;
    r = vkEnumeratePhysicalDevices(inst, &n, NULL);
    say("devices: %u (VkResult %d)", n, r);
    if (!n) {
        lack("a Vulkan device");
        return 2;
    }
    VkPhysicalDevice all[8];
    if (n > 8) {
        n = 8;
    }
    vkEnumeratePhysicalDevices(inst, &n, all);
    pd = all[0];
    VkPhysicalDeviceDriverProperties drv = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DRIVER_PROPERTIES};
    VkPhysicalDeviceExternalMemoryHostPropertiesEXT hostp = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_EXTERNAL_MEMORY_HOST_PROPERTIES_EXT,
                                                             .pNext = &drv};
    VkPhysicalDeviceProperties2 p2 = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2, .pNext = &hostp};
    vkGetPhysicalDeviceProperties2(pd, &p2);
    for (char *c = drv.driverInfo; *c; c++) {
        if (*c == 10 || *c == 13) {
            *c = ' ';          /* Qualcomm's spans lines */
        }
    }
    VkPhysicalDeviceProperties *p = &p2.properties;
    say("gpu: %s", p->deviceName);
    say("vendor: %#x (%s), device %#x", p->vendorID, vendor(p->vendorID), p->deviceID);
    say("device api: Vulkan %u.%u.%u", VK_API_VERSION_MAJOR(p->apiVersion), VK_API_VERSION_MINOR(p->apiVersion),
        VK_API_VERSION_PATCH(p->apiVersion));
    say("driver: %s, %s (driver id %d, version %#x, conformance %u.%u.%u.%u)", drv.driverName, drv.driverInfo, drv.driverID,
        p->driverVersion, drv.conformanceVersion.major, drv.conformanceVersion.minor, drv.conformanceVersion.subminor,
        drv.conformanceVersion.patch);
    say("limits: maxMemoryAllocationCount %u, maxStorageBufferRange %u, maxComputeWorkGroupInvocations %u, "
        "maxImageDimension2D %u, bufferImageGranularity %llu",
        p->limits.maxMemoryAllocationCount, p->limits.maxStorageBufferRange, p->limits.maxComputeWorkGroupInvocations,
        p->limits.maxImageDimension2D, (unsigned long long)p->limits.bufferImageGranularity);
    if (p->apiVersion < VK_API_VERSION_1_2) {
        lack("Vulkan 1.2 on the device");
    }

    uint32_t ne = 0;
    vkEnumerateDeviceExtensionProperties(pd, NULL, &ne, NULL);
    VkExtensionProperties *ext = calloc(ne ? ne : 1, sizeof *ext);
    vkEnumerateDeviceExtensionProperties(pd, NULL, &ne, ext);
    fprintf(out, "extensions (%u):", ne);
    for (uint32_t i = 0; i < ne; i++) {
        fprintf(out, " %s", ext[i].extensionName);
    }
    fputc('\n', out);
    fflush(out);
    int host_ext = has_ext(ext, ne, VK_EXT_EXTERNAL_MEMORY_HOST_EXTENSION_NAME);
    if (!host_ext) {
        lack("VK_EXT_external_memory_host");
    } else {
        host_align = hostp.minImportedHostPointerAlignment;
        say("host pointer alignment: %llu", (unsigned long long)host_align);
    }
    static const char *recommended_ext[] = {
        "VK_KHR_maintenance5", "VK_EXT_device_generated_commands", "VK_KHR_external_memory_fd", "VK_EXT_external_memory_dma_buf",
        "VK_EXT_image_drm_format_modifier", "VK_EXT_queue_family_foreign", "VK_EXT_shader_stencil_export",
        "VK_EXT_graphics_pipeline_library", "VK_KHR_pipeline_binary", "VK_EXT_host_image_copy", "VK_EXT_custom_border_color",
        "VK_EXT_extended_dynamic_state", "VK_EXT_extended_dynamic_state2", "VK_KHR_dynamic_rendering", "VK_EXT_robustness2",
        "VK_EXT_shader_demote_to_helper_invocation", "VK_KHR_shader_float_controls", "VK_EXT_fragment_shader_interlock",
        "VK_EXT_rasterization_order_attachment_access",
    };
    for (size_t i = 0; i < sizeof recommended_ext / sizeof *recommended_ext; i++) {
        if (!has_ext(ext, ne, recommended_ext[i])) {
            say("recommended, absent: %s", recommended_ext[i]);
        }
    }

    VkPhysicalDeviceVulkan13Features f13 = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_3_FEATURES};
    VkPhysicalDeviceVulkan12Features f12 = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_2_FEATURES,
                                            .pNext = p->apiVersion >= VK_API_VERSION_1_3 ? &f13 : NULL};
    VkPhysicalDeviceVulkan11Features f11 = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_1_FEATURES, .pNext = &f12};
    VkPhysicalDeviceFeatures2 f2 = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2, .pNext = &f11};
    vkGetPhysicalDeviceFeatures2(pd, &f2);
    VkPhysicalDeviceFeatures *f = &f2.features;
    /* what the guest's GPU work is built on (required) and what metal2vulkan uses where it is (logged) */
    struct { const char *name; VkBool32 v; int required; } feats[] = {
        {"sparseBinding", f->sparseBinding, 1},
        {"sparseResidencyBuffer", f->sparseResidencyBuffer, 1},
        {"shaderInt16", f->shaderInt16, 1},
        {"fragmentStoresAndAtomics", f->fragmentStoresAndAtomics, 1},
        {"vertexPipelineStoresAndAtomics", f->vertexPipelineStoresAndAtomics, 0},
        {"independentBlend", f->independentBlend, 1},
        {"imageCubeArray", f->imageCubeArray, 1},
        {"shaderStorageImageWriteWithoutFormat", f->shaderStorageImageWriteWithoutFormat, 1},
        {"shaderStorageImageReadWithoutFormat", f->shaderStorageImageReadWithoutFormat, 0},
        {"shaderInt64", f->shaderInt64, 0},
        {"shaderFloat64", f->shaderFloat64, 0},
        {"sparseResidencyAliased", f->sparseResidencyAliased, 0},
        {"sparseResidencyImage2D", f->sparseResidencyImage2D, 0},
        {"samplerAnisotropy", f->samplerAnisotropy, 0},
        {"depthClamp", f->depthClamp, 0},
        {"depthBiasClamp", f->depthBiasClamp, 0},
        {"sampleRateShading", f->sampleRateShading, 0},
        {"dualSrcBlend", f->dualSrcBlend, 0},
        {"logicOp", f->logicOp, 0},
        {"multiDrawIndirect", f->multiDrawIndirect, 0},
        {"drawIndirectFirstInstance", f->drawIndirectFirstInstance, 0},
        {"textureCompressionASTC_LDR", f->textureCompressionASTC_LDR, 0},
        {"textureCompressionETC2", f->textureCompressionETC2, 0},
        {"textureCompressionBC", f->textureCompressionBC, 0},
        {"shaderClipDistance", f->shaderClipDistance, 0},
        {"geometryShader", f->geometryShader, 0},
        {"tessellationShader", f->tessellationShader, 0},
        {"robustBufferAccess", f->robustBufferAccess, 0},
        /* not required, same as the 8-bit one below: without it metal2vulkan declares no u16[] view and moves
           halves and shorts through its word views (memory/leaf.rs Units::storage_on); Turnip has none on the
           a6xx gen1/gen2 Adrenos such as the 640 */
        {"storageBuffer16BitAccess", f11.storageBuffer16BitAccess, 0},
        {"uniformAndStorageBuffer16BitAccess", f11.uniformAndStorageBuffer16BitAccess, 0},
        {"multiview", f11.multiview, 0},
        {"samplerYcbcrConversion", f11.samplerYcbcrConversion, 0},
        {"shaderDrawParameters", f11.shaderDrawParameters, 0},
        {"shaderFloat16", f12.shaderFloat16, 1},
        {"shaderInt8", f12.shaderInt8, 1},
        /* not required: where it is missing metal2vulkan declares no u8[] view of a buffer and moves bytes
           through its word views (memory/leaf.rs Units::storage_on); Turnip has none on the Adreno 660 */
        {"storageBuffer8BitAccess", f12.storageBuffer8BitAccess, 0},
        {"timelineSemaphore", f12.timelineSemaphore, 1},
        {"bufferDeviceAddress", f12.bufferDeviceAddress, 1},
        {"descriptorIndexing", f12.descriptorIndexing, 1},
        {"runtimeDescriptorArray", f12.runtimeDescriptorArray, 1},
        {"descriptorBindingPartiallyBound", f12.descriptorBindingPartiallyBound, 1},
        {"descriptorBindingVariableDescriptorCount", f12.descriptorBindingVariableDescriptorCount, 0},
        {"descriptorBindingUpdateUnusedWhilePending", f12.descriptorBindingUpdateUnusedWhilePending, 0},
        {"shaderSampledImageArrayNonUniformIndexing", f12.shaderSampledImageArrayNonUniformIndexing, 0},
        {"shaderStorageBufferArrayNonUniformIndexing", f12.shaderStorageBufferArrayNonUniformIndexing, 0},
        {"scalarBlockLayout", f12.scalarBlockLayout, 1},
        {"uniformBufferStandardLayout", f12.uniformBufferStandardLayout, 0},
        {"vulkanMemoryModel", f12.vulkanMemoryModel, 0},
        {"shaderSubgroupExtendedTypes", f12.shaderSubgroupExtendedTypes, 0},
        {"separateDepthStencilLayouts", f12.separateDepthStencilLayouts, 0},
        {"hostQueryReset", f12.hostQueryReset, 0},
        {"imagelessFramebuffer", f12.imagelessFramebuffer, 0},
        {"samplerFilterMinmax", f12.samplerFilterMinmax, 0},
        {"drawIndirectCount", f12.drawIndirectCount, 0},
        {"shaderBufferInt64Atomics", f12.shaderBufferInt64Atomics, 0},
        {"synchronization2", f13.synchronization2, 0},
        {"dynamicRendering", f13.dynamicRendering, 0},
        {"maintenance4", f13.maintenance4, 0},
        {"subgroupSizeControl", f13.subgroupSizeControl, 0},
        {"computeFullSubgroups", f13.computeFullSubgroups, 0},
        {"shaderDemoteToHelperInvocation", f13.shaderDemoteToHelperInvocation, 0},
        {"robustImageAccess", f13.robustImageAccess, 0},
    };
    fprintf(out, "features:");
    for (size_t i = 0; i < sizeof feats / sizeof *feats; i++) {
        fprintf(out, " %s=%u", feats[i].name, feats[i].v);
    }
    fputc('\n', out);
    fflush(out);
    for (size_t i = 0; i < sizeof feats / sizeof *feats; i++) {
        if (!feats[i].v) {
            if (feats[i].required) {
                lack(feats[i].name);
            } else {
                say("recommended, absent: %s", feats[i].name);
            }
        }
    }

    vkGetPhysicalDeviceMemoryProperties(pd, &mp);
    for (uint32_t t = 0; t < mp.memoryTypeCount; t++) {
        say("memory type %u: flags %#x heap %u (%llu MiB)", t, mp.memoryTypes[t].propertyFlags, mp.memoryTypes[t].heapIndex,
            (unsigned long long)(mp.memoryHeaps[mp.memoryTypes[t].heapIndex].size >> 20));
    }
    uint32_t nq = 0;
    vkGetPhysicalDeviceQueueFamilyProperties(pd, &nq, NULL);
    VkQueueFamilyProperties qf[16];
    if (nq > 16) {
        nq = 16;
    }
    vkGetPhysicalDeviceQueueFamilyProperties(pd, &nq, qf);
    for (uint32_t i = 0; i < nq; i++) {
        say("queue family %u: flags %#x, %u queues", i, qf[i].queueFlags, qf[i].queueCount);
        VkQueueFlags gc = VK_QUEUE_GRAPHICS_BIT | VK_QUEUE_COMPUTE_BIT;
        if (gfx_family == UINT32_MAX && (qf[i].queueFlags & gc) == gc) {
            gfx_family = i;
        }
        if (sparse_family == UINT32_MAX && (qf[i].queueFlags & VK_QUEUE_SPARSE_BINDING_BIT)) {
            sparse_family = i;
        }
    }
    if (gfx_family == UINT32_MAX) {
        lack("a graphics + compute queue");
    }
    if (sparse_family == UINT32_MAX) {
        lack("a queue that binds sparse memory");
    }
    if (gfx_family == UINT32_MAX) {
        return 1;
    }

    /* the device, with what the tests use */
    float prio = 1;
    VkDeviceQueueCreateInfo qci[2] = {
        {.sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO, .queueFamilyIndex = gfx_family, .queueCount = 1, .pQueuePriorities = &prio},
        {.sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO, .queueFamilyIndex = sparse_family, .queueCount = 1, .pQueuePriorities = &prio}};
    uint32_t nqci = sparse_family != UINT32_MAX && sparse_family != gfx_family ? 2 : 1;
    const char *want[2];
    uint32_t nwant = 0;
    if (host_ext) {
        want[nwant++] = VK_EXT_EXTERNAL_MEMORY_HOST_EXTENSION_NAME;
    }
    VkPhysicalDeviceFeatures en = {.sparseBinding = f->sparseBinding, .sparseResidencyBuffer = f->sparseResidencyBuffer};
    VkDeviceCreateInfo dci = {.sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO, .queueCreateInfoCount = nqci, .pQueueCreateInfos = qci,
                              .enabledExtensionCount = nwant, .ppEnabledExtensionNames = want, .pEnabledFeatures = &en};
    r = vkCreateDevice(pd, &dci, NULL, &dev);
    say("device: vkCreateDevice VkResult %d", r);
    if (r != VK_SUCCESS) {
        lack("a device it can open (vkCreateDevice)");
        return 1;
    }
    DFN(vkGetDeviceQueue);
    DFN(vkCreateCommandPool);
    DFN(vkCreateFence);
    vkGetDeviceQueue(dev, gfx_family, 0, &gq);
    if (sparse_family != UINT32_MAX) {
        vkGetDeviceQueue(dev, sparse_family, 0, &sq);
    }
    VkCommandPoolCreateInfo cpi = {.sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO, .queueFamilyIndex = gfx_family};
    VkFenceCreateInfo fci = {.sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};
    if (vkCreateCommandPool(dev, &cpi, NULL, &pool) != VK_SUCCESS || vkCreateFence(dev, &fci, NULL, &fence) != VK_SUCCESS) {
        lack("a command pool and a fence");
        return 1;
    }
    say("test: compute");
    if (!test_compute()) {
        lack("compute work that comes out right");
    }
    say("test: render");
    if (!test_render()) {
        lack("a render pass that comes out right");
    }
    if (host_ext) {
        say("test: host memory");
        if (!test_host()) {
            lack("GPU access to the phone's own memory (host pointer import)");
        }
        if (sparse_family != UINT32_MAX && f->sparseBinding) {
            say("test: sparse gather");
            if (!test_sparse_buffer()) {
                lack("sparse binds from host memory");
            }
            say("test: sparse image");
            if (!test_sparse_image()) {
                say("recommended, absent: sparse linear images from host memory (heap textures are copied instead)");
            }
        }
    }
    if (turnip_mode) {
        kgsl_probe();
    }
    return failed;
}

JNIEXPORT jint JNICALL Java_com_asoft_ios_GpuCheck_probe(JNIEnv *env, jclass cls, jstring jloader, jstring jlog)
{
    (void)cls;
    const char *loader = (*env)->GetStringUTFChars(env, jloader, NULL);
    const char *log = (*env)->GetStringUTFChars(env, jlog, NULL);
    out = fopen(log, "a");
    if (!out) {
        return 3;
    }
    say("loader: %s", loader);
    int rc = check(loader);
    if (missing[0]) {
        say("missing: %s", missing);
    }
    say("result: %s", rc == 0 && !failed ? "pass" : "fail");
    fclose(out);
    (*env)->ReleaseStringUTFChars(env, jloader, loader);
    (*env)->ReleaseStringUTFChars(env, jlog, log);
    return rc == 0 && !failed ? 0 : 1;
}
