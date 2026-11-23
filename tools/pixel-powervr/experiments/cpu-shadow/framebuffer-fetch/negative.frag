#version 450
layout(location = 0) out vec4 next_color;
void main() {
    next_color = vec4(-0.125, 0.5, 1.25, 0.25)
               + vec4(0.00048828125, 0.00048828125, 0.001953125, 0.03125);
}
