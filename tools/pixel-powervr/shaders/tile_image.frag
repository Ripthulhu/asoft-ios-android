#version 450
#extension GL_EXT_shader_tile_image : require

// Intentionally coherent: no noncoherent qualifier/execution mode. The test
// needs order between overlapping primitives inside one draw, not just draws.
layout(location = 0) tileImageEXT uattachmentEXT priorColor;
layout(location = 0) flat in uint primitiveTag;
layout(location = 0) out uvec4 nextColor;

void main()
{
    uvec4 prior = colorAttachmentReadEXT(priorColor);
    // R detects lost updates; G/B also depend on primitive order. These are
    // exact integer recurrences, with explicitly bounded RGBA8_UINT outputs.
    nextColor = uvec4((prior.r + 1u) & 255u,
                     (prior.g * 3u + primitiveTag + 1u) & 255u,
                     (prior.b * 5u + primitiveTag + 1u) & 255u,
                     255u);
}
