// Geminus NDS Grid
// Rejilla LCD del NDS: borde negro entre pixeles y subpixeles RGB.
// Un solo sample de textura; pensado para 2x + fast-forward.
precision highp float;

uniform sampler2D u_texture;
uniform vec4 u_texture_size;   // (1/w, 1/h, w, h)
uniform vec2 u_target_size;
varying vec2 v_texcoord;

void main()
{
    vec3 src = texture2D(u_texture, v_texcoord).rgb;

    // Las dos pantallas del NDS: 256x192 cada una, lado a lado.
    vec2 nds_res = vec2(512.0, 192.0);
    vec2 p = v_texcoord * nds_res;
    vec2 f = fract(p);

    // Borde de cada pixel LCD (se oscurece en los cuatro lados).
    float edge = min(min(f.x, 1.0 - f.x), min(f.y, 1.0 - f.y));
    float grid = smoothstep(0.0, 0.20, edge);

    // Subpixeles RGB verticales dentro de cada pixel del NDS.
    float s = fract(p.x * 3.0);
    vec3 mask = vec3(0.72);
    if (s < 0.3333)      mask.r = 1.0;
    else if (s < 0.6666) mask.g = 1.0;
    else                 mask.b = 1.0;

    // Un poco de brillo en el centro para que no quede demasiado oscuro.
    float glow = 0.84 + 0.16 * smoothstep(0.0, 0.35, edge);
    vec3 col = src * (0.58 + 0.42 * mask) * (0.34 + 0.66 * grid) * glow;

    gl_FragColor = vec4(col, 1.0);
}
