// Geminus CRT
// CRT suave: curvatura ligera, scanlines y mascara RGB de apertura.
// Un solo sample; no usa multipass.
precision highp float;

uniform sampler2D u_texture;
uniform vec4 u_texture_size;   // (1/w, 1/h, w, h)
uniform vec2 u_target_size;
varying vec2 v_texcoord;

void main()
{
    // Sin curvatura/recorte: la imagen CRT debe ocupar todo el panel tal
    // cual, solo con scanlines y mascara de fosforo.
    vec2 uv = v_texcoord;
    vec2 cc = uv * 2.0 - 1.0;

    vec3 col = texture2D(u_texture, uv).rgb;

    // Scanlines con onda triangular (mucho mas barata que sin()).
    float sy = fract(uv.y * 192.0);
    float scan = 0.80 + 0.20 * (1.0 - 2.0 * abs(sy - 0.5));

    // Mascara de apertura RGB (3 columnas de fosforo).
    float m = mod(gl_FragCoord.x, 3.0);
    vec3 mask = vec3(0.92);
    if (m < 1.0)      mask.r = 1.10;
    else if (m < 2.0) mask.g = 1.10;
    else              mask.b = 1.10;

    // Vineteado suave en los bordes.
    float vig = 1.0 - 0.10 * dot(cc, cc);
    col *= scan * mask * max(vig, 0.0);

    gl_FragColor = vec4(col, 1.0);
}
