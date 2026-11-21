#version 450

layout(push_constant) uniform Parameters {
    uint firstPrimitive;
} parameters;

layout(location = 0) flat out uint primitiveTag;

void main()
{
    const vec2 corners[3] = vec2[3](
        vec2(-1.0, -1.0), vec2(3.0, -1.0), vec2(-1.0, 3.0));
    gl_Position = vec4(corners[gl_VertexIndex % 3], 0.0, 1.0);
    primitiveTag = parameters.firstPrimitive + uint(gl_VertexIndex) / 3u;
}
