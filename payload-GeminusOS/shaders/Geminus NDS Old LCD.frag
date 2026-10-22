// Geminus NDS Old LCD
// NDS + rejilla LCD + color apagado/opaco de pantalla antigua.
precision highp float;

uniform sampler2D u_texture;
uniform vec4 u_texture_size;   // (1/w, 1/h, w, h)
uniform vec2 u_target_size;
varying vec2 v_texcoord;

void main()
{
    vec3 src = texture2D(u_texture, v_texcoord).rgb;

    // --- color de panel NDS antiguo ---
    src = src * (1.0 + 0.06 * (1.0 - src));
    float lum = dot(src, vec3(0.299, 0.587, 0.114));
    src = mix(vec3(lum), src, 0.80);          // desaturar
    src *= vec3(0.93, 0.98, 0.90);            // tono verdoso
    src = src * 0.86 + 0.025;                 // oscurecer y levantar negros
    src = clamp(src, 0.0, 1.0);

    // --- rejilla de 512x192, con cuadros ---
    vec2 p = v_texcoord * vec2(512.0, 192.0);
    vec2 f = fract(p);
    float edge = min(min(f.x, 1.0 - f.x), min(f.y, 1.0 - f.y));
    float grid = smoothstep(0.0, 0.22, edge);

    // --- subpixeles RGB suaves ---
    float s = fract(p.x * 3.0);
    vec3 mask = vec3(0.78);
    if (s < 0.3333)      mask.r = 1.0;
    else if (s < 0.6666) mask.g = 1.0;
    else                 mask.b = 1.0;

    vec3 col = src * (0.62 + 0.38 * mask) * (0.30 + 0.70 * grid);
    gl_FragColor = vec4(col, 1.0);
}
