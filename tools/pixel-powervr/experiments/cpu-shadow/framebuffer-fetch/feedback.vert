#version 450

void main() {
    const vec2 corners[3] = vec2[3](vec2(-1.0, -1.0), vec2(3.0, -1.0), vec2(-1.0, 3.0));
    float depth = gl_InstanceIndex < 2 ? 0.5 : 0.875;
    gl_Position = vec4(corners[gl_VertexIndex], depth, 1.0);
}
