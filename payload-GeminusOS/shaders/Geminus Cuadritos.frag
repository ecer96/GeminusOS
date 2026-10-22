// Geminus Cuadritos
// Lineas horizontales y verticales formando cuadros, sin tocar el color.
precision highp float;

uniform sampler2D u_texture;
uniform vec4 u_texture_size;   // (1/w, 1/h, w, h)
uniform vec2 u_target_size;
varying vec2 v_texcoord;

void main()
{
    vec3 src = texture2D(u_texture, v_texcoord).rgb;

    // Cuadricula densa pero visible: lineas cada 3 pixeles de salida.
    float cell = 3.0;
    vec2 p = v_texcoord * u_target_size;
    vec2 f = fract(p / cell);
    float thick = 0.30;
    float lx = step(f.x, thick) + step(1.0 - thick, f.x);
    float ly = step(f.y, thick) + step(1.0 - thick, f.y);
    float line = clamp(lx + ly, 0.0, 1.0);

    // Lineas oscuras y un poco de brillo dentro del cuadro.
    float inside = 1.0 - line;
    vec3 col = src * (0.42 + 0.58 * inside);
    col += src * 0.04 * inside;

    gl_FragColor = vec4(col, 1.0);
}
